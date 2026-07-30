import { join } from "node:path";

import { roleBody, specialistBody } from "../installer/render.mjs";


export const ADAPTER_ID = "claude-code";
const MANAGER_IDS = new Set([
  "cto", "cpo", "cco", "cfo", "cdo", "cqo", "cmo", "cro", "cso", "coo", "clo",
]);

function yamlString(value) {
  return JSON.stringify(String(value));
}

function runtimeAgentName(agentId) {
  return `ast-${agentId}`;
}

function canonicalDescription(agent) {
  if (agent.id === "ceo") {
    return `跨职能、公司级或高不确定性任务的总协调者。需要拆解目标、选择 C-suite 角色、保留独立复核并综合决策时调用。${agent.focus}`;
  }
  if (agent.id === "governor") {
    return `重大结论、发布、安全、资金、法律或完成声明需要独立证据复核时调用。${agent.focus}`;
  }
  return `任务主要属于 ${agent.name} 的职责范围时调用。${agent.focus}`;
}

function assignedSkillLines(assignedSkills, agentId) {
  const names = assignedSkills?.byAgent?.[agentId] || [];
  for (const name of names) {
    if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(name)) {
      throw new Error(`invalid Claude Code Skill name assigned to ${agentId}: ${name}`);
    }
  }
  const unique = [...new Set(names)].sort();
  return unique.length ? ["skills:", ...unique.map((name) => `  - ${name}`)] : [];
}

function canonicalAgentArtifact(packageRoot, tool, agent, groups, assignedSkills) {
  const name = runtimeAgentName(agent.id);
  const canDelegate = agent.id === "ceo" || MANAGER_IDS.has(agent.id);
  const frontmatter = [
    "---",
    `name: ${name}`,
    `description: ${yamlString(canonicalDescription(agent))}`,
    "model: inherit",
    ...assignedSkillLines(assignedSkills, agent.id),
    ...(canDelegate ? [] : ["disallowedTools: Agent"]),
    "---",
  ].join("\n");
  const execution = canDelegate
    ? "你是受限的协调或管理 Agent。需要独立专长时使用 Claude Code 的 Agent 工具，只调用路由表允许的直属角色；每个子任务必须写清目标、输入、输出、边界和验收。"
    : "你是叶子 Agent，不得创建或调用其他 Agent；只完成当前边界内的任务并回传证据、限制和下一步。";
  const body = roleBody(
    packageRoot,
    agent,
    groups?.[agent.id] || null,
    (manager, id) => `ast-${manager}-${id}`,
    (id) => `ast-${id}`,
  );
  return {
    relativePath: join(tool.agentPaths[0], `${name}.md`),
    content: Buffer.from(`${frontmatter}\n\n${body}\n\n## Claude Code 执行约束\n\n${execution}\n`),
    label: `Claude Code Agent ${name}`,
  };
}

function specialistAgentArtifact(packageRoot, tool, specialist) {
  const name = `ast-${specialist.manager}-${specialist.id}`;
  const description = `${specialist.manager.toUpperCase()} 直属叶子专家｜${specialist.name}。${specialist.trigger} 不适用：${specialist.doNotUseWhen}`;
  const frontmatter = [
    "---",
    `name: ${name}`,
    `description: ${yamlString(description)}`,
    "model: inherit",
    "disallowedTools: Agent",
    "---",
  ].join("\n");
  return {
    relativePath: join(tool.agentPaths[0], `${name}.md`),
    content: Buffer.from(
      `${frontmatter}\n\n${specialistBody(packageRoot, specialist)}\n\n` +
      "## Claude Code 执行约束\n\n你是叶子 Agent，不得创建或调用其他 Agent。只接受一个边界清楚的任务，回传产物、检查、限制和下一步；不得声称未执行的验证。\n",
    ),
    label: `Claude Code specialist ${name}`,
  };
}

