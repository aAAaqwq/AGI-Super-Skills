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
  readdirSync,
  realpathSync,
  renameSync,
  rmdirSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import * as nativePath from "node:path";
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

export function safeRoot(input, label, pathApi = nativePath) {
  const path = pathApi.resolve(input);
  if (!input || pathApi.parse(path).root === path) throw new Error(`refusing unsafe ${label}: ${path}`);
  if (pathApi !== nativePath) return path;
  if (existsSync(path)) {
    if (lstatSync(path).isSymbolicLink() || !statSync(path).isDirectory()) {
      throw new Error(`invalid ${label}: ${path}`);
    }
    return realpathSync.native(path);
  }
  let ancestor = path;
  while (!existsSync(ancestor)) {
    const parent = dirname(ancestor);
    if (parent === ancestor) throw new Error(`invalid ${label}: ${path}`);
    ancestor = parent;
  }
  if (!statSync(ancestor).isDirectory()) throw new Error(`invalid ${label}: ${path}`);
  return resolve(realpathSync.native(ancestor), relative(ancestor, path));
}

export function readSafe(path) {
  if (!existsSync(path)) return null;
  const metadata = lstatSync(path);
  if (metadata.isSymbolicLink() || !metadata.isFile()) throw new Error(`refusing unsafe destination: ${path}`);
  return readFileSync(path);
}

export function modesEquivalent(actualMode, expectedMode, platform = process.platform) {
  const actual = actualMode & 0o777;
  const expected = expectedMode & 0o777;
  if (platform === "win32") return Boolean(actual & 0o200) === Boolean(expected & 0o200);
  return actual === expected;
}

function destination(root, configuredPath, child = "") {
  if (isAbsolute(configuredPath) || configuredPath.split(/[\\/]/).includes("..")) {
    throw new Error(`unsafe adapter path: ${configuredPath}`);
  }
  return join(root, configuredPath, child);
}

