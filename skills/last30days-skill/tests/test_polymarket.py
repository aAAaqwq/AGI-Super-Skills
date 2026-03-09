"""Tests for Polymarket prediction market source module."""

import json
import math
import sys
import unittest
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import polymarket, normalize, schema, score


class TestExtractCoreSubject(unittest.TestCase):
    def test_plain_topic(self):
        self.assertEqual(polymarket._extract_core_subject("Arizona Basketball"), "Arizona Basketball")

    def test_strips_last_n_days(self):
        self.assertEqual(polymarket._extract_core_subject("last 7 days Iran"), "Iran")

    def test_strips_what_are(self):
        result = polymarket._extract_core_subject("what are people saying about Bitcoin")
        self.assertEqual(result, "Bitcoin")

    def test_strips_tell_me_about(self):
        result = polymarket._extract_core_subject("tell me about Ukraine")
        self.assertEqual(result, "Ukraine")

    def test_strips_whitespace(self):
        self.assertEqual(polymarket._extract_core_subject("  Iran  "), "Iran")

    def test_empty_string(self):
        self.assertEqual(polymarket._extract_core_subject(""), "")


class TestExpandQueries(unittest.TestCase):
    def test_single_word(self):
        queries = polymarket._expand_queries("Iran")
        self.assertIn("Iran", queries)
        # Single word: no split, just the core
        self.assertEqual(len(queries), 1)

    def test_multi_word(self):
        queries = polymarket._expand_queries("Arizona Basketball")
        self.assertIn("Arizona Basketball", queries)
        self.assertIn("Arizona", queries)
        self.assertIn("Basketball", queries)
        self.assertEqual(len(queries), 3)

    def test_with_prefix_stripped(self):
        queries = polymarket._expand_queries("last 7 days Iran")
        self.assertIn("Iran", queries)
        # Full topic should also be included since it differs from core
        self.assertIn("last 7 days Iran", queries)

    def test_deduplication(self):
        queries = polymarket._expand_queries("Iran")
        # Should not have duplicates
        self.assertEqual(len(queries), len(set(q.lower() for q in queries)))

    def test_max_6_queries(self):
        queries = polymarket._expand_queries("some really long topic with many words")
        self.assertLessEqual(len(queries), 6)

    def test_all_words_included(self):
        queries = polymarket._expand_queries("Iran War")
        self.assertIn("Iran War", queries)
        self.assertIn("Iran", queries)
        self.assertIn("War", queries)
        self.assertEqual(len(queries), 3)

    def test_short_words_excluded(self):
        """Single-char words should not become standalone queries."""
        queries = polymarket._expand_queries("A new idea")
        # "A" is single char, should be excluded
        self.assertNotIn("A", queries)
        self.assertIn("new", queries)
        self.assertIn("idea", queries)


class TestExtractDomainQueries(unittest.TestCase):
    def _make_tag(self, label):
        return {"id": "1", "label": label, "slug": label.lower().replace(" ", "-")}

    def test_finds_frequent_tags(self):
        tag_ncaa = self._make_tag("NCAA CBB")
        tag_sport = self._make_tag("Sports")
        tag_bball = self._make_tag("Basketball")
        events = [
            {"title": "SEC Champion", "tags": [tag_ncaa, tag_sport, tag_bball]},
            {"title": "ACC Champion", "tags": [tag_ncaa, tag_sport, tag_bball]},
            {"title": "Big 12 Champion", "tags": [tag_ncaa, tag_sport, tag_bball]},
        ]
        result = polymarket._extract_domain_queries("Arizona Basketball", events)
        self.assertIn("NCAA CBB", result)

    def test_skips_generic_tags(self):
        tag_sport = self._make_tag("Sports")
        events = [
            {"title": "Event 1", "tags": [tag_sport]},
            {"title": "Event 2", "tags": [tag_sport]},
            {"title": "Event 3", "tags": [tag_sport]},
        ]
        result = polymarket._extract_domain_queries("test topic", events)
        self.assertNotIn("Sports", result)

    def test_skips_topic_word_tags(self):
        tag_bball = self._make_tag("Basketball")
        events = [
            {"title": "Event 1", "tags": [tag_bball]},
            {"title": "Event 2", "tags": [tag_bball]},
        ]
        result = polymarket._extract_domain_queries("Arizona Basketball", events)
        self.assertNotIn("Basketball", result)

    def test_requires_minimum_frequency(self):
        tag_a = self._make_tag("Unique Tag A")
        tag_b = self._make_tag("Unique Tag B")
        events = [
            {"title": "Event 1", "tags": [tag_a]},
            {"title": "Event 2", "tags": [tag_b]},
        ]
        result = polymarket._extract_domain_queries("test topic", events)
        self.assertEqual(result, [])

    def test_caps_at_two(self):
        tags = [self._make_tag(f"Tag {i}") for i in range(5)]
        events = [{"title": f"Event {i}", "tags": tags} for i in range(3)]
        result = polymarket._extract_domain_queries("test topic", events)
        self.assertLessEqual(len(result), 2)

    def test_empty_events(self):
        result = polymarket._extract_domain_queries("Arizona Basketball", [])
        self.assertEqual(result, [])

    def test_events_without_tags(self):
        events = [
            {"title": "Event 1"},
            {"title": "Event 2", "tags": None},
            {"title": "Event 3", "tags": []},
        ]
        result = polymarket._extract_domain_queries("test topic", events)
        self.assertEqual(result, [])


