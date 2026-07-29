import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin" / "agi-super-team.mjs"
NODE = os.environ.get("NODE", "node")


class NpxInstallerTests(unittest.TestCase):
    def run_cli(self, codex_home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [NODE, str(CLI), "--skip-plugin", "--codex-home", str(codex_home), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_default_preview_is_non_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"
            result = self.run_cli(codex_home)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PREVIEW", result.stdout)
            self.assertIn("add=14", result.stdout)
            self.assertFalse(codex_home.exists())

    def test_default_install_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"
            first = self.run_cli(codex_home, "--install")
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertIn("Musk CEO", (codex_home / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertEqual(len(list((codex_home / "agents").glob("ast-*.toml"))), 13)

            second = self.run_cli(codex_home)
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            self.assertIn("unchanged=14", second.stdout)

    def test_selective_team_installs_only_needed_leaves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"
            result = self.run_cli(codex_home, "--team", "solo-founder", "--install")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            names = {path.stem for path in (codex_home / "agents").glob("*.toml")}
            self.assertEqual(names, {"ast-cpo", "ast-pe", "ast-cco", "ast-cmo", "ast-governor"})

    def test_all_agents_installs_entire_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"
            result = self.run_cli(codex_home, "--all-agents", "--install")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            installed = list((codex_home / "agents").glob("*.toml"))
            payload = list(
                (ROOT / "plugins/agi-super-team-codex/payload/agents").glob("*.toml")
            )
            self.assertEqual(len(installed), len(payload))

    def test_existing_global_rules_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"
            codex_home.mkdir()
            (codex_home / "AGENTS.md").write_text("# Mine\n\n- Preserve me.\n", encoding="utf-8")
            result = self.run_cli(codex_home, "--install")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            guidance = (codex_home / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(guidance.startswith("# Mine"))
            self.assertIn("- Preserve me.", guidance)
            self.assertEqual(guidance.count("AGI-SUPER-TEAM:CEO:BEGIN"), 1)


if __name__ == "__main__":
    unittest.main()
