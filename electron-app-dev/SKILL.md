---
name: electron-app-dev
description: |
  Electron desktop application development specialist. Use when developing Electron desktop apps, creating windows, handling IPC communication, packaging applications, or configuring Electron projects.

  Use this skill when:
  1. Creating a new Electron project with electron-vite + TypeScript + React
  2. Implementing secure IPC communication between main and renderer processes
  3. Managing windows (create, control, multi-window, window state)
  4. Integrating native features (system tray, menus, notifications, file dialogs)
  5. Configuring electron-builder for packaging and distribution
  6. Implementing auto-updates and code signing

  All code follows latest Electron security best practices: contextIsolation enabled, nodeIntegration disabled, sandbox mode enabled, contextBridge for safe IPC exposure.
---

# Electron Desktop Application Development

## Quick Start: Create New Project

Use the bundled script to create a new Electron project with best practices:

```bash
python "C:/Users/Administrator/.claude/skills/electron-app-dev/scripts/create_electron_app.py" my-app
cd my-app
npm install
npm run dev
```

**The generated project includes:**
- electron-vite for fast HMR in all processes
- TypeScript + React setup
- Secure IPC patterns with contextBridge
- electron-builder configuration

## Core Security Principles (Non-Negotiable)

Always enforce these security configurations:

```typescript
webPreferences: {
  preload: path.join(__dirname, '../preload/index.js'),
  contextIsolation: true,    // MUST BE TRUE
  nodeIntegration: false,     // MUST BE FALSE
  sandbox: true               // RECOMMENDED
}
```

**Why:**
- `contextIsolation: true` - Separates preload script from renderer
- `nodeIntegration: false` - Prevents renderer from accessing Node.js directly
- `sandbox: true` - Further restricts renderer process capabilities

## IPC Communication Patterns

### The Only Right Way: contextBridge + Whitelist

**Preload (preload/index.ts):**
```typescript
const SEND_CHANNELS = ['app-ready']
const INVOKE_CHANNELS = ['get-app-info', 'save-file']

contextBridge.exposeInMainWorld('electronAPI', {
  send: (channel, ...args) => {
    if (SEND_CHANNELS.includes(channel)) {
      ipcRenderer.send(channel, ...args)
    }
  },
  invoke: async (channel, ...args) => {
    if (INVOKE_CHANNELS.includes(channel)) {
      return await ipcRenderer.invoke(channel, ...args)
    }
    return Promise.reject(new Error(`Invalid channel: ${channel}`))
  }
})
```

**Main Process (main/index.ts):**
```typescript
function validateSender(frame: Electron.WebFrameMain | null): boolean {
  if (!frame) return false
  const url = new URL(frame.url)
  const allowedHosts = ['localhost', 'yourdomain.com']
  return allowedHosts.includes(url.hostname) || url.protocol === 'file:'
}

ipcMain.handle('get-app-info', (event) => {
  if (!validateSender(event.senderFrame)) return null
  return { name: app.getName(), version: app.getVersion() }
})
```

## Reference Documentation

For detailed implementation patterns, consult:

| Topic | Reference File |
|-------|---------------|
| IPC communication patterns, security validation | [references/ipc-patterns.md](references/ipc-patterns.md) |
| Window creation, control, multi-window, state persistence | [references/window-management.md](references/window-management.md) |
| System tray, menus, notifications, file dialogs | [references/native-features.md](references/native-features.md) |
| electron-builder config, code signing, auto-updates | [references/packaging.md](references/packaging.md) |

## Common Tasks

### Create Window
```typescript
import { BrowserWindow } from 'electron'
import * as path from 'path'

const win = new BrowserWindow({
  width: 1200,
  height: 800,
  webPreferences: {
    preload: path.join(__dirname, '../preload/index.js'),
    contextIsolation: true,
    nodeIntegration: false,
    sandbox: true
  }
})

if (process.env.NODE_ENV === 'development') {
  win.loadURL('http://localhost:5173')
  win.webContents.openDevTools()
} else {
  win.loadFile(path.join(__dirname, '../renderer/index.html'))
}
```

### System Tray
```typescript
import { Tray, Menu, nativeImage } from 'electron'

const tray = new Tray(nativeImage.createFromPath('build/icon.png'))
tray.setContextMenu(Menu.buildFromTemplate([
  { label: 'Show', click: () => win.show() },
  { label: 'Quit', click: () => app.quit() }
]))
```

### File Dialog
```typescript
import { dialog } from 'electron'

const { canceled, filePaths } = await dialog.showOpenDialog({
  properties: ['openFile'],
  filters: [{ name: 'Images', extensions: ['jpg', 'png'] }]
})
```

## Project Structure (electron-vite)

```
my-app/
├── electron/
│   ├── main/
│   │   └── index.ts      # Main process entry
│   └── preload/
│       ├── index.ts      # Preload script
│       └── index.d.ts    # TypeScript definitions
├── src/
│   ├── main.tsx          # React entry
│   ├── App.tsx
│   └── index.css
├── out/                   # Compiled output
├── electron.vite.config.ts
├── package.json
└── electron-builder.yml
```

## Build and Package

```bash
# Development
npm run dev

# Build for production
npm run build

# Package for specific platform
npm run build:win    # Windows (NSIS + portable)
npm run build:mac    # macOS (DMG + ZIP)
npm run build:linux  # Linux (AppImage + deb)
```

## Important Notes

1. **Memory Leaks**: Always remove IPC listeners when components unmount
2. **Error Handling**: Wrap invoke calls in try-catch in renderer
3. **Sensitive Data**: Never send passwords/tokens through IPC
4. **Large Files**: Pass file paths instead of file contents
5. **Platform Differences**: Test on all target platforms (win/mac/linux)
