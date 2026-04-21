---
name: project-autoloop
description: Project autoloop engine — cron-driven automated project iteration with CEO coordination
---

# Project Autoloop Engine 🔄

项目自循环引擎 — Cron 驱动的自动化项目迭代器。CEO 作为项目经理协调各 agent 有序推进，直到验收通过或遇到需要人工干预的 blocker。

## 一句话

> Daniel 说一句话启动，小a 按 PM 模式协调各 agent 逐步推进，达标后自动删除 cron 并汇报结果。Daniel 只看结果，不听过程。

## 触发条件

- `启动项目循环`
- `开始自动迭代`
- `autoloop`
- `查看项目循环状态`
- `停止项目循环`

## Daniel 的三条铁律

> 以下三条由 Daniel 制定，不可违反：

1. **达标后自动删除该临时循环 cron** — 不是禁用，是彻底 `cron remove`，不留垃圾
2. **CEO 统一协调，按敏捷原则按需调度专业 agent** — pm 管进度、code 写代码、research 调研、data 采集，按需派活不越权
3. **agent 解决不了的问题统一记录为 blocker 汇报 Daniel** — 不废话过程，Daniel 只看结果；需要什么直接问，拿不到就跳过做下一步

## 架构

```
Daniel 一句话启动
       ↓
  ┌──────────────────────────────────┐
  │  CEO 初始化（主 session）          │
  │  ① 解析项目路径 + 验收标准         │
  │  ② 按 PM 模式拆解为可执行任务链     │
  │  ③ 创建 acceptance-criteria.md    │
  │  ④ 创建 progress.json            │
  │  ⑤ 设置 cron 循环                 │
  │  ⑥ 确认启动                       │
  └────────────┬─────────────────────┘
               ↓
  ┌──────────────────────────────────────────┐
  │  Cron 每轮触发（隔离 Session = CEO 轮次）  │
  │                                          │
  │  以小a CEO 身份执行 PM 循环：               │
  │                                          │
  │  ① 读 progress.json（当前状态）            │
  │  ② 检查哪些 agent 在忙（避免重复派发）       │
  │  ③ 按优先级评估未完成条件                    │
  │  ④ 未通过 → 按职责矩阵派给对应 agent        │
  │  ⑤ 遇到 agent 解决不了的 → 记 blocker      │
  │  ⑥ 写回 progress.json                     │
  │  ⑦ 全部通过 → 删除 cron + 通知 Daniel      │
  │  ⑧ 超轮次/blocker 汇总 → 通知 Daniel       │
  └──────────────────────────────────────────┘
               ↓
  ┌─────────────────────────────────────┐
  │  Agent 执行（群聊上下文）               │
  │  收到指令 → 执行 → 群里汇报结果          │
  │  解决不了 → 标记 blocker + 说明原因     │
  └─────────────────────────────────────┘
               ↓
  等待下一轮 cron → 回到顶部
```

## 核心机制

### 为什么用 Cron 而不是 While Loop

| 维度 | while loop | Cron 循环 |
|------|-----------|----------|
| 上下文 | 同一 session（context 爆炸风险） | 每轮独立隔离 session |
| 容错 | 崩溃即死 | 自动恢复，重启后继续 |
| 多 agent | 难并行 | 天然并行 |
| 持久化 | 无 | progress.json 文件 |
| 资源 | 一直占 context | 用完释放 |

### 敏捷调度原则

每轮 cron 执行时，CEO 按以下原则调度：

1. **依赖排序**：有前置依赖的条件优先排，并行条件同时派
2. **职责匹配**：严格按职责矩阵派活，不混派
3. **忙碌检查**：`sessions_list(activeMinutes=20)` 检查 agent 是否在忙，忙则跳过本轮
4. **Blocker 处理**：agent 反馈无法解决 → 标记 blocker + 分类（人工/资源/外部） → 不卡死，跳过继续下一条件
5. **不空转**：如果本轮无任务可派（都在忙或都 blocker），本轮只记录状态

