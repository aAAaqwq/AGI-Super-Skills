# 🧠 蜂群学习 Round 9/10 — 私有去中心化军团：安全、权限、审计、治理

**日期**: 2026-04-02 18:31 (Thu)
**角色**: 小a CEO
**主题**: OpenClaw 私有去中心化 Agent 军团的可靠性、权限模型、日志审计与安全治理

---

## 一、当前安全态势审计

### 1.1 攻击面全景

```
                    ┌─────────────────────────┐
                    │   外部攻击面             │
                    │                         │
    Telegram Bot ──→│  Channel Webhooks       │
    Discord Bot ──→ │  Channel Webhooks       │
    Signal Bot  ──→ │  Channel Webhooks       │
    WebChat     ──→ │  WebSocket              │
                    └──────────┬──────────────┘
                               │
                    ┌──────────▼──────────────┐
                    │   Gateway (单点)         │
                    │  - 消息路由              │
                    │  - Session 管理          │
                    │  - Tool 调度             │
                    │  - Model Provider 调用   │
                    │  - Cron 调度器           │
                    └──────────┬──────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
    ┌─────────▼──┐   ┌────────▼──┐   ┌────────▼──┐
    │ Agent:main │   │Agent:code │   │ Agent:ops │  ... ×13
    │ (CEO)      │   │           │   │           │
    │ allowAgents│   │ 无spawn权 │   │ 无spawn权 │
    │ = ["*"]    │   │           │   │           │
    └──────┬─────┘   └───────────┘   └───────────┘
           │ spawn
    ┌──────▼─────┐
    │ Sub-agents │
    │ (隔离session)│
    │ 32并发上限  │
    └────────────┘
```

### 1.2 现有安全配置审计

| 维度 | 当前状态 | 风险等级 | 说明 |
|------|---------|---------|------|
| **Spawn 权限** | 只有 main 可 spawn（`allowAgents: ["*"]`） | 🟢 低 | CEO 集中调度，其余 agent 无 spawn 权限 |
| **并发上限** | `maxConcurrent: 32` | 🟡 中 | 32 并发足以打满 token 限流，但无速率熔断 |
| **Spawn 深度** | 默认 `maxSpawnDepth: 1` | 🟢 低 | 子 agent 不能再 spawn，防止递归失控 |
| **Tool 权限** | 全局无 deny list，exec 无限制 | 🔴 高 | 任何 agent 可执行任意 shell 命令 |
| **日志审计** | `logging: {}` 空 | 🔴 高 | 无结构化审计日志，无法回溯谁做了什么 |
| **Session 可见性** | `visibility: "all"` | 🟡 中 | 所有 session 互相可见，无隔离 |
| **Auth Profiles** | 8 个 provider，API key 模式 | 🟡 中 | 密钥通过 pass 管理，但运行时 `.env` 明文 |
| **Elevated 执行** | 未配置 | 🟡 中 | 无权限分级，无审批流 |
| **Quant 特殊权限** | `allowAgents: ["finance","research","news"]` | 🟢 低 | 量化 agent 只能调用 3 个下游 agent |

### 1.3 历史安全事故教训

| 日期 | 事故 | 根因 | 安全维度 |
|------|------|------|---------|
| 02-05 | 公开仓库硬编码 API key | 无 pre-push 扫描 | 代码安全 |
| 02-21 | 飞书 Secret + OpenRouter 泄露 | 代码硬编码 | 密钥管理 |
| 03-04 | AGI-Super-Skills 推送 12 个真实密钥 | 批量 push 无扫描 | 代码安全 |
| 03-14 | Google API Key 暴露 (GitHub Alert) | 第三方 skill 自带作者 key | 供应链安全 |

**结论：安全事故全部集中在「密钥泄露」，尚未发生「权限越权」或「Agent 恶意行为」。但随着 agent 数量和复杂度增长，权限越权只是时间问题。**

---

## 二、最小安全基线（Security Baseline）

### 2.1 分层安全模型

