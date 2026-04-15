# Claude Code Control

Control Claude Code programmatically through visible Terminal.app windows on macOS.

## How It Works

Uses AppleScript to:
1. Open Terminal.app and launch `claude code` in a project directory
2. Type commands via System Events keystrokes
3. Capture screenshots of just the Terminal window (not full screen)
4. Record full sessions with timestamped logs

## Requirements

- macOS
- Node.js 18+
- Claude Code installed and authenticated
- Accessibility permissions for Terminal.app + Script Editor (System Settings → Privacy & Security → Accessibility)

## Usage

```javascript
const cc = require('./index');

// Launch Claude Code visibly
const session = await cc.launch('/path/to/project');

// Send a command (types it + presses Enter)
const result = await cc.send(session, 'write tests for app.py', 30);
// result.screenshot → path to Terminal window screenshot

// Save session recording
await cc.saveSession(session, './recording.json');

// Close
await cc.close(session);
```

## API

| Function | Description |
|---|---|
| `launch(path, opts?)` | Open Terminal + start Claude Code. Returns session ID |
| `send(id, command, waitSec?)` | Type command, wait, screenshot. Returns `{screenshot, duration_ms}` |
| `verifyScreen(id, desc)` | Take a verification screenshot |
| `approveSecurity(id)` | Handle "trust this folder" prompt |
| `handleLogin(id)` | Send `/login` command |
| `saveSession(id, path)` | Save session log to JSON |
| `close(id)` / `closeAll()` | Exit Claude Code gracefully |
| `takeScreenshot(path?)` | Capture Terminal window |
| `focusTerminal()` | Bring Terminal to front |

## Pro Features (Coming Soon)

- 🎬 Video recording of sessions
- 🤖 Multi-agent / multi-terminal orchestration
- 📊 Session analytics
- 🔄 Session replay
- 🌐 Remote control via SSH
