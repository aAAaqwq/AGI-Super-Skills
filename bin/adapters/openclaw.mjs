import {
  existsSync,
  lstatSync,
  readFileSync,
  statSync,
} from "node:fs";
import { isAbsolute, join, posix, resolve } from "node:path";
import { isPhysicalStrictDescendant } from "../installer/path-safety.mjs";


export const ADAPTER_ID = "openclaw";

const ROLE_FILES = ["IDENTITY.md", "SOUL.md", "AGENTS.md", "USER.md", "TOOLS.md", "MEMORY.md"];
const ORCHESTRATOR_SKILL = "agi-super-team-orchestrator";
const SAFE_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;


function safeId(value, label) {
  if (typeof value !== "string" || !SAFE_ID.test(value)) {
    throw new Error(`unsafe ${label}: ${String(value)}`);
  }
  return value;
}

function safeRelative(value, label) {
  if (typeof value !== "string" || !value || isAbsolute(value) || value.split(/[\\/]/).includes("..")) {
    throw new Error(`unsafe ${label}: ${String(value)}`);
  }
  return value.replaceAll("\\", "/").replace(/\/$/, "");
}

function uniqueSorted(values, label) {
  if (!Array.isArray(values)) throw new Error(`${label} must be an array`);
  return [...new Set(values.map((value) => safeId(value, label)))].sort();
}

function validateTool(tool) {
  if (!tool || tool.id !== ADAPTER_ID) throw new Error("OpenClaw adapter requires the openclaw tool contract");
  if (!Array.isArray(tool.agentPaths) || tool.agentPaths.length !== 1) throw new Error("OpenClaw tool must define one agent path");
  if (!Array.isArray(tool.skillPaths) || tool.skillPaths.length !== 1) throw new Error("OpenClaw tool must define one skill path");
  const agentPath = safeRelative(tool.agentPaths[0], "OpenClaw agent path");
  return {
    workspaceRoot: posix.basename(agentPath) === "agi-super-team" ? agentPath : posix.join(agentPath, "agi-super-team"),
    skillRoot: safeRelative(tool.skillPaths[0], "OpenClaw skill path"),
  };
}

function normalizeAgents(agents, allowEmpty = false) {
  if (!Array.isArray(agents) || (!allowEmpty && !agents.length)) throw new Error("OpenClaw adapter requires canonical agents");
  const seen = new Set();
  const normalized = agents.map((agent) => {
    const id = safeId(agent?.id, "agent id");
    if (seen.has(id)) throw new Error(`duplicate agent id: ${id}`);
    seen.add(id);
    if (agent.path !== `agents/${id}`) throw new Error(`unsafe canonical agent path: ${agent.path}`);
    return agent;
  });
  for (const required of ["ceo", "governor"]) {
    if (normalized.length && !seen.has(required)) throw new Error(`OpenClaw adapter requires canonical ${required}`);
  }
  return normalized;
}

function normalizeSpecialists(specialists, canonicalIds) {
  if (!Array.isArray(specialists)) throw new Error("specialists must be an array");
  const seen = new Set();
  return specialists.map((specialist) => {
    const manager = safeId(specialist?.manager, "specialist manager");
    const id = safeId(specialist?.id, "specialist id");
    if (!canonicalIds.has(manager)) throw new Error(`specialist manager is not installed: ${manager}`);
    const runtimeId = `ast-${manager}-${id}`;
    if (seen.has(runtimeId)) throw new Error(`duplicate specialist id: ${runtimeId}`);
    seen.add(runtimeId);
    if (specialist.vendoredPath !== `agents/${manager}/subagents/${id}/AGENTS.md`) {
      throw new Error(`unsafe specialist source: ${specialist.vendoredPath}`);
    }
    return specialist;
  });
}

