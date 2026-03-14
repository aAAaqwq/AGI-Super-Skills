---
title: "OpenClaw ACP/acpx 完整配置与排错指南"
date: 2026-03-03
status: verified
tags: [acp, acpx, debug, setup, openclaw]
---

# OpenClaw ACP/acpx 完整配置与排错指南

> 从零配置 ACP（Agent Client Protocol），让 OpenClaw 通过 `sessions_spawn` 调度 Claude Code / Codex 执行编码任务。
> 基于 2026-03-03 实战调试经验，OpenClaw 2026.3.1 + acpx 0.1.15。

## TL;DR

ACP 需要 **6 项配置全部正确** 才能工作。任何一项缺失都会导致静默失败（返回 `accepted` 但不执行）。

## 前置条件

- OpenClaw 2026.3.x+ 已安装（推荐 homebrew：`npm i -g openclaw`）
- Claude Code CLI (`claude`) 已安装并可用
- `claude --version` 正常输出

## 配置清单（6 项，缺一不可）

### ⚠️ 第 0 步：确保 Gateway Service 和 CLI 用同一份 OpenClaw

**这是 ACP 不工作的 #1 根因。**

```bash
# 检查 gateway service 的 entrypoint
openclaw gateway status | grep "Command:"
```

如果显示 `~/.npm/_npx/` 路径而不是安装路径 → **必须修**。

**为什么会出这个问题？**
npx 首次运行 OpenClaw 会缓存到 `~/.npm/_npx/`。LaunchAgent 记住了这个路径。之后用 homebrew/npm -g 安装了正式版，但 service 还在跑缓存版。导致：
- Gateway 从 npx 缓存加载 acpx（路径 A）
- `openclaw agents add` 操作正式安装版（路径 B）
- 两者不一致 → acpx duplicate + ACP dispatch 失败

```bash
# 修复方法
# macOS:
sed -i '' 's|/Users/<user>/.npm/_npx/.*/openclaw/dist/index.js|/opt/homebrew/lib/node_modules/openclaw/dist/index.js|' \
  ~/Library/LaunchAgents/ai.openclaw.gateway.plist

# 重启 service
launchctl unload ~/Library/LaunchAgents/ai.openclaw.gateway.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.gateway.plist

# 或者用 doctor（可能不会自动修）
openclaw doctor --repair
```

### 第 1 步：注册 Agent

```bash
mkdir -p ~/.openclaw/agents/claude/workspace
mkdir -p ~/.openclaw/agents/claude/agent

openclaw agents add claude \
  --workspace ~/.openclaw/agents/claude/workspace \
  --model anthropic/claude-sonnet-4-6 \
  --non-interactive
```

> ⚠️ workspace 不要用 `/tmp`，重启后丢失。用持久路径。

### 第 2 步：openclaw.json — agents.list

确保 `agents.list` 包含注册的 agent：

```json
{
  "agents": {
    "list": [
      { "id": "main" },
      {
        "id": "claude",
        "name": "claude",
        "workspace": "/Users/<user>/.openclaw/agents/claude/workspace",
        "agentDir": "/Users/<user>/.openclaw/agents/claude/agent",
        "model": "anthropic/claude-sonnet-4-6"
      }
    ]
  }
}
```

### 第 3 步：openclaw.json — ACP 三层开关

三层全开，缺任何一层都静默失败：

```json
{
  "acp": {
    "enabled": true,
    "dispatch": { "enabled": true },
    "defaultAgent": "claude",
    "allowedAgents": ["claude"]
  }
}
```

| 缺哪个 | 现象 |
|---------|------|
| `acp.enabled` | spawn 被拒 |
| `acp.dispatch.enabled` | 日志报 `ACP_DISPATCH_DISABLED` |
| `allowedAgents` | spawn 被拒 |

### 第 4 步：acpx 插件配置

```json
{
  "plugins": {
    "allow": ["acpx", ...],
    "entries": {
      "acpx": {
        "enabled": true,
        "config": {
          "permissionMode": "approve-all",
          "nonInteractivePermissions": "deny",
          "queueOwnerTtlSeconds": 300
        }
      }
    },
    "installs": {
      "acpx": {
        "source": "path",
        "spec": "@openclaw/acpx",
        "sourcePath": "/opt/homebrew/lib/node_modules/openclaw/extensions/acpx",
        "installPath": "/opt/homebrew/lib/node_modules/openclaw/extensions/acpx"
      }
    }
  }
}
```

**关键参数说明：**

| 参数 | 默认值 | 推荐值 | 原因 |
|------|--------|--------|------|
| `permissionMode` | `approve-reads` | `approve-all` | 非交互模式必须，否则 Claude Code 请求权限时挂起 |
| `nonInteractivePermissions` | `fail` | `deny` | `fail` 会让进程崩溃，`deny` 优雅跳过 |
| `queueOwnerTtlSeconds` | `0.1` (100ms) | `300` | 默认太短，进程还没跑完就被杀 |

### 第 5 步：清理 Duplicate Plugin

OpenClaw 会从两个地方加载 acpx：
1. `plugins.installs` 中注册的路径
2. Gateway 进程 CWD 下的 `extensions/acpx/`

