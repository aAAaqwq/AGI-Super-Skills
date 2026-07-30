import {
  chmodSync,
  closeSync,
  copyFileSync,
  existsSync,
  lstatSync,
  mkdirSync,
  mkdtempSync,
  openSync,
  readFileSync,
  realpathSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";
import { adapterFor } from "../adapters/index.mjs";
import {
  agentAsSkill,
  antigravityAgent,
  codexAgent,
  codexSpecialist,
  combinedRules,
  globalCeoPayload,
  markdownAgent,
  markdownSpecialist,
  openClawFiles,
  renderManaged,
  specialistAsSkill,
  specialistBody,
  walkFiles,
} from "./render.mjs";

export function safeRoot(input, label) {
  const path = resolve(input);
  if (path === resolve("/") || !input) throw new Error(`refusing unsafe ${label}: ${path}`);
  if (existsSync(path) && (lstatSync(path).isSymbolicLink() || !statSync(path).isDirectory())) {
    throw new Error(`invalid ${label}: ${path}`);
  }
  return path;
}

export function readSafe(path) {
  if (!existsSync(path)) return null;
  const metadata = lstatSync(path);
  if (metadata.isSymbolicLink() || !metadata.isFile()) throw new Error(`refusing unsafe destination: ${path}`);
  return readFileSync(path);
}

function destination(root, configuredPath, child = "") {
  if (isAbsolute(configuredPath) || configuredPath.split(/[\\/]/).includes("..")) {
    throw new Error(`unsafe adapter path: ${configuredPath}`);
  }
  return join(root, configuredPath, child);
}

function assertSafeAncestors(root, path) {
  const rel = relative(root, path);
  if (rel === ".." || rel.startsWith(`..${process.platform === "win32" ? "\\" : "/"}`)) {
    throw new Error(`refusing destination outside target root: ${path}`);
  }
  let cursor = root;
  for (const component of rel.split(/[\\/]/).slice(0, -1)) {
    if (!component) continue;
    cursor = join(cursor, component);
    if (!existsSync(cursor)) continue;
    const metadata = lstatSync(cursor);
    if (metadata.isSymbolicLink() || !metadata.isDirectory()) {
      throw new Error(`refusing unsafe destination ancestor: ${cursor}`);
    }
  }
}

function addFile(plan, tool, root, path, content, label) {
  assertSafeAncestors(root, path);
  const baseline = readSafe(path);
  const rendered = Buffer.isBuffer(content) ? content : Buffer.from(content);
  plan.push({
    tool: tool.id,
    root,
    destination: path,
    content: rendered,
    baseline,
    label,
    status: baseline === null ? "add" : Buffer.compare(baseline, rendered) === 0 ? "unchanged" : "update",
  });
}

function selectedAssignedSkills(catalog, agents) {
  const byAgent = Object.fromEntries(
    agents.map((agent) => [
      agent.id,
      [...(catalog.assignedSkills.byAgent[agent.id] || [])],
    ]),
  );
  return {
    byAgent,
    all: [...new Set(Object.values(byAgent).flat())].sort(),
  };
}

function planSkills(plan, catalog, tool, root, assignedSkills) {
  if (!tool.skillPaths.length) return;
  const canonical = tool.skillSource === "canonical-assigned";
  const skillNames = canonical ? assignedSkills.all : catalog.curatedSkills;
  const skillsRoot = canonical ? catalog.canonicalSkillsRoot : catalog.curatedSkillsRoot;
  for (const configured of tool.skillPaths) {
    for (const skill of skillNames) {
      const sourceRoot = join(skillsRoot, skill);
      const targetRoot = destination(root, configured, skill);
      if (existsSync(targetRoot) && lstatSync(targetRoot).isSymbolicLink()) {
        const resolved = realpathSync(targetRoot);
        if (!statSync(resolved).isDirectory()) {
          throw new Error(`refusing non-directory Skill symlink: ${targetRoot}`);
        }
        const sourceFiles = walkFiles(sourceRoot);
        const targetFiles = walkFiles(resolved);
        const targetByPath = new Map(
          targetFiles.map((file) => [file.relative, file.content]),
        );
        const exact = sourceFiles.length === targetFiles.length
          && sourceFiles.every((file) => {
            const candidate = targetByPath.get(file.relative);
            return candidate && Buffer.compare(file.content, candidate) === 0;
          });
        if (!exact) {
          throw new Error(`refusing mismatched Skill symlink: ${targetRoot}`);
        }
        continue;
      }
      for (const file of walkFiles(sourceRoot)) {
        addFile(plan, tool, root, destination(root, configured, join(skill, file.relative)), file.content, `skill:${skill}`);
      }
    }
  }
}

function renderAgents(plan, packageRoot, catalog, tool, root, agents, codexPayloadAll, groups = {}) {
  const mode = tool.agentMode;
  if (mode === "codex-toml") {
    const ceo = agents.find((agent) => agent.id === "ceo");
    if (ceo) {
      const path = destination(root, dirname(tool.agentPaths[0]), "AGENTS.md");
      const begin = "<!-- AGI-SUPER-TEAM:CEO:BEGIN -->";
      const end = "<!-- AGI-SUPER-TEAM:CEO:END -->";
      const payload = globalCeoPayload(packageRoot);
      const inner = payload.slice(begin.length, payload.length - end.length).trim();
      addFile(plan, tool, root, path, renderManaged(readSafe(path), inner, begin, end), "global-ceo");
    }
    if (codexPayloadAll) {
      const payload = join(packageRoot, "plugins", "agi-super-team-codex", "payload", "agents");
      for (const file of walkFiles(payload)) {
        addFile(plan, tool, root, destination(root, tool.agentPaths[0], file.relative), file.content, `agent:${file.relative}`);
      }
    } else {
      for (const agent of agents.filter((item) => item.id !== "ceo")) {
        addFile(plan, tool, root, destination(root, tool.agentPaths[0], `ast-${agent.id}.toml`), codexAgent(packageRoot, agent, groups[agent.id] || null), `agent:${agent.id}`);
      }
    }
    return;
  }
  if (mode === "openclaw-workspace") {
    for (const agent of agents) for (const file of openClawFiles(packageRoot, agent, groups[agent.id] || null)) {
      addFile(plan, tool, root, destination(root, tool.agentPaths[0], file.relative), file.content, `agent:${agent.id}`);
    }
    return;
  }
  if (mode === "agent-as-skill") {
    for (const agent of agents) addFile(plan, tool, root, destination(root, tool.agentPaths[0], join(agent.id, "SKILL.md")), agentAsSkill(packageRoot, agent, groups[agent.id] || null), `agent:${agent.id}`);
    return;
  }
  if (mode === "antigravity-agent") {
    for (const agent of agents) {
      const file = antigravityAgent(packageRoot, agent, groups[agent.id] || null);
      addFile(plan, tool, root, destination(root, tool.agentPaths[0], file.relative), file.content, `agent:${agent.id}`);
    }
    return;
  }
  if (mode === "combined-rules") {
    throw new Error(`internal error: combined rules for ${tool.id} must be planned jointly`);
  }
  if (["markdown", "cursor-rule", "trae-rule", "gemini-extension-skill"].includes(mode)) {
    const suffix = tool.id === "copilot" ? ".agent.md" : mode === "cursor-rule" ? ".mdc" : ".md";
    for (const configured of tool.agentPaths) for (const agent of agents) {
      const rendered = markdownAgent(packageRoot, agent, suffix, groups[agent.id] || null);
      addFile(plan, tool, root, destination(root, configured, rendered.name), rendered.content, `agent:${agent.id}`);
    }
    return;
  }
  throw new Error(`unsupported agent mode for ${tool.id}: ${mode}`);
}

function renderSpecialists(plan, packageRoot, tool, root, specialists) {
  if (!specialists.length) return;
  const mode = tool.agentMode;
  if (mode === "codex-toml") {
    for (const specialist of specialists) {
      addFile(plan, tool, root, destination(root, tool.agentPaths[0], `ast-${specialist.manager}-${specialist.id}.toml`), codexSpecialist(packageRoot, specialist), `specialist:${specialist.manager}/${specialist.id}`);
    }
    return;
  }
  if (mode === "openclaw-workspace") {
    for (const specialist of specialists) {
      addFile(plan, tool, root, destination(root, tool.agentPaths[0], join(`workspace-${specialist.manager}-${specialist.id}`, "AGENTS.md")), Buffer.from(specialistBody(packageRoot, specialist)), `specialist:${specialist.manager}/${specialist.id}`);
    }
    return;
  }
  if (mode === "agent-as-skill") {
    for (const specialist of specialists) {
      addFile(plan, tool, root, destination(root, tool.agentPaths[0], join(`${specialist.manager}-${specialist.id}`, "SKILL.md")), specialistAsSkill(packageRoot, specialist), `specialist:${specialist.manager}/${specialist.id}`);
    }
    return;
  }
  if (mode === "antigravity-agent") {
    for (const specialist of specialists) {
      addFile(plan, tool, root, destination(root, tool.agentPaths[0], join(`${specialist.manager}-${specialist.id}`, "agent.md")), markdownSpecialist(packageRoot, specialist).content, `specialist:${specialist.manager}/${specialist.id}`);
    }
    return;
  }
  if (["markdown", "cursor-rule", "trae-rule", "gemini-extension-skill"].includes(mode)) {
    const suffix = tool.id === "copilot" ? ".agent.md" : mode === "cursor-rule" ? ".mdc" : ".md";
    for (const configured of tool.agentPaths) for (const specialist of specialists) {
      const rendered = markdownSpecialist(packageRoot, specialist, suffix);
      addFile(plan, tool, root, destination(root, configured, rendered.name), rendered.content, `specialist:${specialist.manager}/${specialist.id}`);
    }
    return;
  }
  if (mode !== "combined-rules") throw new Error(`unsupported specialist mode for ${tool.id}: ${mode}`);
}

export function buildPlan({ packageRoot, catalog, tools, home, projectDir, includeAgents, includeSkills, agentIds, subagentManagers = new Set(), includeCcoSpecialists = false, codexPayloadAll = false }) {
  const plan = [];
  const selected = agentIds ? catalog.agents.filter((agent) => agentIds.has(agent.id)) : catalog.agents;
  const managers = new Set(subagentManagers);
  if (includeCcoSpecialists) managers.add("cco");
  const groups = Object.fromEntries([...managers].map((manager) => [manager, catalog.specialistGroups[manager]]));
  const specialists = Object.values(groups).flatMap((group) => group.specialists);
  const assignedSkills = selectedAssignedSkills(catalog, selected);
  for (const tool of tools) {
    const root = tool.scope === "project" ? projectDir : home;
    if (!root) throw new Error(`${tool.id} is project-scoped; pass --project-dir <path>`);
    if (tool.agentMode === "harness-adapter") {
      const adapter = adapterFor(tool.id);
      const artifacts = adapter.renderAdapterArtifacts({
        packageRoot,
        tool,
        agents: includeAgents ? selected : [],
        groups,
        specialists: includeAgents ? specialists : [],
        assignedSkills,
        includeAgents,
        includeSkills,
      });
      for (const artifact of artifacts) {
        const path = destination(root, artifact.relativePath);
        let content = artifact.content;
        if (artifact.managed) {
          const rendered = Buffer.isBuffer(content) ? content.toString("utf8") : String(content);
          const { begin, end } = artifact.managed;
          const start = rendered.indexOf(begin);
          const finish = rendered.indexOf(end, start + begin.length);
          if (start < 0 || finish < 0) throw new Error(`invalid managed Adapter artifact: ${artifact.label}`);
          content = renderManaged(
            readSafe(path),
            rendered.slice(start + begin.length, finish).trim(),
            begin,
            end,
          );
        }
        addFile(plan, tool, root, path, content, artifact.label);
      }
      const adapterConnection = adapter.buildConnectionSpec({
        packageRoot,
        home: root,
        tool,
        agents: includeAgents ? selected : [],
        groups,
        specialists: includeAgents ? specialists : [],
        assignedSkills,
      });
      const connection = {
        ...adapterConnection,
        schemaVersion: 1,
        harness: tool.id,
        runtimeEvidence: "pending",
        coordinator: adapterConnection.coordinator ?? "ast-ceo",
        independentReviewer: adapterConnection.independentReviewer ?? "ast-governor",
        requiredMaxDepth: adapterConnection.requiredMaxDepth ?? 2,
        maxConcurrentChildren: adapterConnection.maxConcurrentChildren ?? 2,
      };
      addFile(
        plan,
        tool,
        root,
        destination(root, tool.connectionPath),
        `${JSON.stringify(connection, null, 2)}\n`,
        `adapter:${tool.id}/connection`,
      );
      if (includeSkills) planSkills(plan, catalog, tool, root, assignedSkills);
      continue;
    }
    if (tool.agentMode === "combined-rules") {
      const path = destination(root, tool.agentPaths[0]);
      assertSafeAncestors(root, path);
      addFile(
        plan,
        tool,
        root,
        path,
        renderManaged(readSafe(path), combinedRules(packageRoot, includeAgents ? selected : [], includeSkills ? catalog.skills : [], groups)),
        "combined-rules",
      );
      continue;
    }
    if (includeAgents) renderAgents(plan, packageRoot, catalog, tool, root, selected, codexPayloadAll && tool.id === "codex", groups);
    if (includeAgents && !(codexPayloadAll && tool.id === "codex")) renderSpecialists(plan, packageRoot, tool, root, specialists);
    if (includeSkills) planSkills(plan, catalog, tool, root, assignedSkills);
  }
  return plan;
}

function atomicWrite(path, content) {
  mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  if (existsSync(path) && lstatSync(path).isSymbolicLink()) throw new Error(`refusing symlinked destination: ${path}`);
  const temporary = join(dirname(path), `.agi-super-team.${process.pid}.${Date.now()}.tmp`);
  const descriptor = openSync(temporary, "wx", 0o600);
  try { writeFileSync(descriptor, content); } finally { closeSync(descriptor); }
  chmodSync(temporary, 0o600);
  renameSync(temporary, path);
}

export function applyPlan(plan) {
  const changed = plan.filter((item) => item.status !== "unchanged");
  if (!changed.length) return [];
  const roots = [...new Set(changed.map((item) => item.root))];
  const locks = [];
  const backups = [];
  const written = [];
  try {
    for (const root of roots) {
      mkdirSync(root, { recursive: true, mode: 0o700 });
      const lock = join(root, ".agi-super-team-installer.lock");
      locks.push({ path: lock, descriptor: openSync(lock, "wx", 0o600) });
    }
    for (const root of roots) {
      if (changed.some((item) => item.root === root && item.baseline !== null)) {
        const backupRoot = join(root, ".agi-super-team-backups");
        mkdirSync(backupRoot, { recursive: true, mode: 0o700 });
        backups.push({ root, path: mkdtempSync(join(backupRoot, `${new Date().toISOString().replaceAll(":", "")}-`)) });
      }
    }
    for (const item of changed) {
      const current = readSafe(item.destination);
      const stable = current === null ? item.baseline === null : item.baseline !== null && Buffer.compare(current, item.baseline) === 0;
      if (!stable) throw new Error(`destination changed after preview: ${item.destination}`);
      if (item.baseline !== null) {
        const backup = backups.find((entry) => entry.root === item.root);
        const target = join(backup.path, relative(item.root, item.destination));
        mkdirSync(dirname(target), { recursive: true, mode: 0o700 });
        copyFileSync(item.destination, target);
      }
      atomicWrite(item.destination, item.content);
      written.push(item);
    }
  } catch (error) {
    for (const item of written.reverse()) {
      const current = readSafe(item.destination);
      if (current === null || Buffer.compare(current, item.content) !== 0) continue;
      if (item.baseline === null) unlinkSync(item.destination);
      else atomicWrite(item.destination, item.baseline);
    }
    throw error;
  } finally {
    for (const lock of locks) {
      closeSync(lock.descriptor);
      if (existsSync(lock.path)) unlinkSync(lock.path);
    }
  }
  return backups.map((entry) => entry.path);
}

export function doctor(plan, tools) {
  const issues = [];
  for (const item of plan) {
    try {
      const current = readSafe(item.destination);
      if (current === null) issues.push(`missing: ${item.destination}`);
      else if (Buffer.compare(current, item.content) !== 0) issues.push(`drifted: ${item.destination}`);
    } catch (error) { issues.push(error.message); }
  }
  return {
    ok: issues.length === 0,
    issues,
    tools: tools.map((tool) => ({ id: tool.id, support: tool.support, scope: tool.scope })),
    files: plan.length,
  };
}
