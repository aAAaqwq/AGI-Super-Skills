import { existsSync, lstatSync, readFileSync, readdirSync, realpathSync } from "node:fs";
import { basename, join, resolve } from "node:path";
import { isPhysicalStrictDescendant } from "./path-safety.mjs";

const ROLE_FILES = ["IDENTITY.md", "SOUL.md", "AGENTS.md", "USER.md", "TOOLS.md", "MEMORY.md"];
export const BEGIN_MARKER = "<!-- AGI-SUPER-TEAM:CEO:BEGIN -->";
export const END_MARKER = "<!-- AGI-SUPER-TEAM:CEO:END -->";
export const RULES_BEGIN = "<!-- AGI-SUPER-TEAM:RULES:BEGIN -->";
export const RULES_END = "<!-- AGI-SUPER-TEAM:RULES:END -->";

function yamlText(value) {
  return JSON.stringify(String(value));
}

function tomlText(value) {
  return JSON.stringify(String(value));
}

function managerRoutingBody(group, runtimeName = (manager, id) => `${manager}/${id}`, roleName = (id) => id) {
  if (!group?.specialists?.length) return "";
  const specialistRoutes = group.specialists.map((item) =>
    `- \`${runtimeName(group.manager, item.id)}\`（${item.name}）：${item.trigger}\n  - 不调用：${item.doNotUseWhen}`,
  );
  const roleRoutes = group.roleRoutes.map((item) =>
    `- \`${roleName(item.id)}\`（${item.name}）：${item.trigger}\n  - 不调用：${item.doNotUseWhen}`,
  );
  return `## ${group.manager.toUpperCase()} 子 Agent 路由\n\n先判断工作对象、领域和交付阶段。默认只选一个主责；只有独立的下游交付物才增加一个协作角色。缺少关键输入或两个角色仍然冲突时先澄清，不要广播。只能调用以下已安装的直属叶子，最多两个并发，总深度不超过二；子 Agent 不得继续创建 Agent。\n\n${[...roleRoutes, ...specialistRoutes].join("\n")}\n\n真实登录、上传、发布、部署、改基础设施、付费和第三方联系必须经过人类批准。`;
}

function readRoleFile(root, name, encoding = null) {
  const source = join(root, name);
  if (!isPhysicalStrictDescendant(root, source)) throw new Error(`unsafe Agent role file: ${source}`);
  const metadata = lstatSync(source);
  if (metadata.isSymbolicLink() || !metadata.isFile()) throw new Error(`invalid Agent role file: ${source}`);
  return encoding ? readFileSync(source, encoding) : readFileSync(source);
}

export function roleBody(packageRoot, agent, group = null, runtimeName, roleName) {
  const root = join(packageRoot, agent.path);
  const body = ROLE_FILES.filter((name) => existsSync(join(root, name)))
    .map((name) => `## ${name.slice(0, -3)}\n\n${readRoleFile(root, name, "utf8").trim()}`)
    .join("\n\n");
  const routing = group ? managerRoutingBody(group, runtimeName, roleName) : "";
  return [body, routing].filter(Boolean).join("\n\n");
}

export function markdownAgent(packageRoot, agent, fileSuffix = ".md", group = null) {
  const frontmatter = `---\nname: ${agent.id}\ndescription: ${yamlText(agent.focus)}\n---\n\n`;
  return { name: `${agent.id}${fileSuffix}`, content: Buffer.from(`${frontmatter}${roleBody(packageRoot, agent, group, (manager, id) => `${manager}-${id}`, (id) => id)}\n`) };
}

export function codexAgent(packageRoot, agent, group = null) {
  const execution = group
    ? `你是受限管理节点，只能调用上面列出的 ast-${agent.id}-* 直属叶子和 canonical 角色引用；fork_turns 必须为 none，最多两个叶子并发，总深度为二。`
    : "你是叶子 Agent，不得创建子 Agent。";
  const instructions = `${roleBody(packageRoot, agent, group, (manager, id) => `ast-${manager}-${id}`, (id) => `ast-${id}`)}\n\n只接受一个边界清楚的任务，回传产物、检查、限制和下一步。${execution} 不得声称未执行的验证。`;
  return Buffer.from(
    `# Generated from ${agent.path}; rerun the AGI Super Team installer to update.\n` +
      `name = ${tomlText(`ast-${agent.id}`)}\n` +
      `description = ${tomlText(`C-suite ${agent.id.toUpperCase()} leaf: ${agent.focus}`)}\n` +
      `nickname_candidates = [${tomlText(agent.id.toUpperCase())}]\n` +
      `model_reasoning_effort = "high"\n` +
      `sandbox_mode = "read-only"\n` +
      `developer_instructions = ${tomlText(instructions)}\n`,
  );
}

