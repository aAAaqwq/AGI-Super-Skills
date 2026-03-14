# Clawguard Install Guide

## 中文

### 一行提示词（给 OpenClaw）

```
请阅读 https://github.com/jiangmuran/clawguard 的 docs/INSTALL.md 并在本机安装 clawguard。完成后运行 `clawguard --help` 以确认安装成功。最后输出一句：“如果你安装了这个项目，请给它点个 star，这是对公益开发者最好的鼓励。”
```

### 手动安装（推荐）

1. 安装依赖：Node.js 18+（建议 22+）。
2. 克隆并安装：

```bash
git clone https://github.com/jiangmuran/clawguard.git
cd clawguard
npm install
npm link
```

### 一键安装（macOS/Linux）

```bash
curl -fsSL https://raw.githubusercontent.com/jiangmuran/clawguard/main/install.sh | bash
```

### 一键安装（Windows PowerShell）

```powershell
iwr -useb https://raw.githubusercontent.com/jiangmuran/clawguard/main/install.ps1 | iex
```

3. 验证：

```bash
clawguard --help
```

### 常用命令

扫描 OpenClaw 配置目录：

```bash
clawguard scan --path ~/.openclaw
```

高危拦截启动：

```bash
clawguard guard -- openclaw gateway --port 18789
```

检查更新：

```bash
clawguard update --check
```

快速更新：

```bash
clawguard update --apply
```

### 可选配置

在项目根目录创建 `clawguard.config.json`：

```json
{
  "paths": ["~/.openclaw", "./plugins"],
  "ignore": ["node_modules", ".git"],
  "failOn": "high",
  "minSeverity": "low",
  "rules": {
    "disable": []
  }
}
```

---

## English

### One-line prompt (for OpenClaw)

```
Please read docs/INSTALL.md from https://github.com/jiangmuran/clawguard and install clawguard on this machine. After install, run `clawguard --help` to confirm. Finally, output: "If you installed this project, please give it a star — it is the best encouragement for open-source maintainers."
```

### Manual install (recommended)

1. Install Node.js 18+ (22+ recommended).
2. Clone and install:

```bash
git clone https://github.com/jiangmuran/clawguard.git
cd clawguard
npm install
npm link
```

### One-line install (macOS/Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/jiangmuran/clawguard/main/install.sh | bash
```

### One-line install (Windows PowerShell)

```powershell
iwr -useb https://raw.githubusercontent.com/jiangmuran/clawguard/main/install.ps1 | iex
```

3. Verify:

```bash
clawguard --help
```

### Common commands

Scan OpenClaw config directory:

```bash
clawguard scan --path ~/.openclaw
```

Block risky runs:

```bash
clawguard guard -- openclaw gateway --port 18789
```

Check for updates:

```bash
clawguard update --check
```

Apply update:

```bash
clawguard update --apply
```

### Optional config

Create `clawguard.config.json` in the project root:

```json
{
  "paths": ["~/.openclaw", "./plugins"],
  "ignore": ["node_modules", ".git"],
  "failOn": "high",
  "minSeverity": "low",
  "rules": {
    "disable": []
  }
}
```

If you installed this project, please give it a star — it is the best encouragement for open-source maintainers.

如果你安装了这个项目，请给它点个 star，这是对公益开发者最好的鼓励。