class TestFormatPriceMovement(unittest.TestCase):
    def test_significant_monthly_change(self):
        market = {
            "oneDayPriceChange": 0.005,
            "oneWeekPriceChange": -0.02,
            "oneMonthPriceChange": -0.117,
        }
        result = polymarket._format_price_movement(market)
        self.assertEqual(result, "down 11.7% this month")

    def test_significant_weekly_change(self):
        market = {
            "oneDayPriceChange": 0.01,
            "oneWeekPriceChange": 0.225,
            "oneMonthPriceChange": 0.15,
        }
        result = polymarket._format_price_movement(market)
        self.assertEqual(result, "up 22.5% this week")

    def test_significant_daily_change(self):
        market = {
            "oneDayPriceChange": -0.15,
            "oneWeekPriceChange": 0.02,
            "oneMonthPriceChange": 0.03,
        }
        result = polymarket._format_price_movement(market)
        self.assertEqual(result, "down 15.0% today")

    def test_no_significant_change(self):
        market = {
            "oneDayPriceChange": 0.005,
            "oneWeekPriceChange": -0.003,
            "oneMonthPriceChange": 0.002,
        }
        result = polymarket._format_price_movement(market)
        self.assertIsNone(result)

    def test_missing_fields(self):
        result = polymarket._format_price_movement({})
        self.assertIsNone(result)

    def test_none_values(self):
        market = {
            "oneDayPriceChange": None,
            "oneWeekPriceChange": None,
            "oneMonthPriceChange": None,
        }
        result = polymarket._format_price_movement(market)
        self.assertIsNone(result)


class TestParseOutcomePrices(unittest.TestCase):
    def test_binary_market_json_strings(self):
        market = {
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.65", "0.35"]',
        }
        result = polymarket._parse_outcome_prices(market)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ("Yes", 0.65))
        self.assertEqual(result[1], ("No", 0.35))

    def test_list_inputs(self):
        market = {
            "outcomes": ["Yes", "No"],
            "outcomePrices": ["0.70", "0.30"],
        }
        result = polymarket._parse_outcome_prices(market)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], ("Yes", 0.70))

    def test_multi_outcome(self):
        market = {
            "outcomes": '["Arizona", "Kansas", "Houston"]',
            "outcomePrices": '["0.35", "0.22", "0.18"]',
        }
        result = polymarket._parse_outcome_prices(market)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0][0], "Arizona")
        self.assertAlmostEqual(result[0][1], 0.35)

    def test_malformed_outcomes_json(self):
        market = {
            "outcomes": "not valid json",
            "outcomePrices": '["0.50", "0.50"]',
        }
        result = polymarket._parse_outcome_prices(market)
        # Should fall back to "Outcome N" names
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0][0], "Outcome 1")

    def test_malformed_prices_json(self):
        market = {
            "outcomes": '["Yes", "No"]',
            "outcomePrices": "not valid json",
        }
        result = polymarket._parse_outcome_prices(market)
        self.assertEqual(result, [])

    def test_missing_prices(self):
        market = {"outcomes": '["Yes", "No"]'}
        result = polymarket._parse_outcome_prices(market)
        self.assertEqual(result, [])

    def test_empty_outcomes(self):
        market = {
            "outcomes": "[]",
            "outcomePrices": '["0.50", "0.50"]',
        }
        result = polymarket._parse_outcome_prices(market)
        self.assertEqual(len(result), 2)
        # Should use fallback names
        self.assertEqual(result[0][0], "Outcome 1")


