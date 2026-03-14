const fs = require("fs");

function formatSummary(result) {
  const totalFindings = result.findings.length;
  const parts = [
    `Scanned ${result.filesScanned} file(s) in ${result.pathsScanned.length} path(s).`,
    `Findings: high=${result.counts.high}, medium=${result.counts.medium}, low=${result.counts.low}.`,
  ];
  if (totalFindings === 0) {
    parts.push("No findings detected.");
  }
  return parts.join(" ");
}

function formatTextReport(result) {
  const lines = [formatSummary(result)];
  if (result.findings.length > 0) {
    lines.push("Findings:");
    result.findings.forEach((finding) => {
      lines.push(
        `- [${finding.severity.toUpperCase()}] ${finding.filePath}:${finding.line} ${finding.ruleId} - ${finding.description}`
      );
    });
  }

  if (result.errors.length > 0) {
    lines.push("Errors:");
    result.errors.forEach((item) => {
      lines.push(`- ${item.path}: ${item.error}`);
    });
  }

  if (result.skipped.length > 0) {
    lines.push("Skipped:");
    result.skipped.forEach((item) => {
      lines.push(`- ${item.filePath}: ${item.reason}`);
    });
  }

  return lines.join("\n");
}

function formatJsonReport(result) {
  return JSON.stringify(result, null, 2);
}

function writeReport(outputPath, content) {
  fs.writeFileSync(outputPath, content, "utf8");
}

module.exports = {
  formatTextReport,
  formatJsonReport,
  writeReport,
};
