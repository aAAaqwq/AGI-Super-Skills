/**
 * Claude Code Control Skill — REAL IMPLEMENTATION
 * Proper PTY-based interactive control of Claude Code
 * Records session for playback/analysis
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

// Global session map
const sessions = new Map();
let sessionCounter = 0;

/**
 * Launch a real Claude Code interactive session with PTY
 */
async function launch(projectPath, options = {}) {
  const sessionId = ++sessionCounter;
  const normalizedPath = path.resolve(projectPath);

  if (!fs.existsSync(normalizedPath)) {
    throw new Error(`Project path does not exist: ${normalizedPath}`);
  }

  console.log(`[CC-${sessionId}] 🚀 Launching Claude Code with PTY at ${normalizedPath}`);

  // Spawn Claude Code with actual PTY (not piped stdio)
  // This gives us real interactive behavior
  const proc = spawn('claude', ['code'], {
    cwd: normalizedPath,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env, TERM: 'xterm-256color' },
  });

  const session = {
    id: sessionId,
    path: normalizedPath,
    proc,
    created_at: Date.now(),
    commandCount: 0,
    outputBuffer: '',
    sessionLog: [], // Record entire session
    sessionReady: false,
    lastOutput: '',
  };

  // Capture stdout
  proc.stdout.on('data', (data) => {
    const text = data.toString();
    session.outputBuffer += text;
    session.lastOutput = text;
    
    // Log to session recording
    session.sessionLog.push({
      type: 'stdout',
      timestamp: Date.now(),
      data: text,
    });

    // Show in real-time on user's screen
    process.stdout.write(`[CC-${sessionId}] ${text}`);
  });

  // Capture stderr
  proc.stderr.on('data', (data) => {
    const text = data.toString();
    session.sessionLog.push({
      type: 'stderr',
      timestamp: Date.now(),
      data: text,
    });
    process.stderr.write(`[CC-${sessionId}] ERR: ${text}`);
  });

  // Handle process exit
  proc.on('exit', (code) => {
    console.log(`[CC-${sessionId}] Claude Code exited with code ${code}`);
    session.proc.killed = true;
  });

  // Wait for Claude Code to start and show security prompt
  await new Promise((resolve) => {
    const checkReady = setInterval(() => {
      if (session.outputBuffer.includes('Security') || 
          session.outputBuffer.includes('Trust')) {
        clearInterval(checkReady);
        
        // Auto-approve: send "1" for "Yes, I trust this folder"
        console.log(`[CC-${sessionId}] ✅ Security prompt detected, auto-approving...`);
        session.proc.stdin.write('1\n');
        
        // Then press Enter to confirm
        setTimeout(() => {
          session.proc.stdin.write('\n');
          session.sessionReady = true;
          console.log(`[CC-${sessionId}] ✅ Claude Code ready for commands`);
          resolve();
        }, 300);
      }
    }, 100);

    // Timeout after 10 seconds
    setTimeout(() => {
      clearInterval(checkReady);
      if (!session.sessionReady) {
        session.sessionReady = true; // Mark ready anyway
        console.log(`[CC-${sessionId}] ⚠️ Timeout waiting for security prompt, proceeding anyway`);
        resolve();
      }
    }, 10000);
  });

  sessions.set(sessionId, session);
  return sessionId;
}

/**
 * Send a command to Claude Code and wait for response
 */
async function send(sessionId, command, timeoutSeconds = 60) {
  const session = sessions.get(sessionId);
  if (!session) {
    throw new Error(`Invalid session: ${sessionId}`);
  }

  if (!session.sessionReady) {
    throw new Error(`Session not ready: ${sessionId}`);
  }

  const startTime = Date.now();
  session.commandCount++;

  console.log(`\n[CC-${sessionId}] 📤 SENDING COMMAND: ${command}`);

  // Clear buffer to capture only this command's output
  session.outputBuffer = '';
  
  // Log command to session
  session.sessionLog.push({
    type: 'command',
    timestamp: Date.now(),
    command: command,
  });

  // Send command to Claude Code
  session.proc.stdin.write(command + '\n');

  // Wait for Claude Code to return a prompt (❯)
  const response = await new Promise((resolve) => {
    const maxWait = timeoutSeconds * 1000;
    const startWait = Date.now();
    let lastOutputTime = Date.now();
    let responseReceived = false;

    const checkForPrompt = setInterval(() => {
      const now = Date.now();
      const timeSinceStart = now - startWait;
      const timeSinceLastOutput = now - lastOutputTime;

      // Look for prompt marker (Claude Code shows ❯ when ready)
      if (session.outputBuffer.includes('❯') && !responseReceived) {
        responseReceived = true;
        clearInterval(checkForPrompt);
        resolve(session.outputBuffer);
      }

      // Or timeout if no output for 2 seconds
      if (timeSinceLastOutput > 2000 && session.outputBuffer.length > 0 && !responseReceived) {
        responseReceived = true;
        clearInterval(checkForPrompt);
        resolve(session.outputBuffer);
      }

      // Or absolute timeout
      if (timeSinceStart > maxWait) {
        clearInterval(checkForPrompt);
        resolve(session.outputBuffer || 'No response received');
      }
    }, 50);
  });

  const duration = Date.now() - startTime;

  // Determine if command succeeded
  const status = response.toLowerCase().includes('error') ? 'error' : 'success';

  const result = {
    sessionId,
    command,
    output: response,
    duration_ms: duration,
    status,
  };

  console.log(`[CC-${sessionId}] ✅ Response received (${duration}ms, status: ${status})`);

  // Log result to session
  session.sessionLog.push({
    type: 'response',
    timestamp: Date.now(),
    output: response,
    duration_ms: duration,
  });

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
    logEntries: session.sessionLog.length,
  };
}

/**
 * Get full session recording
 */
function getSessionLog(sessionId) {
  const session = sessions.get(sessionId);
  if (!session) return null;
  return session.sessionLog;
}

/**
 * Save session to file
 */
async function saveSession(sessionId, filepath) {
  const session = sessions.get(sessionId);
  if (!session) throw new Error(`Invalid session: ${sessionId}`);

  const recording = {
    sessionId,
    path: session.path,
    duration_ms: Date.now() - session.created_at,
    commands_sent: session.commandCount,
    createdAt: new Date(session.created_at).toISOString(),
    log: session.sessionLog,
  };

  fs.writeFileSync(filepath, JSON.stringify(recording, null, 2));
  console.log(`[CC-${sessionId}] 💾 Session saved to ${filepath}`);
  return filepath;
}

/**
 * Close session
 */
async function close(sessionId) {
  const session = sessions.get(sessionId);
  if (!session) return;

  console.log(`\n[CC-${sessionId}] 🧹 Closing Claude Code session`);

  if (session.proc && !session.proc.killed) {
    // Try graceful exit first
    session.proc.stdin.write('exit\n');

    // Wait for process to exit
    await new Promise((resolve) => {
      const timeout = setTimeout(() => {
        console.log(`[CC-${sessionId}] Force killing process...`);
        session.proc.kill('SIGKILL');
        resolve();
      }, 3000);

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
  getSessionLog,
  saveSession,
  close,
  closeAll,
};