如果 service 指向 npx 缓存（第 0 步的问题），就会加载两份。

```bash
# 诊断
grep "duplicate" ~/.openclaw/logs/gateway.log | tail -5

# 确保 plugins.load.paths 为空（不重复加载）
# "load": { "paths": [] }

# 清理 npx 缓存
find ~/.npm/_npx -path "*/openclaw/extensions/acpx" -type d -exec rm -rf {} + 2>/dev/null
```

## 常见错误速查表

| 错误 | 原因 | 修复 |
|------|------|------|
| `ACP_DISPATCH_DISABLED` | `acp.dispatch.enabled` 未设 | config patch |
| `acpx exited with code 5` | session 找不到 / Gateway 用错误版本 | 检查第 0 步 |
| `acpx exited with code 4` | `.omc/` 目录不存在 | ensure session |
| `Permission prompt unavailable` | `permissionMode` 未设 approve-all | 第 4 步 |
| `Queue owner disconnected` | `queueOwnerTtlSeconds` 太短 | 改成 300 |
| `identity reconcile failed` | 旧 session 残留 | 删 `.omc/` 重来 |
| `ACP runtime backend not configured` | acpx 插件未安装/未启用 | 第 4 步 |
| `agents_list 只有 main` | 正常！`agents_list` 是给 subagent 用的 | ACP 用 `acp.allowedAgents` |
| `duplicate plugin id detected` | npx 缓存 + installs 都加载了 | 第 0 步 + 第 5 步 |
| spawn `accepted` 但 session 空 | 多种可能 | 按顺序检查第 0-5 步 |

## 诊断命令速查

```bash
# 1. Gateway 版本一致性
openclaw gateway status | grep "Command:"

# 2. 无 duplicate
grep "duplicate" ~/.openclaw/logs/gateway.log | tail -5

# 3. acpx 状态
grep "acpx.*ready" ~/.openclaw/logs/gateway.log | tail -1

# 4. agent 注册
openclaw agents list

# 5. ACP dispatch 错误
grep "ACP" ~/.openclaw/logs/gateway.log | tail -5

# 6. 完整 doctor 检查
openclaw doctor --non-interactive
```

## 手动测试 acpx CLI

如果 OpenClaw dispatch 不工作，先验证底层 acpx CLI 是否正常：

```bash
ACPX=/opt/homebrew/lib/node_modules/openclaw/extensions/acpx/node_modules/.bin/acpx

# 1. ensure session
$ACPX --format json --json-strict --cwd /tmp/test claude sessions ensure --name test

# 2. run prompt
echo 'echo hello' | $ACPX --format json --json-strict --cwd /tmp/test \
  --approve-all --timeout 30 --ttl 300 \
  claude prompt --session test --file -
```

如果手动能跑但 OpenClaw dispatch 不行 → 问题在 Gateway 配置/路径。

## 清理检查清单

确保系统干净：

```bash
# 残留进程
ps aux | grep "acpx\|openclaw.*install" | grep -v grep

# npx 缓存
find ~/.npm/_npx -path "*acpx*" 2>/dev/null

# 无用 agent 目录
ls ~/.openclaw/agents/

# .omc session 残留
find /tmp -name ".omc" -type d 2>/dev/null
```

## 调试时间线（实际经历）

| 时间 | 问题 | 修复 |
|------|------|------|
| 11:50 | `sessions_spawn` accepted 但 session 空 | 发现 ACP agent 未注册 |
| 12:04 | `openclaw agents add` 注册 claude/codex | ✅ |
| 12:07 | `acp.enabled: true` 但还是不行 | 发现缺 `dispatch.enabled` |
| 13:07 | 日志报 `ACP_DISPATCH_DISABLED` | 加 `acp.dispatch.enabled: true` |
| 13:17 | dispatch 通了但 `acpx exited with code 5` | 发现 duplicate plugin |
| 13:26 | 手动 acpx CLI 测试成功 | 问题在 gateway → acpx 管道 |
| 13:33 | 清空 `plugins.load.paths` | duplicate 仍在 |
| 13:37 | 加 acpx config (approve-all, TTL 300) | code 5 不再报但 session 仍空 |
| 13:39 | 彻底清理重装 | 手写 config |
| 13:50 | `openclaw doctor` 发现 service 用 npx 缓存版！ | **根因！** |
| 14:10 | 改 plist entrypoint 到 homebrew 路径 | ✅ |
| 14:18 | `ACP_FINALLY_WORKS_1772518678` | **🎉 成功** |

**总耗时：2.5 小时。根因就是一行 plist 路径。**

## 经验总结

1. **`openclaw doctor` 是第一步**，不是最后一步
2. **Service 版本一致性** 比任何配置都重要
3. **ACP 的三层开关设计** 导致排查困难——缺任何一层都静默失败
4. **`sessions_spawn` 返回 `accepted` 不代表成功**——必须在 30s 内验证 session 有输出
5. **acpx 默认参数对非交互不友好**——`permissionMode` 和 `queueOwnerTtlSeconds` 必须手动调
6. **npx 缓存是隐形杀手**——首次 npx 运行后 service 记住了缓存路径，正式安装后不会自动更新
