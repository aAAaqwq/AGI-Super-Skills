import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReadmeContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.english = (ROOT / "README.md").read_text(encoding="utf-8")
        cls.chinese = (ROOT / "README_CN.md").read_text(encoding="utf-8")

    def test_readmes_define_the_product_and_its_boundary(self) -> None:
        self.assertIn("installable AI team packs", self.english)
        self.assertIn("not a model or an agent runtime", self.english)
        self.assertIn("可安装的 AI 团队包", self.chinese)
        self.assertIn("不是模型或 Agent 运行时", self.chinese)

    def test_readmes_include_a_truthful_installation_receipt(self) -> None:
        self.assertIn("## Five-minute installation receipt", self.english)
        self.assertIn("## 五分钟安装凭据", self.chinese)
        for readme in (self.english, self.chinese):
            self.assertIn("workspace-ceo/SOUL.md", readme)
            self.assertIn("workspace-pe/SOUL.md", readme)
            self.assertIn("workspace-cco/SOUL.md", readme)
            self.assertIn("Validation pending", readme)
            self.assertIn("mktemp -d", readme)

    def test_readmes_expose_repository_architecture_and_discovery(self) -> None:
        expected_headings = {
            self.english: ("## Explore", "## Repository architecture", "## Team topology"),
            self.chinese: ("## 探索仓库", "## 仓库架构", "## 团队拓扑"),
        }
        for readme, headings in expected_headings.items():
            for heading in headings:
                self.assertIn(heading, readme)
            self.assertIn("config/team-manifest.json", readme)
            self.assertIn("scripts/repository_model.py", readme)
            self.assertIn("config/external-skill-sources.json", readme)
            self.assertIn("./docs/guides/", readme)
            self.assertIn("./agents/", readme)
            self.assertIn("./cookbook/", readme)

    def test_readme_local_links_resolve(self) -> None:
        pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)|<img[^>]+src=\"([^\"]+)\"")
        for filename, readme in (("README.md", self.english), ("README_CN.md", self.chinese)):
            for match in pattern.finditer(readme):
                target = next(group for group in match.groups() if group)
                if target.startswith(("http://", "https://", "#")):
                    continue
                path = ROOT / target.split("#", 1)[0]
                with self.subTest(readme=filename, target=target):
                    self.assertTrue(path.exists())

    def test_linked_setup_and_catalog_docs_do_not_reintroduce_stale_claims(self) -> None:
        setup = (ROOT / "setup.md").read_text(encoding="utf-8")
        agents = (ROOT / "agents/README.md").read_text(encoding="utf-8")
        skills = (ROOT / "skills/README.md").read_text(encoding="utf-8")
        self.assertIn("Node.js", setup)
        self.assertIn("Python 3", setup)
        self.assertNotIn("optional skills named by the installer may not exist", setup)
        self.assertNotIn("Existing files were preserved", setup)
        self.assertNotIn("12 个 C-Suite", agents)
        self.assertNotIn("700+", agents)
        self.assertNotIn("cp -r agents/", agents)
        self.assertNotRegex(skills, r"\b(?:1,?639|1,?651|2,?659)\b")
        self.assertIn("config/team-manifest.json", skills)

    def test_distribution_metadata_uses_the_evidence_backed_positioning(self) -> None:
        metadata_paths = [
            ".claude-plugin/plugin.json",
            ".claude-plugin/marketplace.json",
            ".codex-plugin/plugin.json",
            ".cursor-plugin/plugin.json",
            ".kimi-plugin/plugin.json",
            "gemini-extension.json",
            "package.json",
        ]
        for relative_path in metadata_paths:
            text = (ROOT / relative_path).read_text(encoding="utf-8")
            with self.subTest(path=relative_path):
                self.assertIn("Evidence-backed", text)
                self.assertNotIn("legendary minds", text)
                self.assertNotRegex(text, r"\b1,651\b")

    def test_demo_is_labeled_as_an_illustration_not_runtime_evidence(self) -> None:
        demo = (ROOT / "assets/demo-install.txt").read_text(encoding="utf-8")
        for readme in (self.english, self.chinese):
            self.assertIn("storyboard", readme.lower())
        self.assertIn("Illustrative storyboard", demo)
        self.assertIn("--destination ./demo-workspace", demo)

    def test_linked_site_uses_the_canonical_solo_founder_roles(self) -> None:
        site = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        self.assertIn("CEO scopes the outcome, PE plans the implementation, and CCO", site)
        self.assertNotIn(
            "CEO scopes the outcome, Product Engineer builds it, and Governor",
            site,
        )


if __name__ == "__main__":
    unittest.main()
