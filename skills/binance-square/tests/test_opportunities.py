from decimal import Decimal
import unittest

from scanner.authors import AuthorProfile
from scanner.opportunities import (
    ConsensusObservation,
    Direction,
    ParameterEvidenceSource,
    build_consensus_index,
    calculate_risk_reward,
    extract_signal,
)
from scanner.contracts import ContractViolation
from scanner.square import StructuredPost


def author_profile(*, author_id: str = "author-btc") -> AuthorProfile:
    return AuthorProfile(
        author_id=author_id,
        username=author_id,
        display_name=author_id,
        profile_url=f"https://www.binance.com/en/square/profile/{author_id}",
        visible_labels=(),
        trading_days=None,
        duration_tier="UNKNOWN",
        public_live=False,
        leaderboard_tags=(),
        tier_status="UNQUALIFIED_UNKNOWN_TRADING_DURATION",
        follower_count=None,
        following_count=None,
        like_count=None,
        observed_at="2026-08-01T08:00:00Z",
    )


def structured_post(content: str, *, post_id: str = "101") -> StructuredPost:
    return StructuredPost(
        post_id=post_id,
        post_url=f"https://www.binance.com/en/square/post/{post_id}",
        published_at="2026-08-01T07:00:00Z",
        content=content,
        author_name="Evidence Author",
        profile_url="https://www.binance.com/en/square/profile/evidence-author",
        profile_slug="evidence-author",
    )


class StructuredSignalExtractionTests(unittest.TestCase):
    def test_real_structured_post_and_profile_produce_decimal_long_plan(self) -> None:
        post = structured_post(
            "BTCUSDT LONG\n"
            "Entry: 62,900 - 63,100\n"
            "Stop Loss: 61,800\n"
            "TP1: 65,000\n"
            "TP2: 66,000\n"
            "Invalidation: 4h close below support"
        )

        signal = extract_signal(post, author_profile())

        self.assertEqual("101:BTCUSDT:LONG", signal.signal_id)
        self.assertEqual(Direction.LONG, signal.direction)
        self.assertEqual(Decimal("62900"), signal.entry_low)
        self.assertEqual(Decimal("63100"), signal.entry_high)
        self.assertEqual(Decimal("63000"), signal.entry_price)
        self.assertEqual(Decimal("61800"), signal.stop_loss)
        self.assertEqual(Decimal("65000"), signal.tp1)
        self.assertEqual(Decimal("66000"), signal.tp2)
        self.assertEqual("AUTHOR", signal.parameter_source)
        self.assertEqual(
            ParameterEvidenceSource.STRUCTURED_POST, signal.parameter_evidence_source
        )

    def test_legacy_explicit_author_parameters_parse_short_ranges_and_rr(self) -> None:
        post = structured_post("SOL supply rejection", post_id="102")

        signal = extract_signal(
            post,
            author_profile(author_id="author-sol"),
            legacy_signal={
                "symbol": "SOL",
                "direction": "short",
                "entry": "72 - 74",
                "sl": "76",
                "tp": "69 / 66",
                "reasoning": "supply rejection",
            },
        )
        rr = calculate_risk_reward(signal)

        self.assertEqual(Direction.SHORT, signal.direction)
        self.assertEqual(Decimal("72"), signal.entry_low)
        self.assertEqual(Decimal("74"), signal.entry_high)
        self.assertEqual(Decimal("73"), signal.entry_price)
        self.assertEqual(Decimal("69"), signal.tp1)
        self.assertEqual(Decimal("66"), signal.tp2)
        self.assertEqual(ParameterEvidenceSource.LEGACY_EXPLICIT_INPUT, signal.parameter_evidence_source)
        self.assertEqual(Decimal("1.333333333333333333333333333"), rr.tp1_rr)
        self.assertEqual(Decimal("2.333333333333333333333333333"), rr.main_target_rr)

    def test_legacy_comma_grouped_prices_are_not_split_into_fake_targets(self) -> None:
        signal = extract_signal(
            structured_post("BTC plan", post_id="103"),
            author_profile(),
            legacy_signal={
                "symbol": "BTC", "direction": "long", "entry": "63,000",
                "sl": "61,800", "tp": "64,000 / 64,500 / 65,200",
            },
        )

        self.assertEqual(Decimal("63000"), signal.entry_price)
        self.assertEqual(Decimal("61800"), signal.stop_loss)
        self.assertEqual(Decimal("64000"), signal.tp1)
        self.assertEqual(Decimal("64500"), signal.tp2)

    def test_symbol_fallback_requires_an_explicit_ticker_marker(self) -> None:
        coti = extract_signal(
            structured_post("Setup long $COTI\nEntry: 0.0165", post_id="104"),
            author_profile(),
        )
        self.assertEqual("COTIUSDT", coti.symbol)

        with self.assertRaises(ContractViolation):
            extract_signal(
                structured_post("Markets remain high. Short covering continued.", post_id="105"),
                author_profile(),
            )


class ConsensusIndexTests(unittest.TestCase):
    def test_only_distinct_other_stable_authors_and_content_clusters_count(self) -> None:
        observations = (
            ConsensusObservation("self", "BTCUSDT", Direction.LONG, "author-a", "hash-self"),
            ConsensusObservation("copy", "BTCUSDT", Direction.LONG, "author-b", "hash-self"),
            ConsensusObservation("independent-b", "BTCUSDT", Direction.LONG, "author-b", "hash-b"),
            ConsensusObservation("independent-c", "BTCUSDT", Direction.LONG, "author-c", "hash-copied"),
            ConsensusObservation("copy-d", "BTCUSDT", Direction.LONG, "author-d", "hash-copied"),
            ConsensusObservation("self-again", "BTCUSDT", Direction.LONG, "author-a", "hash-a-2"),
            ConsensusObservation("unknown", "BTCUSDT", Direction.LONG, None, "hash-unknown"),
            ConsensusObservation("bad-live", "BTCUSDT", Direction.LONG, "LIVE", "hash-live"),
            ConsensusObservation("opposite", "BTCUSDT", Direction.SHORT, "author-z", "hash-z"),
        )

        index = build_consensus_index(reversed(observations))
        authors = index.other_author_ids(
            symbol="btcusdt",
            direction=Direction.LONG,
            author_id="author-a",
            content_hash="hash-self",
        )

        self.assertEqual(("author-b", "author-c"), authors)
        self.assertEqual(2, index.count_for(
            symbol="BTCUSDT",
            direction=Direction.LONG,
            author_id="author-a",
            content_hash="hash-self",
        ))

    def test_same_author_never_counts_itself_even_across_content_hashes(self) -> None:
        index = build_consensus_index(
            (
                ConsensusObservation("one", "SOLUSDT", Direction.SHORT, "same", "h1"),
                ConsensusObservation("two", "SOLUSDT", Direction.SHORT, "same", "h2"),
            )
        )

        self.assertEqual((), index.other_author_ids(
            symbol="SOLUSDT",
            direction=Direction.SHORT,
            author_id="same",
        ))


if __name__ == "__main__":
    unittest.main()