```
┌─────────────────────────────────────────────────┐
│ Layer 5: 治理层 (Governance)                     │
│   - 审计日志不可篡改                              │
│   - 定期安全回顾                                  │
│   - 权限变更审批流                                │
├─────────────────────────────────────────────────┤
│ Layer 4: 数据层 (Data Protection)                │
│   - 密钥管理: pass → .env → 环境变量             │
│   - 个人信息: 脱敏存储，不进入 memory             │
│   - 金融数据: 只读查询，写入需确认                │
├─────────────────────────────────────────────────┤
│ Layer 3: Agent 行为层 (Behavior Control)         │
│   - Tool allow/deny per agent                    │
│   - 执行权限分级（普通/提升/禁止）                │
│   - 行为边界（SOUL.md 宪法约束）                  │
├─────────────────────────────────────────────────┤
│ Layer 2: 调度层 (Orchestration)                  │
│   - Spawn 权限矩阵                               │
│   - 并发控制 + 速率限制                           │
│   - 超时保护 + 资源配额                           │
├─────────────────────────────────────────────────┤
│ Layer 1: 基础设施层 (Infrastructure)             │
│   - Gateway 认证 (Token)                         │
│   - Tailscale 内网隔离                           │
│   - systemd 服务管理                              │
└─────────────────────────────────────────────────┘
```

### 2.2 权限矩阵（推荐配置）

| Agent | Spawn 权限 | Shell 执行 | 金融操作 | 对外通信 | 密钥访问 |
|-------|-----------|-----------|---------|---------|---------|
| **main (CEO)** | ✅ 全部 | ✅ 任意 | ⚠️ 需确认 | ⚠️ 需确认 | ✅ pass show |
| **ops** | ❌ | ✅ 运维命令 | ❌ | ✅ 监控告警 | ✅ pass show |
| **code** | ❌ | ✅ 开发环境 | ❌ | ❌ | ❌ |
| **quant** | ✅ finance/research/news | ❌ | ⚠️ 只读+信号 | ❌ | ❌ |
| **research** | ❌ | ✅ 只读/搜索 | ❌ | ❌ | ❌ |
| **content** | ❌ | ❌ | ❌ | ⚠️ 需确认发布 | ❌ |
| **data** | ❌ | ✅ 数据脚本 | ❌ | ❌ | ❌ |
| **finance** | ❌ | ❌ | ✅ 只读分析 | ❌ | ❌ |
| **market** | ❌ | ❌ | ❌ | ⚠️ 需确认 | ❌ |
| **pm** | ❌ | ❌ | ❌ | ❌ | ❌ |
| **law** | ❌ | ❌ | ❌ | ❌ | ❌ |
| **product** | ❌ | ❌ | ❌ | ❌ | ❌ |
| **sales** | ❌ | ❌ | ❌ | ❌ | ❌ |

### 2.3 OpenClaw 配置实现

```jsonc
// openclaw.json — 安全加固配置（推荐）
{
  "tools": {
    // 全局 exec 安全模式
    "exec": {
      "security": "allowlist",  // allowlist | full | deny
      "allowlist": [
        "git *", "python3 *", "node *", "npm *",
        "ls *", "cat *", "head *", "tail *", "grep *",
        "wc *", "find *", "curl *", "pass show *",
        "tailscale *", "systemctl status *",
        "docker ps", "docker logs *"
      ]
    },
    // 子 agent 工具限制
    "subagents": {
      "deny": ["gateway"]  // 子 agent 不能修改 gateway 配置
    },
    // Agent 间通信
    "agentToAgent": {
      "enabled": true,
      "audit": true  // 记录所有跨 agent 调用
    },
    // 提升权限
    "elevated": {
      "requireApproval": true  // 需要人工审批
    }
  },
  
  "agents": {
    "defaults": {
      "subagents": {
        "maxConcurrent": 32,
        "maxSpawnDepth": 1,
        "maxChildrenPerAgent": 5,
        "runTimeoutSeconds": 600
      }
    }
  },
  
  // 审计日志（推荐开启）
  "logging": {
    "level": "info",
    "audit": {
      "enabled": true,
      "events": ["tool_call", "spawn", "config_change", "elevated_exec", "message_send"],
      "retention": "30d"
    }
  }
}
```

---

## 三、日志与审计体系

### 3.1 审计事件分类

| 事件级别 | 事件类型 | 示例 | 存储 |
|---------|---------|------|------|
| **P0 Critical** | 金融操作 | quant 下单、资金转移 | 永久 |
| **P1 High** | 权限变更 | config.apply、allowAgents 修改 | 90d |
| **P1 High** | 对外通信 | 邮件发送、社交媒体发布 | 90d |
| **P2 Medium** | Shell 执行 | exec 调用及返回值 | 30d |
| **P2 Medium** | Agent spawn | sessions_spawn 调用 | 30d |
| **P3 Low** | 日常工具 | read/write/search | 7d |

