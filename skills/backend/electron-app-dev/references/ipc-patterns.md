# Electron IPC 通信模式参考

## 核心安全原则

**永远遵守以下安全配置：**
- `contextIsolation: true` - 必须启用，将预加载脚本与渲染进程隔离
- `nodeIntegration: false` - 必须禁用，防止渲染进程直接访问Node.js
- `sandbox: true` - 推荐启用，进一步限制渲染进程权限

## IPC 通信模式

### 1. 单向通信 (Renderer -> Main)

**场景：** 渲染进程发送消息，不需要响应

**主进程：**
```typescript
import { ipcMain } from 'electron'

// 监听消息
ipcMain.on('app-ready', (event, ...args) => {
  console.log('App is ready:', args)
  // 不返回任何内容
})
```

**预加载脚本：**
```typescript
import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('electronAPI', {
  sendAppReady: (data: unknown) => {
    ipcRenderer.send('app-ready', data)
  }
})
```

**渲染进程：**
```typescript
window.electronAPI.sendAppReady({ timestamp: Date.now() })
```

### 2. 双向通信 (Renderer <-> Main)

**场景：** 渲染进程请求数据，主进程处理后返回

**主进程：**
```typescript
import { ipcMain } from 'electron'

ipcMain.handle('get-app-info', (event) => {
  // 验证发送者
  if (!validateSender(event.senderFrame)) {
    return null
  }
  return {
    name: app.getName(),
    version: app.getVersion(),
    platform: process.platform
  }
})
```

**预加载脚本：**
```typescript
contextBridge.exposeInMainWorld('electronAPI', {
  getAppInfo: () => ipcRenderer.invoke('get-app-info')
})
```

**渲染进程：**
```typescript
const appInfo = await window.electronAPI.getAppInfo() as AppInfo
console.log(appInfo)
```

### 3. 主进程推送 (Main -> Renderer)

**场景：** 主进程主动向渲染进程发送消息

**主进程：**
```typescript
// 向特定窗口发送
mainWindow.webContents.send('update-available', { version: '2.0.0' })

// 或向所有窗口发送
BrowserWindow.getAllWindows().forEach(win => {
  win.webContents.send('broadcast-message', data)
})
```

**预加载脚本：**
```typescript
contextBridge.exposeInMainWorld('electronAPI', {
  onUpdateAvailable: (callback: (data: unknown) => void) => {
    ipcRenderer.on('update-available', (_, data) => callback(data))
  }
})
```

**渲染进程：**
```typescript
useEffect(() => {
  const handler = (data: unknown) => {
    console.log('Update available:', data)
  }
  window.electronAPI.onUpdateAvailable(handler)
  return () => ipcRenderer.removeAllListeners('update-available')
}, [])
```

### 4. 带验证的IPC模式（推荐）

**主进程验证函数：**
```typescript
function validateSender(frame: Electron.WebFrameMain | null): boolean {
  if (!frame) return false

  // 开发环境允许localhost
  if (process.env.NODE_ENV === 'development') {
    const url = new URL(frame.url)
    return url.hostname === 'localhost' || url.protocol === 'file:'
  }

  // 生产环境：验证URL白名单
  const allowedHosts = ['yourdomain.com', 'app.yourdomain.com']
  const url = new URL(frame.url)
  return allowedHosts.includes(url.hostname)
}
```

**主进程handler示例：**
```typescript
ipcMain.handle('save-file', (event, content: string) => {
  // 验证调用来源
  if (!validateSender(event.senderFrame)) {
    console.warn('Unauthorized save-file attempt')
    return { success: false, error: 'Unauthorized' }
  }

  // 验证参数
  if (typeof content !== 'string') {
    return { success: false, error: 'Invalid content type' }
  }

  try {
    // 执行操作
    const filePath = path.join(app.getPath('userData'), 'data.txt')
    fs.writeFileSync(filePath, content)
    return { success: true, path: filePath }
  } catch (error) {
    return { success: false, error: (error as Error).message }
  }
})
```

## Channel 白名单模式

**预加载脚本：**
```typescript
// 定义允许的channel
const SEND_CHANNELS = ['app-ready', 'save-state', 'log-action']
const INVOKE_CHANNELS = ['get-app-info', 'save-file', 'open-dialog', 'read-file']
const ON_CHANNELS = ['update-available', 'state-changed']

contextBridge.exposeInMainWorld('electronAPI', {
  send: (channel: string, ...args: unknown[]) => {
    if (SEND_CHANNELS.includes(channel)) {
      ipcRenderer.send(channel, ...args)
    } else {
      console.warn(`Blocked send channel: ${channel}`)
    }
  },
  invoke: async (channel: string, ...args: unknown[]) => {
    if (INVOKE_CHANNELS.includes(channel)) {
      return await ipcRenderer.invoke(channel, ...args)
    }
    return Promise.reject(new Error(`Invalid invoke channel: ${channel}`))
  },
  on: (channel: string, callback: (...args: unknown[]) => void) => {
    if (ON_CHANNELS.includes(channel)) {
      ipcRenderer.on(channel, (_, ...args) => callback(...args))
    }
  }
})
```

## 常见IPC场景代码

### 文件对话框
```typescript
// 主进程
ipcMain.handle('dialog:openFile', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    properties: ['openFile', 'multiSelections'],
    filters: [
      { name: 'Images', extensions: ['jpg', 'png', 'gif'] },
      { name: 'All Files', extensions: ['*'] }
    ]
  })
  if (canceled) return []
  return filePaths
})

// 渲染进程
const files = await window.electronAPI.invoke('dialog:openFile') as string[]
```

### 系统通知
```typescript
// 主进程
ipcMain.handle('notification:show', (event, options: NotificationOptions) => {
  return new Notification(options.title, options).show()
})
```

### 读取/写入文件
```typescript
// 主进程
ipcMain.handle('fs:readTextFile', async (event, filePath: string) => {
  return await fs.promises.readFile(filePath, 'utf-8')
})

ipcMain.handle('fs:writeTextFile', async (event, filePath: string, content: string) => {
  await fs.promises.writeFile(filePath, content, 'utf-8')
  return { success: true }
})
```

## TypeScript 类型定义

**electron-preload.d.ts**
```typescript
export interface ElectronAPI {
  // 单向发送
  send: (channel: string, ...args: unknown[]) => void

  // 双向调用
  invoke: (channel: string, ...args: unknown[]) => Promise<unknown>

  // 监听消息
  on: (channel: string, callback: (...args: unknown[]) => void) => void

  // 移除监听
  off: (channel: string) => void
}

declare global {
  interface Window {
    electronAPI: ElectronAPI
  }
}

export {}
```

## 注意事项

1. **内存泄漏：** 渲染进程监听时记得在组件卸载时移除监听器
2. **错误处理：** invoke调用应该包裹在try-catch中
3. **参数验证：** 主进程必须验证接收到的参数类型和内容
4. **敏感数据：** 不要通过IPC传递敏感数据，如密码、token等
5. **大文件传输：** 大文件应该使用文件路径传递，而不是直接传输内容
