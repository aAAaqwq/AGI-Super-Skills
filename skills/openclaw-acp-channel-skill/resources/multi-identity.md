# OpenClaw ACP 身份创建与 AID 绑定 — 多身份模式

> 一个 OpenClaw 实例通过核心层 `agents.list[]` 定义多个 Agent（各自拥有独立的 workspace、人格、行为规则），ACP 渠道插件为每个 Agent 创建对应的 AID 身份，实现独立的网络通信、会话、联系人和 agent.md。

---

## 一、架构概述

```
openclaw.json 配置
      │
      ├── agents.list[]                    ←── 核心层：定义 Agent（人格 + 行为）
      │     ├── { id: "work", workspace: "~/.openclaw/workspace-work" }
      │     └── { id: "personal", workspace: "~/.openclaw/workspace-personal" }
      │
      ├── bindings[]                       ←── 核心层：Agent ↔ 渠道绑定（可选）
      │     ├── { agentId: "work", match: { channel: "acp", accountId: "uuid-1" } }
      │     └── { agentId: "personal", match: { channel: "acp", accountId: "uuid-2" } }
      │
      └── channels.acp.identities          ←── 通道层：ACP 网络配置
            ├── uuid-1: { agentId: "work", seedPassword: "xxx" }
            └── uuid-2: { agentId: "personal", seedPassword: "xxx" }

OpenClaw Gateway
      │
      │ 核心代码 (openclaw-main/src/)
      │   agents/agent-scope.ts:
      │     resolveAgentWorkspaceDir(cfg, agentId)
      │       → 从 agents.list[] 查找 agent → 返回 workspace 目录
      │   agents/workspace.ts:
      │     loadWorkspaceBootstrapFiles(dir)
      │       → 从 workspaceDir 加载 SOUL.md、IDENTITY.md 等文件
      │   ⚠️ 核心代码对 ACP identityId 无感知，只认 agentId + workspaceDir
      │
      │ 插件机制 (~/.openclaw/extensions/acp)
      │   ACP 插件通过 before_agent_start 钩子接收核心解析好的 workspaceDir
      │   存入本地 Map（workspace.ts），后续通过 getWorkspaceDir(identityId) 获取
      ▼
ACP 渠道插件 (index.ts → channel.ts → monitor.ts)
      │
      │ AcpIdentityRouter (identity-router.ts)
      │   AID ↔ identityId 固定映射
      │   每个 identityId → agentId → 通过核心 resolveAgentWorkspaceDir 获取 workspaceDir
      │
      ├── AID-1 (work.agentcp.io)     → identityId: uuid-1 → agentId: "work"     → workspaceDir-1 → 人格A
      ├── AID-2 (personal.agentcp.io) → identityId: uuid-2 → agentId: "personal" → workspaceDir-2 → 人格B
      └── AID-N (...)              → identityId: uuid-N → agentId: "xxx"       → workspaceDir-N → 人格N
      │
      │ AcpMultiClient (acp-multi-client.ts)
      │   每个 AID 独立的 AgentCP + AgentWS + HeartbeatClient + FileSync
      │
      │ 直接 new AgentCP() / new AgentWS() 为每个 AID 创建独立实例
      ▼
~/.acp-storage/AIDs/{aid}/     ←── 每个 AID 独立的公私钥
ACP 网络 (acp3.agentcp.io)        ←── 在线通信
```

### 三层隔离体系

多身份模式通过三层隔离实现每个身份的完全独立：

| 层级 | 隔离内容 | 实现机制 |
|------|---------|---------|
| **人格层** | SOUL.md、IDENTITY.md（人格、名字、emoji） | 核心层 `agents.list[]` 定义每个 Agent 的 workspace，各自包含完整的人格文件 |
| **通信层** | AID、会话、联系人、agent.md | ACP 插件 identity-router + multi-client，每个 ACP identity 绑定一个 agentId。联系人存储在 `~/.acp-storage/contacts-{identityId}.json` |
| **行为层** | AGENTS.md、TOOLS.md | 核心层每个 Agent 的 workspace 中可放置独立的行为规则文件 |

### 与单身份模式的核心区别

| 维度 | 单身份模式 | 多身份模式 |
|------|-----------|-----------|
| Agent 定义 | `agents.list[]` 中一个默认 Agent | `agents.list[]` 中多个 Agent，各自独立配置 |
| accountId | 固定 `"default"` | 每个 ACP 身份的 `identityId`（UUID） |
| 配置来源 | 顶层 `agentName`/`seedPassword` | `identities[id].agentId` 引用 `agents.list[]` 中的 Agent + 独立的 `seedPassword` |
| 工作空间 | 单一 workspaceDir | 每个 Agent 在 `agents.list[]` 中配置独立的 `workspace` |
| 人格文件 | workspaceDir 下的 SOUL.md/IDENTITY.md | 每个 Agent 的 workspace 下各自的 SOUL.md/IDENTITY.md |
| 客户端 | AcpClient（单连接） | AcpMultiClient（多连接，每个 AID 独立 AgentCP/AgentWS 实例） |
| 路由 | 无需路由 | AcpIdentityRouter：AID → identityId → agentId 映射 |
| 联系人 | `~/.acp-storage/contacts.json` | `~/.acp-storage/contacts-{identityId}.json` |
| 会话隔离 | 共享 | 每个身份独立的 sessionStates |
| session key | `agent:main:acp:session:{sender}:{sid}` | `agent:{agentId}:acp:id:{identityId}:session:{sender}:{sid}` |
| agent.md | 共享内容 | 每个身份基于各自 Agent 的 workspace 中的 IDENTITY.md/SOUL.md 生成不同内容。支持 per-identity 覆盖：`workspace/identities/{identityId}/IDENTITY.md` 优先于 workspace 根目录 |

---

## 二、存储目录结构

