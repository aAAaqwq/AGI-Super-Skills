import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "skill_evidence.py"


def load_module():
    scripts_path = str(ROOT / "scripts")
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    spec = importlib.util.spec_from_file_location("skill_evidence_contract", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Skill evidence module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SkillEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_authored_contracts_validate_and_selected_reviews_are_current(self) -> None:
        provenance, curation = self.module.load_contracts(ROOT)
        self.assertEqual(provenance["scope"], "authored-provenance-evidence-not-runtime-verification")
        self.assertEqual(curation["scoreName"], "Curation evidence score")

        evidence = self.module.build_evidence_index(ROOT)
        for skill_id in ("content-typography", "jimeng-storyboard"):
            self.assertEqual(evidence[skill_id]["provenance"]["review_state"], "reviewed")
            self.assertEqual(evidence[skill_id]["curation"]["status"], "selected")

    def test_changed_skill_digest_hides_score_and_marks_review_stale(self) -> None:
        changed = "sha256:" + "0" * 64
        with mock.patch.object(self.module, "skill_tree_digest", return_value=changed):
            evidence = self.module.build_evidence_index(ROOT)

        selected = evidence["content-typography"]
        self.assertEqual(selected["provenance"]["review_state"], "stale")
        self.assertEqual(selected["curation"]["status"], "stale")
        self.assertNotIn("score", selected["curation"])

    def test_schema_rejects_collected_claim_without_pinned_upstream(self) -> None:
        document = json.loads((ROOT / "config" / "skill-provenance.json").read_text(encoding="utf-8"))
        schema = json.loads((ROOT / "config" / "skill-provenance.schema.json").read_text(encoding="utf-8"))
        forged = copy.deepcopy(document)
        forged["entries"][0] = {
            "skill_id": "agent-team-orchestration",
            "origin_kind": "collected",
            "review_state": "reviewed",
            "authors": ["Unknown"],
            "local_tree_digest": "sha256:" + "0" * 64,
            "declared_hints": [],
            "evidence": ["unresolved source hint"]
        }
        self.assertTrue(list(Draft202012Validator(schema).iter_errors(forged)))


if __name__ == "__main__":
    unittest.main()
