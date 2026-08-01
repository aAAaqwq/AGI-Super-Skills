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
from scanner.scoring import RankBucket, build_opportunity_board, score_opportunity
from scanner.square import StructuredPost


DECISION_AT = datetime(2026, 8, 1, 8, 0, tzinfo=timezone.utc)


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

        result = score_opportunity(signal, author, market_snapshot())

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
        self.assertEqual((), result.hard_gate_reasons)
        self.assertTrue(any(item.startswith("15m_trend=BULLISH") for item in result.evidence))
        self.assertTrue(any("1h_bb_percent_b=" in item for item in result.evidence))
        self.assertTrue(any("1h_volume_ratio=" in item for item in result.evidence))

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

    def test_missing_tp_is_hard_filtered_even_when_other_evidence_is_strong(self) -> None:
        author = qualified_author()
        signal = extract_signal(
            post(
                "BTCUSDT LONG\nEntry: 62,900 - 63,100\nStop Loss: 61,800\n"
                "Invalidation: 4h close below support"
            ),
            author,
        )

        result = score_opportunity(signal, author, market_snapshot())

        self.assertEqual(RankBucket.FILTER, result.rank_bucket)
        self.assertIn("MISSING_TP1", result.hard_gate_reasons)

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


if __name__ == "__main__":
    unittest.main()