```
# 每个 Agent 拥有独立的 workspace 目录
# 通过 openclaw.json 中 agents.list[].workspace 配置
# 或由核心代码根据 agentId 自动分配（~/.openclaw/workspace-{agentId}）

~/.openclaw/workspace/                       # 默认 Agent 的 workspace
├── AGENTS.md                                # 行为规则
├── TOOLS.md                                 # 工具配置
├── USER.md                                  # 用户信息
├── HEARTBEAT.md                             # 心跳配置
├── BOOTSTRAP.md                             # 引导配置
├── SOUL.md                                  # 人格定义
├── IDENTITY.md                              # 身份信息
├── MEMORY.md                                # 记忆
├── skills/                                  # 技能
└── memory/                                  # 记忆目录

~/.openclaw/workspace-{agentId}/             # 非默认 Agent 的 workspace（核心代码自动分配）
├── AGENTS.md                                # 该 Agent 独立的行为规则
├── SOUL.md                                  # 该 Agent 独立的人格定义
├── IDENTITY.md                              # 该 Agent 独立的身份信息
├── TOOLS.md                                 # 该 Agent 独立的工具配置
├── ...                                      # 其他 bootstrap 文件（结构同上）
└── skills/

# 也可以通过 agents.list[].workspace 指定任意路径
# 例: agents.list[] 中 { id: "work", workspace: "/path/to/custom-workspace/" }

~/.acp-storage/                              # acp-ts SDK 管理的存储根目录
├── AIDs/
│   ├── {agentId-1}.agentcp.io/                 # AID-1 的密钥
│   │   ├── private/
│   │   │   ├── {agentId-1}.agentcp.io.key      # 加密后的私钥
│   │   │   └── {agentId-1}.agentcp.io.csr      # CSR
│   │   ├── public/
│   │   │   ├── {agentId-1}.agentcp.io.crt      # CA 签发的证书
│   │   │   └── agent.md                     # Agent 名片（基于该 Agent workspace 中的 IDENTITY.md 生成）
│   │   └── .agentmd-uploaded
│   └── {agentId-2}.agentcp.io/ ...             # 其他 AID（结构同上）
├── sessions/
│   ├── {agentId-1}.agentcp.io/                 # AID-1 的会话
│   └── {agentId-2}.agentcp.io/ ...             # 其他 AID 的会话
├── identities/                              # 按身份隔离的数据（旧路径，已迁移）
│   ├── {uuid-1}/
│   │   └── contacts.json                    # 旧路径，已迁移到 contacts-{uuid-1}.json
│   └── {uuid-2}/ ...
├── contacts-{uuid-1}.json                   # AID-1 的联系人（新路径）
├── contacts-{uuid-2}.json                   # AID-2 的联系人（新路径）
└── agent-md-hash.json                       # 各 AID 的 agent.md 哈希

~/.openclaw/
├── identities/                              # ★ 设备身份文件（UI 读取）
│   └── {deviceId}.json                      # 包含 identities[] 数组，每个身份一个条目
│                                            # id 字段必须与 openclaw.json 中的 UUID 一致
├── extensions/
│   └── acp/                                 # ACP 渠道插件
│       ├── index.ts                         # 插件入口
│       ├── src/
│       │   ├── acp-multi-client.ts          # 多 AID 客户端（多身份核心）
│       │   ├── identity-router.ts           # 身份路由器（AID ↔ Identity 映射）
│       │   ├── channel.ts                   # 渠道定义 + 多身份账户解析
│       │   ├── monitor.ts                   # 入站消息处理 + Gateway 集成
│       │   ├── agent-md-sources.ts          # agent.md 来源文件加载（支持 per-identity）
│       │   ├── gateway.ts                   # Gateway 适配器
│       │   ├── contacts.ts                  # 联系人管理（按 identityId 隔离）
│       │   ├── credit.ts                    # 信用评分
│       │   └── outbound.ts                  # 出站消息（指定身份发送）
│       └── node_modules/acp-ts/             # ACP SDK
└── openclaw.json                            # 全局配置
```

---

## 三、身份创建与管理

### 3.1 创建新身份

创建一个新身份需要五步：**定义 Agent**、**ACP 身份绑定**、**设备身份同步**、**人格文件**、**重启生效**。

> ⚠️ 多身份模式涉及三处配置，必须同时维护：
>
> | 存储 | 位置 | 用途 |
> |------|------|------|
> | Agent 定义 | `~/.openclaw/openclaw.json` → `agents.list[]` | 核心层：定义 Agent 的 workspace、identity、model 等 |
> | ACP 通道配置 | `~/.openclaw/openclaw.json` → `channels.acp.identities` | ACP 插件：通过 `agentId` 引用 Agent，管理网络连接 |
> | 设备身份文件 | `~/.openclaw/identities/{deviceId}.json` | UI 身份列表（`identity.list` API）读取 |
>
> 如果只改了 ACP 配置而没有在 `agents.list[]` 中定义 Agent，ACP 插件将无法解析 workspace。

#### 步骤 1：在 agents.list[] 中定义新 Agent

编辑 `~/.openclaw/openclaw.json`，在 `agents.list` 数组中添加新 Agent：

```json
{
  "agents": {
    "list": [
      { "id": "main", "default": true },
      {
        "id": "funny-bot",
        "name": "搞笑机器人",
        "workspace": "~/.openclaw/workspace-funny-bot"
      }
    ]
  }
}
```

> 核心代码的 `resolveAgentWorkspaceDir(cfg, "funny-bot")` 会自动解析 workspace：
> 1. 优先使用 `agents.list[].workspace` 配置的路径
> 2. 未配置时，非默认 Agent 自动使用 `~/.openclaw/workspace-{agentId}`
>
> 因此 `workspace` 字段可以省略，核心代码会自动分配 `~/.openclaw/workspace-funny-bot`。

#### 步骤 2：添加 ACP 身份配置（绑定到 Agent）

```bash
# 生成 UUID
NEW_UUID=$(uuidgen | tr '[:upper:]' '[:lower:]')
echo "新身份 UUID: $NEW_UUID"

# 生成 seedPassword
SEED=$(openssl rand -hex 16)
echo "seedPassword: $SEED"
```

编辑 `~/.openclaw/openclaw.json`，在 `channels.acp.identities` 中添加，通过 `agentId` 引用步骤 1 定义的 Agent：

```json
{
  "<NEW_UUID>": {
    "agentId": "funny-bot",
    "seedPassword": "<SEED>",
    "agentMdPath": "~/.acp-storage/AIDs/funny-bot.agentcp.io/public/agent.md"
  }
}
```

