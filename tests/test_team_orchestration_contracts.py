import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
MODEL_PATH = ROOT / "scripts" / "repository_model.py"


def load_module(path: Path, name: str):
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TeamOrchestrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.model = load_module(MODEL_PATH, "team_orchestration_repository_model")
        cls.manifest = json.loads(
            (ROOT / "config" / "team-manifest.json").read_text(encoding="utf-8")
        )
        cls.schema = json.loads(
            (ROOT / "config" / "team-manifest.schema.json").read_text(
                encoding="utf-8"
            )
        )

    def test_manifest_is_schema_valid_and_exposes_eight_outcome_kits(self) -> None:
        Draft202012Validator.check_schema(self.schema)
        Draft202012Validator(self.schema).validate(self.manifest)
        self.assertEqual(
            {kit["id"] for kit in self.manifest["kits"]},
            {
                "solo-founder",
                "content-creator",
                "quant-trader",
                "product-delivery",
                "research-decision",
                "go-to-market",
                "operations-response",
                "full-team",
            },
        )

    def test_each_kit_has_a_complete_portable_orchestration_contract(self) -> None:
        expected_fields = {
            "id",
            "name",
            "outcome",
            "entrypoint",
            "coordinator",
            "reviewers",
            "coreAgents",
            "agents",
            "outputs",
            "checks",
        }
        known_agents = {agent["id"] for agent in self.manifest["agents"]}
        for kit in self.manifest["kits"]:
            with self.subTest(kit=kit["id"]):
                self.assertEqual(set(kit), expected_fields)
                members = set(kit["agents"])
                core = set(kit["coreAgents"])
                reviewers = set(kit["reviewers"])
                self.assertTrue(members <= known_agents)
                self.assertTrue(core <= members)
                self.assertIn(kit["coordinator"], core)
                self.assertTrue(reviewers)
                self.assertTrue(reviewers <= core)
                self.assertNotIn(kit["coordinator"], reviewers)
                self.assertGreaterEqual(len(kit["outputs"]), 2)
                self.assertGreaterEqual(len(kit["checks"]), 2)

    def test_full_team_has_one_ceo_coordinator_and_governor_review(self) -> None:
        full_team = next(
            kit for kit in self.manifest["kits"] if kit["id"] == "full-team"
        )
        roster = {agent["id"] for agent in self.manifest["agents"]}
        self.assertEqual(set(full_team["agents"]), roster)
        self.assertEqual(full_team["coordinator"], "ceo")
        self.assertEqual(full_team["reviewers"], ["governor"])
        self.assertIn("ceo", full_team["coreAgents"])
        self.assertIn("governor", full_team["coreAgents"])

    def test_repository_model_rejects_relational_kit_contract_violations(self) -> None:
        cases = {
            "unknown coordinator": (
                lambda manifest: manifest["kits"][0].__setitem__(
                    "coordinator", "missing-role"
                ),
                "manifest.kit_unknown_coordinator",
            ),
            "reviewer outside members": (
                lambda manifest: manifest["kits"][0].__setitem__(
                    "reviewers", ["governor"]
                    if "governor" not in manifest["kits"][0]["agents"]
                    else ["cto"]
                ),
                "manifest.kit_reviewer_membership",
            ),
            "core outside members": (
                lambda manifest: manifest["kits"][0].__setitem__(
                    "coreAgents", [*manifest["kits"][0]["coreAgents"], "cto"]
                    if "cto" not in manifest["kits"][0]["agents"]
                    else [*manifest["kits"][0]["coreAgents"], "cqo"]
                ),
                "manifest.kit_core_membership",
            ),
            "coordinator also reviewer": (
                lambda manifest: manifest["kits"][0].__setitem__(
                    "reviewers", [manifest["kits"][0]["coordinator"]]
                ),
                "manifest.kit_review_independence",
            ),
        }
        for name, (mutate, expected_code) in cases.items():
            with self.subTest(name=name):
                manifest = copy.deepcopy(self.manifest)
                mutate(manifest)
                report = self.model.validate_team_orchestration_contracts(
                    ROOT, manifest
                )
                self.assertIn(expected_code, {issue.code for issue in report.issues})

    def test_every_entrypoint_is_a_runnable_capability_aware_runbook(self) -> None:
        required_sections = (
            "## Input",
            "## Waves",
            "## Artifacts",
            "## Checks",
            "## Capability fallback",
            "## Human approval",
        )
        for kit in self.manifest["kits"]:
            entrypoint = ROOT / kit["entrypoint"]
            with self.subTest(kit=kit["id"], entrypoint=kit["entrypoint"]):
                self.assertTrue(entrypoint.is_file())
                text = entrypoint.read_text(encoding="utf-8")
                for heading in required_sections:
                    self.assertIn(heading, text)
                for agent_id in kit["coreAgents"]:
                    self.assertIn(f"`{agent_id}`", text)
                self.assertIn("Validation pending", text)

    def test_full_team_runbook_bounds_parallelism_and_avoids_mass_fan_out(self) -> None:
        full_team = next(
            kit for kit in self.manifest["kits"] if kit["id"] == "full-team"
        )
        text = (ROOT / full_team["entrypoint"]).read_text(encoding="utf-8")
        self.assertIn("smallest relevant subset", text)
        self.assertRegex(text, r"2(?:–|-| to )3")
        self.assertIn("Never start all 14 roles at once", text)


if __name__ == "__main__":
    unittest.main()