function normalizeSkillAssignments(assignedSkills, canonicalIds, allowUninstalledAgents = false) {
  if (!assignedSkills || typeof assignedSkills !== "object" || Array.isArray(assignedSkills)) {
    throw new Error("assignedSkills must contain all and byAgent");
  }
  const all = uniqueSorted(assignedSkills.all, "skill id");
  if (!assignedSkills.byAgent || typeof assignedSkills.byAgent !== "object" || Array.isArray(assignedSkills.byAgent)) {
    throw new Error("assignedSkills.byAgent must be an object");
  }
  const allowed = new Set(all);
  const byAgent = {};
  for (const [agentId, values] of Object.entries(assignedSkills.byAgent)) {
    safeId(agentId, "assigned skill agent id");
    if (!allowUninstalledAgents && !canonicalIds.has(agentId)) throw new Error(`skill assignment references uninstalled agent: ${agentId}`);
    const skills = uniqueSorted(values, `skills for ${agentId}`);
    for (const skill of skills) if (!allowed.has(skill)) throw new Error(`skill assignment is absent from all: ${skill}`);
    byAgent[agentId] = skills;
  }
  return { all, byAgent };
}

function physicalFile(path, label) {
  if (!existsSync(path) || lstatSync(path).isSymbolicLink() || !statSync(path).isFile()) {
    throw new Error(`invalid physical ${label}: ${path}`);
  }
}

function selectedByManager(specialists) {
  const output = new Map();
  for (const specialist of specialists) {
    if (!output.has(specialist.manager)) output.set(specialist.manager, []);
    output.get(specialist.manager).push(specialist);
  }
  return output;
}

function managerTargets(manager, group, specialists, canonicalIds) {
  const targets = [];
  for (const role of group?.roleRoutes || []) {
    if (canonicalIds.has(role.id)) targets.push(`ast-${role.id}`);
  }
  for (const specialist of specialists.get(manager) || []) targets.push(`ast-${manager}-${specialist.id}`);
  return [...new Set(targets)];
}

function managerRouting(manager, group, targets, specialists) {
  const routeDetails = [];
  for (const role of group?.roleRoutes || []) {
    if (targets.includes(`ast-${role.id}`)) routeDetails.push(`- \`ast-${role.id}\`（${role.name}）：${role.trigger}`);
  }
  for (const specialist of specialists || []) {
    routeDetails.push(`- \`ast-${manager}-${specialist.id}\`（${specialist.name}）：${specialist.trigger}`);
  }
  const routes = routeDetails.length ? routeDetails.join("\n") : "- 当前安装没有该管理节点可调用的直属角色；不要尝试未注册的 ID。";
  return `<!-- AGI-SUPER-TEAM:OPENCLAW-ROUTING:BEGIN -->
# OpenClaw 直属路由

你是 \`ast-${manager}\` 管理节点。先用 \`agents_list\` 核对目标存在，再用 \`sessions_spawn(agentId=\"<允许的 ID>\", task=\"<自包含任务包>\")\` 委派。最多两个并发叶子，总深度不得超过二。用 \`sessions_yield\` 让出调度时间，并用 \`subagents(action=\"list\")\` 检查仍在运行的子任务。只能调用下面列出的 ID，叶子不得继续委派：

${routes}

真实登录、发布、部署、付费、外部联系和不可逆操作仍需人类明确批准。不得把文件存在当成运行时验证。
<!-- AGI-SUPER-TEAM:OPENCLAW-ROUTING:END -->`;
}