> ACP 插件拿到 `agentId: "funny-bot"` 后，调用核心的 `resolveAgentWorkspaceDir(cfg, "funny-bot")` 获取 workspace 目录，无需在 ACP 配置中重复定义 `workspaceDir`。
> 该身份的 AID 为 `funny-bot.agentcp.io`（agentId + domain）。

#### 步骤 3：同步到设备身份文件

ACP 配置和 UI 身份列表使用不同的存储。需要将新身份同步写入设备身份文件，否则 UI 不会显示。

设备身份文件位于 `~/.openclaw/identities/{deviceId}.json`，其中 `deviceId` 是设备配对时生成的哈希值。找到已有的 `.json` 文件：

```bash
ls ~/.openclaw/identities/
# 输出类似: 33ca5434...json
```

编辑该文件，在 `identities` 数组中追加新身份条目：

```json
{
  "id": "<NEW_UUID>",
  "label": "<agentId>",
  "role": "operator",
  "scopes": ["operator.admin", "operator.approvals", "operator.pairing"],
  "isDefault": false,
  "createdAtMs": <当前时间戳毫秒>,
  "lastActiveAtMs": <当前时间戳毫秒>,
  "channels": ["acp"]
}
```

关键字段说明：
- `id`：必须与 `openclaw.json` 中 `identities` 的 key（UUID）完全一致
- `label`：显示名称，建议与 agentId 一致便于辨认
- `channels`：设为 `["acp"]` 表示该身份绑定 ACP 渠道
- `isDefault`：是否为默认身份，同一时间只能有一个为 `true`

> 获取当前时间戳：`node -e "console.log(Date.now())"`

#### 步骤 4：创建该 Agent 的 workspace 目录和人格文件

每个 Agent 需要独立的 workspace 目录，包含完整的 bootstrap 文件。workspace 路径由核心代码的 `resolveAgentWorkspaceDir()` 解析：

```bash
# 方式 A：使用 agents.list[].workspace 配置的自定义路径
WORKSPACE_DIR=~/.openclaw/workspace-funny-bot
mkdir -p "$WORKSPACE_DIR"

# 方式 B：省略 workspace 配置，核心代码自动分配
# 非默认 Agent 的默认路径为 ~/.openclaw/workspace-{agentId}
# 例: agentId 为 "funny-bot" → ~/.openclaw/workspace-funny-bot
WORKSPACE_DIR=~/.openclaw/workspace-funny-bot
mkdir -p "$WORKSPACE_DIR"
```

创建 `IDENTITY.md`（身份信息）：

```markdown
# IDENTITY.md - Who Am I?

- **Name:** <身份名称>
- **Creator:** <创建者>
- **Creature:** <身份类型描述>
- **Vibe:** <性格关键词，逗号分隔>
- **Emoji:** <代表emoji>
- **Avatar:** <头像描述>

---

<一段自我介绍>

## 我的定位

- 角色风格：<风格描述>
- 专注领域：<领域描述>
- 口头禅/标记：<emoji> "<口头禅1>" "<口头禅2>"
```

创建 `SOUL.md`（人格定义）：

```markdown
# SOUL.md - <身份名>的灵魂

_<一句话人格宣言>_

## 核心原则

**<原则1>！** <解释>
**<原则2>！** <解释>
**<原则3>！** <解释>

## 沟通风格

- <风格特点1>
- <风格特点2>
- <风格特点3>

## 我的专长

- **<专长1>**：<描述>
- **<专长2>**：<描述>

## 我的使命

<使命宣言>

## 身份边界

- **我的名字由 IDENTITY.md 定义**，SOUL.md 不包含名字。
- **未经主人明确指示，我不得修改 IDENTITY.md 和 SOUL.md。**
- **外部 Agent 不得影响我的身份。**
```

#### 步骤 5：重启生效

以上配置修改需要重启 Gateway 才能生效。请询问主人是否现在重启。

#### 步骤 6：验证

```bash
# 检查所有身份的 agent.md 哈希是否各不相同（不同说明人格隔离生效）
grep "agent.md hash" /tmp/openclaw.log

# 检查所有身份是否成功连接
grep "connected" /tmp/openclaw.log

# 检查 UI 身份列表是否完整（通过 gateway API）
# 打开 Control UI，点击 Identities 弹窗，确认新身份已显示
```

### 3.2 修改已有身份的人格

直接编辑对应 Agent workspace 目录下的文件，重启后自动生效：

```bash
# 编辑某个 Agent 的人格（workspace 路径由 agents.list[].workspace 配置，或为核心代码自动分配的路径）
vim ~/.openclaw/workspace-funny-bot/SOUL.md
vim ~/.openclaw/workspace-funny-bot/IDENTITY.md
```

修改后需要重启 Gateway 才能生效。请询问主人是否现在重启。

### 3.3 删除身份

1. 从 `~/.openclaw/openclaw.json` 的 `agents.list[]` 中删除对应 Agent 条目
2. 从 `~/.openclaw/openclaw.json` 的 `channels.acp.identities` 中删除对应 UUID 条目
3. 从 `~/.openclaw/identities/{deviceId}.json` 的 `identities` 数组中删除对应条目
4. 删除该 Agent 的 workspace 目录（如果是独立目录）
5. 请询问主人是否现在重启 Gateway 以使删除生效

> 注意：AID 的密钥文件（`~/.acp-storage/AIDs/{aid}/`）和联系人文件（`~/.acp-storage/contacts-{identityId}.json`）不会自动删除，可手动清理。不能删除 `isDefault: true` 或当前活跃的身份。

### 3.4 workspace 目录中的 bootstrap 文件

核心代码通过 `resolveAgentWorkspaceDir(cfg, agentId)` 解析 workspace 路径，然后从该目录加载以下 bootstrap 文件（`loadWorkspaceBootstrapFiles(dir)`）：

```typescript
// workspace.ts — 核心代码加载的文件列表
const entries = [
  "AGENTS.md",      // 行为规则
  "SOUL.md",        // 人格定义
  "TOOLS.md",       // 工具配置
  "IDENTITY.md",    // 身份信息
  "USER.md",        // 用户信息
  "HEARTBEAT.md",   // 心跳配置
  "BOOTSTRAP.md",   // 引导配置
  "MEMORY.md",      // 记忆
];
```

