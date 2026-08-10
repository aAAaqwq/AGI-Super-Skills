import { existsSync } from "node:fs";
import { basename, dirname, join, relative, resolve } from "node:path";
import { safeRoot } from "./core.mjs";

const OPENCLAW_CONFIG_NAMES = ["openclaw.json", "clawdbot.json"];

function configured(environment, name) {
  const value = environment[name]?.trim();
  return value || null;
}

function resolveHomePath(value, home) {
  if (value === "~") return resolve(home);
  if (value.startsWith("~/") || value.startsWith("~\\")) {
    return resolve(home, value.slice(2));
  }
  return resolve(value);
}

function samePath(left, right) {
  return relative(resolve(left), resolve(right)) === "";
}

function safeConfigPath(path) {
  const directory = safeRoot(dirname(path), "OpenClaw config directory");
  return join(directory, basename(path));
}

function requireAlignedExplicitHome(name, actual, expected) {
  if (!samePath(actual, expected)) {
    throw new Error(`--home conflicts with ${name}: ${actual}`);
  }
}

function defaultHermesHome(home, environment, runtimePlatform, homeExplicit) {
  if (runtimePlatform !== "win32") return join(home, ".hermes");
  const localAppData = !homeExplicit && configured(environment, "LOCALAPPDATA");
  return localAppData
    ? join(resolveHomePath(localAppData, home), "hermes")
    : join(home, "AppData", "Local", "hermes");
}

export function resolveHermesHome({
  home,
  homeExplicit = false,
  environment = process.env,
  runtimePlatform = process.platform,
}) {
  const fallback = defaultHermesHome(home, environment, runtimePlatform, homeExplicit);
  const override = configured(environment, "HERMES_HOME");
  const target = override ? resolveHomePath(override, home) : fallback;
  if (homeExplicit && override) {
    requireAlignedExplicitHome("HERMES_HOME", target, fallback);
  }
  return safeRoot(target, "Hermes home");
}

function firstExistingConfig(effectiveHome, stateDir, stateOverride) {
  const directories = stateOverride
    ? [stateDir]
    : [join(effectiveHome, ".openclaw"), join(effectiveHome, ".clawdbot")];
  for (const directory of directories) {
    for (const filename of OPENCLAW_CONFIG_NAMES) {
      const candidate = join(directory, filename);
      if (existsSync(candidate)) return candidate;
    }
  }
  return null;
}

export function resolveOpenClawRoots({
  home,
  homeExplicit = false,
  environment = process.env,
}) {
  const homeOverride = configured(environment, "OPENCLAW_HOME");
  const effectiveHome = homeOverride ? resolveHomePath(homeOverride, home) : resolve(home);
  if (homeExplicit && homeOverride) {
    requireAlignedExplicitHome("OPENCLAW_HOME", effectiveHome, home);
  }

  const defaultStateDir = join(effectiveHome, ".openclaw");
  const stateOverride = configured(environment, "OPENCLAW_STATE_DIR");
  const stateDir = stateOverride
    ? resolveHomePath(stateOverride, effectiveHome)
    : defaultStateDir;
  if (homeExplicit && stateOverride) {
    requireAlignedExplicitHome("OPENCLAW_STATE_DIR", stateDir, defaultStateDir);
  }

  const configOverride = configured(environment, "OPENCLAW_CONFIG_PATH");
  const discoveredConfig = firstExistingConfig(effectiveHome, stateDir, stateOverride);
  const configPath = safeConfigPath(
    configOverride
      ? resolveHomePath(configOverride, effectiveHome)
      : discoveredConfig || join(stateDir, "openclaw.json"),
  );
  if (homeExplicit && configOverride) {
    requireAlignedExplicitHome("OPENCLAW_CONFIG_PATH", configPath, join(defaultStateDir, "openclaw.json"));
  }

  // OpenClaw v2026.6.8 resolves its managed-skill/config directory from an
  // explicit state directory first, then dirname(OPENCLAW_CONFIG_PATH), then
  // the default state directory. OPENCLAW_PROFILE alone does not project paths;
  // the upstream --profile option materializes state/config overrides itself.
  const configDir = stateOverride
    ? stateDir
    : configOverride
      ? dirname(configPath)
      : defaultStateDir;

  return {
    effectiveHome: safeRoot(effectiveHome, "OpenClaw home"),
    stateDir: safeRoot(stateDir, "OpenClaw state directory"),
    configDir: safeRoot(configDir, "OpenClaw config directory"),
    configPath,
  };
}

export function configureHarnessRoots({
  tools,
  home,
  homeExplicit = false,
  environment = process.env,
  runtimePlatform = process.platform,
}) {
  return tools.map((tool) => {
    if (tool.id === "hermes") {
      return {
        ...tool,
        installationRoot: resolveHermesHome({
          home,
          homeExplicit,
          environment,
          runtimePlatform,
        }),
      };
    }
    if (tool.id === "openclaw") {
      const roots = resolveOpenClawRoots({home, homeExplicit, environment});
      return {
        ...tool,
        installationRoot: roots.configDir,
        effectiveHome: roots.effectiveHome,
        stateDir: roots.stateDir,
        configPath: roots.configPath,
      };
    }
    return tool;
  });
}