class TestParsePolymarketResponse(unittest.TestCase):
    def setUp(self):
        fixture_path = Path(__file__).parent.parent / "fixtures" / "polymarket_sample.json"
        with open(fixture_path) as f:
            self.sample = json.load(f)

    def test_parses_active_events(self):
        items = polymarket.parse_polymarket_response(self.sample)
        # Should include Arizona Big 12, Arizona NCAA, multi-outcome, and malformed
        # Should exclude: closed/resolved event and no-liquidity event
        titles = [item["title"] for item in items]
        self.assertIn("Will Arizona win the Big 12 Championship?", titles)
        self.assertIn("Will Arizona win the NCAA Tournament?", titles)
        self.assertIn("Who will win the Big 12 Tournament?", titles)

    def test_filters_closed_events(self):
        items = polymarket.parse_polymarket_response(self.sample)
        titles = [item["title"] for item in items]
        self.assertNotIn("Resolved Event (should be filtered)", titles)

    def test_filters_no_liquidity(self):
        items = polymarket.parse_polymarket_response(self.sample)
        titles = [item["title"] for item in items]
        self.assertNotIn("Dead market (no liquidity)", titles)

    def test_item_fields(self):
        items = polymarket.parse_polymarket_response(self.sample)
        item = items[0]  # Arizona Big 12
        self.assertEqual(item["event_id"], "evt-arizona-big12")
        self.assertEqual(item["url"], "https://polymarket.com/event/arizona-big-12-championship")
        self.assertIsNotNone(item["date"])
        self.assertIsNotNone(item["outcome_prices"])
        self.assertIsNotNone(item["volume24hr"])
        self.assertIsNotNone(item["liquidity"])

    def test_outcome_prices_parsed(self):
        items = polymarket.parse_polymarket_response(self.sample)
        item = items[0]  # Arizona Big 12 - binary
        self.assertEqual(len(item["outcome_prices"]), 2)
        self.assertEqual(item["outcome_prices"][0][0], "Yes")
        self.assertAlmostEqual(item["outcome_prices"][0][1], 0.64)

    def test_multi_outcome_top3(self):
        items = polymarket.parse_polymarket_response(self.sample)
        multi = [i for i in items if i["title"] == "Who will win the Big 12 Tournament?"][0]
        # Top 3 outcomes shown
        self.assertEqual(len(multi["outcome_prices"]), 3)
        # 5 total - 3 shown = 2 remaining
        self.assertEqual(multi["outcomes_remaining"], 2)

    def test_price_movement(self):
        items = polymarket.parse_polymarket_response(self.sample)
        item = items[0]  # Arizona Big 12
        # Weekly change (22.5%) is the most significant
        self.assertEqual(item["price_movement"], "up 22.5% this week")

    def test_date_extraction(self):
        items = polymarket.parse_polymarket_response(self.sample)
        item = items[0]
        self.assertEqual(item["date"], "2026-02-24")

    def test_relevance_range(self):
        items = polymarket.parse_polymarket_response(self.sample)
        for item in items:
            self.assertGreaterEqual(item["relevance"], 0.0)
            self.assertLessEqual(item["relevance"], 1.0)

    def test_empty_response(self):
        items = polymarket.parse_polymarket_response({"events": []})
        self.assertEqual(items, [])

    def test_missing_events_key(self):
        items = polymarket.parse_polymarket_response({})
        self.assertEqual(items, [])

    def test_malformed_prices_still_produces_item(self):
        items = polymarket.parse_polymarket_response(self.sample)
        malformed = [i for i in items if i["title"] == "Malformed prices"]
        self.assertEqual(len(malformed), 1)
        # Outcome prices should be empty due to malformed JSON
        self.assertEqual(malformed[0]["outcome_prices"], [])

    def test_end_date_extraction(self):
        items = polymarket.parse_polymarket_response(self.sample)
        item = items[0]  # Arizona Big 12
        self.assertEqual(item["end_date"], "2026-03-15")


