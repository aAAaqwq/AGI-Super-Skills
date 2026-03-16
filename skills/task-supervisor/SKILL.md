# Task Supervisor Skill — 任务监工

## 概述
每 15 分钟自动巡检所有 agent 的工作状态，发现偷懒/卡死/abort 立即告警。

## 触发
- Cron: 每 15 分钟
- 手动: `task-supervisor check`

## 巡检流程

### Step 1: 获取活跃 session 列表
```
sessions_list(activeMinutes=20, messageLimit=1)
```

### Step 2: 逐个检查
对每个 agent session:
1. **是否活跃** — updatedAt 在 15min 内?
2. **是否 abort** — lastMessage.stopReason == "aborted"?
3. **是否完成** — 有没有发群汇报?
4. **是否偷懒** — 收到任务但没有产出文件?

### Step 3: 异常分类
| 等级 | 情况 | 动作 |
|------|------|------|
| 🔴 P0 | session aborted/crash | 重发任务 + 告警 |
| 🟡 P1 | 15min 无进展 | 发催促 |
| 🟢 OK | 正常工作中 | 不打扰 |

### Step 4: 汇报
发到群里（accountId=default, target=-1003890797239）:
```
🔍 监工巡检 [HH:MM]
━━━━━━━━━━━━━━
✅ 小quant: [状态]
✅ 小content: [状态]
❌ 小code: [问题] → [处理]
...
```

### Step 5: 自动处理
- abort 的 session: 自动用 sessions_send 重发最近的任务
- 超时的 agent: 发催促消息
- 全部正常: 静默不汇报（不打扰 Daniel）

## 关键规则
1. **全部正常时不汇报** — 只在发现问题时告警
2. **不重复催促** — 同一 agent 15min 内只催一次
3. **深夜模式** — 23:00-08:00 不催促，只记录
4. **汇报精简** — ≤200字，只说问题和处理
