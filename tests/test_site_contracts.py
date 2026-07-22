import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CANONICAL = "https://aaaaqwq.github.io/AGI-Super-Team/"


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.titles: list[str] = []
        self._title_parts: list[str] | None = None
        self.json_ld_parts: list[str] | None = None
        self.json_ld_documents: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {key: value or "" for key, value in attrs}
        self.tags.append((tag, attributes))
        if tag == "title":
            self._title_parts = []
        if tag == "script" and attributes.get("type") == "application/ld+json":
            self.json_ld_parts = []

    def handle_data(self, data: str) -> None:
        if self._title_parts is not None:
            self._title_parts.append(data)
        if self.json_ld_parts is not None:
            self.json_ld_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._title_parts is not None:
            self.titles.append("".join(self._title_parts).strip())
            self._title_parts = None
        if tag == "script" and self.json_ld_parts is not None:
            self.json_ld_documents.append("".join(self.json_ld_parts))
            self.json_ld_parts = None


class SiteContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (DOCS / "index.html").read_text(encoding="utf-8")
        cls.parser = SiteParser()
        cls.parser.feed(cls.html)

    def tag_attributes(self, tag_name: str) -> list[dict[str, str]]:
        return [attrs for tag, attrs in self.parser.tags if tag == tag_name]

    def test_homepage_has_unique_search_and_social_metadata(self) -> None:
        self.assertEqual(len(self.parser.titles), 1)
        self.assertGreaterEqual(len(self.parser.titles[0]), 30)
        metas = self.tag_attributes("meta")
        descriptions = [item for item in metas if item.get("name") == "description"]
        self.assertEqual(len(descriptions), 1)
        self.assertGreaterEqual(len(descriptions[0].get("content", "")), 70)
        canonical = [
            item
            for item in self.tag_attributes("link")
            if item.get("rel") == "canonical"
        ]
        self.assertEqual(canonical, [{"rel": "canonical", "href": CANONICAL}])
        properties = {item.get("property") for item in metas}
        names = {item.get("name") for item in metas}
        self.assertTrue({"og:title", "og:description", "og:image", "og:url"} <= properties)
        self.assertTrue({"twitter:card", "twitter:title", "twitter:description"} <= names)

    def test_json_ld_is_truthful_and_parseable(self) -> None:
        self.assertEqual(len(self.parser.json_ld_documents), 1)
        document = json.loads(self.parser.json_ld_documents[0])
        nodes = document.get("@graph", [])
        self.assertEqual({node.get("@type") for node in nodes}, {"WebSite", "SoftwareSourceCode"})
        serialized = json.dumps(document)
        self.assertNotRegex(serialized, r'"(stars|ratingValue|aggregateRating)"')
        self.assertNotIn("production-ready", serialized.lower())

    def test_homepage_has_accessible_structure(self) -> None:
        html_tags = self.tag_attributes("html")
        self.assertEqual(html_tags[0].get("lang"), "en")
        self.assertEqual(len(self.tag_attributes("h1")), 1)
        self.assertEqual(len(self.tag_attributes("main")), 1)
        self.assertGreaterEqual(len(self.tag_attributes("nav")), 1)
        anchors = self.tag_attributes("a")
        self.assertTrue(any(item.get("href") == "#main-content" for item in anchors))
        self.assertTrue(any(item.get("href", "").endswith("README_CN.md") for item in anchors))
        statuses = [item for item in self.tag_attributes("span") if item.get("role") == "status"]
        self.assertGreaterEqual(len(statuses), 2)
        table_headers = self.tag_attributes("th")
        self.assertTrue(table_headers)
        self.assertTrue(all(item.get("scope") in {"col", "row"} for item in table_headers))

    def test_homepage_uses_same_origin_data_and_no_stale_claims(self) -> None:
        script = (DOCS / "assets/site.js").read_text(encoding="utf-8")
        site_source = self.html + script
        self.assertIn("data/repo-stats.json", site_source)
        self.assertIn("data/star-history.json", site_source)
        lowered = site_source.lower()
        self.assertNotIn("api.star-history.com", lowered)
        self.assertNotIn("blob/master", lowered)
        self.assertNotIn("1,639", self.html)
        self.assertNotRegex(self.html, r">\s*73\s*<")
        self.assertNotRegex(self.html, r">\s*16\s*<")
        self.assertNotIn("verified outcome", lowered)
        self.assertNotIn("real outcomes", lowered)
        self.assertNotIn("Install for Codex", self.html)
        self.assertIn("--destination /path/to/review-workspace", self.html)

    def test_homepage_copy_uses_disciplined_punctuation_and_labels(self) -> None:
        self.assertNotRegex(self.html, r"[—–•]")
        self.assertNotIn("60-second", self.html)
        self.assertIn("Preview Solo Founder", self.html)
        self.assertIn("Inspect Codex package", self.html)

    def test_site_routes_and_sitemap_are_present(self) -> None:
        required = [
            DOCS / "verification.html",
            DOCS / "404.html",
            DOCS / "robots.txt",
            DOCS / "sitemap.xml",
            DOCS / "assets/site.css",
            DOCS / "assets/site.js",
        ]
        for path in required:
            with self.subTest(path=path.name):
                self.assertTrue(path.is_file())
        sitemap = (DOCS / "sitemap.xml").read_text(encoding="utf-8")
        urls = re.findall(r"<loc>([^<]+)</loc>", sitemap)
        self.assertEqual(len(urls), len(set(urls)))
        self.assertIn(CANONICAL, urls)
        for url in urls:
            parsed = urlparse(url)
            self.assertEqual(parsed.netloc, "aaaaqwq.github.io")
            self.assertTrue(parsed.path.startswith("/AGI-Super-Team/"))

    def test_editorial_guides_are_unique_self_canonical_and_in_sitemap(self) -> None:
        guide_paths = sorted((DOCS / "guides").glob("*.html"))
        self.assertEqual(len(guide_paths), 8)
        sitemap = (DOCS / "sitemap.xml").read_text(encoding="utf-8")
        sitemap_urls = set(re.findall(r"<loc>([^<]+)</loc>", sitemap))
        titles: set[str] = set()
        descriptions: set[str] = set()
        headings: set[str] = set()

        for path in guide_paths:
            with self.subTest(guide=path.name):
                html = path.read_text(encoding="utf-8")
                parser = SiteParser()
                parser.feed(html)
                self.assertEqual(len(parser.titles), 1)
                title = parser.titles[0]
                self.assertGreaterEqual(len(title), 30)
                self.assertNotIn(title, titles)
                titles.add(title)

                metas = [attrs for tag, attrs in parser.tags if tag == "meta"]
                description_tags = [
                    item for item in metas if item.get("name") == "description"
                ]
                self.assertEqual(len(description_tags), 1)
                description = description_tags[0].get("content", "")
                self.assertGreaterEqual(len(description), 70)
                self.assertNotIn(description, descriptions)
                descriptions.add(description)

                h1_tags = [attrs for tag, attrs in parser.tags if tag == "h1"]
                self.assertEqual(len(h1_tags), 1)
                heading_match = re.search(r"<h1>(.*?)</h1>", html, re.DOTALL)
                self.assertIsNotNone(heading_match)
                heading = re.sub(r"<[^>]+>", "", heading_match.group(1)).strip()
                self.assertNotIn(heading, headings)
                headings.add(heading)

                expected_url = (
                    f"{CANONICAL}guides/"
                    if path.name == "index.html"
                    else f"{CANONICAL}guides/{path.name}"
                )
                canonical_tags = [
                    attrs
                    for tag, attrs in parser.tags
                    if tag == "link" and attrs.get("rel") == "canonical"
                ]
                self.assertEqual(
                    canonical_tags,
                    [{"rel": "canonical", "href": expected_url}],
                )
                self.assertIn(expected_url, sitemap_urls)
                self.assertIn("Last reviewed: 2026-07-21", html)
                self.assertIn("Limitations", html)
                self.assertRegex(html, r"Rollback(?: and uninstall)?")
                self.assertEqual(html.count('class="button button-primary"'), 1)
                self.assertNotIn("production-ready", html.lower())
                self.assertNotRegex(
                    html,
                    r"\b(?:727|793|819|1,639|1,651|2,659) skills\b",
                )

    def test_progressive_enhancement_avoids_html_injection(self) -> None:
        script = (DOCS / "assets/site.js").read_text(encoding="utf-8")
        self.assertNotIn("innerHTML", script)
        self.assertIn("AbortController", script)
        self.assertIn("textContent", script)
        self.assertIn("localStorage", script)
        self.assertIn("fifteenMinutes", script)
        self.assertIn("Older than 24 hours", script)
        self.assertNotRegex(script, r"stargazers_count\s*\|\|\s*0")
        self.assertIn('root.classList.add("js")', script)
        stylesheet = (DOCS / "assets/site.css").read_text(encoding="utf-8")
        self.assertIn(".js .primary-nav", stylesheet)


if __name__ == "__main__":
    unittest.main()