function assertSafeAncestors(root, path) {
  const rel = relative(root, path);
  if (rel === "" || rel === ".." || rel.startsWith(`..${nativePath.sep}`) || isAbsolute(rel)) {
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

function addFile(plan, tool, root, path, content, label, mode = 0o600) {
  assertSafeAncestors(root, path);
  const baseline = readSafe(path);
  const baselineMode = baseline === null ? null : lstatSync(path).mode & 0o777;
  const rendered = Buffer.isBuffer(content) ? content : Buffer.from(content);
  plan.push({
    tool: tool.id,
    root,
    destination: path,
    content: rendered,
    baseline,
    baselineMode,
    mode,
    platform: tool.platform ?? process.platform,
    label,
    status: baseline === null
      ? "add"
      : Buffer.compare(baseline, rendered) === 0
        && modesEquivalent(baselineMode, mode, tool.platform)
        ? "unchanged"
        : "update",
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
        const targetByPath = new Map(targetFiles.map((file) => [file.relative, file]));
        const exact = sourceFiles.length === targetFiles.length
          && sourceFiles.every((file) => {
            const candidate = targetByPath.get(file.relative);
            return candidate
              && modesEquivalent(candidate.mode, file.mode, tool.platform)
              && Buffer.compare(file.content, candidate.content) === 0;
          });
        if (!exact) {
          throw new Error(`refusing mismatched Skill symlink: ${targetRoot}`);
        }
        continue;
      }
      for (const file of walkFiles(sourceRoot)) {
        addFile(plan, tool, root, destination(root, configured, join(skill, file.relative)), file.content, `skill:${skill}`, file.mode);
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
        addFile(plan, tool, root, destination(root, tool.agentPaths[0], file.relative), file.content, `agent:${file.relative}`, file.mode);
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

export function buildPlan({ packageRoot, catalog, tools, home, projectDir, includeAgents, includeSkills, agentIds, subagentManagers = new Set(), includeCcoSpecialists = false, codexPayloadAll = false, platform = process.platform }) {
  const plan = [];
  const selected = agentIds ? catalog.agents.filter((agent) => agentIds.has(agent.id)) : catalog.agents;
  const managers = new Set(subagentManagers);
  if (includeCcoSpecialists) managers.add("cco");
  const groups = Object.fromEntries([...managers].map((manager) => [manager, catalog.specialistGroups[manager]]));
  const specialists = Object.values(groups).flatMap((group) => group.specialists);
  const assignedSkills = selectedAssignedSkills(catalog, selected);
  for (const configuredTool of tools) {
    const tool = { ...configuredTool, platform };
    const root = tool.scope === "project"
      ? projectDir
      : tool.installationRoot
        ? safeRoot(tool.installationRoot, `${tool.id} installation root`)
        : home;
    if (!root) throw new Error(`${tool.id} is project-scoped; pass --project-dir <path>`);
    if (tool.agentMode === "harness-adapter") {
      const adapter = adapterFor(tool.id);
      const artifacts = adapter.renderAdapterArtifacts({
        packageRoot,
        home: root,
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

function atomicWrite(path, content, mode = 0o600) {
  mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  if (existsSync(path) && lstatSync(path).isSymbolicLink()) throw new Error(`refusing symlinked destination: ${path}`);
  const temporary = join(dirname(path), `.agi-super-team.${process.pid}.${Date.now()}.tmp`);
  const descriptor = openSync(temporary, "wx", 0o600);
  try { writeFileSync(descriptor, content); } finally { closeSync(descriptor); }
  chmodSync(temporary, mode);
  renameSync(temporary, path);
}

function baselineMatches(item, current) {
  if (current === null || item.baseline === null) return current === null && item.baseline === null;
  if (Buffer.compare(current, item.baseline) !== 0) return false;
  return item.baselineMode === null
    || item.baselineMode === undefined
    || modesEquivalent(lstatSync(item.destination).mode, item.baselineMode, item.platform);
}

function releaseLocks(locks) {
  for (const lock of locks) {
    closeSync(lock.descriptor);
    if (existsSync(lock.path)) unlinkSync(lock.path);
  }
}

function acquireLocks(roots) {
  const locks = [];
  try {
    for (const root of roots) {
      const lock = join(root, ".agi-super-team-installer.lock");
      locks.push({ path: lock, descriptor: openSync(lock, "wx", 0o600) });
    }
    return locks;
  } catch (error) {
    releaseLocks(locks);
    throw error;
  }
}

function ensureDirectory(path, createdDirectories) {
  const missing = [];
  let cursor = resolve(path);
  while (!existsSync(cursor)) {
    missing.unshift(cursor);
    const parent = dirname(cursor);
    if (parent === cursor) break;
    cursor = parent;
  }
  for (const directory of missing) {
    try {
      mkdirSync(directory, { mode: 0o700 });
      const metadata = lstatSync(directory);
      createdDirectories.push({ path: directory, dev: metadata.dev, ino: metadata.ino });
    } catch (error) {
      if (error.code !== "EEXIST") throw error;
      const metadata = lstatSync(directory);
      if (metadata.isSymbolicLink() || !metadata.isDirectory()) {
        throw new Error(`refusing unsafe destination directory: ${directory}`);
      }
    }
  }
}

function removeEmptyCreatedDirectories(createdDirectories) {
  const byPath = new Map(createdDirectories.map((entry) => [entry.path, entry]));
  const directories = [...byPath.values()].sort((left, right) => right.path.length - left.path.length);
  for (const directory of directories) {
    if (!existsSync(directory.path)) continue;
    const metadata = lstatSync(directory.path);
    if (metadata.isSymbolicLink() || !metadata.isDirectory()) continue;
    if (metadata.dev !== directory.dev || metadata.ino !== directory.ino) continue;
    if (readdirSync(directory.path).length === 0) rmdirSync(directory.path);
  }
}

function assertBackupsUnchanged(backupFiles) {
  for (const backup of backupFiles) {
    const current = readSafe(backup.path);
    if (current === null
      || Buffer.compare(current, backup.content) !== 0
      || !modesEquivalent(lstatSync(backup.path).mode, backup.mode, backup.platform)) {
      throw new Error(`backup changed after install; refusing rollback: ${backup.path}`);
    }
  }
}

function removeBackupFiles(backupFiles) {
  for (const backup of [...backupFiles].reverse()) unlinkSync(backup.path);
}

function restoreWritten(written) {
  for (const item of written) {
    const current = readSafe(item.destination);
    const currentMode = current === null ? null : lstatSync(item.destination).mode & 0o777;
    if (current === null
      || Buffer.compare(current, item.content) !== 0
      || !modesEquivalent(currentMode, item.installedMode, item.platform)) {
      throw new Error(`destination changed after install; refusing rollback: ${item.destination}`);
    }
  }
  for (const item of [...written].reverse()) {
    if (item.baseline === null) unlinkSync(item.destination);
    else atomicWrite(item.destination, item.baseline, item.baselineMode);
  }
}

function completedTransaction(backups, written, backupFiles = [], createdDirectories = []) {
  let active = true;
  return {
    backups: backups.map((entry) => entry.path),
    commit() {
      active = false;
    },
    rollback() {
      if (!active) throw new Error("installer transaction is no longer active");
      const roots = [...new Set(written.map((item) => item.root))];
      const locks = acquireLocks(roots);
      let restored = false;
      try {
        assertBackupsUnchanged(backupFiles);
        restoreWritten(written);
        removeBackupFiles(backupFiles);
        active = false;
        restored = true;
      } finally {
        releaseLocks(locks);
      }
      if (restored) removeEmptyCreatedDirectories(createdDirectories);
    },
  };
}

export function applyPlanTransaction(plan) {
  const changed = plan
    .filter((item) => item.status !== "unchanged")
    .map((item) => ({ ...item }));
  if (!changed.length) return completedTransaction([], []);
  const roots = [...new Set(changed.map((item) => item.root))];
  let locks = [];
  const backups = [];
  const backupFiles = [];
  const createdDirectories = [];
  const written = [];
  try {
    for (const root of roots) {
      const resolvedRoot = resolve(root);
      if (safeRoot(root, "target root") !== resolvedRoot) {
        throw new Error(`refusing unsafe target root: ${root}`);
      }
    }
    for (const item of changed) {
      assertSafeAncestors(item.root, item.destination);
      const current = readSafe(item.destination);
      if (!baselineMatches(item, current)) throw new Error(`destination changed after preview: ${item.destination}`);
      item.mode ??= 0o600;
      item.baselineMode ??= current === null ? null : lstatSync(item.destination).mode & 0o777;
    }
    for (const root of roots) {
      ensureDirectory(root, createdDirectories);
    }
    locks = acquireLocks(roots);
    for (const root of roots) {
      if (changed.some((item) => item.root === root && item.baseline !== null)) {
        const backupRoot = join(root, ".agi-super-team-backups");
        ensureDirectory(backupRoot, createdDirectories);
        const backupPath = mkdtempSync(join(backupRoot, `${new Date().toISOString().replaceAll(":", "")}-`));
        const backupMetadata = lstatSync(backupPath);
        createdDirectories.push({ path: backupPath, dev: backupMetadata.dev, ino: backupMetadata.ino });
        backups.push({ root, path: backupPath });
      }
    }
    for (const item of changed) {
      const current = readSafe(item.destination);
      if (!baselineMatches(item, current)) throw new Error(`destination changed after preview: ${item.destination}`);
      if (item.baseline !== null) {
        const backup = backups.find((entry) => entry.root === item.root);
        const target = join(backup.path, relative(item.root, item.destination));
        ensureDirectory(dirname(target), createdDirectories);
        copyFileSync(item.destination, target);
        chmodSync(target, item.baselineMode);
        backupFiles.push({
          path: target,
          content: item.baseline,
          mode: lstatSync(target).mode & 0o777,
          platform: item.platform,
        });
      }
      ensureDirectory(dirname(item.destination), createdDirectories);
      atomicWrite(item.destination, item.content, item.mode ?? 0o600);
      written.push({
        ...item,
        installedMode: lstatSync(item.destination).mode & 0o777,
      });
    }
  } catch (error) {
    let rollbackError = null;
    try {
      assertBackupsUnchanged(backupFiles);
      restoreWritten(written);
      removeBackupFiles(backupFiles);
    } catch (caught) {
      rollbackError = caught;
    }
    releaseLocks(locks);
    locks = [];
    if (!rollbackError) {
      try {
        removeEmptyCreatedDirectories(createdDirectories);
      } catch (caught) {
        rollbackError = caught;
      }
    }
    if (rollbackError) throw new AggregateError([error, rollbackError], "installation failed and rollback could not complete");
    throw error;
  } finally {
    releaseLocks(locks);
  }
  return completedTransaction(backups, written, backupFiles, createdDirectories);
}

export function applyPlan(plan) {
  const transaction = applyPlanTransaction(plan);
  transaction.commit();
  return transaction.backups;
}

export function doctor(plan, tools) {
  const issues = [];
  for (const item of plan) {
    try {
      const current = readSafe(item.destination);
      if (current === null) issues.push(`missing: ${item.destination}`);
      else if (Buffer.compare(current, item.content) !== 0) issues.push(`drifted: ${item.destination}`);
      else if (!modesEquivalent(
        lstatSync(item.destination).mode,
        item.mode ?? 0o600,
        item.platform,
      )) {
        issues.push(`mode drifted: ${item.destination}`);
      }
    } catch (error) { issues.push(error.message); }
  }
  return {
    ok: issues.length === 0,
    issues,
    tools: tools.map((tool) => ({ id: tool.id, support: tool.support, scope: tool.scope })),
    files: plan.length,
  };
}
