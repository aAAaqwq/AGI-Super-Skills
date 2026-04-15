---
name: codex-cc-guide
description: 如何用 ACP sessions_spawn 调用 Claude Code / Codex 写代码 — 小code 团队编码任务指南
trigger: acp codex / claude code / sessions_spawn acp / /acp spawn / CC 写代码 / ACP 调用 CC
---

# ACP 调用 Claude Code / Codex 写代码指南

## 核心：sessions_spawn + runtime: "acp"

在 OpenClaw 里，agent 可以直接用 `sessions_spawn` 调起 Claude Code 或 Codex，写代码像发指令一样简单。

### 最常用：Claude Code（已装在 /usr/bin/claude）

```javascript
sessions_spawn({
  task: "用 TypeScript 重构 ~/project/src/api.ts，加入错误处理和类型定义",
  runtime: "acp",
  agentId: "claude",        // 或 "claude-code"
  label: "重构-api",
  mode: "run",              // run=一次性，session=持久会话
  cleanup: "delete"         // 完成后删除 session
})
```

### Codex（需要额外配置）

```javascript
sessions_spawn({
  task: "写一个 Python FastAPI CRUD 接口",
  runtime: "acp",
  agentId: "codex",
  model: "openai/gpt-5.4",
  label: "fastapi-crud"
})
```

## 两种模式：一次性 vs 持久会话

| 模式 | 参数 | 适用场景 |
|------|------|---------|
| **一次性** | `mode: "run"` | 单个任务，完成即删，最省资源 |
| **持久会话** | `mode: "session"` | 多步骤迭代、需要上下文累积 |

```javascript
// 一次性：适合简单任务
sessions_spawn({
  task: "在 /tmp 创建一个 React 组件 Counter.tsx",
  runtime: "acp",
  agentId: "claude",
  mode: "run"
})

// 持久会话：适合复杂项目
sessions_spawn({
  task: "继续上次的工作，修复登录页面的 bug",
  runtime: "acp",
  agentId: "claude",
  mode: "session",
  label: "react-project"
})
```

## 持久会话 + thread：绑定到 Telegram 话题

```javascript
sessions_spawn({
  task: "用 Next.js 14 App Router 重构整个电商前端",
  runtime: "acp",
  agentId: "claude",
  thread: true,              // 绑定到当前 Telegram thread
  mode: "session",
  label: "nextjs重构"
})
```

完成后 Claude Code 的输出会自动推送到 Telegram thread 里。

## 聊天指令（人类直接用）

在 Telegram 发这些指令即可：

```
/acp spawn claude 帮我写一个 Docker Compose 文件

/acp spawn codex 用 Rust 写一个 http server

/acp status   查看当前 ACP 会话状态

/acp cancel    取消当前任务

/acp close     关闭会话
```

## 小code 团队标准工作流

**场景**：Daniel 让你写一个 API

**错误做法**（慢、资源浪费）：
```
自己开模型 → 写代码 → 测试 → 修 bug → 循环
```

**正确做法**（用 ACP + Claude Code）：
```
1. 理解需求，确定技术栈和文件位置
2. sessions_spawn 调起 Claude Code 一次性任务
3. Claude Code 完成后你负责 review
4. 有问题再调一次 Claude Code 修
```

```javascript
// 示例：Daniel 让小code 写一个用户认证 API
sessions_spawn({
  task: `在 ~/clawd/projects/api/ 下创建用户认证模块：
  - POST /auth/login（邮箱+密码，返回 JWT）
  - POST /auth/register（邮箱+密码+昵称）
  - GET /auth/me（返回当前用户信息，需带 Bearer token）
  - 使用 Python FastAPI + SQLite
  - 密码用 bcrypt 哈希
  - JWT secret 从环境变量 AUTH_SECRET 读取
  - 代码要可以运行，有完整的错误处理`,
  runtime: "acp",
  agentId: "claude",
  label: "auth-api"
})
```

## 关键规则

1. **任务描述要具体**：包含文件路径、技术栈、具体要求
2. **清理 session**：`cleanup: "delete"` 避免垃圾积累
3. **并发控制**：最多同时跑 3 个 ACP 会话
4. **Review 是你的活**：Claude Code 写完你要检查，不是直接交付

## 错误排查

| 症状 | 检查项 |
|------|--------|
| `sessions_spawn` 没反应 | 确认 `acp.enabled: true` 在 openclaw.json |
| Claude Code 报错 "not found" | 确认 `/usr/bin/claude` 存在 |
| 会话卡住 | `/acp cancel` 然后重试 |
| 输出没推送到 Telegram | 确认 `thread: true` 且在支持 thread 的 channel |

## 配置文件参考

```json5
{
  acp: {
    enabled: true,
    defaultAgent: "claude",
    allowedAgents: ["claude", "codex", "gemini-cli"]
  }
}
```
