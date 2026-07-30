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
            self.assertIn("plugin marketplace add aAAaqwq/AGI-Super-Team --ref main", calls)
            self.assertIn("plugin marketplace upgrade agi-super-team", calls)
            self.assertIn("plugin add agi-super-team-codex@agi-super-team", calls)


if __name__ == "__main__":
    unittest.main()
