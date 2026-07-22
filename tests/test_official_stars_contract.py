import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OfficialStarsContractTests(unittest.TestCase):
    def test_readmes_link_to_github_instead_of_claiming_an_official_history(self) -> None:
        for readme_name in ("README.md", "README_CN.md"):
            with self.subTest(readme=readme_name):
                readme = (ROOT / readme_name).read_text(encoding="utf-8")
                self.assertIn(
                    "https://github.com/aAAaqwq/AGI-Super-Team/stargazers",
                    readme,
                )
                self.assertNotIn("docs/assets/star-history", readme)
                self.assertNotIn("api.star-history.com", readme)

    def test_pages_workflow_does_not_write_star_charts_to_the_repository(self) -> None:
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("contents: read", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("git push origin HEAD:main", workflow)


if __name__ == "__main__":
    unittest.main()
