from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
from types import MappingProxyType
import unittest

from scanner.authors import AuthorProfile
from scanner.derivation import (
    DerivationDisposition,
    DerivationSetup,
    apply_derivation_policy,
    derive_post_signal,
)
from scanner.market import Candle, ContractRecord, MarketSnapshot, MarketSource
from scanner.opportunities import ParameterSource, extract_signal
from scanner.square import StructuredPost


UTC = timezone.utc
DECISION_AT = datetime(2026, 8, 1, 8, 0, tzinfo=UTC)
DECISION_MS = int(DECISION_AT.timestamp() * 1000)


def author() -> AuthorProfile:
    return AuthorProfile(
        author_id="stable-author",
        username="route-alias",
        display_name="Evidence Author",
        profile_url="https://www.binance.com/en/square/profile/route-alias",
        visible_labels=(),
        trading_days=None,
        duration_tier="UNKNOWN",
        public_live=False,
        leaderboard_tags=(),
        tier_status="UNQUALIFIED",
        follower_count=None,
        following_count=None,
        like_count=None,
        observed_at="2026-08-01T07:00:00Z",
    )


def post(content: str, *, published_at: str = "2026-08-01T07:00:00Z") -> StructuredPost:
    return StructuredPost(
        post_id="derivation-post",
        post_url="https://www.binance.com/en/square/post/9001",
        published_at=published_at,
        content=content,
        author_name="Evidence Author",
        profile_url="https://www.binance.com/en/square/profile/route-alias",
        profile_slug="route-alias",
    )


def trend_candles(
    interval_ms: int,
    *,
    step: Decimal,
    breakout_retest: bool = False,
) -> tuple[Candle, ...]:
    values: list[Candle] = []
    for index in range(21):
        close = Decimal("100") + step * index
        high = close + Decimal("1")
        low = close - Decimal("1")
        if breakout_retest and index == 19:
            close, high, low = Decimal("106"), Decimal("107"), Decimal("104.5")
        if breakout_retest and index == 20:
            close, high, low = Decimal("105.5"), Decimal("106"), Decimal("104.5")
        open_time = DECISION_MS - (21 - index) * interval_ms
        values.append(
            Candle(
                open_time=open_time,
                open=close,
                high=high,
                low=low,
                close=close,
                volume=Decimal("20") if index == 20 else Decimal("10"),
                close_time=open_time + interval_ms - 1,
                quote_volume=Decimal("1000"),
                number_of_trades=10,
                source=MarketSource.FUTURES,
                volume_unit="BASE_ASSET",
            )
        )
    return tuple(values)


def complete_market(
    *,
    current_price: Decimal = Decimal("105"),
    breakout_retest: bool = False,
    bearish: bool = False,
    decision_time_ms: int = DECISION_MS,
    source: MarketSource = MarketSource.FUTURES,
    missing_fields: tuple[str, ...] = (),
) -> MarketSnapshot:
    sign = Decimal("-1") if bearish else Decimal("1")
    intervals = {
        "15m": trend_candles(900_000, step=sign * Decimal("0.25")),
        "1h": trend_candles(
            3_600_000,
            step=(
                Decimal("0.2")
                if breakout_retest
                else sign * Decimal("0.5")
            ),
            breakout_retest=breakout_retest,
        ),
        "4h": trend_candles(14_400_000, step=sign * Decimal("1")),
        "1d": trend_candles(86_400_000, step=sign * Decimal("1.2")),
    }
    if source is MarketSource.SPOT_PROXY:
        intervals = {
            name: tuple(
                Candle(
                    open_time=item.open_time,
                    open=item.open,
                    high=item.high,
                    low=item.low,
                    close=item.close,
                    volume="UNKNOWN",
                    close_time=item.close_time,
                    quote_volume="UNKNOWN",
                    number_of_trades=item.number_of_trades,
                    source=source,
                    volume_unit="UNKNOWN",
                )
                for item in candles
            )
            for name, candles in intervals.items()
        }
    contract = ContractRecord(
        "BTCUSDT", "TRADING", "PERPETUAL", "BTC", "USDT", "USDT"
    )
    unknown_or_value: Decimal | str = (
        "UNKNOWN" if source is MarketSource.SPOT_PROXY else Decimal("1")
    )
    return MarketSnapshot(
        symbol="BTCUSDT",
        contract=contract,
        source=source,
        decision_time_ms=decision_time_ms,
        captured_at=DECISION_AT,
        last_price=current_price,
        mark_price=unknown_or_value,
        index_price=unknown_or_value,
        funding_rate=unknown_or_value,
        open_interest=unknown_or_value,
        base_volume_24h=unknown_or_value,
        quote_volume_24h=unknown_or_value,
        candles=MappingProxyType(intervals),
        missing_fields=missing_fields,
        failures=(),
    )


