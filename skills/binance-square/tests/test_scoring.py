from datetime import datetime, timezone
from dataclasses import replace
from decimal import Decimal
from types import MappingProxyType
import unittest

from scanner.authors import AuthorProfile
from scanner.market import Candle, ContractRecord, MarketSnapshot, MarketSource, UNKNOWN
from scanner.opportunities import (
    ConsensusObservation,
    Direction,
    build_consensus_index,
    extract_signal,
)
from scanner.scoring import (
    ExecutionCostConfig,
    ExecutionReadinessStatus,
    RankBucket,
    build_opportunity_board,
    score_opportunity,
)
from scanner.square import StructuredPost


DECISION_AT = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)
SOURCE_CAPTURED_AT = datetime(2026, 8, 1, 7, 5, tzinfo=timezone.utc)


def ready_score_kwargs() -> dict[str, object]:
    return {
        "execution_costs": ExecutionCostConfig(
            fee_rate=Decimal("0.0004"),
            slippage_rate=Decimal("0.0005"),
            funding_rate=Decimal("0.0001"),
            depth_available=True,
        ),
        "source_detail_captured_at": SOURCE_CAPTURED_AT,
    }


def qualified_author(author_id: str = "qualified") -> AuthorProfile:
    return AuthorProfile(
        author_id=author_id,
        username=author_id,
        display_name=author_id,
        profile_url=f"https://www.binance.com/en/square/profile/{author_id}",
        visible_labels=("Futures Live Trading",),
        trading_days=500,
        duration_tier="A",
        public_live=True,
        leaderboard_tags=("30D Profit",),
        tier_status="A",
        follower_count=100,
        following_count=1,
        like_count=100,
        observed_at="2026-08-01T07:00:00Z",
    )


def post(content: str, *, post_id: str = "201", published_at: str = "2026-08-01T07:00:00Z") -> StructuredPost:
    return StructuredPost(
        post_id=post_id,
        post_url=f"https://www.binance.com/en/square/post/{post_id}",
        published_at=published_at,
        content=content,
        author_name="qualified",
        profile_url="https://www.binance.com/en/square/profile/qualified",
        profile_slug="qualified",
    )


def complete_long_post(symbol: str = "BTCUSDT") -> str:
    return (
        f"{symbol} LONG\nEntry: 62,900 - 63,100\nStop Loss: 61,800\n"
        "TP1: 65,000\nTP2: 66,000\n"
        "Invalidation: 4h close below support\nMomentum and structure agree."
    )


def candle(
    index: int, interval_ms: int, *, source: MarketSource, bullish: bool = True
) -> Candle:
    close = Decimal(62_000 + index * 50 if bullish else 64_000 - index * 50)
    volume = Decimal("60") if index == 20 else Decimal("10")
    return Candle(
        open_time=index * interval_ms,
        open=close - Decimal("10"),
        high=close + Decimal("20"),
        low=close - Decimal("20"),
        close=close,
        volume=volume if source is MarketSource.FUTURES else UNKNOWN,
        close_time=(index + 1) * interval_ms - 1,
        quote_volume=volume * close if source is MarketSource.FUTURES else UNKNOWN,
        number_of_trades=10,
        source=source,
        volume_unit="BASE_ASSET" if source is MarketSource.FUTURES else UNKNOWN,
    )


