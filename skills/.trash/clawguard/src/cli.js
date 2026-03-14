const fs = require("fs");
const path = require("path");
const { loadConfig, normalizeConfig } = require("./config");
const { scanPaths, collectFiles } = require("./scanner");
const { formatTextReport, formatJsonReport, writeReport } = require("./report");
const { normalizeSeverity, severityGte, toAbsolute } = require("./utils");
const { buildShareMessage } = require("./share");
const { checkUpdate, compareVersions, applyUpdate } = require("./update");
const { loadRules, updateRulePack, DEFAULT_RULES_URL, resolveRulePackPath } = require("./rulepack");
const { loadState, saveState } = require("./state");
const { runHealthChecks } = require("./health");
const { initBaseline, checkBaseline } = require("./integrity");
const { spawnSync } = require("child_process");
const os = require("os");

function printHelp() {
  const help = [
    "Clawguard - scan OpenClaw skills/plugins for risky patterns",
    "",
    "Usage:",
    "  clawguard scan [--path <path> ...] [--config <file>] [--format text|json] [--fail-on <severity>] [--min-severity <severity>] [--output <file>]",
    "  clawguard guard [options] -- <command> [args...]",
    "",
    "Commands:",
    "  scan      Scan paths and report findings",
    "  guard     Block command execution if high-risk findings exist",
    "  share     Print a shareable install snippet",
    "  update    Check or apply updates",
    "  watch     Watch for new or changed files",
    "  health    Check critical system paths",
    "  integrity Init/check file integrity baselines",
    "  rules     Manage detection rule packs",
    "",
    "Options:",
    "  --path <path>         Add a path to scan (repeatable)",
    "  --config <file>       Use a custom config file",
    "  --format <text|json>  Output format (default: text)",
    "  --fail-on <severity>  Exit non-zero if findings >= severity (default: high)",
    "  --min-severity <sev>  Only show findings >= severity (default: low)",
    "  --output <file>       Write report to file",
    "  --repo <owner/repo>   Override GitHub repository for share/update",
    "  --lang <en|zh>        Language for share output (default: en)",
    "  --apply               Apply update (update command)",
    "  --method <git|npm>    Update method (default: auto)",
    "  --interval <sec>      Watch interval in seconds",
    "  --auto-update         Auto-update rules before scan/watch",
    "",
    "Severity values: low, medium, high",
  ];
  console.log(help.join("\n"));
}

function parseArgs(args) {
  const options = {
    paths: [],
    configPath: null,
    format: "text",
    failOn: "high",
    minSeverity: "low",
    output: null,
    autoUpdate: false,
  };
  const positional = [];

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === "--path") {
      options.paths.push(args[i + 1]);
      i += 1;
      continue;
    }
    if (arg === "--config") {
      options.configPath = args[i + 1];
      i += 1;
      continue;
    }
    if (arg === "--format") {
      options.format = args[i + 1];
      i += 1;
      continue;
    }
    if (arg === "--fail-on") {
      options.failOn = args[i + 1];
      i += 1;
      continue;
    }
    if (arg === "--min-severity") {
      options.minSeverity = args[i + 1];
      i += 1;
      continue;
    }
    if (arg === "--output") {
      options.output = args[i + 1];
      i += 1;
      continue;
    }
    if (arg === "--auto-update") {
      options.autoUpdate = true;
      continue;
    }
    positional.push(arg);
  }

  return { options, positional };
}

function parseShareArgs(args) {
  const options = { lang: "en", format: "text", repo: null };
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === "--lang") {
      options.lang = args[i + 1] || "en";
      i += 1;
      continue;
    }
    if (arg === "--format") {
      options.format = args[i + 1] || "text";
      i += 1;
      continue;
    }
    if (arg === "--repo") {
      options.repo = args[i + 1];
      i += 1;
      continue;
    }
  }
  return options;
}

