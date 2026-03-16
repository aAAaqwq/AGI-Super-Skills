# Team Supervisor Skill — 团队监工

监控所有 agent 的任务执行状态，发现未响应/未完成的 agent 自动催促。

## 触发方式
- Cron 定时执行（建议每 15 分钟）
- 手动调用

## 执行流程

1. **扫描活跃 session**:
   - 调用 `sessions_list(activeMinutes=30, messageLimit=1)` 获取所有 agent session
   - 检查每个 agent 的 `updatedAt` 时间

2. **判断状态**:
   | 状态 | 条件 | 动作 |
   |------|------|------|
   | ✅ 正常 | updatedAt < 15min 且有产出 | 无 |
   | ⚠️ 疑似卡住 | updatedAt > 15min 且无新消息 | 发催促 |
   | ❌ abort/无响应 | lastRun aborted 或 session 不存在 | 重发任务 + 报告 CEO |
   | 🔄 正在执行 | updatedAt < 5min | 等待 |

3. **催促机制**:
   - 第一次: `sessions_send` 温和催促
   - 第二次(30min后): 强制催促 + 通知 CEO
   - 第三次(60min后): 报告 Daniel

4. **汇报格式**:
```
🔍 团队监工巡检报告
━━━━━━━━━━━━━━
✅ 正常: 小quant(22:10), 小content(22:05)
⚠️ 疑似卡住: 小code(21:45, 未产出)
❌ 无响应: 小ops(session aborted)
📊 活跃率: 10/12 (83%)
```

## 不在巡检范围
- 23:00-08:00 静默期不巡检
- Cron 自动任务不算