### Blocker 管理（铁律 #3 落地）

| Blocker 类型 | 处理方式 | 示例 |
|-------------|---------|------|
| **人工决策** | 记录并跳过，下次 cron 仍会检查 | 需要付费 API key、需要 Daniel 选择方案 |
| **资源缺失** | 记录并尝试找替代方案，替代不了则跳过 | 没有服务器、没有账号权限 |
| **外部依赖** | 记录并跳过，条件设为 `blocked` | 第三方服务宕机、API 无响应 |
| **技术瓶颈** | 最多重试 2 次，第 3 次仍失败 → blocker | 代码 bug 修不好、环境配置问题 |

**Blocker 汇报格式（Daniel 只看这个）：**

```
🚧 [项目名] Blocker 清单
━━━━━━━━━━━━━━━━━━━━
| # | 条件 | 类型 | 需要什么 | 当前方案 |
|---|------|------|---------|---------|
| 1 | 数据源可用 | 人工 | 天眼查 API key 或替代源 | 跳过，先做集成层 |
| 2 | 部署上线 | 资源 | 需要服务器 IP | 跳过，先做本地测试 |
━━━━━━━━━━━━━━━━━━━━
✅ 已完成: 3/5 | 🟡 进行中: 1/5 | 🚧 Blocker: 1/5
需 Daniel 决策: 第1条（给 key 或用替代方案？）
```

## 使用流程

### 第一步：Daniel 下达指令

```
启动项目循环：
  项目路径: ~/clawd/projects/xxx/
  验收标准: [具体标准，或指向文件]
  频率: [15min / 30min / 1h]（默认 15min）
  最大轮次: [数字]（默认 20）
```

**验收标准可以是：**
- 内联描述：`"至少有1个免费数据源可用"`
- 文件引用：`"按 PRD.md 中的验收标准"`
- 列表：`"1. 数据源层通过 2. 集成层通过 3. 通信层通过"`

### 第二步：CEO 初始化（主 session 执行）

1. 解析指令，确定：
   - 项目路径
   - 验收标准（解析为结构化条件列表）
   - 每条条件的负责 agent（按职责矩阵匹配）
   - 条件间依赖关系（哪些需要先完成）
   - 验证方法（读文件/执行命令/API 检查）
2. 在项目目录创建 `acceptance-criteria.md`
3. 在项目目录创建 `progress.json`
4. 通过 `cron add` 创建循环任务（`sessionTarget: "isolated"`）
5. 记录 cronJobId 到 progress.json
6. 向 Daniel 确认：项目名、条件数、频率、cron ID

### 第三步：自动迭代（Cron 驱动）

每轮 cron 触发隔离 session，CEO 以 PM 模式执行 Driver Prompt（见下方）。

### 第四步：完成

- **全部达标** → `cron remove` 彻底删除临时循环 → message 通知 Daniel → 只发结果摘要
- **出现 Blocker** → 继续推进非 blocker 条件 → Blocker 汇总下次一起汇报（不每条都打扰）
- **超最大轮次** → `cron remove` 删除 → 汇报最终结果：通过项 / blocker 项 / 建议下一步

### 手动控制

| 指令 | 动作 |
|------|------|
| `查看项目循环状态` | 读 progress.json → 简洁进度条 + blocker 清单 |
| `停止项目循环` | `cron remove` 删除 → 通知 |
| `继续项目循环` | 重新创建 cron |
| `重置项目循环` | 清零 progress.json → 重建 cron |

## Driver Prompt（核心 — 每轮 cron 执行的内容）

CEO 在创建 cron 时，将以下模板填入 `{变量}` 后作为 cron payload 的 message：

