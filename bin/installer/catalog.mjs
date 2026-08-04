import { existsSync, lstatSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { createHash } from "node:crypto";
import { isPhysicalStrictDescendant } from "./path-safety.mjs";


const SAFE_ID = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

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
  const priorityHarnesses = new Set(["claude-code", "codex", "openclaw", "hermes"]);
  for (const tool of adapters.tools) {
    if (!SAFE_ID.test(tool.id || "") || ids.has(tool.id) || !["global", "project"].includes(tool.scope)) {
      throw new Error(`invalid or duplicate CLI adapter: ${tool.id || "<missing>"}`);
    }
    if (!Array.isArray(tool.agentPaths) || !Array.isArray(tool.skillPaths)) {
      throw new Error(`CLI adapter ${tool.id} must declare agentPaths and skillPaths`);
    }
    if (priorityHarnesses.has(tool.id)) {
      if (
        tool.agentMode !== "harness-adapter"
        || tool.runtimeEvidence !== "pending"
        || tool.skillSource !== "canonical-assigned"
        || typeof tool.adapterModule !== "string"
        || typeof tool.connectionPath !== "string"
      ) {
        throw new Error(`priority harness ${tool.id} must declare the external Adapter contract`);
      }
      const adapterPath = resolve(packageRoot, tool.adapterModule);
      const adapterRoot = resolve(packageRoot, "bin", "adapters");
      if (
        tool.adapterModule !== `bin/adapters/${tool.id}.mjs`
        || !isPhysicalStrictDescendant(adapterRoot, adapterPath)
      ) {
        throw new Error(`unsafe ${tool.id} Adapter module: ${tool.adapterModule}`);
      }
      regularFile(adapterPath, `${tool.id} Adapter module`);
    }
    ids.add(tool.id);
  }
  if (!Array.isArray(manifest.agents) || manifest.agents.length !== 14) {
    throw new Error("team manifest must contain exactly 14 canonical agents");
  }
  const agentsRoot = resolve(packageRoot, "agents");
  for (const agent of manifest.agents) {
    const expected = resolve(packageRoot, agent.path);
    if (
      !SAFE_ID.test(agent.id || "")
      || agent.path !== `agents/${agent.id}`
      || !isPhysicalStrictDescendant(agentsRoot, expected)
      || !lstatSync(expected).isDirectory()
    ) {
      throw new Error(`invalid canonical Agent path: ${agent.path}`);
    }
  }
  if (hierarchy.requiredMaxDepth !== 2 || hierarchy.executionPolicy !== "wave" || !hierarchy.managers) {
    throw new Error("Agent hierarchy must define depth-2 wave execution");
  }
  const sourceByRole = new Map(sourceLock.entries.map((entry) => {
    if (
      !SAFE_ID.test(entry.manager || "")
      || !SAFE_ID.test(entry.id || "")
      || entry.vendoredPath !== `agents/${entry.manager}/subagents/${entry.id}/AGENTS.md`
    ) {
      throw new Error(`invalid Agent source lock path: ${entry.vendoredPath}`);
    }
    return [`${entry.manager}/${entry.id}`, entry];
  }));
  const specialistGroups = {};
  for (const [manager, settings] of Object.entries(hierarchy.managers)) {
    if (!SAFE_ID.test(manager) || settings.routingFile !== `config/${manager}-specialists.json`) {
      throw new Error(`invalid manager routing path: ${manager}`);
    }
    const routePath = resolve(packageRoot, settings.routingFile);
    if (!isPhysicalStrictDescendant(resolve(packageRoot, "config"), routePath)) {
      throw new Error(`unsafe routing file: ${settings.routingFile}`);
    }
    const registry = readJson(routePath, `${manager} specialist routing`);
    if (registry.parent !== manager || registry.requiredMaxDepth !== 2 || registry.maxConcurrentLeaves !== 2) {
      throw new Error(`invalid specialist routing contract: ${manager}`);
    }
    const ids = registry.specialists.map((item) => item.id);
    if (ids.some((id) => !SAFE_ID.test(id || ""))) throw new Error(`invalid specialist id for manager: ${manager}`);
    if (new Set(ids).size !== ids.length || JSON.stringify(ids) !== JSON.stringify(settings.subagents)) {
      throw new Error(`hierarchy and routing order differ for manager: ${manager}`);
    }
    const specialists = registry.specialists.map((specialist) => {
      const source = sourceByRole.get(`${manager}/${specialist.id}`);
      if (!source || source.sourcePath !== specialist.sourcePath) throw new Error(`missing source lock: ${manager}/${specialist.id}`);
      const vendored = resolve(packageRoot, source.vendoredPath);
      const expectedRoot = resolve(packageRoot, "agents", manager, "subagents");
      if (
        !isPhysicalStrictDescendant(agentsRoot, vendored)
        || !isPhysicalStrictDescendant(expectedRoot, vendored)
      ) {
        throw new Error(`unsafe vendored path: ${source.vendoredPath}`);
      }
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
  const curatedSkillsRoot = join(packageRoot, "plugins", "agi-super-team-codex", "skills");
  const curatedSkills = readdirSync(curatedSkillsRoot)
    .filter((name) => statSync(join(curatedSkillsRoot, name)).isDirectory())
    .sort();
  if (curatedSkills.length !== 6) throw new Error("Codex plugin must contain exactly 6 curated Skills");

  const canonicalSkillsRoot = join(packageRoot, "skills");
  const physicalSkills = new Set(
    readdirSync(canonicalSkillsRoot)
      .filter((name) => {
        const root = join(canonicalSkillsRoot, name);
        return !lstatSync(root).isSymbolicLink()
          && statSync(root).isDirectory()
          && existsSync(join(root, "SKILL.md"));
      }),
  );
  const byAgent = {};
  for (const agent of manifest.agents) {
    const selected = new Set();
    for (const tier of ["required", "optional", "harnessSpecific"]) {
      for (const skill of agent.skills?.[tier] || []) {
        if (physicalSkills.has(skill)) selected.add(skill);
      }
    }
    byAgent[agent.id] = [...selected].sort();
  }
  const assignedSkills = {
    byAgent,
    all: [...new Set(Object.values(byAgent).flat())].sort(),
  };
  return {
    tools: adapters.tools,
    agents: manifest.agents,
    kits: manifest.kits,
    hierarchy,
    specialistGroups,
    skills: curatedSkills,
    skillsRoot: curatedSkillsRoot,
    curatedSkills,
    curatedSkillsRoot,
    canonicalSkillsRoot,
    assignedSkills,
  };
}

export function selectTools(catalog, requested, allTools) {
  const byId = new Map(catalog.tools.map((tool) => [tool.id, tool]));
  const ids = allTools ? catalog.tools.map((tool) => tool.id) : requested.length ? requested : ["codex"];
  const unknown = [...new Set(ids)].filter((id) => !byId.has(id));
  if (unknown.length) throw new Error(`unknown tool: ${unknown.join(", ")}`);
  return [...new Set(ids)].map((id) => byId.get(id));
}