function parseUpdateArgs(args) {
  const options = { apply: false, check: false, method: "auto", repo: null };
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === "--apply") {
      options.apply = true;
      continue;
    }
    if (arg === "--check") {
      options.check = true;
      continue;
    }
    if (arg === "--method") {
      options.method = args[i + 1] || "auto";
      i += 1;
      continue;
    }
    if (arg === "--repo") {
      options.repo = args[i + 1];
      i += 1;
      continue;
    }
  }
  if (!options.apply && !options.check) {
    options.check = true;
  }
  return options;
}

function parseWatchArgs(args) {
  const options = {
    paths: [],
    configPath: null,
    minSeverity: "low",
    interval: 5,
    autoUpdate: false,
  };
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === "--path") {
      options.paths.push(args[i + 1]);
      i += 1;
      continue;
    }
    if (arg === "--config") {
      options.configPath = args[i + 1];
      i += 1;
      continue;
    }
    if (arg === "--min-severity") {
      options.minSeverity = args[i + 1];
      i += 1;
      continue;
    }
    if (arg === "--interval") {
      options.interval = Number(args[i + 1]) || 5;
      i += 1;
      continue;
    }
    if (arg === "--auto-update") {
      options.autoUpdate = true;
    }
  }
  return options;
}

function parseRulesArgs(args) {
  const options = { action: "update", url: null, dest: null, configPath: null };
  if (args[0]) {
    options.action = args[0];
  }
  for (let i = 1; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === "--url") {
      options.url = args[i + 1];
      i += 1;
      continue;
    }
    if (arg === "--dest") {
      options.dest = args[i + 1];
      i += 1;
      continue;
    }
    if (arg === "--config") {
      options.configPath = args[i + 1];
      i += 1;
    }
  }
  return options;
}

function parseIntegrityArgs(args) {
  const options = { action: "check", paths: [], self: false, openclaw: false, configPath: null };
  if (args[0]) {
    options.action = args[0];
  }
  for (let i = 1; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === "--path") {
      options.paths.push(args[i + 1]);
      i += 1;
      continue;
    }
    if (arg === "--self") {
      options.self = true;
      continue;
    }
    if (arg === "--openclaw") {
      options.openclaw = true;
      continue;
    }
    if (arg === "--config") {
      options.configPath = args[i + 1];
      i += 1;
    }
  }
  return options;
}

function resolveScanPaths(cliPaths, configPaths, cwd) {
  const resolved = [];
  const candidatePaths = cliPaths.length > 0 ? cliPaths : configPaths;
  if (candidatePaths.length > 0) {
    candidatePaths.forEach((item) => resolved.push(toAbsolute(item, cwd)));
  }

  const defaultPaths = [
    path.join(cwd, "plugins"),
    path.join(cwd, "skills"),
    path.join(require("os").homedir(), ".openclaw"),
  ];

  if (resolved.length === 0) {
    defaultPaths.forEach((item) => {
      if (fs.existsSync(item)) resolved.push(item);
    });
  }

  if (resolved.length === 0) {
    resolved.push(cwd);
  }

  return resolved;
}

async function runScan(options) {
  const cwd = process.cwd();
  const { config, configPath } = loadConfig(cwd, options.configPath);
  const normalized = normalizeConfig(config, cwd);
  const scanPathsList = resolveScanPaths(options.paths, normalized.paths, cwd);
  const ignore = normalized.ignore;
  const minSeverity = normalizeSeverity(options.minSeverity, normalized.minSeverity);
  const failOn = normalizeSeverity(options.failOn, normalized.failOn);

  const disabledRules = normalized.rules.disable;

  try {
    await maybeAutoUpdateRules(normalized, cwd, options.autoUpdate);
  } catch (error) {
    console.error(`Rule auto-update failed: ${error.message}`);
  }

  const { rules, packPath, error: rulesError } = loadRules({ config: normalized, cwd });
  if (rulesError) {
    console.error(`Rule pack error (${packPath}): ${rulesError}`);
  }

  const result = scanPaths({
    paths: scanPathsList,
    ignorePatterns: ignore,
    disabledRules,
    rules,
  });

  const allFindings = result.findings;
  const visibleFindings = allFindings.filter((finding) =>
    severityGte(finding.severity, minSeverity)
  );
  const visibleCounts = { low: 0, medium: 0, high: 0 };
  visibleFindings.forEach((finding) => {
    visibleCounts[finding.severity] += 1;
  });
  result.allFindings = allFindings;
  result.allCounts = result.counts;
  result.findings = visibleFindings;
  result.counts = visibleCounts;

  result.configPath = configPath;
  result.minSeverity = minSeverity;
  result.failOn = failOn;

  const output = options.format === "json"
    ? formatJsonReport(result)
    : formatTextReport(result);

  if (options.output) {
    writeReport(options.output, output);
  } else {
    console.log(output);
  }

  const blocked = result.allFindings.some((finding) =>
    severityGte(finding.severity, failOn)
  );

  return blocked ? 2 : 0;
}

