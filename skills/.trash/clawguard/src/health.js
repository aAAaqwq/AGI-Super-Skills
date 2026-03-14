const fs = require("fs");
const os = require("os");
const path = require("path");

function isWorldWritable(stats) {
  return (stats.mode & 0o002) !== 0;
}

function isGroupWritable(stats) {
  return (stats.mode & 0o020) !== 0;
}

function checkPath(targetPath, options = {}) {
  const findings = [];
  const { required = false, checkWritable = true, label = null } = options;
  try {
    const stats = fs.lstatSync(targetPath);
    if (stats.isSymbolicLink()) {
      findings.push({
        path: targetPath,
        severity: "medium",
        message: `${label || targetPath} is a symlink`,
      });
    }
    if (checkWritable && (isWorldWritable(stats) || isGroupWritable(stats))) {
      findings.push({
        path: targetPath,
        severity: "high",
        message: `${label || targetPath} is writable by group/world`,
      });
    }
  } catch (error) {
    if (required) {
      findings.push({
        path: targetPath,
        severity: "medium",
        message: `${label || targetPath} is missing`,
      });
    }
  }
  return findings;
}

function runHealthChecks() {
  const home = os.homedir();
  const checks = [
    { path: path.join(home, ".ssh"), required: false, label: "~/.ssh" },
    { path: path.join(home, ".ssh", "authorized_keys"), required: false, label: "~/.ssh/authorized_keys" },
    { path: path.join(home, ".gnupg"), required: false, label: "~/.gnupg" },
    { path: path.join(home, ".openclaw"), required: false, label: "~/.openclaw" },
    { path: path.join(home, ".openclaw", "openclaw.json"), required: false, label: "~/.openclaw/openclaw.json" },
    { path: path.join(home, ".zshrc"), required: false, label: "~/.zshrc" },
    { path: path.join(home, ".bashrc"), required: false, label: "~/.bashrc" },
    { path: path.join(home, ".profile"), required: false, label: "~/.profile" },
  ];

  if (process.platform !== "win32") {
    checks.push(
      { path: "/etc/sudoers", required: true, label: "/etc/sudoers" },
      { path: "/etc/ssh/sshd_config", required: false, label: "/etc/ssh/sshd_config" }
    );
  }

  const findings = [];
  checks.forEach((item) => {
    findings.push(...checkPath(item.path, item));
  });

  const counts = { low: 0, medium: 0, high: 0 };
  findings.forEach((finding) => {
    counts[finding.severity] += 1;
  });

  return { findings, counts };
}

module.exports = {
  runHealthChecks,
};
