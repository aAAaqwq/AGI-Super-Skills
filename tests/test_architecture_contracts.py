import copy
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
AUDITOR_PATH = ROOT / "scripts" / "audit_architecture.py"
CONTRACT_PATH = ROOT / "config" / "repository-architecture.json"
SCHEMA_PATH = ROOT / "config" / "repository-architecture.schema.json"


def load_auditor():
    spec = importlib.util.spec_from_file_location("audit_architecture", AUDITOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load architecture auditor")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ArchitectureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.auditor = load_auditor()
        cls.contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))

    def test_repository_contract_is_complete_and_scores_at_least_95(self) -> None:
        result = self.auditor.audit_repository(ROOT, self.contract)
        self.assertEqual(result["issues"], [])
        self.assertGreaterEqual(result["classificationContractScore"], 95)
        self.assertEqual(result["classificationContractScore"], 100)
        self.assertEqual(result["scoreSemantics"], "automated architecture-classification contracts")

    def test_contract_uses_the_shared_architecture_vocabulary(self) -> None:
        self.assertEqual(self.contract["$schema"], "./repository-architecture.schema.json")
        self.assertEqual(self.contract["schemaVersion"], 1)
        self.assertTrue(SCHEMA_PATH.is_file())
        vocabulary = self.contract["vocabulary"]
        self.assertEqual(
            set(vocabulary),
            {"Module", "Interface", "Implementation", "Depth", "Seam", "Adapter", "Leverage", "Locality"},
        )
        self.assertTrue(all(len(definition) >= 24 for definition in vocabulary.values()))

    def test_every_public_top_level_area_has_one_primary_owner_and_role(self) -> None:
        expected = {
            ".github",
            ".codex",
            "agents",
            "assets",
            "catalog",
            "config",
            "cookbook",
            "docs",
            "growth",
            "plugins",
            "scripts",
            "skills",
            "starter-kits",
            "tests",
        }
        paths = [item["path"] for item in self.contract["pathOwnership"]]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertTrue(expected <= set(paths))
        known_modules = {item["id"] for item in self.contract["modules"]}
        self.assertTrue(all(item["module"] in known_modules for item in self.contract["pathOwnership"]))

    def test_every_tracked_managed_path_has_one_effective_owner(self) -> None:
        self.assertEqual(self.auditor.tracked_ownership_issues(ROOT, self.contract), [])

    def test_authority_and_generated_output_cannot_be_confused(self) -> None:
        invalid = copy.deepcopy(self.contract)
        generated = next(item for item in invalid["pathOwnership"] if item["role"] == "generated-output")
        generated["authority"] = True
        issues = self.auditor.validate_contract(ROOT, invalid)
        self.assertTrue(any("authority must be true only" in issue for issue in issues))

    def test_generated_output_must_declare_lineage_and_check(self) -> None:
        invalid = copy.deepcopy(self.contract)
        generated = next(item for item in invalid["pathOwnership"] if item["role"] == "generated-output")
        generated.pop("generatedBy")
        generated.pop("verify")
        issues = self.auditor.validate_contract(ROOT, invalid)
        self.assertTrue(any("generated output requires generatedBy" in issue for issue in issues))
        self.assertTrue(any("generated output requires verify" in issue for issue in issues))

    def test_duplicate_path_ownership_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.contract)
        invalid["pathOwnership"].append(copy.deepcopy(invalid["pathOwnership"][0]))
        issues = self.auditor.validate_contract(ROOT, invalid)
        self.assertTrue(any("path ownership must be unique" in issue for issue in issues))

    def test_distribution_adapters_do_not_claim_runtime_verification(self) -> None:
        for item in self.contract["pathOwnership"]:
            if item["role"] == "distribution-adapter":
                self.assertFalse(item["authority"])
                self.assertIn(item["evidenceStatus"], {"manifest", "pending", "legacy"})

    def test_taxonomy_health_is_part_of_the_architecture_gate(self) -> None:
        result = self.auditor.audit_repository(ROOT, self.contract)
        metrics = result["taxonomy"]
        tracked = subprocess.run(
            ["git", "ls-files", "skills/*/SKILL.md"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        canonical = [path for path in tracked if len(Path(path).parts) == 3]
        self.assertEqual(metrics["inventoryCount"], len(canonical))
        self.assertLessEqual(metrics["fallbackRatio"], self.contract["qualityGates"]["taxonomy"]["maxFallbackRatio"])
        self.assertLessEqual(metrics["overrideRatio"], self.contract["qualityGates"]["taxonomy"]["maxOverrideRatio"])
        self.assertLessEqual(
            metrics["multipleCategoryMatchRatio"],
            self.contract["qualityGates"]["taxonomy"]["maxMultipleCategoryMatchRatio"],
        )
        self.assertEqual(metrics["deterministicTieBreakFailures"], 0)
        self.assertEqual(
            metrics["unreviewedPriorityResolvedTies"],
            metrics["priorityResolvedTopScoreTies"],
        )

    def test_generic_install_payload_excludes_harness_specific_skills(self) -> None:
        manifest = json.loads(
            (ROOT / "config/team-manifest.json").read_text(encoding="utf-8")
        )
        harness_specific = set()
        portable = set()
        for agent in manifest["agents"]:
            skills = agent["skills"]
            self.assertEqual(
                set(skills),
                {"required", "optional", "harnessSpecific", "recommendedExternal"},
            )
            harness_specific.update(skills["harnessSpecific"])
            portable.update(skills["required"])
            portable.update(skills["optional"])
        self.assertTrue(harness_specific)
        self.assertFalse(harness_specific & portable)
        self.assertEqual(self.auditor.installed_workspace_issues(ROOT), [])

    def test_critical_contract_failure_caps_the_score(self) -> None:
        invalid = copy.deepcopy(self.contract)
        generated = next(item for item in invalid["pathOwnership"] if item["role"] == "generated-output")
        generated["authority"] = True
        result = self.auditor.audit_repository(ROOT, invalid)
        self.assertLessEqual(result["classificationContractScore"], 60)
        self.assertNotEqual(result["issues"], [])

    def test_taxonomy_debt_ceiling_cannot_be_relaxed_inside_the_contract(self) -> None:
        invalid = copy.deepcopy(self.contract)
        invalid["qualityGates"]["taxonomy"]["maxFallbackRatio"] = 0.10
        issues = self.auditor.validate_contract(ROOT, invalid)
        self.assertTrue(any("cannot exceed hard ceiling" in issue for issue in issues))

    def test_adversarial_contract_mutations_fail_closed(self) -> None:
        mutations = {}

        empty_routes = copy.deepcopy(self.contract)
        empty_routes["qualityGates"]["requiredEntrypoints"] = []
        empty_routes["qualityGates"]["requiredDecisions"] = []
        mutations["empty routes"] = empty_routes

        wrong_owner = copy.deepcopy(self.contract)
        next(item for item in wrong_owner["pathOwnership"] if item["path"] == "catalog")["module"] = "governance-memory"
        mutations["wrong critical owner"] = wrong_owner

        fake_lineage = copy.deepcopy(self.contract)
        generated = next(item for item in fake_lineage["pathOwnership"] if item["path"] == "catalog")
        generated["generatedBy"] = "README.md"
        generated["verify"] = "true"
        mutations["fake lineage"] = fake_lineage

        unknown_seam = copy.deepcopy(self.contract)
        unknown_seam["modules"][0]["seams"].append("missing-module")
        mutations["unknown seam"] = unknown_seam

        extra_field = copy.deepcopy(self.contract)
        extra_field["unexpected"] = True
        mutations["schema extra field"] = extra_field

        invalid_vocabulary = copy.deepcopy(self.contract)
        invalid_vocabulary["vocabulary"]["Module"] = 42
        mutations["invalid vocabulary"] = invalid_vocabulary

        invalid_module_scope = copy.deepcopy(self.contract)
        next(
            item for item in invalid_module_scope["pathOwnership"]
            if item["path"] == ".gitignore"
        )["module"] = "catalog-discovery"
        mutations["noncritical path outside module scope"] = invalid_module_scope

        invalid_modules_type = copy.deepcopy(self.contract)
        invalid_modules_type["modules"] = 42
        mutations["invalid modules type"] = invalid_modules_type

        invalid_ownership_type = copy.deepcopy(self.contract)
        invalid_ownership_type["pathOwnership"] = "bad"
        mutations["invalid ownership type"] = invalid_ownership_type

        for name, invalid in mutations.items():
            with self.subTest(name=name):
                result = self.auditor.audit_repository(ROOT, invalid)
                self.assertNotEqual(result["issues"], [])
                self.assertLess(result["classificationContractScore"], 95)

    def test_context_and_decisions_are_first_class_navigation(self) -> None:
        context = (ROOT / "CONTEXT.md").read_text(encoding="utf-8")
        architecture = (ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
        adr_index = (ROOT / "docs" / "adr" / "README.md").read_text(encoding="utf-8")
        for term in self.contract["vocabulary"]:
            self.assertIn(term, context)
        for route in ("CONTEXT.md", "docs/adr/", "config/repository-architecture.json"):
            self.assertIn(route, architecture)
        self.assertIn("0001-canonical-inventory-and-generated-outputs.md", adr_index)
        self.assertIn("0002-generic-workspace-and-curated-distributions.md", adr_index)
        self.assertIn("0003-structural-evidence-and-runtime-receipts.md", adr_index)

    def test_verification_receipt_is_schema_valid_and_fail_closed(self) -> None:
        schema = json.loads((ROOT / "docs/data/verification-receipt.schema.json").read_text(encoding="utf-8"))
        receipt = json.loads((ROOT / "docs/data/verification-receipt.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(receipt)
        if receipt["result"] == "passed":
            self.assertEqual(receipt["commit"], receipt["siteCommit"])
            self.assertTrue(all(check["result"] == "passed" for check in receipt["checks"]))

    def test_cli_check_is_deterministic_and_machine_readable(self) -> None:
        command = [sys.executable, str(AUDITOR_PATH), "--root", str(ROOT), "--format", "json", "--check"]
        first = subprocess.run(command, capture_output=True, text=True, check=False)
        second = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        payload = json.loads(first.stdout)
        self.assertEqual(payload["classificationContractScore"], 100)


if __name__ == "__main__":
    unittest.main()
