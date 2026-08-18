import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class OfficialStarsContractTests(unittest.TestCase):
    def test_readmes_keep_star_history_and_use_a_low_pressure_invitation(self) -> None:
        expected = {
            "README.md": (
                "If AGI Super Team has genuinely saved you time",
                "AGI Super Team Star History chart",
            ),
            "README_CN.md": (
                "如果 AGI Super Team 确实帮你省下了时间",
                "AGI Super Team Star History chart",
            ),
            "README.es-ES.md": (
                "Si AGI Super Team realmente te ha ahorrado tiempo",
                "Gráfico de Historial de Estrellas de AGI Super Team",
            ),
        }
        for readme_name, (invitation, alt) in expected.items():
            with self.subTest(readme=readme_name):
                readme = (ROOT / readme_name).read_text(encoding="utf-8")
                self.assertIn(invitation, readme)
                self.assertIn(f'alt="{alt}"', readme)
                self.assertIn(
                    "https://api.star-history.com/svg?repos=aAAaqwq/AGI-Super-Team&amp;type=Date&amp;legend=top-left",
                    readme,
                )
                self.assertIn("https://github.com/aAAaqwq/AGI-Super-Team/stargazers", readme)

    def test_pages_workflow_does_not_write_star_charts_to_the_repository(self) -> None:
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("contents: read", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("git push origin HEAD:main", workflow)

    def test_pages_workflow_uses_the_dedicated_star_history_token(self) -> None:
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "GITHUB_TOKEN: ${{ secrets.STAR_HISTORY_TOKEN || github.token }}",
            workflow,
        )
        self.assertNotIn("GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}", workflow)

    def test_pages_workflow_uses_a_site_scoped_quality_gate(self) -> None:
        workflow = (ROOT / ".github/workflows/pages.yml").read_text(
            encoding="utf-8"
        )
        repository_workflow = (
            ROOT / ".github/workflows/validate-repository.yml"
        ).read_text(encoding="utf-8")
        package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
        site_test = package["scripts"].get("test:site", "")

        for module in (
            "tests.test_site_contracts",
            "tests.test_site_data",
            "tests.test_official_stars_contract",
            "tests.test_readme_contracts",
        ):
            self.assertIn(module, site_test)
        self.assertIn("npm run test:site", workflow)
        self.assertNotIn("run: npm test", workflow)
        self.assertNotIn("npm run validate:strict", workflow)
        self.assertIn("run: npm test", repository_workflow)
        self.assertIn("run: npm run validate:strict", repository_workflow)

    def test_homepage_shows_current_github_signal_instead_of_an_empty_history(self) -> None:
        homepage = (ROOT / "docs/index.html").read_text(encoding="utf-8")
        script = (ROOT / "docs/assets/site.js").read_text(encoding="utf-8")

        self.assertIn("GitHub repository signal", homepage)
        self.assertIn(
            "https://github.com/aAAaqwq/AGI-Super-Team/stargazers",
            homepage,
        )
        self.assertIn('data-star-count', homepage)
        self.assertIn('querySelectorAll("[data-star-count]")', script)
        self.assertRegex(homepage, r'assets/site\.css\?v=\d+')
        self.assertRegex(homepage, r'assets/site\.js\?v=\d+')
        self.assertNotIn("star-history-chart", homepage)
        self.assertNotIn("data/star-history.json", script)


if __name__ == "__main__":
    unittest.main()
