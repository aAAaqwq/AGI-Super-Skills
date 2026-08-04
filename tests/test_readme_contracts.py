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
        cls.spanish = (ROOT / "README.es-ES.md").read_text(encoding="utf-8")

    def test_public_npm_commands_are_consistent_across_languages(self) -> None:
        command = "npx -y agi-super-team@latest --list-tools"
        install = "npx -y agi-super-team@latest --tool claude-code --install --connect"
        for readme in (self.english, self.chinese, self.spanish):
            self.assertIn(command, readme)
            self.assertIn(install, readme)
            self.assertNotIn("npx -y github:aAAaqwq/AGI-Super-Team", readme)
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        self.assertEqual(package["name"], "agi-super-team")
        self.assertIn("README.es-ES.md", package["files"])
        self.assertNotIn("skills/", package["files"])
        self.assertIn("skills/*/SKILL.md", package["files"])
        manifest = json.loads((ROOT / "config/team-manifest.json").read_text(encoding="utf-8"))
        assigned_skills = {
            skill
            for agent in manifest["agents"]
            for tier in ("required", "optional", "harnessSpecific")
            for skill in agent["skills"][tier]
        }
        self.assertEqual(len(assigned_skills), 169)
        packaged_skill_roots = {
            entry.removeprefix("skills/").removesuffix("/")
            for entry in package["files"]
            if entry.startswith("skills/") and entry.endswith("/")
        }
        self.assertTrue(assigned_skills <= packaged_skill_roots)
        self.assertIn("all 817 `SKILL.md` entrypoints", self.english)
        self.assertIn("全部 817 个 `SKILL.md` 入口", self.chinese)
        self.assertIn("los 817 puntos de entrada `SKILL.md`", self.spanish)
        cli_entrypoint = ROOT / package["bin"]["agi-super-team"]
        self.assertTrue(cli_entrypoint.stat().st_mode & 0o111)
        self.assertIn("!**/__pycache__/**", package["files"])
        self.assertIn("!**/*.pyc", package["files"])
        npmignore = (ROOT / ".npmignore").read_text(encoding="utf-8")
        self.assertIn("**/__pycache__/", npmignore)
        self.assertIn(".npmrc", npmignore)

    def test_spanish_readme_matches_current_team_contract(self) -> None:
        self.assertIn("Un equipo organizado e instalable de Agents + Skills", self.spanish)
        self.assertIn("92 especialistas", self.spanish)
        self.assertIn("11 ejecutivos gestores", self.spanish)
        self.assertIn("8 Teams", self.spanish)
        self.assertIn("runtime pendiente", self.spanish)
        self.assertIn("starter-kits/operations-response/", self.spanish)
        self.assertIn("docs/guides/team-agent-skill-architecture.md", self.spanish)
        self.assertNotIn("44 especialistas", self.spanish)
        self.assertNotIn("4 kits", self.spanish)
        self.assertNotIn("./growth/README.md", self.spanish)

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

    def test_readmes_offer_agent_prompt_install_and_swarm_quick_start(self) -> None:
        self.assertIn('<h1 align="center">🤖 AGI Super Team</h1>', self.english)
        self.assertIn('<h1 align="center">🤖 AGI Super Team</h1>', self.chinese)
        self.assertIn("## ⚡ Quick Start for Coding Agents", self.english)
        self.assertIn("## 🐝 Run your first swarm", self.english)
        self.assertIn("## ⚡ 用 Coding Agent 一键安装", self.chinese)
        self.assertIn("## 🐝 用 Swarm agents 召集军团", self.chinese)
        for readme in (self.english, self.chinese):
            self.assertIn("https://github.com/aAAaqwq/AGI-Super-Team", readme)
            self.assertIn("Swarm agents: <", readme)
            self.assertIn("--all-subagents", readme)
            self.assertIn("--all-tools", readme)
            self.assertIn("--doctor", readme)
            self.assertIn("Governor", readme)

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

    def test_readmes_expose_provenance_navigation_and_use_the_china_flag(self) -> None:
        self.assertIn('<a href="./README_CN.md">🇨🇳 中文</a>', self.english)
        for readme in (self.english, self.chinese):
            self.assertIn("./catalog/#project-original-skills", readme)
            self.assertIn("./catalog/#adapted-skills", readme)
            self.assertIn("./catalog/#collected-skills", readme)
            self.assertIn("./catalog/#unknown-origin-skills", readme)

        skills = (ROOT / "skills/README.md").read_text(encoding="utf-8")
        self.assertIn("## ✨ Browse by provenance", skills)
        self.assertIn("../catalog/#project-original-skills", skills)
        self.assertIn("../catalog/#collected-skills", skills)

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
        for filename, readme in (
            ("README.md", self.english),
            ("README_CN.md", self.chinese),
            ("README.es-ES.md", self.spanish),
        ):
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
        for readme in (self.english, self.chinese, self.spanish):
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
