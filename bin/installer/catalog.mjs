import { existsSync, lstatSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { createHash } from "node:crypto";

function regularFile(path, label) {
  if (!existsSync(path) || lstatSync(path).isSymbolicLink() || !statSync(path).isFile()) {
    throw new Error(`invalid ${label}: ${path}`);
  }
}

function readJson(path, label) {
  regularFile(path, label);
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (error) {
    throw new Error(`invalid ${label}: ${error.message}`);
  }
}

export function loadCatalog(packageRoot) {
  const adaptersPath = join(packageRoot, "config", "cli-adapters.json");
  const manifestPath = join(packageRoot, "config", "team-manifest.json");
  const hierarchyPath = join(packageRoot, "config", "agent-hierarchy.json");
  const sourcesPath = join(packageRoot, "config", "agent-sources.lock.json");
  const adapters = readJson(adaptersPath, "CLI adapter manifest");
  const manifest = readJson(manifestPath, "team manifest");
  const hierarchy = readJson(hierarchyPath, "agent hierarchy");
  const sourceLock = readJson(sourcesPath, "Agent source lock");
  if (adapters.schemaVersion !== 1 || !Array.isArray(adapters.tools) || adapters.tools.length !== 18) {
    throw new Error("CLI adapter manifest must contain exactly 18 tools");
  }
  const ids = new Set();
  for (const tool of adapters.tools) {
    if (!tool.id || ids.has(tool.id) || !["global", "project"].includes(tool.scope)) {
      throw new Error(`invalid or duplicate CLI adapter: ${tool.id || "<missing>"}`);
    }
    if (!Array.isArray(tool.agentPaths) || !Array.isArray(tool.skillPaths)) {
      throw new Error(`CLI adapter ${tool.id} must declare agentPaths and skillPaths`);
    }
    ids.add(tool.id);
  }
  if (!Array.isArray(manifest.agents) || manifest.agents.length !== 14) {
    throw new Error("team manifest must contain exactly 14 canonical agents");
  }
  for (const agent of manifest.agents) {
    const expected = resolve(packageRoot, agent.path);
    if (!expected.startsWith(`${resolve(packageRoot, "agents")}/`) || !statSync(expected).isDirectory()) {
      throw new Error(`invalid canonical Agent path: ${agent.path}`);
    }
  }
  if (hierarchy.requiredMaxDepth !== 2 || hierarchy.executionPolicy !== "wave" || !hierarchy.managers) {
    throw new Error("Agent hierarchy must define depth-2 wave execution");
  }
  const sourceByRole = new Map(sourceLock.entries.map((entry) => [`${entry.manager}/${entry.id}`, entry]));
  const specialistGroups = {};
  for (const [manager, settings] of Object.entries(hierarchy.managers)) {
    const routePath = resolve(packageRoot, settings.routingFile);
    if (!routePath.startsWith(`${resolve(packageRoot, "config")}/`)) throw new Error(`unsafe routing file: ${settings.routingFile}`);
    const registry = readJson(routePath, `${manager} specialist routing`);
    if (registry.parent !== manager || registry.requiredMaxDepth !== 2 || registry.maxConcurrentLeaves !== 2) {
      throw new Error(`invalid specialist routing contract: ${manager}`);
    }
    const ids = registry.specialists.map((item) => item.id);
    if (new Set(ids).size !== ids.length || JSON.stringify(ids) !== JSON.stringify(settings.subagents)) {
      throw new Error(`hierarchy and routing order differ for manager: ${manager}`);
    }
    const specialists = registry.specialists.map((specialist) => {
      const source = sourceByRole.get(`${manager}/${specialist.id}`);
      if (!source || source.sourcePath !== specialist.sourcePath) throw new Error(`missing source lock: ${manager}/${specialist.id}`);
      const vendored = resolve(packageRoot, source.vendoredPath);
      const expectedRoot = resolve(packageRoot, "agents", manager, "subagents");
      if (!vendored.startsWith(`${expectedRoot}/`)) throw new Error(`unsafe vendored path: ${source.vendoredPath}`);
      regularFile(vendored, "vendored subagent");
      const digest = createHash("sha256").update(readFileSync(vendored)).digest("hex");
      if (digest !== source.sha256) throw new Error(`vendored subagent drift: ${manager}/${specialist.id}`);
      return { ...specialist, manager, vendoredPath: source.vendoredPath, sourceSha256: source.sha256 };
    });
    specialistGroups[manager] = { manager, roleRoutes: registry.roleRoutes, specialists };
  }
  if (sourceByRole.size !== Object.values(specialistGroups).reduce((count, group) => count + group.specialists.length, 0)) {
    throw new Error("Agent source lock contains an unreferenced or missing specialist");
  }
  const skillsRoot = join(packageRoot, "plugins", "agi-super-team-codex", "skills");
  const skills = readdirSync(skillsRoot)
    .filter((name) => statSync(join(skillsRoot, name)).isDirectory())
    .sort();
  if (skills.length !== 6) throw new Error("Codex plugin must contain exactly 6 curated Skills");
  return { tools: adapters.tools, agents: manifest.agents, kits: manifest.kits, hierarchy, specialistGroups, skills, skillsRoot };
}

export function selectTools(catalog, requested, allTools) {
  const byId = new Map(catalog.tools.map((tool) => [tool.id, tool]));
  const ids = allTools ? catalog.tools.map((tool) => tool.id) : requested.length ? requested : ["codex"];
  const unknown = [...new Set(ids)].filter((id) => !byId.has(id));
  if (unknown.length) throw new Error(`unknown tool: ${unknown.join(", ")}`);
  return [...new Set(ids)].map((id) => byId.get(id));
}
