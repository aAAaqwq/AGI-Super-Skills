# Electron 原生功能集成参考

## 系统托盘

### 基础托盘图标

```typescript
import { app, BrowserWindow, Tray, Menu, nativeImage } from 'electron'
import * as path from 'path'

let tray: Tray | null = null
let mainWindow: BrowserWindow | null = null

function createTray() {
  // 加载图标
  const iconPath = path.join(__dirname, '../../build/tray-icon.png')
  const icon = nativeImage.createFromPath(iconPath)
  // macOS需要调整模板图标
  icon.setTemplateImage(true)

  tray = new Tray(icon)

  // 托盘提示文本
  tray.setToolTip('My Electron App')

  // 点击托盘图标显示/隐藏窗口
  tray.on('click', () => {
    if (mainWindow) {
      if (mainWindow.isVisible()) {
        mainWindow.hide()
      } else {
        mainWindow.show()
        mainWindow.focus()
      }
    }
  })

  // 托盘右键菜单
  const contextMenu = Menu.buildFromTemplate([
    { label: 'Show App', click: () => mainWindow?.show() },
    { label: 'Hide App', click: () => mainWindow?.hide() },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.quit()
      }
    }
  ])

  tray.setContextMenu(contextMenu)

  return tray
}
```

### 托盘闪烁图标（通知效果）

```typescript
let originalIcon: nativeImage
let isEmptyIcon = false

function flashTrayIcon(flash: boolean) {
  if (!tray) return

  if (flash) {
    originalIcon = tray.getImage()
    // 创建空图标（透明）
    const emptyIcon = nativeImage.createEmpty()
    isEmptyIcon = !isEmptyIcon
    tray.setImage(isEmptyIcon ? emptyIcon : originalIcon)
  } else {
    tray.setImage(originalIcon)
  }
}

// 使用
let flashInterval: NodeJS.Timeout | null = null

function startTrayFlash() {
  flashInterval = setInterval(() => flashTrayIcon(true), 500)
}

function stopTrayFlash() {
  if (flashInterval) {
    clearInterval(flashInterval)
    flashInterval = null
  }
  flashTrayIcon(false)
}
```

## 应用菜单

### 创建菜单

```typescript
import { app, BrowserWindow, Menu, dialog } from 'electron'

function createMenu(window: BrowserWindow) {
  const template: Electron.MenuItemConstructorOptions[] = [
    // macOS应用菜单（必须有）
    ...(process.platform === 'darwin' ? [{
      label: app.getName(),
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' }
      ]
    }] : []),

    // 文件菜单
    {
      label: 'File',
      submenu: [
        {
          label: 'New',
          accelerator: 'CmdOrCtrl+N',
          click: () => {
            window.webContents.send('menu:new-file')
          }
        },
        {
          label: 'Open',
          accelerator: 'CmdOrCtrl+O',
          click: async () => {
            const { canceled, filePaths } = await dialog.showOpenDialog({
              properties: ['openFile']
            })
            if (!canceled && filePaths.length > 0) {
              window.webContents.send('menu:file-opened', filePaths[0])
            }
          }
        },
        { type: 'separator' },
        { role: 'save' },
        { role: 'recentDocuments' },
        { type: 'separator' },
        ...(process.platform === 'darwin' ? [{ role: 'close' }] : [{ role: 'quit' }])
      ]
    },

    // 编辑菜单
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'pasteAndMatchStyle' },
        { role: 'delete' },
        { role: 'selectAll' }
      ]
    },

    // 视图菜单
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' }
      ]
    },

    // 帮助菜单
    {
      label: 'Help',
      submenu: [
        {
          label: 'Learn More',
          click: async () => {
            const { shell } = require('electron')
            await shell.openExternal('https://electronjs.org')
          }
        },
        {
          label: 'About',
          click: () => {
            dialog.showMessageBox(window, {
              type: 'info',
              title: 'About',
              message: `Version ${app.getVersion()}`,
              detail: 'An Electron application'
            })
          }
        }
      ]
    }
  ]

  const menu = Menu.buildFromTemplate(template)
  Menu.setApplicationMenu(menu)
}
```

## 系统通知

### 基础通知

```typescript
import { Notification } from 'electron'

function showNotification(title: string, body: string) {
  if (Notification.isSupported()) {
    new Notification({ title, body }).show()
  }
}

// 带交互的通知
function showInteractiveNotification() {
  const notification = new Notification({
    title: 'New Message',
    body: 'You have a new message',
    icon: nativeImage.createFromPath('path/to/icon.png'),
    // 自定义操作按钮（仅支持部分平台）
    actions: [
      { type: 'button', text: 'Reply' },
      { type: 'button', text: 'Dismiss' }
    ]
  })

  notification.on('action', (event, actionIndex) => {
    if (actionIndex === 0) {
      // Reply clicked
      console.log('User clicked Reply')
    }
  })

  notification.on('click', () => {
    console.log('Notification clicked')
  })

  notification.show()
}
```

## 文件对话框

### 打开文件

```typescript
import { dialog } from 'electron'

// 单文件选择
async function openFile() {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    title: 'Select a file',
    properties: ['openFile'],
    filters: [
      { name: 'Images', extensions: ['jpg', 'png', 'gif', 'webp'] },
      { name: 'Documents', extensions: ['pdf', 'doc', 'docx', 'txt'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  })

  if (!canceled && filePaths.length > 0) {
    return filePaths[0]
  }
  return null
}

// 多文件选择
async function openFiles() {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    properties: ['openFile', 'multiSelections']
  })

  if (!canceled) {
    return filePaths
  }
  return []
}

// 选择目录
async function selectDirectory() {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    properties: ['openDirectory']
  })

  if (!canceled && filePaths.length > 0) {
    return filePaths[0]
  }
  return null
}
```

