import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/agent-skill-repository-index/scripts/verify_repository_index.py"
REFERENCE = ROOT / "skills/agent-skill-repository-index/references/repositories.md"


def load_verifier():
    spec = importlib.util.spec_from_file_location("verify_repository_index", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load repository-index verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RepositoryIndexSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.verifier = load_verifier()

    def test_portable_index_has_unique_repositories(self) -> None:
        repositories = self.verifier.parse_index(REFERENCE)
        self.assertGreaterEqual(len(repositories), 20)
        self.assertEqual(len(repositories), len({item.slug.lower() for item in repositories}))
        self.assertEqual(len(repositories), len({item.local for item in repositories}))
        text = REFERENCE.read_text(encoding="utf-8")
        self.assertNotIn("/Users/", text)
        self.assertNotIn("/home/", text)

    def test_github_slug_normalizes_https_and_ssh_remotes(self) -> None:
        self.assertEqual(
            self.verifier.github_slug("https://github.com/anthropics/skills.git"),
            "anthropics/skills",
        )
        self.assertEqual(
            self.verifier.github_slug("git@github.com:anthropics/skills.git"),
            "anthropics/skills",
        )

    def test_expected_count_is_optional_but_enforced_when_supplied(self) -> None:
        default = subprocess.run(
            [sys.executable, str(SCRIPT), "--reference", str(REFERENCE)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(default.returncode, 0, default.stdout + default.stderr)
        self.assertRegex(default.stdout, r"PASS \d+ entries")
        mismatch = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--reference",
                str(REFERENCE),
                "--expected-count",
                "1",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(mismatch.returncode, 1)
        self.assertIn("entry count mismatch", mismatch.stdout)

    def test_local_origin_mismatch_is_reported(self) -> None:
        repository = self.verifier.Repository(
            "anthropics/skills",
            "https://github.com/anthropics/skills",
            "candidate",
        )
        with tempfile.TemporaryDirectory() as directory:
            clone = Path(directory) / "candidate"
            subprocess.run(["git", "init", str(clone)], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(clone), "remote", "add", "origin", "https://github.com/example/wrong.git"],
                check=True,
            )
            error = self.verifier.check_local(repository, Path(directory))
        self.assertIsNotNone(error)
        self.assertIn("origin mismatch", error)

    def test_label_and_url_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / "repositories.md"
            reference.write_text(
                "| Repository | Local | Class | Best use |\n"
                "|---|---|---|---|\n"
                "| [anthropics/skills](https://github.com/example/wrong) | `skills` | LIBRARY | Test |\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--reference", str(reference)],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertEqual(result.returncode, 1)
        self.assertIn("label/url mismatch", result.stdout)


if __name__ == "__main__":
    unittest.main()