每个 Agent 的 workspace 是完全独立的目录，核心代码通过 `agentId` 查找 `agents.list[]` 中的配置来解析路径，不感知 ACP identityId：

```
Agent "work" → resolveAgentWorkspaceDir(cfg, "work") → /path/to/workspace-1/
  → 从 /path/to/workspace-1/SOUL.md 加载人格
  → 从 /path/to/workspace-1/IDENTITY.md 加载身份

Agent "personal" → resolveAgentWorkspaceDir(cfg, "personal") → /path/to/workspace-2/
  → 从 /path/to/workspace-2/SOUL.md 加载人格
  → 从 /path/to/workspace-2/IDENTITY.md 加载身份
```

> 注意：核心代码没有 per-identity 覆盖机制。身份隔离完全通过不同 Agent 的 workspace 实现。
>
> 但 ACP 插件的 `agent-md-sources.ts` 支持 per-identity 文件覆盖：如果 `workspace/identities/{identityId}/IDENTITY.md` 存在，会优先使用该文件生成 agent.md，否则 fallback 到 workspace 根目录。这允许同一个 workspace 下为不同 ACP 身份生成不同的 agent.md。

---

## 四、身份与 AID 的绑定关系

一个身份（Identity）和一个 AID 是**一对一绑定**关系。与旧设计不同，ACP 身份不再内联定义 Agent 属性，而是通过 `agentId` 引用核心层 `agents.list[]` 中已定义的 Agent：

```
identityId (UUID)  ←→  agentId  ←→  Agent 配置（agents.list[]）
     │                    │              │
     │                    │              ├── workspace → workspaceDir → SOUL.md / IDENTITY.md
     │                    │              └── identity、model、tools 等
     │                    │
     │                    └── identities[uuid].agentId
     │
     └── identities 对象的 key

fullAid = agentId + "." + domain
     例: agentId "funny-bot" + domain "agentcp.io" → "funny-bot.agentcp.io"
```

> 例：UUID `a1b2c3d4-...` 配置了 `agentId: "funny-bot"`，核心层 `agents.list[]` 中定义了 `{ id: "funny-bot", workspace: "..." }`，domain 默认 `agentcp.io`，则 fullAid 为 `funny-bot.agentcp.io`。

绑定关系在四个层面生效：

| 层面 | 绑定方式 | 作用 |
|------|---------|------|
| **Agent 定义层** | `agents.list[]` 中的 Agent 条目 | 定义 workspace、identity、model 等 Agent 属性 |
| **配置层** | `channels.acp.identities[uuid].agentId` | ACP 身份引用 Agent，建立 UUID → agentId 映射 |
| **路由层** | `AcpIdentityRouter.aidToIdentityId` Map | 运行时 AID → UUID → agentId 双向查找 |
| **人格层** | 核心 `resolveAgentWorkspaceDir(cfg, agentId)` | agentId → workspace 目录 → 独立人格文件 |

绑定一旦建立，以下内容自动隔离：
- 该 AID 收到的消息 → 通过 agentId 找到对应 Agent 的 workspace → 使用该人格回复
- 该 AID 的 agent.md → 基于该 Agent workspace 中的 IDENTITY.md/SOUL.md 生成
- 该 AID 的联系人 → 存储在 `~/.acp-storage/contacts-{identityId}.json`
- 该 AID 的会话 → session key 包含 agentId 和 UUID

---

## 五、配置

### 5.1 openclaw.json 配置示例

```json
{
  "agents": {
    "list": [
      {
        "id": "main",
        "default": true,
        "name": "默认助手"
      },
      {
        "id": "funny-bot",
        "name": "搞笑机器人",
        "workspace": "~/.openclaw/workspace-funny-bot"
      },
      {
        "id": "scholar-bot",
        "name": "学术助手",
        "workspace": "~/.openclaw/workspace-scholar-bot"
      }
    ]
  },
  "channels": {
    "acp": {
      "enabled": true,
      "domain": "agentcp.io",
      "ownerAid": "my-owner.agentcp.io",
      "allowFrom": ["*"],
      "session": {
        "maxTurns": 1000,
        "maxDurationMs": 172800000,
        "idleTimeoutMs": 86400000,
        "maxConcurrentSessions": 400,
        "maxSessionsPerTarget": 10
      },
      "identities": {
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890": {
          "agentId": "funny-bot",
          "seedPassword": "6a42cc7fa4a1dc9f05fbf41e53b62ef2",
          "agentMdPath": "~/.acp-storage/AIDs/funny-bot.agentcp.io/public/agent.md"
        },
        "b2c3d4e5-f6a7-8901-bcde-f12345678901": {
          "agentId": "scholar-bot",
          "seedPassword": "e352ad64d27923fb4cca737d57d61a99",
          "agentMdPath": "~/.acp-storage/AIDs/scholar-bot.agentcp.io/public/agent.md"
        }
      }
    }
  },
  "plugins": {
    "entries": {
      "acp": { "enabled": true }
    }
  }
}
```

> 关键变化：ACP `identities` 中不再包含 `agentName` 和 `workspaceDir`，而是通过 `agentId` 引用 `agents.list[]` 中已定义的 Agent。workspace 由核心代码的 `resolveAgentWorkspaceDir()` 统一解析。

### 5.2 配置字段说明

#### agents.list[] 中每个 Agent 的字段（核心层）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | Agent 唯一标识，用于 ACP identity 的 `agentId` 引用 |
| `default` | boolean | 否 | 是否为默认 Agent |
| `name` | string | 否 | 显示名称 |
| `workspace` | string | 否 | 自定义 workspace 目录（未配置时自动分配 `~/.openclaw/workspace-{id}`） |
| `identity` | object | 否 | Agent 身份信息（name、avatar、emoji） |
| `model` | string/object | 否 | 模型配置 |
| `tools` | object | 否 | 工具配置 |

> 完整字段参见核心代码 `AgentEntrySchema`（`src/config/zod-schema.agent-runtime.ts`）。

#### channels.acp 顶层字段（ACP 全局默认值）

| 字段 | 类型 | 说明 |
|------|------|------|
| `enabled` | boolean | 是否启用 ACP 渠道 |
| `domain` | string | 默认域名，各身份可覆盖 |
| `ownerAid` | string | 默认主人 AID，各身份可覆盖 |
| `allowFrom` | string[] | 默认允许列表，各身份可覆盖 |
| `seedPassword` | string | 默认密码，各身份可覆盖 |
| `session` | object | 会话终止控制（所有身份共享） |

