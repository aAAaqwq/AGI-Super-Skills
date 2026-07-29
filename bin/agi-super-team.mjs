#!/usr/bin/env node

import { spawnSync } from "node:child_process";
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
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { homedir, platform } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const PACKAGE_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const PLUGIN_ROOT = join(PACKAGE_ROOT, "plugins", "agi-super-team-codex");
const AGENT_PAYLOAD = join(PLUGIN_ROOT, "payload", "agents");
const GLOBAL_PAYLOAD = join(PLUGIN_ROOT, "payload", "global", "AGENTS.md");
const TEAM_CONTRACTS = join(
  PLUGIN_ROOT,
  "skills",
  "c-suite-team",
  "references",
  "team-contracts.json",
);
const BEGIN_MARKER = "<!-- AGI-SUPER-TEAM:CEO:BEGIN -->";
const END_MARKER = "<!-- AGI-SUPER-TEAM:CEO:END -->";
const MARKETPLACE = "agi-super-team";
const PLUGIN = "agi-super-team-codex@agi-super-team";

function usage() {
  console.log(`AGI Super Team — one-command Codex installer

Usage:
  npx -y agi-super-team [options]
  npx -y github:aAAaqwq/AGI-Super-Team [options]

Default: preview plugin + global Musk CEO + all eight outcome Teams.

Options:
  --install              Apply the previewed installation
  --team <id>            Install one Team (repeatable)
  --all-teams            Install all eight outcome Teams (default)
  --all-agents           Install all 44 bundled Agent TOMLs
  --no-global-ceo        Do not inject the global Musk CEO
  --skip-plugin          Do not install or update the Codex plugin
  --codex-home <path>    Override CODEX_HOME / ~/.codex
  --list                 List available Teams
  --help                 Show this help

Examples:
  npx -y github:aAAaqwq/AGI-Super-Team
  npx -y github:aAAaqwq/AGI-Super-Team --install
  npx -y github:aAAaqwq/AGI-Super-Team --team solo-founder --install
  npx -y github:aAAaqwq/AGI-Super-Team --all-agents --install`);
}

function parseArgs(argv) {
  const options = {
    install: false,
    teams: [],
    allTeams: true,
    allAgents: false,
    globalCeo: true,
    plugin: true,
    codexHome: process.env.CODEX_HOME || join(homedir(), ".codex"),
    list: false,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--install") options.install = true;
    else if (argument === "--all-teams") options.allTeams = true;
    else if (argument === "--all-agents") options.allAgents = true;
    else if (argument === "--no-global-ceo") options.globalCeo = false;
    else if (argument === "--skip-plugin") options.plugin = false;
    else if (argument === "--list") options.list = true;
    else if (argument === "--help" || argument === "-h") {
      usage();
      process.exit(0);
    } else if (argument === "--team") {
      const value = argv[index + 1];
      if (!value || value.startsWith("--")) throw new Error("--team requires an ID");
      options.teams.push(value);
      options.allTeams = false;
      index += 1;
    } else if (argument === "--codex-home") {
      const value = argv[index + 1];
      if (!value || value.startsWith("--")) throw new Error("--codex-home requires a path");
      options.codexHome = value;
      index += 1;
    } else {
      throw new Error(`unknown option: ${argument}`);
    }
  }
  return options;
}

function assertRegularFile(path, label) {
  if (!existsSync(path) || lstatSync(path).isSymbolicLink() || !statSync(path).isFile()) {
    throw new Error(`invalid ${label}: ${path}`);
  }
}

function loadContracts() {
  assertRegularFile(TEAM_CONTRACTS, "Team contracts");
  const contracts = JSON.parse(readFileSync(TEAM_CONTRACTS, "utf8"));
  if (!Array.isArray(contracts.kits) || !Array.isArray(contracts.agents)) {
    throw new Error("Team contracts must contain kits and agents");
  }
  return contracts;
}

function listTeams(contracts) {
  console.log("AGI Super Team outcome Teams");
  for (const team of contracts.kits) {
    console.log(`  ${team.id.padEnd(20)} ${team.name} — ${team.agents.join(", ")}`);
  }
}

