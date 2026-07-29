import { existsSync, lstatSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

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
  const adapters = readJson(adaptersPath, "CLI adapter manifest");
  const manifest = readJson(manifestPath, "team manifest");
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
  const skillsRoot = join(packageRoot, "plugins", "agi-super-team-codex", "skills");
  const skills = readdirSync(skillsRoot)
    .filter((name) => statSync(join(skillsRoot, name)).isDirectory())
    .sort();
  if (skills.length !== 6) throw new Error("Codex plugin must contain exactly 6 curated Skills");
  return { tools: adapters.tools, agents: manifest.agents, kits: manifest.kits, skills, skillsRoot };
}

export function selectTools(catalog, requested, allTools) {
  const byId = new Map(catalog.tools.map((tool) => [tool.id, tool]));
  const ids = allTools ? catalog.tools.map((tool) => tool.id) : requested.length ? requested : ["codex"];
  const unknown = [...new Set(ids)].filter((id) => !byId.has(id));
  if (unknown.length) throw new Error(`unknown tool: ${unknown.join(", ")}`);
  return [...new Set(ids)].map((id) => byId.get(id));
}
