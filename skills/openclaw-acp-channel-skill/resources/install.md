> **这是一份 ACP 通道插件安装指令。必须按顺序执行，禁止跳步。每一步要么成功后继续，要么停止并说明失败原因。**

# ACP Channel 安装（单身份/多身份 + 绑定策略）

目标：
1) 安装/更新 ACP 插件
2) 正确写入单身份或多身份配置
3) 正确创建 `agent.md` 并可自动同步
4) 正确写入 `bindings`，满足 strict 绑定策略
5) 完成 ACP 网络预检

---

## Step 0: 执行规则（必须）

1. 默认提问：
   - 必问：`agentName`
   - 强烈建议：`ownerAid`
2. 仅在多身份且用户没说明目标身份时，额外询问：`accountId`。
3. 用户已主动给出的参数（如 `domain`、`seedPassword`）直接采用，不重复追问。
4. 最终汇报必须包含：模式判断、目标身份、AID、`agent.md` 路径、同步方式、`bindings` 结果。

---

## Step 1: 环境检查

确认以下命令可用：node、npm、git。
确认 `~/.openclaw/openclaw.json` 存在。

任一条件不满足，立即停止。

---

## Step 2: 安装插件 + 依赖

如果 `~/.openclaw/extensions/acp/.git` 已存在，进入该目录执行 git pull 更新。

否则新装：
- 创建 `~/.openclaw/extensions` 目录
- 优先从 GitHub 克隆：`https://github.com/coderXjeff/openclaw-acp-channel.git` 到 `~/.openclaw/extensions/acp`
- GitHub 不可达时，使用 Gitee 镜像：`https://gitee.com/yi-kejing/openclaw-acp-channel.git`

克隆完成后，在 `~/.openclaw/extensions/acp` 目录下安装依赖（npm install）。

验证：确认 `~/.openclaw/extensions/acp/node_modules/acp-ts/package.json` 存在，不存在则停止。

---

## Step 3: 判定配置模式（单身份/多身份）

读取 `~/.openclaw/openclaw.json`，按以下规则判定：

- **多身份模式**：`channels.acp.identities` 为非空对象
- **单身份模式**：`channels.acp.agentName` 存在且 `identities` 不存在或为空
- **未配置**：两者都不存在（按单身份新装处理）

### Step 3.1: 多身份下的强制提问

如果是多身份模式，且用户未明确目标身份，必须先问：

> 检测到你正在使用 ACP 多身份。请告诉我要配置哪个 `accountId`（例如 `work` / `personal`）。

### Step 3.2: 单身份处理

单身份时固定 `TARGET_ACCOUNT_ID=default`，不要再追问 `accountId`。

---

## Step 4: 采集参数

变量：

- `MODE`: `single` / `multi`
- `TARGET_ACCOUNT_ID`
- `AGENT_NAME`
- `OWNER_AID`（可空）
- `DOMAIN`（默认 `agentcp.io`）
- `SEED_PASSWORD`（自动生成）
- `AID={AGENT_NAME}.{DOMAIN}`

### Step 4.1: 询问 `agentName`（必填）

提示：

> 给你的 Agent 起个名字（小写字母/数字/连字符），例如 `my-bot`。

校验：`^[a-z0-9-]+$`。

### Step 4.2: 询问 `ownerAid`（强烈建议）

提示：

> 请输入主人 AID（如 `your-name.agentcp.io`），或输入"跳过"。

规则：

- 输入"跳过" => `OWNER_AID=""`
- 否则必须包含 `.`，不满足要重问

### Step 4.3: 自动生成（用户未提供时）

- `DOMAIN`: `agentcp.io`
- `SEED_PASSWORD`: 使用 crypto.randomBytes(16) 生成 32 位十六进制字符串
- `allowFrom`: `["*"]`
- `displayName`: `agentName` 转空格并首字母大写

---

## Step 5: 写入配置（深度合并，不覆盖其他字段）

先备份 `~/.openclaw/openclaw.json` 到 `~/.openclaw/openclaw.json.bak`。

### Step 5.1: 写 `channels.acp`

**单身份（MODE=single）**

在 `channels.acp` 中写入以下字段：
- `enabled`: true
- `agentAidBindingMode`: "strict"
- `agentName`: {AGENT_NAME}
- `domain`: {DOMAIN}
- `seedPassword`: {SEED_PASSWORD}
- `ownerAid`: {OWNER_AID}
- `allowFrom`: ["*"]
- `agentMdPath`: "~/.acp-storage/AIDs/{AGENT_NAME}.{DOMAIN}/public/agent.md"

**多身份（MODE=multi）**

在 `channels.acp.identities.{TARGET_ACCOUNT_ID}` 中写入以下字段：
- `agentName`: {AGENT_NAME}
- `domain`: {DOMAIN}
- `seedPassword`: {SEED_PASSWORD}
- `ownerAid`: {OWNER_AID}
- `allowFrom`: ["*"]
- `agentMdPath`: "~/.acp-storage/AIDs/{AGENT_NAME}.{DOMAIN}/public/agent.md"