function validateCodexHome(input) {
  const path = resolve(input);
  if (path === resolve("/") || path === resolve(homedir())) {
    throw new Error(`refusing unsafe Codex home: ${path}`);
  }
  if (existsSync(path) && (lstatSync(path).isSymbolicLink() || !statSync(path).isDirectory())) {
    throw new Error(`invalid Codex home: ${path}`);
  }
  return path;
}

function readSafe(path) {
  if (!existsSync(path)) return null;
  const metadata = lstatSync(path);
  if (metadata.isSymbolicLink() || !metadata.isFile()) {
    throw new Error(`refusing unsafe destination: ${path}`);
  }
  return readFileSync(path);
}

function atomicWrite(path, content) {
  mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  if (existsSync(path) && lstatSync(path).isSymbolicLink()) {
    throw new Error(`refusing symlinked destination: ${path}`);
  }
  const temporary = join(dirname(path), `.${dirname(path).length}.${process.pid}.${Date.now()}.tmp`);
  const descriptor = openSync(temporary, "wx", 0o600);
  try {
    writeFileSync(descriptor, content);
  } finally {
    closeSync(descriptor);
  }
  chmodSync(temporary, 0o600);
  renameSync(temporary, path);
}

function renderGlobal(existing) {
  assertRegularFile(GLOBAL_PAYLOAD, "global CEO payload");
  const managed = readFileSync(GLOBAL_PAYLOAD, "utf8").trim();
  if (
    managed.split(BEGIN_MARKER).length !== 2 ||
    managed.split(END_MARKER).length !== 2
  ) {
    throw new Error("global CEO payload has invalid managed markers");
  }
  if (existing === null) return Buffer.from(`${managed}\n`);
  const current = existing.toString("utf8");
  const beginCount = current.split(BEGIN_MARKER).length - 1;
  const endCount = current.split(END_MARKER).length - 1;
  if (beginCount === 0 && endCount === 0) {
    const prefix = current.trimEnd();
    return Buffer.from(`${prefix ? `${prefix}\n\n` : ""}${managed}\n`);
  }
  if (beginCount !== 1 || endCount !== 1) {
    throw new Error("existing AGENTS.md has malformed AGI Super Team markers");
  }
  const start = current.indexOf(BEGIN_MARKER);
  const finishMarker = current.indexOf(END_MARKER, start);
  if (finishMarker < start) throw new Error("existing AGENTS.md has reversed managed markers");
  const finish = finishMarker + END_MARKER.length;
  return Buffer.from(`${current.slice(0, start)}${managed}${current.slice(finish)}`);
}

function selectAgentNames(contracts, options) {
  if (options.allAgents) {
    return readdirSync(AGENT_PAYLOAD)
      .filter((name) => name.endsWith(".toml"))
      .map((name) => name.slice(0, -5))
      .sort();
  }
  const teams = new Map(contracts.kits.map((team) => [team.id, team]));
  const selectedIds = options.allTeams ? [...teams.keys()] : options.teams;
  const unknown = selectedIds.filter((id) => !teams.has(id));
  if (unknown.length) throw new Error(`unknown Team: ${unknown.join(", ")}`);
  const roles = new Set();
  for (const id of selectedIds) {
    for (const role of teams.get(id).agents) if (role !== "ceo") roles.add(role);
  }
  return [...roles].map((role) => `ast-${role}`).sort();
}

function buildPlan(contracts, options, codexHome) {
  const plan = [];
  if (options.globalCeo) {
    const destination = join(codexHome, "AGENTS.md");
    const baseline = readSafe(destination);
    plan.push({ label: "global-ceo", destination, baseline, content: renderGlobal(baseline) });
  }
  for (const name of selectAgentNames(contracts, options)) {
    const source = join(AGENT_PAYLOAD, `${name}.toml`);
    assertRegularFile(source, `Agent payload ${name}`);
    const destination = join(codexHome, "agents", `${name}.toml`);
    plan.push({ label: name, destination, baseline: readSafe(destination), content: readFileSync(source) });
  }
  return plan.map((item) => ({
    ...item,
    status:
      item.baseline === null
        ? "add"
        : Buffer.compare(item.baseline, item.content) === 0
          ? "unchanged"
          : "update",
  }));
}

