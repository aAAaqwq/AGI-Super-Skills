import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
ADAPTER_PATH = ROOT / "config" / "harness-adapters" / "hermes.json"
SCHEMA_PATH = ROOT / "config" / "harness-adapters" / "hermes.schema.json"
MODULE_PATH = ROOT / "bin" / "adapters" / "hermes.mjs"


def run_node(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", "--input-type=module", "--eval", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def fixture_script(action: str, *, home: str = "/tmp/hermes-adapter-home") -> str:
    return f"""
import {{ readFileSync }} from "node:fs";
import {{ join }} from "node:path";
import {{ ADAPTER_ID, renderAdapterArtifacts, buildConnectionSpec }} from {json.dumps(MODULE_PATH.as_uri())};

const packageRoot = {json.dumps(str(ROOT))};
const readJson = (relative) => JSON.parse(readFileSync(join(packageRoot, relative), "utf8"));
const manifest = readJson("config/team-manifest.json");
const sourceLock = readJson("config/agent-sources.lock.json");
const registry = readJson("config/cpo-specialists.json");
const sourceByRole = new Map(sourceLock.entries.map((entry) => [`${{entry.manager}}/${{entry.id}}`, entry]));
const cpoSpecialists = registry.specialists.map((specialist) => ({{
  ...specialist,
  manager: "cpo",
  vendoredPath: sourceByRole.get(`cpo/${{specialist.id}}`).vendoredPath,
}}));
const groups = {{ cpo: {{ manager: "cpo", roleRoutes: registry.roleRoutes, specialists: cpoSpecialists }} }};
const specialists = groups.cpo.specialists;
const agents = manifest.agents;
const assignedSkills = {{
  all: ["accessibility-compliance-accessibility-audit", "ux-heuristics"],
  byAgent: Object.fromEntries(agents.map((agent) => [agent.id, agent.id === "cpo" ? ["ux-heuristics"] : []])),
}};
const tool = {{ id: "hermes" }};
{action}
"""


class HermesAdapterTests(unittest.TestCase):
    def test_contract_is_schema_valid_and_maps_all_canonical_roles(self) -> None:
        adapter = json.loads(ADAPTER_PATH.read_text(encoding="utf-8"))
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        manifest = json.loads(
            (ROOT / "config" / "team-manifest.json").read_text(encoding="utf-8")
        )
        hierarchy = json.loads(
            (ROOT / "config" / "agent-hierarchy.json").read_text(encoding="utf-8")
        )

        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(adapter)

        canonical_ids = {agent["id"] for agent in manifest["agents"]}
        self.assertEqual(adapter["harness"], "hermes")
        self.assertEqual(adapter["runtimeEvidence"], "pending")
        self.assertEqual(set(adapter["profileMap"]), canonical_ids)
        self.assertEqual(adapter["requiredMaxDepth"], 2)
        self.assertEqual(adapter["maxConcurrentChildren"], 2)
        self.assertEqual(adapter["coordinator"], "ceo")
        self.assertEqual(adapter["independentReviewer"], "governor")
        self.assertEqual(adapter["runtimePaths"]["roleSkillRoot"], "skills/agi-super-team-agents")
        self.assertEqual(
            adapter["runtimePaths"]["orchestratorSkill"],
            "skills/agi-super-team-orchestrator/SKILL.md",
        )
        self.assertEqual(
            adapter["runtimePaths"]["profileBlueprintRoot"],
            "agi-super-team/profiles",
        )
        self.assertEqual(
            {role for role, profile in adapter["profileMap"].items() if profile["roleType"] == "manager"},
            set(hierarchy["managers"]),
        )
        self.assertEqual(adapter["profileMap"]["ceo"]["roleType"], "coordinator")
        self.assertEqual(adapter["profileMap"]["pe"]["roleType"], "leaf")
        self.assertEqual(adapter["profileMap"]["governor"]["roleType"], "independent-reviewer")
        self.assertTrue(adapter["kanbanPolicy"]["roleSkillPinningRequired"])
        self.assertFalse(adapter["sideEffects"]["createProfiles"])
        self.assertFalse(adapter["sideEffects"]["createCron"])
        self.assertFalse(adapter["sideEffects"]["startGateway"])

    def test_renderer_emits_role_skills_selected_specialists_orchestrator_and_blueprints(self) -> None:
        result = run_node(
            fixture_script(
                """
const artifacts = renderAdapterArtifacts({ packageRoot, tool, agents, groups, specialists, assignedSkills });
console.log(JSON.stringify({
  adapterId: ADAPTER_ID,
  artifacts: artifacts.map((artifact) => ({
    relativePath: artifact.relativePath,
    label: artifact.label,
    content: Buffer.isBuffer(artifact.content) ? artifact.content.toString("utf8") : String(artifact.content),
  })),
}));
"""
            )
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        artifacts = {item["relativePath"]: item for item in payload["artifacts"]}

        self.assertEqual(payload["adapterId"], "hermes")
        self.assertEqual(len(artifacts), 14 + 3 + 1 + 14)
        for role in ("ceo", "cto", "pe", "governor"):
            role_path = f"skills/agi-super-team-agents/ast-{role}/SKILL.md"
            blueprint_path = f"agi-super-team/profiles/ast-{role}/profile.json"
            self.assertTrue(
                role_path in artifacts,
                f"Hermes role artifact must be HERMES_HOME-relative; got {list(artifacts)[:3]}",
            )
            self.assertTrue(
                blueprint_path in artifacts,
                f"Hermes blueprint must be HERMES_HOME-relative; got {list(artifacts)[:3]}",
            )
            self.assertIn(f"name: ast-{role}", artifacts[role_path]["content"])
            blueprint = json.loads(artifacts[blueprint_path]["content"])
            self.assertEqual(blueprint["profileId"], f"ast-{role}")
            self.assertTrue(blueprint["blueprintOnly"])
            self.assertFalse(blueprint["runtimeStateCreated"])
            self.assertEqual(blueprint["kanbanTaskSkills"][0], f"ast-{role}")

        specialist_path = "skills/agi-super-team-agents/ast-cpo-ui-designer/SKILL.md"
        self.assertIn(specialist_path, artifacts)
        self.assertIn("不得创建子 Agent", artifacts[specialist_path]["content"])

        orchestrator_path = "skills/agi-super-team-orchestrator/SKILL.md"
        self.assertIn(orchestrator_path, artifacts)
        orchestrator = artifacts[orchestrator_path]["content"]
        self.assertIn("Profiles + Kanban", orchestrator)
        self.assertIn("delegate_task(profile=...)", orchestrator)
        self.assertIn("匿名短任务", orchestrator)
        self.assertIn("runtimeEvidence: pending", orchestrator)
        self.assertIn("kanban_create", orchestrator)
        self.assertIn("skills", orchestrator)

        self.assertFalse(
            any("~/.hermes" in artifact["content"] for artifact in artifacts.values()),
            "Hermes artifacts must resolve from HERMES_HOME instead of a hard-coded default home",
        )

        self.assertFalse(
            any(path.startswith("skills/agi-super-team/") for path in artifacts),
            "canonical Skills are copied by the shared installer, not the Hermes adapter",
        )

    def test_connection_spec_is_depth_two_and_keeps_governor_independent(self) -> None:
        result = run_node(
            fixture_script(
                """
const spec = buildConnectionSpec({ home: %s, tool, agents, groups, specialists, assignedSkills });
console.log(JSON.stringify(spec));
""" % json.dumps("/tmp/hermes-adapter-home")
            )
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        spec = json.loads(result.stdout)

        self.assertEqual(spec["harness"], "hermes")
        self.assertEqual(spec["runtimeEvidence"], "pending")
        self.assertEqual(spec["requiredMaxDepth"], 2)
        self.assertEqual(spec["maxConcurrentChildren"], 2)
        self.assertEqual(len(spec["profileMap"]), 14)
        self.assertEqual(spec["profileMap"]["cpo"]["profileId"], "ast-cpo")
        self.assertEqual(
            spec["profileMap"]["cpo"]["kanbanTaskSkills"],
            ["ast-cpo", "ux-heuristics"],
        )
        self.assertEqual(
            spec["permissions"]["manager"]["allowedRoleSkills"],
            [
                "ast-cpo-ui-designer",
                "ast-cpo-ux-architect",
                "ast-cpo-ux-researcher",
            ],
        )
        self.assertEqual(spec["permissions"]["manager"]["delegateTask"]["mode"], "anonymous-short-task-only")
        self.assertFalse(spec["permissions"]["manager"]["delegateTask"]["profileArgumentAllowed"])
        self.assertFalse(spec["permissions"]["leaf"]["delegateTask"]["allowed"])
        self.assertTrue(spec["permissions"]["governor"]["independent"])
        self.assertFalse(spec["permissions"]["governor"]["delegateTask"]["allowed"])
        self.assertTrue(spec["kanbanPolicy"]["governorRunsInSeparateProfile"])
        self.assertTrue(spec["kanbanPolicy"]["roleSkillPinningRequired"])
        self.assertEqual(
            spec["kanbanPolicy"]["ceoSynthesisDependsOn"],
            ["manager-output", "governor-review"],
        )
        self.assertFalse(spec["sideEffects"]["createCron"])
        self.assertFalse(spec["sideEffects"]["startGateway"])
        self.assertEqual(spec["assignedSkills"]["all"], ["accessibility-compliance-accessibility-audit", "ux-heuristics"])
        self.assertEqual(spec["assignedSkills"]["byAgent"]["cpo"], ["ux-heuristics"])
        target_home = Path("/tmp/hermes-adapter-home")
        self.assertEqual(
            Path(spec["paths"]["roleSkillRoot"]),
            target_home / "skills/agi-super-team-agents",
        )
        self.assertEqual(
            Path(spec["paths"]["orchestratorSkill"]),
            target_home / "skills/agi-super-team-orchestrator/SKILL.md",
        )
        self.assertEqual(
            Path(spec["paths"]["profileBlueprintRoot"]),
            target_home / "agi-super-team/profiles",
        )
        self.assertNotIn(".hermes", json.dumps(spec))

    def test_connection_spec_is_pure_and_does_not_create_home(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            home = Path(temporary_directory) / "not-created"
            result = run_node(
                fixture_script(
                    f"""
const spec = buildConnectionSpec({{ home: {json.dumps(str(home))}, tool, agents, groups, specialists, assignedSkills }});
console.log(JSON.stringify(spec));
"""
                )
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(home.exists())

    def test_renderer_respects_agent_and_skill_selection_flags(self) -> None:
        result = run_node(
            fixture_script(
                """
const withoutAgents = renderAdapterArtifacts({ packageRoot, tool, agents: [], groups: {}, specialists: [], assignedSkills, includeAgents: false, includeSkills: true });
const withoutOrchestrator = renderAdapterArtifacts({ packageRoot, tool, agents, groups, specialists, assignedSkills, includeAgents: true, includeSkills: false });
const emptyConnection = buildConnectionSpec({ home: "/tmp/hermes-adapter-home", tool, agents: [], groups: {}, specialists: [], assignedSkills });
console.log(JSON.stringify({
  withoutAgents: withoutAgents.length,
  withoutOrchestrator: withoutOrchestrator.map((artifact) => artifact.relativePath),
  emptyProfiles: Object.keys(emptyConnection.profileMap).length,
}));
"""
            )
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["withoutAgents"], 1)
        self.assertEqual(payload["emptyProfiles"], 0)
        self.assertFalse(
            any("agi-super-team-orchestrator" in path for path in payload["withoutOrchestrator"])
        )
        self.assertEqual(len(payload["withoutOrchestrator"]), 14 + 3 + 14)

    def test_renderer_fails_closed_on_incomplete_skill_assignments(self) -> None:
        result = run_node(
            fixture_script(
                """
const broken = { all: ["ux-heuristics"], byAgent: { ceo: [] } };
renderAdapterArtifacts({ packageRoot, tool, agents, groups, specialists, assignedSkills: broken });
"""
            )
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("assignedSkills.byAgent", result.stderr)


if __name__ == "__main__":
    unittest.main()
