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


def snapshot_tree(root: Path) -> dict[str, tuple[str, bytes | None]]:
    snapshot: dict[str, tuple[str, bytes | None]] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            snapshot[relative] = ("directory", None)
        else:
            snapshot[relative] = ("file", path.read_bytes())
    return snapshot


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
        self,
        home: Path,
        project: Path,
        *arguments: str,
        environment: dict[str, str] | None = None,
        explicit_home: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            NODE,
            str(CLI),
            "--project-dir",
            str(project),
            *arguments,
        ]
        if explicit_home:
            command[2:2] = ["--home", str(home)]
        if "codex" in arguments:
            command.append("--skip-plugin")
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )

    def sanitized_environment(self, **overrides: str) -> dict[str, str]:
        environment = os.environ.copy()
        for name in (
            "HERMES_HOME",
            "OPENCLAW_HOME",
            "OPENCLAW_STATE_DIR",
            "OPENCLAW_CONFIG_PATH",
        ):
            environment.pop(name, None)
        environment.update(overrides)
        return environment

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
                self.assertIn("orchestrate-agi-super-team", body)
                self.assertNotIn("spawn_agent", body)
                self.assertNotIn("CODEX_HOME", body)
                self.assertNotIn("~/.codex", body)

    def test_codex_uses_only_the_official_skill_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()

            result = self.run_cli(
                home,
                project,
                "--tool",
                "codex",
                "--no-agents",
                "--install",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            skill_root = home / ".agents/skills"
            wrapper = skill_root / "agi-super-team-orchestrator/SKILL.md"
            canonical = skill_root / "orchestrate-agi-super-team/SKILL.md"
            self.assertTrue(wrapper.is_file())
            self.assertTrue(canonical.is_file())
            self.assertIn(
                "../orchestrate-agi-super-team/SKILL.md",
                wrapper.read_text(encoding="utf-8"),
            )
            self.assertFalse((home / ".codex/skills").exists())

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

    def test_hermes_home_controls_preview_install_connect_and_doctor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "login-home"
            hermes_home = root / "hermes-runtime"
            project = root / "project"
            project.mkdir()
            environment = self.sanitized_environment(
                HOME=str(home),
                HERMES_HOME=str(hermes_home),
            )
            resolved_home = home.resolve()
            resolved_hermes_home = hermes_home.resolve()

            preview = self.run_cli(
                home,
                project,
                "--tool",
                "hermes",
                environment=environment,
                explicit_home=False,
            )
            self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
            self.assertTrue(
                str(resolved_hermes_home) in preview.stdout,
                "preview ignored HERMES_HOME and planned a different installation root",
            )
            self.assertNotIn(str(resolved_home / ".hermes"), preview.stdout)
            self.assertFalse(home.exists(), "preview must not create the login home")
            self.assertFalse(hermes_home.exists(), "preview must not create HERMES_HOME")

            installed = self.run_cli(
                home,
                project,
                "--tool",
                "hermes",
                "--install",
                "--connect",
                environment=environment,
                explicit_home=False,
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            connection_path = hermes_home / "agi-super-team/connection.json"
            receipt_path = hermes_home / "agi-super-team/receipt.json"
            role_skill = hermes_home / "skills/agi-super-team-agents/ast-ceo/SKILL.md"
            orchestrator = hermes_home / "skills/agi-super-team-orchestrator/SKILL.md"
            canonical_skill = hermes_home / "skills/agi-super-team/orchestrate-agi-super-team/SKILL.md"
            for expected in (
                connection_path,
                receipt_path,
                role_skill,
                orchestrator,
                canonical_skill,
            ):
                self.assertTrue(expected.is_file(), f"missing Hermes artifact: {expected}")
            self.assertFalse((home / ".hermes").exists())
            self.assertFalse((hermes_home / ".hermes").exists())

            connection = json.loads(connection_path.read_text(encoding="utf-8"))
            self.assertEqual(Path(connection["home"]), resolved_hermes_home)
            self.assertTrue(
                all(
                    str(path).startswith(f"{resolved_hermes_home}{os.sep}")
                    for path in connection["paths"].values()
                )
            )
            self.assertNotIn(".hermes", json.dumps(connection))

            before_doctor = {
                path.relative_to(hermes_home): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in hermes_home.rglob("*")
                if path.is_file()
            }
            checked = self.run_cli(
                home,
                project,
                "--tool",
                "hermes",
                "--doctor",
                environment=environment,
                explicit_home=False,
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn("FILES_HEALTHY", checked.stdout)
            after_doctor = {
                path.relative_to(hermes_home): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in hermes_home.rglob("*")
                if path.is_file()
            }
            self.assertEqual(after_doctor, before_doctor, "doctor must be read-only")

    def test_openclaw_state_dir_wins_for_managed_installation_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "login-home"
            openclaw_home = root / "openclaw-home"
            state = root / "openclaw-state"
            config = root / "separate-config" / "custom.json"
            project = root / "project"
            project.mkdir()
            environment = self.sanitized_environment(
                HOME=str(home),
                OPENCLAW_HOME=str(openclaw_home),
                OPENCLAW_STATE_DIR=str(state),
                OPENCLAW_CONFIG_PATH=str(config),
            )

            installed = self.run_cli(
                home,
                project,
                "--tool",
                "openclaw",
                "--no-agents",
                "--install",
                environment=environment,
                explicit_home=False,
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            self.assertTrue(
                (state / "skills/agi-super-team/orchestrate-agi-super-team/SKILL.md").is_file()
            )
            self.assertTrue((state / "agi-super-team/connection.json").is_file())
            self.assertFalse((home / ".openclaw").exists())
            self.assertFalse((openclaw_home / ".openclaw").exists())
            self.assertFalse(config.exists(), "install without --connect must not edit OpenClaw config")

    def test_openclaw_legacy_state_stays_active_after_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            legacy = home / ".clawdbot"
            legacy.mkdir(parents=True)
            legacy_config = legacy / "clawdbot.json"
            legacy_config.write_text('{"agents":{"list":[]}}\n', encoding="utf-8")
            project = root / "project"
            project.mkdir()
            environment = self.sanitized_environment(HOME=str(home))

            installed = self.run_cli(
                home,
                project,
                "--tool",
                "openclaw",
                "--no-skills",
                "--install",
                environment=environment,
                explicit_home=False,
            )

            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            self.assertTrue((legacy / "agency-agents/agi-super-team/ast-ceo/AGENTS.md").is_file())
            self.assertTrue((legacy / "agi-super-team/connection.json").is_file())
            self.assertEqual(legacy_config.read_text(encoding="utf-8"), '{"agents":{"list":[]}}\n')
            self.assertFalse(
                (home / ".openclaw").exists(),
                "installing into a discovered legacy state must not switch future OpenClaw runs",
            )

    def test_openclaw_ambiguous_managed_current_and_legacy_user_state_fails_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            current = home / ".openclaw"
            legacy = home / ".clawdbot"
            project = root / "project"

            (current / "agi-super-team").mkdir(parents=True)
            (current / "agi-super-team/connection.json").write_bytes(
                b'{"schemaVersion":1,"harness":"openclaw"}\n'
            )
            (current / "agi-super-team/receipt.json").write_bytes(
                b'{"schemaVersion":1,"status":"filesystem-connected"}\n'
            )
            (current / "agency-agents/agi-super-team/ast-ceo").mkdir(parents=True)
            (current / "agency-agents/agi-super-team/ast-ceo/AGENTS.md").write_bytes(
                b"managed by AGI Super Team\n"
            )

            (legacy / "credentials").mkdir(parents=True)
            (legacy / "sessions/session-1").mkdir(parents=True)
            (legacy / "clawdbot.json").write_bytes(
                b'{"agents":{"list":[]},"preserve":"legacy-config"}\n'
            )
            (legacy / "credentials/provider.json").write_bytes(
                b'{"token":"fixture-only"}\n'
            )
            (legacy / "sessions/session-1/transcript.jsonl").write_bytes(
                b'{"role":"user","content":"preserve me"}\n'
            )
            project.mkdir()

            before = snapshot_tree(root)
            result = self.run_cli(
                home,
                project,
                "--tool",
                "openclaw",
                "--no-skills",
                "--install",
                environment=self.sanitized_environment(HOME=str(home)),
                explicit_home=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(".openclaw", result.stderr)
            self.assertIn(".clawdbot", result.stderr)
            self.assertRegex(
                result.stderr,
                r"(?is)\bset\b.*OPENCLAW_STATE_DIR.*OPENCLAW_CONFIG_PATH",
            )
            self.assertEqual(
                snapshot_tree(root),
                before,
                "ambiguous OpenClaw roots must fail before changing any directory or file bytes",
            )

    def test_openclaw_current_config_selects_current_root_when_legacy_state_also_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            current = home / ".openclaw"
            legacy = home / ".clawdbot"
            project = root / "project"

            current.mkdir(parents=True)
            current_config = current / "openclaw.json"
            current_config.write_bytes(
                b'{"agents":{"list":[]},"preserve":"current-config"}\n'
            )
            (legacy / "credentials").mkdir(parents=True)
            legacy_config = legacy / "clawdbot.json"
            legacy_config.write_bytes(
                b'{"agents":{"list":[]},"preserve":"legacy-config"}\n'
            )
            (legacy / "credentials/provider.json").write_bytes(
                b'{"token":"fixture-only"}\n'
            )
            project.mkdir()

            legacy_before = snapshot_tree(legacy)
            result = self.run_cli(
                home,
                project,
                "--tool",
                "openclaw",
                "--no-skills",
                "--install",
                environment=self.sanitized_environment(HOME=str(home)),
                explicit_home=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(
                (current / "agency-agents/agi-super-team/ast-ceo/AGENTS.md").is_file()
            )
            self.assertTrue((current / "agi-super-team/connection.json").is_file())
            self.assertEqual(
                current_config.read_bytes(),
                b'{"agents":{"list":[]},"preserve":"current-config"}\n',
            )
            self.assertEqual(
                snapshot_tree(legacy),
                legacy_before,
                "selecting the official current root must leave legacy user state byte-exact",
            )

    def test_openclaw_explicit_home_conflicts_fail_before_writes(self) -> None:
        overrides = {
            "OPENCLAW_HOME": lambda root: root / "different-home",
            "OPENCLAW_STATE_DIR": lambda root: root / "different-state",
            "OPENCLAW_CONFIG_PATH": lambda root: root / "different-config/openclaw.json",
        }
        for variable, value_for in overrides.items():
            with self.subTest(variable=variable), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                home = root / "selected-home"
                project = root / "project"
                project.mkdir()
                environment = self.sanitized_environment(
                    HOME=str(root / "ambient-home"),
                    **{variable: str(value_for(root))},
                )

                result = self.run_cli(
                    home,
                    project,
                    "--tool",
                    "openclaw",
                    "--no-skills",
                    "--install",
                    environment=environment,
                )

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(f"--home conflicts with {variable}", result.stderr)
                self.assertFalse(home.exists())
                self.assertEqual(list(project.iterdir()), [])
                self.assertFalse(value_for(root).exists())


if __name__ == "__main__":
    unittest.main()