async function runGuard(options, commandArgs) {
  const exitCode = await runScan(options);
  if (exitCode !== 0) {
    console.error("Clawguard blocked execution due to high-risk findings.");
    process.exit(exitCode);
  }

  if (commandArgs.length === 0) {
    console.error("No command provided for guard mode.");
    process.exit(1);
  }

  const { spawn } = require("child_process");
  const [command, ...args] = commandArgs;
  const child = spawn(command, args, { stdio: "inherit" });
  child.on("exit", (code) => process.exit(code ?? 0));
}

function runShare(options) {
  const pkg = require("../package.json");
  const repoUrl = options.repo
    || (pkg.repository && pkg.repository.url ? pkg.repository.url : pkg.repository);
  const output = buildShareMessage({
    lang: options.lang,
    format: options.format,
    repoUrl,
  });
  console.log(output);
}

async function runUpdate(options) {
  const cwd = process.cwd();
  const result = await checkUpdate({ cwd, repoOverride: options.repo });
  if (options.check) {
    if (result.latest) {
      const comparison = compareVersions(result.current, result.latest.version);
      const updateAvailable = comparison === -1;
      console.log(`Current: ${result.current}`);
      console.log(`Latest: ${result.latest.version} (${result.latest.source})`);
      console.log(`Update available: ${updateAvailable ? "yes" : "no"}`);
      if (result.latest.url) {
        console.log(`More info: ${result.latest.url}`);
      }
    } else {
      console.log(`Current: ${result.current}`);
      console.log("Latest: unavailable");
      if (result.errors.length > 0) {
        console.log(`Errors: ${result.errors.join("; ")}`);
      }
    }
  }

  if (options.apply) {
    const pkg = require("../package.json");
    const method = options.method === "auto" ? undefined : options.method;
    const applied = await applyUpdate({ cwd, method, pkgName: pkg.name });
    console.log(`Update applied via ${applied}.`);
  }
}

async function runRules(options) {
  const cwd = process.cwd();
  const { config } = loadConfig(cwd, options.configPath);
  const normalized = normalizeConfig(config, cwd);
  const destination = options.dest || resolveRulePackPath(normalized, cwd);
  if (options.action === "path") {
    console.log(destination);
    return;
  }
  if (options.action !== "update") {
    console.error("rules command supports: update, path");
    process.exit(1);
  }
  const url = options.url || normalized.rules.updateUrl || DEFAULT_RULES_URL;
  const result = await updateRulePack({ url, destination });
  const state = loadState();
  state.rulesLastUpdated = new Date().toISOString();
  saveState(state);
  console.log(`Rules updated: ${result.destination}`);
}

function formatHealthReport(report) {
  if (report.findings.length === 0) {
    return "No critical path issues detected.";
  }
  const lines = [
    `Findings: high=${report.counts.high}, medium=${report.counts.medium}, low=${report.counts.low}.`,
  ];
  report.findings.forEach((finding) => {
    lines.push(`- [${finding.severity.toUpperCase()}] ${finding.path} ${finding.message}`);
  });
  return lines.join("\n");
}

