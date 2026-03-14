const crypto = require("crypto");
const fs = require("fs");
const os = require("os");
const path = require("path");
const { collectFiles } = require("./scanner");
const { toAbsolute } = require("./utils");

const BASELINE_PATH = path.join(os.homedir(), ".clawguard", "baselines.json");
const MAX_HASH_SIZE = 50 * 1024 * 1024;

function loadBaselines() {
  try {
    const raw = fs.readFileSync(BASELINE_PATH, "utf8");
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function saveBaselines(data) {
  fs.mkdirSync(path.dirname(BASELINE_PATH), { recursive: true });
  fs.writeFileSync(BASELINE_PATH, JSON.stringify(data, null, 2), "utf8");
}

function hashFile(filePath) {
  const stats = fs.statSync(filePath);
  if (stats.size > MAX_HASH_SIZE) {
    return null;
  }
  const hash = crypto.createHash("sha256");
  const contents = fs.readFileSync(filePath);
  hash.update(contents);
  return hash.digest("hex");
}

function buildSnapshot(rootPath, ignorePatterns) {
  const { files, errors } = collectFiles([rootPath], ignorePatterns, { includeAll: true });
  const root = path.resolve(rootPath);
  const snapshot = {
    root,
    generatedAt: new Date().toISOString(),
    files: {},
    skipped: [],
    errors,
  };

  files.forEach((filePath) => {
    const hash = hashFile(filePath);
    let relative = path.relative(root, filePath);
    if (!relative) {
      relative = path.basename(filePath);
    }
    if (!hash) {
      snapshot.skipped.push(relative);
      return;
    }
    snapshot.files[relative] = hash;
  });

  return snapshot;
}

function initBaseline(paths, ignorePatterns, cwd) {
  const baselines = loadBaselines();
  const created = [];
  paths.forEach((inputPath) => {
    const absolute = toAbsolute(inputPath, cwd);
    const snapshot = buildSnapshot(absolute, ignorePatterns);
    baselines[absolute] = snapshot;
    created.push({ path: absolute, files: Object.keys(snapshot.files).length });
  });
  saveBaselines(baselines);
  return { created };
}

function compareSnapshots(previous, current) {
  const added = [];
  const removed = [];
  const modified = [];

  const prevFiles = previous.files || {};
  const currFiles = current.files || {};

  Object.keys(currFiles).forEach((file) => {
    if (!prevFiles[file]) {
      added.push(file);
    } else if (prevFiles[file] !== currFiles[file]) {
      modified.push(file);
    }
  });

  Object.keys(prevFiles).forEach((file) => {
    if (!currFiles[file]) {
      removed.push(file);
    }
  });

  return { added, removed, modified };
}

function checkBaseline(paths, ignorePatterns, cwd) {
  const baselines = loadBaselines();
  const results = [];
  paths.forEach((inputPath) => {
    const absolute = toAbsolute(inputPath, cwd);
    const baseline = baselines[absolute];
    if (!baseline) {
      results.push({ path: absolute, error: "no baseline found" });
      return;
    }
    const snapshot = buildSnapshot(absolute, ignorePatterns);
    const diff = compareSnapshots(baseline, snapshot);
    results.push({
      path: absolute,
      diff,
      skipped: snapshot.skipped,
      errors: snapshot.errors,
    });
  });
  return results;
}

module.exports = {
  BASELINE_PATH,
  initBaseline,
  checkBaseline,
};
