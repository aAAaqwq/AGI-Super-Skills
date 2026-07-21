import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = REPOSITORY_ROOT / "scripts" / "validate_repository.py"


class RepositoryValidatorTests(unittest.TestCase):
    def run_validator(
        self,
        fixture_root: Path,
        *checks: str,
        extra_arguments: tuple[str, ...] = (),
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(VALIDATOR),
            "--root",
            str(fixture_root),
            "--checks",
            ",".join(checks),
            *extra_arguments,
        ]
        return subprocess.run(command, capture_output=True, text=True, check=False)

    def git(self, fixture_root: Path, *arguments: str) -> None:
        subprocess.run(
            ["git", *arguments],
            cwd=fixture_root,
            capture_output=True,
            text=True,
            check=True,
        )

    def test_valid_workflow_passes_when_workflow_check_is_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            workflow_directory = fixture_root / ".github" / "workflows"
            workflow_directory.mkdir(parents=True)
            (workflow_directory / "ci.yml").write_text(
                """name: CI
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo ok
""",
                encoding="utf-8",
            )

            result = self.run_validator(fixture_root, "workflows")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS workflows", result.stdout)

    def test_invalid_workflow_yaml_fails_and_names_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            workflow_directory = fixture_root / ".github" / "workflows"
            workflow_directory.mkdir(parents=True)
            (workflow_directory / "broken.yml").write_text(
                "name: Broken\non: [push\njobs: {}\n",
                encoding="utf-8",
            )

            result = self.run_validator(fixture_root, "workflows")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("broken.yml: YAML parse failed", result.stdout)

    def test_runner_specific_working_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            workflow_directory = fixture_root / ".github" / "workflows"
            workflow_directory.mkdir(parents=True)
            (workflow_directory / "portable.yml").write_text(
                """name: Portable
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: cd /home/example/project
""",
                encoding="utf-8",
            )

            result = self.run_validator(fixture_root, "workflows")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("runner-specific absolute path", result.stdout)

    def test_invalid_json_fails_and_names_the_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            (fixture_root / "package.json").write_text('{"name": }\n', encoding="utf-8")

            result = self.run_validator(fixture_root, "structured")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("package.json: JSON parse failed", result.stdout)

    def test_tracked_absolute_broken_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            (fixture_root / "skills").mkdir()
            (fixture_root / "skills" / "portable-skill").symlink_to(
                "/home/example/missing-skill"
            )
            self.git(fixture_root, "init", "--quiet")
            self.git(fixture_root, "add", "skills/portable-skill")

            result = self.run_validator(fixture_root, "symlinks")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("tracked absolute symlink", result.stdout)
        self.assertIn("tracked broken symlink", result.stdout)

    def test_broken_agent_skill_reference_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            tools_file = fixture_root / "agents" / "ceo" / "TOOLS.md"
            tools_file.parent.mkdir(parents=True)
            tools_file.write_text(
                "Use [planning](../skills/planning/) for plans.\n",
                encoding="utf-8",
            )

            result = self.run_validator(fixture_root, "references")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("agents/ceo/TOOLS.md", result.stdout)
        self.assertIn("broken skill reference", result.stdout)

    def test_installer_agent_mapping_to_missing_role_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            (fixture_root / "agents" / "ceo").mkdir(parents=True)
            (fixture_root / "install.sh").write_text(
                """declare -A AGENT_MAP=(
  [ceo]=main
)
""",
                encoding="utf-8",
            )

            result = self.run_validator(fixture_root, "references")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("installer agent mapping", result.stdout)
        self.assertIn("agents/main", result.stdout)

    def test_installer_skill_mapping_to_missing_skill_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            (fixture_root / "install.sh").write_text(
                """declare -A AGENT_SKILLS=(
  [ceo]="planning missing-skill"
)
""",
                encoding="utf-8",
            )
            (fixture_root / "skills" / "planning").mkdir(parents=True)

            result = self.run_validator(fixture_root, "references")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("installer skill reference", result.stdout)
        self.assertIn("skills/missing-skill", result.stdout)

    def test_count_drift_warns_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            skill_file = fixture_root / "skills" / "one-skill" / "SKILL.md"
            skill_file.parent.mkdir(parents=True)
            skill_file.write_text("# One skill\n", encoding="utf-8")
            (fixture_root / "package.json").write_text(
                '{"description": "A repository with 2 skills"}\n',
                encoding="utf-8",
            )
            self.git(fixture_root, "init", "--quiet")
            self.git(fixture_root, "add", "skills/one-skill/SKILL.md", "package.json")

            result = self.run_validator(fixture_root, "counts")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("WARNING package.json", result.stdout)
        self.assertIn("claims 2 skills; canonical inventory has 1", result.stdout)
        self.assertIn("SUMMARY errors=0 warnings=1", result.stdout)

    def test_diagnostics_are_bounded_without_hiding_summary_counts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            tools_file = fixture_root / "agents" / "ceo" / "TOOLS.md"
            tools_file.parent.mkdir(parents=True)
            tools_file.write_text(
                "../skills/missing-one/\n../skills/missing-two/\n",
                encoding="utf-8",
            )

            result = self.run_validator(
                fixture_root,
                "references",
                extra_arguments=("--max-details", "1"),
            )

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("1 additional error(s) omitted", result.stdout)
        self.assertIn("SUMMARY errors=2 warnings=0", result.stdout)

    def test_installer_function_skill_reference_is_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            (fixture_root / "install.sh").write_text(
                """agent_skills() {
  case "$1" in
    ceo) printf '%s\\n' "present missing" ;;
  esac
}
""",
                encoding="utf-8",
            )
            (fixture_root / "skills" / "present").mkdir(parents=True)

            result = self.run_validator(fixture_root, "references")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("ceo -> skills/missing", result.stdout)

    def test_json_output_is_stable_and_uses_coded_issue_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            (fixture_root / "package.json").write_text('{"name": }\n', encoding="utf-8")

            first = self.run_validator(
                fixture_root,
                "structured",
                extra_arguments=("--format", "json"),
            )
            second = self.run_validator(
                fixture_root,
                "structured",
                extra_arguments=("--format", "json"),
            )

        self.assertEqual(first.stdout, second.stdout)
        payload = json.loads(first.stdout)
        self.assertEqual(payload["summary"], {"errors": 1, "warnings": 0})
        self.assertEqual(
            set(payload["issues"][0]),
            {"check", "code", "message", "path", "severity"},
        )
        self.assertEqual(payload["issues"][0]["code"], "structured.invalid_json")

    def test_manifest_missing_required_field_has_specific_issue_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            config = fixture_root / "config"
            config.mkdir()
            (config / "team-manifest.schema.json").write_text(
                (REPOSITORY_ROOT / "config/team-manifest.schema.json").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            (config / "team-manifest.json").write_text(
                json.dumps(
                    {
                        "$schema": "./team-manifest.schema.json",
                        "schemaVersion": 1,
                        "inventory": {
                            "agentCount": 0,
                            "physicalSkillCount": 0,
                            "skillEntrypoint": "SKILL.md",
                            "symlinkPolicy": "forbid",
                        },
                        "agents": [],
                    }
                ),
                encoding="utf-8",
            )

            result = self.run_validator(
                fixture_root,
                "manifest",
                extra_arguments=("--format", "json", "--max-details", "50"),
            )

        payload = json.loads(result.stdout)
        codes = {issue["code"] for issue in payload["issues"]}
        self.assertIn("manifest.schema_required", codes)

    def test_inventory_count_excludes_tracked_symlinks_and_untracked_skills(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture_root = Path(temporary_directory)
            tracked = fixture_root / "skills" / "tracked" / "SKILL.md"
            tracked.parent.mkdir(parents=True)
            tracked.write_text("# Tracked\n", encoding="utf-8")
            untracked = fixture_root / "skills" / "untracked" / "SKILL.md"
            untracked.parent.mkdir(parents=True)
            untracked.write_text("# Untracked\n", encoding="utf-8")
            (fixture_root / "skills" / "alias").symlink_to("tracked")
            (fixture_root / "package.json").write_text(
                '{"description": "Repository with 1 skill"}\n', encoding="utf-8"
            )
            self.git(fixture_root, "init", "--quiet")
            self.git(
                fixture_root,
                "add",
                "skills/tracked/SKILL.md",
                "skills/alias",
                "package.json",
            )

            result = self.run_validator(fixture_root, "counts")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("(1 skills, 0 agents)", result.stdout)


if __name__ == "__main__":
    unittest.main()