```
你是小a（CEO），当前以 PM 模式驱动项目自循环。你只做三件事：评估进度、派发任务、处理 blocker。绝不亲自写代码/跑脚本/做采集。

## 项目信息
- 路径: {projectPath}
- 验收标准: {acceptanceCriteriaPath}
- 进度文件: {progressPath}
- 当前轮次: R{currentRound}/{maxRounds}

## 执行步骤

### Step 1: 读取状态
- read {progressPath} → 获取所有 criteria 状态和 blocker 列表
- read {acceptanceCriteriaPath} → 获取完整验收条件

### Step 2: 检查 agent 活跃状态
- sessions_list(activeMinutes=20) → 哪些 agent 在忙
- 对 in_progress 状态的条件，如果负责 agent 在忙 → 跳过本轮，不重复派发
- 对 status=blocked 的条件 → 跳过，Daniel 未处理前不动

### Step 3: 按 PM 模式调度（核心）

按优先级处理未完成条件：

**3a. 可立即派发的（not_started 且 agent 空闲）：**
→ sessions_send 派给对应 agent，消息格式：
  【自循环 R{round}/{maxRounds} | {项目名}】
  任务: {具体可执行的指令，含输入文件路径和输出文件路径}
  输出到: {期望的产出文件/结果}
  如果无法完成，标记原因后群里汇报。
  不发群里 = 没完成。
→ 更新 status 为 in_progress，记录 dispatchedAt

**3b. 验证已完成的（in_progress 且 agent 已完成）：**
→ 根据 verification 字段执行检查：
  - "file_exists: <path>" → read 检查文件是否存在且非空
  - "file_contains: <path>:<pattern>" → read + grep
  - "exec: <command>" → exec 检查返回码
  - "manual" → 信任 agent 汇报
→ 通过 → status 改为 passed
→ 不通过 → 重新派发（带上次失败原因），同一条件最多重试 3 次

**3c. 超过 3 次仍失败 → blocker**
→ status 改为 blocked
→ 记录 blockerReason
→ 跳过，继续处理下一个条件
→ 不卡死在任何一个条件上

### Step 4: 写回进度
- currentRound += 1
- 写入本轮 history 条目（简洁：派了谁、结果如何）
- write 更新 {progressPath}

### Step 5: 终止判断

**全部通过：**
→ cron(remove) 删除这个临时 cron（jobId: {cronJobId}）— 彻底删除，不留垃圾
→ message 通知 Daniel，格式：
  ✅ {项目名} — 项目完成
  完成: {N}/{N} 条验收条件
  总耗时: {elapsed}
  Blocker: 无（或有 N 条已跳过）

**超最大轮次：**
→ cron(remove) 删除
→ message 通知 Daniel：
  ⏱️ {项目名} — 达到最大轮次 R{maxRounds}
  ✅ 通过: {N} | 🚧 Blocker: {M}
  Blocker 清单:
    1. {描述} — 需要什么 — {agent} 反馈原因

## Agent Session Key 路由表
| Agent | session_key |
|-------|------------|
| 小data | agent:data:telegram:group:-1003890797239 |
| 小code | agent:code:telegram:group:-1003890797239 |
| 小quant | agent:quant:telegram:group:-1003890797239 |
| 小content | agent:content:telegram:group:-1003890797239 |
| 小research | agent:research:telegram:group:-1003890797239 |
| 小ops | agent:ops:telegram:group:-1003890797239 |
| 小pm | agent:pm:telegram:group:-1003890797239 |
| 小market | agent:market:telegram:group:-1003890797239 |
| 小finance | agent:finance:telegram:group:-1003890797239 |

## 铁律
1. 只做 PM（评估 + 派发），绝不亲自执行具体任务
2. 派发要具体：输入在哪、输出放哪、验收标准是什么
3. 不重复派发正在执行的任务
4. 解决不了就记 blocker 跳过，不卡死
5. 全部通过或超轮次时必须 cron remove 彻底删除，零残留
6. Daniel 只看结果，汇报不超过 5 行
```

## 进度文件 Schema (progress.json)

