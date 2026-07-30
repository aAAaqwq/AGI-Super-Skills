import { join, resolve } from "node:path";
import { roleBody, specialistBody } from "../installer/render.mjs";

export const ADAPTER_ID = "hermes";

const ROLE_SKILL_ROOT = ".hermes/skills/agi-super-team-agents";
const ORCHESTRATOR_SKILL = ".hermes/skills/agi-super-team-orchestrator/SKILL.md";
const BLUEPRINT_ROOT = ".hermes/agi-super-team/profiles";
const MANAGER_IDS = new Set(["cto", "cpo", "cqo", "cmo", "cfo", "cdo", "cco", "clo", "cro", "cso", "coo"]);
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

function yamlText(value) {
  return JSON.stringify(String(value));
}

function stableJson(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

function sortedUnique(values, label) {
  if (!Array.isArray(values) || values.some((value) => typeof value !== "string" || !SLUG.test(value))) {
    throw new Error(`${label} must be an array of skill slugs`);
  }
  const normalized = [...new Set(values)].sort();
  if (JSON.stringify(values) !== JSON.stringify(normalized)) {
    throw new Error(`${label} must be deduplicated and sorted`);
  }
  return normalized;
}

function validateInputs({ tool, agents, groups = {}, specialists = [], assignedSkills }, { allowEmptyAgents = false } = {}) {
  if (!tool || tool.id !== ADAPTER_ID) throw new Error("Hermes adapter requires tool.id=hermes");
  if (!Array.isArray(agents) || (!agents.length && !allowEmptyAgents)) throw new Error("Hermes adapter requires canonical agents");
  const agentIds = agents.map((agent) => agent?.id);
  if (agentIds.some((id) => typeof id !== "string" || !SLUG.test(id)) || new Set(agentIds).size !== agentIds.length) {
    throw new Error("Hermes adapter received invalid or duplicate canonical agents");
  }
  if (!assignedSkills || typeof assignedSkills !== "object" || Array.isArray(assignedSkills)) {
    throw new Error("assignedSkills must contain all and byAgent");
  }
  const allSkills = sortedUnique(assignedSkills.all, "assignedSkills.all");
  if (!assignedSkills.byAgent || typeof assignedSkills.byAgent !== "object" || Array.isArray(assignedSkills.byAgent)) {
    throw new Error("assignedSkills.byAgent must map every canonical Agent");
  }
  const byAgent = {};
  for (const id of agentIds) {
    if (!Object.hasOwn(assignedSkills.byAgent, id)) {
      throw new Error(`assignedSkills.byAgent is missing canonical Agent: ${id}`);
    }
    const skills = sortedUnique(assignedSkills.byAgent[id], `assignedSkills.byAgent.${id}`);
    const unknown = skills.filter((skill) => !allSkills.includes(skill));
    if (unknown.length) throw new Error(`assignedSkills.byAgent.${id} contains skills outside assignedSkills.all: ${unknown.join(", ")}`);
    byAgent[id] = skills;
  }
  if (!groups || typeof groups !== "object" || Array.isArray(groups)) throw new Error("groups must be an object");
  if (!Array.isArray(specialists)) throw new Error("specialists must be an array");
  const specialistKeys = specialists.map((item) => `${item?.manager}/${item?.id}`);
  if (specialistKeys.some((key) => !/^[a-z0-9-]+\/[a-z0-9-]+$/.test(key)) || new Set(specialistKeys).size !== specialistKeys.length) {
    throw new Error("Hermes adapter received invalid or duplicate specialists");
  }
  return { agentIds, allSkills, byAgent };
}

function roleType(id) {
  if (id === "ceo") return "coordinator";
  if (id === "governor") return "independent-reviewer";
  if (MANAGER_IDS.has(id)) return "manager";
  return "leaf";
}

function runtimeRoleName(agent) {
  return `ast-${agent.id}`;
}

function roleSkillContent(packageRoot, agent, group, assigned) {
  const runtimeName = runtimeRoleName(agent);
  const kind = roleType(agent.id);
  const execution = kind === "coordinator"
    ? "持久命名 C-suite 的分派只通过 Hermes Profiles + Kanban；先确认 Profile 真实存在，不得用 delegate_task 模拟命名 Profile。"
    : kind === "manager"
      ? "使用对应专家 Skill 完成专门工作；delegate_task 只可用于当前 Profile 内的匿名短任务，最多两个并发，总深度上限为二。"
      : kind === "independent-reviewer"
        ? "你必须在独立 ast-governor Profile 中复核证据，不执行工作 Agent 的实现，也不得调用 delegate_task。"
        : "你是叶子角色，不得调用 delegate_task，也不得继续创建 Agent。";
  const assignedIndex = assigned.length
    ? assigned.map((skill) => `- \`${skill}\``).join("\n")
    : "- 无 canonical Skill 分配；只使用本角色指令与运行时明确提供的工具。";
  const body = roleBody(
    packageRoot,
    agent,
    group,
    (manager, id) => `ast-${manager}-${id}`,
    (id) => `ast-${id}`,
  );
  return `---
name: ${runtimeName}
description: ${yamlText(`${agent.id.toUpperCase()} 角色｜${agent.focus}`)}
metadata:
  hermes:
    category: agi-super-team-agents
    tags: [agi-super-team, role, ${kind}]
---

# ${agent.name}

> 此文件由 Hermes Adapter 从 canonical \`${agent.path}\` 生成；canonical 内容仍由源目录拥有。runtimeEvidence: pending。

## Hermes 执行信封

${execution}

命名角色的 Profile 必须由人类审阅蓝图后通过 Hermes CLI 创建或更新。本 Adapter 不创建 Profile、不启动 Gateway、不创建 Cron，也不声称运行时已加载。

## 分配的 canonical Skills

${assignedIndex}

${body.trim()}
`;
}

function specialistSkillContent(packageRoot, specialist) {
  const runtimeName = `ast-${specialist.manager}-${specialist.id}`;
  return `---
name: ${runtimeName}
description: ${yamlText(`${specialist.manager.toUpperCase()} 子专家｜${specialist.name}：${specialist.trigger}`)}
metadata:
  hermes:
    category: agi-super-team-agents
    tags: [agi-super-team, specialist, ${specialist.manager}]
---

> 此角色作为 Hermes progressive Skill 安装，不是持久命名 Profile。runtimeEvidence: pending。

${specialistBody(packageRoot, specialist).trim()}
`;
}

function orchestratorSkillContent(agents, specialists) {
  const profiles = agents.map((agent) => `- \`ast-${agent.id}\`：${agent.focus}`).join("\n");
  const specialistIndex = specialists.length
    ? specialists.map((item) => `- \`ast-${item.manager}-${item.id}\`：${item.trigger}`).join("\n")
    : "- 本次未选择 specialist Skill。";
  return `---
name: agi-super-team-orchestrator
description: 使用 Hermes Profiles 与 Kanban 路由 AGI Super Team
metadata:
  hermes:
    category: orchestration
    tags: [agi-super-team, profiles, kanban]
    requires_toolsets: [kanban]
---

# AGI Super Team｜Hermes Orchestrator

runtimeEvidence: pending

## 触发条件

当任务需要一个以上持久命名 C-suite 角色、独立 Governor 复核，或需要跨 Profile 保留可观察的依赖与交接时使用。

## 核心约束

1. 持久命名角色必须通过 **Profiles + Kanban** 路由。先从真实 Profile roster 确认 assignee 存在；蓝图文件不等于已创建 Profile。
2. 不要调用或发明 \`delegate_task(profile=...)\`。Hermes 的 \`delegate_task\` 不承担命名 Profile 路由。
3. \`delegate_task\` 只用于 Manager Profile 内需要推理的匿名短任务；默认使用 leaf，不得把匿名结果宣称为某个 ast-* Profile 的持久产出。
4. 标准 Team 深度上限为二、每个 Manager 最多两个并发匿名子任务。叶子和 Governor 不得继续委派。
5. Manager 工作完成后再让独立 \`ast-governor\` Profile 复核；CEO 综合任务同时依赖 Manager 产出和 Governor 复核。
6. 未经人类批准，不创建 Profile、Cron 或 Gateway，不启动 Kanban dispatcher，不执行发布、部署、资金、账号或不可逆操作。

创建工作卡时，通过 \`kanban_create\` 的 \`skills\` 数组固定装载与 assignee 同名的角色 Skill（例如 assignee 为 \`ast-cto\` 时至少传入 \`ast-cto\`）。再按 connection spec 追加该角色分配的 canonical Skills。Governor 卡必须固定装载 \`ast-governor\`，CEO 综合卡必须固定装载 \`ast-ceo\`；仅写 assignee 而不装载角色 Skill，不算完成角色接线。

## Kanban 依赖模板

- \`manager-output\`：分配给一个已确认存在的 Manager Profile。
- \`governor-review\`：分配给 \`ast-governor\`，父依赖为 \`manager-output\`。
- \`ceo-synthesis\`：分配给 \`ast-ceo\`，依赖 \`manager-output\` 与 \`governor-review\`。

如果 Hermes CLI、Profile、Gateway 或 Kanban dispatcher 不可用，停止自动调度，返回缺失项并采用人工/顺序回退；不得伪造 canary 或 receipt。

## Persistent Profile 索引

${profiles}

## Selected Specialist Skills

${specialistIndex}
`;
}

function profileBlueprint(agent, assigned) {
  const profileId = runtimeRoleName(agent);
  const kind = roleType(agent.id);
  const isManager = kind === "manager";
  return {
    schemaVersion: 1,
    harness: ADAPTER_ID,
    profileId,
    roleId: agent.id,
    roleType: kind,
    description: agent.focus,
    blueprintOnly: true,
    runtimeStateCreated: false,
    runtimeEvidence: "pending",
    canonicalSource: agent.path,
    roleSkill: `~/.hermes/skills/agi-super-team-agents/${profileId}/SKILL.md`,
    assignedSkills: assigned,
    kanbanTaskSkills: [profileId, ...assigned],
    profileSkillVisibility: {
      reason: "Hermes Profiles use separate HERMES_HOME directories and do not inherit the default profile's Skills implicitly.",
      requiredExternalDirectory: "~/.hermes/skills",
      desiredConfig: { skills: { external_dirs: ["~/.hermes/skills"] } },
    },
    desiredCapabilities: {
      kanbanRole: kind === "coordinator" ? "orchestrator" : kind === "independent-reviewer" ? "reviewer" : "worker",
      delegateTask: isManager ? "anonymous-short-task-only" : "disabled",
      requiredMaxDepth: 2,
      maxConcurrentChildren: isManager ? 2 : 0,
    },
    activation: {
      humanReviewRequired: true,
      profileCreateOrUpdateRequired: true,
      gatewayStartRequiredForKanbanDispatch: true,
      performedByAdapter: false,
    },
  };
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
  const normalized = validateInputs(
    { tool, agents, groups, specialists, assignedSkills },
    { allowEmptyAgents: includeAgents === false },
  );
  const artifacts = [];
  if (includeAgents) {
    for (const agent of agents) {
      const runtimeName = runtimeRoleName(agent);
      artifacts.push({
        relativePath: join(ROLE_SKILL_ROOT, runtimeName, "SKILL.md"),
        content: Buffer.from(roleSkillContent(packageRoot, agent, groups[agent.id] || null, normalized.byAgent[agent.id])),
        label: `hermes-role:${agent.id}`,
      });
      artifacts.push({
        relativePath: join(BLUEPRINT_ROOT, runtimeName, "profile.json"),
        content: Buffer.from(stableJson(profileBlueprint(agent, normalized.byAgent[agent.id]))),
        label: `hermes-profile-blueprint:${agent.id}`,
      });
    }
    for (const specialist of specialists) {
      const runtimeName = `ast-${specialist.manager}-${specialist.id}`;
      artifacts.push({
        relativePath: join(ROLE_SKILL_ROOT, runtimeName, "SKILL.md"),
        content: Buffer.from(specialistSkillContent(packageRoot, specialist)),
        label: `hermes-specialist:${specialist.manager}/${specialist.id}`,
      });
    }
  }
  if (includeSkills) {
    artifacts.push({
      relativePath: ORCHESTRATOR_SKILL,
      content: Buffer.from(orchestratorSkillContent(agents, specialists)),
      label: "hermes-orchestrator",
    });
  }
  return artifacts;
}

export function buildConnectionSpec({ home, tool, agents, groups = {}, specialists = [], assignedSkills }) {
  const normalized = validateInputs(
    { tool, agents, groups, specialists, assignedSkills },
    { allowEmptyAgents: true },
  );
  if (typeof home !== "string" || !home.trim()) throw new Error("Hermes connection spec requires home");
  const targetHome = resolve(home);
  if (targetHome === resolve("/")) throw new Error("refusing unsafe Hermes connection home");
  const profileMap = Object.fromEntries(agents.map((agent) => [agent.id, {
    profileId: runtimeRoleName(agent),
    roleType: roleType(agent.id),
    roleSkill: join(targetHome, ROLE_SKILL_ROOT, runtimeRoleName(agent), "SKILL.md"),
    blueprint: join(targetHome, BLUEPRINT_ROOT, runtimeRoleName(agent), "profile.json"),
    assignedSkills: normalized.byAgent[agent.id],
    kanbanTaskSkills: [runtimeRoleName(agent), ...normalized.byAgent[agent.id]],
  }]));
  const managerProfiles = agents.filter((agent) => roleType(agent.id) === "manager").map(runtimeRoleName).sort();
  const selectedRoleSkills = specialists.map((item) => `ast-${item.manager}-${item.id}`).sort();
  const allowedByManager = Object.fromEntries(
    Object.keys(groups).sort().map((manager) => [
      manager,
      specialists.filter((item) => item.manager === manager).map((item) => `ast-${item.manager}-${item.id}`).sort(),
    ]),
  );
  return {
    schemaVersion: 1,
    harness: ADAPTER_ID,
    connectionMode: "profiles-kanban-blueprint",
    runtimeEvidence: "pending",
    writesRuntimeState: false,
    home: targetHome,
    requiredMaxDepth: 2,
    maxConcurrentChildren: 2,
    paths: {
      roleSkillRoot: join(targetHome, ROLE_SKILL_ROOT),
      orchestratorSkill: join(targetHome, ORCHESTRATOR_SKILL),
      profileBlueprintRoot: join(targetHome, BLUEPRINT_ROOT),
    },
    profileMap,
    permissions: {
      ceo: {
        persistentDispatch: "profiles-kanban-only",
        allowedProfiles: [...managerProfiles, ...(profileMap.pe ? ["ast-pe"] : []), ...(profileMap.governor ? ["ast-governor"] : [])].sort(),
        delegateTask: { allowed: false, profileArgumentAllowed: false },
      },
      manager: {
        allowedRoleSkills: selectedRoleSkills,
        allowedByManager,
        maxConcurrentChildren: 2,
        delegateTask: {
          allowed: true,
          mode: "anonymous-short-task-only",
          profileArgumentAllowed: false,
          defaultRole: "leaf",
          maxSpawnDepth: 2,
        },
      },
      leaf: { delegateTask: { allowed: false }, canCreateKanbanTasks: false },
      governor: { delegateTask: { allowed: false }, independent: true, canCreateKanbanTasks: false },
    },
    kanbanPolicy: {
      namedRoleDispatch: "profiles-only",
      managerOutput: "manager-output",
      governorReviewDependsOn: ["manager-output"],
      ceoSynthesisDependsOn: ["manager-output", "governor-review"],
      governorRunsInSeparateProfile: true,
      roleSkillPinningRequired: true,
      realProfileRosterRequired: true,
      gatewayDispatcherRequiredAtRuntime: true,
    },
    profileSkillVisibility: {
      namedProfilesHaveSeparateHermesHome: true,
      requiredExternalDirectory: join(targetHome, ".hermes", "skills"),
      configKey: "skills.external_dirs",
    },
    assignedSkills: { all: normalized.allSkills, byAgent: normalized.byAgent },
    sideEffects: { createProfiles: false, createCron: false, startGateway: false },
    canary: {
      status: "pending",
      requiresHermesCli: true,
      requiredFlow: ["ast-ceo", "manager-output", "ast-governor", "ast-ceo-synthesis"],
      receiptMustBindRepositoryRevision: true,
    },
  };
}
