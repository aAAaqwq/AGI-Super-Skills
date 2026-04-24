# Team Foreman — 团队监工巡查 Skill

> 每 15 分钟由 cron 调用。核心目标：**真实推进任务，不是写报告。**
> 版本: 2026-04-19 | Wave 2.1 修复重复催促
> **v2 修复**：sessions_send → message 工具（避免 heavy group session 超时）
> **v2 修复**：升级逻辑必须有实质证据，不再基于 sessions_send 超时
> **v3 修复**：Step 1 直接读 jobs.json（CTO方案），Freqtrade改用 freqtrade-health.sh（CQO方案）
> **v3 修复**：LinuxDo ced988c3 已确认正常，禁止重复催促

## ⚡ 进度同步机制（核心改进）

**问题**：每次巡检信息不同步，重复催促已完成的任务。
**方案**：以 **git log + progress 文件 + CEO memory** 为进度真相源。

### Step 0.5: 加载进度快照（必须执行）

```bash
# 1. 读取上一轮快照
PREV=$(cat ~/.openclaw/tmp/foreman-snapshot.json 2>/dev/null)

# 2. 从 git 获取各项目真实进度（最近24h commits）
for repo in ~/clawd/projects/MediaClaw ~/clawd/projects/super-quant-claw ~/clawd/projects/content-automation-bot; do
  name=$(basename $repo)
  if [ -d "$repo/.git" ]; then
    echo "=== $name (git) ==="
    git -C "$repo" log --oneline --since="24 hours ago" --format="%h %s (%cr)" 2>/dev/null | head -5
  else
    echo "=== $name (no git) ==="
    [ -f "$repo/progress.json" ] && cat "$repo/progress.json" | head -10
    ls -lt "$repo/" --time=ctime 2>/dev/null | head -3
  fi
done

# 3. 检查各 agent 今日工作产出（workspace 日志）
today=$(date +%Y-%m-%d)
for ws in ~/.openclaw/workspace-*/; do
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
mkdir -p ~/.openclaw/tmp
cat > ~/.openclaw/tmp/foreman-snapshot.json << EOF
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

| agentId | 角色 | accountId | 群聊 sessionKey 后缀 |
|---------|------|-----------|---------------------|
| main | Musk CEO | default | agent:main:telegram:group:-1003890797239 |
| cto | Jensen CTO | xiaoops | agent:cto:telegram:group:-1003890797239 |
| pe | 小code PE | xiaocode | agent:pe:telegram:group:-1003890797239 |
| cqo | 小quant CQO | xiaoq | agent:cqo:telegram:group:-1003890797239 |
| cro | 小research CRO | xiaoresearch | agent:cro:telegram:group:-1003890797239 |
| cfo | 小finance CFO | xiaofinance | agent:cfo:telegram:group:-1003890797239 |
| cdo | 小data CDO | xiaodata | agent:cdo:telegram:group:-1003890797239 |
| cmo | 小market CMO | xiaomarket | agent:cmo:telegram:group:-1003890797239 |
| cco | 小content CCO | xiaocontent | agent:cco:telegram:group:-1003890797239 |
| clo | 小law CLO | xiaolaw | agent:clo:telegram:group:-1003890797239 |
| cpo | 小product CPO | xiaoproduct | agent:cpo:telegram:group:-1003890797239 |
| cso | 小sales CSO | xiaosales | agent:cso:telegram:group:-1003890797239 |
| coo | Grove COO | xiaoops | agent:coo:telegram:group:-1003890797239 |
| batch | Batch | — | agent:batch:telegram:group:-1003890797239 |

> **注意**：PM agent 已于 2026-04-13 彻底删除，产品职责由 CPO (cpo) 承担。禁止在任何场景引用 "pm" 作为 agent ID。

群聊 ID: `-1003890797239`

## 活跃项目注册表

| 项目 | 负责 agent | 进度追踪方式 | 优先级 | 当前进度 |
|------|-----------|------------|--------|----------|
| MediaClaw | PE (code) | git repo | P1 | 查看 git log |
| Super-Quant-Claw | CQO (quant) | 非 git → 最近文件 + progress.json | P1 | Paper Trading RUNNING |
| 内容自动化 | CCO (content) | **已停止** — Daniel 指示暂停 | ❌ | 永久暂停 |

---

## 执行步骤

### Step 0: 时间判断
- **08:00-23:00**: 正常巡检 + 推进
- **23:00-08:00**: 静默退出 (NO_REPLY)

### Step 1: 快速扫描 Cron 状态

**必须使用脚本精确检查，不要依赖 LLM 解读 `cron(action='list')` 的文本输出。**

```bash
# 精确 cron 状态检查（替代 cron list 文本解读）
python3 << 'PYEOF'
import json, time