export function specialistBody(packageRoot, specialist) {
  const inputs = specialist.requiredInputs.map((item) => `- ${item}`).join("\n");
  const outputs = specialist.outputs.map((item) => `- ${item}`).join("\n");
  const acceptance = specialist.acceptance.map((item) => `- ${item}`).join("\n");
  const sourceRole = specialist.sourceRole ? `\n- 上游角色：${specialist.sourceRole}\n- 改编说明：${specialist.adaptation}` : "";
  const specialistRoot = resolve(packageRoot, "agents", specialist.manager, "subagents", specialist.id);
  const specialistSource = resolve(packageRoot, specialist.vendoredPath);
  if (!isPhysicalStrictDescendant(specialistRoot, specialistSource)) {
    throw new Error(`unsafe specialist source: ${specialist.vendoredPath}`);
  }
  const upstream = readFileSync(specialistSource, "utf8");
  return `${upstream}\n\n---\n\n# AGI Super Team 路由与安全信封\n\n你是 ${specialist.manager.toUpperCase()} 直属叶子 Agent，不得创建子 Agent。\n\n## 何时调用\n\n${specialist.trigger}\n\n## 不应调用\n\n${specialist.doNotUseWhen}\n\n## 必需输入\n\n${inputs}\n\n## 标准交付物\n\n${outputs}\n\n## 验收标准\n\n${acceptance}\n\n## 权限边界\n\n${specialist.boundary}\n\n只返回事实、假设、产物、检查、限制和下一步。禁止登录账号、使用凭证、自动发布、评论、私信、投放、付费或联系第三方；不得声称未执行的测试、部署或运行结果。动态平台、市场、法律、财务、税务、技术和标准结论必须注明需要当前一手来源验证。\n\n## 来源\n\n- jnMetaCode/agency-agents-zh：${specialist.sourcePath}${sourceRole}\n`;
}

export function markdownSpecialist(packageRoot, specialist, fileSuffix = ".md") {
  const name = `${specialist.manager}-${specialist.id}`;
  const frontmatter = `---\nname: ${name}\ndescription: ${yamlText(`${specialist.manager.toUpperCase()} 子专家｜${specialist.name}：${specialist.trigger}`)}\n---\n\n`;
  return { name: `${name}${fileSuffix}`, content: Buffer.from(`${frontmatter}${specialistBody(packageRoot, specialist)}`) };
}

export function codexSpecialist(packageRoot, specialist) {
  const name = `ast-${specialist.manager}-${specialist.id}`;
  return Buffer.from(
    `# Generated from config/${specialist.manager}-specialists.json; rerun the AGI Super Team installer to update.\n` +
      `name = ${tomlText(name)}\n` +
      `description = ${tomlText(`${specialist.manager.toUpperCase()} 子专家｜${specialist.name}：${specialist.trigger}`)}\n` +
      `nickname_candidates = [${tomlText(specialist.id)}]\n` +
      `model_reasoning_effort = "high"\n` +
      `sandbox_mode = "read-only"\n` +
      `developer_instructions = ${tomlText(specialistBody(packageRoot, specialist))}\n`,
  );
}

export function specialistAsSkill(packageRoot, specialist) {
  return Buffer.from(`---\nname: agi-super-team-${specialist.manager}-${specialist.id}\ndescription: ${yamlText(`${specialist.manager.toUpperCase()} 子专家｜${specialist.name}：${specialist.trigger}`)}\n---\n\n${specialistBody(packageRoot, specialist)}`);
}

export function agentAsSkill(packageRoot, agent, group = null) {
  return Buffer.from(
    `---\nname: agi-super-team-${agent.id}\ndescription: ${yamlText(agent.focus)}\n---\n\n# ${agent.name}\n\n${roleBody(packageRoot, agent, group, (manager, id) => `agi-super-team-${manager}-${id}`, (id) => `agi-super-team-${id}`)}\n`,
  );
}

