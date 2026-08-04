import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "agi-super-team.mjs"
ADAPTERS = ROOT / "config" / "cli-adapters.json"
NODE = os.environ.get("NODE", "node")
PRIORITY_TOOLS = ("claude-code", "codex", "openclaw", "hermes")
EXPECTED_TOOL_IDS = {
    "aider",
    "antigravity",
    "claude-code",
    "codewhale",
    "codex",
    "copilot",
    "cursor",
    "deerflow",
    "gemini-cli",
    "hermes",
    "kiro",
    "opencode",
    "openclaw",
    "qoder",
    "qwen",
    "trae",
    "windsurf",
    "workbuddy",
}


class MultiCliInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads(ADAPTERS.read_text(encoding="utf-8"))
        cls.tools = {tool["id"]: tool for tool in cls.manifest["tools"]}

    def run_cli(
        self,
        home: Path,
        project: Path,
        *arguments: str,
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
        if "codex" in arguments or "--all-tools" in arguments:
            command.append("--skip-plugin")
        return subprocess.run(command, capture_output=True, text=True, check=False)

    def assert_success(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def tool_root(self, tool: dict[str, object], home: Path, project: Path) -> Path:
        return home if tool["scope"] == "global" else project

    def assert_contains_artifact(self, path: Path) -> None:
        self.assertTrue(path.exists(), f"expected installer destination: {path}")
        if path.is_dir():
            self.assertTrue(
                any(item.is_file() for item in path.rglob("*")),
                f"expected an installed artifact below: {path}",
            )
        else:
            self.assertGreater(path.stat().st_size, 0, f"expected non-empty artifact: {path}")

    def snapshot(self, *roots: Path) -> tuple[tuple[str, str, str], ...]:
        entries = []
        for index, root in enumerate(roots):
            if not root.exists() and not root.is_symlink():
                continue
            for path in [root, *sorted(root.rglob("*"))]:
                relative = "." if path == root else path.relative_to(root).as_posix()
                if path.is_symlink():
                    entries.append((str(index), relative, f"symlink:{os.readlink(path)}"))
                elif path.is_file():
                    digest = hashlib.sha256(path.read_bytes()).hexdigest()
                    entries.append((str(index), relative, f"file:{digest}"))
                else:
                    entries.append((str(index), relative, "directory"))
        return tuple(entries)

    def test_adapter_manifest_has_exactly_eighteen_unique_tool_ids(self) -> None:
        ids = [tool["id"] for tool in self.manifest["tools"]]

        self.assertEqual(len(ids), 18)
        self.assertEqual(len(set(ids)), 18)
        self.assertEqual(set(ids), EXPECTED_TOOL_IDS)

    def test_list_tools_reports_every_manifest_tool(self) -> None:
        result = subprocess.run(
            [NODE, str(CLI), "--list-tools"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assert_success(result)
        for tool_id in self.tools:
            self.assertIn(tool_id, result.stdout)

    def test_spawn_cli_uses_comspec_for_windows_command_shims(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_comspec = root / "fake-comspec"
            log = root / "comspec.json"
            fake_comspec.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "with open(os.environ['FAKE_COMSPEC_LOG'], 'w', encoding='utf-8') as f:\n"
                "    json.dump(sys.argv[1:], f)\n",
                encoding="utf-8",
            )
            fake_comspec.chmod(0o755)
            script = (
                "import {spawnCli} from './bin/installer/process.mjs';"
                "const result=spawnCli('C:\\\\Program Files (x86)\\\\Codex\\\\codex.cmd',"
                "['plugin','marketplace','upgrade','agi-super-team'],"
                "{platform:'win32',comspec:process.env.FAKE_COMSPEC,env:process.env});"
                "process.exit(result.status ?? 1);"
            )
            environment = os.environ.copy()
            environment["FAKE_COMSPEC"] = str(fake_comspec)
            environment["FAKE_COMSPEC_LOG"] = str(log)

            result = subprocess.run(
                [NODE, "--input-type=module", "--eval", script],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

            self.assert_success(result)
            self.assertEqual(
                json.loads(log.read_text(encoding="utf-8")),
                [
                    "/d",
                    "/s",
                    "/c",
                    '\"\"C:\\Program Files (x86)\\Codex\\codex.cmd\" plugin marketplace upgrade agi-super-team\"',
                ],
            )

    def test_spawn_cli_does_not_quote_bare_windows_command_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_comspec = root / "fake-comspec"
            log = root / "comspec.json"
            fake_comspec.write_text(
                "#!/usr/bin/env python3\n"
                "import json, os, sys\n"
                "with open(os.environ['FAKE_COMSPEC_LOG'], 'w', encoding='utf-8') as f:\n"
                "    json.dump(sys.argv[1:], f)\n",
                encoding="utf-8",
            )
            fake_comspec.chmod(0o755)
            script = (
                "import {spawnCli} from './bin/installer/process.mjs';"
                "const result=spawnCli('openclaw',['--version'],"
                "{platform:'win32',comspec:process.env.FAKE_COMSPEC,env:process.env});"
                "process.exit(result.status ?? 1);"
            )
            environment = os.environ.copy()
            environment["FAKE_COMSPEC"] = str(fake_comspec)
            environment["FAKE_COMSPEC_LOG"] = str(log)

            result = subprocess.run(
                [NODE, "--input-type=module", "--eval", script],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

            self.assert_success(result)
            self.assertEqual(
                json.loads(log.read_text(encoding="utf-8")),
                ["/d", "/s", "/c", "openclaw --version"],
            )

    def test_spawn_cli_rejects_windows_shell_metacharacters(self) -> None:
        script = (
            "import {spawnCli} from './bin/installer/process.mjs';"
            "try { spawnCli('codex',['plugin&whoami'],{platform:'win32'}); }"
            "catch (error) { console.error(error.message); process.exit(23); }"
        )

        result = subprocess.run(
            [NODE, "--input-type=module", "--eval", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 23, result.stdout + result.stderr)
        self.assertIn("unsafe Windows CLI argument", result.stderr)

    def test_default_preview_does_not_create_or_change_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            sentinel = project / "keep.txt"
            sentinel.write_text("owned by user\n", encoding="utf-8")
            before = self.snapshot(home, project)

            result = self.run_cli(home, project, "--tool", "claude-code")

            self.assert_success(result)
            self.assertIn("PREVIEW", result.stdout.upper())
            self.assertEqual(self.snapshot(home, project), before)

    def test_connect_rejects_targets_without_an_adapter_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            sentinel = project / "keep.txt"
            sentinel.write_text("owned by user\n", encoding="utf-8")
            before = self.snapshot(home, project)

            result = self.run_cli(
                home,
                project,
                "--tool",
                "cursor",
                "--install",
                "--connect",
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("does not support --connect", result.stderr)
            self.assertEqual(self.snapshot(home, project), before)

    def test_legacy_team_options_reject_all_tools_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            before = self.snapshot(home, project)

            result = self.run_cli(
                home,
                project,
                "--all-tools",
                "--team",
                "solo-founder",
                "--install",
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("legacy Team options only apply to the codex target", result.stderr)
            self.assertEqual(self.snapshot(home, project), before)

    def test_subagent_group_requires_its_manager_in_the_selected_team(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            before = self.snapshot(home, project)

            result = self.run_cli(
                home,
                project,
                "--tool",
                "codex",
                "--team",
                "content-creator",
                "--with-subagents",
                "cto",
                "--install",
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("subagent manager is not in the selected Team: cto", result.stderr)
            self.assertEqual(self.snapshot(home, project), before)

    def test_priority_tools_install_agents_at_their_native_paths(self) -> None:
        for tool_id in PRIORITY_TOOLS:
            with self.subTest(tool=tool_id), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                home = root / "home"
                project = root / "project"
                project.mkdir()

                result = self.run_cli(
                    home,
                    project,
                    "--tool",
                    tool_id,
                    "--no-skills",
                    "--install",
                )

                self.assert_success(result)
                tool = self.tools[tool_id]
                destination_root = self.tool_root(tool, home, project)
                for relative_path in tool["agentPaths"]:
                    self.assert_contains_artifact(destination_root / relative_path)

    def test_priority_tools_install_all_executive_subagents_on_request(self) -> None:
        hierarchy = json.loads((ROOT / "config/agent-hierarchy.json").read_text(encoding="utf-8"))
        expected = {f"{manager}-{role}" for manager, settings in hierarchy["managers"].items() for role in settings["subagents"]}
        for tool_id in PRIORITY_TOOLS:
            with self.subTest(tool=tool_id), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                home = root / "home"
                project = root / "project"
                project.mkdir()
                result = self.run_cli(home, project, "--tool", tool_id, "--no-skills", "--all-subagents", "--install")
                self.assert_success(result)
                if tool_id == "codex":
                    installed = {path.stem.removeprefix("ast-") for path in (home / ".codex/agents").glob("ast-*-*.toml") if path.stem.removeprefix("ast-") in expected}
                elif tool_id == "claude-code":
                    installed = {path.stem.removeprefix("ast-") for path in (home / ".claude/agents").glob("ast-*-*.md") if path.stem.removeprefix("ast-") in expected}
                elif tool_id == "openclaw":
                    installed = {path.name.removeprefix("ast-") for path in (home / ".openclaw/agency-agents/agi-super-team").glob("ast-*-*") if path.name.removeprefix("ast-") in expected}
                else:
                    installed = {path.name.removeprefix("ast-") for path in (home / ".hermes/skills/agi-super-team-agents").glob("ast-*-*") if path.name.removeprefix("ast-") in expected}
                self.assertEqual(installed, expected)

    def test_no_agents_installs_only_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()

            result = self.run_cli(
                home,
                project,
                "--tool",
                "claude-code",
                "--no-agents",
                "--install",
            )

            self.assert_success(result)
            tool = self.tools["claude-code"]
            for relative_path in tool["agentPaths"]:
                self.assertFalse((home / relative_path).exists())
            for relative_path in tool["skillPaths"]:
                self.assert_contains_artifact(home / relative_path)

    def test_all_tools_installs_global_and_project_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()

            result = self.run_cli(
                home,
                project,
                "--all-tools",
                "--no-skills",
                "--install",
            )

            self.assert_success(result)
            scopes_seen = set()
            for tool in self.tools.values():
                scopes_seen.add(tool["scope"])
                destination_root = self.tool_root(tool, home, project)
                for relative_path in tool["agentPaths"]:
                    self.assert_contains_artifact(destination_root / relative_path)
            self.assertEqual(scopes_seen, {"global", "project"})

    def test_installed_tree_is_unchanged_by_second_preview(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            install_arguments = ("--tool", "claude-code", "--no-skills")
            installed = self.run_cli(home, project, *install_arguments, "--install")
            self.assert_success(installed)
            before = self.snapshot(home, project)

            preview = self.run_cli(home, project, *install_arguments)

            self.assert_success(preview)
            self.assertIn("UNCHANGED", preview.stdout.upper())
            self.assertEqual(self.snapshot(home, project), before)

    def test_existing_destination_is_preserved_or_backed_up(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            destination = project / "CONVENTIONS.md"
            sentinel = "user-owned convention\n"
            destination.write_text(sentinel, encoding="utf-8")

            result = self.run_cli(
                home,
                project,
                "--tool",
                "aider",
                "--no-skills",
                "--install",
            )

            self.assert_success(result)
            preserved_in_place = sentinel in destination.read_text(encoding="utf-8")
            preserved_in_backup = any(
                path.is_file() and sentinel.encode() in path.read_bytes()
                for path in root.rglob("*")
                if path != destination
            )
            self.assertTrue(
                preserved_in_place or preserved_in_backup,
                "existing destination must be retained or recoverably backed up",
            )

    def test_symlinked_destination_is_refused_without_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            outside = root / "outside"
            home.mkdir()
            project.mkdir()
            outside.mkdir()
            sentinel = outside / "keep.txt"
            sentinel.write_text("do not change\n", encoding="utf-8")
            (home / ".claude").symlink_to(outside, target_is_directory=True)
            before = self.snapshot(outside)

            result = self.run_cli(
                home,
                project,
                "--tool",
                "claude-code",
                "--no-skills",
                "--install",
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertRegex(
                (result.stdout + result.stderr).lower(),
                r"refus|unsafe|symlink|symbolic",
            )
            self.assertEqual(self.snapshot(outside), before)

    def test_exact_whole_skill_symlink_is_reused_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            external = root / "external-ai-marketing-videos"
            shutil.copytree(ROOT / "skills" / "ai-marketing-videos", external)
            skill_root = home / ".claude" / "skills"
            skill_root.mkdir(parents=True)
            linked = skill_root / "ai-marketing-videos"
            linked.symlink_to(external, target_is_directory=True)
            before = self.snapshot(external)

            result = self.run_cli(
                home,
                project,
                "--tool",
                "claude-code",
                "--no-agents",
                "--install",
            )

            self.assert_success(result)
            self.assertTrue(linked.is_symlink())
            self.assertEqual(self.snapshot(external), before)

    def test_mismatched_whole_skill_symlink_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            external = root / "external-ai-marketing-videos"
            external.mkdir()
            (external / "SKILL.md").write_text("not canonical\n", encoding="utf-8")
            skill_root = home / ".claude" / "skills"
            skill_root.mkdir(parents=True)
            (skill_root / "ai-marketing-videos").symlink_to(
                external, target_is_directory=True
            )
            before = self.snapshot(external)

            result = self.run_cli(
                home,
                project,
                "--tool",
                "claude-code",
                "--no-agents",
                "--install",
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("mismatched Skill symlink", result.stderr)
            self.assertEqual(self.snapshot(external), before)

    def test_doctor_fails_for_missing_install_and_passes_after_install(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            arguments = ("--tool", "claude-code", "--no-skills")

            missing = self.run_cli(home, project, *arguments, "--doctor")
            self.assertNotEqual(missing.returncode, 0, missing.stdout + missing.stderr)
            self.assertRegex(
                (missing.stdout + missing.stderr).lower(),
                r"missing|not installed|fail",
            )

            installed = self.run_cli(home, project, *arguments, "--install")
            self.assert_success(installed)
            healthy = self.run_cli(home, project, *arguments, "--doctor")
            self.assert_success(healthy)
            self.assertRegex(healthy.stdout.lower(), r"ok|pass|healthy|installed")
            self.assertIn("FILES_HEALTHY", healthy.stdout)
            self.assertIn("connection/runtime status requires a receipt", healthy.stdout)

    def test_codex_install_uses_allowlisted_plugin_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            fake_codex = root / "codex"
            log = root / "codex.log"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import os, sys\n"
                "if sys.argv[1:] != ['--version'] and not os.path.isdir(os.environ['CODEX_HOME']):\n"
                "    print('CODEX_HOME must exist before plugin commands', file=sys.stderr)\n"
                "    raise SystemExit(23)\n"
                "with open(os.environ['FAKE_CODEX_LOG'], 'a', encoding='utf-8') as f:\n"
                "    f.write(' '.join(sys.argv[1:]) + '\\n')\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            environment = os.environ.copy()
            environment["CODEX_CLI"] = str(fake_codex)
            environment["FAKE_CODEX_LOG"] = str(log)

            result = subprocess.run(
                [
                    NODE,
                    str(CLI),
                    "--home",
                    str(home),
                    "--project-dir",
                    str(project),
                    "--tool",
                    "codex",
                    "--plugin",
                    "--install",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

            self.assert_success(result)
            calls = log.read_text(encoding="utf-8").splitlines()
            self.assertIn("--version", calls)
            self.assertIn("plugin marketplace add aAAaqwq/AGI-Super-Team --ref v1.4.1", calls)
            self.assertIn("plugin marketplace upgrade agi-super-team", calls)
            self.assertIn("plugin add agi-super-team-codex@agi-super-team", calls)

    def test_codex_plugin_capability_failure_prevents_mutation_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            fake_codex = root / "codex"
            log = root / "codex.log"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import os, sys\n"
                "args = sys.argv[1:]\n"
                "with open(os.environ['FAKE_CODEX_LOG'], 'a', encoding='utf-8') as f:\n"
                "    f.write(' '.join(args) + '\\n')\n"
                "if args == ['plugin', 'marketplace', 'add', '--help']:\n"
                "    print('unknown command', file=sys.stderr)\n"
                "    raise SystemExit(64)\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            environment = os.environ.copy()
            environment["CODEX_CLI"] = str(fake_codex)
            environment["FAKE_CODEX_LOG"] = str(log)

            result = subprocess.run(
                [
                    NODE,
                    str(CLI),
                    "--home",
                    str(home),
                    "--project-dir",
                    str(project),
                    "--tool",
                    "codex",
                    "--plugin",
                    "--install",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("does not support required plugin command", result.stderr)
            calls = log.read_text(encoding="utf-8").splitlines()
            self.assertIn("plugin marketplace add --help", calls)
            self.assertFalse(any(call.startswith("plugin marketplace add aAAaqwq/") for call in calls))
            self.assertFalse((home / ".codex" / "agents" / "ast-cto.toml").exists())
            self.assertFalse(home.exists(), "failed plugin preflight must restore the original directory tree")

    def test_codex_plugin_is_an_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            fake_codex = root / "codex"
            log = root / "codex.log"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import os, sys\n"
                "with open(os.environ['FAKE_CODEX_LOG'], 'a', encoding='utf-8') as f:\n"
                "    f.write(' '.join(sys.argv[1:]) + '\\n')\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            environment = os.environ.copy()
            environment["CODEX_CLI"] = str(fake_codex)
            environment["FAKE_CODEX_LOG"] = str(log)

            result = subprocess.run(
                [
                    NODE,
                    str(CLI),
                    "--home",
                    str(home),
                    "--project-dir",
                    str(project),
                    "--tool",
                    "codex",
                    "--no-skills",
                    "--install",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

            self.assert_success(result)
            self.assertFalse(log.exists(), "default Codex install must not invoke the external plugin CLI")
            self.assertIn("disabled (add --plugin to opt in)", result.stdout)

    def test_codex_home_controls_artifacts_and_connection_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            codex_home = root / "custom-codex"
            project.mkdir()
            environment = os.environ.copy()
            environment["HOME"] = str(home)
            environment["CODEX_HOME"] = str(codex_home)

            result = subprocess.run(
                [
                    NODE,
                    str(CLI),
                    "--project-dir",
                    str(project),
                    "--tool",
                    "codex",
                    "--skip-plugin",
                    "--install",
                    "--connect",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

            self.assert_success(result)
            self.assertTrue((codex_home / "agents" / "ast-cto.toml").is_file())
            self.assertTrue((codex_home / "agi-super-team" / "connection.json").is_file())
            self.assertTrue((codex_home / "agi-super-team" / "receipt.json").is_file())
            self.assertFalse((home / ".codex").exists())
            self.assertTrue((home / ".agents" / "skills" / "agi-super-team-orchestrator" / "SKILL.md").is_file())
            self.assertFalse((codex_home / "skills").exists())

    def test_conflicting_home_and_codex_home_are_rejected_before_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            codex_home = root / "different-codex"
            project.mkdir()
            before = self.snapshot(home, project, codex_home)
            environment = os.environ.copy()
            environment["CODEX_HOME"] = str(codex_home)

            result = subprocess.run(
                [
                    NODE,
                    str(CLI),
                    "--home",
                    str(home),
                    "--project-dir",
                    str(project),
                    "--tool",
                    "codex",
                    "--skip-plugin",
                    "--install",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("--home conflicts with CODEX_HOME", result.stderr)
            self.assertEqual(self.snapshot(home, project, codex_home), before)

    def test_codex_home_does_not_affect_non_codex_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            environment = os.environ.copy()
            environment["CODEX_HOME"] = str(root / "unrelated-codex-home")

            result = subprocess.run(
                [
                    NODE,
                    str(CLI),
                    "--home",
                    str(home),
                    "--project-dir",
                    str(project),
                    "--tool",
                    "claude-code",
                    "--no-skills",
                    "--install",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

            self.assert_success(result)
            self.assertTrue((home / ".claude" / "agents" / "ast-ceo.md").is_file())
            self.assertFalse((root / "unrelated-codex-home").exists())

    def test_failed_connect_rolls_back_installed_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            fake_openclaw = root / "openclaw"
            fake_openclaw.write_text(
                "#!/usr/bin/env python3\n"
                "import os, pathlib, sys\n"
                "args = sys.argv[1:]\n"
                "if args == ['--version']:\n"
                "    print('openclaw-test')\n"
                "elif args == ['config', 'get', 'agents.list', '--json']:\n"
                "    print('Config path not found: agents.list', file=sys.stderr)\n"
                "    raise SystemExit(1)\n"
                "elif args[:2] == ['config', 'patch'] and '--dry-run' not in args:\n"
                "    state = pathlib.Path(os.environ['OPENCLAW_STATE_DIR'])\n"
                "    state.mkdir(parents=True, exist_ok=True)\n"
                "    (state / 'openclaw.json').write_text(sys.stdin.read(), encoding='utf-8')\n"
                "elif args == ['config', 'validate', '--json']:\n"
                "    print('invalid test config', file=sys.stderr)\n"
                "    raise SystemExit(9)\n",
                encoding="utf-8",
            )
            fake_openclaw.chmod(0o755)
            environment = os.environ.copy()
            environment["OPENCLAW_CLI"] = str(fake_openclaw)

            result = subprocess.run(
                [
                    NODE,
                    str(CLI),
                    "--home",
                    str(home),
                    "--project-dir",
                    str(project),
                    "--tool",
                    "openclaw",
                    "--no-skills",
                    "--install",
                    "--connect",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("invalid test config", result.stderr)
            self.assertFalse((home / ".openclaw" / "agency-agents" / "agi-super-team" / "ast-ceo" / "AGENTS.md").exists())
            self.assertFalse((home / ".openclaw" / "agi-super-team" / "connection.json").exists())
            self.assertFalse((home / ".openclaw" / "openclaw.json").exists())

    def test_later_receipt_failure_rolls_back_all_selected_harnesses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            unsafe_receipt = home / ".hermes" / "agi-super-team" / "receipt.json"
            unsafe_receipt.mkdir(parents=True)

            result = self.run_cli(
                home,
                project,
                "--tool",
                "claude-code",
                "--tool",
                "hermes",
                "--no-skills",
                "--install",
                "--connect",
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("unsafe receipt destination", result.stderr)
            self.assertTrue(unsafe_receipt.is_dir())
            self.assertFalse((home / ".claude" / "agents" / "ast-ceo.md").exists())
            self.assertFalse((home / ".claude" / "agi-super-team" / "connection.json").exists())
            self.assertFalse((home / ".claude" / "agi-super-team" / "receipt.json").exists())
            self.assertFalse((home / ".hermes" / "skills" / "agi-super-team-agents" / "ast-ceo" / "SKILL.md").exists())
            self.assertFalse((home / ".hermes" / "agi-super-team" / "connection.json").exists())

    def test_all_connections_are_preflighted_before_codex_plugin_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            project = root / "project"
            project.mkdir()
            codex_log = root / "codex.log"
            fake_codex = root / "codex"
            fake_codex.write_text(
                "#!/usr/bin/env python3\n"
                "import os, sys\n"
                "with open(os.environ['FAKE_CODEX_LOG'], 'a', encoding='utf-8') as f:\n"
                "    f.write(' '.join(sys.argv[1:]) + '\\n')\n",
                encoding="utf-8",
            )
            fake_codex.chmod(0o755)
            fake_openclaw = root / "openclaw"
            fake_openclaw.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "print('OpenClaw unavailable', file=sys.stderr)\n"
                "raise SystemExit(8)\n",
                encoding="utf-8",
            )
            fake_openclaw.chmod(0o755)
            environment = os.environ.copy()
            environment["CODEX_CLI"] = str(fake_codex)
            environment["FAKE_CODEX_LOG"] = str(codex_log)
            environment["OPENCLAW_CLI"] = str(fake_openclaw)

            result = subprocess.run(
                [
                    NODE,
                    str(CLI),
                    "--home",
                    str(home),
                    "--project-dir",
                    str(project),
                    "--tool",
                    "codex",
                    "--plugin",
                    "--tool",
                    "openclaw",
                    "--no-skills",
                    "--install",
                    "--connect",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("OpenClaw unavailable", result.stderr)
            self.assertFalse(codex_log.exists(), "Codex plugin commands ran before every connection preflight passed")
            self.assertFalse(home.exists(), "failed preflight must not create the installation home")


if __name__ == "__main__":
    unittest.main()
