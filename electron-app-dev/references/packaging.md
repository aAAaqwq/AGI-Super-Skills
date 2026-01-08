# Electron 打包和分发参考

## electron-builder 基础配置

### YAML配置文件 (electron-builder.yml)

```yaml
# 应用标识
appId: com.yourcompany.app
productName: My Electron App
copyright: Copyright © 2024 Your Company

# 目录配置
directories:
  output: dist           # 输出目录
  buildResources: build  # 构建资源目录

# 包含文件
files:
  - out/**/*             # 编译后的Electron代码
  - package.json
  - "!**/*.map"          # 排除sourcemap

# 额外资源
extraResources:
  - from: resources
    to: .
    filter:
      - "**/*"

# 额外文件（打包到app.asar中）
extraMetadata:
  key: value
```

### package.json 配置

```json
{
  "name": "my-electron-app",
  "version": "1.0.0",
  "main": "out/main/index.js",
  "build": {
    "appId": "com.yourcompany.app",
    "productName": "My App",
    "directories": {
      "output": "dist"
    },
    "files": [
      "out/**/*",
      "package.json"
    ]
  },
  "scripts": {
    "build": "electron-vite build",
    "build:win": "npm run build && electron-builder --win",
    "build:mac": "npm run build && electron-builder --mac",
    "build:linux": "npm run build && electron-builder --linux"
  }
}
```

## Windows 配置

```yaml
# electron-builder.yml
win:
  # 目标格式
  target:
    - target: nsis           # NSIS安装程序
      arch:
        - x64                # x64架构
        - ia32               # 32位
    - target: portable       # 便携版（绿色版）
      arch:
        - x64

  # 图标
  icon: build/icon.ico

  # 证书签名
  signtoolOptions:
    certificateFile: ./certs/cert.pfx
    certificatePassword: ${env.WIN_CSC_KEY_PASSWORD}

  # 文件关联
  fileAssociations:
    - ext: txt
      name: Text File
      description: My Text File
      role: Editor
      icon: build/file-icon.ico

# NSIS安装程序配置
nsis:
  oneClick: false              # 允许用户选择安装目录
  perMachine: false            # 为当前用户安装
  allowElevation: true         # 允许提升权限
  allowToChangeInstallationDirectory: true
  installerIcon: build/installer-icon.ico
  uninstallerIcon: build/uninstaller-icon.ico
  createDesktopShortcut: always    # 创建桌面快捷方式
  createStartMenuShortcut: true    # 创建开始菜单快捷方式
  shortcutName: My App

  # 安装/卸载脚本
  include: build/installer.nsh

  # 许可协议
  license: build/LICENSE.txt

#便携版配置
portable:
  artifactName: ${productName}-${version}-portable.exe
```

## macOS 配置

```yaml
mac:
  # 应用类别
  category: public.app-category.productivity

  # 目标格式
  target:
    - target: dmg          # DMG磁盘镜像
    - target: zip         # ZIP压缩包
    - target: pkg         # PKG安装包（需签名）

  # 图标
  icon: build/icon.icns

  # 硬化运行时（推荐）
  hardenedRuntime: true
  gatekeeperAssess: false

  # 权限
  entitlements: build/entitlements.mac.plist
  entitlementsInherit: build/entitlements.mac.plist

  # 公证（macOS 10.15+需要）
  notarize:
    teamId: YOUR_TEAM_ID

# DMG配置
dmg:
  background: build/background.png    # 背景图
  icon: build/volume-icon.icns        # 卷图标
  iconSize: 100                       # 图标大小
  contents:                           # 内容布局
    - x: 130
      y: 220
      type: file
    - x: 410
      y: 220
      type: link
      path: /Applications
  window:
    width: 540
    height: 380

# PKG配置
pkg:
  allowAnywhere: true
  allowCurrentUserHome: true
  allowRootDirectory: true
  license: build/LICENSE.txt
```

### entitlements.mac.plist

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.cs.allow-jit</key>
  <true/>
  <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
  <true/>
  <key>com.apple.security.cs.disable-library-validation</key>
  <true/>
  <key>com.apple.security.network.client</key>
  <true/>
  <key>com.apple.security.network.server</key>
  <true/>
</dict>
</plist>
```

## Linux 配置

```yaml
linux:
  # 目标格式
  target:
    - AppImage          # 通用格式
    - deb               # Debian/Ubuntu
    - rpm               # Fedora/RedHat
    - snap             # Snap Store
    - pacman           # Arch Linux

  # 应用类别
  category: Development

  # 图标
  icon: build/icons

  # 简短描述
  synopsis: Short description of the app

  # 详细描述
  description: |
    Long description of the application.
    This can span multiple lines.

  # 维护者信息
  maintainer: Your Name <your@email.com>

  # 供应商
  vendor: Your Company

# AppImage配置
appImage:
  artifactName: ${productName}-${version}-${arch}.${ext}
  synopsis: My Electron App

