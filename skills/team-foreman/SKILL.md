# Team Foreman — 团队监工巡查 Skill

> 每 15 分钟由 cron 调用。核心目标：**真实推进任务，不是写报告。**

## ⚡ 进度同步机制（核心改进）

**问题**：每次巡检信息不同步，重复催促已完成的任务。
**方案**：以 **git log + progress 文件** 为进度真相源。

### Step 0.5: 加载进度快照（新增，必须执行）

```bash
# 1. 读取上一轮快照
PREV=$(cat ~/clawd/tmp/foreman-snapshot.json 2>/dev/null)

# 2. 从 git 获取各项目真实进度（最近24h commits）
for repo in ~/clawd/projects/MediaClaw ~/clawd/projects/super-quant-claw ~/clawd/projects/content-automation-bot; do
  name=$(basename $repo)
  if [ -d "$repo/.git" ]; then
    echo "=== $name (git) ==="
    git -C "$repo" log --oneline --since="24 hours ago" --format="%h %s (%cr)" 2>/dev/null | head -5
  else
    echo "=== $name (no git) ==="
    # 非 git 项目：用 progress.json 或最近修改文件
    [ -f "$repo/progress.json" ] && cat "$repo/progress.json" | head -10
    ls -lt "$repo/" --time=ctime 2>/dev/null | head -3
  fi
done

# 3. 检查各 agent 今日工作产出（workspace 日志）
today=$(date +%Y-%m-%d)
for ws in ~/clawd/workspace-*/; do
  agent=$(basename $ws)
  if [ -f "$ws/memory/$today.md" ]; then
    echo "=== $agent 今日记录 ==="
    tail -5 "$ws/memory/$today.md"
  fi
done

# 4. 读取 CEO main session 当日记忆（进度真相源）
tail -20 ~/.openclaw/workspace-main/memory/$today.md 2>/dev/null
```

**进度判断规则**：
- 项目有新 git commit → 已推进，**不催促**
- agent workspace 有今日记忆且含"完成/启动/修复" → 已推进
- CEO main memory 已记录任务完成 → **绝不重复催促**
- 仅当以上三项都无更新时，才判断为"停滞"

### 推进后必须写回进度

每次执行推进动作后，必须更新快照：
```bash
cat > ~/clawd/tmp/foreman-snapshot.json << EOF
{
  "timestamp": "$(date -Iseconds)",
  "git_progress": {
    "MediaClaw": "$(git -C ~/clawd/projects/MediaClaw log --oneline -1 --format='%h %s' 2>/dev/null)",
    "super-quant-claw": "$(ls -lt ~/clawd/projects/super-quant-claw/ --time=ctime 2>/dev/null | head -2)"
  },
  "actions_taken": [],
  "resolved_items": [],
  "pending_followup": []
}
EOF
```

---

## Agent 清单

| agentId | 名字 | accountId | 群聊 sessionKey 后缀 |
|---------|------|-----------|---------------------|
| main | 小a | default | agent:main:telegram:group:-1003890797239 |
| cto | 小ops/CTO | xiaoops | agent:cto:telegram:group:-1003890797239 |
| pe | 小code/PE | xiaocode | agent:pe:telegram:group:-1003890797239 |
| cqo | 小quant/CQO | xiaoq | agent:cqo:telegram:group:-1003890797239 |
| cro | 小research/CRO | xiaoresearch | agent:cro:telegram:group:-1003890797239 |
| cfo | 小finance/CFO | xiaofinance | agent:cfo:telegram:group:-1003890797239 |
| cdo | 小data/CDO | xiaodata | agent:cdo:telegram:group:-1003890797239 |
| cmo | 小market/CMO | xiaomarket | agent:cmo:telegram:group:-1003890797239 |
| cco | 小content/CCO | xiaocontent | agent:cco:telegram:group:-1003890797239 |
| clo | 小law/CLO | xiaolaw | agent:clo:telegram:group:-1003890797239 |
| cpo | 小product/CPO | xiaoproduct | agent:cpo:telegram:group:-1003890797239 |
| cso | 小sales/CSO | xiaosales | agent:cso:telegram:group:-1003890797239 |
| coo | Grove/COO | xiaoops | agent:coo:telegram:group:-1003890797239 |

> **PM agent 已删除**（2026-04-13），不再存在。部分旧名称仍可用于 session 寻址。

群聊 ID: `-1003890797239`

## 活跃项目注册表

| 项目 | 负责 agent | 进度追踪方式 | 优先级 | 当前进度 |
|------|-----------|------------|--------|----------|
| MediaClaw | PE(CTO) | git repo | P1 | 查看 git log |
| Super-Quant-Claw | CQO | 非 git → 最近文件 + progress.json | P1 | Paper Trading RUNNING |
| 内容自动化 | CCO | **已停止** — Daniel"别再推了" | ❌ | 永久暂停 |

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

# 写入本轮快照（包含 git 进度指纹）
mkdir -p ~/clawd/tmp
cat > ~/clawd/tmp/foreman-snapshot.json << EOF
{
  "timestamp": "$(date -Iseconds)",
  "git_progress": {
    "MediaClaw": "$(git -C ~/clawd/projects/MediaClaw log --oneline -1 --format='%h' 2>/dev/null)",
    "super-quant-claw": "NOT_A_GIT_REPO"
  },
  "resolved_items": [],
  "actions_taken": [],
  "pending_followup": []
}
EOF
```

下一轮优先检查 `pending_followup` 中的事项是否已解决。

## 非 Git 项目进度追踪

对 `super-quant-claw` 等非 git 项目，使用以下方式追踪进度：

```bash
# 1. 最近修改的关键文件
find ~/clawd/projects/super-quant-claw/strategies/ -name "*.py" -newer ~/clawd/tmp/foreman-snapshot.json 2>/dev/null

# 2. Paper Trading 状态
curl -s -u freqtrade:freqtrade http://127.0.0.1:8082/api/v1/status 2>/dev/null

# 3. 主 workspace CEO memory（进度真相源）
tail -30 ~/.openclaw/workspace-main/memory/$(date +%Y-%m-%d).md 2>/dev/null | grep -E "完成|启动|修复|RUNNING|已确认"
```

**关键规则**：CEO main session 的 `memory/YYYY-MM-DD.md` 是最终进度真相源。如果 CEO memory 记录了"Paper Trading 已启动 RUNNING"，则**不再催促**。

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
