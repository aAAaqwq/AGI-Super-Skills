const rulesData = require("../rules/rules.json");

const RULES = rulesData.rules.map((rule) => ({
  ...rule,
  regex: new RegExp(rule.pattern, rule.flags || ""),
}));

module.exports = {
  RULES,
};
