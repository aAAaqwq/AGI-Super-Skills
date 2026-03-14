const fs = require("fs");
const os = require("os");
const path = require("path");
const https = require("https");
const { RULES } = require("./rules");
const { fileExists, toAbsolute } = require("./utils");

const DEFAULT_RULES_URL = "https://raw.githubusercontent.com/jiangmuran/clawguard/main/rules/rules.json";
const DEFAULT_RULES_PATH = path.join(os.homedir(), ".clawguard", "rules.json");

function ensureDir(filePath) {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
}

function parseRulePack(raw) {
  if (!raw || !Array.isArray(raw.rules)) {
    throw new Error("Invalid rule pack format");
  }
  const rules = raw.rules.map((rule) => {
    if (!rule.id || !rule.pattern || !rule.severity) {
      throw new Error("Invalid rule entry");
    }
    return {
      id: rule.id,
      severity: rule.severity,
      description: rule.description || "",
      regex: new RegExp(rule.pattern, rule.flags || ""),
    };
  });
  return {
    version: raw.version || null,
    updatedAt: raw.updatedAt || null,
    rules,
  };
}

function loadRulePackFromFile(filePath) {
  const raw = fs.readFileSync(filePath, "utf8");
  const parsed = JSON.parse(raw);
  return parseRulePack(parsed);
}

function mergeRules(baseRules, packRules) {
  const map = new Map();
  baseRules.forEach((rule) => map.set(rule.id, rule));
  packRules.forEach((rule) => map.set(rule.id, rule));
  return Array.from(map.values());
}

function resolveRulePackPath(config, cwd) {
  if (config && config.rules && config.rules.packPath) {
    return toAbsolute(config.rules.packPath, cwd);
  }
  return DEFAULT_RULES_PATH;
}

function loadRules({ config, cwd }) {
  const packPath = resolveRulePackPath(config, cwd);
  if (fileExists(packPath)) {
    try {
      const pack = loadRulePackFromFile(packPath);
      return {
        rules: mergeRules(RULES, pack.rules),
        pack,
        packPath,
      };
    } catch (error) {
      return { rules: RULES, pack: null, packPath, error: error.message };
    }
  }
  return { rules: RULES, pack: null, packPath };
}

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers: { "User-Agent": "clawguard" } }, (res) => {
      let data = "";
      res.on("data", (chunk) => { data += chunk; });
      res.on("end", () => {
        if (res.statusCode && res.statusCode >= 200 && res.statusCode < 300) {
          try {
            resolve(JSON.parse(data));
          } catch (error) {
            reject(error);
          }
          return;
        }
        reject(new Error(`HTTP ${res.statusCode || 0}`));
      });
    });
    req.on("error", reject);
  });
}

async function updateRulePack({ url = DEFAULT_RULES_URL, destination = DEFAULT_RULES_PATH }) {
  const data = await fetchJson(url);
  parseRulePack(data);
  ensureDir(destination);
  fs.writeFileSync(destination, JSON.stringify(data, null, 2), "utf8");
  return { destination, version: data.version || null, updatedAt: data.updatedAt || null };
}

module.exports = {
  DEFAULT_RULES_URL,
  DEFAULT_RULES_PATH,
  loadRules,
  resolveRulePackPath,
  updateRulePack,
};
