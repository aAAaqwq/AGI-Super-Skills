import { spawnSync } from "node:child_process";
import {
  chmodSync,
  closeSync,
  copyFileSync,
  existsSync,
  lstatSync,
  mkdirSync,
  openSync,
  renameSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, isAbsolute, join, relative, resolve } from "node:path";


export function mergeManagedAgents(existing, managed) {
  const replacements = new Map(managed.map((entry) => [entry.id, entry]));
  const output = existing.map((entry) => {
    const replacement = replacements.get(entry.id);
    if (!replacement) return entry;
    replacements.delete(entry.id);
    return replacement;
  });
  output.push(...replacements.values());
  return output;
}

function run(command, args, {environment, input = undefined, allowMissingPath = false}) {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    env: environment,
    input,
    maxBuffer: 16 * 1024 * 1024,
  });
  if (result.status !== 0 && !allowMissingPath) {
    const detail = (result.stderr || result.stdout || "").trim();
    throw new Error(`${command} ${args.join(" ")} failed${detail ? `: ${detail}` : ""}`);
  }
  return result;
}

function parseJsonOutput(result, fallback) {
  const text = (result.stdout || "").trim();
  if (!text || result.status !== 0) return fallback;
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`invalid JSON from OpenClaw CLI: ${error.message}`);
  }
}

function backupOpenClawConfig(home) {
  const stateRoot = join(home, ".openclaw");
  const config = join(stateRoot, "openclaw.json");
  if (!existsSync(config)) return null;
  const metadata = lstatSync(config);
  if (metadata.isSymbolicLink() || !statSync(config).isFile()) {
    throw new Error(`refusing unsafe OpenClaw config: ${config}`);
  }
  const backupRoot = join(stateRoot, ".agi-super-team-backups");
  mkdirSync(backupRoot, {recursive: true, mode: 0o700});
  const timestamp = new Date().toISOString().replaceAll(":", "").replaceAll(".", "");
  const backup = join(backupRoot, `openclaw.json.${timestamp}.bak`);
  copyFileSync(config, backup);
  return backup;
}

function connectOpenClaw({home, connection, environment}) {
  const command = environment.OPENCLAW_CLI || "openclaw";
  const stateRoot = join(home, ".openclaw");
  const env = {
    ...environment,
    OPENCLAW_STATE_DIR: stateRoot,
  };
  const version = run(command, ["--version"], {environment: env}).stdout.trim();
  const currentResult = run(
    command,
    ["config", "get", "agents.list", "--json"],
    {environment: env, allowMissingPath: true},
  );
  const existing = parseJsonOutput(currentResult, []);
  if (!Array.isArray(existing)) throw new Error("OpenClaw agents.list must be an array");
  const managed = connection?.configPatch?.agents?.list;
  if (!Array.isArray(managed)) throw new Error("OpenClaw connection spec is missing configPatch.agents.list");
  const requirements = connection.requirements || {};
  const patch = {
    agents: {
      defaults: {
        subagents: {
          maxSpawnDepth: requirements.requiredMaxDepth || 2,
          maxChildrenPerAgent: requirements.maxChildrenPerAgent || 2,
        },
      },
      list: mergeManagedAgents(existing, managed),
    },
  };
  const input = `${JSON.stringify(patch)}\n`;
  run(
    command,
    [
      "config",
      "patch",
      "--stdin",
      "--dry-run",
      "--json",
      "--replace-path",
      "agents.list",
    ],
    {environment: env, input},
  );
  const backup = backupOpenClawConfig(home);
  run(
    command,
    ["config", "patch", "--stdin", "--replace-path", "agents.list"],
    {environment: env, input},
  );
  run(command, ["config", "validate", "--json"], {environment: env});
  return {
    schemaVersion: 1,
    harness: "openclaw",
    status: "connected-structural",
    runtimeEvidence: "pending",
    version,
    managedAgents: managed.map((entry) => entry.id),
    preservedAgents: existing
      .filter((entry) => !managed.some((item) => item.id === entry.id))
      .map((entry) => entry.id),
    bindingsChanged: false,
    backup,
    checks: [
      "config-patch-dry-run",
      "managed-agent-upsert",
      "unmanaged-agent-preservation",
      "config-validate",
    ],
    limitations: [
      "No model-backed delegation canary was executed.",
      "No inbound channel binding was created.",
    ],
  };
}

export function connectHarness({
  tool,
  home,
  connection,
  environment = process.env,
}) {
  if (!tool?.id) throw new Error("connectHarness requires a tool id");
  if (!home) throw new Error("connectHarness requires a home path");
  if (tool.id === "openclaw") {
    return connectOpenClaw({home, connection, environment});
  }
  return {
    schemaVersion: 1,
    harness: tool.id,
    status: "filesystem-connected",
    runtimeEvidence: "pending",
    checks: ["adapter-artifacts-materialized"],
    limitations: [
      "The harness client did not execute a model-backed trigger or delegation canary.",
    ],
  };
}

function assertSafeReceiptPath(root, path) {
  const resolvedRoot = resolve(root);
  const resolvedPath = resolve(path);
  const rel = relative(resolvedRoot, resolvedPath);
  if (
    rel === ".."
    || rel.startsWith(`..${process.platform === "win32" ? "\\" : "/"}`)
    || isAbsolute(rel)
  ) {
    throw new Error(`refusing receipt outside target root: ${resolvedPath}`);
  }
  let cursor = resolvedRoot;
  for (const component of rel.split(/[\\/]/).slice(0, -1)) {
    if (!component) continue;
    cursor = join(cursor, component);
    if (!existsSync(cursor)) continue;
    const metadata = lstatSync(cursor);
    if (metadata.isSymbolicLink() || !metadata.isDirectory()) {
      throw new Error(`refusing unsafe receipt ancestor: ${cursor}`);
    }
  }
  if (existsSync(resolvedPath)) {
    const metadata = lstatSync(resolvedPath);
    if (metadata.isSymbolicLink() || !metadata.isFile()) {
      throw new Error(`refusing unsafe receipt destination: ${resolvedPath}`);
    }
  }
  return resolvedPath;
}

export function writeHarnessReceipt({root, connectionPath, receipt}) {
  if (!root) throw new Error("writeHarnessReceipt requires a target root");
  if (
    typeof connectionPath !== "string"
    || !connectionPath
    || isAbsolute(connectionPath)
    || connectionPath.split(/[\\/]/).includes("..")
  ) {
    throw new Error(`unsafe connection path: ${connectionPath}`);
  }
  const path = assertSafeReceiptPath(
    root,
    join(root, dirname(connectionPath), "receipt.json"),
  );
  mkdirSync(dirname(path), {recursive: true, mode: 0o700});
  const temporary = join(
    dirname(path),
    `.agi-super-team-receipt.${process.pid}.${Date.now()}.tmp`,
  );
  const descriptor = openSync(temporary, "wx", 0o600);
  try {
    writeFileSync(descriptor, `${JSON.stringify(receipt, null, 2)}\n`);
  } finally {
    closeSync(descriptor);
  }
  chmodSync(temporary, 0o600);
  renameSync(temporary, path);
  return path;
}
