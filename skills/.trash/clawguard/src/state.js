const fs = require("fs");
const os = require("os");
const path = require("path");

const STATE_PATH = path.join(os.homedir(), ".clawguard", "state.json");

function loadState() {
  try {
    const raw = fs.readFileSync(STATE_PATH, "utf8");
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function saveState(state) {
  const dir = path.dirname(STATE_PATH);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(STATE_PATH, JSON.stringify(state, null, 2), "utf8");
}

module.exports = {
  STATE_PATH,
  loadState,
  saveState,
};