with open("/home/aa/.openclaw/cron/jobs.json") as f:
    data = json.load(f)

jobs = []
for v in data.values():
    if isinstance(v, list): jobs.extend(v)
    elif isinstance(v, dict): jobs.append(v)

now_ms = int(time.time() * 1000)
issues = []
for j in jobs:
    if not j.get("enabled", True):
        continue
    s = j.get("state", {})
    jid = str(j.get("id", ""))[:8]
    name = j.get("name", "?")
    consec = s.get("consecutiveErrors", 0)
    status = s.get("lastRunStatus", "unknown")
    err_reason = s.get("lastErrorReason", "")
    running = s.get("runningAtMs")
    last_run = s.get("lastRunAtMs", 0)
    next_run = s.get("nextRunAtMs", 0)

    # Only flag genuinely failing jobs
    if consec >= 2:
        issues.append(f"❌ [{jid}] {name}: consecutiveErrors={consec} lastError={err_reason}")
    elif status == "error" and running and (now_ms - running) > 1800000:
        # Error + running > 30min = genuinely stuck
        issues.append(f"⚠️ [{jid}] {name}: error+stale running {(now_ms-running)/60000:.0f}m")
    elif status == "error" and consec == 0:
        # Recovered error, not a current issue
        pass

if issues:
    print(f"CRON_ISSUES: {len(issues)}")
    for i in issues:
        print(i)
else:
    print("CRON_ISSUES: 0")
