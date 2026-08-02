from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import unittest

from scanner.contracts import ContractViolation
from scanner.opportunities import (
    Direction as OpportunityDirection,
    ParameterEvidenceSource,
    ParameterSource,
    SignalCandidate,
)
from scanner.scoring import RankBucket, ScoreBreakdown, ScoredOpportunity
from scanner.tracking import (
    AuthorObservation,
    Candle,
    Direction,
    ExecutionConfig,
    Outcome,
    TrackingSignal,
    aggregate_author_performance,
    deduplicate_signal_families,
    track_signal,
    tracking_signal_from_scored,
    tracking_signals_from_scored,
)


UTC = timezone.utc


def scored_opportunity(*, bucket: RankBucket = RankBucket.TOP) -> ScoredOpportunity:
    candidate = SignalCandidate(
        signal_id="scored-signal",
        signal_family_id="scored-family",
        post_id="post-1",
        post_url="https://www.binance.com/en/square/post/1",
        author_id="stable-author",
        symbol="BTCUSDT",
        direction=OpportunityDirection.LONG,
        entry_low=Decimal("99"),
        entry_high=Decimal("101"),
        entry_price=Decimal("100"),
        stop_loss=Decimal("95"),
        tp1=Decimal("107.5"),
        tp2=Decimal("110"),
        published_at="2026-08-01T00:00:00Z",
        invalidation="below structure",
        rationale="market structure",
        parameter_source=ParameterSource.AUTHOR,
        parameter_evidence_source=ParameterEvidenceSource.STRUCTURED_POST,
        source_class="SQUARE_UGC",
    )
    breakdown = ScoreBreakdown(25, 15, 10, 20, 10, 15, 0)
    return ScoredOpportunity(
        candidate=candidate,
        score_breakdown=breakdown,
        total_score=breakdown.total,
        rank_bucket=bucket,
        hard_gate_reasons=(),
        evidence=(),
        current_price=Decimal("100"),
        market_source=None,
        market_captured_at=None,
        missing_market_fields=(),
    )


