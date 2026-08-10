import {
  chmodSync,
  closeSync,
  existsSync,
  lstatSync,
  mkdirSync,
  openSync,
  readFileSync,
  renameSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { basename, dirname, isAbsolute, join, relative, resolve } from "node:path";
import { spawnCli } from "./process.mjs";

const OPENCLAW_REDACTED_SENTINEL = "__OPENCLAW_REDACTED__";


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
  const result = spawnCli(command, args, {
    encoding: "utf8",
    env: environment,
    input,
    maxBuffer: 16 * 1024 * 1024,
  });
  if (result.status !== 0 && !allowMissingPath) {
    throw commandFailure(command, args, result);
  }
  return result;
}

function commandFailure(command, args, result) {
  const detail = (
    result.error?.message
    || result.stderr
    || result.stdout
    || (result.signal ? `terminated by signal ${result.signal}` : "")
  ).trim();
  return new Error(`${command} ${args.join(" ")} failed${detail ? `: ${detail}` : ""}`);
}

function isMissingAgentsList(result) {
  if (result.status === 0 || result.error || result.signal) return false;
  const output = `${result.stderr || ""}\n${result.stdout || ""}`;
  return /Config path not found:\s*agents\.list(?:[.\s]|$)/.test(output);
}

function parseJsonOutput(result) {
  const text = (result.stdout || "").trim();
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`invalid JSON from OpenClaw CLI: ${error.message}`);
  }
}

function containsRedactedSentinel(value, seen = new Set()) {
  if (value === OPENCLAW_REDACTED_SENTINEL) return true;
  if (!value || typeof value !== "object") return false;
  if (seen.has(value)) return false;
  seen.add(value);
  if (Array.isArray(value)) {
    return value.some((item) => containsRedactedSentinel(item, seen));
  }
  return Object.values(value).some((item) => containsRedactedSentinel(item, seen));
}

function decodeEscapedCodePoint(text, offset, marker, width) {
  const digits = text.slice(offset + marker.length, offset + marker.length + width);
  if (!new RegExp(`^[0-9a-f]{${width}}$`, "i").test(digits)) return null;
  return {
    value: String.fromCodePoint(Number.parseInt(digits, 16)),
    end: offset + marker.length + width - 1,
  };
}

function skipJson5Trivia(text, offset) {
  let cursor = offset;
  while (cursor < text.length) {
    if (/\s/u.test(text[cursor])) {
      cursor += 1;
      continue;
    }
    if (text[cursor] === "/" && text[cursor + 1] === "/") {
      cursor += 2;
      while (
        cursor < text.length
        && text[cursor] !== "\r"
        && text[cursor] !== "\n"
        && text[cursor] !== "\u2028"
        && text[cursor] !== "\u2029"
      ) cursor += 1;
      continue;
    }
    if (text[cursor] === "/" && text[cursor + 1] === "*") {
      cursor += 2;
      while (
        cursor + 1 < text.length
        && !(text[cursor] === "*" && text[cursor + 1] === "/")
      ) cursor += 1;
      cursor = Math.min(cursor + 2, text.length);
      continue;
    }
    break;
  }
  return cursor;
}

const JSON5_IDENTIFIER_START = /[$_\p{ID_Start}]/u;
const JSON5_IDENTIFIER_PART = /[$_\u200c\u200d\p{ID_Continue}]/u;

function readJson5Identifier(text, offset) {
  let cursor = offset;
  let value = "";
  let first = true;
  let end = offset - 1;
  while (cursor < text.length) {
    let character = text[cursor];
    let characterEnd = cursor;
    if (character === "\\" && text[cursor + 1] === "u") {
      const decoded = decodeEscapedCodePoint(text, cursor + 1, "u", 4);
      if (!decoded) break;
      character = decoded.value;
      characterEnd = decoded.end;
    }
    const allowed = first ? JSON5_IDENTIFIER_START : JSON5_IDENTIFIER_PART;
    if (!allowed.test(character)) break;
    value += character;
    end = characterEnd;
    cursor = characterEnd + 1;
    first = false;
  }
  return first ? null : {value, end};
}