function resolveCodex() {
  const candidates = [
    process.env.CODEX_CLI,
    "codex",
    join(homedir(), ".local", "bin", "codex"),
    platform() === "darwin" ? "/Applications/ChatGPT.app/Contents/Resources/codex" : null,
  ].filter(Boolean);
  for (const candidate of candidates) {
    const result = spawnSync(candidate, ["--version"], { encoding: "utf8" });
    if (result.status === 0) return candidate;
  }
  throw new Error("Codex CLI not found; install Codex or pass --skip-plugin");
}

function installPlugin() {
  const codex = resolveCodex();
  const commands = [
    ["plugin", "marketplace", "add", "aAAaqwq/AGI-Super-Team", "--ref", "main"],
    ["plugin", "add", PLUGIN],
  ];
  for (const arguments_ of commands) {
    const result = spawnSync(codex, arguments_, { stdio: "inherit" });
    if (result.status !== 0) throw new Error(`Codex command failed: ${arguments_.join(" ")}`);
  }
}

function applyPlan(plan, codexHome) {
  const changed = plan.filter((item) => item.status !== "unchanged");
  if (!changed.length) return null;
  const agentsDirectory = join(codexHome, "agents");
  mkdirSync(agentsDirectory, { recursive: true, mode: 0o700 });
  const lock = join(agentsDirectory, ".agi-super-team-npx.lock");
  const lockDescriptor = openSync(lock, "wx", 0o600);
  const updated = changed.some((item) => item.baseline !== null);
  let backup = null;
  if (updated) {
    const backupRoot = join(codexHome, "backups", "agi-super-team");
    mkdirSync(backupRoot, { recursive: true, mode: 0o700 });
    const timestamp = new Date().toISOString().replaceAll(":", "");
    backup = mkdtempSync(join(backupRoot, `${timestamp}-`));
  }
  const written = [];
  try {
    for (const item of changed) {
      const current = readSafe(item.destination);
      const unchanged =
        current === null ? item.baseline === null : item.baseline !== null && Buffer.compare(current, item.baseline) === 0;
      if (!unchanged) throw new Error(`destination changed after preview: ${item.destination}`);
      if (backup && item.baseline !== null) {
        const backupPath = join(backup, relative(codexHome, item.destination));
        mkdirSync(dirname(backupPath), { recursive: true, mode: 0o700 });
        copyFileSync(item.destination, backupPath);
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
    closeSync(lockDescriptor);
    if (existsSync(lock)) unlinkSync(lock);
  }
  return backup;
}

function printPlan(plan, options, codexHome) {
  const counts = Object.fromEntries(
    ["add", "update", "unchanged"].map((status) => [status, plan.filter((item) => item.status === status).length]),
  );
  console.log(`AGI Super Team — ${options.install ? "INSTALL" : "PREVIEW"}`);
  console.log(`Codex home: ${codexHome}`);
  console.log(`Plugin: ${options.plugin ? `${PLUGIN} (${options.install ? "ensure installed" : "would install/update"})` : "skipped"}`);
  console.log(`Files: add=${counts.add} update=${counts.update} unchanged=${counts.unchanged}`);
  for (const item of plan) {
    if (item.status !== "unchanged") console.log(`  ${item.status.padEnd(6)} ${item.label.padEnd(20)} ${item.destination}`);
  }
}

function main() {
  try {
    const options = parseArgs(process.argv.slice(2));
    const contracts = loadContracts();
    if (options.list) {
      listTeams(contracts);
      return;
    }
    const codexHome = validateCodexHome(options.codexHome);
    const plan = buildPlan(contracts, options, codexHome);
    printPlan(plan, options, codexHome);
    if (!options.install) {
      console.log("\nPreview only. Add --install to apply.");
      return;
    }
    if (options.plugin) installPlugin();
    mkdirSync(codexHome, { recursive: true, mode: 0o700 });
    const backup = applyPlan(plan, codexHome);
    if (backup) console.log(`Backup: ${backup}`);
    console.log("\nInstalled. Start a new Codex task to load the CEO, Skills, and Agents.");
  } catch (error) {
    console.error(`error: ${error.message}`);
    process.exitCode = 2;
  }
}

main();
