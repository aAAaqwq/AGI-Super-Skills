const fs = require("fs");
const path = require("path");
const { fileExists, toAbsolute, normalizeSeverity } = require("./utils");

const DEFAULT_CONFIG_FILE = "clawguard.config.json";

function loadConfig(cwd, configPath) {
  const resolvedPath = configPath
    ? toAbsolute(configPath, cwd)
    : path.join(cwd, DEFAULT_CONFIG_FILE);

  if (!fileExists(resolvedPath)) {
    return { configPath: null, config: {} };
  }

  const raw = fs.readFileSync(resolvedPath, "utf8");
  const parsed = JSON.parse(raw);
  return { configPath: resolvedPath, config: parsed || {} };
}

function normalizeConfig(config, cwd) {
  const paths = Array.isArray(config.paths) ? config.paths : [];
  const ignore = Array.isArray(config.ignore) ? config.ignore : [];
  const rules = config.rules && typeof config.rules === "object" ? config.rules : {};
  const rulesConfig = {
    disable: Array.isArray(rules.disable) ? rules.disable : [],
    packPath: typeof rules.packPath === "string" ? rules.packPath : null,
    autoUpdate: Boolean(rules.autoUpdate),
    updateUrl: typeof rules.updateUrl === "string" ? rules.updateUrl : null,
    updateIntervalHours: Number.isFinite(rules.updateIntervalHours)
      ? rules.updateIntervalHours
      : 24,
  };
  return {
    paths: paths.map((item) => toAbsolute(item, cwd)),
    ignore,
    rules: rulesConfig,
    failOn: normalizeSeverity(config.failOn, "high"),
    minSeverity: normalizeSeverity(config.minSeverity, "low"),
  };
}

module.exports = {
  loadConfig,
  normalizeConfig,
  DEFAULT_CONFIG_FILE,
};
