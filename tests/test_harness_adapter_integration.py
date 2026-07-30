import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "agi-super-team.mjs"
NODE = os.environ.get("NODE", "node")
PRIORITY_HARNESSES = ("claude-code", "codex", "openclaw", "hermes")


class HarnessAdapterIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(
            (ROOT / "config" / "team-manifest.json").read_text(encoding="utf-8")
        )
        cls.adapters = json.loads(
            (ROOT / "config" / "cli-adapters.json").read_text(encoding="utf-8")
        )
        cls.tools = {tool["id"]: tool for tool in cls.adapters["tools"]}

    def run_cli(
        self, home: Path, project: Path, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        command = [
            NODE,
            str(CLI),
            "--home",
            str(home),
            "--project-dir",
            str(project),
            *arguments,
        ]
        if "codex" in arguments:
            command.append("--skip-plugin")
        return subprocess.run(command, capture_output=True, text=True, check=False)

    def assigned_physical_skills(self) -> set[str]:
        selected = set()
        for agent in self.manifest["agents"]:
            for tier in ("required", "optional", "harnessSpecific"):
                for skill_id in agent["skills"].get(tier, []):
                    if (ROOT / "skills" / skill_id / "SKILL.md").is_file():
                        selected.add(skill_id)
        return selected

    def test_priority_harnesses_declare_external_adapter_contracts(self) -> None:
        schema = ROOT / "config" / "cli-adapters.schema.json"
        self.assertTrue(schema.is_file(), "CLI adapters require a shared schema")
        schema_payload = json.loads(schema.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema_payload)
        Draft202012Validator(schema_payload).validate(self.adapters)

        for harness in PRIORITY_HARNESSES:
            with self.subTest(harness=harness):
                tool = self.tools[harness]
                self.assertEqual(tool["runtimeEvidence"], "pending")
                self.assertEqual(tool["skillSource"], "canonical-assigned")
                self.assertTrue((ROOT / tool["adapterModule"]).is_file())
                self.assertTrue(
                    (ROOT / "config" / "harness-adapters" / f"{harness}.json").is_file()
                )
                self.assertTrue(
                    (
                        ROOT
                        / "config"
                        / "harness-adapters"
                        / f"{harness}.schema.json"
                    ).is_file()
                )

    def test_priority_harnesses_install_connection_specs(self) -> None:
        expected = {
            "claude-code": Path(".claude/agi-super-team/connection.json"),
            "codex": Path(".codex/agi-super-team/connection.json"),
            "openclaw": Path(".openclaw/agi-super-team/connection.json"),
            "hermes": Path(".hermes/agi-super-team/connection.json"),
        }
        for harness, relative in expected.items():
            with self.subTest(harness=harness), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                home = root / "home"
                project = root / "project"
                project.mkdir()
                result = self.run_cli(
                    home,
                    project,
                    "--tool",
                    harness,
                    "--no-skills",
                    "--install",
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                connection = home / relative
                self.assertTrue(connection.is_file(), f"missing {connection}")
                payload = json.loads(connection.read_text(encoding="utf-8"))
                self.assertEqual(payload["schemaVersion"], 1)
                self.assertEqual(payload["harness"], harness)
                self.assertEqual(payload["runtimeEvidence"], "pending")
                expected_coordinator = "ceo" if harness == "codex" else "ast-ceo"
                self.assertEqual(payload["coordinator"], expected_coordinator)
                self.assertEqual(payload["independentReviewer"], "ast-governor")
                self.assertEqual(payload["requiredMaxDepth"], 2)

    def test_non_codex_harnesses_copy_assigned_canonical_skills_byte_exact(self) -> None:
        expected = self.assigned_physical_skills()
        self.assertGreater(len(expected), 20)
        roots = {
            "claude-code": Path(".claude/skills"),
            "openclaw": Path(".openclaw/skills/agi-super-team"),
            "hermes": Path(".hermes/skills/agi-super-team"),
        }
        for harness, relative in roots.items():
            with self.subTest(harness=harness), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                home = root / "home"
                project = root / "project"
                project.mkdir()
                result = self.run_cli(
                    home,
                    project,
                    "--tool",
                    harness,
                    "--no-agents",
                    "--install",
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                destination = home / relative
                installed = {
                    path.parent.name
                    for path in destination.glob("*/SKILL.md")
                    if path.parent.name != "agi-super-team-orchestrator"
                }
                self.assertEqual(installed, expected)
                for skill_id in expected:
                    source = ROOT / "skills" / skill_id / "SKILL.md"
                    target = destination / skill_id / "SKILL.md"
                    self.assertEqual(
                        hashlib.sha256(target.read_bytes()).hexdigest(),
                        hashlib.sha256(source.read_bytes()).hexdigest(),
                        f"{harness} changed canonical Skill bytes: {skill_id}",
                    )

    def test_non_codex_orchestrators_do_not_contain_codex_runtime_calls(self) -> None:
        paths = {
            "claude-code": Path(
                ".claude/skills/agi-super-team-orchestrator/SKILL.md"
            ),
            "openclaw": Path(
                ".openclaw/skills/agi-super-team/agi-super-team-orchestrator/SKILL.md"
            ),
            "hermes": Path(
                ".hermes/skills/agi-super-team-orchestrator/SKILL.md"
            ),
        }
        for harness, relative in paths.items():
            with self.subTest(harness=harness), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                home = root / "home"
                project = root / "project"
                project.mkdir()
                result = self.run_cli(
                    home, project, "--tool", harness, "--no-agents", "--install"
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                body = (home / relative).read_text(encoding="utf-8")
                self.assertNotIn("spawn_agent", body)
                self.assertNotIn("CODEX_HOME", body)
                self.assertNotIn("~/.codex", body)

    def test_connect_requires_install_and_writes_pending_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()

            rejected = self.run_cli(
                home, project, "--tool", "claude-code", "--connect"
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("--install", rejected.stderr)

            installed = self.run_cli(
                home,
                project,
                "--tool",
                "claude-code",
                "--no-skills",
                "--install",
                "--connect",
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            receipt_path = home / ".claude/agi-super-team/receipt.json"
            self.assertTrue(receipt_path.is_file())
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["harness"], "claude-code")
            self.assertEqual(receipt["status"], "filesystem-connected")
            self.assertEqual(receipt["runtimeEvidence"], "pending")
            self.assertIn("packageVersion", receipt)
            self.assertIn("sourceRevision", receipt)
            self.assertIn("sourceDirty", receipt)
            self.assertIn("revisionMatched", receipt)
            self.assertRegex(receipt["connectionSha256"], r"^[0-9a-f]{64}$")
            receipt_schema = json.loads(
                (
                    ROOT
                    / "config"
                    / "harness-adapters"
                    / "receipt.schema.json"
                ).read_text(encoding="utf-8")
            )
            Draft202012Validator.check_schema(receipt_schema)
            Draft202012Validator(receipt_schema).validate(receipt)


if __name__ == "__main__":
    unittest.main()
