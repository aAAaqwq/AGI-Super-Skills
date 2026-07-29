import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER_PATH = ROOT / "scripts" / "build_agent_skill_indexes.py"


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


class AgentSkillIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = load_module(BUILDER_PATH, "build_agent_skill_indexes")
        cls.quality = load_module(ROOT / "scripts" / "audit_skill_quality.py", "agent_index_quality")
        cls.manifest = json.loads((ROOT / "config" / "team-manifest.json").read_text(encoding="utf-8"))

    def test_generated_indexes_are_current(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BUILDER_PATH), "--root", str(ROOT), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_every_agent_index_exposes_manifest_contract_and_assignments(self) -> None:
        outputs = self.builder.build_outputs(ROOT)
        self.assertEqual(len(outputs), self.manifest["inventory"]["agentCount"])
        for agent in self.manifest["agents"]:
            path = ROOT / agent["path"] / "TOOLS.md"
            content = outputs[path]
            self.assertIn(self.builder.GENERATED_MARKER, content)
            self.assertIn(agent["focus"], content)
            self.assertIn(agent["boundary"], content)
            for output in agent["outputs"]:
                self.assertIn(output, content)
            for level in ("required", "optional", "harnessSpecific"):
                for skill_id in agent["skills"][level]:
                    self.assertIn(f"../../skills/{skill_id}/", content)

    def test_indexes_show_fail_closed_origin_and_curation_labels(self) -> None:
        outputs = self.builder.build_outputs(ROOT)
        cco = outputs[ROOT / "agents" / "cco" / "TOOLS.md"]
        self.assertIn("项目原创 · 80/100 精选 · 运行证据：待验证", cco)

        ceo = outputs[ROOT / "agents" / "ceo" / "TOOLS.md"]
        self.assertIn("来源待核 · 尚未评分 · 运行证据：待验证", ceo)
        self.assertNotIn("来源待核 · 外部收录", ceo)

    def test_required_stacks_are_structurally_valid_and_need_no_execution_review(self) -> None:
        report = self.quality.build_report(ROOT)
        evidence = {item["skill_id"]: item for item in report["skills"]}
        failures = []
        for agent in self.manifest["agents"]:
            for skill_id in agent["skills"]["required"]:
                item = evidence.get(skill_id, {})
                if item.get("structure_status") == "invalid" or item.get("execution_status") == "review-required":
                    failures.append(f"{agent['id']}:{skill_id}")
        self.assertEqual(failures, [])

    def test_all_local_assignments_are_structurally_valid(self) -> None:
        report = self.quality.build_report(ROOT)
        evidence = {item["skill_id"]: item for item in report["skills"]}
        failures = []
        for agent in self.manifest["agents"]:
            for level in ("required", "optional", "harnessSpecific"):
                for skill_id in agent["skills"][level]:
                    if evidence.get(skill_id, {}).get("structure_status") == "invalid":
                        failures.append(f"{agent['id']}:{level}:{skill_id}")
        self.assertEqual(failures, [])

    def test_curated_shadow_indexes_do_not_exist(self) -> None:
        self.assertEqual(list((ROOT / "agents").glob("*/TOOLS_CURATED.md")), [])


if __name__ == "__main__":
    unittest.main()
