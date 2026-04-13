# Team Foreman — 团队监工巡查 Skill

> 触发词: 监工、巡查、foreman、团队状态、项目推进、巡检

## 用途

CEO 的监工助手，定期检查团队健康 + 主动推进卡住的任务。由 cron 每 15 分钟调用一次。

## Agent 清单

| agentId | 名字 | accountId | sessionKey |
|---------|------|-----------|------------|
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

## 项目注册表

读取 `~/clawd/projects/*/progress.json` 和 `~/clawd/projects/*/PRD.md` 扫描所有活跃项目。

### 当前活跃项目（硬编码 + 自动扫描结合）

| 项目 | 负责 agent | 关键文件 | 优先级 |
|------|-----------|----------|--------|
| MediaClaw | 小code | `~/clawd/projects/MediaClaw/progress.json` | P1 |
| Super-Quant-Claw | 小pm(待PRD审核)→小quant | `~/clawd/projects/super-quant-claw/PRD.md` | P1 |
| 内容自动化 | 小content | `~/clawd/projects/content-automation-bot/PRD.md` | P2 |

---

## 执行步骤（严格按顺序）

### Step 0: 时间判断
- **08:00-23:00**: 正常巡检 + 推进
- **23:00-08:00**: 仅记录，不修不推不报，静默退出 (NO_REPLY)

### Step 1: 扫描 Cron 状态
```
cron(action='list')
```
找出:
- `state.runningAtMs` 有值的（正在执行）
- `state.consecutiveErrors >= 2` 的（反复出错）
- `state.lastRunStatus == "error"` 的（上次失败）

### Step 2: 扫描项目进度
```bash
# 扫描所有 progress.json
for f in ~/clawd/projects/*/progress.json; do
  echo "=== $(dirname $f) ==="
  cat "$f" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('project','?'), d.get('task','?'), d.get('assessed_at','?'))" 2>/dev/null
done

# 检查 PRD 文件（PRD 存在但无 progress.json = 待启动）
ls ~/clawd/projects/*/PRD.md 2>/dev/null
```

### Step 3: 扫描 Agent 活跃状态
```
sessions_list(activeMinutes=60, kinds=['agent'], messageLimit=1)
```

### Step 4: 🔑 扫描 Session 对话发现项目进展（核心新增）

**这是监工最关键的能力：通过读取 agent 的 session 对话历史，发现正在进行的工作、遇到的阻塞、以及需要跟进的承诺。**

#### 4a. 确定要检查的 session

从 Step 3 的 `sessions_list` 结果中，筛选出：
- 过去 1 小时内有活动（`updatedAt` 在 60min 内）的 agent session
- 状态为 `running` 或 `done` 的 session（跳过 `failed` 除非要排错）
- 关注群聊 session（`key` 包含 `telegram:group:-1003890797239`）和活跃的 cron/subagent session

**优先检查的 session 类型：**
1. **群聊 session** — agent 在群里的汇报和讨论（最重要）
2. **Cron session** — 正在/刚完成的定时任务
3. **Subagent session** — CEO 派出的子任务

#### 4b. 读取 session 对话历史

对每个需要检查的 session：
```
sessions_history(sessionKey="<key>", limit=10, includeTools=false)
```

**只读最近 10 条消息**（控制 token 消耗），重点关注 assistant 的回复内容。

#### 4c. 从对话中提取项目信号

扫描对话内容，识别以下模式：

**项目关键词匹配表：**

| 关键词 | 关联项目 | 负责 agent |
|--------|---------|-----------|
| MediaClaw, mediaclaw, xhs发布, 小红书发布, 选择器验证 | MediaClaw | 小code |
| Super-Quant, Freqtrade, freqtrade, 量化, SQC, 网格交易 | Super-Quant-Claw | 小pm/小quant |
| 内容自动化, daily-xhs, daily-gzh, daily-douyin | 内容自动化 | 小content |
| 樱花, MV, 音画同步, phase1_v4 | 樱花MV | 小code |
| Polymarket, 仓位, 止盈止损, Elon推文 | Polymarket | 小quant |
| PRD, 审核, 小product | PRD审核链 | 小pm/小product |

**提取的信号类型：**

| 信号 | 含义 | 推进动作 |
|------|------|---------|
| ✅ 完成 / 已完成 / success | 任务完成 | 更新 progress.json（如需要），确认闭环 |
| ⚠️ 阻塞 / blocking / 等待 / 需要 Daniel | 任务卡住 | 检查阻塞原因，能内部解决就推，否则升级 |
| 🔄 进行中 / 正在做 / WIP | 任务进行中 | 记录进展，预估完成时间 |
| ❌ 失败 / error / timeout | 任务失败 | 分析原因，尝试修复或重新派发 |
| 📋 承诺 / 下一步 / 待做 | agent 承诺了后续动作 | 跟踪是否按时执行 |
| 🤝 交接 / 需要@xxx / 等xxx完成 | 跨 agent 依赖 | 检查依赖方状态，推动交接 |

#### 4d. 建立本轮巡检的项目状态快照

综合 Step 2（文件进度）+ Step 4c（对话信号），为每个活跃项目建立实时状态：

```
项目状态快照示例：
{
  "MediaClaw": {
    "progress_file": "assessed_at: 04-08, 真实发布验证中",
    "session_signals": ["小code 最近1h无活动", "blocking: XHS登录需Daniel"],
    "status": "卡住 - 等Daniel登录",
    "action": "无需催促（等Daniel）"
  },
  "Super-Quant-Claw": {
    "progress_file": "PRD v1.0 完成，待审核",
    "session_signals": ["小pm 提到PRD已交小product", "小product 无近期活动"],
    "status": "PRD审核链断在product",
    "action": "催促小product审核"
  }
}
```