#### channels.acp.identities 中每个身份的字段（ACP 通道层）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `agentId` | string | 是 | 引用 `agents.list[]` 中的 Agent（fullAid = agentId.domain） |
| `agentName` | string | 否 | 遗留字段，仅用于单身份模式。多身份模式下不参与 AID 构建，可忽略 |
| `domain` | string | 否 | 覆盖顶层 domain |
| `seedPassword` | string | 否 | 覆盖顶层 seedPassword |
| `ownerAid` | string | 否 | 覆盖顶层 ownerAid |
| `allowFrom` | string[] | 否 | 覆盖顶层 allowFrom |
| `agentMdPath` | string | 否 | 该身份的 agent.md 路径 |

> 注意：`workspaceDir` 不再出现在 ACP 配置中。workspace 由核心层 `agents.list[].workspace` 定义，ACP 插件通过 `before_agent_start` 钩子接收。
>
> `agentName` 是单身份模式的遗留字段。多身份模式下 AID 由 `agentId + domain` 构建，`agentName` 不参与。如果配置中同时存在 `agentId` 和 `agentName`，以 `agentId` 为准。

#### 继承规则

ACP 通道层字段优先使用自身配置，未配置时回退到顶层默认值：

```
ACP 身份字段值 = identities[id].field ?? 顶层 field ?? 默认值
```

Agent 属性（workspace、identity、model 等）统一从核心层 `agents.list[]` 获取：

```
workspace = resolveAgentWorkspaceDir(cfg, identities[id].agentId)
         → agents.list[].workspace ?? ~/.openclaw/workspace-{agentId}
```

---

## 六、workspaceDir 在核心代码中的传递链路

> ⚠️ 核心代码对 ACP identityId 无感知。核心代码通过 `agentId` 查找 `agents.list[]` 配置来解析 workspace，ACP 插件只需提供 `agentId` 即可复用核心的解析逻辑。

### 6.1 核心代码的 workspaceDir 解析（agents/agent-scope.ts）

```typescript
// agent-scope.ts — 核心代码根据 agentId 解析 workspace
export function resolveAgentWorkspaceDir(cfg: OpenClawConfig, agentId: string) {
  const id = normalizeAgentId(agentId);

  // 1. 查找 agents.list[] 中该 Agent 的 workspace 配置
  const configured = resolveAgentConfig(cfg, id)?.workspace?.trim();
  if (configured) {
    return resolveUserPath(configured);
  }

  // 2. 默认 Agent 使用全局默认 workspace
  const defaultAgentId = resolveDefaultAgentId(cfg);
  if (id === defaultAgentId) {
    const fallback = cfg.agents?.defaults?.workspace?.trim();
    if (fallback) {
      return resolveUserPath(fallback);
    }
    return DEFAULT_AGENT_WORKSPACE_DIR;  // ~/.openclaw/workspace
  }

  // 3. 非默认 Agent 自动分配 ~/.openclaw/workspace-{agentId}
  return path.join(os.homedir(), ".openclaw", `workspace-${id}`);
}
```

> ACP 插件通过 `before_agent_start` 钩子接收核心解析好的 workspaceDir，存入本地 Map，后续通过 `getWorkspaceDir(identityId)` 获取。

### 6.2 ACP 插件获取 workspaceDir 的方式

```typescript
// index.ts — 通过 before_agent_start 钩子接收 workspaceDir
api.on("before_agent_start", async (_event, ctx) => {
  if (ctx.workspaceDir) {
    updateWorkspaceDir(ctx.workspaceDir, accountId);
    await checkAndUploadAgentMd(accountId);
  }
});

// workspace.ts — 本地 Map 存储
const workspaceDirs = new Map<string, string>();

export function getWorkspaceDir(identityId?: string): string | null {
  const normalized = normalizeIdentityId(identityId);
  return workspaceDirs.get(normalized) ?? null;
}

// monitor.ts — 使用时通过 identityId 获取
const wsDir = getWorkspaceDir(identityId);
```

### 6.3 Path A — auto-reply 流程（收到消息自动回复）

```
ACP 入站消息
  → monitor.ts: handleInboundMessageForIdentity(state, ...)
    → agentId = state.account.agentId          // 从 ACP identity 配置获取
    → ctx.AccountId = state.identityId
  → dispatchReplyFromConfig(ctx, ...)
    → getReplyFromConfig(ctx, ...)
      → resolveAgentWorkspaceDir(cfg, agentId)  // 核心函数：agentId → agents.list[] → workspace
        → 返回该 Agent 对应的 workspaceDir
      → runEmbeddedPiAgent({ workspaceDir })
        → runEmbeddedAttempt({ workspaceDir })
          → resolveBootstrapContextForRun({ workspaceDir })
            → loadWorkspaceBootstrapFiles(dir)
              → 从 workspaceDir 加载 SOUL.md、IDENTITY.md 等 ✓
```

### 6.4 Path B — gateway agent 命令（WebSocket 直接调用）

```
WebSocket 请求
  → gateway/server-methods/agent.ts: agentCommand({ ... })
    → resolveAgentWorkspaceDir(cfg, agentId)
    → runEmbeddedPiAgent({ workspaceDir })
      → runEmbeddedAttempt({ workspaceDir })
        → resolveBootstrapContextForRun({ workspaceDir })
          → loadWorkspaceBootstrapFiles(dir)
            → 从 workspaceDir 加载文件 ✓
```

### 6.5 agent.md 生成流程

```
AID 连接成功
  → monitor.ts: checkAndUploadAgentMdForIdentity(state)
    → agentId = state.account.agentId
    → wsDir = resolveAgentWorkspaceDir(cfg, agentId)  // 核心函数解析
    → agent-md-sources.ts: loadAgentMdSources(wsDir, state.identityId)
      → 从该 Agent 的 workspace 读取 IDENTITY.md、SOUL.md 等
    → 生成 agent.md 内容（每个 Agent 内容不同，因为 workspace 不同）
    → multiClient.uploadAgentMd(aid, content)
```

### 6.6 涉及的核心代码文件

