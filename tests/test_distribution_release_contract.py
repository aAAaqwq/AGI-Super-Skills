import json
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DistributionReleaseContractTests(unittest.TestCase):
    def test_npm_tarball_contains_the_runtime_and_no_transient_files(self) -> None:
        result = subprocess.run(
            ["npm", "pack", "--dry-run", "--json", "--ignore-scripts"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)[0]
        files = {entry["path"]: entry for entry in payload["files"]}

        required_runtime = {
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "bin").rglob("*.mjs")
        }
        self.assertTrue(required_runtime <= files.keys())
        self.assertEqual(files["bin/agi-super-team.mjs"]["mode"] & 0o111, 0o111)
        self.assertFalse(
            any(
                "__pycache__" in path
                or path.endswith((".pyc", ".pyo", ".DS_Store", ".env"))
                for path in files
            )
        )

    def test_npm_and_codex_plugin_versions_are_identical(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        plugin = json.loads(
            (
                ROOT
                / "plugins"
                / "agi-super-team-codex"
                / ".codex-plugin"
                / "plugin.json"
            ).read_text(encoding="utf-8")
        )

        self.assertRegex(package["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(plugin["version"], package["version"])

    def test_codex_marketplace_install_never_tracks_a_mutable_branch(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        cli = (ROOT / "bin" / "agi-super-team.mjs").read_text(encoding="utf-8")
        shell_installer = (ROOT / "install.sh").read_text(encoding="utf-8")
        guide = (ROOT / "docs" / "guides" / "codex-install.html").read_text(
            encoding="utf-8"
        )

        self.assertNotIn('"--ref", "main"', cli)
        self.assertNotIn("git pull", shell_installer)
        self.assertIn(f'REPO_REF="${{AGI_SUPER_TEAM_REF:-v{package["version"]}}}"', shell_installer)
        self.assertNotIn("--ref main", guide)
        self.assertIn(f"v{package['version']}", guide)

    def test_ci_covers_supported_node_releases_and_primary_harnesses(self) -> None:
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        workflow = (
            ROOT / ".github" / "workflows" / "validate-repository.yml"
        ).read_text(encoding="utf-8")
        packed_smoke = (ROOT / "tests" / "windows_cli_smoke.mjs").read_text(
            encoding="utf-8"
        )

        self.assertEqual(package["engines"]["node"], ">=18")
        for version in ("18", "20", "22", "24"):
            with self.subTest(node=version):
                self.assertRegex(workflow, rf'["\']{re.escape(version)}["\']')
        for harness in ("claude-code", "codex", "openclaw", "hermes"):
            with self.subTest(harness=harness):
                self.assertIn(harness, packed_smoke)
        for runner in ("ubuntu-latest", "macos-latest", "windows-latest"):
            with self.subTest(runner=runner):
                self.assertIn(runner, workflow)


if __name__ == "__main__":
    unittest.main()