### 3.2 审计日志格式

```json
{
  "timestamp": "2026-04-02T18:31:00+08:00",
  "event": "tool_call",
  "level": "P2",
  "agent": "code",
  "session": "agent:code:subagent:abc-123",
  "tool": "exec",
  "input_hash": "sha256:a1b2c3...",
  "input_preview": "git push origin main",
  "output_status": "success",
  "duration_ms": 2340,
  "tokens_used": 1250,
  "model": "zai/glm-5.1"
}
```

### 3.3 现有替代方案（Audit 未原生支持时）

```bash
# 方案A: Cron 审计脚本
# 每小时扫描 session 历史，记录关键操作
python3 ~/clawd/scripts/audit-log.py

# 方案B: Git 作为审计日志
# 所有文件变更通过 git commit，天然有审计链
# git log --author="openclaw" --since="1h ago"

# 方案C: Memory 作为轻量审计
# 关键操作写入 memory/YYYY-MM-DD.md
# AGENTS.md 已要求 compact 前写 QMD 记录
```

---

## 四、治理机制（Governance）

### 4.1 决策权分层

```
Daniel (董事长)
  │
  ├─ 战略决策：项目立项/砍掉、对外发布、金融操作
  ├─ 安全策略：权限变更、密钥轮换、新 agent 上线
  ├─ 最终审批：config.apply、对外通信
  │
  ▼
小a (CEO)
  │
  ├─ 执行决策：任务调度、质量把控、日常运营
  ├─ 紧急处理：P0 事故响应（先处理后汇报）
  ├─ 非紧急建议：安全加固建议、优化方案
  │
  ▼
C-Suite Agents
  │
  ├─ 职责内自主执行（按 SOUL.md/AGENTS.md 约束）
  ├─ 跨职责 → 必须通过 CEO
  ├─ 越权操作 → 自动拒绝 + 上报
```

### 4.2 变更审批流程（Change Management）

| 变更类型 | 审批人 | 流程 | 紧急通道 |
|---------|-------|------|---------|
| Gateway 配置变更 | Daniel | config.apply → 自动 restart | CEO 先 apply，事后汇报 |
| 新 Agent 上线 | Daniel | 创建 agent.json → 测试 → 审批 → 上线 | — |
| 权限扩展 | Daniel | 评估风险 → Daniel 确认 → 配置变更 | — |
| Skill 安装 | CEO | 安全扫描 → 测试 → 安装 | 高风险需 Daniel |
| Cron 创建 | CEO | 按职责分配 → 测试 → 上线 | — |
| 金融操作 | Daniel | 信号生成 → Daniel 确认 → 执行 | CEO 可紧急止损 |
| 对外发布 | Daniel | 内容生成 → 审核 → 发布 | — |

### 4.3 安全响应 SOP

```
P0 安全事故响应流程:

发现事故 (5min内)
    │
    ├─ 1. 立即止血
    │     - 泄露密钥 → pass insert 轮换
    │     - 恶意操作 → kill agent session
    │     - 异常进程 → systemctl stop openclaw
    │
    ├─ 2. 评估影响 (10min内)
    │     - 哪些数据泄露？
    │     - 哪些操作被恶意执行？
    │     - 影响范围多大？
    │
    ├─ 3. 通知 Daniel (15min内)
    │     - 事故简报（发生了什么+影响+已处理）
    │     - 需要决策的事项
    │
    ├─ 4. 根因分析 (1h内)
    │     - 5-Why 分析
    │     - 防止复发的措施
    │
    └─ 5. 记录+复盘
          - 写入 memory/YYYY-MM-DD.md
          - 更新安全策略
          - 下次 compact 时同步到 MEMORY.md
```

---

## 五、多租户安全（未来：Mac Studio 部署）

### 5.1 租户隔离模型

```
┌──────────────────────────────────────────────┐
│            Mac Studio (64GB)                  │
│                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Tenant A │  │ Tenant B │  │ Tenant C │  │
│  │ 用户: Alice│  │ 用户: Bob │  │ 用户: Carol│  │
│  │          │  │          │  │          │  │
│  │ OpenClaw │  │ OpenClaw │  │ OpenClaw │  │
│  │ :18789   │  │ :18790   │  │ :18791   │  │
│  │          │  │          │  │          │  │
│  │ ~/tenant-a│  │ ~/tenant-b│  │ ~/tenant-c│  │
│  │ pass命名空间│  │ pass命名空间│  │ pass命名空间│  │
│  └──────────┘  └──────────┘  └──────────┘  │
│                                              │
│  共享: Tailscale 网络 + Ollama GPU           │
│  隔离: 文件系统 + 进程 + 密钥 + Session      │
└──────────────────────────────────────────────┘
```