| 文件 | 作用 |
|------|------|
| `agents/agent-scope.ts` | `resolveAgentWorkspaceDir(cfg, agentId)` 按 agentId 查找 `agents.list[]` 解析 workspace 目录（核心入口） |
| `agents/workspace.ts` | `loadWorkspaceBootstrapFiles(dir)` 从指定目录加载 bootstrap 文件 |
| `agents/bootstrap-files.ts` | `resolveBootstrapFilesForRun({ workspaceDir })` 解析 bootstrap 文件 |
| `agents/pi-embedded-runner/run/params.ts` | `RunEmbeddedPiAgentParams.workspaceDir` |
| `agents/pi-embedded-runner/run/attempt.ts` | 传递 workspaceDir 到 resolveBootstrapContextForRun |
| `auto-reply/reply/get-reply.ts` | 解析 workspaceDir 并传递给 runner |
| `gateway/server-methods/agent.ts` | 解析 workspaceDir 并传递给 agentCommand |

#### ACP 插件中的关键文件

| 文件 | 作用 |
|------|------|
| `src/channel.ts` | `resolveAccount()` 解析每个身份的 agentId，调用核心 `resolveAgentWorkspaceDir()` 获取 workspace |
| `src/monitor.ts` | 入站消息处理时通过 agentId 获取 wsDir，传递给 agent.md 生成和上下文加载 |
| `src/identity-router.ts` | 身份路由器，每个身份的 account 中包含 agentId |
| `src/agent-md-sources.ts` | 从 Agent 的 workspace 加载 agent.md 来源文件 |

---

## 七、AID 创建流程

每个身份的 AID 创建流程与单身份模式相同，由 `acp-ts` SDK 完成。多身份模式通过 `AcpMultiClient` 为每个 AID 创建独立的 `AgentCP` / `AgentWS` 实例。

### 7.1 acp-ts SDK 创建步骤

1. **检查本地**：`acp.loadAid(fullAid)` → 扫描 `~/.acp-storage/AIDs/{aid}/`
2. **生成密钥对**：EC secp384r1，SHA256withECDSA
3. **创建 CSR**：Subject 包含 AID 作为 CN
4. **CA 签发**：`POST https://acp3.{domain}/api/accesspoint/sign_cert`
5. **加密存储私钥**：`AES(privateKey, SHA256(seedPassword))` → `{aid}/private/{aid}.key`
6. **保存证书**：`{aid}/public/{aid}.crt`

### 7.2 独立实例模式

不再使用 `AgentManager` 单例，直接 `new AgentCP()` / `new AgentWS()` 为每个 AID 创建独立实例，避免全局覆盖问题：

```typescript
// acp-multi-client.ts
async connectAid(opts: AidInstanceOptions): Promise<string> {
  const fullAid = `${opts.agentId}.${opts.domain}`;

  // 1. 每个 AID 独立的 AgentCP 实例
  const acp = new AgentCP(opts.domain, opts.seedPassword || "", ACP_STORAGE_DIR, {
    persistGroupMessages: true,
  });

  // 2. 加载或创建 AID
  let loadedAid = await acp.loadAid(fullAid);
  if (!loadedAid) {
    loadedAid = await acp.createAid(fullAid);
  }

  // 3. 上线获取连接配置
  const config = await acp.online();

  // 4. 每个 AID 独立的 AgentWS 实例
  const agentWs = new AgentWS(fullAid, config.messageServer, config.messageSignature);

  // 5. 启动 WebSocket + 心跳
  await agentWs.startWebSocket();
  // ...
}
```

每个 AID 的 `AgentCP`、`AgentWS`、`HeartbeatClient`、`FileSync` 实例完全独立，互不干扰。

---

## 八、身份路由器（identity-router.ts）

`AcpIdentityRouter` 是多身份模式的核心，维护 AID ↔ Identity 的固定映射。

### 8.1 数据结构

```typescript
class AcpIdentityRouter {
  // AID → identityId 固定映射
  private aidToIdentityId = new Map<string, string>();
  // identityId → 运行时状态
  private states = new Map<string, IdentityAcpState>();
  // 共享的多 AID 客户端
  public multiClient: AcpMultiClient;
}
```

### 8.2 身份注册

```typescript
router.registerIdentity(identityId, account);
// → states.set(identityId, { identityId, account, aidKey: account.fullAid, ... })
// → aidToIdentityId.set(account.fullAid, identityId)
// 例: aidToIdentityId.set("funny-bot.agentcp.io", "a1b2c3d4-...")
```

### 8.3 入站消息路由

```typescript
private routeInbound(receiverAid, sender, sessionId, identifyingCode, content) {
  // 1. 通过 receiverAid 找到 identityId
  const identityId = this.aidToIdentityId.get(receiverAid);

  // 2. 获取该身份的运行时状态
  const state = this.states.get(identityId);

  // 3. 调用入站处理器（monitor.ts 注入）
  //    → ctx.AccountId = identityId
  //    → 通过 state.account.agentId 调用核心 resolveAgentWorkspaceDir 加载对应人格文件
  this.inboundHandler(state, sender, sessionId, identifyingCode, content);
}
```

### 8.4 出站消息路由

```typescript
// outbound.ts
async function sendAcpMessage(params: { to, content, identityId? }) {
  const router = getRouter();

  // 通过 identityId 找到对应身份的 AID
  const state = params.identityId
    ? router.getState(params.identityId)
    : router.getDefaultState();

  const fromAid = state.aidKey;  // 如 "funny-bot.agentcp.io"
  await router.multiClient.sendMessage(fromAid, params.to, content);
}
```

---

## 九、账户解析流程（channel.ts）

### 9.1 枚举账户

```typescript
listAccountIds(cfg):
  → acpConfig.identities 存在且非空
  → 返回 Object.keys(acpConfig.identities)  // ["uuid-1", "uuid-2", ...]
```

### 9.2 解析账户

