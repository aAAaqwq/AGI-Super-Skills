import json
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "plugins" / "agi-super-team-codex" / "payload" / "agents"


class VisualDirectorRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "config" / "team-manifest.json").read_text(encoding="utf-8")
        )
        cls.hierarchy = json.loads(
            (ROOT / "config" / "agent-hierarchy.json").read_text(encoding="utf-8")
        )
        cls.cco_routes = json.loads(
            (ROOT / "config" / "cco-specialists.json").read_text(encoding="utf-8")
        )

    def test_visual_director_duties_stay_under_the_existing_cco_leaf(self) -> None:
        self.assertEqual(self.manifest["inventory"]["agentCount"], 14)
        self.assertNotIn(
            "visual-director", {agent["id"] for agent in self.manifest["agents"]}
        )
        self.assertIn(
            "content-illustration-planner",
            self.hierarchy["managers"]["cco"]["subagents"],
        )
        self.assertFalse((ROOT / "agents" / "visual-director").exists())

    def test_visual_leaf_has_a_specific_trigger_and_quality_gates(self) -> None:
        role = next(
            item
            for item in self.cco_routes["specialists"]
            if item["id"] == "content-illustration-planner"
        )
        self.assertIn("Visual Director", role["name"])
        self.assertIn("article-to-infographic", role["trigger"])
        self.assertIn("逐字", " ".join(role["acceptance"]))
        self.assertIn("节点完整", " ".join(role["acceptance"]))
        self.assertIn("人工视觉验收", " ".join(role["acceptance"]))
        self.assertIn("不得", role["boundary"])

    def test_cco_owns_the_visual_route_and_required_skill_surface(self) -> None:
        cco = next(agent for agent in self.manifest["agents"] if agent["id"] == "cco")
        self.assertIn(
            "article-to-infographic", cco["skills"]["harnessSpecific"]
        )
        contract = (ROOT / "agents" / "cco" / "AGENTS.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("content-illustration-planner", contract)
        self.assertIn("视觉内容总监", contract)
        self.assertIn("不得继续创建子 Agent", contract)

    def test_generated_visual_leaf_remains_non_recursive(self) -> None:
        payload = tomllib.loads(
            (PAYLOAD / "ast-cco-content-illustration-planner.toml").read_text(
                encoding="utf-8"
            )
        )
        instructions = payload["developer_instructions"]
        self.assertIn("Visual Director", instructions)
        self.assertIn("article-to-infographic", instructions)
        self.assertIn("不得创建子 Agent", instructions)
        self.assertFalse((PAYLOAD / "ast-visual-director.toml").exists())


if __name__ == "__main__":
    unittest.main()
