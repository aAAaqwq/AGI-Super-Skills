import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "plugins"
    / "agi-super-team-codex"
    / "skills"
    / "agi-super-team-sync"
    / "scripts"
    / "install_codex_team.py"
)


class CodexTeamInstallerTests(unittest.TestCase):
    def run_installer(self, codex_home: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--codex-home", str(codex_home), *arguments],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_lists_all_eight_outcome_teams(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_installer(Path(directory) / "codex", "--list-teams")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for team in (
            "solo-founder",
            "content-creator",
            "quant-trader",
            "product-delivery",
            "research-decision",
            "go-to-market",
            "operations-response",
            "full-team",
        ):
            self.assertIn(team, result.stdout)

    def test_preview_does_not_create_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"
            result = self.run_installer(codex_home, "--global-ceo", "--team", "solo-founder")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(codex_home.exists())
            self.assertIn("add=6", result.stdout)

    def test_install_all_teams_adds_global_ceo_and_thirteen_leaves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"
            codex_home.mkdir()
            result = self.run_installer(codex_home, "--global-ceo", "--all-teams", "--install")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            guidance = (codex_home / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("AGI Super Team 全局主 Agent｜Musk CEO", guidance)
            self.assertEqual(guidance.count("AGI-SUPER-TEAM:CEO:BEGIN"), 1)
            agents = sorted((codex_home / "agents").glob("ast-*.toml"))
            self.assertEqual(len(agents), 13)
            self.assertFalse((codex_home / "agents" / "ast-ceo.toml").exists())

            repeated = self.run_installer(codex_home, "--global-ceo", "--all-teams", "--install")
            self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
            self.assertIn("unchanged=14", repeated.stdout)

    def test_existing_global_content_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"
            codex_home.mkdir()
            (codex_home / "AGENTS.md").write_text("# My existing rules\n\n- Keep this.\n", encoding="utf-8")
            result = self.run_installer(codex_home, "--global-ceo", "--install")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            guidance = (codex_home / "AGENTS.md").read_text(encoding="utf-8")
            self.assertTrue(guidance.startswith("# My existing rules"))
            self.assertIn("- Keep this.", guidance)
            self.assertEqual(guidance.count("AGI-SUPER-TEAM:CEO:BEGIN"), 1)

    def test_all_subagents_installs_three_managers_pe_reference_and_forty_four_leaves(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"
            result = self.run_installer(codex_home, "--all-subagents", "--install")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            names = {path.stem for path in (codex_home / "agents").glob("ast-*.toml")}
            self.assertEqual(len(names), 48)
            self.assertTrue({"ast-cto", "ast-cpo", "ast-cco", "ast-pe"}.issubset(names))
            self.assertFalse((codex_home / "agents" / "ast-cto-pe.toml").exists())
            self.assertEqual(len([name for name in names if name.startswith(("ast-cto-", "ast-cpo-", "ast-cco-"))]), 44)

    def test_unknown_team_fails_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            codex_home = Path(directory) / "codex"
            result = self.run_installer(codex_home, "--team", "missing", "--install")
            self.assertEqual(result.returncode, 2)
            self.assertIn("unknown team", result.stderr)
            self.assertFalse(codex_home.exists())


if __name__ == "__main__":
    unittest.main()