```typescript
resolveAccount(cfg, "a1b2c3d4-..."):
  → entry = acpConfig.identities["a1b2c3d4-..."]
  → domain = entry.domain ?? acpConfig.domain ?? "agentcp.io"
  → agentId = entry.agentId                                   // "funny-bot"（引用 agents.list[]）
  → 返回 ResolvedAcpAccount {
      accountId: "a1b2c3d4-...",
      identityId: "a1b2c3d4-...",
      agentId: entry.agentId,                                  // "funny-bot"
      domain: domain,                                           // "agentcp.io"
      fullAid: `${entry.agentId}.${domain}`,                   // "funny-bot.agentcp.io"
      ownerAid: entry.ownerAid ?? acpConfig.ownerAid,          // 继承
      seedPassword: entry.seedPassword ?? acpConfig.seedPassword,  // 继承
      allowFrom: entry.allowFrom ?? acpConfig.allowFrom,        // 继承
      agentMdPath: entry.agentMdPath ?? acpConfig.agentMdPath,
      // ⚠️ workspaceDir 不再从 ACP 配置获取
      // 需要时调用 resolveAgentWorkspaceDir(cfg, agentId) 从核心层获取
    }
```

---

## 十、联系人隔离（contacts.ts）

每个身份拥有独立的联系人数据：

```typescript
// contacts.ts
function getStoragePathForIdentity(identityId?: string): string {
  const normalized = normalizeIdentityId(identityId);
  if (normalized === "default") {
    return STORAGE_PATH;  // ~/.acp-storage/contacts.json
  }
  const newPath = path.join(STORAGE_DIR, `contacts-${normalized}.json`);
  // 迁移：旧路径 ~/.acp-storage/identities/{id}/contacts.json -> 新路径
  if (!fs.existsSync(newPath)) {
    const oldPath = path.join(STORAGE_DIR, "identities", normalized, "contacts.json");
    if (fs.existsSync(oldPath)) {
      fs.copyFileSync(oldPath, newPath);
    }
  }
  return newPath;
}
```

---

## 十一、完整生命周期流程图

```
┌─────────────────────────────────────────────────────────────┐
│  1. OpenClaw Gateway 启动                                    │
│     读取 openclaw.json → 发现 ACP 渠道已启用                   │
│     加载插件 ~/.openclaw/extensions/acp/index.ts              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  2. 插件注册                                                  │
│     register(api) → registerChannel(acpChannelPlugin)        │
│     注册工具 + 注册命令                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  3. Gateway 枚举账户                                          │
│     listAccountIds(cfg)                                      │
│     → identities 存在 → ["uuid-1", "uuid-2", ...]           │
│                                                              │
│     对每个 UUID 调用 resolveAccount(cfg, uuid)                │
│     → { fullAid: "{agentId}.agentcp.io", identityId: uuid, agentId: "xxx" }  │
└──────────────────────┬──────────────────────────────────────┘
                       │
              ┌────────┴────────┐
              ▼                 ▼
┌──────────────────┐  ┌──────────────────┐
│  身份 uuid-1     │  │  身份 uuid-2     │
│  agentId: work   │  │  agentId: personal│
│  人格 A          │  │  人格 B          │
└────────┬─────────┘  └────────┬─────────┘
         │                     │
         ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│  4. 对每个身份调用 gateway.startAccount(ctx)                   │
│     → startIdentityWithGateway(ctx, acpConfig)               │
│     → router = getOrCreateRouter()                           │
│     → router.setInboundHandler(handleInboundMessageForIdentity)│
│     → router.registerIdentity(identityId, account)           │
│     → router.startIdentity(identityId, ...)                  │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌─────────────────────────────────────────────────────────────┐
│  5. multiClient.connectAid(opts) ← 每个 AID 独立实例        │
│                                                              │
│  [AID-1]                                                     │
│  5a. new AgentCP(domain, seedPassword, ~/.acp-storage)   │
│  5b. acp.loadAid(fullAid)                                    │
│  5c. 若不存在 → acp.createAid(fullAid)                       │
│       → 生成密钥对 → CSR → CA签发 → 加密存储                   │
│  5d. acp.online() → 认证 → 获取连接配置                       │
│  5e. agentWs = new AgentWS(aid, messageServer, signature)      │
│  5f. aws.startWebSocket() + HeartbeatClient.online()         │
│                                                              │
│  [AID-2]  ← 独立实例，可并行                             │
│  5a-5f 同上，各自独立的 AgentCP/AgentWS 实例                           │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  6. 各身份独立生成并上传 agent.md                               │
│     checkAndUploadAgentMdForIdentity(state)                  │
│     → agentId = state.account.agentId                        │
│     → wsDir = resolveAgentWorkspaceDir(cfg, agentId)         │
│     → loadAgentMdSources(wsDir, state.identityId)            │
│       → 从该 Agent 的 workspace 读取 IDENTITY.md、SOUL.md 等│
│     → 生成 agent.md（每个 Agent 内容不同，因为 workspace 不同）│
│     → multiClient.uploadAgentMd(aid, content)                │
│                                                              │
│  验证：各 AID 的 agent.md hash 应各不相同                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  7. 消息路由 + 人格隔离                                        │
│                                                              │
│  入站: aws.onMessage → handleIncomingMessage                 │
│    → routeInbound(receiverAid, ...)                          │
│    → aidToIdentityId.get(receiverAid) → identityId           │
│    → handleInboundMessageForIdentity(state[identityId], ...) │
│    → ctx.AccountId = identityId                              │
│    → agentId = state.account.agentId                         │
│    → wsDir = resolveAgentWorkspaceDir(cfg, agentId)          │
│    → 核心代码: resolveBootstrapContextForRun({ workspaceDir })│
│      → 从该 Agent 的 workspace 加载 SOUL.md（该 Agent 人格） │
│      → 从该 Agent 的 workspace 加载 IDENTITY.md（该 Agent 信息）│
│    → AI 以该身份的人格回复                                     │
│    → multiClient.sendReply(receiverAid, ...)                 │
│                                                              │
│  出站: sendAcpMessage({ to, identityId })                    │
│    → router.getState(identityId) → aidKey                    │
│    → multiClient.sendMessage(aidKey, ...)                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 十二、身份感知的 Session Key

多身份模式下，session key 包含 identityId 以实现会话隔离：

```typescript
// monitor.ts → handleInboundMessageForIdentity

const agentId = state.account.agentId;
const sessionKey = identityId === "default"
  ? `agent:${agentId}:acp:session:${sender}:${sessionIdShort}`
  : `agent:${agentId}:acp:id:${identityId}:session:${sender}:${sessionIdShort}`;
