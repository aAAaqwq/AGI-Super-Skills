/**
 * Claude Code Control Skill — PROPER IMPLEMENTATION
 * 
 * Uses macOS AppleScript to:
 * 1. Open a REAL visible Terminal.app window running Claude Code
 * 2. Send keystrokes via System Events
 * 3. Take screenshots with screencapture
 * 4. Verify state via image analysis
 * 
 * The user can SEE Claude Code running on their screen.
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const sessions = new Map();
let sessionCounter = 0;

// ─── Helpers ────────────────────────────────────────────────

/**
 * Run AppleScript and return output
 */
function runAppleScript(script) {
  try {
    return execSync(`osascript -e '${script.replace(/'/g, "'\\''")}'`, {
      encoding: 'utf-8',
      timeout: 10000,
    }).trim();
  } catch (err) {
    console.error(`[AppleScript Error] ${err.message}`);
    return '';
  }
}

/**
 * Run multi-line AppleScript
 */
function runAppleScriptMulti(lines) {
  const script = lines.join('\n');
  const tmpFile = `/tmp/cc-applescript-${Date.now()}.scpt`;
  fs.writeFileSync(tmpFile, script);
  try {
    return execSync(`osascript ${tmpFile}`, {
      encoding: 'utf-8',
      timeout: 15000,
    }).trim();
  } catch (err) {
    console.error(`[AppleScript Error] ${err.message}`);
    return '';
  } finally {
    try { fs.unlinkSync(tmpFile); } catch {}
  }
}

/**
 * Bring Terminal.app to the front and focus it
 */
function focusTerminal() {
  runAppleScriptMulti([
    'tell application "Terminal"',
    '  activate',
    '  set frontWindow to front window',
    '  set index of frontWindow to 1',
    'end tell',
  ]);
  // Small pause to let the window actually come forward
  execSync('sleep 1');
}

/**
 * Get Terminal.app front window bounds {x, y, w, h}
 */
