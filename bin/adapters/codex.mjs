import { dirname, join } from "node:path";
import {
  BEGIN_MARKER,
  END_MARKER,
  codexAgent,
  codexSpecialist,
  globalCeoPayload,
} from "../installer/render.mjs";


export const ADAPTER_ID = "codex";

function jsonSkill(assignedSkills, id) {
  return assignedSkills?.byAgent?.[id] || [];
}

function orchestratorSkill() {
  return `---
name: agi-super-team-orchestrator
description: 在 Codex 中按 CEO→C-suite→Leaf→Governor 路由复杂任务；需要跨职能并行、独立复核或完整团队交付时使用。
---

# AGI Super Team｜Codex Adapter

这是 Codex 的运行时包装 Skill。开始前必须读取同一 Skill 根目录中的 \`../orchestrate-agi-super-team/SKILL.md\`，并按需读取其 references；canonical Skill 决定是否组队、通用任务包、Governor 和人工批准契约，本文件只补充 Codex 调度方式。

你是主会话中的 CEO 协调者。先定义结果、约束和验收，再按任务选择最小充分团队。

- 使用 \`spawn_agent\` 调用已安装的 \`ast-*\` Agent。
- CEO 只能调用 C-suite、PE 和 Governor。
- Manager 只能调用自己在配置中列出的直属叶子，最多两个并发。
- Leaf 和 Governor 不得继续创建 Agent，总深度不得超过二。
- Governor 必须独立审查重大结论；主 Agent 保留其有证据支持的异议。
- 登录、发布、部署、资金、凭证、法律承诺和其他不可逆动作必须由用户最终批准。
- 最终回传决策、证据、验证、限制、剩余风险和下一步。
`;
}

export function renderAdapterArtifacts({
  packageRoot,
  tool,
  agents,
  groups,
  specialists,
  includeAgents = true,
  includeSkills = true,
}) {
  const artifacts = [];
  if (includeAgents) {
    const ceo = agents.find((agent) => agent.id === "ceo");
    if (ceo) {
      const payload = globalCeoPayload(packageRoot);
      artifacts.push({
        relativePath: join(dirname(tool.agentPaths[0]), "AGENTS.md"),
        content: payload,
        label: "adapter:codex/global-ceo",
        managed: {begin: BEGIN_MARKER, end: END_MARKER},
      });
    }
    for (const agent of agents.filter((item) => item.id !== "ceo")) {
      artifacts.push({
        relativePath: join(tool.agentPaths[0], `ast-${agent.id}.toml`),
        content: codexAgent(packageRoot, agent, groups[agent.id] || null),
        label: `adapter:codex/agent:${agent.id}`,
      });
    }
    for (const specialist of specialists) {
      artifacts.push({
        relativePath: join(
          tool.agentPaths[0],
          `ast-${specialist.manager}-${specialist.id}.toml`,
        ),
        content: codexSpecialist(packageRoot, specialist),
        label: `adapter:codex/specialist:${specialist.manager}/${specialist.id}`,
      });
    }
  }
  if (includeSkills) {
    for (const skillPath of tool.skillPaths) {
      artifacts.push({
        relativePath: join(
          skillPath,
          "agi-super-team-orchestrator",
          "SKILL.md",
        ),
        content: orchestratorSkill(),
        label: `adapter:codex/skill:orchestrator:${skillPath}`,
      });
    }
  }
  return artifacts;
}

export function buildConnectionSpec({
  agents,
  groups,
  specialists,
  assignedSkills,
}) {
  const selectedIds = new Set(agents.map((agent) => agent.id));
  const agentMap = Object.fromEntries(
    agents.map((agent) => [agent.id, `ast-${agent.id}`]),
  );
  const managerAgentMap = {};
  for (const [manager, group] of Object.entries(groups || {})) {
    managerAgentMap[manager] = {
      agent: `ast-${manager}`,
      requiredMaxDepth: 2,
      maxConcurrentChildren: 2,
      delegates: Object.fromEntries(
        group.specialists.map((item) => [
          item.id,
          `ast-${manager}-${item.id}`,
        ]),
      ),
      roleRefs: Object.fromEntries(
        (group.roleRoutes || [])
          .filter((item) => selectedIds.has(item.id))
          .map((item) => [item.id, `ast-${item.id}`]),
      ),
    };
  }
  return {
    schemaVersion: 1,
    harness: ADAPTER_ID,
    runtimeEvidence: "pending",
    coordinator: "ceo",
    coordinatorRuntime: "current-session-global-agents-md",
    independentReviewer: "ast-governor",
    requiredMaxDepth: 2,
    maxConcurrentChildren: 2,
    agentMap,
    managerAgentMap,
    specialistAgents: specialists.map(
      (item) => `ast-${item.manager}-${item.id}`,
    ),
    assignedSkills: Object.fromEntries(
      agents.map((agent) => [agent.id, jsonSkill(assignedSkills, agent.id)]),
    ),
    activation: {
      mode: "codex-custom-agents",
      entrySkill: "agi-super-team-orchestrator",
      pluginOptional: true,
    },
    revisionMatchedReceipt: {
      status: "pending",
      required: true,
      requiredFields: [
        "sourceRevision",
        "sourceDirty",
        "connectionSha256",
        "revisionMatched",
      ],
      mustUseCleanSourceRevision: true,
      requiredChecks: [
        "fresh-codex-home",
        "agents-discovered",
        "orchestrator-semantic-trigger",
        "ceo-manager-leaf-dispatch-observed",
        "governor-independent-review-observed",
      ],
    },
  };
}