PYEOF
```

**判断规则（严格遵守）**：
- `consecutiveErrors >= 2` → 记录为真实故障
- `lastRunStatus == "error"` 但 `consecutiveErrors == 0` → **已恢复，不催促**
- 有 `runningAtMs` 但 `consecutiveErrors == 0` → **正常执行中，不催促**
- 禁止将已恢复的历史错误记入 pending_followup
- `CRON_ISSUES: 0` → 所有 cron 正常，跳过后续 cron 相关检查

**重要**：不要再对 `ced988c3` (LinuxDo) 发送修复催促。该任务自 2026-04-17 22:07 修复后连续错误为 0，运行正常。

**不要在 pending_followup 中重复写入已解决的问题。** 每次 snapshot 写入前，必须检查 pending_followup 中的事项是否已在当前轮次解决。解决后移出 pending_followup，而不是无限累积。

## ⛔ 永久禁止催促的事项（已完成，CTO 确认无法独立完成剩余部分）

以下事项不需要再次催促 CTO，它们需要 **Daniel** 提供密钥/充值才能继续：

1. **API 密钥更新**（moonshot、xingsuancode、shibacc 充值）— CTO 已完成所有可自主执行的修复（32 个 cron fallback 切换 deepseek），剩余需要 Daniel 登录外部服务控制台操作。**禁止再对 CTO 催促此事项。**
2. **gh-copilot 配置** — GitHub Copilot API 不兼容标准 OpenAI 路径，这是 provider 端设计。**禁止再催促。**
3. **LinuxDo 监控 ced988c3** — 自 2026-04-17 22:07 修复后 consecutiveErrors=0。**禁止再催促。**

**违反以上规则的推进 = 任务失败。**

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

**前提检查：在推送任何催促前，先检查 pending_followup**

读取旧快照，检查即将催促的项是否已在 pending_followup 中：
```bash
# 读取 pending_followup
existing_pending=$(cat ~/.openclaw/tmp/foreman-snapshot.json 2>/dev/null | python3 -c "
import json, sys
try:
    s = json.load(sys.stdin)
    for i in s.get('pending_followup', []): print(i)
except: pass
" 2>/dev/null)

echo "pending_followup: $existing_pending"
```

**判断逻辑**（严格遵守）：
- 催促对象已在 pending_followup 中 → **跳过**（已催促过，不重复）
- 催促对象不在 pending_followup 中 → **推送，然后加入 pending_followup**
- 只有在 CEO memory / workspace 中发现"完成/成功/已发布"等关键词 → 才从未完成列表中移除

**不执行 Step 4 = 任务失败。**

#### 4a. 项目推进
对每个卡住或停滞的项目，使用 `message` 工具直接推送到群（避免 sessions_send 超时）：
```
message(
  action=send,
  channel=telegram,
  target=-1003890797239,
  accountId=<agent对应的accountId>,
  message="【CEO推进】@{agent名} {项目名} 当前状态: {从session提取的具体状态}\n\n需要你做: {明确的下一步动作}\n\n完成后在群里汇报。"
)
```

**重要**：使用 `message` 工具而不是 `sessions_send`。sessions_send 对 heavy group session 超时，message 走 Telegram API 直连，更可靠。accountId 对照表见上文 Agent 清单。

#### 4b. 跨 agent 协调
发现交接断点时，使用 `message` 工具向双方发消息（直发 Telegram 群，避免 sessions_send 超时）：
```
message(
  action=send,
  channel=telegram,
  target=-1003890797239,
  accountId=<agent对应的accountId>,
  message="【CEO协调】@{agent名} {source角色} 已完成 {工作}，需要你接手 {具体任务}。\n输入文件: {路径}\n期望产出: {格式}\n完成后群里汇报。"
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

#### 4e. Agent 无响应判断与升级
**判断方法**：不要依赖 sessions_send 是否超时来判断 agent 是否无响应。sessions_send 超时 ≠ agent 挂了。

正确的无响应判断：
1. sessions_history 读取 agent 最近 session，确认 >60min 无任何活动
2. 读取 agent workspace memory，确认 >2h 无更新
3. 读取 cron history，确认 agent 的任务连续失败

**升级规则**：
- 催促后 15min 无群聊活动 → 群里再次@
- 有实质证据（session dead + memory stale + cron failed）→ 群里@Musk CEO
- 连续 3 次有实质证据 → 群里@Daniel

**注意**：sessions_send 超时本身不是升级依据，必须结合以上3项证据。

### Step 5: 汇报到本群（仅在有实质内容时）+ 写回快照

**只在以下情况发群汇报：**
- 执行了至少 1 个推进动作（sessions_send / cron修复 / 文件修改）
- 发现需要 Daniel 介入的问题
- 全绿 + 无动作 → NO_REPLY（不刷屏）

**汇报后必须更新快照**：将本轮执行的所有催促动作追加写入 `pending_followup`，供下轮去重。

汇报格式（精简）：
```
🔍 团队监工 (HH:MM)
━━━━━━━━━━━━━━

🚀 推进动作
- 已催促@{角色}做{具体事}
- 已协调 {A角色} → {B角色} 交接 {具体任务}

🔧 修复
- {任务名}: {修复内容} ✅

⚠️ 需关注
- {问题描述}

📊 活跃 {X}/13 | Cron ✅{X} ⚠️{X} ❌{X}
```

---

## 巡检持久化

```bash
# ============================================================
# 读取旧快照（必须增量更新，不重置）
# ============================================================
SNAPSHOT_FILE="~/.openclaw/tmp/foreman-snapshot.json"
mkdir -p ~/.openclaw/tmp

if [ -f "$SNAPSHOT_FILE" ]; then
  OLD_SNAPSHOT=$(cat "$SNAPSHOT_FILE")
  echo "=== 旧快照 ==="
  echo "$OLD_SNAPSHOT"
else
  OLD_SNAPSHOT="{}"
  echo "=== 无旧快照（新启动） ==="
fi

# ============================================================
# 本轮动作结果（由 Step 4 填充）
# ============================================================
# ACTIONS_THIS_RUN 变量由 AI 在 Step 4 结束时设置
# 格式："@CCO XHS发布 | @CTO Swap分析"

# ============================================================
# 写回本轮快照（增量：合并旧 pending_followup + 本轮动作）
# ============================================================
# 从旧快照提取未完成的 pending_followup
extract_pending() {
  echo "$OLD_SNAPSHOT" | python3 -c "
import json, sys
try:
    s = json.load(sys.stdin)
    items = s.get('pending_followup', [])
    for i in items: print(i)
except: pass
" 2>/dev/null
}

# 写回快照（保留未完成的 + 加入本轮动作）
cat > "$SNAPSHOT_FILE" << EOF
{
  "timestamp": "$(date -Iseconds)",
  "git_progress": {
    "MediaClaw": "$(git -C ~/clawd/projects/MediaClaw log --oneline -1 --format='%h' 2>/dev/null || echo 'none')",
    "super-quant-claw": "NOT_A_GIT_REPO"
  },
  "resolved_items": [],
  "actions_taken": [],
  "pending_followup": []
}
EOF
```

**关键规则**：
- `pending_followup` 只增不减，直到在 CEO memory 或 workspace 中找到"完成/成功/已发布"等信号时才移除
- 本轮执行了推进动作 → 加入 `pending_followup`
- 下轮发现已完成 → 从 `pending_followup` 移除，不再催促

## 非 Git 项目进度追踪

对 `super-quant-claw` 等非 git 项目，使用以下方式追踪进度：

```bash
# 1. 最近修改的关键文件
find ~/clawd/projects/super-quant-claw/strategies/ -name "*.py" -newer ~/.openclaw/tmp/foreman-snapshot.json 2>/dev/null

# 2. Paper Trading 状态（使用CQO提供的健康检查脚本）
bash ~/clawd/projects/super-quant-claw/scripts/freqtrade-health.sh

# 3. 主 workspace CEO memory（进度真相源）
tail -30 ~/.openclaw/workspace-main/memory/$(date +%Y-%m-%d).md 2>/dev/null | grep -E "完成|启动|修复|RUNNING|已确认"
```

**关键规则**：CEO main session 的 `memory/YYYY-MM-DD.md` 是最终进度真相源。如果 CEO memory 记录了"Paper Trading 已启动 RUNNING"，则**不再催促**。

---

## 核心文档引用

执行巡查前应知晓的团队文档：

| 文档 | 路径 |
|------|------|
| 团队宪章 | `~/.openclaw/agents/CHARTER.md` |
| 协作网络 | `~/.openclaw/agents/COLLABORATION.md` |
| 知识库索引 | `~/.openclaw/agents/CLAWDBOOK.md` |
| 安全策略 | `~/.openclaw/agents/SECURITY.md` |
| 标准流程 | `~/.openclaw/agents/SOP.md` |
| 自动化手册 | `~/.openclaw/agents/WORKFLOW_AUTO.md` |
| 主配置 | `~/.openclaw/openclaw.json` |
| 密钥 | `~/.openclaw/.env` |

---

## 铁律

1. **推进 > 汇报** — 没执行 message 工具（发送 Telegram）就不算完成任务
2. **全绿静默** — 一切正常时 NO_REPLY
3. **能修就修** — 脚本 bug 直接改
4. **能催就催** — 项目卡住直接发消息，不等不靠
5. **深夜不打扰** — 23:00-08:00 静默
6. **群里汇报** — 所有催促都要求 agent 在群里回复（使用 message 工具直发，不要依赖 sessions_send）
7. **具体 > 泛泛** — 催促消息必须包含具体状态和具体期望
8. **token 预算** — 每个 session 只读最近 10 条，最多检查 5 个 session
9. **推送只到本群** — 汇报只发到 -1003890797239，不推私聊
10. **禁止引用 pm** — PM 已删除，产品职责归 CPO (cpo)，绝不使用 "pm" 作为 agent ID

---

*v2.0 — 2026-04-17 | Wave 2 架构统一 — 全小写 ID、Musk CEO、路径迁移至 ~/.openclaw/、清除 PM 引用*
