"""Tests for cross-source linking."""

import sys
import unittest
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from lib import dedupe, schema


class TestCrossSourceLink(unittest.TestCase):
    def _make_reddit(self, id, title, score=50):
        item = schema.RedditItem(id=id, title=title, url="", subreddit="test")
        item.score = score
        return item

    def _make_hn(self, id, title, score=50):
        item = schema.HackerNewsItem(id=id, title=title, url="", hn_url="", author="user")
        item.score = score
        return item

    def _make_x(self, id, text, score=50):
        item = schema.XItem(id=id, text=text, url="", author_handle="user")
        item.score = score
        return item

    def _make_yt(self, id, title, score=50):
        item = schema.YouTubeItem(id=id, title=title, url="", channel_name="ch")
        item.score = score
        return item

    def _make_web(self, id, title, score=50):
        item = schema.WebSearchItem(id=id, title=title, url="", source_domain="example.com", snippet="")
        item.score = score
        return item

    def test_no_crossrefs_for_unrelated(self):
        reddit = [self._make_reddit("R1", "Best Claude Code Tips")]
        hn = [self._make_hn("HN1", "Python Django Release Notes")]
        dedupe.cross_source_link(reddit, hn)
        self.assertEqual(reddit[0].cross_refs, [])
        self.assertEqual(hn[0].cross_refs, [])

    def test_bidirectional_link(self):
        reddit = [self._make_reddit("R1", "OpenAI launches GPT-5 with new features")]
        hn = [self._make_hn("HN1", "OpenAI launches GPT-5 with new features")]
        dedupe.cross_source_link(reddit, hn)
        self.assertIn("HN1", reddit[0].cross_refs)
        self.assertIn("R1", hn[0].cross_refs)

    def test_multi_source_link(self):
        reddit = [self._make_reddit("R1", "Claude Code gets new skill system")]
        hn = [self._make_hn("HN1", "Claude Code gets new skill system")]
        yt = [self._make_yt("YT1", "Claude Code gets new skill system")]
        dedupe.cross_source_link(reddit, hn, yt)
        # All three should reference each other
        self.assertEqual(len(reddit[0].cross_refs), 2)
        self.assertEqual(len(hn[0].cross_refs), 2)
        self.assertEqual(len(yt[0].cross_refs), 2)

    def test_same_source_not_linked(self):
        reddit = [
            self._make_reddit("R1", "OpenAI GPT-5 launch details"),
            self._make_reddit("R2", "OpenAI GPT-5 launch details"),
        ]
        dedupe.cross_source_link(reddit)
        self.assertEqual(reddit[0].cross_refs, [])
        self.assertEqual(reddit[1].cross_refs, [])

    def test_x_text_truncation_helps(self):
        # Truncation increases similarity vs full tweet.
        # A near-identical short tweet should match a Reddit title.
        reddit = [self._make_reddit("R1", "Anthropic releases Claude 4 model")]
        x_short = [self._make_x("X1", "Anthropic releases Claude 4 model today!")]
        dedupe.cross_source_link(reddit, x_short)
        self.assertIn("X1", reddit[0].cross_refs)
        self.assertIn("R1", x_short[0].cross_refs)

    def test_long_x_text_may_not_match(self):
        # When a tweet diverges significantly after the shared prefix,
        # Jaccard drops below 0.5 even with truncation. This is expected.
        reddit = [self._make_reddit("R1", "Anthropic releases Claude 4 model")]
        x_long = [self._make_x("X1",
            "Anthropic releases Claude 4 model and it's incredible. "
            "The reasoning capabilities are next level. Just tested it "
            "on my entire codebase and it understood everything."
        )]
        dedupe.cross_source_link(reddit, x_long)
        # May or may not match depending on trigram overlap - just verify no crash
        self.assertIsInstance(reddit[0].cross_refs, list)

    def test_empty_lists(self):
        # Should not crash
        dedupe.cross_source_link([], [], [])

    def test_single_item(self):
        reddit = [self._make_reddit("R1", "Test item")]
        dedupe.cross_source_link(reddit)
        self.assertEqual(reddit[0].cross_refs, [])

    def test_no_duplicate_refs(self):
        reddit = [self._make_reddit("R1", "Same exact title repeated")]
        hn = [self._make_hn("HN1", "Same exact title repeated")]
        # Call twice - should not duplicate refs
        dedupe.cross_source_link(reddit, hn)
        dedupe.cross_source_link(reddit, hn)
        self.assertEqual(reddit[0].cross_refs.count("HN1"), 1)
        self.assertEqual(hn[0].cross_refs.count("R1"), 1)

    def test_web_items_linked(self):
        web = [self._make_web("W1", "Claude Code skill system overview")]
        hn = [self._make_hn("HN1", "Claude Code skill system overview")]
        dedupe.cross_source_link(web, hn)
        self.assertIn("HN1", web[0].cross_refs)
        self.assertIn("W1", hn[0].cross_refs)

    def _make_pm(self, id, title, score=50):
        item = schema.PolymarketItem(id=id, title=title, question="Q?", url="")
        item.score = score
        return item

    def test_polymarket_to_reddit_link(self):
        reddit = [self._make_reddit("R1", "Will Arizona win the Big 12 Championship?")]
        pm = [self._make_pm("PM1", "Will Arizona win the Big 12 Championship?")]
        dedupe.cross_source_link(reddit, pm)
        self.assertIn("PM1", reddit[0].cross_refs)
        self.assertIn("R1", pm[0].cross_refs)

    def test_polymarket_multi_source(self):
        reddit = [self._make_reddit("R1", "Iran nuclear deal prediction markets")]
        hn = [self._make_hn("HN1", "Iran nuclear deal prediction markets")]
        pm = [self._make_pm("PM1", "Iran nuclear deal prediction markets")]
        dedupe.cross_source_link(reddit, hn, pm)
        self.assertEqual(len(reddit[0].cross_refs), 2)
        self.assertEqual(len(pm[0].cross_refs), 2)