function orchestratorSkill(agents, groups, specialists) {
  const canonicalIds = new Set(agents.map((agent) => agent.id));
  const selected = selectedByManager(specialists);
  const canonicalRoutes = agents
    .filter((agent) => agent.id !== "ceo")
    .map((agent) => `- \`ast-${agent.id}\`：${agent.focus}`)
    .join("\n");
  const managerRoutes = Object.entries(groups || {})
    .filter(([manager]) => canonicalIds.has(manager))
    .map(([manager, group]) => {
      const targets = managerTargets(manager, group, selected, canonicalIds);
      return `- \`ast-${manager}\` 只能继续调用：${targets.length ? targets.map((id) => `\`${id}\``).join("、") : "本次无已安装直属角色"}`;
    })
    .join("\n");
  return Buffer.from(`---
name: ${ORCHESTRATOR_SKILL}
description: 在 OpenClaw 中按 CEO→管理节点→叶子→Governor 路由 AGI Super Team。用户要求组队、跨职能执行、独立复核或明确调用 AGI Super Team 时使用。
---

# AGI Super Team｜OpenClaw 调度入口

开始前先读取同一 Skill 根目录中的 \`../orchestrate-agi-super-team/SKILL.md\`，并按需读取其 references。canonical Skill 决定是否组队、通用任务包、Governor 与人工批准契约；本 Skill 只补充 OpenClaw 会话调度方式。

仅由 \`ast-ceo\` 使用。先定义结果、验收、边界与不做什么，再选择最小充分团队。

## 原生工具流程

1. 用 \`agents_list\` 确认准备调用的 ID 已注册；缺失时停止，不得假装已委派。
2. 对相互独立的任务调用 \`sessions_spawn(agentId=\"ast-...\", task=\"自包含任务包\")\`。任务包写明所有权、输入、输出、限制、检查和回传格式。
3. 一轮最多并行两个叶子。需要给运行中子任务时间时调用 \`sessions_yield\`，用 \`subagents(action=\"list\")\` 检查状态。
4. 工作结果完成后，单独调用 \`ast-governor\` 复核证据、安全边界和未解决异议。复核任务必须携带原始工作子会话的 \`childSessionKey\`；Governor 应自行调用 \`sessions_history(sessionKey=\"...\")\` 核对原始请求、工具轨迹和结果，不能只接受 CEO 转述。若会话可见性阻止读取，必须把复核标为 pending/failed，不得宣称通过。Governor 不得继续委派。
5. CEO 综合决策、证据、异议、剩余风险、负责人和下一步。没有真实 canary receipt 时，运行证据保持 pending。

## CEO 可调用的 canonical Agent

${canonicalRoutes}

## 管理节点边界

${managerRoutes}

禁止生成 channel bindings，禁止自动对外发送，禁止在没有人类批准时执行发布、部署、凭证、资金、法律承诺或不可逆操作。
`);
}

function renderAgentArtifacts(packageRoot, roots, agents, groups, specialists) {
  const artifacts = [];
  const canonicalIds = new Set(agents.map((agent) => agent.id));
  const selected = selectedByManager(specialists);
  for (const agent of agents) {
    const sourceRoot = resolve(packageRoot, agent.path);
    const expectedRoot = resolve(packageRoot, "agents");
    if (!isPhysicalStrictDescendant(expectedRoot, sourceRoot)) throw new Error(`unsafe canonical agent path: ${agent.path}`);
    const group = groups?.[agent.id];
    const targets = group ? managerTargets(agent.id, group, selected, canonicalIds) : [];
    for (const filename of ROLE_FILES) {
      const source = join(sourceRoot, filename);
      if (!existsSync(source)) continue;
      if (!isPhysicalStrictDescendant(sourceRoot, source)) throw new Error(`unsafe role file: ${agent.path}/${filename}`);
      physicalFile(source, "role file");
      const original = readFileSync(source);
      const content = filename === "AGENTS.md" && group
        ? Buffer.concat([original, Buffer.from(`${original.length && original.at(-1) === 10 ? "\n" : "\n\n"}${managerRouting(agent.id, group, targets, selected.get(agent.id) || [])}\n`)])
        : original;
      artifacts.push({
        relativePath: posix.join(roots.workspaceRoot, `ast-${agent.id}`, filename),
        content,
        label: `openclaw-agent:${agent.id}`,
      });
    }
  }
  for (const specialist of specialists) {
    const source = resolve(packageRoot, specialist.vendoredPath);
    const expectedRoot = resolve(packageRoot, "agents", specialist.manager, "subagents", specialist.id);
    if (!isPhysicalStrictDescendant(expectedRoot, source)) throw new Error(`unsafe specialist source: ${specialist.vendoredPath}`);
    physicalFile(source, "specialist role file");
    artifacts.push({
      relativePath: posix.join(roots.workspaceRoot, `ast-${specialist.manager}-${specialist.id}`, "AGENTS.md"),
      content: readFileSync(source),
      label: `openclaw-specialist:${specialist.manager}/${specialist.id}`,
    });
  }
  return artifacts;
}

function renderSkillArtifacts(roots, agents, groups, specialists) {
  return [{
    relativePath: posix.join(roots.skillRoot, ORCHESTRATOR_SKILL, "SKILL.md"),
    content: orchestratorSkill(agents, groups, specialists),
    label: "openclaw-skill:orchestrator",
  }];
}

