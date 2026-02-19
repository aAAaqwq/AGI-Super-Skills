#!/usr/bin/env python3
"""
Electron + electron-vite + TypeScript + React 项目快速创建脚本
基于最新Electron官方文档和最佳实践
使用: python create_electron_app.py <project-name> [options]
"""

import os
import sys
import json
import argparse
from pathlib import Path


# 项目模板 - 使用electron-vite
PACKAGE_JSON = '''{
  "name": "{project_name}",
  "version": "0.1.0",
  "description": "Electron app built with electron-vite",
  "main": "out/main/index.js",
  "author": "",
  "license": "MIT",
  "scripts": {{
    "dev": "electron-vite dev",
    "build": "electron-vite build",
    "preview": "electron-vite preview",
    "build:win": "npm run build && electron-builder --win",
    "build:mac": "npm run build && electron-builder --mac",
    "build:linux": "npm run build && electron-builder --linux"
  }},
  "dependencies": {{
    "react": "^18.2.0",
    "react-dom": "^18.2.0"
  }},
  "devDependencies": {{
    "@types/node": "^20.10.0",
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "electron": "^28.0.0",
    "electron-builder": "^24.9.0",
    "electron-vite": "^2.0.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0"
  }}
}}
'''

# electron-vite配置
ELECTRON_VITE_CONFIG = '''import { defineConfig } from 'electron-vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({{
  // 主进程配置
  main: {{
    build: {{
      rollupOptions: {{
        output: {{
          entryFileNames: '[name].js'
        }}
      }}
    }}
  }},
  // 预加载脚本配置
  preload: {{
    build: {{
      rollupOptions: {{
        output: {{
          entryFileNames: '[name].js'
        }}
      }}
    }}
  }},
  // 渲染进程配置
  renderer: {{
    resolve: {{
      alias: {{
        '@': path.resolve(__dirname, 'src')
      }}
    }},
    plugins: [react()]
  }}
}})
'''

# TypeScript配置 - 主进程/预加载
TS_CONFIG = '''{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "lib": ["ES2020"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true
  },
  "include": ["electron", "src"]
}}
'''

# Electron主进程 - 带IPC安全验证
ELECTRON_MAIN = '''import {{ app, BrowserWindow, ipcMain }} from 'electron'
import * as path from 'path'

let mainWindow: BrowserWindow | null = null

// 验证IPC发送者 - 安全最佳实践
function validateSender(frame: Electron.WebFrameMain | null): boolean {{
  if (!frame) return false
  // 生产环境应该验证URL的host是否在白名单中
  const allowedHosts = ['localhost'] // 生产环境替换为实际域名
  const url = new URL(frame.url)
  return allowedHosts.includes(url.hostname) || url.protocol === 'file:'
}}

function createWindow() {{
  mainWindow = new BrowserWindow({{
    width: 1200,
    height: 800,
    webPreferences: {{
      preload: path.join(__dirname, '../preload/index.js'),
      // 安全配置 - 必须启用
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true // 推荐启用沙盒模式
    }},
  }})

  if (process.env.NODE_ENV === 'development') {{
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  }} else {{
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'))
  }}

  mainWindow.on('closed', () => {{
    mainWindow = null
  }})
}}

// IPC处理器 - 带安全验证
ipcMain.handle('ping', (event, ...args) => {{
  // 验证发送者
  if (!validateSender(event.senderFrame)) {{
    console.warn('Unauthorized IPC call')
    return null
  }}
  return 'pong: ' + JSON.stringify(args)
}}

ipcMain.handle('get-app-version', (event) => {{
  if (!validateSender(event.senderFrame)) {{
    return null
  }}
  return app.getVersion()
}})

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {{
  if (process.platform !== 'darwin') {{
    app.quit()
  }}
}})

app.on('activate', () => {{
  if (BrowserWindow.getAllWindows().length === 0) {{
    createWindow()
  }}
}})
'''

# Electron预加载脚本 - 使用contextBridge安全暴露
ELECTRON_PRELOAD = '''import {{ contextBridge, ipcRenderer }} from 'electron'

// 使用contextBridge安全暴露API - Electron官方推荐方式
contextBridge.exposeInMainWorld('electronAPI', {{
  // 单向发送 - 不需要响应
  send: (channel: string, ...args: unknown[]) => {{
    // 白名单验证 - 只允许特定的channel
    const validChannels = ['app-ready', 'save-state']
    if (validChannels.includes(channel)) {{
      ipcRenderer.send(channel, ...args)
    }}
  }},
  // 监听主进程消息
  on: (channel: string, callback: (...args: unknown[]) => void) => {{
    const validChannels = ['update-available', 'update-downloaded']
    if (validChannels.includes(channel)) {{
      // 订阅时移除旧监听器，避免重复
      ipcRenderer.removeAllListeners(channel)
      ipcRenderer.on(channel, (_, ...args) => callback(...args))
    }}
  }},
  // 移除监听器
  off: (channel: string) => {{
    ipcRenderer.removeAllListeners(channel)
  }},
  // 双向通信 - invoke/handle模式
  invoke: async (channel: string, ...args: unknown[]) => {{
    const validChannels = ['ping', 'get-app-version', 'save-file', 'open-file']
    if (validChannels.includes(channel)) {{
      return await ipcRenderer.invoke(channel, ...args)
    }}
    return Promise.reject(new Error(`Invalid channel: ${{channel}}`))
  }}
}})
'''