```

这确保不同身份与同一个 sender 的对话互不干扰，且 session key 中包含 agentId 使核心代码能正确解析 workspace。

---

## 十三、IdentityAcpState（身份运行时状态）

每个身份拥有独立的运行时状态：

```typescript
{
  identityId: string;                    // UUID
  account: ResolvedAcpAccount;           // 解析后的账户配置
  aidKey: string;                        // fullAid，如 "funny-bot.agentcp.io"
  sessionStates: Map<string, AcpSessionState>;  // 该身份的所有会话
  isRunning: boolean;
  lastConnectedAt: number | null;
  lastInboundAt: number | null;
  lastOutboundAt: number | null;
  reconnectAttempts: number;
  lastError: string | null;
  idleCheckInterval: ReturnType<typeof setInterval> | null;
}
```

---

## 十四、acp-ts SDK API 参考

### AgentCP / AgentWS（独立实例）

```typescript
const acp = new AgentCP(domain, seedPassword, basePath);  // 每个 AID 独立实例
const agentWs = new AgentWS(aid, messageServer, signature);   // 每个 AID 独立实例
```

每个 AID 使用独立的 `AgentCP` / `AgentWS` 实例，互不干扰。

### AgentCP（身份管理）

```typescript
acp.createAid(aid): Promise<string>
acp.loadAid(aid): Promise<string | null>
acp.loadAidList(): Promise<string[] | null>
acp.online(): Promise<IConnectionConfig>
acp.getCertInfo(aid): Promise<{ privateKey, publicKey, csr, cert } | null>
acp.setAgentMdPath(filePath): void
acp.resetAgentMdUploadStatus(): Promise<void>
```

### AgentWS（WebSocket 通信）

```typescript
aws.startWebSocket(): Promise<void>
aws.connectTo(receiver, onSessionCreated, onInviteStatus): void
aws.send(msg, to, sessionId, identifyingCode): void
aws.onMessage(cb): void
aws.onStatusChange(cb): void
aws.disconnect(): void
aws.acceptInviteFromHeartbeat(sessionId, inviterId, inviteCode): void
```

### HeartbeatClient（UDP 心跳）

```typescript
const hb = new HeartbeatClient(agentId, serverUrl, seedPassword);
hb.online(): Promise<boolean>
hb.offline(): void
hb.onInvite(cb): void
```

### FileSync（文件同步）

```typescript
const fs = new FileSync({ apiUrl, aid, signature, localDir });
fs.uploadAgentMd(content): Promise<{ success, url?, error? }>
fs.uploadAgentMdFromFile(filePath): Promise<{ success, url?, error? }>
```

---

## 十五、安全机制

| 机制 | 说明 |
|------|------|
| EC secp384r1 密钥对 | 每个 AID 独立的密钥对，私钥本地生成不上传 |
| SHA256withECDSA 签名 | 认证时签名 nonce，防伪造 |
| 私钥 AES 加密存储 | 每个 AID 使用各自的 seedPassword 加密 |
| CA 证书签发 | CSR 提交到 ACP 服务器签发，建立信任链 |
| 权限隔离 | 每个身份可配置不同的 ownerAid 和 allowFrom |
| 人格隔离 | 每个 Agent 在 `agents.list[]` 中定义独立 workspace，各自包含 SOUL.md/IDENTITY.md，AI 回复风格完全不同 |
| 通信隔离 | 会话、联系人、agent.md、session key 完全隔离 |
| 信用评分 | 按身份独立计算，低于 20 分拒绝交互 |
| 独立实例 | 每个 AID 独立的 AgentCP/AgentWS 实例，互不干扰 |
| 提示词注入防护 | 外部 Agent 无法跨身份操作 |

---

## 十六、信用评分体系

每个身份独立维护联系人信用评分。

### 评分公式

```
base = 50
+ min(interactionCount, 20)                              // 交互频次，上限 +20
+ min(floor(totalDurationMs / 60000), 15)                 // 交互时长，上限 +15
+ clamp((successfulSessions - failedSessions) * 3, -15, 15)  // 会话成功率
= clamp(result, 0, 100)
```

### 信用等级

| 分数范围 | 等级 | 行为 |
|---------|------|------|
| ≥ 70 | trusted | 正常交互 |
| 40-69 | neutral | 正常交互 |
| 20-39 | untrusted | 正常交互（警告） |
| < 20 | — | 拒绝交互 |

### 会话评分融合

`新分 = 累积分 × 0.7 + 本次评分 × 0.3`

---

## 十七、关键数据结构

### ResolvedAcpAccount

```typescript
{
  accountId: string;        // = identityId（UUID）
  identityId: string;
  agentId: string;          // 引用 agents.list[] 中的 Agent，如 "funny-bot"
  domain: string;           // 如 "agentcp.io"
  fullAid: string;          // 如 "funny-bot.agentcp.io"（agentId + domain）
  enabled: boolean;
  ownerAid: string;         // 该身份的主人
  allowFrom: string[];      // 该身份的允许列表
  seedPassword: string;     // 该身份的密钥密码
  agentMdPath?: string;
  // ⚠️ workspaceDir 不再存储在此处
  // 需要时调用 resolveAgentWorkspaceDir(cfg, agentId) 从核心层获取
}
```

### AcpIdentityEntry（配置中的身份条目）

```typescript
{
  agentId: string;          // 必填，引用 agents.list[] 中的 Agent（fullAid = agentId.domain）
  domain?: string;          // 可选，覆盖顶层
  seedPassword?: string;    // 可选，覆盖顶层
  ownerAid?: string;        // 可选，覆盖顶层
  allowFrom?: string[];     // 可选，覆盖顶层
  agentMdPath?: string;
  // ⚠️ 不再包含 workspaceDir，workspace 由核心层 agents.list[].workspace 定义
}
```

### Contact（联系人，按身份隔离）

```typescript
{
  aid: string;
  name?: string;
  emoji?: string;
  groups: string[];
  interactionCount: number;
  lastInteractionAt?: number;
  totalDurationMs: number;
  notes?: string;
  selfIntro?: string;
  addedAt: number;
  updatedAt: number;
  creditScore: number;         // 0-100
  creditManualOverride?: number;
  creditManualReason?: string;
  successfulSessions: number;
  failedSessions: number;
}
```
