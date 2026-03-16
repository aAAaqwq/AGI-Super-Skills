# Agent 任务派发与确认机制

确保每次派发任务后，agent 确实收到并在执行。

## 触发条件

- 每次通过 sessions_send 派发任务后自动执行
- "检查员工状态"、"任务确认"

## 派发后确认流程

### Step 1: 派发任务
```
sessions_send(sessionKey="agent:<id>:telegram:group:-1003890797239", message="【CEO指令】...")
```

### Step 2: 立即确认送达（30秒内）
```
sessions_list(activeMinutes=5, kinds=["agent"], messageLimit=0)
```
检查目标 agent 的 session 是否 active（updatedAt 在最近 60 秒内）。

### Step 3: 判断状态

| 状态 | 判断条件 | 处理 |
|------|----------|------|
| ✅ 已接收 | session active, updatedAt 刚更新 | 等汇报 |
| ⚠️ 可能卡住 | session active 但 5min+ 无新消息 | 发催促消息 |
| ❌ 未接收 | session 不在 active 列表 | 重发一次，仍失败则报告 Daniel |

### Step 4: 超时催促（5分钟无汇报）
如果 agent 5 分钟内没有发群里汇报，发催促：
```
sessions_send(sessionKey="agent:<id>:...", message="【催促】你的任务完成了吗？立即用 message 发群里汇报进度。")
```

### Step 5: 死亡判定（10分钟无响应）
如果催促后 5 分钟仍无反应：
1. 检查 agent 的 session 是否报错（abortedLastRun）
2. 报告 Daniel："小X 可能卡住了，需要检查"
3. 考虑重新派发给其他 agent

## 每次派发的标准模板

任务消息必须包含：
1. 【CEO指令】开头
2. 具体任务描述
3. 文件写在哪里
4. 完成后的 message 汇报指令（含 accountId）
5. "不发群里 = 任务没完成"

## 批量检查命令

快速检查所有 agent 状态：
```
sessions_list(activeMinutes=10, kinds=["agent"], messageLimit=1)
```
看每个 agent 的 updatedAt 和最后一条消息判断是否在工作。