# TypeScript类型声明
ELECTRON_PRELOAD_DTS = '''/**
 * ElectronAPI - 渲染进程可用的安全API接口
 * 通过contextBridge从预加载脚本暴露
 */
export interface ElectronAPI {{
  /** 发送单向消息到主进程 */
  send: (channel: string, ...args: unknown[]) => void
  /** 监听来自主进程的消息 */
  on: (channel: string, callback: (...args: unknown[]) => void) => void
  /** 移除消息监听器 */
  off: (channel: string) => void
  /** 调用主进程方法并等待响应 */
  invoke: (channel: string, ...args: unknown[]) => Promise<unknown>
}}

declare global {{
  interface Window {{
    electronAPI: ElectronAPI
  }}
}}

export {}
'''

# React入口文件
RENDERER_MAIN = '''import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
'''

# React App组件 - 展示IPC使用
RENDERER_APP = '''import {{ useState, useEffect }} from 'react'
import './App.css'

function App() {{
  const [message, setMessage] = useState('Hello Electron!')
  const [appVersion, setAppVersion] = useState<string>('')

  // 获取应用版本
  useEffect(() => {{
    window.electronAPI.invoke('get-app-version').then((version) => {{
      setAppVersion(version as string)
    }})
  }}, [])

  const handlePing = async () => {{
    try {{
      const response = await window.electronAPI.invoke('ping', 'data from renderer')
      setMessage(response as string)
    }} catch (error) {{
      console.error('IPC call failed:', error)
    }}
  }}

  return (
    <div className="App">
      <h1>{{message}}</h1>
      <p>App Version: {{appVersion}}</p>
      <button onClick={{handlePing}}>Send IPC Message</button>
    </div>
  )
}}

export default App
'''

# CSS文件
INDEX_CSS = '''* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
}
'''

APP_CSS = '''.App {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100vh;
  gap: 20px;
}

.App button {
  padding: 10px 20px;
  font-size: 16px;
  cursor: pointer;
  background: #007acc;
  color: white;
  border: none;
  border-radius: 4px;
}

.App button:hover {
  background: #005a9e;
}
'''

# HTML模板
INDEX_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'" />
    <title>Electron App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
'''

# electron-builder配置
ELECTRON_BUILDER_CONFIG = '''appId: com.example.app
productName: My Electron App
directories:
  output: dist
  buildResources: build

files:
  - out/**/*
  - package.json

mac:
  category: public.app-category.productivity
  target: [dmg, zip]
  icon: build/icon.icns

win:
  target: [nsis, portable]
  icon: build/icon.ico

linux:
  target: [AppImage, deb]
  category: Development
  icon: build/icon.png
'''


def create_project(project_name: str, dest: str = "."):
    """创建Electron项目"""
    project_path = Path(dest) / project_name

    if project_path.exists():
        print(f"Error: Directory '{project_name}' already exists")
        sys.exit(1)

    # 创建目录结构
    dirs = [
        project_path / "src",
        project_path / "electron" / "main",
        project_path / "electron" / "preload",
        project_path / "build",
    ]
    for d in dirs:
        d.mkdir(parents=True)

    # 写入文件
    files = {{
        "package.json": PACKAGE_JSON.format(project_name=project_name),
        "electron.vite.config.ts": ELECTRON_VITE_CONFIG,
        "tsconfig.json": TS_CONFIG,
        "electron/main/index.ts": ELECTRON_MAIN,
        "electron/preload/index.ts": ELECTRON_PRELOAD,
        "electron/preload/index.d.ts": ELECTRON_PRELOAD_DTS,
        "src/main.tsx": RENDERER_MAIN,
        "src/App.tsx": RENDERER_APP,
        "src/index.css": INDEX_CSS,
        "src/App.css": APP_CSS,
        "index.html": INDEX_HTML,
        "electron-builder.yml": ELECTRON_BUILDER_CONFIG,
    }}

    for file_path, content in files.items():
        (project_path / file_path).write_text(content, encoding="utf-8")

    print(f"\n=== Electron project '{project_name}' created successfully! ===\n")
    print(f"Based on Electron latest best practices:")
    print(f"  - electron-vite for fast HMR")
    print(f"  - contextIsolation: true (security)")
    print(f"  - nodeIntegration: false (security)")
    print(f"  - sandbox: true (security)")
    print(f"  - contextBridge for safe IPC exposure")
    print(f"\nNext steps:")
    print(f"  1. cd {project_name}")
    print(f"  2. npm install")
    print(f"  3. npm run dev")
    print()


def main():
    parser = argparse.ArgumentParser(description="Create Electron + electron-vite + TypeScript + React project with best practices")
    parser.add_argument("project_name", help="Project name")
    parser.add_argument("--dest", default=".", help="Destination directory (default: current directory)")

    args = parser.parse_args()
    create_project(args.project_name, args.dest)


if __name__ == "__main__":
    main()