function decodedJson5KeyCandidates(content) {
  const text = content.toString("utf8");
  const candidates = [];
  for (let cursor = 0; cursor < text.length; cursor += 1) {
    const significant = skipJson5Trivia(text, cursor);
    if (significant !== cursor) {
      cursor = significant;
      if (cursor >= text.length) break;
    }
    const quote = text[cursor];
    if (quote !== '"' && quote !== "'") {
      const identifier = readJson5Identifier(text, cursor);
      if (!identifier) continue;
      candidates.push(identifier);
      cursor = identifier.end;
      continue;
    }
    let value = "";
    let closed = false;
    for (cursor += 1; cursor < text.length; cursor += 1) {
      const character = text[cursor];
      if (character === quote) {
        closed = true;
        break;
      }
      if (character !== "\\") {
        value += character;
        continue;
      }
      cursor += 1;
      if (cursor >= text.length) break;
      const escaped = text[cursor];
      if (escaped === "\r") {
        if (text[cursor + 1] === "\n") cursor += 1;
        continue;
      }
      if (escaped === "\n" || escaped === "\u2028" || escaped === "\u2029") continue;
      const simpleEscapes = {
        b: "\b",
        f: "\f",
        n: "\n",
        r: "\r",
        t: "\t",
        v: "\v",
        0: "\0",
      };
      if (Object.hasOwn(simpleEscapes, escaped)) {
        value += simpleEscapes[escaped];
        continue;
      }
      if (escaped === "x") {
        const decoded = decodeEscapedCodePoint(text, cursor, "x", 2);
        if (decoded) {
          value += decoded.value;
          cursor = decoded.end;
          continue;
        }
      }
      if (escaped === "u") {
        const decoded = decodeEscapedCodePoint(text, cursor, "u", 4);
        if (decoded) {
          value += decoded.value;
          cursor = decoded.end;
          continue;
        }
      }
      value += escaped;
    }
    if (closed) candidates.push({value, end: cursor});
  }
  return {text, candidates};
}

function containsIncludeDirective(content) {
  const {text, candidates} = decodedJson5KeyCandidates(content);
  return candidates.some(({value, end}) =>
    value === "$include" && text[skipJson5Trivia(text, end + 1)] === ":");
}

function rejectIncludeBackedConfig(snapshot) {
  if (snapshot.exists && containsIncludeDirective(snapshot.content)) {
    throw new Error(
      "refusing OpenClaw connection because the active config contains $include; automatic rollback cannot cover included files",
    );
  }
}

function resolveTildePath(value, effectiveHome, label) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`invalid ${label}: ${String(value)}`);
  }
  const normalized = value.trim();
  let path;
  if (normalized === "~") path = resolve(effectiveHome);
  else if (normalized.startsWith("~/") || normalized.startsWith("~\\")) {
    path = resolve(effectiveHome, normalized.slice(2));
  } else if (normalized.startsWith("~")) {
    throw new Error(`unsupported ${label}: ${normalized}`);
  } else {
    path = resolve(normalized);
  }
  if (path === resolve("/")) throw new Error(`refusing unsafe ${label}: ${path}`);
  return path;
}