class TestNormalizePolymarketItems(unittest.TestCase):
    def test_normalize(self):
        raw_items = [
            {
                "event_id": "evt-1",
                "title": "Test Market",
                "question": "Will test pass?",
                "url": "https://polymarket.com/event/test",
                "outcome_prices": [("Yes", 0.75), ("No", 0.25)],
                "outcomes_remaining": 0,
                "price_movement": "up 5.0% this week",
                "volume24hr": 100000.0,
                "liquidity": 500000.0,
                "date": "2026-02-20",
                "end_date": "2026-03-01",
                "relevance": 0.85,
                "why_relevant": "Prediction market: Test Market",
            }
        ]
        result = normalize.normalize_polymarket_items(raw_items, "2026-01-01", "2026-03-01")
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], schema.PolymarketItem)
        self.assertEqual(result[0].id, "PM1")
        self.assertEqual(result[0].title, "Test Market")
        self.assertEqual(result[0].question, "Will test pass?")
        self.assertEqual(result[0].date_confidence, "high")
        self.assertEqual(result[0].engagement.volume, 100000.0)
        self.assertEqual(result[0].engagement.liquidity, 500000.0)
        self.assertEqual(result[0].price_movement, "up 5.0% this week")

    def test_normalize_multiple(self):
        raw_items = [
            {
                "event_id": f"evt-{i}",
                "title": f"Market {i}",
                "question": f"Question {i}?",
                "url": f"https://polymarket.com/event/test-{i}",
                "outcome_prices": [],
                "outcomes_remaining": 0,
                "volume24hr": 0.0,
                "liquidity": 0.0,
                "date": "2026-02-20",
                "relevance": 0.5,
                "why_relevant": f"Market {i}",
            }
            for i in range(3)
        ]
        result = normalize.normalize_polymarket_items(raw_items, "2026-01-01", "2026-03-01")
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0].id, "PM1")
        self.assertEqual(result[1].id, "PM2")
        self.assertEqual(result[2].id, "PM3")


class TestScorePolymarketItems(unittest.TestCase):
    def test_score_items(self):
        items = [
            schema.PolymarketItem(
                id="PM1", title="High volume", question="Q1?", url="",
                date="2026-02-20",
                engagement=schema.Engagement(volume=500000.0, liquidity=2000000.0),
                relevance=0.9,
            ),
            schema.PolymarketItem(
                id="PM2", title="Low volume", question="Q2?", url="",
                date="2026-02-18",
                engagement=schema.Engagement(volume=100.0, liquidity=500.0),
                relevance=0.5,
            ),
        ]
        scored = score.score_polymarket_items(items)
        self.assertEqual(len(scored), 2)
        # High engagement + high relevance should score higher
        self.assertGreater(scored[0].score, scored[1].score)

    def test_score_empty(self):
        result = score.score_polymarket_items([])
        self.assertEqual(result, [])

    def test_engagement_formula(self):
        eng = schema.Engagement(volume=100000.0, liquidity=500000.0)
        result = score.compute_polymarket_engagement_raw(eng)
        self.assertIsNotNone(result)
        self.assertGreater(result, 0)
        # Verify formula: 0.60 * log1p(volume) + 0.40 * log1p(liquidity)
        expected = 0.60 * math.log1p(100000.0) + 0.40 * math.log1p(500000.0)
        self.assertAlmostEqual(result, expected)

    def test_engagement_none(self):
        result = score.compute_polymarket_engagement_raw(None)
        self.assertIsNone(result)

    def test_engagement_empty(self):
        eng = schema.Engagement()
        result = score.compute_polymarket_engagement_raw(eng)
        self.assertIsNone(result)

    def test_zero_volume(self):
        eng = schema.Engagement(volume=0.0, liquidity=0.0)
        result = score.compute_polymarket_engagement_raw(eng)
        self.assertIsNotNone(result)
        self.assertEqual(result, 0.0)


class TestSortItemsWithPolymarket(unittest.TestCase):
    def test_pm_priority_after_hn(self):
        """Polymarket should sort after HN at same score."""
        hn_item = schema.HackerNewsItem(id="HN1", title="test", url="", hn_url="", author="user")
        hn_item.score = 50

        pm_item = schema.PolymarketItem(id="PM1", title="test", question="test?", url="")
        pm_item.score = 50

        web_item = schema.WebSearchItem(id="W1", title="test", url="", source_domain="example.com", snippet="")
        web_item.score = 50

        sorted_items = score.sort_items([web_item, pm_item, hn_item])
        # Same score, so sorted by priority: HN(3) > PM(4) > Web(5)
        self.assertIsInstance(sorted_items[0], schema.HackerNewsItem)
        self.assertIsInstance(sorted_items[1], schema.PolymarketItem)
        self.assertIsInstance(sorted_items[2], schema.WebSearchItem)


