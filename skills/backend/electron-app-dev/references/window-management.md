# Electron 窗口管理参考

## 创建窗口

### 基础窗口创建

```typescript
import { app, BrowserWindow } from 'electron'
import * as path from 'path'

let mainWindow: BrowserWindow | null = null

function createWindow() {
  mainWindow = new BrowserWindow({
    // 窗口尺寸
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,

    // 窗口位置
    x: undefined, // 默认居中
    y: undefined,

    // 窗口外观
    title: 'My App',
    icon: path.join(__dirname, '../../build/icon.png'),
    backgroundColor: '#ffffff',

    // 窗口行为
    show: false, // 延迟显示，防止闪烁
    autoHideMenuBar: true, // 自动隐藏菜单栏

    // 安全配置 - 必须设置
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  })

  // 加载内容
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'))
  }

  // 窗口准备好后显示，避免闪烁
  mainWindow.once('ready-to-show', () => {
    mainWindow?.show()
  })

  return mainWindow
}
```

### 无边框窗口

```typescript
const framelessWindow = new BrowserWindow({
  width: 400,
  height: 600,
  frame: false,        // 无边框
  transparent: true,   // 透明背景
  titleBarStyle: 'hidden', // macOS风格: 'default' | 'hidden' | 'customButtonsOnHover'
  webPreferences: {
    preload: path.join(__dirname, '../preload/index.js'),
    contextIsolation: true,
    nodeIntegration: false
  }
})
```

### 窗口类型选项

```typescript
// 工具窗口（轻量级，不显示在任务栏）
const toolWindow = new BrowserWindow({
  width: 300,
  height: 400,
  type: 'toolbar', // 'desktop' | 'toolbar' | 'splash' | 'notification'
  alwaysOnTop: true,
  skipTaskbar: true
})

// 启动画面
const splashScreen = new BrowserWindow({
  width: 500,
  height: 400,
  transparent: true,
  frame: false,
  alwaysOnTop: true,
  center: true,
  skipTaskbar: true,
  closable: false
})

// 子窗口（模态）
const childWindow = new BrowserWindow({
  width: 600,
  height: 400,
  parent: mainWindow,  // 设置父窗口
  modal: true,         // 模态窗口
  show: false
})
```

## 窗口控制

### 窗口状态控制

```typescript
// 显示/隐藏/最小化/最大化/关闭
window.show()
window.hide()
window.minimize()
window.maximize()
window.unmaximize()
window.isMaximized() // 检查是否最大化
window.close()
window.isDestroyed()

// 全屏控制
window.setFullScreen(true)
window.isFullScreen()
window.setSimpleFullScreen(true) // 更流畅的全屏

// 窗口位置
window.center()
window.setPosition(x, y)
window.getPosition() // [x, y]
window.setSize(width, height)
window.getSize() // [width, height]

// 窗口可移动和可调整大小
window.setMovable(false)
window.setResizable(false)
window.isResizable()
```

### 通过IPC控制窗口

**预加载脚本：**
```typescript
contextBridge.exposeInMainWorld('windowAPI', {
  minimize: () => ipcRenderer.send('window:minimize'),
  maximize: () => ipcRenderer.send('window:maximize'),
  close: () => ipcRenderer.send('window:close'),
  isMaximized: () => ipcRenderer.invoke('window:isMaximized')
})
```

**主进程：**
```typescript
ipcMain.on('window:minimize', () => {
  mainWindow?.minimize()
})

ipcMain.on('window:maximize', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize()
  } else {
    mainWindow?.maximize()
  }
})

ipcMain.on('window:close', () => {
  mainWindow?.close()
})

ipcMain.handle('window:isMaximized', () => {
  return mainWindow?.isMaximized() ?? false
})
```

**渲染进程：**
```typescript
// 自定义标题栏按钮
<div className="title-bar">
  <button onClick={() => window.windowAPI.minimize()}>_</button>
  <button onClick={() => window.windowAPI.maximize()}>□</button>
  <button onClick={() => window.windowAPI.close()}>×</button>
</div>
```

## 窗口事件

