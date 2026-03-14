const assert = require("assert");
const path = require("path");
const { scanPaths } = require("../src/scanner");

const fixtures = path.join(__dirname, "fixtures");
const result = scanPaths({
  paths: [fixtures],
  ignorePatterns: [],
});

const hasExec = result.findings.some((finding) => finding.ruleId === "EXEC");
assert.ok(hasExec, "Expected EXEC finding in fixtures");
assert.ok(result.filesScanned >= 2, "Expected at least two files scanned");

console.log("Tests passed.");