# deb配置
deb:
  depends:
    - gconf2
    - gconf-service
    - libnotify4
    - libxtst6
    - libnss3

# rpm配置
rpm:
  depends:
    - gconf2
    - gconf-service
    - libnotify4
  fpm: ['--rpm-rpmbuild-define', '_build_id_links none']
```

## 代码签名

### Windows 签名

```yaml
win:
  signtoolOptions:
    certificateFile: ./certs/cert.pfx
    certificatePassword: ${env.WIN_CSC_KEY_PASSWORD}
    # 或使用SHA1指纹
    # certificateSha1: "12:34:56..."
```

### macOS 签名和公证

```yaml
mac:
  identity: "Developer ID Application: Your Name (TEAM_ID)"
  hardenedRuntime: true
  gatekeeperAssess: false

  notarize:
    teamId: YOUR_TEAM_ID
    # Apple ID凭据（环境变量）
    # appleId: ${env.APPLE_ID}
    # appleIdPassword: ${env.APPLE_ID_PASSWORD}
```

### 命令行签名

```bash
# Windows
signtool sign /f cert.pfx /p password /fd sha256 /tr http://timestamp.digicert.com dist/my-app.exe

# macOS
codesign --deep --force --verify --verbose --sign "Developer ID Application: Your Name" dist/MyApp.app

# 公证（需要Xcode 13+）
xcrun notarytool submit dist/MyApp.app --apple-id "your@email.com" --password "app-specific-password" --team-id "TEAM_ID" --wait
xcrun stapler staple dist/MyApp.app
```

## 自动更新配置

### 主进程配置

```typescript
import { autoUpdater } from 'electron-updater'
import { app } from 'electron'

export function setupAutoUpdater() {
  // 配置更新服务器
  autoUpdater.setFeedURL({
    provider: 'github',
    owner: 'your-username',
    repo: 'your-repo'
  })

  // 检查更新
  autoUpdater.checkForUpdatesAndNotify()

  // 更新事件
  autoUpdater.on('update-available', (info) => {
    // 通知用户新版本可用
    mainWindow?.webContents.send('update-available', info)
  })

  autoUpdater.on('update-downloaded', (info) => {
    // 通知用户更新已下载
    mainWindow?.webContents.send('update-downloaded', info)
  })

  autoUpdater.on('error', (error) => {
    console.error('Update error:', error)
  })
}

// 下载后重启并安装
ipcMain.on('install-update', () => {
  autoUpdater.quitAndInstall()
})
```

### electron-builder 发布配置

```yaml
publish:
  provider: github      # GitHub Releases
  owner: your-username
  repo: your-repo
  releaseType: release # draft | prerelease | release

# 或使用私有S3
# publish:
#   provider: s3
#   bucket: your-bucket
#   path: releases/

# 或使用自定义服务器
# publish:
#   provider: generic
#   url: https://your-server.com/releases/
```

## 常用构建命令

```bash
# 构建当前平台
electron-builder

# 构建指定平台
electron-builder --win        # Windows
electron-builder --mac        # macOS
electron-builder --linux      # Linux

# 构建指定架构
electron-builder --mac --x64
electron-builder --mac --arm64    # Apple Silicon
electron-builder --win --ia32     # 32位

# 构建特定目标
electron-builder --win --target nsis
electron-builder --win --target portable
electron-builder --linux --target AppImage

# 只构建不打包
electron-builder --dir

# 发布后构建
electron-builder --publish always
electron-builder --publish onTag
```

## 优化和调试

### 减小包体积

```yaml
# 排除不必要的文件
files:
  - out/**/*
  - package.json
  - "!**/*.map"
  - "!**/*.ts"
  - "!node_modules/**/*"
  - "node_modules/**/*.node"

# 依赖优化
nodeGypRebuild: false
npmRebuild: false

# 压缩
compression: maximum    # store | normal | maximum

# asar打包
asar: true
asarUnpack:            # 不打包到asar的文件
  - resources/**
  - node_modules/**/*.node
```

### 环境变量

```bash
# 禁用asar打包（调试）
export CSC_IDENTITY_AUTO_DISCOVERY=false

# GitHub发布token
export GH_TOKEN="your-github-token"

# Windows签名密码
export WIN_CSC_KEY_PASSWORD="your-password"

# macOS公证凭据
export APPLE_ID="your@email.com"
export APPLE_ID_PASSWORD="app-specific-password"
export APPLE_TEAM_ID="YOUR_TEAM_ID"
```

## 注意事项

1. **首次构建较慢**：会下载原生二进制文件
2. **图标格式**：Windows需要.ico，macOS需要.icns，Linux需要.png
3. **代码签名**：发布必须签名，否则会被系统警告
4. **macOS公证**：10.15+需要公证，否则无法打开
5. **测试安装包**：在干净环境中测试安装流程
