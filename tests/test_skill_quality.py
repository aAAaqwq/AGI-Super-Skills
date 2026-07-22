import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_skill_quality.py"


def load_auditor():
    spec = importlib.util.spec_from_file_location("audit_skill_quality", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load skill quality auditor")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SkillQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.auditor = load_auditor()

    def inspect(self, skill_id: str, text: str, files: dict[str, str] | None = None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            skill = root / "skills" / skill_id
            skill.mkdir(parents=True)
            path = skill / "SKILL.md"
            path.write_text(text, encoding="utf-8")
            for relative, content in (files or {}).items():
                target = skill / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            return self.auditor.inspect_skill(root, path)

    def test_clean_skill_passes_structural_and_disclosure_checks(self) -> None:
        evidence = self.inspect(
            "example",
            '---\nname: example\ndescription: "Review examples. Use when a user requests example analysis."\n---\n\n# Example\n',
        )
        self.assertEqual(evidence.structure_status, "pass")
        self.assertEqual(evidence.disclosure_status, "pass")
        self.assertEqual(evidence.issues, ())

    def test_invalid_yaml_and_name_mismatch_are_hard_failures(self) -> None:
        evidence = self.inspect(
            "example",
            "---\nname: wrong\ndescription: **unquoted alias**\n---\n\n# Example\n",
        )
        self.assertEqual(evidence.structure_status, "invalid")
        self.assertIn("invalid-frontmatter-yaml", evidence.issues)

    def test_duplicate_yaml_keys_are_rejected(self) -> None:
        evidence = self.inspect(
            "example",
            '---\nname: example\nname: duplicate\ndescription: "Review examples. Use when requested."\n---\n',
        )
        self.assertEqual(evidence.structure_status, "invalid")
        self.assertIn("invalid-frontmatter-yaml", evidence.issues)

    def test_unmentioned_script_requires_execution_review(self) -> None:
        evidence = self.inspect(
            "example",
            '---\nname: example\ndescription: "Run checks. Use when validation is requested."\n---\n\n# Example\n',
            {"scripts/run.py": "print('ok')\n"},
        )
        self.assertEqual(evidence.execution_status, "review-required")
        self.assertIn("unmentioned-scripts", evidence.issues)
        self.assertIn("scripts-without-test-evidence", evidence.issues)

    def test_fixture_data_alone_is_not_script_test_evidence(self) -> None:
        evidence = self.inspect(
            "example",
            '---\nname: example\ndescription: "Run checks. Use when validation is requested."\n---\n\nUse `scripts/run.py` with `scripts/fixture.json`.\n',
            {"scripts/run.py": "print('ok')\n", "scripts/fixture.json": "{}\n"},
        )
        self.assertEqual(evidence.execution_status, "review-required")
        self.assertIn("scripts-without-test-evidence", evidence.issues)

    def test_personal_path_in_reference_is_detected(self) -> None:
        evidence = self.inspect(
            "example",
            '---\nname: example\ndescription: "Review docs. Use when requested."\n---\n\nRead [guide](references/guide.md).\n',
            {"references/guide.md": "Use /Users/alice/private/tool.\n"},
        )
        self.assertIn("personal-absolute-path", evidence.issues)

    def test_ignored_python_cache_does_not_change_evidence(self) -> None:
        evidence = self.inspect(
            "example",
            '---\nname: example\ndescription: "Run checks. Use when requested."\n---\n\nRun `scripts/run.py`.\n',
            {
                "scripts/run.py": "print('ok')\n",
                "scripts/__pycache__/run.cpython-314.pyc": "local cache",
            },
        )
        self.assertNotIn("unmentioned-scripts", evidence.issues)

    def test_missing_relative_link_is_a_hard_failure(self) -> None:
        evidence = self.inspect(
            "example",
            '---\nname: example\ndescription: "Review docs. Use when documentation is requested."\n---\n\n[Missing](references/missing.md)\n',
        )
        self.assertEqual(evidence.structure_status, "invalid")
        self.assertIn("unresolved-local-link", evidence.issues)

    def test_baseline_allows_improvement_and_rejects_regression(self) -> None:
        baseline = {
            "structureInvalid": 2,
            "disclosureWarnings": 3,
            "executionReviewRequired": 1,
            "issueCounts": {"missing-frontmatter": 2},
        }
        improved = {
            "summary": {
                "structureInvalid": 1,
                "disclosureWarnings": 3,
                "executionReviewRequired": 0,
                "issueCounts": {"missing-frontmatter": 1},
            }
        }
        self.assertEqual(self.auditor.baseline_regressions(improved, baseline), [])
        regressed = {"summary": {**improved["summary"], "structureInvalid": 3}}
        self.assertIn("structureInvalid regressed", self.auditor.baseline_regressions(regressed, baseline)[0])

    def test_unregistered_issue_type_is_a_regression(self) -> None:
        baseline = {
            "structureInvalid": 0,
            "disclosureWarnings": 0,
            "executionReviewRequired": 0,
            "issueCounts": {"known": 1},
        }
        report = {
            "summary": {
                "structureInvalid": 0,
                "disclosureWarnings": 0,
                "executionReviewRequired": 0,
                "issueCounts": {"known": 0, "new": 1},
            }
        }
        self.assertIn("unregistered issue type: new", self.auditor.baseline_regressions(report, baseline))

    def test_baseline_schema_is_fail_closed(self) -> None:
        self.assertIn("baseline schemaVersion must equal 1", self.auditor.validate_baseline({}))

    def test_check_fails_when_baseline_is_missing_or_malformed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            command = [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(ROOT),
                "--output",
                str(ROOT / "catalog/skill-quality.json"),
                "--baseline",
                str(missing),
                "--check",
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("baseline is missing", result.stderr)
            malformed = Path(directory) / "malformed.json"
            malformed.write_text("{", encoding="utf-8")
            command[command.index(str(missing))] = str(malformed)
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertIn("baseline is unreadable", result.stderr)


if __name__ == "__main__":
    unittest.main()