### Step 5: 主动推进（基于 Step 4 的发现）

**对每个识别到的问题，执行具体推进动作：**

#### 5a. 项目卡住 → 催促负责 agent（通过群聊 session）

```
sessions_send(
  sessionKey="agent:<agentId>:telegram:group:-1003890797239",
  message="【CEO催促】项目 {项目名} 进度停滞。\n\n当前状态: {从session对话中提取的具体状态}\n阻塞原因: {从对话中发现的具体阻塞}\n期望进展: {明确的下一步}\n\n请立即推进并在群里汇报进展。完成后用 message(action=send, channel=telegram, target=-1003890797239) 汇报。"
)
```

**催促消息必须包含：**
1. 从 session 对话中提取的**具体状态**（不是泛泛而谈）
2. **明确的期望**（下一步要做什么）
3. **群里汇报的要求**（不让私聊）

#### 5b. Cron 故障修复
- consecutiveErrors ≥ 2 + timeout → 自动调大 (300→600→900→1200→1800→❌人工)
- consecutiveErrors ≥ 3 → 检查 delivery/fallbacks/schedule
- delivery 缺失 → 改 announce
- 静默类任务（Session清理/Gateway重启/QMD同步）→ 不干预
- 连续失败 ≥ 5 → 群里 @Daniel 升级

#### 5c. 跨 agent 协调推动

**从 session 对话中发现跨 agent 依赖时主动推动：**

场景示例：
- 小data 采集完数据 → 该交接给小content 了 → 在群里 @小content
- 小pm 写完 PRD → 该交给小product 审核 → 在群里 @小product
- 小code 遇到需要 ops 配合的环境问题 → 在群里 @小ops
- 小quant 需要小research 的调研结果 → 在群里 @小research

```
sessions_send(
  sessionKey="agent:<targetAgentId>:telegram:group:-1003890797239",
  message="【CEO协调】@小{target}，小{source} 已完成 {具体工作}，需要你接手 {具体任务}。\n\n背景: {从session对话中提取的上下文}\n输入文件: {具体路径}\n期望产出: {具体格式}\n\n请完成后在群里汇报。"
)
```

#### 5d. 修复脚本/Skill
如果 cron 失败原因是脚本 bug：
1. 读取相关 skill/脚本文件
2. 分析根因
3. 用 edit/write 直接修复
4. 重跑验证: `cron(action='run', jobId=xxx, runMode='force')`

#### 5e. Agent 承诺追踪

**从对话中发现 agent 承诺了「下一步做 X」但尚未执行的情况：**
- 检查承诺时间 vs 当前时间
- 超过 30min 未执行 → 温和提醒
- 超过 2h 未执行 → CEO 催促
- 超过 4h 未执行 → 升级 Daniel

#### 5f. Agent 不响应处理
- 催促后 15min 无群聊活动 → 在群里再次 @该 agent
- 连续 2 次催促无响应 → 报告 CEO（群聊 @小a）
- 连续 3 次 → 报告 Daniel

### Step 6: 汇报到群聊

只有 **有实质内容** 时才发群汇报（全绿 + 无推进动作 = 静默）：

```
message(action=send, channel=telegram, target=-1003890797239)
```

格式：
```
🔍 团队监工 (HH:MM)
━━━━━━━━━━━━━━

🚀 项目推进
- {项目名}: {从对话发现的具体进展} → {推进动作}
- {项目名}: 已催促@小{agent}做{具体事}

📋 Session 巡查发现
- 小{agent}: {从对话中提取的最新状态}
- 小{agent}: 承诺{某事}，{是否已执行}

🔧 Cron 修复
- {任务名}: {修复内容} ✅
- {任务名}: ❌ 需人工介入

📊 整体
活跃 {X}/13 | Cron ✅{X} ⚠️{X} ❌{X}
```

---

## 巡检记录持久化

每轮巡检结果写入临时文件，供下一轮对比：

```bash
# 写入本轮快照
cat > ~/clawd/tmp/foreman-snapshot.json << 'EOF'
{
  "timestamp": "$(date -Iseconds)",
  "projects": { ... },
  "cron_status": { ... },
  "actions_taken": [ ... ],
  "pending_followup": [ ... ]
}
EOF
```

下一轮巡检时先读取：
```bash
cat ~/clawd/tmp/foreman-snapshot.json 2>/dev/null
```

**用途：**
- 对比 progress.json 的 `assessed_at` 是否有变化
- 检查上一轮催促的 agent 是否响应了
- 跟踪承诺追踪的时间线

---

## 铁律

1. **推进 > 汇报** — 能推动进展的动作优先于写报告
2. **全绿静默** — 一切正常时 NO_REPLY，不刷屏
3. **能修就修** — 脚本 bug 直接改，不等不靠
4. **能催就催** — 项目卡住直接 sessions_send，不给模棱两可的建议
5. **深夜不打扰** — 23:00-08:00 只记录不行动
6. **修复必须实际执行** — 用 tool 改文件/调参数，不要只写在报告里
7. **agent 必须群里汇报** — 催促时明确要求 agent 在群里汇报进展，不要私聊
8. **对话驱动推进** — 通过读 session 对话发现真实进展和阻塞，不依赖过时的 progress.json
9. **具体 > 泛泛** — 催促消息必须包含从对话中提取的具体状态和具体期望
10. **token 预算控制** — 每个 session 只读最近 10 条，不超过 5 个 session，总计 < 50 条消息

## 与 Cron 集成

cron payload 只需一行引用本 skill：
```
读取并严格执行 ~/clawd/skills/team-foreman/SKILL.md 中的全部步骤。
```
