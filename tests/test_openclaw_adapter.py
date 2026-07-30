import base64
import json
import os
import subprocess
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
NODE = os.environ.get("NODE", "node")
ADAPTER_MODULE = ROOT / "bin" / "adapters" / "openclaw.mjs"
ADAPTER_MANIFEST = ROOT / "config" / "harness-adapters" / "openclaw.json"
ADAPTER_SCHEMA = ROOT / "config" / "harness-adapters" / "openclaw.schema.json"


class OpenClawAdapterTests(unittest.TestCase):
    def run_adapter(self, action: str, *, include_agents: bool = True, include_skills: bool = True):
        script = r"""
import { loadCatalog } from './bin/installer/catalog.mjs';
import { renderAdapterArtifacts, buildConnectionSpec } from './bin/adapters/openclaw.mjs';

const action = process.argv[1];
const includeAgents = process.argv[2] === 'true';
const includeSkills = process.argv[3] === 'true';
const packageRoot = process.cwd();
const catalog = loadCatalog(packageRoot);
const specialists = [
  catalog.specialistGroups.cto.specialists[0],
  catalog.specialistGroups.cpo.specialists[0],
];
const assignedSkills = {
  all: ['api-design-patterns', 'competitive-analysis', 'first-principles-thinking'],
  byAgent: {
    ceo: ['competitive-analysis', 'first-principles-thinking'],
    cto: ['api-design-patterns'],
  },
};
const common = {
  packageRoot,
  tool: catalog.tools.find((tool) => tool.id === 'openclaw'),
  agents: catalog.agents,
  groups: catalog.specialistGroups,
  specialists,
  assignedSkills,
};

if (action === 'render') {
  const artifacts = renderAdapterArtifacts({ ...common, includeAgents, includeSkills });
  process.stdout.write(JSON.stringify(artifacts.map((artifact) => ({
    relativePath: artifact.relativePath,
    label: artifact.label,
    content: Buffer.from(artifact.content).toString('base64'),
  }))));
} else if (action === 'connect') {
  process.stdout.write(JSON.stringify(buildConnectionSpec({
    ...common,
    home: '/tmp/isolated-openclaw-home',
  })));
} else if (action === 'unsafe-skill') {
  process.stdout.write(JSON.stringify(renderAdapterArtifacts({
    ...common,
    assignedSkills: { all: ['../escape'], byAgent: {} },
  })));
} else {
  throw new Error(`unknown action: ${action}`);
}
"""
        result = subprocess.run(
            [NODE, "--input-type=module", "-e", script, action, str(include_agents).lower(), str(include_skills).lower()],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def rendered_artifacts(self, **kwargs) -> dict[str, tuple[str, bytes]]:
        rendered = self.run_adapter("render", **kwargs)
        return {
            item["relativePath"]: (item["label"], base64.b64decode(item["content"]))
            for item in rendered
        }

    def test_manifest_is_schema_valid_and_keeps_runtime_evidence_pending(self) -> None:
        manifest = json.loads(ADAPTER_MANIFEST.read_text(encoding="utf-8"))
        schema = json.loads(ADAPTER_SCHEMA.read_text(encoding="utf-8"))

        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(manifest)
        self.assertEqual(manifest["harness"], "openclaw")
        self.assertEqual(manifest["runtimeEvidence"], "pending")
        self.assertEqual(manifest["requiredMaxDepth"], 2)
        self.assertEqual(manifest["maxChildrenPerAgent"], 2)
        self.assertFalse(manifest["connection"]["generateBindings"])

    def test_renders_fourteen_namespaced_canonical_workspaces_and_only_selected_specialists(self) -> None:
        artifacts = self.rendered_artifacts()
        manifest = json.loads((ROOT / "config" / "team-manifest.json").read_text(encoding="utf-8"))
        workspace_root = ".openclaw/agency-agents/agi-super-team"
        workspace_ids = {
            Path(path).parts[3]
            for path in artifacts
            if path.startswith(f"{workspace_root}/")
        }

        self.assertEqual(
            {f"ast-{agent['id']}" for agent in manifest["agents"]}
            | {"ast-cto-frontend-developer", "ast-cpo-ui-designer"},
            workspace_ids,
        )
        self.assertEqual(len([item for item in workspace_ids if item.count("-") == 1]), 14)
        self.assertNotIn("ast-cto-backend-architect", workspace_ids)

    def test_role_files_are_copied_verbatim_except_manager_routing_append(self) -> None:
        artifacts = self.rendered_artifacts()
        root = ".openclaw/agency-agents/agi-super-team"

        for filename in ("IDENTITY.md", "SOUL.md", "USER.md", "TOOLS.md", "MEMORY.md"):
            with self.subTest(filename=filename):
                self.assertEqual(
                    artifacts[f"{root}/ast-cto/{filename}"][1],
                    (ROOT / "agents" / "cto" / filename).read_bytes(),
                )
        canonical_manager = (ROOT / "agents" / "cto" / "AGENTS.md").read_bytes()
        rendered_manager = artifacts[f"{root}/ast-cto/AGENTS.md"][1]
        self.assertTrue(rendered_manager.startswith(canonical_manager))
        self.assertIn(b"sessions_spawn", rendered_manager)
        self.assertIn(b"ast-cto-frontend-developer", rendered_manager)
        self.assertNotIn(b"ast-cto-backend-architect", rendered_manager)

        self.assertEqual(
            artifacts[f"{root}/ast-pe/AGENTS.md"][1],
            (ROOT / "agents" / "pe" / "AGENTS.md").read_bytes(),
        )
        self.assertEqual(
            artifacts[f"{root}/ast-cto-frontend-developer/AGENTS.md"][1],
            (ROOT / "agents" / "cto" / "subagents" / "frontend-developer" / "AGENTS.md").read_bytes(),
        )

    def test_renders_only_openclaw_specific_orchestrator_skill(self) -> None:
        artifacts = self.rendered_artifacts()
        skill_root = ".openclaw/skills/agi-super-team"
        entrypoints = {
            path
            for path in artifacts
            if path.startswith(f"{skill_root}/") and path.endswith("/SKILL.md")
        }

        self.assertEqual(
            entrypoints,
            {
                f"{skill_root}/agi-super-team-orchestrator/SKILL.md",
            },
        )
        orchestrator = artifacts[f"{skill_root}/agi-super-team-orchestrator/SKILL.md"][1].decode()
        for tool_name in (
            "agents_list",
            "sessions_spawn",
            "sessions_yield",
            "sessions_history",
            "subagents",
        ):
            self.assertIn(tool_name, orchestrator)
        self.assertIn("childSessionKey", orchestrator)
        self.assertIn("不能只接受 CEO 转述", orchestrator)
        self.assertNotIn("spawn_agent", orchestrator)
        self.assertNotIn(".codex", orchestrator)

    def test_respects_independent_agent_and_skill_switches(self) -> None:
        without_agents = self.rendered_artifacts(include_agents=False, include_skills=True)
        self.assertFalse(any(path.startswith(".openclaw/agency-agents/") for path in without_agents))
        self.assertTrue(any(path.startswith(".openclaw/skills/") for path in without_agents))

        without_skills = self.rendered_artifacts(include_agents=True, include_skills=False)
        self.assertTrue(any(path.startswith(".openclaw/agency-agents/") for path in without_skills))
        self.assertFalse(any(path.startswith(".openclaw/skills/") for path in without_skills))

    def test_connection_spec_preserves_unmanaged_agents_and_never_generates_bindings(self) -> None:
        spec = self.run_adapter("connect")
        contract = spec["mergeContract"]

        self.assertEqual(spec["runtimeEvidence"], "pending")
        self.assertEqual(contract["path"], "agents.list")
        self.assertEqual(contract["key"], "id")
        self.assertEqual(contract["strategy"], "upsert-managed-preserve-unmanaged")
        self.assertTrue(contract["preserveUnmanaged"])
        self.assertFalse(contract["removeUnmentionedManaged"])
        self.assertNotIn("bindings", spec["configPatch"])
        self.assertEqual(spec["requirements"]["requiredMaxDepth"], 2)
        self.assertEqual(spec["requirements"]["maxChildrenPerAgent"], 2)
        self.assertIn(
            "governor-raw-child-session-history-observed",
            spec["canary"]["requiredChecks"],
        )

    def test_connection_allowlists_follow_ceo_manager_leaf_boundaries(self) -> None:
        spec = self.run_adapter("connect")
        entries = {entry["id"]: entry for entry in spec["configPatch"]["agents"]["list"]}
        canonical = json.loads((ROOT / "config" / "team-manifest.json").read_text(encoding="utf-8"))["agents"]

        self.assertEqual(
            set(entries["ast-ceo"]["subagents"]["allowAgents"]),
            {f"ast-{agent['id']}" for agent in canonical if agent["id"] != "ceo"},
        )
        self.assertEqual(
            entries["ast-cto"]["subagents"]["allowAgents"],
            ["ast-pe", "ast-cto-frontend-developer"],
        )
        self.assertEqual(entries["ast-cpo"]["subagents"]["allowAgents"], ["ast-cpo-ui-designer"])
        self.assertNotIn("ast-cpo-ui-designer", entries["ast-cto"]["subagents"]["allowAgents"])

        for leaf in ("ast-pe", "ast-governor", "ast-cto-frontend-developer", "ast-cpo-ui-designer"):
            with self.subTest(leaf=leaf):
                self.assertEqual(entries[leaf]["subagents"]["allowAgents"], [])
                self.assertTrue(entries[leaf]["subagents"]["requireAgentId"])
                self.assertIn("sessions_spawn", entries[leaf]["tools"]["deny"])

    def test_connection_spec_assigns_only_declared_agent_skills(self) -> None:
        spec = self.run_adapter("connect")
        entries = {entry["id"]: entry for entry in spec["configPatch"]["agents"]["list"]}

        self.assertEqual(
            entries["ast-ceo"]["skills"],
            ["agi-super-team-orchestrator", "competitive-analysis", "first-principles-thinking"],
        )
        self.assertEqual(entries["ast-cto"]["skills"], ["api-design-patterns"])
        self.assertEqual(entries["ast-cpo"]["skills"], [])
        self.assertEqual(entries["ast-cto-frontend-developer"]["skills"], [])

    def test_rejects_skill_path_traversal(self) -> None:
        script = r"""
import { loadCatalog } from './bin/installer/catalog.mjs';
import { renderAdapterArtifacts } from './bin/adapters/openclaw.mjs';
const root = process.cwd();
const catalog = loadCatalog(root);
renderAdapterArtifacts({
  packageRoot: root,
  tool: catalog.tools.find((tool) => tool.id === 'openclaw'),
  agents: catalog.agents,
  groups: catalog.specialistGroups,
  specialists: [],
  assignedSkills: { all: ['../escape'], byAgent: {} },
});
"""
        result = subprocess.run(
            [NODE, "--input-type=module", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe skill id", result.stderr)


if __name__ == "__main__":
    unittest.main()
