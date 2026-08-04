import { spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const cli = resolve(process.argv[2] || join(repositoryRoot, "bin", "agi-super-team.mjs"));
const sandbox = mkdtempSync(join(tmpdir(), "agi-super-team-windows-smoke-"));

function isolatedEnvironment(home) {
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
  return environment;
}

function invoke(label, args, home) {
  const sourceModule = extname(cli) === ".mjs";
  const command = sourceModule ? process.execPath : cli;
  const commandArgs = sourceModule ? [cli, ...args] : args;
  const result = spawnSync(command, commandArgs, {
    cwd: sandbox,
    encoding: "utf8",
    env: isolatedEnvironment(home),
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
    "--project-dir", installed.project, "--skip-plugin", "--install", "--connect",
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
    "--project-dir", installed.project, "--skip-plugin", "--doctor",
  ], installed.home);
  expectIncludes(doctorOutput, "AGI Super Team doctor: HEALTHY", "claude-code doctor");
  expectIncludes(doctorOutput, "0 issues", "claude-code doctor");

  const openclaw = roots("openclaw-subagents");
  const openclawOutput = invoke("openclaw --all-subagents preview", [
    "--tool", "openclaw", "--home", openclaw.home,
    "--project-dir", openclaw.project, "--skip-plugin", "--all-subagents",
  ], openclaw.home);
  expectIncludes(openclawOutput, "AGI Super Team — PREVIEW", "openclaw --all-subagents preview");
  expectIncludes(openclawOutput, "Tools: openclaw", "openclaw --all-subagents preview");
  expectIncludes(openclawOutput, "Preview only. Add --install to apply.", "openclaw --all-subagents preview");
  if (tree(dirname(openclaw.home)).length !== 0) throw new Error("openclaw preview mutated its isolated roots");

  const allTools = roots("all-tools");
  const allToolsOutput = invoke("--all-tools preview", [
    "--all-tools", "--home", allTools.home,
    "--project-dir", allTools.project, "--skip-plugin",
  ], allTools.home);
  expectIncludes(allToolsOutput, "AGI Super Team — PREVIEW", "--all-tools preview");
  expectIncludes(allToolsOutput, "Tools: claude-code, codex, openclaw, hermes", "--all-tools preview");
  expectIncludes(allToolsOutput, "Preview only. Add --install to apply.", "--all-tools preview");
  if (tree(dirname(allTools.home)).length !== 0) throw new Error("--all-tools preview mutated its isolated roots");

  console.log(`Windows CLI smoke passed via ${basename(cli)}`);
} finally {
  rmSync(sandbox, { recursive: true, force: true });
}
