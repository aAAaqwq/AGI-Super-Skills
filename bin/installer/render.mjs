import { existsSync, lstatSync, readFileSync, readdirSync, statSync } from "node:fs";
import { basename, join } from "node:path";

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

export function roleBody(packageRoot, agent) {
  const root = join(packageRoot, agent.path);
  return ROLE_FILES.filter((name) => existsSync(join(root, name)))
    .map((name) => `## ${name.slice(0, -3)}\n\n${readFileSync(join(root, name), "utf8").trim()}`)
    .join("\n\n");
}

export function markdownAgent(packageRoot, agent, fileSuffix = ".md") {
  const frontmatter = `---\nname: ${agent.id}\ndescription: ${yamlText(agent.focus)}\n---\n\n`;
  return { name: `${agent.id}${fileSuffix}`, content: Buffer.from(`${frontmatter}${roleBody(packageRoot, agent)}\n`) };
}

export function codexAgent(packageRoot, agent) {
  const instructions = `${roleBody(packageRoot, agent)}\n\nAccept one bounded task from the parent coordinator. Return artifacts, checks, limitations, and next action. Do not spawn subagents or claim unperformed verification.`;
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

export function agentAsSkill(packageRoot, agent) {
  return Buffer.from(
    `---\nname: agi-super-team-${agent.id}\ndescription: ${yamlText(agent.focus)}\n---\n\n# ${agent.name}\n\n${roleBody(packageRoot, agent)}\n`,
  );
}

export function openClawFiles(packageRoot, agent) {
  const source = join(packageRoot, agent.path);
  return ROLE_FILES.filter((name) => existsSync(join(source, name))).map((name) => ({
    relative: join(`workspace-${agent.id}`, name),
    content: readFileSync(join(source, name)),
  }));
}

export function walkFiles(root, prefix = "") {
  const output = [];
  for (const name of readdirSync(root).sort()) {
    const source = join(root, name);
    const metadata = lstatSync(source);
    if (metadata.isSymbolicLink()) throw new Error(`refusing symlinked source: ${source}`);
    if (metadata.isDirectory()) output.push(...walkFiles(source, join(prefix, name)));
    else if (metadata.isFile()) output.push({ source, relative: join(prefix, name), content: readFileSync(source) });
  }
  return output;
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

export function combinedRules(packageRoot, agents, skills) {
  const sections = ["# AGI Super Team"];
  if (agents.length) sections.push(agents.map((agent) => `## ${agent.name}\n\n${roleBody(packageRoot, agent)}`).join("\n\n"));
  if (skills.length) sections.push(`## Curated Skills\n\n${skills.map((name) => `- ${name}`).join("\n")}`);
  return sections.join("\n\n");
}

export function globalCeoPayload(packageRoot) {
  const path = join(packageRoot, "plugins", "agi-super-team-codex", "payload", "global", "AGENTS.md");
  const content = readFileSync(path, "utf8").trim();
  if (content.split(BEGIN_MARKER).length !== 2 || content.split(END_MARKER).length !== 2) {
    throw new Error("global CEO payload has invalid managed markers");
  }
  return content;
}

export function antigravityAgent(packageRoot, agent) {
  return { relative: join(agent.id, "agent.md"), content: markdownAgent(packageRoot, agent).content };
}

export function displayPath(path) {
  return basename(path) || path;
}
