import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_MARKDOWN = (
    "README.md",
    "README_CN.md",
    "ARCHITECTURE.md",
    "CONTEXT.md",
    "AGENTS.md",
    "STARTUP.md",
    "CLAUDE.md",
    "skills/README.md",
    "starter-kits/README.md",
    "cookbook/README.md",
    "plugins/README.md",
    "plugins/agi-super-team-codex/README.md",
    "config/README.md",
    "scripts/README.md",
    "tests/README.md",
    "docs/README.md",
    "docs/adr/README.md",
)
MARKDOWN_LINK = re.compile(r"!?\[[^]]*\]\(([^)]+)\)")


class NavigationContractTests(unittest.TestCase):
    def test_curated_markdown_relative_links_resolve(self) -> None:
        for relative in PUBLIC_MARKDOWN:
            source = ROOT / relative
            text = source.read_text(encoding="utf-8")
            for target in MARKDOWN_LINK.findall(text):
                target = target.strip().split(maxsplit=1)[0].strip("<>")
                if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                    continue
                route, _, fragment = target.partition("#")
                path = (source.parent / route).resolve()
                with self.subTest(source=relative, target=target):
                    self.assertTrue(path.exists())
                    if fragment:
                        index = path / "README.md" if path.is_dir() else path
                        content = index.read_text(encoding="utf-8")
                        self.assertIn(f'id="{fragment}"', content)

    def test_language_and_distribution_routes_are_bidirectional(self) -> None:
        english = (ROOT / "README.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README_CN.md").read_text(encoding="utf-8")
        self.assertIn("./README_CN.md", english)
        self.assertIn("./README.md", chinese)
        for text in (english, chinese):
            self.assertIn("docs/guides/claude-code-install.html", text)
            self.assertIn("docs/guides/harness-compatibility.html", text)

    def test_curated_entrypoints_reject_legacy_install_commands(self) -> None:
        forbidden = (
            "openclaw gateway start",
            "openclaw gateway restart",
            "cp -r skills/",
            "ln -s $(pwd)/skills/",
            "skills/categories/README.md",
        )
        for relative in PUBLIC_MARKDOWN:
            text = (ROOT / relative).read_text(encoding="utf-8")
            for value in forbidden:
                with self.subTest(source=relative, forbidden=value):
                    self.assertNotIn(value, text)


if __name__ == "__main__":
    unittest.main()