### 保存文件

```typescript
async function saveFile(defaultPath?: string) {
  const { canceled, filePath } = await dialog.showSaveDialog({
    title: 'Save file',
    defaultPath,
    filters: [
      { name: 'Text Files', extensions: ['txt'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  })

  if (!canceled && filePath) {
    // 写入文件
    await fs.promises.writeFile(filePath, 'content', 'utf-8')
    return filePath
  }
  return null
}
```

### 消息对话框

```typescript
// 信息框
await dialog.showMessageBox({
  type: 'info',
  title: 'Information',
  message: 'Operation completed successfully',
  buttons: ['OK']
})

// 确认框
const { response } = await dialog.showMessageBox({
  type: 'question',
  buttons: ['Cancel', 'Yes, please', 'No, thanks'],
  defaultId: 1,
  title: 'Question',
  message: 'Do you want to continue?'
})

if (response === 1) {
  // User clicked "Yes, please"
}

// 错误框
await dialog.showErrorBox('Error', 'Something went wrong')

// 自定义对话框
const { response, checkboxChecked } = await dialog.showMessageBox({
  type: 'warning',
  title: 'Warning',
  message: 'Are you sure?',
  detail: 'This action cannot be undone',
  buttons: ['Cancel', 'Proceed'],
  defaultId: 0,
  cancelId: 0,
  checkboxLabel: 'Don\'t show this again',
  checkboxChecked: false
})
```

## 全局快捷键

```typescript
import { globalShortcut, app } from 'electron'

function registerGlobalShortcuts(window: BrowserWindow) {
  // 注册快捷键
  const ret = globalShortcut.register('CommandOrControl+Shift+S', () => {
    // 显示/隐藏窗口
    if (window.isVisible()) {
      window.hide()
    } else {
      window.show()
      window.focus()
    }
  })

  if (!ret) {
    console.error('Registration failed')
  }

  // 检查是否注册成功
  console.log(globalShortcut.isRegistered('CommandOrControl+Shift+S'))
}

// 应用退出时注销
app.on('will-quit', () => {
  globalShortcut.unregisterAll()
})
```

## 剪贴板

```typescript
import { clipboard, nativeImage } from 'electron'

// 写入文本
clipboard.writeText('Hello World')

// 读取文本
const text = clipboard.readText()

// 写入HTML
clipboard.writeHTML('<b>Hello</b> World')

// 读取HTML
const html = clipboard.readHTML()

// 写入图片
clipboard.writeImage(nativeImage.createFromPath('path/to/image.png'))

// 读取图片
const image = clipboard.readImage()

// 清空剪贴板
clipboard.clear()

// 可用格式
const availableFormats = clipboard.availableFormats()
```

## 屏幕和显示器

```typescript
import { screen } from 'electron'

// 获取所有显示器
const displays = screen.getAllDisplays()
const primaryDisplay = screen.getPrimaryDisplay()

// 获取屏幕尺寸
const { width, height } = screen.getPrimaryDisplay().workAreaSize

// 获取鼠标所在显示器
const currentDisplay = screen.getDisplayNearestPoint(screen.getCursorScreenPoint())

// 监听显示器变化
screen.on('display-added', (event, newDisplay) => {
  console.log('Display added:', newDisplay)
})

screen.on('display-removed', (event, oldDisplay) => {
  console.log('Display removed:', oldDisplay)
})

screen.on('display-metrics-changed', (event, display, changedMetrics) => {
  console.log('Display metrics changed:', changedMetrics)
})
```

## 系统信息

```typescript
import { app, process } from 'electron'

// 应用信息
app.getName()        // 应用名称
app.getVersion()     // 应用版本
app.getPath('home')  // 用户主目录
app.getPath('appData') // 应用数据目录
app.getPath('userData') // 用户数据目录
app.getPath('temp')  // 临时目录
app.getPath('downloads') // 下载目录

// 系统信息
process.platform     // 'darwin', 'win32', 'linux'
process.arch         // 'x64', 'arm64', etc.
process.version      // Node.js版本
process.versions.v8  // V8版本
process.versions.electron // Electron版本

// 内存使用
process.getProcessMemoryInfo().then(info => {
  console.log('Memory:', info)
})

// CPU使用
process.getCPUUsage()
```

## Shell操作

```typescript
import { shell } from 'electron'

// 打开外部链接
await shell.openExternal('https://example.com')

// 在文件管理器中显示项目
await shell.showItemInFolder('/path/to/file')

// 打开文件（用系统默认应用）
await shell.openPath('/path/to/file')

// 移动到废纸篓/回收站
await shell.trashItem('/path/to/file')

// 创建快捷方式（Windows）
await shell.writeShortcutLink(
  '/path/to/shortcut.lnk',
  'target',
  '/path/to/target'
)
```

## 注意事项

1. **权限：** 某些功能需要用户权限或系统授权
2. **平台差异：** 注意macOS/Windows/Linux的行为差异
3. **安全：** shell.openExternal需要验证URL安全性
4. **资源清理：** 托盘、快捷键等需要在应用退出时清理
5. **IPC安全：** 原生功能调用必须通过IPC，并验证调用来源
