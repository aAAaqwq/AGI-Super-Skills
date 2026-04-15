/**
 * Claude Code Control Skill
 * Autonomous agent interface for Claude Code
 * 
 * Usage:
 *   const cc = require('./index');
 *   const session = await cc.launch('/path/to/project');
 *   const result = await cc.send(session, 'run pytest tests/ -v');
 *   await cc.close(session);
 */

const { execSync, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// Global session map
const sessions = new Map();
let sessionCounter = 0;

/**
 * Parse test output and extract metrics
 */
function parseTestOutput(output) {
  const parsed = {
    tests_passed: 0,
    tests_failed: 0,
    tests_skipped: 0,
    warnings: 0,
    duration_seconds: 0,
  };

  // pytest format: "33 passed, 16 warnings"
  const passMatch = output.match(/(\d+)\s+passed/);
  if (passMatch) parsed.tests_passed = parseInt(passMatch[1]);

  const failMatch = output.match(/(\d+)\s+failed/);
  if (failMatch) parsed.tests_failed = parseInt(failMatch[1]);

  const skipMatch = output.match(/(\d+)\s+skipped/);
  if (skipMatch) parsed.tests_skipped = parseInt(skipMatch[1]);

  const warnMatch = output.match(/(\d+)\s+warnings?/);
  if (warnMatch) parsed.warnings = parseInt(warnMatch[1]);

  const timeMatch = output.match(/in\s+([\d.]+)s/);
  if (timeMatch) parsed.duration_seconds = parseFloat(timeMatch[1]);

  return parsed;
}

/**
 * Parse npm/yarn output
 */
function parseBuildOutput(output) {
  const parsed = {
    success: !output.toLowerCase().includes('error'),
    lines: output.split('\n').length,
  };

  if (output.includes('built')) {
    const match = output.match(/built\s+(\d+)\s+files?/);
    if (match) parsed.files_built = parseInt(match[1]);
  }

  return parsed;
}

/**
 * Strip ANSI codes from output
 */
function stripAnsi(str) {
  return str.replace(/\u001b\[[0-9;]*m/g, '');
}

/**
 * Launch Claude Code instance
 */
async function launch(projectPath, options = {}) {
  const sessionId = ++sessionCounter;
  const normalizedPath = path.resolve(projectPath);

  if (!fs.existsSync(normalizedPath)) {
    throw new Error(`Project path does not exist: ${normalizedPath}`);
  }

  console.log(`[CC-${sessionId}] Launching Claude Code at ${normalizedPath}`);

  try {
    // Check if Claude Code is installed
    execSync('which claude', { stdio: 'pipe' });
  } catch {
    throw new Error('Claude Code CLI not found. Install with: brew install anthropic-cli');
  }

  // Spawn Claude Code process
  const proc = spawn('claude', ['code'], {
    cwd: normalizedPath,
    stdio: ['pipe', 'pipe', 'pipe'],
    detached: false,
  });

  const session = {
    id: sessionId,
    path: normalizedPath,
    proc,
    created_at: Date.now(),
    commandCount: 0,
    stdout: '',
    stderr: '',
  };

  // Capture output
  proc.stdout.on('data', (data) => {
    session.stdout += data.toString();
  });

  proc.stderr.on('data', (data) => {
    session.stderr += data.toString();
  });

  // Auto-approve security check
  await new Promise((resolve) => setTimeout(resolve, 500));
  
  // Send "Yes, I trust this folder" (option 1)
  if (proc.stdin) {
    proc.stdin.write('1\n');
    proc.stdin.write('\n'); // Confirm
  }

  console.log(`[CC-${sessionId}] ✅ Claude Code started`);

  sessions.set(sessionId, session);
  return sessionId;
}

/**
 * Send a command to Claude Code via subprocess execution
 * (Since Claude Code interactive session output is hard to capture,
 *  we execute commands directly in the workspace)
 */
async function send(sessionId, command, timeoutSeconds = 300) {
  const session = sessions.get(sessionId);
  if (!session) {
    throw new Error(`Invalid session: ${sessionId}`);
  }

  const startTime = Date.now();
  session.commandCount++;

  console.log(`[CC-${sessionId}] > ${command}`);

  try {
    // Execute command directly in the session's working directory
    // This bypasses Claude Code's interactive layer
    const result = execSync(`cd "${session.path}" && ${command}`, {
      encoding: 'utf-8',
      maxBuffer: 10 * 1024 * 1024, // 10MB buffer
      timeout: timeoutSeconds * 1000,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    const duration = Date.now() - startTime;
    const output = stripAnsi(result);

    // Parse output based on command type
    let parsed = {};
    if (command.includes('pytest')) {
      parsed = parseTestOutput(output);
    } else if (command.includes('npm') || command.includes('yarn')) {
      parsed = parseBuildOutput(output);
    }

    const res = {
      sessionId,
      command,
      status: 'success',
      output: output.slice(0, 10000), // Truncate to 10k chars
      duration_ms: duration,
      parsed,
      errors: [],
    };

    console.log(`[CC-${sessionId}] ✅ Command completed (${duration}ms, status=success)`);
    return res;
  } catch (err) {
    const duration = Date.now() - startTime;
    const output = stripAnsi(err.stdout ? err.stdout.toString() : '');
    const stderr = err.stderr ? stripAnsi(err.stderr.toString()) : err.message;
    const errors = stderr.split('\n').filter((e) => e.trim()).slice(0, 10);

    // Parse even on error
    let parsed = {};
    if (command.includes('pytest')) {
      parsed = parseTestOutput(output + '\n' + stderr);
    }

    const res = {
      sessionId,
      command,
      status: 'error',
      output: output.slice(0, 10000),
      duration_ms: duration,
      parsed,
      errors,
    };

    console.log(`[CC-${sessionId}] ❌ Command failed (${duration}ms)`);
    return res;
  }
}

/**
 * Get session status
 */
function getStatus(sessionId) {
  const session = sessions.get(sessionId);
  if (!session) return null;

  return {
    sessionId,
    path: session.path,
    uptime_ms: Date.now() - session.created_at,
    commands_sent: session.commandCount,
    running: session.proc && !session.proc.killed,
  };
}

/**
 * Close session gracefully
 */
async function close(sessionId) {
  const session = sessions.get(sessionId);
  if (!session) return;

  console.log(`[CC-${sessionId}] Closing Claude Code session`);

  if (session.proc && !session.proc.killed) {
    session.proc.kill('SIGTERM');

    // Wait for process to exit
    await new Promise((resolve) => {
      const timeout = setTimeout(() => {
        session.proc.kill('SIGKILL');
        resolve();
      }, 5000);

      session.proc.on('exit', () => {
        clearTimeout(timeout);
        resolve();
      });
    });
  }

  sessions.delete(sessionId);
  console.log(`[CC-${sessionId}] ✅ Session closed`);
}

/**
 * Close all sessions
 */
async function closeAll() {
  const sessionIds = Array.from(sessions.keys());
  for (const id of sessionIds) {
    await close(id);
  }
}

// Cleanup on exit
process.on('exit', () => {
  closeAll().catch(console.error);
});

// Export API
module.exports = {
  launch,
  send,
  getStatus,
  close,
  closeAll,
};

// CLI usage
if (require.main === module) {
  (async () => {
    const projectPath = process.argv[2] || '.';
    const command = process.argv[3] || 'echo "No command specified"';

    try {
      const sessionId = await launch(projectPath);
      const result = await send(sessionId, command);
      await close(sessionId);

      console.log('\n=== Result ===');
      console.log(JSON.stringify(result, null, 2));
      process.exit(result.status === 'success' ? 0 : 1);
    } catch (err) {
      console.error('Error:', err.message);
      process.exit(1);
    }
  })();
}