function runHealth() {
  const report = runHealthChecks();
  console.log(formatHealthReport(report));
  const blocked = report.findings.some((finding) => finding.severity === "high");
  if (blocked) {
    process.exit(2);
  }
}

function resolveOpenclawPaths() {
  const paths = [];
  const home = os.homedir();
  const envHome = process.env.OPENCLAW_HOME;
  if (envHome) paths.push(envHome);
  const defaultHome = path.join(home, ".openclaw");
  if (fs.existsSync(defaultHome)) paths.push(defaultHome);
  if (process.platform !== "win32") {
    const whichResult = spawnSync("which", ["openclaw"], { encoding: "utf8" });
    if (whichResult.status === 0) {
      const binaryPath = whichResult.stdout.trim();
      if (binaryPath) paths.push(binaryPath);
    }
  }
  return Array.from(new Set(paths));
}

function checkSelfGitStatus(cwd) {
  const gitDir = path.join(cwd, ".git");
  if (!fs.existsSync(gitDir)) {
    return { status: "no-git" };
  }
  const result = spawnSync("git", ["status", "--porcelain"], { cwd, encoding: "utf8" });
  if (result.status !== 0) {
    return { status: "error", message: "git status failed" };
  }
  const output = result.stdout.trim();
  if (!output) {
    return { status: "clean" };
  }
  const lines = output.split(/\r?\n/);
  return { status: "dirty", changes: lines };
}

function runIntegrity(options) {
  const cwd = process.cwd();
  const { config } = loadConfig(cwd, options.configPath);
  const normalized = normalizeConfig(config, cwd);
  const ignore = normalized.ignore;
  const paths = [...options.paths];
  if (options.openclaw) {
    paths.push(...resolveOpenclawPaths());
  }
  if (options.self) {
    paths.push(cwd);
  }
  if (paths.length === 0 && !options.self) {
    console.error("No paths provided for integrity check.");
    process.exit(1);
  }

  if (options.action === "init") {
    const result = initBaseline(paths, ignore, cwd);
    result.created.forEach((item) => {
      console.log(`Baseline created: ${item.path} (${item.files} files)`);
    });
    return;
  }

  if (options.action !== "check") {
    console.error("integrity command supports: init, check");
    process.exit(1);
  }

  const results = paths.length > 0 ? checkBaseline(paths, ignore, cwd) : [];
  let hasIssues = false;
  results.forEach((item) => {
    if (item.error) {
      hasIssues = true;
      console.log(`- ${item.path}: ${item.error}`);
      return;
    }
    const { added, removed, modified } = item.diff;
    if (added.length || removed.length || modified.length) {
      hasIssues = true;
    }
    console.log(`Path: ${item.path}`);
    console.log(`  Added: ${added.length}`);
    console.log(`  Removed: ${removed.length}`);
    console.log(`  Modified: ${modified.length}`);
  });

  if (options.self) {
    const selfCheck = checkSelfGitStatus(cwd);
    if (selfCheck.status === "dirty") {
      hasIssues = true;
      console.log("Self check: git working tree has changes");
      selfCheck.changes.forEach((line) => console.log(`  ${line}`));
    } else if (selfCheck.status === "clean") {
      console.log("Self check: git working tree clean");
    } else if (selfCheck.status === "no-git") {
      console.log("Self check: no git metadata found");
    } else {
      console.log("Self check: git status error");
    }
  }
  if (hasIssues) {
    process.exit(2);
  }
}