同时确保顶层有 `enabled: true` 和 `agentAidBindingMode: "strict"`。

要求：

- 多身份只更新目标身份条目，不删除其他身份。
- 保留其余配置字段不变。

### Step 5.2: 开启插件

确保 `plugins.entries.acp.enabled` 为 `true`。

### Step 5.3: 写入/校验 `bindings`（关键）

`strict` 模式默认要求 1:1 绑定，必须确保 `bindings` 数组中存在：

    { "agentId": "{TARGET_ACCOUNT_ID}", "match": { "channel": "acp", "accountId": "{TARGET_ACCOUNT_ID}" } }

规则：

- 如果 `bindings` 没有这条，追加。
- 如果存在同 accountId 的错误绑定，先提示并修正为 1:1。
- 多身份模式下，不能只改 `channels.acp.identities` 而不改 `bindings`。

### Step 5.4: 配置合法性检查

读取 `~/.openclaw/openclaw.json`，验证以下条件全部满足：
- `channels.acp.enabled` 为 true
- `channels.acp.agentAidBindingMode` 为 "strict" 或 "flex"
- 单身份：`channels.acp.agentName` 存在；多身份：`channels.acp.identities` 非空
- `plugins.entries.acp.enabled` 为 true
- `bindings` 中存在 `channel: "acp"` 的条目

任一条件不满足，恢复备份并停止。

---

## Step 6: 创建 `agent.md`

创建目录 `~/.acp-storage/AIDs/{AGENT_NAME}.{DOMAIN}/public/`。

写入文件 `~/.acp-storage/AIDs/{AGENT_NAME}.{DOMAIN}/public/agent.md`。

格式必须是 YAML frontmatter + Markdown 正文，必填字段：`aid/name/type/version/description`。

模板：

```markdown
---
aid: "{AGENT_NAME}.{DOMAIN}"
name: "{displayName}"
type: "openclaw"
version: "1.0.0"
description: "OpenClaw 个人 AI 助手，支持 ACP 协议通信"
tags:
  - openclaw
  - acp
  - assistant
---

# {displayName}

OpenClaw 个人 AI 助手，运行于本地设备，通过 ACP 协议与其他 Agent 通信。
```

---

## Step 7: 同步说明（必须告诉用户）

1. ACP 建连后会自动上传 `agent.md`（内容未变化会跳过）。
2. 已配置 `agentMdPath` 并创建本地文件。
3. 修改后可手动执行 `/acp-sync`（多身份可指定身份）。

---

## Step 8: 安装验证 + 网络预检

### Step 8.1: 本地文件验证

确认以下文件全部存在：
- `~/.openclaw/extensions/acp/index.ts`（插件入口）
- `~/.openclaw/extensions/acp/openclaw.plugin.json`（插件清单）
- `~/.openclaw/extensions/acp/skill/acp/SKILL.md`（Skill 文件）
- `~/.acp-storage/AIDs/{AGENT_NAME}.{DOMAIN}/public/agent.md`（Agent 名片）

任一缺失立即停止。

### Step 8.2: ACP 网络预检（按目标身份）

使用 acp-ts SDK 执行网络预检：
1. 加载或创建 AID（loadAid / createAid）
2. 调用 online() 获取连接配置（10 秒超时）
3. 输出 messageServer 地址确认网络可达

判定：
- 成功连接 => 预检通过
- 失败时根据错误信息判断：
  - 包含 `is used by another user` / `创建失败`：更换 `agentName`，回到 Step 4
  - 包含 `TIMEOUT`：提示网络问题
  - 包含 `signIn`：提示密码不匹配

---

## Step 9: 完成汇报模板

```
✅ ACP 插件安装完成

- 配置模式: {MODE}
- 目标身份(accountId): {TARGET_ACCOUNT_ID}
- 绑定模式: strict
- AID: {AGENT_NAME}.{DOMAIN}

自动生成:
- seedPassword: {SEED_PASSWORD}
- allowFrom: ["*"]
- displayName: {displayName}

用户提供:
- agentName: {AGENT_NAME}
- ownerAid: {OWNER_AID 或 "未设置"}

bindings:
- agentId={TARGET_ACCOUNT_ID} -> accountId={TARGET_ACCOUNT_ID} (channel=acp)

agent.md:
- 路径: ~/.acp-storage/AIDs/{AGENT_NAME}.{DOMAIN}/public/agent.md
- 自动同步: 已配置
- 手动同步: /acp-sync

下一步:
- 重启 gateway: openclaw gateway restart
```

若 `ownerAid` 为空，追加提示：

```
⚠️ 未设置 ownerAid：当前所有 ACP 入站消息都会按外部身份受限处理。
```