class DerivationPolicyTests(unittest.TestCase):
    def test_valid_unmissed_author_plan_is_preserved(self) -> None:
        signal = extract_signal(
            post(
                "BTCUSDT LONG\nEntry: 103 - 105\nStop Loss: 100\n"
                "TP1: 112\nTP2: 121\nInvalidation: 4h structure breaks"
            ),
            author(),
        )

        result = apply_derivation_policy(signal, complete_market())

        self.assertEqual(DerivationDisposition.AUTHOR, result.disposition)
        self.assertIs(signal, result.candidate)
        self.assertEqual(("AUTHOR_PARAMETERS_VALID",), result.reasons)

    def test_author_plan_stopped_after_publication_cannot_revive_at_decision(self) -> None:
        signal = extract_signal(
            post(
                "BTCUSDT LONG\nEntry: 103 - 105\nStop Loss: 100\n"
                "TP1: 112\nTP2: 121\nInvalidation: 4h structure breaks"
            ),
            author(),
        )
        market = complete_market(current_price=Decimal("105"))
        replay = list(market.candles["15m"])
        stopped = replay[-3]
        replay[-3] = replace(
            stopped,
            open=Decimal("104"),
            high=Decimal("106"),
            low=Decimal("99"),
            close=Decimal("104"),
        )
        market = replace(
            market,
            candles=MappingProxyType({**market.candles, "15m": tuple(replay)}),
        )

        result = apply_derivation_policy(signal, market)

        self.assertEqual(DerivationDisposition.REJECTED, result.disposition)
        self.assertIn("AUTHOR_STOP_HIT_BEFORE_DECISION", result.reasons)

    def test_publication_candle_stop_touch_is_ambiguous_and_fails_closed(self) -> None:
        signal = extract_signal(
            post(
                "BTCUSDT LONG\nEntry: 103 - 105\nStop Loss: 100\n"
                "TP1: 112\nTP2: 121",
                published_at="2026-08-01T07:50:00Z",
            ),
            author(),
        )
        market = complete_market(current_price=Decimal("105"))
        replay = list(market.candles["15m"])
        overlap = replay[-1]
        replay[-1] = replace(overlap, low=Decimal("99"))
        market = replace(
            market,
            candles=MappingProxyType({**market.candles, "15m": tuple(replay)}),
        )

        result = apply_derivation_policy(signal, market)

        self.assertEqual(DerivationDisposition.REJECTED, result.disposition)
        self.assertIn("AUTHOR_STOP_HIT_BEFORE_DECISION", result.reasons)
        self.assertIn("PUBLICATION_CANDLE_PATH_AMBIGUOUS_ASSUMED_HIT", result.reasons)

    def test_candle_closing_exactly_at_decision_is_included_in_replay(self) -> None:
        signal = extract_signal(
            post(
                "BTCUSDT LONG\nEntry: 103 - 105\nStop Loss: 100\n"
                "TP1: 112\nTP2: 121"
            ),
            author(),
        )
        market = complete_market(current_price=Decimal("105"))
        replay = list(market.candles["15m"])
        decision_close = replay[-1]
        replay[-1] = replace(
            decision_close,
            low=Decimal("99"),
            close_time=DECISION_MS,
        )
        market = replace(
            market,
            candles=MappingProxyType({**market.candles, "15m": tuple(replay)}),
        )

        result = apply_derivation_policy(signal, market)

        self.assertIn("AUTHOR_STOP_HIT_BEFORE_DECISION", result.reasons)

    def test_author_stop_structure_requires_prepublication_closed_candles(self) -> None:
        signal = extract_signal(
            post(
                "BTCUSDT LONG\nEntry: 103 - 105\nStop Loss: 90\n"
                "TP1: 130\nTP2: 150",
                published_at="2026-08-01T03:00:00Z",
            ),
            author(),
        )

        result = apply_derivation_policy(signal, complete_market())

        self.assertEqual(DerivationDisposition.REJECTED, result.disposition)
        self.assertIn("AUTHOR_STOP_STRUCTURE_UNAVAILABLE", result.reasons)

    def test_author_plan_tp_hit_after_publication_cannot_revive_at_decision(self) -> None:
        signal = extract_signal(
            post(
                "BTCUSDT LONG\nEntry: 103 - 105\nStop Loss: 100\n"
                "TP1: 112\nTP2: 121"
            ),
            author(),
        )
        market = complete_market(current_price=Decimal("105"))
        replay = list(market.candles["15m"])
        reached = replay[-3]
        replay[-3] = replace(
            reached,
            open=Decimal("105"),
            high=Decimal("113"),
            low=Decimal("104"),
            close=Decimal("108"),
        )
        market = replace(
            market,
            candles=MappingProxyType({**market.candles, "15m": tuple(replay)}),
        )

        result = apply_derivation_policy(signal, market)

        self.assertEqual(DerivationDisposition.REJECTED, result.disposition)
        self.assertIn("AUTHOR_TP_HIT_BEFORE_DECISION", result.reasons)

    def test_same_candle_stop_and_tp_uses_conservative_stop_first_order(self) -> None:
        signal = extract_signal(
            post(
                "BTCUSDT LONG\nEntry: 103 - 105\nStop Loss: 100\n"
                "TP1: 112\nTP2: 121"
            ),
            author(),
        )
        market = complete_market(current_price=Decimal("105"))
        replay = list(market.candles["15m"])
        ambiguous = replay[-3]
        replay[-3] = replace(
            ambiguous,
            open=Decimal("104"),
            high=Decimal("113"),
            low=Decimal("99"),
            close=Decimal("108"),
        )
        market = replace(
            market,
            candles=MappingProxyType({**market.candles, "15m": tuple(replay)}),
        )

        result = apply_derivation_policy(signal, market)

        self.assertEqual(
            (
                "AUTHOR_STOP_HIT_BEFORE_DECISION",
                "SAME_CANDLE_STOP_AND_TP_ASSUMED_STOP_FIRST",
            ),
            result.reasons,
        )

    def test_author_stop_too_narrow_relative_to_atr_is_rejected_despite_high_rr(self) -> None:
        signal = extract_signal(
            post(
                "BTCUSDT LONG\nEntry: 103 - 105\nStop Loss: 103.9\n"
                "TP1: 112\nTP2: 121",
                published_at="2026-08-01T07:50:00Z",
            ),
            author(),
        )

        result = apply_derivation_policy(signal, complete_market())

        self.assertEqual(DerivationDisposition.REJECTED, result.disposition)
        self.assertIn("AUTHOR_STOP_TOO_NARROW_VS_ATR", result.reasons)

    def test_author_stop_inside_recent_market_structure_is_rejected(self) -> None:
        signal = extract_signal(
            post(
                "BTCUSDT LONG\nEntry: 103 - 105\nStop Loss: 102.9\n"
                "TP1: 112\nTP2: 121",
                published_at="2026-08-01T07:50:00Z",
            ),
            author(),
        )

        result = apply_derivation_policy(signal, complete_market())

        self.assertEqual(DerivationDisposition.REJECTED, result.disposition)
        self.assertIn("AUTHOR_STOP_INSIDE_RECENT_STRUCTURE", result.reasons)

    def test_missing_author_prices_are_rederived_as_pullback_with_exact_atr_buffer(self) -> None:
        signal = extract_signal(post("BTCUSDT LONG\nBullish continuation structure"), author())

        result = apply_derivation_policy(signal, complete_market())

        self.assertEqual(DerivationDisposition.SYSTEM_REDERIVED, result.disposition)
        self.assertEqual(DerivationSetup.PULLBACK, result.setup)
        self.assertIsNotNone(result.candidate)
        assert result.candidate is not None
        self.assertEqual(ParameterSource.SYSTEM_REDERIVED, result.candidate.parameter_source)
        self.assertEqual(Decimal("102.75"), result.candidate.entry_price)
        self.assertEqual(Decimal("101.95"), result.candidate.stop_loss)
        self.assertEqual(Decimal("111.0"), result.candidate.tp1)
        self.assertEqual(Decimal("121"), result.candidate.tp2)
        self.assertTrue(any("atr_buffer=0.4" in item for item in result.evidence))

    def test_breakout_retest_is_classified_separately(self) -> None:
        signal = extract_signal(post("BTCUSDT LONG\nBreakout continuation"), author())

        result = apply_derivation_policy(
            signal, complete_market(breakout_retest=True)
        )

        self.assertEqual(DerivationDisposition.SYSTEM_REDERIVED, result.disposition)
        self.assertEqual(DerivationSetup.BREAKOUT_RETEST, result.setup)

    def test_short_pullback_uses_mirrored_structure_stop_and_targets(self) -> None:
        signal = extract_signal(post("BTCUSDT SHORT\nBearish continuation"), author())

        result = apply_derivation_policy(
            signal,
            complete_market(current_price=Decimal("95"), bearish=True),
        )

        self.assertEqual(DerivationDisposition.SYSTEM_REDERIVED, result.disposition)
        assert result.candidate is not None
        self.assertEqual(Decimal("97.25"), result.candidate.entry_price)
        self.assertEqual(Decimal("98.05"), result.candidate.stop_loss)
        self.assertEqual(Decimal("89.0"), result.candidate.tp1)
        self.assertEqual(Decimal("79"), result.candidate.tp2)

    def test_expired_post_stale_market_and_spot_proxy_are_rejected(self) -> None:
        expired = extract_signal(
            post("BTCUSDT LONG", published_at="2026-07-31T08:00:00Z"), author()
        )
        stale_ms = DECISION_MS - 16 * 60 * 1000
        current = extract_signal(post("BTCUSDT LONG"), author())

        expired_result = apply_derivation_policy(expired, complete_market())
        stale_result = apply_derivation_policy(
            current, complete_market(decision_time_ms=stale_ms), decision_at=DECISION_AT
        )
        proxy_result = apply_derivation_policy(
            current,
            complete_market(
                source=MarketSource.SPOT_PROXY,
                missing_fields=("mark_price", "funding_rate"),
            ),
        )

        self.assertIn("POST_EXPIRED", expired_result.reasons)
        self.assertIn("STALE_MARKET_SNAPSHOT", stale_result.reasons)
        self.assertIn("INCOMPLETE_MARKET_SPOT_PROXY", proxy_result.reasons)
        self.assertTrue(all(not item.accepted for item in (expired_result, stale_result, proxy_result)))

    def test_main_target_reached_and_chasing_are_rejected(self) -> None:
        author_signal = extract_signal(
            post(
                "BTCUSDT LONG\nEntry: 103 - 105\nStop Loss: 100\n"
                "TP1: 112\nTP2: 121"
            ),
            author(),
        )
        incomplete = extract_signal(post("BTCUSDT LONG"), author())

        invalid = apply_derivation_policy(
            author_signal, complete_market(current_price=Decimal("122"))
        )
        chasing = apply_derivation_policy(
            incomplete, complete_market(current_price=Decimal("110"))
        )

        self.assertIn("AUTHOR_MAIN_TARGET_ALREADY_REACHED", invalid.reasons)
        self.assertIn("CURRENT_PRICE_TOO_EXTENDED", chasing.reasons)

    def test_ambiguous_direction_is_an_explicit_rejection(self) -> None:
        direction_result = derive_post_signal(
            post("BTCUSDT long or short around the range"), author(), complete_market()
        )
        symbol_result = derive_post_signal(
            post("BTCUSDT and ETHUSDT long around the range"), author(), complete_market()
        )

        for result in (direction_result, symbol_result):
            self.assertEqual(DerivationDisposition.REJECTED, result.disposition)
            self.assertIsNone(result.original_candidate)
            self.assertIn("AMBIGUOUS_OR_MISSING_SYMBOL_DIRECTION", result.reasons)


if __name__ == "__main__":
    unittest.main()