function normalizedInputs({ tool, agents, groups = {}, specialists = [], assignedSkills }, allowEmptyAgents = false) {
  const roots = validateTool(tool);
  const normalizedAgents = normalizeAgents(agents, allowEmptyAgents);
  const canonicalIds = new Set(normalizedAgents.map((agent) => agent.id));
  const normalizedSpecialists = normalizeSpecialists(specialists, canonicalIds);
  const normalizedSkills = normalizeSkillAssignments(assignedSkills, canonicalIds, allowEmptyAgents && canonicalIds.size === 0);
  return { roots, agents: normalizedAgents, groups, specialists: normalizedSpecialists, assignedSkills: normalizedSkills, canonicalIds };
}

export function renderAdapterArtifacts({
  packageRoot,
  tool,
  agents,
  groups = {},
  specialists = [],
  assignedSkills,
  includeAgents = true,
  includeSkills = true,
}) {
  if (typeof packageRoot !== "string" || !packageRoot) throw new Error("packageRoot is required");
  const input = normalizedInputs({ tool, agents, groups, specialists, assignedSkills }, !includeAgents);
  return [
    ...(includeAgents ? renderAgentArtifacts(packageRoot, input.roots, input.agents, input.groups, input.specialists) : []),
    ...(includeSkills ? renderSkillArtifacts(input.roots, input.agents, input.groups, input.specialists) : []),
  ];
}

function absoluteHome(home) {
  if (typeof home !== "string" || !home || !isAbsolute(home) || resolve(home) === resolve("/")) {
    throw new Error(`unsafe OpenClaw home: ${String(home)}`);
  }
  return resolve(home);
}

export function buildConnectionSpec({
  home,
  tool,
  agents,
  groups = {},
  specialists = [],
  assignedSkills,
}) {
  const targetHome = absoluteHome(home);
  const input = normalizedInputs({ tool, agents, groups, specialists, assignedSkills }, true);
  const selected = selectedByManager(input.specialists);
  const entries = [];
  for (const agent of input.agents) {
    const id = `ast-${agent.id}`;
    let allowAgents = [];
    if (agent.id === "ceo") allowAgents = input.agents.filter((item) => item.id !== "ceo").map((item) => `ast-${item.id}`);
    else if (input.groups?.[agent.id]) allowAgents = managerTargets(agent.id, input.groups[agent.id], selected, input.canonicalIds);
    const isLeaf = agent.id !== "ceo" && !input.groups?.[agent.id];
    entries.push({
      id,
      name: agent.name,
      workspace: resolve(targetHome, input.roots.workspaceRoot, id),
      skills: [...new Set([...(agent.id === "ceo" ? [ORCHESTRATOR_SKILL] : []), ...(input.assignedSkills.byAgent[agent.id] || [])])].sort(),
      subagents: { allowAgents, requireAgentId: true },
      ...(isLeaf ? { tools: { deny: ["sessions_spawn"] } } : {}),
    });
  }
  for (const specialist of input.specialists) {
    const id = `ast-${specialist.manager}-${specialist.id}`;
    entries.push({
      id,
      name: specialist.name,
      workspace: resolve(targetHome, input.roots.workspaceRoot, id),
      skills: [],
      subagents: { allowAgents: [], requireAgentId: true },
      tools: { deny: ["sessions_spawn"] },
    });
  }
  return {
    schemaVersion: 1,
    harness: ADAPTER_ID,
    runtimeEvidence: "pending",
    targetVersion: "2026.6.8",
    targetHome,
    mergeContract: {
      configPath: resolve(targetHome, ".openclaw", "openclaw.json"),
      path: "agents.list",
      key: "id",
      strategy: "upsert-managed-preserve-unmanaged",
      managedPrefix: "ast-",
      preserveUnmanaged: true,
      removeUnmentionedManaged: false,
      conflictPolicy: "fail-unless-previewed",
      mapStrategy: "deep-merge",
    },
    requirements: {
      requiredMaxDepth: 2,
      maxChildrenPerAgent: 2,
    },
    configPatch: {
      agents: {
        defaults: {
          subagents: {
            maxSpawnDepth: 2,
            maxChildrenPerAgent: 2,
          },
        },
        list: entries,
      },
    },
    canary: {
      status: "pending",
      requiredChecks: [
        "isolated-state-directory",
        "config-validate",
        "managed-agents-discovered",
        "ceo-manager-leaf-dispatch-observed",
        "governor-raw-child-session-history-observed",
        "governor-independent-review-observed",
        "bindings-unchanged",
      ],
      receiptMustBindRepositoryRevision: true,
    },
  };
}