### 5.2 多租户安全要求

| 隔离维度 | 方案 | 优先级 |
|---------|------|-------|
| **文件系统** | macOS 用户账户或 Linux namespace | P0 |
| **进程隔离** | 每租户独立 systemd service | P0 |
| **密钥隔离** | `pass` 前缀命名空间 (`tenant-a/api/xxx`) | P0 |
| **网络隔离** | Tailscale ACL + 端口隔离 | P1 |
| **资源配额** | `ulimit` + `cgroup` CPU/内存限制 | P1 |
| **GPU 共享** | Ollama 多模型 + 请求队列 | P2 |
| **审计独立** | 每租户独立日志目录 | P0 |

---

## 六、安全加固实施路线图

### Phase 1: 立即可做（本周）

| # | 措施 | 工作量 | 影响 |
|---|------|-------|------|
| 1 | **exec allowlist 配置** | 1h | 防止任意 shell 执行 |
| 2 | **per-agent tool deny** | 2h | 限制 content/law/pm 的 exec 权限 |
| 3 | **audit-log.py 脚本** | 3h | 轻量审计，cron 定期运行 |
| 4 | **pre-push-security-scan 强化** | 1h | 覆盖 `.md` 文件中的密钥泄露 |

### Phase 2: 短期优化（2周内）

| # | 措施 | 工作量 | 影响 |
|---|------|-------|------|
| 5 | **Quant agent 金融操作审批流** | 1天 | 金融操作需确认 |
| 6 | **Session 可见性分 agent 控制** | 2天 | 敏感 session 隔离 |
| 7 | **自动密钥轮换 cron** | 1天 | 定期提醒轮换高风险密钥 |
| 8 | **Security Dashboard** | 2天 | 可视化审计日志 |

### Phase 3: 长期架构（Mac Studio 部署时）

| # | 措施 | 工作量 | 影响 |
|---|------|-------|------|
| 9 | **多租户隔离部署** | 3天 | 租户完全隔离 |
| 10 | **零信任 Agent 网络** | 5天 | Agent 间通信需双向认证 |
| 11 | **SBOM + 供应链安全** | 2天 | 所有 skill 的安全扫描 |
| 12 | **灾难恢复方案** | 2天 | 全量备份+快速恢复 |

---

## 七、Round 9 → Round 10 收敛

### 已覆盖的 9 轮主题

| Round | 主题 | 核心收获 |
|-------|------|---------|
| R1-R4 | (前序轮次) | OpenClaw 基础架构、Skill 体系、Agent 协作 |
| R5 | 开发军团 | CEO→PM→Code 协作 SOP、职责矩阵 |
| R6-R7 | (前序轮次) | 内容工厂、数据采集 |
| R8 | 物理信息交互 | Nodes 架构、设备控制、跨机协作 |
| **R9** | **安全治理** | **权限矩阵、审计体系、治理机制、多租户安全** |

### Round 10 预告：终极整合

R10 将收敛所有轮次的核心洞察，产出：
1. **OpenClaw 军团作战手册 v1.0** — 整合 10 轮学习的完整操作指南
2. **安全基线检查清单** — 可执行的逐项检查
3. **Daniel 的 30 分钟军团指挥速查** — 快速上手指南

---

## 八、关键决策建议

### 🔴 必须立即做

1. **exec allowlist** — 当前任何 agent 可执行任意命令，风险极高
2. **per-agent tool deny** — content/law/pm/sales 不需要 shell 权限
3. **金融操作确认流** — quant 的交易信号必须经 Daniel 确认

### 🟡 本周应做

4. **审计日志** — 即使是简单的 git-based audit，也比当前零审计强
5. **密钥轮换提醒** — Polymarket 钱包私钥已泄露 40 天未轮换

### 🟢 长期规划

6. **多租户安全架构** — Mac Studio 部署前必须完成隔离方案
7. **零信任 Agent 网络** — Agent 数量超过 20 时必须考虑

---

*Round 9 完成: 2026-04-02 18:31 | 下轮: Round 10 终极整合*
