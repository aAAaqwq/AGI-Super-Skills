/**
 * Claude Code Control Skill v2 — REAL IMPLEMENTATION
 * Actually controls Claude Code interactive process
 * Not just a shell wrapper
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// Global session map
const sessions = new Map();
let sessionCounter = 0;

/**
 * Launch a real Claude Code interactive session
 */
async function launch(projectPath, options = {}) {
  const sessionId = ++sessionCounter;
  const normalizedPath = path.resolve(projectPath);

  if (!fs.existsSync(normalizedPath)) {
    throw new Error(`Project path does not exist: ${normalizedPath}`);
  }

  console.log(`[CC-${sessionId}] Launching Claude Code at ${normalizedPath}`);

  // Spawn Claude Code as interactive process
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
    outputBuffer: '',
    sessionReady: false,
    waitingForPrompt: false,
  };

  // Capture ALL output from Claude Code
  proc.stdout.on('data', (data) => {
    const chunk = data.toString();
    session.outputBuffer += chunk;
    console.log(`[CC-${sessionId}] [STDOUT] ${chunk}`);
  });

  proc.stderr.on('data', (data) => {
    const chunk = data.toString();
    console.log(`[CC-${sessionId}] [STDERR] ${chunk}`);
  });

  // Wait for Claude Code to start and show prompt
  await new Promise((resolve) => {
    setTimeout(() => {
      // Send security approval (option 1)
      proc.stdin.write('1\n');
      setTimeout(() => {
        // Confirm
        proc.stdin.write('\n');
        session.sessionReady = true;
        console.log(`[CC-${sessionId}] ✅ Claude Code interactive session started`);
        resolve();
      }, 500);
    }, 1000);
  });

  sessions.set(sessionId, session);
  return sessionId;
}

/**
 * Send a command directly to Claude Code's interactive session
 */
async function send(sessionId, command, timeoutSeconds = 300) {
  const session = sessions.get(sessionId);
  if (!session) {
    throw new Error(`Invalid session: ${sessionId}`);
  }

  if (!session.sessionReady) {
    throw new Error(`Session not ready: ${sessionId}`);
  }

  const startTime = Date.now();
  session.commandCount++;

  console.log(`[CC-${sessionId}] > SENDING TO CLAUDE CODE: ${command}`);

  // Clear output buffer for this command
  session.outputBuffer = '';

  // Send command to Claude Code's stdin
  session.proc.stdin.write(command + '\n');

  // Wait for response (with timeout)
  let response = '';
  const waitForResponse = () =>
    new Promise((resolve) => {
      const checkInterval = setInterval(() => {
        const now = Date.now();
        
        // Check if we got a prompt back (indicates command completed)
        if (session.outputBuffer.includes('❯') || 
            now - startTime > timeoutSeconds * 1000) {
          clearInterval(checkInterval);
          response = session.outputBuffer;
          resolve();
        }
      }, 100);
    });

  await waitForResponse();

  const duration = Date.now() - startTime;

  const result = {
    sessionId,
    command,
    output: response,
    duration_ms: duration,
    status: response.includes('error') || response.includes('Error') ? 'error' : 'success',
  };

  console.log(`[CC-${sessionId}] ✅ Response received (${duration}ms)`);

  return result;
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
    running: session.proc && !session.proc.killed,
    uptime_ms: Date.now() - session.created_at,
    commands_sent: session.commandCount,
    ready: session.sessionReady,
  };
}

/**
 * Close Claude Code session
 */
async function close(sessionId) {
  const session = sessions.get(sessionId);
  if (!session) return;

  console.log(`[CC-${sessionId}] Closing Claude Code session`);

  if (session.proc && !session.proc.killed) {
    // Send exit command to Claude Code
    session.proc.stdin.write('exit\n');

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

process.on('exit', () => {
  closeAll().catch(console.error);
});

module.exports = {
  launch,
  send,
  getStatus,
  close,
  closeAll,
};