class TestPolymarketSchemaRoundTrip(unittest.TestCase):
    def test_to_dict_and_back(self):
        item = schema.PolymarketItem(
            id="PM1",
            title="Test Event",
            question="Will test pass?",
            url="https://polymarket.com/event/test",
            outcome_prices=[("Yes", 0.75), ("No", 0.25)],
            outcomes_remaining=0,
            price_movement="up 5.0% this week",
            date="2026-02-20",
            engagement=schema.Engagement(volume=100000.0, liquidity=500000.0),
            end_date="2026-03-01",
            relevance=0.85,
            why_relevant="Test",
            cross_refs=["R1", "HN2"],
        )
        d = item.to_dict()
        self.assertEqual(d["id"], "PM1")
        self.assertEqual(d["title"], "Test Event")
        self.assertEqual(d["cross_refs"], ["R1", "HN2"])

    def test_empty_crossrefs_omitted(self):
        item = schema.PolymarketItem(id="PM1", title="Test", question="Q?", url="")
        d = item.to_dict()
        self.assertNotIn("cross_refs", d)

    def test_report_roundtrip_with_polymarket(self):
        report = schema.Report(
            topic="test", range_from="2026-01-01", range_to="2026-02-01",
            generated_at="2026-02-01T00:00:00Z", mode="both",
            polymarket=[schema.PolymarketItem(
                id="PM1", title="Test", question="Q?", url="",
                outcome_prices=[("Yes", 0.5), ("No", 0.5)],
                cross_refs=["R1"],
            )],
        )
        d = report.to_dict()
        restored = schema.Report.from_dict(d)
        self.assertEqual(len(restored.polymarket), 1)
        self.assertEqual(restored.polymarket[0].id, "PM1")
        self.assertEqual(restored.polymarket[0].cross_refs, ["R1"])

    def test_report_backward_compat_no_polymarket(self):
        """Old cached reports without polymarket key should load fine."""
        data = {
            "topic": "test",
            "range": {"from": "2026-01-01", "to": "2026-02-01"},
            "generated_at": "2026-02-01T00:00:00Z",
            "mode": "both",
            "reddit": [],
            "x": [],
            "web": [],
            "youtube": [],
            "hackernews": [],
            # No "polymarket" key
        }
        report = schema.Report.from_dict(data)
        self.assertEqual(report.polymarket, [])
        self.assertIsNone(report.polymarket_error)

    def test_engagement_volume_liquidity(self):
        eng = schema.Engagement(volume=342000.0, liquidity=2100000.0)
        d = eng.to_dict()
        self.assertEqual(d["volume"], 342000.0)
        self.assertEqual(d["liquidity"], 2100000.0)


class TestDepthConfig(unittest.TestCase):
    def test_quick_pages(self):
        self.assertEqual(polymarket.DEPTH_CONFIG["quick"], 1)

    def test_default_pages(self):
        self.assertEqual(polymarket.DEPTH_CONFIG["default"], 3)

    def test_deep_pages(self):
        self.assertEqual(polymarket.DEPTH_CONFIG["deep"], 4)

    def test_result_cap_quick(self):
        self.assertEqual(polymarket.RESULT_CAP["quick"], 5)

    def test_result_cap_default(self):
        self.assertEqual(polymarket.RESULT_CAP["default"], 15)

    def test_result_cap_deep(self):
        self.assertEqual(polymarket.RESULT_CAP["deep"], 25)