```typescript
// 窗口生命周期
window.on('show', () => console.log('Window shown'))
window.on('hide', () => console.log('Window hidden'))
window.on('close', (event) => {
  // 阻止关闭
  if (hasUnsavedChanges) {
    event.preventDefault()
    // 显示保存对话框
  }
  // 清理资源
  mainWindow = null
})

// 窗口状态变化
window.on('maximize', () => console.log('Maximized'))
window.on('unmaximize', () => console.log('Unmaximized'))
window.on('minimize', () => console.log('Minimized'))
window.on('restore', () => console.log('Restored'))
window.on('move', () => {
  const [x, y] = window.getPosition()
  console.log('Moved to:', x, y)
})
window.on('resize', () => {
  const [width, height] = window.getSize()
  console.log('Resized to:', width, height)
})

// 窗口焦点
window.on('focus', () => console.log('Focused'))
window.on('blur', () => console.log('Blurred'))
window.on('app-command', (e, cmd) => {
  // 浏览器导航按钮
  if (cmd === 'browser-backward') {
    // 处理后退
  }
})
```

## 保存和恢复窗口状态

```typescript
import { app, BrowserWindow } from 'electron'
import * as path from 'path'
import fs from 'fs'

const stateFile = path.join(app.getPath('userData'), 'window-state.json')

interfaceWindowState {
  width: number
  height: number
  x: number
  y: number
  isMaximized: boolean
}

function getWindowState(): WindowState | null {
  try {
    if (fs.existsSync(stateFile)) {
      return JSON.parse(fs.readFileSync(stateFile, 'utf-8'))
    }
  } catch (error) {
    console.error('Failed to load window state:', error)
  }
  return null
}

function saveWindowState(window: BrowserWindow) {
  const [width, height] = window.getSize()
  const [x, y] = window.getPosition()
  const state: WindowState = {
    width,
    height,
    x,
    y,
    isMaximized: window.isMaximized()
  }
  fs.writeFileSync(stateFile, JSON.stringify(state))
}

function createWindow() {
  const savedState = getWindowState()

  const window = new BrowserWindow({
    width: savedState?.width ?? 1200,
    height: savedState?.height ?? 800,
    x: savedState?.x ?? undefined,
    y: savedState?.y ?? undefined,
    // ... 其他配置
  })

  // 恢复最大化状态
  if (savedState?.isMaximized) {
    window.maximize()
  }

  // 保存状态
  window.on('close', () => saveWindowState(window))
  window.on('resize', () => {
    if (!window.isMaximized()) {
      saveWindowState(window)
    }
  })
  window.on('move', () => {
    if (!window.isMaximized()) {
      saveWindowState(window)
    }
  })

  return window
}
```

## 多窗口管理

```typescript
import { BrowserWindow } from 'electron'

interface WindowManager {
  [key: string]: BrowserWindow | null
}

const windows: WindowManager = {
  main: null,
  settings: null,
  preview: null
}

function createMainWindow() {
  windows.main = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })
  // ...
}

function createSettingsWindow() {
  // 避免重复创建
  if (windows.settings && !windows.settings.isDestroyed()) {
    windows.settings.focus()
    return
  }

  windows.settings = new BrowserWindow({
    width: 600,
    height: 500,
    parent: windows.main ?? undefined,
    modal: true,
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  windows.settings.loadFile('settings.html')

  windows.settings.on('closed', () => {
    windows.settings = null
  })
}

// 关闭所有窗口
function closeAllWindows() {
  Object.values(windows).forEach(win => {
    if (win && !win.isDestroyed()) {
      win.close()
    }
  })
}

// 向所有窗口广播消息
function broadcastToAllWindows(channel: string, ...args: unknown[]) {
  Object.values(windows).forEach(win => {
    if (win && !win.isDestroyed()) {
      win.webContents.send(channel, ...args)
    }
  })
}
```

## 窗口间通信

```typescript
// 主进程：窗口A发送消息给窗口B
function createWindowA() {
  const winA = new BrowserWindow({ /* ... */ })
  return winA
}

function createWindowB() {
  const winB = new BrowserWindow({ /* ... */ })
  return winB
}

// 窗口A请求窗口B的数据
ipcMain.handle('get-window-b-data', (event) => {
  // 从窗口B获取数据
  if (windows.preview && !windows.preview.isDestroyed()) {
    return windows.preview.webContents.executeJavaScript('getSharedData()')
  }
  return null
})

// 广播消息到所有窗口
ipcMain.on('broadcast-data', (event, data) => {
  Object.values(windows).forEach(win => {
    if (win && !win.isDestroyed() && win !== event.sender) {
      win.webContents.send('data-update', data)
    }
  })
})
```

## 注意事项

1. **内存泄漏：** 窗口关闭后清理引用，设为null
2. **状态保存：** 在close事件中保存窗口状态
3. **防抖：** resize和move事件频繁触发，需要防抖处理
4. **多显示器：** 注意窗口位置可能超出当前显示器范围
5. **安全性：** 所有窗口都应设置contextIsolation和nodeIntegration: false