function configuredPath(environment, name) {
  const value = environment?.[name];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function resolveOpenClawTargets({home, connection, environment}) {
  const fallbackHome = resolveTildePath(home, resolve(home), "OpenClaw home");
  const targetHome = resolveTildePath(
    connection?.targetHome
      || configuredPath(environment, "OPENCLAW_HOME")
      || fallbackHome,
    fallbackHome,
    "OpenClaw effective home",
  );
  const targetStateDir = resolveTildePath(
    connection?.targetStateDir
      || configuredPath(environment, "OPENCLAW_STATE_DIR")
      || join(targetHome, ".openclaw"),
    targetHome,
    "OpenClaw state directory",
  );
  const targetConfigPath = resolveTildePath(
    connection?.mergeContract?.configPath
      || configuredPath(environment, "OPENCLAW_CONFIG_PATH")
      || join(targetStateDir, "openclaw.json"),
    targetHome,
    "OpenClaw config path",
  );
  return {targetHome, targetStateDir, targetConfigPath};
}

function captureOpenClawConfig(path) {
  if (!existsSync(path)) {
    return {path, exists: false, content: null, mode: null, device: null, inode: null};
  }
  const metadata = lstatSync(path);
  if (metadata.isSymbolicLink() || !metadata.isFile()) {
    throw new Error(`refusing unsafe OpenClaw config: ${path}`);
  }
  return {
    path,
    exists: true,
    content: readFileSync(path),
    mode: metadata.mode & 0o777,
    device: metadata.dev,
    inode: metadata.ino,
  };
}

function configMatches(snapshot) {
  try {
    if (!existsSync(snapshot.path)) return !snapshot.exists;
    if (!snapshot.exists) return false;
    const metadata = lstatSync(snapshot.path);
    if (metadata.isSymbolicLink() || !metadata.isFile()) return false;
    return (
      (metadata.mode & 0o777) === snapshot.mode
      && metadata.dev === snapshot.device
      && metadata.ino === snapshot.inode
      && readFileSync(snapshot.path).equals(snapshot.content)
    );
  } catch {
    return false;
  }
}

function backupOpenClawConfig(snapshot) {
  if (!snapshot.exists) return null;
  const stateRoot = dirname(snapshot.path);
  const config = snapshot.path;
  const metadata = lstatSync(config);
  if (metadata.isSymbolicLink() || !metadata.isFile()) {
    throw new Error(`refusing unsafe OpenClaw config: ${config}`);
  }
  const backupRoot = join(stateRoot, ".agi-super-team-backups");
  if (existsSync(backupRoot)) {
    const backupMetadata = lstatSync(backupRoot);
    if (backupMetadata.isSymbolicLink() || !backupMetadata.isDirectory()) {
      throw new Error(`refusing unsafe OpenClaw backup directory: ${backupRoot}`);
    }
    chmodSync(backupRoot, 0o700);
  } else {
    mkdirSync(backupRoot, {recursive: true, mode: 0o700});
  }
  const timestamp = new Date().toISOString().replaceAll(":", "").replaceAll(".", "");
  const backup = join(backupRoot, `${basename(config)}.${timestamp}.${process.pid}.bak`);
  const descriptor = openSync(backup, "wx", 0o600);
  try {
    writeFileSync(descriptor, snapshot.content);
  } finally {
    closeSync(descriptor);
  }
  chmodSync(backup, 0o600);
  return backup;
}

function restoreOpenClawConfig({original, expected, backup, failure}) {
  if (!configMatches(expected)) {
    const recovery = backup
      ? `original backup preserved at ${backup}`
      : "no original config existed; the current config was preserved";
    throw new Error(
      `${failure.message}; refusing automatic rollback because OpenClaw config changed concurrently; ${recovery}`,
      {cause: failure},
    );
  }
  if (!original.exists) {
    if (existsSync(original.path)) unlinkSync(original.path);
    return {status: "rolled-back", restored: "removed-new-config", backup};
  }
  const temporary = join(
    dirname(original.path),
    `.agi-super-team-openclaw-restore.${process.pid}.${Date.now()}.tmp`,
  );
  const descriptor = openSync(temporary, "wx", 0o600);
  try {
    writeFileSync(descriptor, original.content);
  } finally {
    closeSync(descriptor);
  }
  chmodSync(temporary, original.mode);
  renameSync(temporary, original.path);
  return {status: "rolled-back", restored: "original-config", backup};
}

function prepareOpenClawConnection({home, connection, environment}) {
  const command = environment.OPENCLAW_CLI || "openclaw";
  const targets = resolveOpenClawTargets({home, connection, environment});
  const env = {
    ...environment,
    OPENCLAW_HOME: targets.targetHome,
    OPENCLAW_STATE_DIR: targets.targetStateDir,
    OPENCLAW_CONFIG_PATH: targets.targetConfigPath,
  };
  const version = run(command, ["--version"], {environment: env}).stdout.trim();
  const originalConfig = captureOpenClawConfig(targets.targetConfigPath);
  rejectIncludeBackedConfig(originalConfig);
  const currentResult = run(
    command,
    ["config", "get", "agents.list", "--json"],
    {environment: env, allowMissingPath: true},
  );
  if (currentResult.status !== 0 && !isMissingAgentsList(currentResult)) {
    throw commandFailure(command, ["config", "get", "agents.list", "--json"], currentResult);
  }
  const existing = currentResult.status === 0 ? parseJsonOutput(currentResult) : [];
  if (!Array.isArray(existing)) throw new Error("OpenClaw agents.list must be an array");
  if (containsRedactedSentinel(existing)) {
    throw new Error(
      "refusing OpenClaw connection because config get returned redacted values that cannot be safely round-tripped",
    );
  }
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
  if (!configMatches(originalConfig)) {
    throw new Error("OpenClaw config changed while preparing the connection; retry without concurrent edits");
  }
  return {
    command,
    env,
    version,
    originalConfig,
    existing,
    managed,
    input,
    targets,
  };
}

function connectOpenClawTransaction({home, connection, environment}) {
  const prepared = prepareOpenClawConnection({home, connection, environment});
  const {
    command,
    env,
    version,
    originalConfig,
    existing,
    managed,
    input,
    targets,
  } = prepared;
  const backup = backupOpenClawConfig(originalConfig);
  if (!configMatches(originalConfig)) {
    if (backup && existsSync(backup)) unlinkSync(backup);
    throw new Error("OpenClaw config changed before applying the connection; retry without concurrent edits");
  }
  try {
    run(
      command,
      ["config", "patch", "--stdin", "--replace-path", "agents.list"],
      {environment: env, input},
    );
  } catch (failure) {
    const failedPatchConfig = captureOpenClawConfig(targets.targetConfigPath);
    const rollback = restoreOpenClawConfig({
      original: originalConfig,
      expected: failedPatchConfig,
      backup,
      failure,
    });
    throw new Error(
      `${failure.message}; OpenClaw config rollback completed (${rollback.restored})${backup ? `; backup preserved at ${backup}` : ""}`,
      {cause: failure},
    );
  }
  const appliedConfig = captureOpenClawConfig(targets.targetConfigPath);
  try {
    run(command, ["config", "validate", "--json"], {environment: env});
  } catch (failure) {
    const rollback = restoreOpenClawConfig({
      original: originalConfig,
      expected: appliedConfig,
      backup,
      failure,
    });
    throw new Error(
      `${failure.message}; OpenClaw config rollback completed (${rollback.restored})${backup ? `; backup preserved at ${backup}` : ""}`,
      {cause: failure},
    );
  }
  const receipt = {
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
  let state = "active";
  return {
    receipt,
    rollback() {
      if (state !== "active") return {status: "not-active", state, backup};
      const rollback = restoreOpenClawConfig({
        original: originalConfig,
        expected: appliedConfig,
        backup,
        failure: new Error("OpenClaw connection rollback requested"),
      });
      state = "rolled-back";
      return rollback;
    },
    commit() {
      if (state === "committed") return {status: "committed", backup};
      if (state !== "active") return {status: "not-active", state, backup};
      state = "committed";
      return {status: "committed", backup};
    },
  };
}

export function preflightHarnessConnection({
  tool,
  home,
  connection,
  environment = process.env,
}) {
  if (!tool?.id) throw new Error("preflightHarnessConnection requires a tool id");
  if (!home) throw new Error("preflightHarnessConnection requires a home path");
  if (tool.id !== "openclaw") {
    return {
      harness: tool.id,
      status: "ready",
      checks: ["adapter-artifacts-plan-ready"],
    };
  }
  const prepared = prepareOpenClawConnection({home, connection, environment});
  return {
    harness: "openclaw",
    status: "ready",
    version: prepared.version,
    managedAgents: prepared.managed.map((entry) => entry.id),
    preservedAgents: prepared.existing
      .filter((entry) => !prepared.managed.some((item) => item.id === entry.id))
      .map((entry) => entry.id),
    checks: ["cli-version", "config-get", "config-patch-dry-run"],
  };
}

export function connectHarnessTransaction({
  tool,
  home,
  connection,
  environment = process.env,
}) {
  if (!tool?.id) throw new Error("connectHarness requires a tool id");
  if (!home) throw new Error("connectHarness requires a home path");
  if (tool.id === "openclaw") {
    return connectOpenClawTransaction({home, connection, environment});
  }
  const receipt = {
    schemaVersion: 1,
    harness: tool.id,
    status: "filesystem-connected",
    runtimeEvidence: "pending",
    checks: ["adapter-artifacts-materialized"],
    limitations: [
      "The harness client did not execute a model-backed trigger or delegation canary.",
    ],
  };
  let state = "active";
  return {
    receipt,
    rollback() {
      if (state !== "active") return {status: "not-active", state, backup: null};
      state = "rolled-back";
      return {status: "not-required", backup: null};
    },
    commit() {
      if (state === "committed") return {status: "committed", backup: null};
      if (state !== "active") return {status: "not-active", state, backup: null};
      state = "committed";
      return {status: "committed", backup: null};
    },
  };
}

export function connectHarness(options) {
  const transaction = connectHarnessTransaction(options);
  transaction.commit();
  return transaction.receipt;
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

function captureReceipt(path) {
  if (!existsSync(path)) {
    return {path, exists: false, content: null, mode: null, device: null, inode: null};
  }
  const metadata = lstatSync(path);
  if (metadata.isSymbolicLink() || !metadata.isFile()) {
    throw new Error(`refusing unsafe receipt destination: ${path}`);
  }
  return {
    path,
    exists: true,
    content: readFileSync(path),
    mode: metadata.mode & 0o777,
    device: metadata.dev,
    inode: metadata.ino,
  };
}

function receiptMatches(snapshot) {
  try {
    if (!existsSync(snapshot.path)) return !snapshot.exists;
    if (!snapshot.exists) return false;
    const metadata = lstatSync(snapshot.path);
    if (metadata.isSymbolicLink() || !metadata.isFile()) return false;
    return (
      (metadata.mode & 0o777) === snapshot.mode
      && metadata.dev === snapshot.device
      && metadata.ino === snapshot.inode
      && readFileSync(snapshot.path).equals(snapshot.content)
    );
  } catch {
    return false;
  }
}

function writePrivateFile(path, content, mode = 0o600) {
  const descriptor = openSync(path, "wx", mode);
  try {
    writeFileSync(descriptor, content);
  } finally {
    closeSync(descriptor);
  }
  chmodSync(path, mode);
}

export function writeHarnessReceiptTransaction({root, connectionPath, receipt}) {
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
  const original = captureReceipt(path);
  const nonce = `${process.pid}.${Date.now()}`;
  const backup = original.exists
    ? join(dirname(path), `.agi-super-team-receipt-backup.${nonce}.tmp`)
    : null;
  if (backup) writePrivateFile(backup, original.content);
  const backupSnapshot = backup ? captureReceipt(backup) : null;
  const temporary = join(
    dirname(path),
    `.agi-super-team-receipt.${nonce}.tmp`,
  );
  let temporarySnapshot = null;
  try {
    writePrivateFile(temporary, `${JSON.stringify(receipt, null, 2)}\n`);
    temporarySnapshot = captureReceipt(temporary);
    assertSafeReceiptPath(root, path);
    if (!receiptMatches(original)) {
      throw new Error(
        "refusing receipt replacement because the destination changed concurrently before write",
      );
    }
    renameSync(temporary, path);
  } catch (error) {
    const preserved = [];
    for (const artifact of [temporarySnapshot, backupSnapshot]) {
      if (!artifact) continue;
      try {
        if (receiptMatches(artifact)) unlinkSync(artifact.path);
        else if (existsSync(artifact.path)) preserved.push(artifact.path);
      } catch {
        preserved.push(artifact.path);
      }
    }
    if (preserved.length) {
      throw new Error(
        `${error.message}; transaction artifacts preserved for inspection at ${preserved.join(", ")}`,
        {cause: error},
      );
    }
    throw error;
  }
  const applied = captureReceipt(path);
  let state = "active";
  let commitResult = null;
  return {
    path,
    rollback() {
      if (state !== "active") return {status: "not-active", state, backup};
      if (!receiptMatches(applied)) {
        const recovery = backup
          ? `original receipt backup preserved at ${backup}`
          : "no original receipt existed; the current receipt was preserved";
        throw new Error(
          `refusing automatic receipt rollback because the receipt changed concurrently; ${recovery}`,
        );
      }
      if (original.exists) {
        const restore = join(
          dirname(path),
          `.agi-super-team-receipt-restore.${process.pid}.${Date.now()}.tmp`,
        );
        writePrivateFile(restore, original.content, original.mode);
        renameSync(restore, path);
      } else if (existsSync(path)) {
        unlinkSync(path);
      }
      if (backup && existsSync(backup)) unlinkSync(backup);
      state = "rolled-back";
      return {status: "rolled-back", backup: null};
    },
    commit() {
      if (state === "committed") return commitResult;
      if (state !== "active") return {status: "not-active", state, backup};
      state = "committed";
      try {
        if (backup && existsSync(backup)) unlinkSync(backup);
        commitResult = {status: "committed", backup: null};
      } catch {
        commitResult = {status: "committed", backup, backupPreserved: true};
      }
      return commitResult;
    },
  };
}

export function writeHarnessReceipt(options) {
  const transaction = writeHarnessReceiptTransaction(options);
  transaction.commit();
  return transaction.path;
}