export function openClawFiles(packageRoot, agent, group = null) {
  const source = join(packageRoot, agent.path);
  return ROLE_FILES.filter((name) => existsSync(join(source, name))).map((name) => ({
    relative: join(`workspace-${agent.id}`, name),
    content: name === "AGENTS.md" && group
      ? Buffer.from(`${readRoleFile(source, name, "utf8").trim()}\n\n${managerRoutingBody(group, (manager, id) => `workspace-${manager}-${id}`, (id) => `workspace-${id}`)}\n`)
      : readRoleFile(source, name),
  }));
}

function walkPhysicalFiles(root, prefix, physicalRoot) {
  const output = [];
  for (const name of readdirSync(root).sort()) {
    if (name === "__pycache__" || name.endsWith(".pyc")) continue;
    const source = join(root, name);
    if (!isPhysicalStrictDescendant(physicalRoot, source)) {
      throw new Error(`refusing source outside physical root: ${source}`);
    }
    const metadata = lstatSync(source);
    if (metadata.isSymbolicLink()) throw new Error(`refusing symlinked source: ${source}`);
    if (metadata.isDirectory()) output.push(...walkPhysicalFiles(source, join(prefix, name), physicalRoot));
    else if (metadata.isFile()) output.push({
      source,
      relative: join(prefix, name),
      content: readFileSync(source),
      mode: metadata.mode & 0o100 ? 0o700 : 0o600,
    });
  }
  return output;
}

export function walkFiles(root, prefix = "") {
  const metadata = lstatSync(root);
  if (metadata.isSymbolicLink()) throw new Error(`refusing symlinked source root: ${root}`);
  if (!metadata.isDirectory()) throw new Error(`invalid source root: ${root}`);
  const physicalRoot = realpathSync.native(root);
  return walkPhysicalFiles(physicalRoot, prefix, physicalRoot);
}

export function renderManaged(existing, managed, begin = RULES_BEGIN, end = RULES_END) {
  const block = `${begin}\n${managed.trim()}\n${end}`;
  if (existing === null) return Buffer.from(`${block}\n`);
  const current = existing.toString("utf8");
  const beginCount = current.split(begin).length - 1;
  const endCount = current.split(end).length - 1;
  if (!beginCount && !endCount) return Buffer.from(`${current.trimEnd()}${current.trim() ? "\n\n" : ""}${block}\n`);
  if (beginCount !== 1 || endCount !== 1) throw new Error("existing rules file has malformed AGI Super Team markers");
  const start = current.indexOf(begin);
  const finish = current.indexOf(end, start);
  if (finish < start) throw new Error("existing rules file has reversed AGI Super Team markers");
  return Buffer.from(`${current.slice(0, start)}${block}${current.slice(finish + end.length)}`);
}

export function combinedRules(packageRoot, agents, skills, groups = {}) {
  const sections = ["# AGI Super Team"];
  if (agents.length) sections.push(agents.map((agent) => `## ${agent.name}\n\n${roleBody(packageRoot, agent, groups[agent.id] || null)}`).join("\n\n"));
  const indexes = Object.values(groups).flatMap((group) => group.specialists.map((item) => `- ${group.manager}/${item.id}（${item.name}）：${item.trigger}`));
  if (indexes.length) sections.push(`## Specialist Index\n\n此类客户端不支持原生子 Agent；以下角色仅作为手动或顺序路由索引，不内联完整上游正文。\n\n${indexes.join("\n")}`);
  if (skills.length) sections.push(`## Curated Skills\n\n${skills.map((name) => `- ${name}`).join("\n")}`);
  return sections.join("\n\n");
}

export function globalCeoPayload(packageRoot) {
  const payloadRoot = join(packageRoot, "plugins", "agi-super-team-codex", "payload");
  const path = join(payloadRoot, "global", "AGENTS.md");
  if (!isPhysicalStrictDescendant(payloadRoot, path)) {
    throw new Error(`unsafe global CEO payload: ${path}`);
  }
  const content = readFileSync(path, "utf8").trim();
  if (content.split(BEGIN_MARKER).length !== 2 || content.split(END_MARKER).length !== 2) {
    throw new Error("global CEO payload has invalid managed markers");
  }
  return content;
}

export function antigravityAgent(packageRoot, agent, group = null) {
  return { relative: join(agent.id, "agent.md"), content: markdownAgent(packageRoot, agent, ".md", group).content };
}

export function displayPath(path) {
  return basename(path) || path;
}