def market_snapshot(
    symbol: str = "BTCUSDT",
    *,
    source: MarketSource = MarketSource.FUTURES,
    bullish: bool = True,
) -> MarketSnapshot:
    intervals = {"15m": 900_000, "1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000}
    candles = MappingProxyType(
        {
            interval: tuple(
                candle(i, width, source=source, bullish=bullish) for i in range(21)
            )
            for interval, width in intervals.items()
        }
    )
    contract = ContractRecord(symbol, "TRADING", "PERPETUAL", symbol[:-4], "USDT", "USDT")
    unknown = UNKNOWN if source is MarketSource.SPOT_PROXY else Decimal("1")
    return MarketSnapshot(
        symbol=symbol,
        contract=contract,
        source=source,
        decision_time_ms=int(DECISION_AT.timestamp() * 1000),
        captured_at=DECISION_AT,
        last_price=Decimal("63000"),
        mark_price=unknown,
        index_price=unknown,
        funding_rate=unknown,
        open_interest=unknown,
        base_volume_24h=unknown,
        quote_volume_24h=unknown,
        candles=candles,
        missing_fields=() if source is MarketSource.FUTURES else ("mark_price", "base_volume_24h"),
        failures=(),
    )


class OpportunityScoringTests(unittest.TestCase):
    def test_complete_btc_long_has_fixed_100_point_breakdown_and_market_evidence(self) -> None:
        author = qualified_author()
        signal = extract_signal(post(complete_long_post()), author)

        result = score_opportunity(
            signal, author, market_snapshot(), **ready_score_kwargs()
        )

        self.assertEqual(25, result.score_breakdown.author_credibility)
        self.assertEqual(15, result.score_breakdown.post_completeness)
        self.assertEqual(10, result.score_breakdown.freshness)
        self.assertEqual(20, result.score_breakdown.trend_alignment)
        self.assertEqual(10, result.score_breakdown.market_confirmation)
        self.assertEqual(15, result.score_breakdown.risk_reward)
        self.assertEqual(0, result.score_breakdown.news_or_consensus)
        self.assertEqual(sum(result.score_breakdown.as_dict().values()), result.total_score)
        self.assertEqual(95, result.total_score)
        self.assertEqual(RankBucket.TOP, result.rank_bucket)
        self.assertEqual("APPLIED", result.cost_model_status)
        self.assertEqual(SOURCE_CAPTURED_AT, result.evidence_captured_at)
        self.assertEqual(Decimal("2.40025"), result.cost_adjusted_main_rr)
        self.assertTrue(result.execution_ready)
        self.assertEqual((), result.hard_gate_reasons)
        self.assertTrue(any(item.startswith("15m_trend=BULLISH") for item in result.evidence))
        self.assertTrue(any("1h_bb_percent_b=" in item for item in result.evidence))
        self.assertTrue(any("1h_volume_ratio=" in item for item in result.evidence))

    def test_top_fails_closed_to_watch_when_execution_costs_are_not_configured(self) -> None:
        author = qualified_author()
        signal = extract_signal(post(complete_long_post()), author)

        result = score_opportunity(signal, author, market_snapshot())

        self.assertEqual(RankBucket.WATCH, result.rank_bucket)
        self.assertEqual("NOT_CONFIGURED", result.execution_readiness_status)
        self.assertEqual("NOT_CONFIGURED", result.cost_model_status)
        self.assertIsNone(result.cost_adjusted_main_rr)
        self.assertFalse(result.execution_ready)
        self.assertEqual("EXECUTION_COSTS_NOT_CONFIGURED", result.waiting_condition)

    def test_applied_costs_below_net_two_r_downgrade_nominally_valid_top(self) -> None:
        author = qualified_author()
        signal = extract_signal(
            post(
                "BTCUSDT LONG\nEntry: 62,900 - 63,100\nStop Loss: 61,800\n"
                "TP1: 64,800\nTP2: 65,400\nInvalidation: below support"
            ),
            author,
        )

        result = score_opportunity(
            signal, author, market_snapshot(), **ready_score_kwargs()
        )

        self.assertEqual("APPLIED", result.cost_model_status)
        self.assertEqual("COST_ADJUSTED_RR_BELOW_MINIMUM", result.execution_readiness_status)
        self.assertLess(result.cost_adjusted_main_rr, Decimal("2"))
        self.assertEqual(RankBucket.WATCH, result.rank_bucket)
        self.assertFalse(result.execution_ready)

    def test_applied_costs_still_require_source_capture_time_for_top(self) -> None:
        author = qualified_author()
        signal = extract_signal(post(complete_long_post()), author)
        costs = ready_score_kwargs()["execution_costs"]

        result = score_opportunity(
            signal, author, market_snapshot(), execution_costs=costs
        )

        self.assertEqual("APPLIED", result.cost_model_status)
        self.assertEqual(RankBucket.WATCH, result.rank_bucket)
        self.assertEqual(
            "EVIDENCE_CAPTURE_TIMESTAMPS_NOT_CONFIGURED",
            result.waiting_condition,
        )

    def test_bollinger_squeeze_without_directional_breakout_is_downgraded_to_watch(self) -> None:
        author = qualified_author()
        signal = extract_signal(post(complete_long_post()), author)
        market = market_snapshot()
        squeezed = {}
        for interval, candles in market.candles.items():
            squeezed[interval] = tuple(
                replace(
                    value,
                    open=Decimal("63000") + index,
                    high=Decimal("63020") + index,
                    low=Decimal("62980") + index,
                    close=Decimal("63000") + index,
                )
                for index, value in enumerate(candles)
            )
        market = replace(market, candles=MappingProxyType(squeezed))

        result = score_opportunity(signal, author, market)

        self.assertEqual(RankBucket.WATCH, result.rank_bucket)
        self.assertEqual("BB_SQUEEZE_AWAITING_BREAKOUT", result.waiting_condition)
        self.assertIn("1h_bb_state=SQUEEZE_NO_BREAKOUT", result.evidence)

    def test_squeeze_with_volume_confirmed_band_breakout_can_remain_top(self) -> None:
        author = qualified_author()
        signal = extract_signal(post(complete_long_post()), author)
        market = market_snapshot()
        compressed_breakout = {}
        for interval, candles in market.candles.items():
            values = []
            for index, value in enumerate(candles):
                close = Decimal("63000") if index < 20 else Decimal("63200")
                values.append(
                    replace(
                        value,
                        open=close,
                        high=close + Decimal("20"),
                        low=close - Decimal("20"),
                        close=close,
                    )
                )
            compressed_breakout[interval] = tuple(values)
        market = replace(market, candles=MappingProxyType(compressed_breakout))

        result = score_opportunity(
            signal, author, market, **ready_score_kwargs()
        )

        self.assertEqual(RankBucket.TOP, result.rank_bucket)
        self.assertIn("1h_bb_state=SQUEEZE_BREAKOUT_CONFIRMED", result.evidence)

    def test_sol_long_short_conflict_below_ten_points_is_observation_only(self) -> None:
        author = qualified_author("sol-author")
        long_signal = extract_signal(
            post(
                "SOLUSDT LONG\nEntry: 62,900 - 63,100\nStop Loss: 61,800\n"
                "TP1: 65,000\nTP2: 66,000\nInvalidation: 4h close below support",
                post_id="sol-long",
            ),
            author,
        )
        short_signal = extract_signal(
            post(
                "SOLUSDT SHORT\nEntry: 62,900 - 63,100\nStop Loss: 64,200\n"
                "TP1: 61,100\nTP2: 60,000\nInvalidation: 4h close above resistance",
                post_id="sol-short",
            ),
            author,
        )
        long_result = score_opportunity(long_signal, author, market_snapshot("SOLUSDT"))
        short_market = market_snapshot("SOLUSDT", bullish=False)
        short_market = MarketSnapshot(
            symbol=short_market.symbol,
            contract=short_market.contract,
            source=short_market.source,
            decision_time_ms=short_market.decision_time_ms,
            captured_at=short_market.captured_at,
            last_price=Decimal("63000"),
            mark_price=short_market.mark_price,
            index_price=short_market.index_price,
            funding_rate=short_market.funding_rate,
            open_interest=short_market.open_interest,
            base_volume_24h=short_market.base_volume_24h,
            quote_volume_24h=short_market.quote_volume_24h,
            candles=short_market.candles,
            missing_fields=short_market.missing_fields,
            failures=short_market.failures,
        )
        short_result = score_opportunity(short_signal, author, short_market)

        board = build_opportunity_board((long_result, short_result))

        self.assertEqual((), board.top)
        self.assertEqual(1, len(board.watch))
        self.assertEqual("SOLUSDT", board.watch[0].symbol)
        self.assertIn("opposing_direction_margin=0", board.watch[0].conflict_evidence)

    def test_direction_conflict_aggregates_independent_authors_not_best_single_post(self) -> None:
        long_author = qualified_author("long-author")
        long_signal = extract_signal(
            post(complete_long_post(), post_id="long-a"), long_author
        )
        long_best = score_opportunity(
            long_signal,
            long_author,
            market_snapshot(),
            content_hash="long-cluster-a",
            **ready_score_kwargs(),
        )
        repeated_long_signal = replace(
            long_signal,
            signal_id="long-repeat",
            signal_family_id="long-repeat",
            post_id="long-repeat",
        )
        repeated_long = score_opportunity(
            repeated_long_signal,
            long_author,
            market_snapshot(),
            content_hash="long-cluster-b",
            **ready_score_kwargs(),
        )

        short_text = (
            "BTCUSDT SHORT\nEntry: 62,900 - 63,100\nStop Loss: 64,200\n"
            "TP1: 61,100\nTP2: 60,000\nInvalidation: above resistance"
        )
        short_market = market_snapshot(bullish=False)
        short_values = []
        for author_id, post_id, score in (
            ("short-author-b", "short-b", 85),
            ("short-author-c", "short-c", 84),
        ):
            short_author = qualified_author(author_id)
            short_signal = extract_signal(
                post(short_text, post_id=post_id), short_author
            )
            short_values.append(
                replace(
                    score_opportunity(
                        short_signal,
                        short_author,
                        short_market,
                        content_hash=f"{post_id}-cluster",
                        **ready_score_kwargs(),
                    ),
                    total_score=score,
                )
            )

        board = build_opportunity_board(
            (long_best, repeated_long, *short_values)
        )

        self.assertEqual(1, len(board.top))
        self.assertEqual(Direction.SHORT, board.top[0].direction)
        self.assertIn("leading_independent_support=2", board.top[0].conflict_evidence)
        self.assertIn("opposing_independent_support=1", board.top[0].conflict_evidence)

        copied_short = replace(
            short_values[1], content_hash=short_values[0].content_hash
        )
        copied_board = build_opportunity_board(
            (long_best, repeated_long, short_values[0], copied_short)
        )

        self.assertEqual(Direction.LONG, copied_board.top[0].direction)
        self.assertIn(
            "opposing_independent_support=1",
            copied_board.top[0].conflict_evidence,
        )

    def test_missing_tp_gets_partial_credit_but_is_not_execution_ready(self) -> None:
        author = qualified_author()
        signal = extract_signal(
            post(
                "BTCUSDT LONG\nEntry: 62,900 - 63,100\nStop Loss: 61,800\n"
                "Invalidation: 4h close below support"
            ),
            author,
        )

        result = score_opportunity(signal, author, market_snapshot())

        self.assertEqual(RankBucket.WATCH, result.rank_bucket)
        self.assertEqual(4, result.score_breakdown.risk_reward)
        self.assertNotIn("MISSING_TP1", result.hard_gate_reasons)
        self.assertEqual(
            ExecutionReadinessStatus.NOT_CONFIGURED,
            result.execution_readiness_status,
        )

    def test_no_active_contract_is_a_hard_filter(self) -> None:
        author = qualified_author()
        signal = extract_signal(post(complete_long_post()), author)

        result = score_opportunity(signal, author, None, decision_at=DECISION_AT)

        self.assertIn("NO_ACTIVE_FUTURES_CONTRACT", result.hard_gate_reasons)

    def test_signal_at_or_beyond_24_hours_is_expired(self) -> None:
        author = qualified_author()
        signal = extract_signal(
            post(complete_long_post(), published_at="2026-07-31T08:00:00Z"), author
        )

        result = score_opportunity(signal, author, market_snapshot())

        self.assertIn("SIGNAL_EXPIRED", result.hard_gate_reasons)

    def test_spot_proxy_never_receives_full_market_confirmation_points(self) -> None:
        author = qualified_author()
        signal = extract_signal(post(complete_long_post()), author)

        result = score_opportunity(
            signal, author, market_snapshot(source=MarketSource.SPOT_PROXY)
        )

        self.assertLess(result.score_breakdown.market_confirmation, 10)
        self.assertIn("source=SPOT_PROXY", "|".join(result.evidence))

    def test_unknown_author_is_not_scored_as_tier_a(self) -> None:
        signal = extract_signal(post(complete_long_post()), None)
        index = build_consensus_index(
            (
                ConsensusObservation("other", "BTCUSDT", Direction.LONG, "stable-other", "other-hash"),
            )
        )

        result = score_opportunity(
            signal,
            None,
            market_snapshot(),
            consensus_index=index,
            consensus_author_ids=("stable-other",),
        )

        self.assertEqual(0, result.score_breakdown.author_credibility)
        self.assertEqual(0, result.score_breakdown.news_or_consensus)

    def test_distinct_same_direction_author_adds_consensus_points(self) -> None:
        author = qualified_author()
        signal = extract_signal(post(complete_long_post()), author)

        result = score_opportunity(
            signal,
            author,
            market_snapshot(),
            consensus_author_ids=("other-author", "other-author"),
        )

        self.assertEqual(3, result.score_breakdown.news_or_consensus)

    def test_consensus_index_excludes_candidate_copy_cluster(self) -> None:
        author = qualified_author("author-a")
        signal = extract_signal(post(complete_long_post()), author)
        index = build_consensus_index(
            (
                ConsensusObservation(signal.signal_id, "BTCUSDT", Direction.LONG, "author-a", "same"),
                ConsensusObservation("copy", "BTCUSDT", Direction.LONG, "author-b", "same"),
                ConsensusObservation("independent", "BTCUSDT", Direction.LONG, "author-c", "different"),
            )
        )

        result = score_opportunity(
            signal,
            author,
            market_snapshot(),
            consensus_index=index,
            content_hash="same",
        )

        self.assertEqual(3, result.score_breakdown.news_or_consensus)
        self.assertIn("consensus_distinct_other_authors=1", result.evidence)

    def test_board_stably_caps_top_three_and_watch_five_without_padding(self) -> None:
        author = qualified_author()
        base = score_opportunity(
            extract_signal(post(complete_long_post()), author),
            author,
            market_snapshot(),
            **ready_score_kwargs(),
        )
        candidates = []
        for index in reversed(range(10)):
            symbol = f"A{index}USDT"
            candidate = replace(
                base.candidate,
                signal_id=f"{index}:{symbol}:LONG",
                signal_family_id=f"{index}:{symbol}:LONG",
                post_id=str(index),
                post_url=f"https://www.binance.com/en/square/post/{index}",
                symbol=symbol,
            )
            candidates.append(replace(base, candidate=candidate))

        board = build_opportunity_board(candidates)

        self.assertEqual(("A0USDT", "A1USDT", "A2USDT"), tuple(item.symbol for item in board.top))
        self.assertEqual(5, len(board.watch))
        self.assertEqual(2, len(board.filtered))

    def test_board_rechecks_cost_readiness_instead_of_trusting_claimed_top(self) -> None:
        author = qualified_author()
        ready = score_opportunity(
            extract_signal(post(complete_long_post()), author),
            author,
            market_snapshot(),
            **ready_score_kwargs(),
        )
        unsafe_claim = replace(
            ready,
            rank_bucket=RankBucket.TOP,
            waiting_condition=None,
            cost_model_status="NOT_CONFIGURED",
            execution_ready=False,
        )

        board = build_opportunity_board((unsafe_claim,))

        self.assertEqual((), board.top)
        self.assertEqual(1, len(board.watch))
        self.assertEqual(
            "EXECUTION_READINESS_NOT_APPLIED", board.watch[0].waiting_condition
        )


if __name__ == "__main__":
    unittest.main()