class TrackingTests(unittest.TestCase):
    def test_publishable_scored_opportunity_converts_to_pure_tracking_signal(self) -> None:
        value = tracking_signal_from_scored(scored_opportunity())

        self.assertEqual("scored-signal", value.signal_id)
        self.assertEqual("stable-author", value.author_id)
        self.assertEqual(Direction.LONG, value.direction)
        self.assertEqual(datetime(2026, 8, 1, tzinfo=UTC), value.published_at)

    def test_tracking_conversion_rejects_filtered_and_deduplicates_families(self) -> None:
        top = scored_opportunity()
        later = replace(
            top,
            candidate=replace(
                top.candidate,
                signal_id="later",
                published_at="2026-08-01T01:00:00Z",
            ),
        )
        filtered = replace(top, rank_bucket=RankBucket.FILTER)

        with self.assertRaises(ContractViolation):
            tracking_signal_from_scored(filtered)
        converted = tracking_signals_from_scored((later, filtered, top))

        self.assertEqual(1, len(converted))
        self.assertEqual("scored-signal", converted[0].signal_id)

    def test_long_entry_zone_triggers_and_stop_is_minus_one_nominal_r(self) -> None:
        signal = TrackingSignal(
            signal_id="signal-1",
            signal_family_id="family-1",
            author_id="author-1",
            direction=Direction.LONG,
            entry_low=Decimal("99"),
            entry_high=Decimal("101"),
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            tp1=Decimal("107.5"),
            tp2=Decimal("110"),
            published_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
        candles = (
            Candle(
                observed_at=datetime(2026, 8, 1, 1, tzinfo=UTC),
                high=Decimal("102"),
                low=Decimal("99.5"),
                close=Decimal("101"),
            ),
            Candle(
                observed_at=datetime(2026, 8, 1, 2, tzinfo=UTC),
                high=Decimal("101"),
                low=Decimal("94"),
                close=Decimal("96"),
            ),
        )

        result = track_signal(signal, candles)

        self.assertEqual(Outcome.STOPPED, result.outcome)
        self.assertEqual(datetime(2026, 8, 1, 1, tzinfo=UTC), result.triggered_at)
        self.assertEqual(Decimal("-1"), result.r_value)
        self.assertEqual("NOMINAL_R", result.r_label)

    def test_short_tp1_is_initial_success_and_tracking_continues_to_tp2(self) -> None:
        signal = TrackingSignal(
            signal_id="signal-short",
            signal_family_id="family-short",
            author_id="author-1",
            direction=Direction.SHORT,
            entry_low=Decimal("99"),
            entry_high=Decimal("101"),
            entry_price=Decimal("100"),
            stop_loss=Decimal("105"),
            tp1=Decimal("92.5"),
            tp2=Decimal("90"),
            published_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
        candles = (
            Candle(datetime(2026, 8, 1, 1, tzinfo=UTC), Decimal("100"), Decimal("98"), Decimal("99")),
            Candle(datetime(2026, 8, 1, 2, tzinfo=UTC), Decimal("99"), Decimal("92"), Decimal("93")),
            Candle(datetime(2026, 8, 1, 3, tzinfo=UTC), Decimal("94"), Decimal("89"), Decimal("90")),
        )

        result = track_signal(signal, candles)

        self.assertEqual(Outcome.TP2_REACHED, result.outcome)
        self.assertTrue(result.tp1_reached)
        self.assertEqual(Decimal("2"), result.r_value)

    def test_same_candle_covering_stop_and_targets_is_conservatively_stopped(self) -> None:
        signal = TrackingSignal(
            signal_id="signal-ambiguous",
            signal_family_id="family-ambiguous",
            author_id="author-1",
            direction=Direction.LONG,
            entry_low=Decimal("99"),
            entry_high=Decimal("101"),
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            tp1=Decimal("107.5"),
            tp2=Decimal("110"),
            published_at=datetime(2026, 8, 1, tzinfo=UTC),
        )

        result = track_signal(
            signal,
            (
                Candle(
                    datetime(2026, 8, 1, 1, tzinfo=UTC),
                    Decimal("111"),
                    Decimal("94"),
                    Decimal("108"),
                ),
            ),
        )

        self.assertEqual(Outcome.STOPPED, result.outcome)
        self.assertFalse(result.tp1_reached)

    def test_entry_not_touched_within_24h_is_untriggered_not_a_loss(self) -> None:
        signal = TrackingSignal(
            signal_id="signal-expired",
            signal_family_id="family-expired",
            author_id="author-1",
            direction=Direction.LONG,
            entry_low=Decimal("99"),
            entry_high=Decimal("101"),
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            tp1=Decimal("107.5"),
            tp2=Decimal("110"),
            published_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
        candles = (
            Candle(datetime(2026, 8, 2, tzinfo=UTC), Decimal("105"), Decimal("102"), Decimal("103")),
            Candle(datetime(2026, 8, 2, 0, 1, tzinfo=UTC), Decimal("103"), Decimal("99"), Decimal("100")),
        )

        result = track_signal(signal, candles)

        self.assertEqual(Outcome.UNTRIGGERED, result.outcome)
        self.assertIsNone(result.triggered_at)
        self.assertIsNone(result.r_value)

    def test_triggered_signal_times_out_at_configured_author_period(self) -> None:
        signal = TrackingSignal(
            signal_id="signal-timeout",
            signal_family_id="family-timeout",
            author_id="author-1",
            direction=Direction.LONG,
            entry_low=Decimal("99"),
            entry_high=Decimal("101"),
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            tp1=Decimal("107.5"),
            tp2=Decimal("110"),
            published_at=datetime(2026, 8, 1, tzinfo=UTC),
            holding_period_hours=48,
        )
        candles = (
            Candle(datetime(2026, 8, 1, 1, tzinfo=UTC), Decimal("102"), Decimal("99"), Decimal("101")),
            Candle(datetime(2026, 8, 3, 1, tzinfo=UTC), Decimal("103"), Decimal("98"), Decimal("102")),
        )

        result = track_signal(signal, candles)

        self.assertEqual(Outcome.TIMEOUT, result.outcome)
        self.assertEqual(datetime(2026, 8, 3, 1, tzinfo=UTC), result.finalized_at)
        self.assertEqual(Decimal("0.4"), result.r_value)

    def test_mfe_and_mae_are_recorded_in_r_units_after_entry(self) -> None:
        signal = TrackingSignal(
            signal_id="signal-excursion",
            signal_family_id="family-excursion",
            author_id="author-1",
            direction=Direction.LONG,
            entry_low=Decimal("99"),
            entry_high=Decimal("101"),
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            tp1=Decimal("107.5"),
            tp2=Decimal("110"),
            published_at=datetime(2026, 8, 1, tzinfo=UTC),
            holding_period_hours=1,
        )
        candles = (
            Candle(datetime(2026, 8, 1, 1, tzinfo=UTC), Decimal("102"), Decimal("99"), Decimal("101")),
            Candle(datetime(2026, 8, 1, 2, tzinfo=UTC), Decimal("106"), Decimal("97"), Decimal("102")),
        )

        result = track_signal(signal, candles)

        self.assertEqual(Decimal("1.2"), result.mfe_r)
        self.assertEqual(Decimal("0.6"), result.mae_r)

    def test_complete_cost_and_exit_config_is_explicitly_labeled_net_r(self) -> None:
        signal = TrackingSignal(
            signal_id="signal-net",
            signal_family_id="family-net",
            author_id="author-1",
            direction=Direction.LONG,
            entry_low=Decimal("99"),
            entry_high=Decimal("101"),
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            tp1=Decimal("107.5"),
            tp2=Decimal("110"),
            published_at=datetime(2026, 8, 1, tzinfo=UTC),
        )
        costs = ExecutionConfig(
            entry_fee_rate=Decimal("0.001"),
            exit_fee_rate=Decimal("0.001"),
            entry_slippage_rate=Decimal("0.001"),
            exit_slippage_rate=Decimal("0.001"),
            tp1_exit_fraction=Decimal("0.5"),
        )
        candles = (
            Candle(datetime(2026, 8, 1, 1, tzinfo=UTC), Decimal("108"), Decimal("99"), Decimal("107")),
            Candle(datetime(2026, 8, 1, 2, tzinfo=UTC), Decimal("111"), Decimal("106"), Decimal("110")),
        )

        result = track_signal(signal, candles, execution_config=costs)

        self.assertEqual("NET_R", result.r_label)
        self.assertEqual(Decimal("1.66650175"), result.r_value)

    def test_signal_family_is_counted_once_using_earliest_publication(self) -> None:
        common = dict(
            signal_family_id="same-family",
            author_id="author-1",
            direction=Direction.LONG,
            entry_low=Decimal("99"),
            entry_high=Decimal("101"),
            entry_price=Decimal("100"),
            stop_loss=Decimal("95"),
            tp1=Decimal("107.5"),
            tp2=Decimal("110"),
        )
        later = TrackingSignal(signal_id="later", published_at=datetime(2026, 8, 2, tzinfo=UTC), **common)
        earlier = TrackingSignal(signal_id="earlier", published_at=datetime(2026, 8, 1, tzinfo=UTC), **common)

        unique = deduplicate_signal_families((later, earlier, earlier))

        self.assertEqual((earlier,), unique)

    def test_author_gate_uses_20_triggered_families_and_70_30_score(self) -> None:
        as_of = datetime(2026, 8, 1, tzinfo=UTC)
        observations = tuple(
            AuthorObservation(
                signal_family_id=f"old-{index}",
                author_id="author-1",
                finalized_at=datetime(2026, 5, 1, tzinfo=UTC),
                triggered=True,
                performance_score=Decimal("10"),
            )
            for index in range(10)
        ) + tuple(
            AuthorObservation(
                signal_family_id=f"recent-{index}",
                author_id="author-1",
                finalized_at=datetime(2026, 7, 15, tzinfo=UTC),
                triggered=True,
                performance_score=Decimal("20"),
            )
            for index in range(10)
        )

        aggregate = aggregate_author_performance("author-1", observations, as_of=as_of)

        self.assertEqual(20, aggregate.triggered_count)
        self.assertTrue(aggregate.eligible_for_tier_change)
        self.assertEqual(Decimal("20"), aggregate.score_60d)
        self.assertEqual(Decimal("15"), aggregate.score_lifetime)
        self.assertEqual(Decimal("18.5"), aggregate.score_final)

    def test_author_below_20_triggered_observations_is_capped_at_20_of_25(self) -> None:
        observations = tuple(
            AuthorObservation(
                signal_family_id=f"family-{index}",
                author_id="author-1",
                finalized_at=datetime(2026, 7, 15, tzinfo=UTC),
                triggered=True,
                performance_score=Decimal("25"),
            )
            for index in range(19)
        )

        aggregate = aggregate_author_performance(
            "author-1", observations, as_of=datetime(2026, 8, 1, tzinfo=UTC)
        )

        self.assertFalse(aggregate.eligible_for_tier_change)
        self.assertEqual(Decimal("20"), aggregate.score_for_ranking)

    def test_author_point_in_time_score_can_exclude_the_signal_being_evaluated(self) -> None:
        observations = (
            AuthorObservation(
                signal_family_id="prior-family",
                author_id="author-1",
                finalized_at=datetime(2026, 7, 15, tzinfo=UTC),
                triggered=True,
                performance_score=Decimal("10"),
            ),
            AuthorObservation(
                signal_family_id="current-family",
                author_id="author-1",
                finalized_at=datetime(2026, 7, 16, tzinfo=UTC),
                triggered=True,
                performance_score=Decimal("25"),
            ),
        )

        aggregate = aggregate_author_performance(
            "author-1",
            observations,
            as_of=datetime(2026, 8, 1, tzinfo=UTC),
            exclude_signal_family_ids=("current-family",),
        )

        self.assertEqual(1, aggregate.triggered_count)
        self.assertEqual(Decimal("10"), aggregate.score_final)


if __name__ == "__main__":
    unittest.main()
