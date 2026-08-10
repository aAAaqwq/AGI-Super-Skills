import { spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, delimiter, dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const cli = resolve(process.argv[2] || join(repositoryRoot, "bin", "agi-super-team.mjs"));
const sourceModule = extname(cli) === ".mjs";
const sandbox = mkdtempSync(join(tmpdir(), "agi-super-team-windows-smoke-"));

function isolatedEnvironment(home, extra = {}) {
  const environment = {};
  for (const name of [
    "PATH", "PATHEXT", "SystemRoot", "ComSpec", "WINDIR",
    "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "NO_COLOR", "CI",
  ]) {
    if (process.env[name] !== undefined) environment[name] = process.env[name];
  }
  environment.HOME = home;
  environment.USERPROFILE = home;
  environment.CODEX_HOME = join(home, ".codex");
  environment.NO_COLOR = "1";
  return {...environment, ...extra};
}

function invoke(label, args, home, extraEnvironment = {}) {
  const command = sourceModule ? process.execPath : cli;
  const commandArgs = sourceModule ? [cli, ...args] : args;
  const result = spawnSync(command, commandArgs, {
    cwd: sandbox,
    encoding: "utf8",
    env: isolatedEnvironment(home, extraEnvironment),
    maxBuffer: 64 * 1024 * 1024,
    shell: process.platform === "win32" && !sourceModule,
  });
  if (result.status !== 0) {
    throw new Error(`${label} failed (${result.status}):\n${result.stdout}\n${result.stderr}`);
  }
  return result.stdout;
}

function tree(root) {
  if (!existsSync(root)) return [];
  const entries = [];
  function visit(path, relative = "") {
    for (const item of readdirSync(path, { withFileTypes: true })) {
      const itemRelative = join(relative, item.name);
      entries.push(`${item.isDirectory() ? "d" : "f"}:${itemRelative}`);
      if (item.isDirectory()) visit(join(path, item.name), itemRelative);
    }
  }
  visit(root);
  return entries.sort();
}

function expectIncludes(output, expected, label) {
  if (!output.includes(expected)) {
    throw new Error(`${label} did not include ${JSON.stringify(expected)}:\n${output.slice(0, 4000)}`);
  }
}

function expectNonEmptyFile(path, label) {
  if (!existsSync(path) || !statSync(path).isFile() || statSync(path).size === 0) {
    throw new Error(`${label} was not created as a non-empty file: ${path}`);
  }
}

function roots(name) {
  return {
    home: join(sandbox, name, "home"),
    project: join(sandbox, name, "project"),
  };
}

try {
  const listHome = join(sandbox, "list-home");
  const listed = invoke("--list-tools", ["--list-tools"], listHome);
  expectIncludes(listed, "AGI Super Team CLI targets (18)", "--list-tools");
  const listedTools = listed.split(/\r?\n/)
    .map((line) => /^\s{2}(\S+)\s+(?:global|project)\s+/.exec(line)?.[1])
    .filter(Boolean);
  if (listedTools.length !== 18 || new Set(listedTools).size !== 18) {
    throw new Error(`--list-tools returned ${listedTools.length} rows (${new Set(listedTools).size} unique)`);
  }
  for (const tool of ["claude-code", "codex", "openclaw", "hermes"]) {
    if (!listedTools.includes(tool)) throw new Error(`--list-tools omitted ${tool}`);
  }

  const preview = roots("claude-preview");
  const previewParent = dirname(preview.home);
  const beforePreview = tree(previewParent);
  const previewed = invoke("claude-code preview", [
    "--tool", "claude-code", "--home", preview.home,
    "--project-dir", preview.project, "--skip-plugin",
  ], preview.home);
  expectIncludes(previewed, "AGI Super Team — PREVIEW", "claude-code preview");
  expectIncludes(previewed, "Tools: claude-code", "claude-code preview");
  expectIncludes(previewed, "Preview only. Add --install to apply.", "claude-code preview");
  const afterPreview = tree(previewParent);
  if (JSON.stringify(afterPreview) !== JSON.stringify(beforePreview)) {
    throw new Error(`claude-code preview mutated its isolated roots: ${afterPreview.join(", ")}`);
  }

  const installed = roots("claude-install");
  const installOutput = invoke("claude-code install/connect", [
    "--tool", "claude-code", "--home", installed.home,
    "--project-dir", installed.project, "--skip-plugin", "--no-skills", "--install", "--connect",
  ], installed.home);
  expectIncludes(installOutput, "Connected: claude-code (filesystem-connected)", "claude-code install/connect");
  expectIncludes(installOutput, "Installed. Restart the selected CLI", "claude-code install/connect");
  const claudeRoot = join(installed.home, ".claude");
  expectNonEmptyFile(join(claudeRoot, "agents", "ast-ceo.md"), "installed CEO Agent");
  expectNonEmptyFile(join(claudeRoot, "agi-super-team", "connection.json"), "connection spec");
  const receiptPath = join(claudeRoot, "agi-super-team", "receipt.json");
  expectNonEmptyFile(receiptPath, "connection receipt");
  const receipt = JSON.parse(readFileSync(receiptPath, "utf8"));
  for (const [field, expected] of Object.entries({
    harness: "claude-code",
    status: "filesystem-connected",
    runtimeEvidence: "pending",
  })) {
    if (receipt[field] !== expected) {
      throw new Error(`connection receipt ${field} was ${JSON.stringify(receipt[field])}, expected ${JSON.stringify(expected)}`);
    }
  }

  const doctorOutput = invoke("claude-code doctor", [
    "--tool", "claude-code", "--home", installed.home,
    "--project-dir", installed.project, "--skip-plugin", "--no-skills", "--doctor",
  ], installed.home);
  expectIncludes(doctorOutput, "AGI Super Team doctor: FILES_HEALTHY", "claude-code doctor");
  expectIncludes(doctorOutput, "0 issues", "claude-code doctor");

  invoke("claude-code repeat install/connect", [
    "--tool", "claude-code", "--home", installed.home,
    "--project-dir", installed.project, "--skip-plugin", "--no-skills", "--install", "--connect",
  ], installed.home);

  const fakeBin = join(sandbox, "fake-bin");
  mkdirSync(fakeBin, {recursive: true});
  const fakePath = `${fakeBin}${delimiter}${process.env.PATH || ""}`;
  const codex = roots("codex-plugin");
  const codexLog = join(sandbox, "fake-codex.log");
  const fakeCodex = join(fakeBin, process.platform === "win32" ? "codex.cmd" : "codex");
  if (process.platform === "win32") {
    writeFileSync(fakeCodex, "@echo off\r\necho %*>>\"%FAKE_CODEX_LOG%\"\r\nexit /b 0\r\n");
  } else {
    writeFileSync(fakeCodex, "#!/bin/sh\nprintf '%s\\n' \"$*\" >> \"$FAKE_CODEX_LOG\"\n");
    chmodSync(fakeCodex, 0o755);
  }
  const codexOutput = invoke("codex install with plugin", [
    "--tool", "codex", "--home", codex.home,
    "--project-dir", codex.project, "--no-skills", "--plugin", "--install", "--connect",
  ], codex.home, {
    PATH: fakePath,
    FAKE_CODEX_LOG: codexLog,
  });
  expectIncludes(codexOutput, "Installed. Restart the selected CLI", "codex install with plugin");
  expectIncludes(codexOutput, "Connected: codex (filesystem-connected)", "codex install with plugin");
  const codexCalls = readFileSync(codexLog, "utf8").split(/\r?\n/).filter(Boolean);
  for (const expected of [
    "--version",
    "plugin marketplace add aAAaqwq/AGI-Super-Team --ref v1.4.2",
    "plugin marketplace upgrade agi-super-team",
    "plugin add agi-super-team-codex@agi-super-team",
  ]) {
    if (!codexCalls.includes(expected)) throw new Error(`fake Codex did not receive ${JSON.stringify(expected)}: ${codexCalls.join(" | ")}`);
  }
  expectNonEmptyFile(join(codex.home, ".codex", "agents", "ast-cto.toml"), "Codex Agent");
  expectNonEmptyFile(join(codex.home, ".codex", "agi-super-team", "connection.json"), "Codex connection");
  expectNonEmptyFile(join(codex.home, ".codex", "agi-super-team", "receipt.json"), "Codex receipt");
  const codexDoctor = invoke("codex doctor", [
    "--tool", "codex", "--home", codex.home,
    "--project-dir", codex.project, "--no-skills", "--doctor",
  ], codex.home, {PATH: fakePath, FAKE_CODEX_LOG: codexLog});
  expectIncludes(codexDoctor, "FILES_HEALTHY", "codex doctor");
  invoke("codex repeat install/connect", [
    "--tool", "codex", "--home", codex.home,
    "--project-dir", codex.project, "--no-skills", "--plugin", "--install", "--connect",
  ], codex.home, {PATH: fakePath, FAKE_CODEX_LOG: codexLog});

  const fakeOpenClawRunner = join(fakeBin, "fake-openclaw.mjs");
  writeFileSync(fakeOpenClawRunner, `
import {existsSync, mkdirSync, readFileSync, writeFileSync} from "node:fs";
import {dirname, join} from "node:path";
const args = process.argv.slice(2);
const config = process.env.OPENCLAW_CONFIG_PATH || join(process.env.OPENCLAW_STATE_DIR, "openclaw.json");
if (args.length === 1 && args[0] === "--version") {
  console.log("openclaw-smoke");
} else if (args.join(" ") === "config get agents.list --json") {
  if (!existsSync(config)) {
    console.error("Config path not found: agents.list");
    process.exit(1);
  }
  const current = JSON.parse(readFileSync(config, "utf8"));
  console.log(JSON.stringify(current.agents?.list || []));
} else if (args[0] === "config" && args[1] === "patch") {
  const input = readFileSync(0, "utf8");
  JSON.parse(input);
  if (!args.includes("--dry-run")) {
    mkdirSync(dirname(config), {recursive: true});
    writeFileSync(config, input);
  }
  console.log("{}");
} else if (args.join(" ") === "config validate --json") {
  JSON.parse(readFileSync(config, "utf8"));
  console.log("{}");
} else {
  console.error("unexpected fake OpenClaw command: " + args.join(" "));
  process.exit(64);
}
`);
  const fakeOpenClaw = join(fakeBin, process.platform === "win32" ? "openclaw.cmd" : "openclaw");
  if (process.platform === "win32") {
    writeFileSync(fakeOpenClaw, `@echo off\r\n"${process.execPath}" "%~dp0fake-openclaw.mjs" %*\r\nexit /b %errorlevel%\r\n`);
  } else {
    writeFileSync(fakeOpenClaw, `#!/bin/sh\nexec "${process.execPath}" "${fakeOpenClawRunner}" "$@"\n`);
    chmodSync(fakeOpenClaw, 0o755);
  }

  const openclawInstalled = roots("openclaw-install");
  const openclawEnvironment = {PATH: fakePath};
  const openclawInstall = invoke("openclaw install/connect", [
    "--tool", "openclaw", "--home", openclawInstalled.home,
    "--project-dir", openclawInstalled.project, "--no-skills", "--install", "--connect",
  ], openclawInstalled.home, openclawEnvironment);
  expectIncludes(openclawInstall, "Connected: openclaw (connected-structural)", "openclaw install/connect");
  expectNonEmptyFile(join(openclawInstalled.home, ".openclaw", "agency-agents", "agi-super-team", "ast-ceo", "AGENTS.md"), "OpenClaw CEO Agent");
  expectNonEmptyFile(join(openclawInstalled.home, ".openclaw", "agi-super-team", "connection.json"), "OpenClaw connection");
  expectNonEmptyFile(join(openclawInstalled.home, ".openclaw", "agi-super-team", "receipt.json"), "OpenClaw receipt");
  const openclawDoctor = invoke("openclaw doctor", [
    "--tool", "openclaw", "--home", openclawInstalled.home,
    "--project-dir", openclawInstalled.project, "--no-skills", "--doctor",
  ], openclawInstalled.home, openclawEnvironment);
  expectIncludes(openclawDoctor, "FILES_HEALTHY", "openclaw doctor");
  invoke("openclaw repeat install/connect", [
    "--tool", "openclaw", "--home", openclawInstalled.home,
    "--project-dir", openclawInstalled.project, "--no-skills", "--install", "--connect",
  ], openclawInstalled.home, openclawEnvironment);

  const openclawOverride = roots("openclaw-override");
  const openclawOverrideHome = join(sandbox, "openclaw-native-home");
  const openclawOverrideState = join(sandbox, "openclaw-native-state");
  const openclawOverrideConfig = join(sandbox, "openclaw-native-config", "custom.json");
  const openclawOverrideEnvironment = {
    PATH: fakePath,
    OPENCLAW_HOME: openclawOverrideHome,
    OPENCLAW_STATE_DIR: openclawOverrideState,
    OPENCLAW_CONFIG_PATH: openclawOverrideConfig,
  };
  const openclawOverrideOutput = invoke("openclaw native root overrides", [
    "--tool", "openclaw", "--project-dir", openclawOverride.project,
    "--no-skills", "--install", "--connect",
  ], openclawOverride.home, openclawOverrideEnvironment);
  expectIncludes(openclawOverrideOutput, "Connected: openclaw (connected-structural)", "openclaw native root overrides");
  expectNonEmptyFile(join(openclawOverrideState, "agency-agents", "agi-super-team", "ast-ceo", "AGENTS.md"), "OpenClaw override CEO Agent");
  expectNonEmptyFile(join(openclawOverrideState, "agi-super-team", "connection.json"), "OpenClaw override connection");
  expectNonEmptyFile(join(openclawOverrideState, "agi-super-team", "receipt.json"), "OpenClaw override receipt");
  expectNonEmptyFile(openclawOverrideConfig, "OpenClaw override config");
  if (existsSync(join(openclawOverride.home, ".openclaw"))) {
    throw new Error("OpenClaw native root overrides created a dead directory under OS home");
  }

  const openclaw = roots("openclaw-subagents");
  const openclawOutput = invoke("openclaw --all-subagents preview", [
    "--tool", "openclaw", "--home", openclaw.home,
    "--project-dir", openclaw.project, "--skip-plugin", "--all-subagents",
  ], openclaw.home);
  expectIncludes(openclawOutput, "AGI Super Team — PREVIEW", "openclaw --all-subagents preview");
  expectIncludes(openclawOutput, "Tools: openclaw", "openclaw --all-subagents preview");
  expectIncludes(openclawOutput, "Preview only. Add --install to apply.", "openclaw --all-subagents preview");
  if (tree(dirname(openclaw.home)).length !== 0) throw new Error("openclaw preview mutated its isolated roots");

  const hermes = roots("hermes-install");
  const hermesInstall = invoke("hermes install/connect", [
    "--tool", "hermes", "--home", hermes.home,
    "--project-dir", hermes.project, "--no-skills", "--install", "--connect",
  ], hermes.home);
  expectIncludes(hermesInstall, "Connected: hermes (filesystem-connected)", "hermes install/connect");
  const hermesRuntimeHome = process.platform === "win32"
    ? join(hermes.home, "AppData", "Local", "hermes")
    : join(hermes.home, ".hermes");
  expectNonEmptyFile(join(hermesRuntimeHome, "skills", "agi-super-team-agents", "ast-ceo", "SKILL.md"), "Hermes CEO Agent");
  expectNonEmptyFile(join(hermesRuntimeHome, "agi-super-team", "connection.json"), "Hermes connection");
  expectNonEmptyFile(join(hermesRuntimeHome, "agi-super-team", "receipt.json"), "Hermes receipt");
  const hermesDoctor = invoke("hermes doctor", [
    "--tool", "hermes", "--home", hermes.home,
    "--project-dir", hermes.project, "--no-skills", "--doctor",
  ], hermes.home);
  expectIncludes(hermesDoctor, "FILES_HEALTHY", "hermes doctor");
  invoke("hermes repeat install/connect", [
    "--tool", "hermes", "--home", hermes.home,
    "--project-dir", hermes.project, "--no-skills", "--install", "--connect",
  ], hermes.home);

  const hermesOverride = roots("hermes-override");
  const hermesOverrideHome = join(sandbox, "hermes-native-home");
  const hermesOverrideOutput = invoke("hermes HERMES_HOME install/connect", [
    "--tool", "hermes", "--project-dir", hermesOverride.project,
    "--no-skills", "--install", "--connect",
  ], hermesOverride.home, {HERMES_HOME: hermesOverrideHome});
  expectIncludes(hermesOverrideOutput, "Connected: hermes (filesystem-connected)", "hermes HERMES_HOME install/connect");
  expectNonEmptyFile(join(hermesOverrideHome, "skills", "agi-super-team-agents", "ast-ceo", "SKILL.md"), "Hermes override CEO Agent");
  expectNonEmptyFile(join(hermesOverrideHome, "agi-super-team", "connection.json"), "Hermes override connection");
  expectNonEmptyFile(join(hermesOverrideHome, "agi-super-team", "receipt.json"), "Hermes override receipt");
  if (existsSync(join(hermesOverride.home, ".hermes"))) {
    throw new Error("HERMES_HOME created a dead directory under OS home");
  }

  const allTools = roots("all-tools");
  const allToolsOutput = invoke("--all-tools preview", [
    "--all-tools", "--home", allTools.home,
    "--project-dir", allTools.project, "--skip-plugin",
  ], allTools.home);
  expectIncludes(allToolsOutput, "AGI Super Team — PREVIEW", "--all-tools preview");
  expectIncludes(allToolsOutput, "Tools: claude-code, codex, openclaw, hermes", "--all-tools preview");
  expectIncludes(allToolsOutput, "Preview only. Add --install to apply.", "--all-tools preview");
  if (tree(dirname(allTools.home)).length !== 0) throw new Error("--all-tools preview mutated its isolated roots");

  console.log(`${sourceModule ? "Source" : "Packed"} CLI smoke passed via ${basename(cli)} on ${process.platform}`);
} finally {
  rmSync(sandbox, { recursive: true, force: true });
}
