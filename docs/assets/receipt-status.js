((root) => {
  "use strict";

  function isVerifiedReceipt(receipt) {
    if (!receipt || receipt.schemaVersion !== 1 || receipt.result !== "passed") return false;
    if (!/^[0-9a-f]{40}$/.test(receipt.commit || "")) return false;
    if (receipt.siteCommit !== receipt.commit) return false;
    if (typeof receipt.fixture !== "string" || receipt.fixture.length === 0) return false;
    if (!Array.isArray(receipt.checks) || receipt.checks.length === 0) return false;
    return receipt.checks.every(
      (check) => check && typeof check.name === "string" && check.name.length > 0
        && check.result === "passed"
    );
  }

  root.AGISuperTeamReceipt = Object.freeze({ isVerifiedReceipt });
})(globalThis);
