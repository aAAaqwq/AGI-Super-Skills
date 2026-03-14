const fs = require("fs");
const path = require("path");
const os = require("os");

const SEVERITY_ORDER = {
  low: 1,
  medium: 2,
  high: 3,
};

function expandHome(inputPath) {
  if (!inputPath || typeof inputPath !== "string") return inputPath;
  if (inputPath === "~") return os.homedir();
  if (inputPath.startsWith("~/")) {
    return path.join(os.homedir(), inputPath.slice(2));
  }
  return inputPath;
}

function toAbsolute(inputPath, baseDir) {
  const expanded = expandHome(inputPath);
  if (path.isAbsolute(expanded)) return expanded;
  return path.join(baseDir, expanded);
}

function normalizeSeverity(value, fallback) {
  if (!value) return fallback;
  const lowered = String(value).toLowerCase();
  if (SEVERITY_ORDER[lowered]) return lowered;
  return fallback;
}

function severityGte(left, right) {
  return SEVERITY_ORDER[left] >= SEVERITY_ORDER[right];
}

function fileExists(filePath) {
  try {
    fs.accessSync(filePath, fs.constants.F_OK);
    return true;
  } catch {
    return false;
  }
}

module.exports = {
  SEVERITY_ORDER,
  expandHome,
  toAbsolute,
  normalizeSeverity,
  severityGte,
  fileExists,
};