class TestTextSimilarity(unittest.TestCase):
    def test_exact_substring_match(self):
        score = polymarket._compute_text_similarity("Arizona", "Will Arizona win the NCAA Tournament?")
        self.assertEqual(score, 1.0)

    def test_full_topic_substring(self):
        score = polymarket._compute_text_similarity("Arizona Basketball", "Arizona Basketball Championship")
        self.assertEqual(score, 1.0)

    def test_partial_token_overlap(self):
        score = polymarket._compute_text_similarity("Arizona Basketball", "Will Arizona win?")
        # "Arizona" matches, "Basketball" doesn't -> 0.5
        self.assertAlmostEqual(score, 0.5)

    def test_no_overlap(self):
        score = polymarket._compute_text_similarity("Arizona Basketball", "Will AI regulation pass?")
        self.assertEqual(score, 0.0)

    def test_empty_topic(self):
        score = polymarket._compute_text_similarity("", "Will Arizona win?")
        self.assertEqual(score, 0.5)

    def test_case_insensitive(self):
        score = polymarket._compute_text_similarity("arizona", "ARIZONA Big 12")
        self.assertEqual(score, 1.0)

    def test_prefix_stripped(self):
        score = polymarket._compute_text_similarity("last 7 days Arizona", "Will Arizona win?")
        self.assertEqual(score, 1.0)

    def test_outcome_substring_match(self):
        """Topic 'Arizona' should match outcome 'Arizona' even when title has no overlap."""
        score = polymarket._compute_text_similarity(
            "Arizona",
            "Who will be the #1 overall seed?",
            outcomes=["Duke", "Arizona", "Houston"],
        )
        self.assertEqual(score, 0.85)

    def test_outcome_bidirectional_match(self):
        """Topic 'Arizona Basketball' should match outcome 'Arizona' (outcome in core)."""
        score = polymarket._compute_text_similarity(
            "Arizona Basketball",
            "Who will be the #1 overall seed?",
            outcomes=["Duke", "Arizona", "Houston"],
        )
        self.assertEqual(score, 0.85)

    def test_outcome_token_overlap(self):
        """Partial token overlap with outcome gets 0.7 when no substring match."""
        score = polymarket._compute_text_similarity(
            "Iran War",
            "Unrelated geopolitics title",
            outcomes=["War continues", "Peace deal"],
        )
        self.assertEqual(score, 0.7)

    def test_outcome_no_match(self):
        """No outcome match falls through to title token overlap."""
        score = polymarket._compute_text_similarity(
            "Arizona Basketball",
            "Will AI regulation pass in 2026?",
            outcomes=["Yes", "No"],
        )
        self.assertEqual(score, 0.0)

    def test_outcome_low_price_filtered_by_caller(self):
        """Outcomes with price <= 1% should be filtered by the caller, not this function."""
        # This function doesn't filter - it trusts the caller to pass only relevant outcomes
        score = polymarket._compute_text_similarity(
            "Arizona",
            "Unrelated title",
            outcomes=["Arizona"],
        )
        self.assertEqual(score, 0.85)

    def test_title_match_still_beats_outcome(self):
        """Title substring match (1.0) takes priority over outcome match (0.85)."""
        score = polymarket._compute_text_similarity(
            "Arizona",
            "Will Arizona win the tournament?",
            outcomes=["Arizona", "Duke"],
        )
        self.assertEqual(score, 1.0)

    def test_empty_outcomes(self):
        """Empty outcomes list falls through to title token overlap."""
        score = polymarket._compute_text_similarity(
            "Arizona Basketball",
            "Unrelated title",
            outcomes=[],
        )
        self.assertEqual(score, 0.0)

    def test_none_outcomes(self):
        """None outcomes falls through to title token overlap."""
        score = polymarket._compute_text_similarity(
            "Arizona Basketball",
            "Unrelated title",
            outcomes=None,
        )
        self.assertEqual(score, 0.0)


