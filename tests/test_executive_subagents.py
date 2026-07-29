import hashlib
import json
import tomllib
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config"
PAYLOAD = ROOT / "plugins" / "agi-super-team-codex" / "payload" / "agents"


class ExecutiveSubagentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.hierarchy = json.loads((CONFIG / "agent-hierarchy.json").read_text(encoding="utf-8"))
        cls.source_lock = json.loads((CONFIG / "agent-sources.lock.json").read_text(encoding="utf-8"))
        cls.registries = {
            manager: json.loads((ROOT / settings["routingFile"]).read_text(encoding="utf-8"))
            for manager, settings in cls.hierarchy["managers"].items()
        }

    def test_hierarchy_and_every_routing_registry_are_schema_valid(self) -> None:
        hierarchy_schema = json.loads((CONFIG / "agent-hierarchy.schema.json").read_text(encoding="utf-8"))
        routing_schema = json.loads((CONFIG / "specialist-routing.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(hierarchy_schema)
        Draft202012Validator(hierarchy_schema).validate(self.hierarchy)
        Draft202012Validator.check_schema(routing_schema)
        for manager, registry in self.registries.items():
            with self.subTest(manager=manager):
                Draft202012Validator(routing_schema).validate(registry)

    def test_pyramid_has_exact_requested_shape_and_pe_is_a_reference(self) -> None:
        expected = {"cco": 19, "cto": 22, "cpo": 3}
        self.assertEqual(
            {manager: len(settings["subagents"]) for manager, settings in self.hierarchy["managers"].items()},
            expected,
        )
        self.assertEqual(self.hierarchy["managers"]["cto"]["roleRefs"], ["pe"])
        self.assertFalse((ROOT / "agents/cto/subagents/pe").exists())
        self.assertEqual(self.hierarchy["requiredMaxDepth"], 2)
        self.assertTrue(all(item["maxConcurrentChildren"] == 2 for item in self.hierarchy["managers"].values()))

    def test_hierarchy_routing_and_source_lock_cover_the_same_forty_four_roles(self) -> None:
        hierarchy_roles = {
            f"{manager}/{role}"
            for manager, settings in self.hierarchy["managers"].items()
            for role in settings["subagents"]
        }
        routing_roles = {
            f"{manager}/{item['id']}"
            for manager, registry in self.registries.items()
            for item in registry["specialists"]
        }
        source_roles = {f"{item['manager']}/{item['id']}" for item in self.source_lock["entries"]}
        self.assertEqual(len(hierarchy_roles), 44)
        self.assertEqual(hierarchy_roles, routing_roles)
        self.assertEqual(hierarchy_roles, source_roles)

    def test_every_vendored_agent_is_verbatim_locked_and_not_a_symlink(self) -> None:
        for entry in self.source_lock["entries"]:
            path = ROOT / entry["vendoredPath"]
            with self.subTest(role=f"{entry['manager']}/{entry['id']}"):
                self.assertTrue(path.is_file())
                self.assertFalse(path.is_symlink())
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry["sha256"])
                self.assertEqual(entry["copyMode"], "verbatim")
                self.assertIn(entry["sourcePath"], entry["sourceUrl"])

    def test_every_codex_projection_contains_verbatim_upstream_prefix_and_local_envelope(self) -> None:
        by_role = {(item["manager"], item["id"]): item for item in self.source_lock["entries"]}
        for manager, registry in self.registries.items():
            for specialist in registry["specialists"]:
                source = by_role[(manager, specialist["id"])]
                upstream = (ROOT / source["vendoredPath"]).read_text(encoding="utf-8")
                name = f"ast-{manager}-{specialist['id']}"
                with self.subTest(role=name):
                    payload = tomllib.loads((PAYLOAD / f"{name}.toml").read_text(encoding="utf-8"))
                    instructions = payload["developer_instructions"]
                    self.assertEqual(payload["nickname_candidates"], [specialist["id"]])
                    self.assertTrue(payload["nickname_candidates"][0].isascii())
                    self.assertTrue(instructions.startswith(upstream))
                    self.assertIn("# AGI Super Team 路由与安全信封", instructions)
                    self.assertIn(specialist["trigger"], instructions)
                    self.assertIn(specialist["doNotUseWhen"], instructions)
                    self.assertIn("不得创建子 Agent", instructions)

    def test_manager_payloads_embed_only_declared_routes(self) -> None:
        for manager, registry in self.registries.items():
            payload = tomllib.loads((PAYLOAD / f"ast-{manager}.toml").read_text(encoding="utf-8"))
            instructions = payload["developer_instructions"]
            self.assertIn("受限管理节点", instructions)
            self.assertIn("最多两个叶子并发", instructions)
            for specialist in registry["specialists"]:
                self.assertIn(f"ast-{manager}-{specialist['id']}", instructions)
        cto = tomllib.loads((PAYLOAD / "ast-cto.toml").read_text(encoding="utf-8"))["developer_instructions"]
        self.assertIn("ast-pe", cto)
        self.assertFalse((PAYLOAD / "ast-cto-pe.toml").exists())

    def test_content_illustration_role_discloses_adaptation(self) -> None:
        role = next(item for item in self.registries["cco"]["specialists"] if item["id"] == "content-illustration-planner")
        self.assertEqual(role["sourceRole"], "图像提示词工程师")
        self.assertIn("上游不存在同名角色", role["adaptation"])


if __name__ == "__main__":
    unittest.main()