class TestCrossRefsSchemaRoundTrip(unittest.TestCase):
    def test_reddit_roundtrip(self):
        item = schema.RedditItem(id="R1", title="Test", url="", subreddit="test",
                                 cross_refs=["HN1", "X2"])
        d = item.to_dict()
        self.assertEqual(d['cross_refs'], ["HN1", "X2"])

    def test_reddit_empty_crossrefs_omitted(self):
        item = schema.RedditItem(id="R1", title="Test", url="", subreddit="test")
        d = item.to_dict()
        self.assertNotIn('cross_refs', d)

    def test_report_roundtrip(self):
        report = schema.Report(
            topic="test", range_from="2026-01-01", range_to="2026-02-01",
            generated_at="2026-02-01T00:00:00Z", mode="both",
            reddit=[schema.RedditItem(id="R1", title="T", url="", subreddit="s",
                                      cross_refs=["HN1"])],
            hackernews=[schema.HackerNewsItem(id="HN1", title="T", url="", hn_url="",
                                              author="u", cross_refs=["R1"])],
        )
        d = report.to_dict()
        restored = schema.Report.from_dict(d)
        self.assertEqual(restored.reddit[0].cross_refs, ["HN1"])
        self.assertEqual(restored.hackernews[0].cross_refs, ["R1"])


class TestGetCrossSourceText(unittest.TestCase):
    def test_x_truncated(self):
        item = schema.XItem(id="X1", text="A" * 200, url="", author_handle="u")
        result = dedupe._get_cross_source_text(item)
        self.assertEqual(len(result), 100)

    def test_reddit_uses_title(self):
        item = schema.RedditItem(id="R1", title="My Title", url="", subreddit="s")
        result = dedupe._get_cross_source_text(item)
        self.assertEqual(result, "My Title")

    def test_web_uses_title(self):
        item = schema.WebSearchItem(id="W1", title="Web Title", url="",
                                    source_domain="example.com", snippet="snip")
        result = dedupe._get_cross_source_text(item)
        self.assertEqual(result, "Web Title")


if __name__ == "__main__":
    unittest.main()
