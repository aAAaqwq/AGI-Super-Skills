import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NODE = os.environ.get("NODE", "node")


def run_adapter(expression: str) -> object:
    script = f"""
import {{ loadCatalog }} from './bin/installer/catalog.mjs';
import {{ ADAPTER_ID, renderAdapterArtifacts, buildConnectionSpec }} from './bin/adapters/claude-code.mjs';
const catalog = loadCatalog(process.cwd());
const tool = catalog.tools.find((candidate) => candidate.id === 'claude-code');
const specialists = Object.values(catalog.specialistGroups).flatMap((group) => group.specialists);
const result = {expression};
process.stdout.write(JSON.stringify(result));
"""
    result = subprocess.run(
        [NODE, "--input-type=module", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return json.loads(result.stdout)


class ClaudeCodeAdapterTests(unittest.TestCase):
    def test_static_contract_keeps_runtime_evidence_pending(self) -> None:
        manifest_path = ROOT / "config" / "harness-adapters" / "claude-code.json"
        schema_path = ROOT / "config" / "harness-adapters" / "claude-code.schema.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["$schema"], "./claude-code.schema.json")
        self.assertEqual(manifest["runtimeEvidence"], "pending")
        self.assertEqual(manifest["agentMap"]["ceo"], "ast-ceo")
        self.assertEqual(len(manifest["agentMap"]), 14)
        self.assertEqual(schema["properties"]["runtimeEvidence"]["enum"][0], "pending")

    def test_renders_every_canonical_agent_with_ast_runtime_names(self) -> None:
        artifacts = run_adapter(
            "renderAdapterArtifacts({"
            "packageRoot: process.cwd(), tool, agents: catalog.agents, "
            "groups: catalog.specialistGroups, specialists: [], assignedSkills: {}"
            "}).map(({ relativePath, content, label }) => ({"
            "relativePath, content: content.toString(), label"
            "}))"
        )

        agent_artifacts = [
            artifact
            for artifact in artifacts
            if artifact["relativePath"].startswith(".claude/agents/")
        ]
        self.assertEqual(len(agent_artifacts), 14)
        names = {
            artifact["relativePath"].removeprefix(".claude/agents/").removesuffix(".md")
            for artifact in agent_artifacts
        }
        self.assertEqual(
            names,
            {
                "ast-ceo", "ast-cto", "ast-pe", "ast-cpo", "ast-cqo", "ast-cmo",
                "ast-cfo", "ast-cdo", "ast-cco", "ast-clo", "ast-cro", "ast-cso",
                "ast-coo", "ast-governor",
            },
        )

    def test_renders_every_selected_specialist_as_a_leaf_agent(self) -> None:
        artifacts = run_adapter(
            "renderAdapterArtifacts({"
            "packageRoot: process.cwd(), tool, agents: catalog.agents, "
            "groups: catalog.specialistGroups, specialists, assignedSkills: {}"
            "}).map(({ relativePath, content }) => ({"
            "relativePath, content: content.toString()"
            "}))"
        )

        specialist_artifacts = [
            artifact
            for artifact in artifacts
            if artifact["relativePath"].startswith(".claude/agents/ast-")
            and artifact["relativePath"].count("-") >= 2
        ]
        self.assertEqual(len(specialist_artifacts), 92)
        xiaohongshu = next(
            artifact
            for artifact in specialist_artifacts
            if artifact["relativePath"].endswith("ast-cco-xiaohongshu-operator.md")
        )
        self.assertIn("name: ast-cco-xiaohongshu-operator", xiaohongshu["content"])
        self.assertIn("disallowedTools: Agent", xiaohongshu["content"])
        self.assertIn("小红书运营专家", xiaohongshu["content"])

    def test_only_coordinator_and_managers_may_use_the_agent_tool(self) -> None:
        contents = run_adapter(
            "Object.fromEntries(renderAdapterArtifacts({"
            "packageRoot: process.cwd(), tool, agents: catalog.agents, "
            "groups: catalog.specialistGroups, specialists: [], assignedSkills: {}"
            "}).map(({ relativePath, content }) => [relativePath, content.toString()]))"
        )

        self.assertNotIn("disallowedTools: Agent", contents[".claude/agents/ast-ceo.md"])
        self.assertNotIn("disallowedTools: Agent", contents[".claude/agents/ast-cto.md"])
        self.assertIn("使用 Claude Code 的 Agent 工具", contents[".claude/agents/ast-ceo.md"])
        self.assertIn("使用 Claude Code 的 Agent 工具", contents[".claude/agents/ast-cto.md"])
        self.assertIn("disallowedTools: Agent", contents[".claude/agents/ast-pe.md"])
        self.assertIn("disallowedTools: Agent", contents[".claude/agents/ast-governor.md"])

    def test_c_suite_managers_remain_manager_agents_without_selected_specialists(self) -> None:
        contents = run_adapter(
            "Object.fromEntries(renderAdapterArtifacts({"
            "packageRoot: process.cwd(), tool, agents: catalog.agents, "
            "groups: {}, specialists: [], assignedSkills: {}, includeSkills: false"
            "}).map(({ relativePath, content }) => [relativePath, content.toString()]))"
        )

        self.assertNotIn("disallowedTools: Agent", contents[".claude/agents/ast-cto.md"])
        self.assertNotIn("disallowedTools: Agent", contents[".claude/agents/ast-cfo.md"])
        self.assertIn("disallowedTools: Agent", contents[".claude/agents/ast-pe.md"])

    def test_preloads_only_the_skills_assigned_to_each_canonical_agent(self) -> None:
        contents = run_adapter(
            "Object.fromEntries(renderAdapterArtifacts({"
            "packageRoot: process.cwd(), tool, agents: catalog.agents, "
            "groups: catalog.specialistGroups, specialists: [], "
            "assignedSkills: { all: ['alpha', 'beta'], byAgent: { ceo: ['alpha'], cto: ['beta'] } }"
            "}).map(({ relativePath, content }) => [relativePath, content.toString()]))"
        )

        self.assertIn("skills:\n  - alpha", contents[".claude/agents/ast-ceo.md"])
        self.assertNotIn("  - beta", contents[".claude/agents/ast-ceo.md"].split("---", 2)[1])
        self.assertIn("skills:\n  - beta", contents[".claude/agents/ast-cto.md"])
        self.assertNotIn("skills:", contents[".claude/agents/ast-pe.md"].split("---", 2)[1])

    def test_generates_a_claude_native_orchestrator_skill(self) -> None:
        artifacts = run_adapter(
            "renderAdapterArtifacts({"
            "packageRoot: process.cwd(), tool, agents: catalog.agents, "
            "groups: catalog.specialistGroups, specialists, assignedSkills: { all: [], byAgent: {} }"
            "}).map(({ relativePath, content }) => ({ relativePath, content: content.toString() }))"
        )

        orchestrator = next(
            artifact
            for artifact in artifacts
            if artifact["relativePath"]
            == ".claude/skills/agi-super-team-orchestrator/SKILL.md"
        )
        self.assertIn("name: agi-super-team-orchestrator", orchestrator["content"])
        self.assertIn("Agent 工具", orchestrator["content"])
        self.assertIn("ast-ceo", orchestrator["content"])
        self.assertIn("ast-governor", orchestrator["content"])
        self.assertIn("ast-cco-xiaohongshu-operator", orchestrator["content"])
        self.assertNotIn("spawn_agent", orchestrator["content"])
        self.assertNotIn("CODEX_HOME", orchestrator["content"])
        self.assertNotIn(".codex", orchestrator["content"].lower())

    def test_respects_independent_agent_and_skill_selection(self) -> None:
        skill_only = run_adapter(
            "renderAdapterArtifacts({"
            "packageRoot: process.cwd(), tool, agents: catalog.agents, "
            "groups: catalog.specialistGroups, specialists, assignedSkills: {}, "
            "includeAgents: false, includeSkills: true"
            "}).map(({ relativePath }) => relativePath)"
        )
        agents_only = run_adapter(
            "renderAdapterArtifacts({"
            "packageRoot: process.cwd(), tool, agents: catalog.agents, "
            "groups: catalog.specialistGroups, specialists, assignedSkills: {}, "
            "includeAgents: true, includeSkills: false"
            "}).map(({ relativePath }) => relativePath)"
        )

        self.assertEqual(
            skill_only,
            [".claude/skills/agi-super-team-orchestrator/SKILL.md"],
        )
        self.assertTrue(agents_only)
        self.assertTrue(all(path.startswith(".claude/agents/") for path in agents_only))

    def test_connection_spec_describes_filesystem_discovery_and_pending_evidence(self) -> None:
        spec = run_adapter(
            "buildConnectionSpec({"
            "home: '/tmp/claude-clean-home', tool, agents: catalog.agents, "
            "groups: catalog.specialistGroups, specialists, "
            "assignedSkills: { all: ['alpha'], byAgent: { ceo: ['alpha'] } }"
            "})"
        )

        self.assertEqual(spec["harness"], "claude-code")
        self.assertEqual(spec["connectionMode"], "filesystem-discovery")
        self.assertEqual(spec["runtimeEvidence"], "pending")
        self.assertEqual(spec["destinations"]["agentRoot"], "/tmp/claude-clean-home/.claude/agents")
        self.assertEqual(spec["destinations"]["skillRoot"], "/tmp/claude-clean-home/.claude/skills")
        self.assertEqual(spec["agentMap"]["ceo"], "ast-ceo")
        self.assertEqual(
            spec["managerAgentMap"]["cco"]["delegates"]["xiaohongshu-operator"],
            "ast-cco-xiaohongshu-operator",
        )
        self.assertEqual(spec["assignedSkills"]["byAgent"]["ceo"], ["alpha"])
        self.assertFalse(spec["capabilities"]["loadVerified"])
        self.assertFalse(spec["capabilities"]["delegationVerified"])


if __name__ == "__main__":
    unittest.main()
