---
name: remote-openclaw-deploy
description: "通用远程部署 OpenClaw Agent 项目。支持任意定制化 agent 团队、跨 macOS/Linux、多渠道（飞书/Telegram/Discord）、deploy.json 声明式配置注入。一个脚本完成从零到可用的全流程。"
license: MIT
metadata:
  version: 2.0.0
  domains: [deployment, openclaw, remote-ops, devops]
  type: automation
---

# 远程 OpenClaw 通用部署 Skill

## 定位

**一个脚本，部署任意定制化 Agent 项目到任意远程机器。**

不是 tian_agent 专用，不是 Mac 专用，不是飞书专用。
任何 OpenClaw Agent 项目，只要按标准目录结构组织，一条命令部署。

## 使用场景

- 为客户/团队部署定制化 Agent 团队
- 从本地开发环境推送到生产机器
- 多台机器批量部署同一套 Agent
- 项目更新后增量重部署

## 核心理念

```
项目仓库（本地）──tar/SSH──→ 远程机器
                              ├── ~/projects/<name>/        ← 源码（可 git pull 更新）
                              ├── ~/.openclaw/agents/       ← Agent 运行时配置
                              ├── ~/.openclaw/skills/       ← Skills
                              └── ~/.openclaw/openclaw.json ← 自动注入 provider/channel/agent
```

## 项目目录结构（标准）

```
my_project/
├── deploy.json              ← 部署清单（声明 provider/channel/agent/权限）
├── agents/
│   ├── assistant/
│   │   └── agent/
│   │       ├── agent.json
│   │       ├── AGENTS.md
│   │       └── SOUL.md
│   ├── support/
│   │   └── agent/
│   └── ...
├── skills/                  ← 共享 skills（可选）
│   └── my-custom-skill/
│       └── SKILL.md
└── workspace/               ← 工作区文件（可选）
    ├── AGENTS.md
    ├── SOUL.md
    └── USER.md
```

## deploy.json — 声明式部署清单

每个项目根目录放一个 `deploy.json`，脚本自动读取并注入远程 `openclaw.json`。

```json
{
  "project_name": "tian_agent",
  
  "providers": {
    "google": {
      "baseUrl": "https://generativelanguage.googleapis.com/v1beta",
      "apiKey": "AIzaSy...",
      "api": "google-genai",
      "models": [{"id": "gemini-2.5-pro"}, {"id": "gemini-2.5-flash"}]
    }
  },
  
  "agents": [
    {"id": "assistant", "model": {"primary": "google/gemini-2.5-pro", "fallbacks": ["zai/glm-5"]}},
    {"id": "media", "model": {"primary": "google/gemini-2.5-pro"}},
    {"id": "operator", "model": {"primary": "google/gemini-3.1-pro-preview"}},
    {"id": "service", "model": {"primary": "google/gemini-3.1-pro-preview"}}
  ],
  
  "channels": {
    "feishu": {
      "accounts": {
        "default":  {"appId": "cli_xxx", "appSecret": "SEC", "agent": "assistant"},
        "media":    {"appId": "cli_yyy", "appSecret": "SEC", "agent": "media"},
        "operator": {"appId": "cli_zzz", "appSecret": "SEC", "agent": "operator"},
        "service":  {"appId": "cli_www", "appSecret": "SEC", "agent": "service"}
      }
    }
  },
  
  "tools": {
    "profile": "full",
    "exec": {"security": "full", "ask": "off"},
    "elevated": {"enabled": true}
  },
  
  "workspace": "${HOME}/projects/tian_agent",
  
  "config_patches": {
    "agents.defaults.thinking": "high"
  }
}
```

### deploy.json 字段说明