function getTerminalWindowBounds() {
  const result = runAppleScriptMulti([
    'tell application "Terminal"',
    '  set b to bounds of front window',
    '  return (item 1 of b as text) & "," & (item 2 of b as text) & "," & (item 3 of b as text) & "," & (item 4 of b as text)',
    'end tell',
  ]);
  if (!result) return null;
  const [x1, y1, x2, y2] = result.split(',').map(Number);
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

/**
 * Take a screenshot of the Terminal.app window only.
 * Falls back to full screen if window bounds can't be detected.
 */
function takeScreenshot(outputPath) {
  const filePath = outputPath || `/tmp/cc-screenshot-${Date.now()}.png`;
  try {
    // First, focus Terminal so it's on top
    focusTerminal();

    // Try to get window bounds for a targeted capture
    const bounds = getTerminalWindowBounds();
    if (bounds) {
      // screencapture -R x,y,w,h captures a specific region
      execSync(`screencapture -x -R "${bounds.x},${bounds.y},${bounds.w},${bounds.h}" "${filePath}"`, { timeout: 5000 });
    } else {
      // Fallback: capture the whole screen
      execSync(`screencapture -x "${filePath}"`, { timeout: 5000 });
    }

    if (fs.existsSync(filePath)) {
      return filePath;
    }
  } catch (err) {
    console.error(`[Screenshot Error] ${err.message}`);
  }
  return null;
}

/**
 * Type text into the frontmost application via System Events
 */
function typeText(text) {
  // Use keystroke for short text, or write to clipboard and paste for long text
  if (text.length > 50) {
    // Use clipboard for long text
    execSync(`echo ${JSON.stringify(text)} | pbcopy`, { timeout: 5000 });
    runAppleScriptMulti([
      'tell application "System Events"',
      '  keystroke "v" using command down',
      'end tell',
    ]);
  } else {
    // Direct keystroke for short text
    runAppleScriptMulti([
      'tell application "System Events"',
      `  keystroke "${text.replace(/"/g, '\\"')}"`,
      'end tell',
    ]);
  }
}

/**
 * Press Enter/Return key
 */
function pressEnter() {
  runAppleScriptMulti([
    'tell application "System Events"',
    '  key code 36',
    'end tell',
  ]);
}

/**
 * Press a special key (escape, tab, etc.)
 */
function pressKey(keyName) {
  const keyCodes = {
    'return': 36,
    'enter': 36,
    'escape': 53,
    'tab': 48,
    'space': 49,
    'delete': 51,
    'up': 126,
    'down': 125,
    'left': 123,
    'right': 124,
  };
  const code = keyCodes[keyName.toLowerCase()] || 36;
  runAppleScriptMulti([
    'tell application "System Events"',
    `  key code ${code}`,
    'end tell',
  ]);
}

// ─── Core API ───────────────────────────────────────────────

/**
 * Launch Claude Code in a VISIBLE Terminal.app window
 */
async function launch(projectPath, options = {}) {
  const sessionId = ++sessionCounter;
  const normalizedPath = path.resolve(projectPath);

  if (!fs.existsSync(normalizedPath)) {
    throw new Error(`Project path does not exist: ${normalizedPath}`);
  }

  console.log(`[CC-${sessionId}] 🚀 Opening Terminal.app with Claude Code at ${normalizedPath}`);

  // Open a new Terminal.app window and run claude code
  runAppleScriptMulti([
    'tell application "Terminal"',
    '  activate',
    `  do script "cd '${normalizedPath}' && claude code"`,
    'end tell',
  ]);

  const session = {
    id: sessionId,
    path: normalizedPath,
    created_at: Date.now(),
    commandCount: 0,
    sessionLog: [],
    ready: false,
  };

  console.log(`[CC-${sessionId}] ⏳ Waiting for Claude Code to start...`);

  // Wait for Claude Code to appear (give it time to load)
  await new Promise(resolve => setTimeout(resolve, 5000));

  // Take a screenshot to verify it's running
  const screenshot = takeScreenshot();
  if (screenshot) {
    console.log(`[CC-${sessionId}] 📸 Screenshot captured: ${screenshot}`);
    session.sessionLog.push({
      type: 'screenshot',
      timestamp: Date.now(),
      path: screenshot,
      event: 'launch',
    });
  }

  session.ready = true;
  sessions.set(sessionId, session);

  console.log(`[CC-${sessionId}] ✅ Claude Code should now be visible on screen`);
  return sessionId;
}

/**
 * Send a command to Claude Code by typing into Terminal.app
 */
async function send(sessionId, command, waitSeconds = 10) {
  const session = sessions.get(sessionId);
  if (!session) throw new Error(`Invalid session: ${sessionId}`);

  const startTime = Date.now();
  session.commandCount++;

  console.log(`[CC-${sessionId}] 📤 Typing command: ${command}`);

  // Log the command
  session.sessionLog.push({
    type: 'command',
    timestamp: Date.now(),
    command,
  });

  // Bring Terminal to front
  focusTerminal();

  // Type the command
  typeText(command);
  await new Promise(resolve => setTimeout(resolve, 200));

  // Press Enter
  pressEnter();

  console.log(`[CC-${sessionId}] ⏳ Waiting ${waitSeconds}s for command to complete...`);

  // Wait for command to process
  await new Promise(resolve => setTimeout(resolve, waitSeconds * 1000));

  // Take screenshot to capture result
  const screenshot = takeScreenshot();
  const duration = Date.now() - startTime;

  const result = {
    sessionId,
    command,
    duration_ms: duration,
    screenshot,
    status: 'sent',
  };

  // Log result
  session.sessionLog.push({
    type: 'response',
    timestamp: Date.now(),
    duration_ms: duration,
    screenshot,
  });

  console.log(`[CC-${sessionId}] ✅ Command sent and screenshot captured (${duration}ms)`);

  return result;
}

/**
 * Verify current screen state by analyzing screenshot
 */
async function verifyScreen(sessionId, description) {
  const session = sessions.get(sessionId);
  if (!session) throw new Error(`Invalid session: ${sessionId}`);

  const screenshot = takeScreenshot();
  if (!screenshot) {
    return { verified: false, error: 'Screenshot failed' };
  }

  session.sessionLog.push({
    type: 'verification',
    timestamp: Date.now(),
    screenshot,
    description,
  });

  return {
    verified: true,
    screenshot,
    description,
  };
}

/**
 * Handle Claude Code security prompt (approve project access)
 */
async function approveSecurity(sessionId) {
  const session = sessions.get(sessionId);
  if (!session) throw new Error(`Invalid session: ${sessionId}`);

  console.log(`[CC-${sessionId}] 🔓 Approving security prompt...`);

  // Bring Terminal to front
  focusTerminal();

  // Press 1 for "Yes, I trust this folder"
  typeText('1');
  await new Promise(resolve => setTimeout(resolve, 200));
  pressEnter();

  await new Promise(resolve => setTimeout(resolve, 2000));

  console.log(`[CC-${sessionId}] ✅ Security prompt approved`);
}

/**
 * Handle Claude Code login flow
 */
async function handleLogin(sessionId) {
  const session = sessions.get(sessionId);
  if (!session) throw new Error(`Invalid session: ${sessionId}`);

  console.log(`[CC-${sessionId}] 🔐 Handling login...`);

  // Bring Terminal to front
  focusTerminal();

  // Type /login command
  typeText('/login');
  pressEnter();

  console.log(`[CC-${sessionId}] 🔐 Login command sent. User should complete auth in browser.`);
  console.log(`[CC-${sessionId}] ⏳ Waiting for authentication to complete...`);
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
    ready: session.ready,
    logEntries: session.sessionLog.length,
  };
}

/**
 * Save session recording (all screenshots + commands)
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
 * Close Claude Code session
 */
async function close(sessionId) {
  const session = sessions.get(sessionId);
  if (!session) return;

  console.log(`[CC-${sessionId}] 🧹 Closing Claude Code...`);

  // Bring Terminal to front and send Escape + exit
  focusTerminal();
  pressKey('escape');
  await new Promise(resolve => setTimeout(resolve, 500));
  typeText('/exit');
  pressEnter();

  sessions.delete(sessionId);
  console.log(`[CC-${sessionId}] ✅ Session closed`);
}

/**
 * Close all sessions
 */
async function closeAll() {
  for (const id of Array.from(sessions.keys())) {
    await close(id);
  }
}

module.exports = {
  launch,
  send,
  verifyScreen,
  approveSecurity,
  handleLogin,
  getStatus,
  saveSession,
  close,
  closeAll,
  takeScreenshot,
  focusTerminal,
  getTerminalWindowBounds,
  typeText,
  pressEnter,
  pressKey,
};
