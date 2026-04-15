/**
 * route-task.js — Generic task router for Claude Code sessions
 *
 * Module API:
 *   const { routeTask } = require('./tasks/route-task');
 *   const result = await routeTask(projectPath, taskDescription, opts);
 *   // result → { sessionId, screenshot, recordingPath, duration_ms }
 *
 * CLI:
 *   node tasks/route-task.js --project /path/to/project --task "description" [--wait 120] [--approve]
 */
const path = require('path');
const fs = require('fs');
const cc = require('../index');

/**
 * Route a task to Claude Code in a managed session.
 *
 * @param {string} projectPath - Absolute path to the project directory
 * @param {string} taskDescription - Task to send to Claude Code
 * @param {object} opts
 * @param {number}  [opts.waitSeconds=120]  - Seconds to wait after sending task
 * @param {boolean} [opts.approve=false]    - Approve security prompt before task
 * @param {string}  [opts.sessionDir=null]  - Directory for session recordings
 * @returns {Promise<{ sessionId, screenshot, recordingPath, duration_ms }>}
 */
async function routeTask(projectPath, taskDescription, opts = {}) {
  const startTime = Date.now();
  const waitSeconds = opts.waitSeconds ?? 120;
  const shouldApprove = opts.approve ?? false;
  const sessionDir = opts.sessionDir
    ? path.resolve(opts.sessionDir)
    : path.join(__dirname, 'sessions');

  // Ensure sessions directory exists
  if (!fs.existsSync(sessionDir)) {
    fs.mkdirSync(sessionDir, { recursive: true });
  }

  // Launch
  const sessionId = await cc.launch(projectPath);
  console.log(`[route-task] Session ${sessionId} launched`);

  // Optional security approval
  if (shouldApprove) {
    await new Promise(r => setTimeout(r, 3000));
    await cc.approveSecurity(sessionId);
    console.log(`[route-task] Security approved`);
  }

  // Send task
  console.log(`[route-task] Sending task (wait=${waitSeconds}s)...`);
  const sendResult = await cc.send(sessionId, taskDescription, waitSeconds);

  // Final screenshot
  const screenshotPath = `/tmp/route-task-final-${sessionId}-${Date.now()}.png`;
  const screenshot = cc.takeScreenshot(screenshotPath);

  // Save session recording
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const recordingPath = path.join(sessionDir, `session-${sessionId}-${timestamp}.json`);
  await cc.saveSession(sessionId, recordingPath);

  // Close session
  await cc.close(sessionId);

  const duration_ms = Date.now() - startTime;
  console.log(`[route-task] Done in ${duration_ms}ms`);

  return { sessionId, screenshot: screenshot || sendResult.screenshot, recordingPath, duration_ms };
}

// ─── CLI entrypoint ──────────────────────────────────────────
if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
Usage: node tasks/route-task.js --project <path> --task <description> [options]

Options:
  --project <path>   Path to the project directory (required)
  --task <text>      Task description to send to Claude Code (required)
  --wait <seconds>   Seconds to wait for task completion (default: 120)
  --approve          Approve the security prompt before sending the task
  --session-dir <p>  Directory to save session recordings (default: tasks/sessions/)
  --help             Show this help message
`);
    process.exit(0);
  }

  function getArg(flag) {
    const idx = args.indexOf(flag);
    return idx !== -1 ? args[idx + 1] : null;
  }

  const projectPath = getArg('--project');
  const taskDescription = getArg('--task');
  const waitArg = getArg('--wait');
  const approve = args.includes('--approve');
  const sessionDir = getArg('--session-dir');

  if (!projectPath || !taskDescription) {
    console.error('Error: --project and --task are required');
    console.error('Run with --help for usage');
    process.exit(1);
  }

  routeTask(projectPath, taskDescription, {
    waitSeconds: waitArg ? Number(waitArg) : 120,
    approve,
    sessionDir,
  })
    .then(result => {
      console.log('\nResult:');
      console.log(JSON.stringify(result, null, 2));
    })
    .catch(err => {
      console.error('Error:', err.message);
      process.exit(1);
    });
}

module.exports = { routeTask };