| 字段 | 作用 | 合并策略 |
|------|------|----------|
| `providers` | 模型供应商 | **不覆盖**已有同名 provider |
| `agents` | Agent 列表 + 模型 | **不覆盖**已有同 id agent |
| `channels` | 渠道账号绑定 | **不覆盖**已有账号，但补充缺失的 `agent` 路由 |
| `tools` | 权限配置 | **直接覆盖** |
| `workspace` | 默认工作区 | 支持 `${HOME}` `${PROJECT}` 变量 |
| `config_patches` | 任意 dot-path 补丁 | 精确设置到指定路径 |

**安全原则**：已有配置不覆盖，避免破坏远程机器现有服务。

## 使用方法

### 基本部署

```bash
./skills/remote-openclaw-deploy/scripts/deploy.sh \
  laotian@100.91.44.116 \
  ~/projects/private_tian_agent \
  ~/.ssh/id_ed25519
```

### 无 deploy.json（仅传文件 + 基础权限）

如果项目没有 deploy.json，脚本只做：
1. 传输 agents/ skills/ workspace/
2. 设置 tools.profile=full, exec=full, elevated=true
3. 设置 workspace 路径
4. 重启 Gateway

Provider、Channel 需手动配置。

### 更新部署

```bash
# 本地改完代码后
cd ~/projects/my_project && git commit -am "update"
# 重新部署（幂等，不会覆盖已有配置）
./deploy.sh user@ip ~/projects/my_project
```

## 5 Phase 流程

| Phase | 动作 | 跨平台 |
|-------|------|--------|
| **1. 环境探测** | SSH 连通、OS/内存/磁盘、OpenClaw 版本、Gateway 状态 | ✅ macOS + Linux |
| **2. 传输文件** | agents/ → ~/.openclaw/agents/, skills/ → ~/.openclaw/skills/, 项目 → ~/projects/ | ✅ 自动检测 HOME |
| **3. 配置注入** | 读 deploy.json → 合并到 openclaw.json（provider/agent/channel/tools/workspace） | ✅ Python3 |
| **4. 重启 Gateway** | SIGUSR1 热重载 → 回退到 gateway install/start | ✅ |
| **5. 验证** | 配置错误、WS 连接数、Agent 列表、Channel 账号绑定 | ✅ |

## 踩坑清单（实战总结）

| 坑 | 现象 | 正确做法 |
|----|------|----------|
| 飞书 account 没 `agent` 字段 | 所有消息路由到 main | 每个 account 必须显式 `"agent": "<id>"` |
| `workspace` 放顶层 | Unknown key，Gateway 崩溃 | 用 `agents.defaults.workspace` |
| `agent.cwd` | Legacy key 警告 | 已废弃，用 `agents.defaults.workspace` |
| `tools.elevated` 写布尔值 | 类型错误 | 必须 `{"enabled": true}` 对象 |
| `tools.profile: "default"` | 无效值 | 只能 minimal/coding/messaging/full |
| xingsuancode 503 | No available accounts | 切 fallback，原模型降级 |
| Tailscale + Clash fake-ip | SSH 连不上域名 | 直接用 IP `100.x.x.x` |
| `/Users/$USER` 硬编码 | Linux 上路径错误 | 用 `$HOME` 自动检测 |

## 模板

- `templates/deploy.json.template` — deploy.json 模板，复制到项目根目录修改即可

## 前置条件

1. SSH 可达（推荐 Tailscale 组网）
2. 目标机已安装 OpenClaw
3. 目标机有 Python3
4. 本地有项目文件 + deploy.json

## FAQ

**Q: 部署后 Agent 不回消息？**
A: 排查：① Channel account 有 `agent` 字段？ ② 模型是否 503？ ③ tools.profile 够不够？

**Q: 如何支持 Telegram/Discord？**
A: 在 deploy.json 的 `channels` 里加对应渠道配置，格式参照 OpenClaw 文档。

**Q: 多台机器部署同一项目？**
A: 循环跑脚本即可：
```bash
for host in user1@ip1 user2@ip2; do
  ./deploy.sh $host ~/projects/my_project
done
```

**Q: 如何回滚？**
A: 远程机器 `cd ~/projects/<name> && git checkout <commit>` → 重跑脚本。
