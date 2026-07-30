import json
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
        self.assertIn("An organized, installable team of Agents + Skills", self.english)
        self.assertIn("not a Codex-only plugin", self.english)
        self.assertIn("not a model, autonomous orchestrator, or agent runtime", self.english)
        self.assertIn("有组织、可安装的 Agents + Skills 团队系统", self.chinese)
        self.assertIn("不是 Codex 专属插件", self.chinese)
        self.assertIn("不是模型、自治编排器或 Agent 运行时", self.chinese)
        for framework in ("Claude Code", "Codex", "OpenClaw", "Hermes"):
            self.assertIn(framework, self.english)
            self.assertIn(framework, self.chinese)

    def test_readmes_expose_all_manifest_outcome_teams(self) -> None:
        manifest = json.loads((ROOT / "config/team-manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["kits"]), 8)
        starter_index = (ROOT / "starter-kits/README.md").read_text(encoding="utf-8")
        for kit in manifest["kits"]:
            kit_path = f"starter-kits/{kit['id']}/"
            self.assertIn(kit_path, self.english)
            self.assertIn(kit_path, self.chinese)
            self.assertIn(f"./{kit['id']}/RUNBOOK.md", starter_index)

    def test_readmes_lead_with_value_before_boundaries(self) -> None:
        for readme, value_heading, boundary_heading, flow_marker in (
            (
                self.english,
                "## 🧠 The system in one minute",
                "## 🛡️ Boundaries and human approval",
                "Coordinator scopes",
            ),
            (
                self.chinese,
                "## 🧠 一分钟理解整个系统",
                "## 🛡️ 边界与人工批准",
                "协调者界定范围",
            ),
        ):
            self.assertLess(readme.index(value_heading), readme.index(boundary_heading))
            self.assertNotIn("Three constraints make the project different", readme)
            self.assertNotIn("项目有三项核心约束", readme)
            self.assertIn(flow_marker, readme)

    def test_readmes_include_a_truthful_installation_receipt(self) -> None:
        self.assertIn("## 🧾 Reproducible installation receipt", self.english)
        self.assertIn("## 🧾 可复现安装凭据", self.chinese)
        for readme in (self.english, self.chinese):
            self.assertIn("workspace-ceo/SOUL.md", readme)
            self.assertIn("workspace-pe/SOUL.md", readme)
            self.assertIn("workspace-cco/SOUL.md", readme)
            self.assertIn("Validation pending", readme)
            self.assertIn("mktemp -d", readme)
            self.assertIn("npm run check:skills", readme)

    def test_readmes_expose_repository_architecture_and_discovery(self) -> None:
        expected_headings = {
            self.english: (
                "## 🧭 Browse skills by outcome",
                "## 🗂️ Repository architecture",
                "## 🧠 Team topology",
            ),
            self.chinese: (
                "## 🧭 按成果浏览技能",
                "## 🗂️ 仓库架构",
                "## 🧠 团队拓扑",
            ),
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
            self.assertIn("./catalog/", readme)
            self.assertIn("./ARCHITECTURE.md", readme)

    def test_legacy_entrypoints_route_to_current_authorities(self) -> None:
        startup = (ROOT / "STARTUP.md").read_text(encoding="utf-8")
        agent_context = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        for text in (startup, agent_context):
            self.assertIn("setup.md", text)
            self.assertIn(".codex/INDEX.md", text)
            self.assertNotIn("openclaw gateway start", text)
            self.assertNotIn("cp -r skills/", text)
            self.assertNotIn("skills/categories/README.md", text)
        self.assertIn("ARCHITECTURE.md", agent_context)

    def test_public_directory_indexes_exist(self) -> None:
        for relative in (
            "ARCHITECTURE.md",
            "starter-kits/README.md",
            "cookbook/README.md",
            "plugins/README.md",
            "plugins/agi-super-team-codex/README.md",
        ):
            with self.subTest(path=relative):
                self.assertTrue((ROOT / relative).is_file())

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

    def test_readmes_embed_the_interactive_star_history_chart(self) -> None:
        for readme in (self.english, self.chinese):
            self.assertIn(
                "https://api.star-history.com/svg?repos=aAAaqwq/AGI-Super-Team&amp;type=Date&amp;legend=top-left",
                readme,
            )
            self.assertIn(
                "https://www.star-history.com/?type=date&amp;legend=top-left&amp;repos=aAAaqwq%2FAGI-Super-Team",
                readme,
            )


if __name__ == "__main__":
    unittest.main()
