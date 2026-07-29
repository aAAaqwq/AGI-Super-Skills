import importlib.util
import json
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "config" / "harness-adapters" / "codex.json"
ADAPTER_SCHEMA_PATH = ROOT / "config" / "harness-adapters" / "codex.schema.json"
BUILDER_PATH = ROOT / "scripts" / "build_codex_csuite_adapter.py"
PLUGIN_ROOT = ROOT / "plugins" / "agi-super-team-codex"


class CodexTeamAdapterTests(unittest.TestCase):
    def _generate_minimal_repository(self, temporary_root: Path) -> dict:
        manifest_path = ROOT / "config" / "team-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        temporary_manifest = temporary_root / "config" / "team-manifest.json"
        temporary_manifest.parent.mkdir(parents=True)
        temporary_manifest.write_text(
            manifest_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        for relative in (
            "config/agent-hierarchy.json",
            "config/cto-specialists.json",
            "config/cpo-specialists.json",
            "config/cco-specialists.json",
        ):
            destination = temporary_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                (ROOT / relative).read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        hierarchy = json.loads((ROOT / "config/agent-hierarchy.json").read_text(encoding="utf-8"))
        for manager, settings in hierarchy["managers"].items():
            for role in settings["subagents"]:
                relative = Path("agents") / manager / "subagents" / role / "AGENTS.md"
                destination = temporary_root / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes((ROOT / relative).read_bytes())
        for kit in manifest["kits"]:
            source = ROOT / kit["entrypoint"]
            destination = temporary_root / kit["entrypoint"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                source.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

        generated = subprocess.run(
            [
                sys.executable,
                str(BUILDER_PATH),
                "--root",
                str(temporary_root),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            generated.returncode, 0, generated.stdout + generated.stderr
        )
        return manifest

    def test_adapter_is_schema_valid_and_covers_every_leaf_role(self) -> None:
        adapter = json.loads(ADAPTER_PATH.read_text(encoding="utf-8"))
        schema = json.loads(ADAPTER_SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = json.loads(
            (ROOT / "config" / "team-manifest.json").read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(adapter)

        agent_ids = {agent["id"] for agent in manifest["agents"]}
        self.assertEqual(adapter["coordinator"], "ceo")
        self.assertEqual(adapter["independentReviewer"], "governor")
        self.assertEqual(set(adapter["agentMap"]), agent_ids - {"ceo"})
        self.assertEqual(len(set(adapter["agentMap"].values())), len(agent_ids) - 1)
        self.assertEqual(adapter["runtimeEvidence"], "pending")

    def test_generated_adapter_payload_is_current(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BUILDER_PATH), "--root", str(ROOT), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_mapped_agent_is_a_safe_role_contract(self) -> None:
        adapter = json.loads(ADAPTER_PATH.read_text(encoding="utf-8"))
        for role_id, agent_name in adapter["agentMap"].items():
            with self.subTest(role=role_id):
                path = PLUGIN_ROOT / "payload" / "agents" / f"{agent_name}.toml"
                payload = tomllib.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(payload["name"], agent_name)
                self.assertIn(payload["sandbox_mode"], {"read-only", "workspace-write"})
                instructions = payload["developer_instructions"].lower()
                if role_id in {"cto", "cpo", "cco"}:
                    self.assertIn("受限管理节点", instructions)
                    self.assertIn(f"ast-{role_id}-", instructions)
                    self.assertIn("总深度不得超过二", instructions)
                else:
                    self.assertIn("叶子 agent", instructions)
                    self.assertIn("不得创建子 agent", instructions)
                self.assertIn("人类明确批准", instructions)
                self.assertNotIn("production-ready", instructions)

    def test_team_skill_has_native_and_honest_fallback_paths(self) -> None:
        skill = (
            PLUGIN_ROOT / "skills" / "c-suite-team" / "SKILL.md"
        ).read_text(encoding="utf-8")
        lowered = skill.lower()
        self.assertIn("parent acts as ceo", lowered)
        self.assertIn("spawn_agent", skill)
        self.assertIn('fork_turns` to `"none"', skill)
        self.assertIn("self-contained task packet", lowered)
        self.assertIn("governor", lowered)
        self.assertIn("sequential", lowered)
        self.assertIn("manual", lowered)
        self.assertIn("runtime evidence", lowered)
        self.assertIn("verification receipt", lowered)
        self.assertIn("read its `entrypoint` runbook", lowered)
        self.assertNotIn("automatically verified", lowered)
        self.assertIn("agent-hierarchy.json", lowered)
        self.assertIn("total depth no greater than two", lowered)

    def test_packaged_team_contract_matches_manifest_kits(self) -> None:
        manifest = json.loads(
            (ROOT / "config" / "team-manifest.json").read_text(encoding="utf-8")
        )
        packaged = json.loads(
            (
                PLUGIN_ROOT
                / "skills"
                / "c-suite-team"
                / "references"
                / "team-contracts.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(packaged["schemaVersion"], manifest["schemaVersion"])
        self.assertEqual(
            [kit["id"] for kit in packaged["kits"]],
            [kit["id"] for kit in manifest["kits"]],
        )
        self.assertEqual(
            {agent["id"] for agent in packaged["agents"]},
            {agent["id"] for agent in manifest["agents"]},
        )

    def test_packaged_kit_entrypoints_are_safe_current_runbooks(self) -> None:
        manifest = json.loads(
            (ROOT / "config" / "team-manifest.json").read_text(encoding="utf-8")
        )
        skill_root = PLUGIN_ROOT / "skills" / "c-suite-team"
        packaged = json.loads(
            (skill_root / "references" / "team-contracts.json").read_text(
                encoding="utf-8"
            )
        )
        manifest_kits = {kit["id"]: kit for kit in manifest["kits"]}

        self.assertEqual(len(packaged["kits"]), 8)
        for kit in packaged["kits"]:
            with self.subTest(kit=kit["id"]):
                entrypoint = Path(kit["entrypoint"])
                self.assertFalse(entrypoint.is_absolute())
                self.assertNotIn("..", entrypoint.parts)
                self.assertEqual(
                    entrypoint,
                    Path("references") / "kits" / f"{kit['id']}.md",
                )

                packaged_runbook = skill_root / entrypoint
                self.assertTrue(packaged_runbook.is_file())
                self.assertFalse(packaged_runbook.is_symlink())
                self.assertTrue(
                    packaged_runbook.resolve().is_relative_to(skill_root.resolve())
                )

                canonical_runbook = ROOT / manifest_kits[kit["id"]]["entrypoint"]
                self.assertEqual(
                    packaged_runbook.read_text(encoding="utf-8"),
                    canonical_runbook.read_text(encoding="utf-8"),
                )

    def test_check_rejects_unexpected_generated_kit_runbook(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            self._generate_minimal_repository(temporary_root)

            extra_runbook = (
                temporary_root
                / "plugins"
                / "agi-super-team-codex"
                / "skills"
                / "c-suite-team"
                / "references"
                / "kits"
                / "obsolete.md"
            )
            extra_runbook.write_text("# Obsolete generated Kit\n", encoding="utf-8")
            checked = subprocess.run(
                [
                    sys.executable,
                    str(BUILDER_PATH),
                    "--root",
                    str(temporary_root),
                    "--check",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(checked.returncode, 0)
            self.assertIn(
                "Unexpected generated Kit runbook", checked.stdout + checked.stderr
            )

    def test_check_rejects_stale_generated_kit_runbook(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            self._generate_minimal_repository(temporary_root)
            generated_runbook = (
                temporary_root
                / "plugins"
                / "agi-super-team-codex"
                / "skills"
                / "c-suite-team"
                / "references"
                / "kits"
                / "solo-founder.md"
            )
            generated_runbook.write_text("# Stale generated Kit\n", encoding="utf-8")

            checked = subprocess.run(
                [
                    sys.executable,
                    str(BUILDER_PATH),
                    "--root",
                    str(temporary_root),
                    "--check",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            output = checked.stdout + checked.stderr
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("Codex C-suite adapter is stale", output)
            self.assertIn("references/kits/solo-founder.md", output)


if __name__ == "__main__":
    unittest.main()