function orchestratorArtifact(tool, agents, groups, specialists) {
  const agentById = new Map(agents.map((agent) => [agent.id, agent]));
  const canonicalRoutes = agents
    .filter((agent) => agent.id !== "ceo")
    .map((agent) => `- \`${runtimeAgentName(agent.id)}\`（${agent.name}）：${agent.focus}`)
    .join("\n");
  const selectedKeys = new Set(specialists.map((item) => `${item.manager}/${item.id}`));
  const managerSections = Object.values(groups || {}).map((group) => {
    const roleRoutes = (group.roleRoutes || [])
      .filter((route) => agentById.has(route.id))
      .map((route) => `- \`ast-${route.id}\`（${route.name}）：${route.trigger}`);
    const specialistRoutes = (group.specialists || [])
      .filter((item) => selectedKeys.has(`${group.manager}/${item.id}`))
      .map((item) => `- \`ast-${group.manager}-${item.id}\`（${item.name}）：${item.trigger}\n  - 不调用：${item.doNotUseWhen}`);
    const routes = [...roleRoutes, ...specialistRoutes];
    return routes.length ? `### ${group.manager.toUpperCase()} 可委派叶子\n\n${routes.join("\n")}` : "";
  })
    .filter(Boolean)
    .join("\n\n");
  const content = `---
name: agi-super-team-orchestrator
description: 跨职能、公司级、高不确定性或用户明确要求 AGI Super Team、C-suite、团队协作、并行专家、独立复核时使用。先按职责选择最小团队，再用 Claude Code Agent 工具精准委派并综合证据。
---

# AGI Super Team｜Claude Code 编排器

开始前先读取同一 Skill 根目录中的 \`../orchestrate-agi-super-team/SKILL.md\`，并按需读取其 references。canonical Skill 决定是否组队、通用任务包、Governor 与人工批准契约；本 Skill 只定义 Claude Code 的运行时编排方式。

canonical 角色正文和专业 Skills 由安装器逐字复制；本文件不改写它们。

## 启动条件

- 单领域、一步可完成的任务不组队，直接完成或调用一个最匹配的 Agent。
- 跨职能、存在独立工作流、需要专业复核，或用户明确要求团队时启动。
- 默认选择 2–3 个互补角色；只有能缩短关键路径时才并行。

## Claude Code 调度协议

1. 固定结果、成功标准、约束、非目标和必须由人类批准的现实动作。
2. 使用 Claude Code 的 \`Agent\` 工具调用 \`ast-ceo\` 作为唯一协调者，并在任务中写明允许调用的直属 C-suite、输入、输出、边界和验收。
3. CEO 只把边界清楚的工作交给匹配的 C-suite Manager；Manager 最多并行调用两个已安装的直属叶子。
4. 叶子和 \`ast-governor\` 已被禁止使用 Agent 工具，不能继续委派。
5. 重大结论、发布、资金、法律、安全或完成声明必须另行调用 \`ast-governor\`，向其提供原始声明和工作证据，不要求它迎合 CEO。
6. 最终由主会话综合决定、证据、异议、限制、负责人和下一步。不得把委派成功当成任务完成。
7. 如果当前 Claude Code 版本或权限不允许嵌套 Agent，主会话按同一路由平铺调用 Manager/叶子，并明确记录降级；不得伪称发生了嵌套委派。

## Canonical Agent 路由

${canonicalRoutes}

${managerSections}

## 安全边界

- 只调用本次安装产物中存在的 \`ast-*\` Agent；未安装的叶子不得作为可用能力声明。
- 登录、凭证、付款、交易、发布、部署、生产写入、法律承诺、对外联系及不可逆动作必须取得人类明确批准。
- 动态事实和高风险结论需要当前一手来源；没有运行证据统一标记为“待验证”。
- Governor 保持独立；CEO 可以调整范围或接受剩余风险，但不得改写其证据结论。
`;
  return {
    relativePath: join(tool.skillPaths[0], "agi-super-team-orchestrator", "SKILL.md"),
    content: Buffer.from(content),
    label: "Claude Code Skill agi-super-team-orchestrator",
  };
}

export function renderAdapterArtifacts({
  packageRoot,
  tool,
  agents,
  groups,
  specialists = [],
  assignedSkills = {},
  includeAgents = true,
  includeSkills = true,
}) {
  const artifacts = [];
  if (includeAgents) {
    artifacts.push(
      ...agents.map((agent) => canonicalAgentArtifact(packageRoot, tool, agent, groups, assignedSkills)),
      ...specialists.map((specialist) => specialistAgentArtifact(packageRoot, tool, specialist)),
    );
  }
  if (includeSkills) artifacts.push(orchestratorArtifact(tool, agents, groups, specialists));
  return artifacts;
}

export function buildConnectionSpec({
  home,
  tool,
  agents,
  groups,
  specialists = [],
  assignedSkills = {},
}) {
  const selectedKeys = new Set(specialists.map((item) => `${item.manager}/${item.id}`));
  const agentIds = new Set(agents.map((agent) => agent.id));
  const managerAgentMap = Object.fromEntries(agents
    .filter((agent) => MANAGER_IDS.has(agent.id))
    .map((agent) => {
      const manager = agent.id;
      const group = groups?.[manager] || { specialists: [], roleRoutes: [] };
      const roleRoutes = group.roleRoutes?.length
        ? group.roleRoutes
        : manager === "cto" ? [{ id: "pe" }] : [];
      return [manager, {
        agent: `ast-${manager}`,
        maxConcurrentChildren: 2,
        delegates: Object.fromEntries((group.specialists || [])
          .filter((item) => selectedKeys.has(`${manager}/${item.id}`))
          .map((item) => [item.id, `ast-${manager}-${item.id}`])),
        roleRefs: Object.fromEntries(roleRoutes
          .filter((item) => agentIds.has(item.id))
          .map((item) => [item.id, `ast-${item.id}`])),
      }];
    }));
  const normalizedAssignedSkills = {
    all: [...new Set(assignedSkills?.all || [])].sort(),
    byAgent: Object.fromEntries(Object.entries(assignedSkills?.byAgent || {})
      .map(([agentId, names]) => [agentId, [...new Set(names)].sort()])),
  };
  const agentRoot = join(home, tool.agentPaths[0]);
  const skillRoot = join(home, tool.skillPaths[0]);
  return {
    schemaVersion: 1,
    harness: ADAPTER_ID,
    connectionMode: "filesystem-discovery",
    runtimeEvidence: "pending",
    home,
    destinations: { agentRoot, skillRoot },
    coordinator: "ast-ceo",
    independentReviewer: "ast-governor",
    requiredMaxDepth: 2,
    maxConcurrentChildren: 2,
    agentMap: Object.fromEntries(agents.map((agent) => [agent.id, runtimeAgentName(agent.id)])),
    managerAgentMap,
    assignedSkills: normalizedAssignedSkills,
    expectedArtifacts: {
      canonicalAgents: agents.length,
      specialistAgents: specialists.length,
      orchestratorSkills: 1,
    },
    capabilities: {
      artifactRenderer: true,
      filesystemDiscovery: true,
      loadVerified: false,
      triggerVerified: false,
      delegationVerified: false,
      canaryVerified: false,
    },
    cleanClientReceipt: {
      configEnvironmentVariable: "CLAUDE_CONFIG_DIR",
      configDirectory: join(home, ".claude"),
      requiredChecks: [
        "fresh-config-directory",
        "agents-discovered",
        "orchestrator-semantic-trigger",
        "ceo-manager-leaf-dispatch-observed",
        "governor-independent-review-observed",
      ],
    },
  };
}
