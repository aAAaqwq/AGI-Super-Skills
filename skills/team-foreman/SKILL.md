# Team Foreman — 团队监工巡查 Skill

> 每 15 分钟由 cron 调用。核心目标：**真实推进任务，不是写报告。**

## Agent 清单

| agentId | 名字 | accountId | 群聊 sessionKey 后缀 |
|---------|------|-----------|---------------------|
| main | 小a | default | agent:main:telegram:group:-1003890797239 |
| ops | 小ops | xiaoops | agent:ops:telegram:group:-1003890797239 |
| code | 小code | xiaocode | agent:code:telegram:group:-1003890797239 |
| quant | 小quant | xiaoq | agent:quant:telegram:group:-1003890797239 |
| research | 小research | xiaoresearch | agent:research:telegram:group:-1003890797239 |
| finance | 小finance | xiaofinance | agent:finance:telegram:group:-1003890797239 |
| data | 小data | xiaodata | agent:data:telegram:group:-1003890797239 |
| market | 小market | xiaomarket | agent:market:telegram:group:-1003890797239 |
| pm | 小pm | xiaopm | agent:pm:telegram:group:-1003890797239 |
| content | 小content | xiaocontent | agent:content:telegram:group:-1003890797239 |
| law | 小law | xiaolaw | agent:law:telegram:group:-1003890797239 |
| product | 小product | xiaoproduct | agent:product:telegram:group:-1003890797239 |
| sales | 小sales | xiaosales | agent:sales:telegram:group:-1003890797239 |

群聊 ID: `-1003890797239`

## 活跃项目注册表

| 项目 | 负责 agent | 关键文件 | 优先级 |
|------|-----------|----------|--------|
| MediaClaw | 小code | `~/clawd/projects/MediaClaw/progress.json` | P1 |
| Super-Quant-Claw | 小pm(待PRD审核)→小quant | `~/clawd/projects/super-quant-claw/PRD.md` | P1 |
| 内容自动化 | 小content | `~/clawd/projects/content-automation-bot/PRD.md` | P2 |

---

## 执行步骤

### Step 0: 时间判断
- **08:00-23:00**: 正常巡检 + 推进
- **23:00-08:00**: 静默退出 (NO_REPLY)

### Step 1: 快速扫描 Cron 状态
```
cron(action='list')
```
筛选出需要关注的：
- `consecutiveErrors >= 2` → 记录，准备修复
- `lastRunStatus == "error"` → 记录，准备修复
- 跳过正常的任务

### Step 2: 扫描活跃 Session（核心）

```
sessions_list(activeMinutes=60, kinds=['agent'], messageLimit=1)
```

对每个活跃 session，读取最近对话：
```
sessions_history(sessionKey="<key>", limit=10, includeTools=false)
```

**重点关注以下信号：**

| 信号 | 动作 |
|------|------|
| agent 说"完成"但没后续 | 确认闭环，推进下一步 |
| agent 说"卡住/等待/需要@xxx" | 立即协调 |
| agent 承诺了下一步但没执行 | 催促 |
| agent 报了 error | 诊断并修复 |
| 跨 agent 依赖 | 推动交接 |

### Step 3: 扫描项目进度文件
```bash
for f in ~/clawd/projects/*/progress.json; do
  echo "=== $(basename $(dirname $f)) ==="
  cat "$f" 2>/dev/null | head -20
done
```

### Step 4: 🔥 真实推进动作（最重要的一步）

**这一步必须产生实际的 sessions_send 或 message 调用。不执行 Step 4 = 任务失败。**

#### 4a. 项目推进
对每个卡住或停滞的项目：
```
sessions_send(
  sessionKey="agent:<agentId>:telegram:group:-1003890797239",
  message="【CEO推进】{项目名} 当前状态: {从session提取的具体状态}\n\n需要你做: {明确的下一步动作}\n\n完成后在群里汇报进展。"
)
```

#### 4b. 跨 agent 协调
发现交接断点时，向双方发消息：
```
sessions_send(
  sessionKey="agent:<targetAgentId>:telegram:group:-1003890797239",
  message="【CEO协调】小{source} 已完成 {工作}，需要你接手 {具体任务}。\n输入文件: {路径}\n期望产出: {格式}\n完成后群里汇报。"
)
```

#### 4c. 承诺追踪
- agent 承诺 >30min 未执行 → 发消息温和提醒
- agent 承诺 >2h 未执行 → 催促
- agent 承诺 >4h 未执行 → 群里@Daniel

#### 4d. Cron 修复
- timeout 导致失败 → 调大 timeout
- 脚本 bug → 直接读文件修
- 修完重跑验证: `cron(action='run', jobId=xxx, runMode='force')`

#### 4e. Agent 无响应
- 催促后 15min 无群聊活动 → 群里再次@
- 连续 2 次催促无响应 → 群里@小a
- 连续 3 次 → 群里@Daniel

### Step 5: 汇报到本群（仅在有实质内容时）

**只在以下情况发群汇报：**
- 执行了至少 1 个推进动作（sessions_send / cron修复 / 文件修改）
- 发现需要 Daniel 介入的问题
- 全绿 + 无动作 → NO_REPLY（不刷屏）

汇报格式（精简）：
```
🔍 团队监工 (HH:MM)
━━━━━━━━━━━━━━

🚀 推进动作
- 已催促@小{agent}做{具体事}
- 已协调 小{A} → 小{B} 交接 {具体任务}

🔧 修复
- {任务名}: {修复内容} ✅

⚠️ 需关注
- {问题描述}

📊 活跃 {X}/13 | Cron ✅{X} ⚠️{X} ❌{X}
```

---

## 巡检持久化

```bash
# 读取上一轮快照（用于对比催促效果）
cat ~/clawd/tmp/foreman-snapshot.json 2>/dev/null

# 写入本轮快照
mkdir -p ~/clawd/tmp
cat > ~/clawd/tmp/foreman-snapshot.json << 'EOF'
{
  "timestamp": "$(date -Iseconds)",
  "actions_taken": ["催促了小xxx做yyy", "修复了zzz cron"],
  "pending_followup": ["等待小xxx回应", "等待小yyy完成zzz"],
  "cron_alerts": []
}
EOF
```

下一轮优先检查 `pending_followup` 中的事项是否已解决。

---

## 铁律

1. **推进 > 汇报** — 没执行 sessions_send 就不算完成任务
2. **全绿静默** — 一切正常时 NO_REPLY
3. **能修就修** — 脚本 bug 直接改
4. **能催就催** — 项目卡住直接发消息，不等不靠
5. **深夜不打扰** — 23:00-08:00 静默
6. **群里汇报** — 所有催促都要求 agent 在群里回复
7. **具体 > 泛泛** — 催促消息必须包含具体状态和具体期望
8. **token 预算** — 每个 session 只读最近 10 条，最多检查 5 个 session
9. **推送只到本群** — 汇报只发到 -1003890797239，不推私聊