class TestQualityRanking(unittest.TestCase):
    """Verify quality-signal ranking: high-volume matching events rank above tangential ones."""

    def setUp(self):
        fixture_path = Path(__file__).parent.parent / "fixtures" / "polymarket_sample.json"
        with open(fixture_path) as f:
            self.sample = json.load(f)

    def test_topic_matching_ranks_above_tangential(self):
        """Arizona markets should rank above AI regulation when topic is 'Arizona Basketball'."""
        items = polymarket.parse_polymarket_response(self.sample, topic="Arizona Basketball")
        titles = [item["title"] for item in items]
        # Arizona events (including outcome-matched ones like NCAA seed) should come before tangential
        arizona_indices = [i for i, t in enumerate(titles) if "Arizona" in t or "Big 12" in t or "NCAA" in t]
        tangential_indices = [i for i, t in enumerate(titles) if "AI regulation" in t]
        if tangential_indices:
            self.assertTrue(max(arizona_indices) < min(tangential_indices),
                f"Arizona markets should rank above tangential. Order: {titles}")

    def test_high_volume_ranks_above_low_volume(self):
        """Among title-matched events, higher volume should rank higher."""
        items = polymarket.parse_polymarket_response(self.sample, topic="Arizona Basketball")
        # Arizona Big 12 Championship has $3.5M monthly volume, Arizona NCAA Tournament has $800K
        # Both have "Arizona" in the title (text_score=1.0), so volume breaks the tie
        big12 = [i for i, item in enumerate(items) if "Big 12 Championship" in item["title"]]
        ncaa_win = [i for i, item in enumerate(items) if item["title"] == "Will Arizona win the NCAA Tournament?"]
        if big12 and ncaa_win:
            self.assertLess(big12[0], ncaa_win[0],
                "Higher volume Big 12 Championship should rank above lower volume NCAA Tournament win")

    def test_result_cap_applied(self):
        """Parse should respect the _cap from search response."""
        capped_response = dict(self.sample)
        capped_response["_cap"] = 2
        items = polymarket.parse_polymarket_response(capped_response, topic="Arizona")
        self.assertLessEqual(len(items), 2)

    def test_no_topic_still_ranks(self):
        """Without a topic, relevance should still be computed from volume/liquidity."""
        items = polymarket.parse_polymarket_response(self.sample)
        self.assertTrue(len(items) > 0)
        for item in items:
            self.assertGreaterEqual(item["relevance"], 0.0)
            self.assertLessEqual(item["relevance"], 1.0)

    def test_relevance_sorted_descending(self):
        """Items should be sorted by relevance descending."""
        items = polymarket.parse_polymarket_response(self.sample, topic="Arizona Basketball")
        relevances = [item["relevance"] for item in items]
        self.assertEqual(relevances, sorted(relevances, reverse=True))

    def test_ncaa_seed_found_via_outcome_matching(self):
        """NCAA seed market should be found when Arizona is an outcome but not in title."""
        items = polymarket.parse_polymarket_response(self.sample, topic="Arizona Basketball")
        titles = [item["title"] for item in items]
        self.assertIn("Who will be the #1 overall seed in the 2026 NCAA Tournament?", titles)

    def test_ncaa_seed_ranks_above_tangential(self):
        """NCAA seed market (outcome match) should rank above AI regulation (no match)."""
        items = polymarket.parse_polymarket_response(self.sample, topic="Arizona Basketball")
        titles = [item["title"] for item in items]
        seed_idx = titles.index("Who will be the #1 overall seed in the 2026 NCAA Tournament?")
        tangential = [i for i, t in enumerate(titles) if "AI regulation" in t]
        if tangential:
            self.assertLess(seed_idx, tangential[0],
                f"NCAA seed should rank above tangential. Order: {titles}")

    def test_outcome_reordering_surfaces_topic(self):
        """Arizona should be surfaced to front of outcome_prices when topic matches."""
        items = polymarket.parse_polymarket_response(self.sample, topic="Arizona Basketball")
        seed_market = [i for i in items if "seed" in i["title"].lower()][0]
        # Arizona should be first in outcome_prices (reordered from position 2)
        self.assertEqual(seed_market["outcome_prices"][0][0], "Arizona")


class TestNormalizePolymarketVolume1mo(unittest.TestCase):
    """Verify normalization prefers volume1mo over volume24hr for engagement."""

    def test_volume1mo_preferred(self):
        raw_items = [
            {
                "event_id": "evt-1",
                "title": "Test",
                "question": "Q?",
                "url": "https://polymarket.com/event/test",
                "outcome_prices": [],
                "outcomes_remaining": 0,
                "volume24hr": 100.0,
                "volume1mo": 5000000.0,
                "liquidity": 1000.0,
                "date": "2026-02-20",
                "relevance": 0.8,
                "why_relevant": "Test",
            }
        ]
        result = normalize.normalize_polymarket_items(raw_items, "2026-01-01", "2026-03-01")
        # Engagement volume should be volume1mo (5M), not volume24hr (100)
        self.assertEqual(result[0].engagement.volume, 5000000.0)

    def test_fallback_to_volume24hr(self):
        raw_items = [
            {
                "event_id": "evt-1",
                "title": "Test",
                "question": "Q?",
                "url": "https://polymarket.com/event/test",
                "outcome_prices": [],
                "outcomes_remaining": 0,
                "volume24hr": 50000.0,
                "liquidity": 1000.0,
                "date": "2026-02-20",
                "relevance": 0.8,
                "why_relevant": "Test",
            }
        ]
        result = normalize.normalize_polymarket_items(raw_items, "2026-01-01", "2026-03-01")
        # No volume1mo, should fall back to volume24hr
        self.assertEqual(result[0].engagement.volume, 50000.0)


if __name__ == "__main__":
    unittest.main()