async function runWatch(options) {
  const cwd = process.cwd();
  const { config } = loadConfig(cwd, options.configPath);
  const normalized = normalizeConfig(config, cwd);
  if (options.autoUpdate || normalized.rules.autoUpdate) {
    try {
      await maybeAutoUpdateRules(normalized, cwd, true);
    } catch (error) {
      console.error(`Rule auto-update failed: ${error.message}`);
    }
  }

  const { rules, packPath, error: rulesError } = loadRules({ config: normalized, cwd });
  if (rulesError) {
    console.error(`Rule pack error (${packPath}): ${rulesError}`);
  }

  const disabledRules = normalized.rules.disable;
  const scanPathsList = resolveScanPaths(options.paths, normalized.paths, cwd);
  const ignore = normalized.ignore;
  const minSeverity = normalizeSeverity(options.minSeverity, normalized.minSeverity);
  const intervalMs = Math.max(1000, Math.floor(options.interval * 1000));

  const seen = new Map();
  const poll = () => {
    const { files } = collectFiles(scanPathsList, ignore);
    files.forEach((filePath) => {
      let stats;
      try {
        stats = fs.statSync(filePath);
      } catch {
        return;
      }
      const signature = `${stats.mtimeMs}:${stats.size}`;
      if (seen.get(filePath) === signature) return;
      seen.set(filePath, signature);
      const result = scanPaths({
        paths: [filePath],
        ignorePatterns: ignore,
        disabledRules,
        rules,
      });
      const findings = result.findings.filter((finding) =>
        severityGte(finding.severity, minSeverity)
      );
      if (findings.length > 0) {
        findings.forEach((finding) => {
          console.log(
            `[WATCH][${finding.severity.toUpperCase()}] ${finding.filePath}:${finding.line} ${finding.ruleId} ${finding.description}`
          );
        });
      }
    });
  };

  poll();
  setInterval(poll, intervalMs);
  console.log(`Watching ${scanPathsList.length} path(s) every ${intervalMs / 1000}s...`);
}

async function maybeAutoUpdateRules(normalizedConfig, cwd, force) {
  if (!normalizedConfig.rules.autoUpdate && !force) return;
  const intervalHours = normalizedConfig.rules.updateIntervalHours || 24;
  const state = loadState();
  const last = state.rulesLastUpdated ? new Date(state.rulesLastUpdated).getTime() : 0;
  const now = Date.now();
  const diffHours = (now - last) / (1000 * 60 * 60);
  if (diffHours < intervalHours) return;

  const url = normalizedConfig.rules.updateUrl || DEFAULT_RULES_URL;
  const destination = resolveRulePackPath(normalizedConfig, cwd);
  await updateRulePack({ url, destination });
  state.rulesLastUpdated = new Date().toISOString();
  saveState(state);
}

async function main() {
  const argv = process.argv.slice(2);
  if (argv.length === 0 || argv.includes("-h") || argv.includes("--help")) {
    printHelp();
    return;
  }

  const command = argv[0];
  if (command === "scan") {
    const { options } = parseArgs(argv.slice(1));
    const exitCode = await runScan(options);
    process.exit(exitCode);
    return;
  }

  if (command === "guard") {
    const guardArgs = argv.slice(1);
    const delimiterIndex = guardArgs.indexOf("--");
    if (delimiterIndex === -1) {
      console.error("Guard mode requires -- before the command to run.");
      process.exit(1);
    }
    const { options } = parseArgs(guardArgs.slice(0, delimiterIndex));
    const commandArgs = guardArgs.slice(delimiterIndex + 1);
    await runGuard(options, commandArgs);
    return;
  }

  if (command === "share") {
    const options = parseShareArgs(argv.slice(1));
    runShare(options);
    return;
  }

  if (command === "update") {
    const options = parseUpdateArgs(argv.slice(1));
    await runUpdate(options);
    return;
  }

  if (command === "rules") {
    const options = parseRulesArgs(argv.slice(1));
    await runRules(options);
    return;
  }

  if (command === "health") {
    runHealth();
    return;
  }

  if (command === "integrity") {
    const options = parseIntegrityArgs(argv.slice(1));
    runIntegrity(options);
    return;
  }

  if (command === "watch") {
    const options = parseWatchArgs(argv.slice(1));
    await runWatch(options);
    return;
  }

  if (command === "version" || command === "--version" || command === "-v") {
    const pkg = require("../package.json");
    console.log(pkg.version);
    return;
  }

  console.error(`Unknown command: ${command}`);
  printHelp();
  process.exit(1);
}

module.exports = { main };
