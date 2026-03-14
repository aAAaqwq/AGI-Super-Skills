const fs = require("fs");
const path = require("path");
const https = require("https");
const { spawn } = require("child_process");
const { resolveRepo } = require("./repo");

function readPackage(cwd) {
  const pkgPath = path.join(cwd, "package.json");
  const raw = fs.readFileSync(pkgPath, "utf8");
  return JSON.parse(raw);
}

function fetchJson(url, headers = {}) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, { headers }, (res) => {
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

async function fetchLatestRelease(repo) {
  const url = `https://api.github.com/repos/${repo.owner}/${repo.name}/releases/latest`;
  const data = await fetchJson(url, { "User-Agent": "clawguard" });
  if (!data || !data.tag_name) return null;
  return {
    version: String(data.tag_name).replace(/^v/, ""),
    url: data.html_url || repo.url,
    source: "github",
  };
}

async function fetchLatestNpmVersion(pkgName) {
  const url = `https://registry.npmjs.org/${pkgName}/latest`;
  const data = await fetchJson(url, { "User-Agent": "clawguard" });
  if (!data || !data.version) return null;
  return {
    version: String(data.version),
    url: data.homepage || `https://www.npmjs.com/package/${pkgName}`,
    source: "npm",
  };
}

function compareVersions(current, latest) {
  const normalize = (value) => String(value).split(".").map((part) => parseInt(part, 10) || 0);
  const left = normalize(current);
  const right = normalize(latest);
  const max = Math.max(left.length, right.length);
  for (let i = 0; i < max; i += 1) {
    const diff = (right[i] || 0) - (left[i] || 0);
    if (diff !== 0) return diff > 0 ? -1 : 1;
  }
  return 0;
}

async function checkUpdate({ cwd, repoOverride }) {
  const pkg = readPackage(cwd);
  const repo = resolveRepo({
    cliRepo: repoOverride,
    envRepo: process.env.CLAWGUARD_REPO,
    pkgRepo: pkg.repository && pkg.repository.url ? pkg.repository.url : pkg.repository,
  });

  let latest = null;
  let errors = [];
  if (repo) {
    try {
      latest = await fetchLatestRelease(repo);
    } catch (error) {
      errors.push(`GitHub: ${error.message}`);
    }
  }

  if (!latest) {
    try {
      latest = await fetchLatestNpmVersion(pkg.name);
    } catch (error) {
      errors.push(`npm: ${error.message}`);
    }
  }

  return {
    current: pkg.version,
    latest,
    repo,
    errors,
  };
}

function runCommand(command, args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: "inherit", cwd });
    child.on("exit", (code) => {
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`${command} exited with code ${code}`));
      }
    });
  });
}

async function applyUpdate({ cwd, method, pkgName }) {
  if (method === "npm") {
    await runCommand("npm", ["install", "-g", `${pkgName}@latest`], cwd);
    return "npm";
  }

  const gitDir = path.join(cwd, ".git");
  if (method === "git" && !fs.existsSync(gitDir)) {
    throw new Error("git update requested but .git was not found");
  }

  if (fs.existsSync(gitDir)) {
    await runCommand("git", ["pull", "--rebase"], cwd);
    await runCommand("npm", ["install"], cwd);
    return "git";
  }

  await runCommand("npm", ["install", "-g", `${pkgName}@latest`], cwd);
  return "npm";
}

module.exports = {
  checkUpdate,
  compareVersions,
  applyUpdate,
};