```json
{
  "project": {
    "name": "项目名",
    "path": "~/clawd/projects/xxx/",
    "startedAt": "2026-03-27T16:50:00+08:00",
    "startedBy": "Daniel",
    "cronJobId": "uuid"
  },
  "config": {
    "intervalMs": 900000,
    "maxRounds": 20,
    "maxRetriesPerCriterion": 3,
    "acceptanceFile": "acceptance-criteria.md"
  },
  "status": "running | completed | timeout | stopped",
  "currentRound": 0,
  "criteria": [
    {
      "id": "c1",
      "description": "至少1个免费数据源验证通过",
      "dependsOn": [],
      "verification": "file_contains: ~/clawd/projects/xxx/data-source-results.md: passed ✅",
      "responsibleAgent": "data",
      "status": "not_started | in_progress | passed | blocked",
      "retryCount": 0,
      "blockerReason": null,
      "lastDispatchedAt": null,
      "lastCheckedAt": null,
      "passedAt": null
    }
  ],
  "blockers": [],
  "history": [
    {
      "round": 1,
      "timestamp": "2026-03-27T16:50:00+08:00",
      "dispatched": ["c1 → data"],
      "passed": [],
      "newBlockers": [],
      "skipped": [],
      "summary": "首轮：派发数据源验证给小data"
    }
  ]
}
```

## 验收标准格式 (acceptance-criteria.md)

```markdown
# 验收标准 — [项目名]

## 概述
[一句话项目目标]

## 验收条件

### 1. [c1] 条件描述
- **验证方法**: `file_exists | file_contains | exec | manual`
- **验证目标**: [文件路径/命令/具体内容]
- **负责 Agent**: [data/code/quant/content/research/ops/pm/market/finance]
- **依赖**: [无 / c1]
- **输出物**: [期望的产出文件/结果]
- **通过标准**: [具体可量化的标准]
```

## 安全限制

| 参数 | 默认值 | 最小值 | 最大值 | 说明 |
|------|--------|--------|--------|------|
| maxRounds | 20 | 1 | 100 | 最大迭代轮次 |
| intervalMs | 900000 (15min) | 300000 (5min) | 3600000 (1h) | 循环间隔 |
| maxRetriesPerCriterion | 3 | 1 | 5 | 单条件最大重试 |
| maxDispatchPerRound | 3 | 1 | 5 | 每轮最多派发数 |
| projectTimeout | 6h | 1h | 72h | 项目总超时 |

## 状态报告格式（查看项目循环状态时）

```
🔄 项目自循环 — {name}
━━━━━━━━━━━━━━━━━━━━
📊 R{currentRound}/{maxRounds} | ⏱️ {elapsed}
✅ {passed}/{total} | 🟡 {inProgress} | 🚧 {blocked}

Blocker:
  1. {描述} — 需要什么
━━━━━━━━━━━━━━━━━━━━
```

## 完整示例

### 启动

> Daniel: 启动项目循环：~/clawd/projects/domestic-acquisition-v1/，验收标准按 PRD.md 中的 4 层架构全部通过，频率 15min，最大 30 轮

CEO 执行：
1. 读 PRD.md → 解析出 4 层验收条件 + 依赖关系
2. 拆解为可执行任务（pm 出验收清单、code 写代码、data 采集…）
3. 创建 acceptance-criteria.md（N 条条件）
4. 创建 progress.json（status: running, round: 0）
5. cron add → 每 15min 隔离 session 执行 PM driver prompt
6. 确认：`🔄 项目循环已启动 — {name} | {N} 条条件 | 15min/轮 | 最多 30 轮 | Cron ID: xxx`

### 中途查看

> Daniel: 项目循环状态

CEO 读 progress.json → 5 行以内状态报告

### 停止

> Daniel: 停止项目循环

CEO → `cron remove` 彻底删除 → 确认通知

---

*Created: 2026-03-27*
*Author: 小a CEO*
*Version: 2.0*
