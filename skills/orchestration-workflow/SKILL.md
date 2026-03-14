---
name: orchestration-workflow
description: Orchestration Protocol v4.2 for coding tasks. Non-blocking event-driven architecture with persistent tmux sessions. Use when: implementing features, fixing bugs, refactoring code, building components, creating PRs, or any development work. Trigger phrases: "按协议跑", "task-card", "编排", "orchestration", "走流程", "开发", "实现", "implement", "build", "refactor", "修bug", "bugfix", "coding task". NOT for: reading code, quick questions, config changes under 15 minutes.
---


# Orchestration Workflow v4.2

> 编码任务的标准执行流程。经 20+ E2E 测试打磨，v4.x 重构为非阻塞事件驱动架构。

---

## ⚡ Quick Start

> **≤15 分钟的单文件修改？跳过本流程，直接 `codex --full-auto "修改描述"`**

### 方式 A：非阻塞模式（推荐 v4.2+）

```bash
# 1. 写任务 prompt（必须是文件，不要 CLI 参数）
cat > /tmp/tasks/my-task.md << 'EOF'
# Task: 功能描述
## Goal
...
## Requirements
1. ...
## Constraints
- Max N new files
- Must pass npm run build
EOF

# 2. 启动（非阻塞，秒回）
orchestrate-start.sh /path/to/repo my-task /tmp/tasks/my-task.md codex --yolo --deploy --skills="core frontend"

# 3. 巡逻（cron/heartbeat 每 60-90s 调一次，或手动）
orchestrate-patrol.sh my-task
# 返回 exit 0 = 还在跑，exit 10 = Gate 通过，exit 20 = Gate 失败

# 4. Worker 完成后自动触发 gate → merge → deploy → cleanup
```

### 方式 B：阻塞模式（fallback，兼容旧版）

```bash
# 一键跑（阻塞等待，直到完成）
orchestrate.sh /path/to/repo my-task /tmp/tasks/my-task.md codex --yolo --deploy --skills="core frontend"
```

### 3 个典型任务速查

| 场景 | 非阻塞命令 |
|------|------|
| **新功能**（多文件） | `orchestrate-start.sh /repo feat /tmp/tasks/feat.md codex --yolo --deploy --skills="core frontend"` |
| **修 bug** | `orchestrate-start.sh /repo bugfix /tmp/tasks/fix.md codex --yolo --skills="core debug"` |
| **远程 Worker** | `WORKER_HOST=root@vps orchestrate-start.sh /repo task /tmp/tasks/task.md codex --yolo` |

### 无超时设计（v4.0+）

**没有硬超时**。Worker 想跑多久跑多久，通过事件检测完成：
- Worker 提交了 git commit → 立即进 Gate
- Worker 写了 .task-result.json → 立即进 Gate
- Worker idle（文件 hash 连续 `IDLE_THRESHOLD=3` 轮不变，~3-4.5min）→ auto-commit
- Worker 被阻塞（问问题）→ 自动检测 + LLM 智能回答
- Worker 进程挂了 → salvage 已有代码
- `MAX_POLLS=120`（~30min）纯安全兜底，正常不触发

### 产物在哪找？

**主键统一为 `task-id`**（即 orchestrate.sh 第二个参数）。所有产物路径都包含它：

| 产物 | 路径 | 主键 |
|------|------|------|
| Worktree | `/tmp/orch-{task-id}/` | task-id |
| Prompt | `/tmp/orch-{task-id}/.task-prompt.md` | task-id |
| Worker 报告 | `/tmp/orch-{task-id}/.task-result.json` | task-id |
| Git 分支 | `feat/{task-id}` | task-id |
| 部署截图 | `$VERIFY_SHOTS_DIR` (默认 `/tmp/deploy-shots/`) | — |
| 最终代码 | repo `main` 分支 | commit msg 含 task-id |
| JSON 日志 | 标准输出（`{"phase":...}` per line） | — |
| Auto-commit 记录 | commit message: `feat: {task-id} (auto-commit by orchestrator)` | task-id |

### 脚本说明

**v4.2 非阻塞模式（推荐）：**

| 脚本 | 角色 | 直接用？ |
|------|------|----------|
| **orchestrate-start.sh** | **启动** — worktree + worker + 秒回 | ✅ 入口 |
| **orchestrate-patrol.sh** | **巡逻** — 检查一轮状态，秒回 | ✅ cron/heartbeat 调 |
| **orchestrate-gate.sh** | **Gate** — 质量检查 + merge + deploy | ❌ patrol 自动调用 |
| deploy-verify.sh | 部署 + 浏览器验证 | ❌ gate 自动调用 |
| inject-worker-skills.sh | 注入 CLAUDE.md | ❌ start 自动调用 |
| parse-worker-output.sh | 解析 tmux 输出 | ❌ patrol 自动调用 |

**阻塞模式（fallback）：**

| 脚本 | 角色 | 直接用？ |
|------|------|----------|
| **orchestrate.sh** | 阻塞版主入口 — 调度全部流程 | ✅ 兼容旧版 |
| worker-session.sh | 启停 tmux session | ❌ orchestrate.sh 调用 |

**状态文件：** `/tmp/orch-tasks/<task-id>.state`（JSON，patrol 读写）

**tmux 管理：** 本机直接 tmux 命令，远程用 persistent-ssh-tmux skill

---

## When to Use

> **⚡ ≤15 分钟单文件？→ 直接 `codex --full-auto`，不走本流程**

**必须走协议（强触发）：**
- 跨文件/跨模块的功能开发
- 新建 feature / 重构 / 数据库变更
- 任何需要 PR 的工作

**可以跳过（Quick Mode）：**
- 单文件修改 < 15 分钟
- 配置调整、文档更新
- 人工明确说"快速模式"

## Hard Rules（9 条红线）

1. ❌ 禁止直投 Worker — 所有任务先过 task-card + prompt 组装
2. ❌ 禁止单 session 多任务 — 一任务一 session 一 worktree
3. ❌ 禁止无门禁合并 — build + commit + 文件完整性 + git clean
4. ❌ 禁止 Worker 做业务决策 — 遇歧义必须停
5. ✅ 每次任务必须产出一条 learning
6. ✅ 跨文件/跨模块任务必须填写 contracts + assumption checklist（≥5 条；高风险 ≥8 条）
7. ✅ **Task Card 约束字段必须包含框架版本行为**（如 "Next.js 16 默认 Turbopack"）
8. ✅ **初始 scaffold 必须配置 .gitignore 排除 `.omc/` 和构建产物**
9. ✅ **Worker 完成后必须写 .task-result.json 并 commit，否则视为未完成**

## Workflow Steps

### Step 0: 环境验证

启动任务前，验证工具链：

```bash
# 1. 检查 Agent 可用
codex --version   # 或 claude --version
tmux -V           # tmux 需要 >= 2.0

# 2. 检查 scripts 在 PATH
which orchestrate-start.sh || echo "run: bash install.sh"

# 3. 远程模式额外检查
ssh user@host "tmux -V && codex --version"
```

> **ACP 已弃用** — v4.0+ 全部使用 tmux + codex/claude CLI，不再依赖 ACP/acpx。
> 历史 ACP 故障排查仍见 `learnings/acp-setup-debug-guide.md`

### Step 1: 填写 Task Card

使用 `templates/task-card.md` 模板，必填字段：

| 字段 | 说明 | v1.3 变更 |
|------|------|-----------|
| 目标 | 做什么 | - |
| 非目标 | 不做什么 | - |
| 相关文件 | 要改的文件路径 | - |
| 约束 | 技术约束 | **必须写框架版本行为** |
| 质量约束 | 代码质量要求 | **v1.3 新增** |
| 验收标准 | 门禁条件 | **必须包含 "commit 存在"** |
| timeout | ACP 超时秒数 | **v1.2 新增，默认 180** |
| .gitignore | 需排除的路径 | **v1.2 新增** |

**质量约束示例**（v1.3 新增，避免产出"能跑但糙"的代码）：
```
- 无硬编码常量（提取到 config/constants）
- 交互组件必须有 loading 状态
- 异步操作必须有 error boundary 或 try/catch
- 表单必须有基础验证（非空、格式）
- 公共组件必须有 JSDoc 注释
- 不使用通用占位链接（如 https://github.com/）
```

**约束字段示例**（避免 Issue #5 再现）：
```
- Next.js 16 默认 Turbopack，不使用 webpack 配置
- React 19 server components 默认，客户端需 "use client"
- 排除 .omc/ 从 git（已在 .gitignore）
```

### Step 2: Orchestrator 组装 Prompt

从 task-card 提取精确信息，**不转发人话**。Prompt 结构：

```
You are a Worker agent. Execute ONLY what is specified.

## Task: {ID} — {Title}

### Context
{框架版本 + 已有代码说明}
{关键约束，特别是框架版本行为}

### Steps
{编号步骤，最后必须是 git commit + git log}

**建议顺序**：commit 完成后再写 run report（确保 Commit 字段准确）。

### Run Report Format (MUST follow exactly)
Write `.acp-runs/{TaskID}.md` using this exact format:
```
# {TaskID} — {Title}
Status: success | failed | stopped
Commit: {hash} {message}
Build: pass | fail
Files: {list of created/modified files}
Notes: {1-3 sentences}
Errors: {if any, otherwise "None"}
```

### Dependencies
{如果 task card 有 depends_on 字段，列出}

### Constraints
{从 task-card 约束字段抄过来}
{明确写 "Exclude .omc/ from git"}

### Quality Standards (v1.6: 前置审查标准，一次做对)
{从 task-card 质量约束字段抄过来}

**代码规范（必须全部满足，否则不算完成）：**
- JSDoc on every exported function, component, type, interface
- JSDoc on every interface/type FIELD (not just the interface itself)
- Error handling: try/catch for async, fallback for unknown enum values
- Empty state: handle empty arrays, null props, missing data
- No hardcoded values (extract to constants/config)
- No `any` type, minimize `as` casts
- Accessible: aria-label on interactive elements, semantic HTML

**自检清单（commit 前必须过一遍）：**
- [ ] 每个 export 都有 JSDoc？
- [ ] 每个 interface 字段都有注释？
- [ ] 传入空数据会崩吗？
- [ ] 有没有硬编码的字符串/数字？
- [ ] aria-label 都加了吗？

**为什么：** 低质量代码需要 review + fix，实测总耗时是一次做对的 2 倍。

### Stop Conditions
{何时停止并回报}

**⚠️ 规则补充：即使触发 Stop Condition，也必须写 run report（.acp-runs）**

### Previous Attempt Context (失败重试时必加)
```
### Previous Attempt Context
T{XX} failed because: {具体错误}
Correction: {修正方案}
```

```

**Orchestrator worktree 准备清单（v1.4 新增）：**
- [ ] `git worktree add` 创建成功
- [ ] **`npm install` 已执行**（Issue #19 教训）
- [ ] 如有依赖分支，已 `git merge` 且无冲突（或已解决）
- [ ] `npm run build` 可通过（预验证）

**Prompt 组装检查清单（v1.4）：**
- [ ] 框架版本行为已写入 Context（如 Turbopack 默认）
- [ ] **Quality Standards 段已写入**（错误处理、loading、验证、JSDoc）
- [ ] 最后一步是 git commit + git log
- [ ] **run report 写在 commit 之后**
- [ ] .omc/ 排除已提及
- [ ] timeout 已设置 ≥ 安装依赖所需时间
- [ ] **npm install 在 build 前执行**（worktree 场景）

### Step 2.5: Worktree 卫生（v2.2 新增）

每次启动新任务前，清理已合并的旧 worktree：
```bash
cd $MAIN_REPO
# 清除所有非 main 的 worktree
for wt in $(git worktree list --porcelain | grep "^worktree " | grep -v "$MAIN_REPO" | sed 's/worktree //'); do
  git worktree remove "$wt" --force 2>/dev/null
done
git worktree prune
```

**为什么重要**：worktree 会无限堆积（实测 23 个后开始影响 git 操作速度）。

### Step 3: 启动 Worker（隔离执行）

```bash
# 3.1 预创建目录（ACP 不会自动创建！）
mkdir -p /path/to/worktree

# 3.2 清理旧分支（重试场景）
cd $MAIN_REPO
git worktree prune
git branch -D feat/xxx 2>/dev/null

# 3.3 创建 worktree
git worktree add /path/to/worktree -b feat/xxx

# 3.4 安装依赖（Hard Rule — 绝不跳过！）
cd /path/to/worktree && npm install

# 3.5 如果有依赖分支，先合并
git merge feat/dep-branch --no-edit  # 可能产生冲突

# 3.6 ACP spawn
sessions_spawn(
  runtime="acp",
  agentId="claude",
  task="...",
  cwd="/path/to/worktree",
  mode="run",
  runTimeoutSeconds=180  # 按 task-card timeout 字段
)
```

**⚠️ ACP 注意事项（实测验证）：**
- cwd **必须预创建**，否则报 `ACP runtime working directory does not exist`
- `sessions_history` 对 ACP session **始终返回空** — 不要用它监控进度
- 用 `git status` + `git log` 检查 worktree 变化来判断 Worker 进度
- Worker 完成后检查 gateway log: `grep "Result:" /tmp/openclaw/openclaw-*.log | tail -1`

### ACP 超时防护策略（v1.5 新增，解决 Issue #21）

**问题：** ACP Worker 被 kill 时无 cleanup 机会，静默退出无 report。

**策略 1：Soft Deadline（Prompt 内嵌，v1.6 修正）**
⚠️ 实测发现：强制时间压力会降低注释覆盖率（51%→0%）和防御性编程。
改为 **warning 模式**，不牺牲质量：
```
### Execution Priority
Quality > Speed > Completeness.
- Do it RIGHT the first time. Fixing later costs 2x.
- Run your self-check before commit (see Quality Standards checklist above)
- If timeout is near: commit what you have (Status: partial), but do NOT skip quality on completed files
- Write run report ONCE, AFTER commit (do not write placeholder reports)
```

**策略 2：Orchestrator Watchdog（推荐）**
Worker 派出后，Orchestrator 定期检查：
```bash
# 每 30s 检查一次 worktree
git -C /path/to/worktree status --short
git -C /path/to/worktree log -1 --oneline
```
如果 Worker 消失（acpx 进程没了）且没 commit：
1. 检查 `git diff` 看有没有有用的改动
2. 如果有 → Orchestrator 自己 commit + 写 report（Status: salvaged）
3. 如果没有 → 记录 timeout failure + 重试

**策略 3：任务拆分规则**
防止单个任务过大导致超时：
- **最多 3 个新文件** / 每个 task
- **最多 2 个修改文件** / 每个 task
- 如果需求超出 → 拆成多个 task
- timeout 公式：`基础 60s + 每个文件 30s + npm install 60s`

**推荐组合：策略 1 + 策略 2 + 策略 3**

### ACP 运行日志中转规范（新增）
由于 ACP session history 缺失，**必须用文档作为中转历史**：

- **统一存放，不按项目分目录**（高复用、易检索）
- 按日期分桶：`acp-runs/YYYY-MM-DD/`
- 单次任务一份日志：`run-<sessionKeySlug>-<taskId>.md`
- 日志必须包含 `Project` 字段（用于筛选）

**⚠️ 写入路径约束（更新）**
- 之前“写 vault 失败”实为 **Claude Code OAuth 过期**导致 ACP 全部失败
- 正常情况下 Worker 可以先写 repo 内 `.acp-runs/<taskId>.md`
- 是否同步到 vault 为 **可选归档层**（视需求）

**模板字段（最小集）：**
```
Project:
Task:
SessionKey:
RunId:
Repo/CWD:
Start/End:
Status: success | failed
Build/Test:
Files touched:
Commit:
Output summary:
Errors:
```

**Task Card 必须加一条硬约束：**
1) Worker 写入 repo 内 `.acp-runs/<taskId>.md`

**可选：** 若需归档，再拷贝到 vault：`acp-runs/YYYY-MM-DD/run-<sessionKeySlug>-<taskId>.md`
**Inspector 默认读 repo 内 run log**（归档只用于长期沉淀）。

### Step 4: Inspector 巡检

**v1.2 改用文件系统检查**（sessions_history 对 ACP 不可用）：

```bash
# 每 30-60 秒检查一次
cd /path/to/worktree

# 1. 有新文件吗？
git status --short

# 2. 有 commit 吗？
git log --oneline -1

# 3. Worker 进程还在吗？
ps aux | grep acpx | grep -v grep

# 4. build 锁？（说明 Worker 还在 build）
ls .next/lock 2>/dev/null && echo "build 中..."
```

### Step 5: 门禁检查

**必检项（v1.2 更新）：**

| # | 检查项 | 命令 | 说明 |
|---|--------|------|------|
| 1 | build 通过 | `npm run build` | 若报 `next: command not found`，先 `npm install` |
| 2 | commit 存在 | `git log --oneline -1` | 必须有新 commit |
| 3 | 文件完整 | `ls <expected files>` | 对照 task-card |
| 4 | git 干净 | `git status --short` | 排除 .omc 后应为空 |
| 5 | 不破坏已有 | `grep <preserved items>` | 验证旧路由/组件还在 |
| 6 | .omc 未被 commit | `git show --stat HEAD` | 不应包含 .omc |
| 7 | **代码质量** | `grep -r "hardcode\|TODO\|FIXME"` | 检查硬编码/占位符 |
| 8 | **run report 存在** | `cat .acp-runs/<taskId>.md` | Hard Rule #9 |
| 9 | **部署后浏览器验证** | 截图 + console errors | Build pass ≠ 运行时正确 (Issue #26) |

**⚠️ 重要：`npm run build` 只验证 TypeScript 编译。运行时资源加载、CSS 层叠、第三方 SDK 初始化等问题只能在浏览器里发现。合并 main 后必须部署 + 截图验证。**

**门禁未通过 → Step 6 失败处理**

### Step 5.5: Inspector 代码审查（v1.6 新增）

门禁通过后，可选派一个 **Inspector Worker** 审查代码质量：

```
You are an Inspector agent. Review the code changes and report issues.

## Task: Review T{XX}

### What to check
1. Read all changed files: {file list}
2. Check: JSDoc on all public functions/components?
3. Check: Error handling / empty state handling?
4. Check: No hardcoded values (should be in config/constants)?
5. Check: Type safety (no `any`, no `as` casts)?
6. Check: Accessibility (aria-labels, semantic HTML)?

### Output
Write .acp-runs/T{XX}-review.md:
```
# T{XX} Review
Score: {1-10}
Issues:
- {issue 1}
- {issue 2}
Verdict: pass | needs-fix
```

If verdict=needs-fix, Orchestrator spawns fix task with review as context.
```

**何时用 Inspector：**
- 重要/复杂任务（≥3 个文件）
- 合并到 main 前
- 代码质量评分低时

**何时跳过：**
- 简单任务（1 文件、<50 行）
- 重试任务（已经审过一次）

### 共享文件冲突预防（v1.6 新增）

**问题：** `app/layout.tsx` 被 5 个 branch 修改，合并时产生 4 次冲突。

**策略：**
1. **标记共享文件**：task card 新增 `shared_files` 字段
2. **串行化共享文件修改**：改同一文件的任务不并行
3. **Layout 修改集中化**：多个 feature 需要改 layout 时，最后统一做一个 "wire-up" task
4. **Prompt 约束**："Do NOT modify app/layout.tsx. Create your component only."

**推荐流程：**
```
T1: Create component A (不改 layout) ← 可并行
T2: Create component B (不改 layout) ← 可并行
T3: Wire A + B into layout (专门改 layout) ← 串行，最后做
```

### Step 6: 失败处理

```
重试策略：
1. 分析失败原因（build error? 文件缺失? 超时?）
2. 在原 prompt 基础上追加失败上下文：
   "The previous Worker created X but build failed because Y. Fix Z."
3. 同一 worktree 重新 spawn（不清空文件，在已有代码上修）
4. 最多 3 次重试，超过则回报 Human

失败模式速查表（来自实测）：
| 失败 | 原因 | 修复 |
|------|------|------|
| Turbopack 冲突 | webpack config + Next.js 16 | 去掉 webpack，用替代方案 |
| Worker 未 commit | build 失败后停了 | 带上下文重试 |
| .omc 被 commit | 没有 .gitignore | 初始 scaffold 加 .gitignore |
| build lock | 上次 build 没清理 | rm .next/lock |
| npm install 超时 | timeout 太短 | 加到 300s |
| next: command not found | worktree 无 node_modules | 先 npm install 再 build |
```

## Debug Workflow（v1.8 新增）

### Debug Task Card 模板

```markdown
## Task: T{XX} — Debug: {症状简述}

### Bug Report（Orchestrator 必填，缺一不可）
- **页面/路由**: {url}
- **复现步骤**: {1. 打开页面 2. ...}
- **现象**: {截图描述 + error message}
- **Console Stack**: {完整 stack trace，没有就写 "unavailable"}
- **疑似组件**: {根据 stack/路由推测的 1-3 个文件}

### Steps
1. Read suspected files: {file list}
2. Identify root cause
3. Fix the bug
4. npm run build
5. Verify: manually check the fix logic is sound
6. git add -A && git commit -m "fix: {描述}"
7. Write .acp-runs/T{XX}-debug.md AFTER commit

### Debug Run Report Format
` ` `
# T{XX} — Debug: {症状}
Status: success | failed
Root Cause: {一句话}
Fix: {改了什么}
Commit: {hash} {message}
Build: pass | fail
Files: {list}
Prevention: {如何避免再发生}
Errors: {if any}
` ` `

### Quality Standards
- Fix 必须包含防御性处理（不只是修当前 bug）
- 如果是类型问题：加 type guard / fallback
- 如果是缺资源：加 error boundary / loading fallback
- 新增的防御代码必须有 JSDoc 注释

### Stop Conditions
- Console stack unavailable AND cannot reproduce → stop, report "insufficient info"
- Bug in third-party library (not our code) → stop, report workaround suggestion
- Fix requires architecture change → stop, escalate to Orchestrator
```

### Smoke Test Macro（Orchestrator 用）

合并到 main 后，跑 5 页面快速检查：
```bash
# Smoke test — 检查所有主要路由
for route in "/" "/explore" "/search" "/map" "/profile"; do
  status=$(curl -s -o /dev/null -w "%{http_code}" "https://{domain}${route}")
  echo "${route}: ${status}"
done
```
如果有 500 → 自动生成 Debug Task Card。
客户端 JS 错误需要 Camoufox 截图 + console 检查。

### ErrorBoundary 标准（v1.8 强制）

项目必须有统一的 ErrorBoundary，要求：
1. error.message 完整显示（不是 `[object Object]`）
2. dev 环境显示 stack trace
3. prod 环境显示友好提示 + error code
4. 提供 "Try Again" / "Go Home" 操作
5. 捕获错误时 console.error 完整 stack

## Debug Workflow（v1.8 新增）

### Debug Task Card 模板

与 feature task 不同，debug task 需要**先收集信息再派任务**。

```
## Task: T{XX} — Debug: {bug title}

### Bug Report
- **Page/Route**: {URL or route}
- **Repro Steps**: {1. 打开页面 2. 点击… 3. 出现错误}
- **Observed**: {截图 + error message + console stack}
- **Expected**: {正常行为}
- **Suspected Files**: {基于 stack trace 缩小范围}
- **Confidence**: high | medium | low（Orchestrator 对 root cause 的把握程度）

### Steps
1. **If Confidence ≤ medium**: First read suspected files and verify root cause matches. If not, STOP and report actual findings.
2. Read suspected files (if Confidence = high, skip verification)
2. Identify root cause
3. Fix the bug
4. npm run build
5. Verify: the fix resolves the error (describe how)
6. git add -A && git commit -m "fix: {description}"
7. Write .acp-runs/T{XX}-debug.md AFTER commit

### Debug Run Report Format
# T{XX} — Debug: {title}
Status: success | failed
Root Cause: {1-2 sentences}
Fix: {what was changed and why}
Commit: {hash} {message}
Build: pass | fail
Files: {list}
Regression Risk: low | medium | high — {why}
Errors: {if any}
```

### Debug 前置条件（Orchestrator 必须完成）

**必须先做，不能跳过：**
1. **截图** — 到页面截一张错误状态
2. **Console stack** — 用浏览器或 `console.error` 拿到完整 stack trace
3. **缩小范围** — 基于 stack 确定 Suspected Files（最多 3 个）

**没有 stack / 没有 repro → 不能派 debug task**，先自己排查。

### Smoke Test Macro（Orchestrator 用）

部署后跑一遍，5 分钟内发现大问题：
```bash
PAGES="/ /explore /search /map /profile"
for page in $PAGES; do
  # HTTP 状态
  curl -s -o /dev/null -w "$page: %{http_code}\n" https://{domain}$page
done
# 然后 Camoufox 逐个截图检查客户端渲染
```

### ErrorBoundary 标准（v1.8 要求）

Worker 写 ErrorBoundary 时必须：
1. **error.message 兜底** — `String(error)` 而非直接渲染 error 对象
2. **Dev 模式显示 stack** — `process.env.NODE_ENV === 'development'` 时展示
3. **error 对象类型化** — `componentDidCatch(error: Error)` 不能是 unknown

**反面教材（Issue #24）：**
- 浏览器 dev overlay 显示 `[object Object]` → 因为 Cesium 抛的不是 Error 实例
- 我们的 ErrorBoundary 没有 catch 到（因为是在 `/explore` 而非 `/map` 触发时没包 boundary）

### 一致性检查（Issue #23）

每个含异步/第三方组件的页面必须包 ErrorBoundary：
```
app/explore/page.tsx → 用了 CesiumMap → ❌ 没包 ErrorBoundary
app/map/page.tsx     → 用了 CesiumMap → ✅ 包了 ErrorBoundary
```
**规则**：如果用了 dynamic import 或第三方 SDK → 必须包 ErrorBoundary + Suspense。

## Escalation（停止条件）

Worker 遇到以下情况 **必须停并回 Orchestrator**：
- 需求歧义
- 找不到关键文件/类型定义
- 需要修改禁改文件
- 测试路径不明确
- contracts 中上游输出格式不匹配

## 执行模式选择（v2.1 核心：灵活变通，各取所长）

**原则：Orchestrator 不是只会派活的调度器，也不是什么都自己干的独行侠。根据任务性质选最合适的执行方式。**

### 各角色能力矩阵
| 能力 | Orchestrator (Minerva) | ACP Worker (Codex/Claude) |
|------|----------------------|--------------------------|
| 写长代码/新组件 | ⚠️ 一般 | ✅ 强 |
| 调试 + 诊断 | ✅ 强（有浏览器截图） | ⚠️ 弱（无运行时视角） |
| 写反馈/指导 | ✅ 强（基于实际观察） | ❌ 无法自评 |
| 部署验证 | ✅ 强（Vercel + 浏览器） | ❌ 无权限 |
| 联网检索 | ✅ 强（web_search + fetch） | ❌ 无网络 |
| 多文件重构 | ⚠️ 繁琐 | ✅ 强（全局视角） |
| 精准小改 | ✅ 快（30 秒 Quick Fix） | ⚠️ 慢（2-3 分钟 ACP 开销） |

**核心思想：用 Orchestrator 的感知能力 + Worker 的生产能力 = 1+1 > 2**

### 决策树
```
任务来了
  ├── 我完全理解改动 + 无需探索？
  │     ├── YES → Mode 1: Orchestrator 直接改（Quick Fix）
  │     └── NO ↓
  ├── 需要多轮迭代 / 实时观察 / 中途可能改方向？
  │     ├── YES → Mode 7: 终端会话（tmux/zellij）
  │     └── NO ↓
  ├── 需要创建多个新文件 / 架构设计？
  │     ├── YES → Mode 2: ACP Worker（完整 task card）
  │     │         └── 任务复杂/耗时？→ Mode 6: 异步轮询（timeout=0）
  │     └── NO ↓
  ├── 需要在已有代码上调试 / 不确定 root cause？
  │     ├── YES → Mode 5: Orchestrator 诊断 → 判断：
  │     │         ├── Confidence high → Quick Fix 或精准 ACP
  │     │         └── Confidence low → Mode 7 终端会话（边看边修）
  │     └── NO ↓
  └── 并行独立任务？
        ├── YES → Mode 4: 多个 ACP Worker 同时跑
        └── NO → Mode 2: 单个 ACP Worker
```

### Mode Selection Protocol（v2.5 — 信号驱动 + 中途切换）

决策树不能靠直觉选。每个 Mode 有**硬性入口信号**（必须满足），选错了有**逃生路径**（不卡死）。

**一、入口信号（AND/OR 条件）**

| Mode | 入口条件（全部满足才用） | 排除条件（任一满足就不用） |
|------|------------------------|--------------------------|
| 1 Quick Fix | 能说出改哪个文件哪几行 + ≤3 文件 + 不需运行确认 | 任何一条说不出 |
| 2 ACP | Task card 能写完整 + Worker 不需问问题 + 有验收标准 | 写 card 时发现"不确定怎么描述" |
| 7 终端会话 | 至少一条：需看 Worker 思考 / 可能改方向 / confidence < high / 同类 ACP 曾失败 | — |

**快速判定法**：写 task card，5 秒内写不出完整 Steps → 任务不够明确 → Mode 7

**二、中途逃生路径（选错了不卡死）**

```
Quick Fix 改不动（发现要改 >3 文件 / 需要运行确认）
  → 立刻停手 → 开 ACP task card 或 Mode 7

ACP Worker 异常（watchdog 30s 无 file change / git status 空 / 走偏）
  → 读 git status 判断：
    ├── 有产出但方向错 → kill → 开 Mode 7 接手（保留已有 diff）
    └── 完全没产出 → kill → 换 agent / 换 Mode / 重写 task card

Mode 7 Worker 自己搞定了
  → 不追加指令 → 等 commit → 走正常 gate 门禁

Mode 7 发现任务其实很明确
  → 不需要继续多轮 → 等本轮完成 → 下次同类任务用 ACP
```

**三、历史匹配（自动优化选择）**

每次任务完成后，run report 里记录了 `Mode` + `Result`。下次同类任务：
- 上次 Mode 2 成功 → 继续 Mode 2
- 上次 Mode 2 失败/超时 → 升级到 Mode 7
- 上次 Mode 7 Worker 一轮搞定 → 降级到 Mode 2（效率更高）

**规则：先查历史，再套决策树。**

### Mode 1: Orchestrator 直接改（Quick Fix）
**适合**：bug 已定位、改动明确、无需探索
**流程**：Edit → build → commit → 部署验证
**例子**：修一个 CSS 属性、加一行 import、改一个常量值、修 API 匹配逻辑

### Mode 2: ACP Worker（标准流程）
**适合**：需要创建新文件、涉及多文件联动、需要设计思考
**流程**：Task Card → spawn → 监控 → 门禁 → 合并
**例子**：新组件、新页面、新 API 路由、跨文件重构

### Mode 3: ACP Worker + Inspector
**适合**：重要/复杂任务、合并到 main 前
**流程**：Task Card → spawn → 门禁 → Inspector review → 修复（如需）→ 合并

### Mode 4: 并行 Workers
**适合**：2+ 独立任务、不改同一文件
**流程**：多个 Task Card → 同时 spawn → 逐个门禁 → wire-up 任务合并

### Mode 5: Orchestrator 诊断 + Worker 修复
**适合**：debug 类任务，Orchestrator 有浏览器但 Worker 没有
**流程**：截图 + console stack → 分析 root cause → 判断 Confidence
  - high → Quick Fix 或精准 Task Card
  - low → Worker 先验证 root cause 再修

### Mode 7: 终端会话（v2.4 新增 — 实时上下文 + 多轮对话）
**适合**：需要多轮迭代、实时干预、debug 循环、不确定一次能做完
**核心思想**：用 tmux/zellij 开持久会话，Orchestrator 随时看 Worker 在干嘛、随时追加指令

**与 ACP 互补关系**：
| | ACP (Mode 2/6) | Terminal Session (Mode 7) |
|---|---|---|
| 通信方式 | 结构化 task card | 自然语言多轮对话 |
| 上下文 | ❌ sessions_history 空 | ✅ 实时 capture-pane |
| 多轮对话 | ❌ one-shot | ✅ 持续发指令 |
| 干预能力 | ❌ 只能 kill | ✅ 随时纠正方向 |
| 质量管控 | ✅ gate 门禁 | ⚠️ 需手动检查 |
| 并行 | ✅ 多 Worker | ✅ 多 session |
| 结构化输出 | ✅ run report | ⚠️ 需解析 TUI |

**何时选 Mode 7 而非 ACP**：
- 需要看 Worker 思考过程（debug 时特别有用）
- 任务需要多轮迭代（"先做 A，看看效果，再调 B"）
- 需要中途纠正方向（"不对，换个方案"）
- Claude Code OAuth 过期时用 Codex 交互模式

**流程**：
```bash
# 1. 启动 Worker 会话（自动检测 tmux/zellij）
./scripts/worker-session.sh start task-42 /tmp/worktree codex "实现搜索自动补全"

# 2. 读取实时输出
./scripts/worker-session.sh read task-42 30

# 3. 追加指令（多轮对话）
./scripts/worker-session.sh send task-42 "用 debounce 优化一下，300ms 延迟"

# 4. 看状态
./scripts/worker-session.sh status task-42

# 5. 完成后关闭
./scripts/worker-session.sh stop task-42
```

**环境变量**：
- `WORKER_MUX=tmux` 或 `WORKER_MUX=zellij` — 强制指定（默认自动检测）

**最佳实践**：
- 给 session 命名用 task ID（如 `task-42`），方便追踪
- 定期 `read` 检查进度，发现走偏立即 `send` 纠正
- Worker 完成后仍需走 gate 门禁（build + commit + 验证）
- Mode 7 产出同样要写 run report（由 Orchestrator 补写）

### Mode 6: 异步轮询（v2.3 新增 — 无 timeout 持久模式）
**适合**：复杂/耗时任务、不确定所需时间、不想被 timeout 中断
**核心思想**：像 tmux/zellij 一样——启动后离开，隔一会回来看结果

**流程**：
```
1. sessions_spawn(runTimeoutSeconds=0)  # 不设 timeout
2. Orchestrator 去做别的事（并行准备下一个 task / 清理 / 检查其他项目）
3. 每 60s 轮询一次 worktree:
   - git log -1 --oneline  → 有新 commit = Worker 完成
   - git status             → 有 modified files = Worker 还在干
   - ps aux | grep acpx     → 进程存在 = 还活着
   - 都没变化 > 5min        → 可能卡住，发 sessions_send 探活
4. 检测到 commit → 进入 gate 验收
```

**优势**：
- 不会半途 kill（Issue #21 彻底解决）
- 质量不受时间压力影响
- Orchestrator 不阻塞，可并行工作

**监控脚本模板**：
```bash
WORKTREE="/tmp/flyme-xxx"
LAST_COMMIT=$(cd $WORKTREE && git log -1 --format=%H 2>/dev/null)
while true; do
  sleep 60
  CURRENT=$(cd $WORKTREE && git log -1 --format=%H 2>/dev/null)
  if [ "$CURRENT" != "$LAST_COMMIT" ]; then
    echo "Worker committed! Entering gate check..."
    break
  fi
  ACPX_COUNT=$(ps aux | grep acpx | grep -v grep | wc -l)
  if [ "$ACPX_COUNT" -eq 0 ]; then
    echo "Worker exited without commit — check for errors"
    break
  fi
done
```

### Quick Mode（人工触发）
当 Arslan 说"快速模式"或任务明显 < 15 分钟时：
- 跳过 task-card、contracts、assumption checklist
- 直接执行，但仍需 build 通过 + commit
- 完成后补一条 learning

## 并行 Worker（v1.3 验证通过）

多个独立任务可同时派发：
```
# 同时 spawn 多个 Worker（不同 worktree）
sessions_spawn(agentId="codex", cwd="/tmp/proj-nav", task="...")
sessions_spawn(agentId="codex", cwd="/tmp/proj-api", task="...")
```

**前提条件：**
- 每个 Worker 有独立 worktree（Hard Rule #2）
- 每个 worktree 已 `npm install`
- 任务之间无依赖（不改同一文件）

**Worktree 创建防呆（v1.8 追加）：**
worktree 残留 + branch 残留会导致连续失败。统一用这个流程：
```bash
cd /path/to/main/repo
git worktree prune                          # 清理残留注册
rm -rf /tmp/proj-xxx 2>/dev/null            # 清理残留目录
git branch -D feat/xxx 2>/dev/null          # 清理残留 branch
git worktree add /tmp/proj-xxx -b feat/xxx  # 创建
cd /tmp/proj-xxx && npm install             # 安装依赖
```
**顺序不能变**：prune → rm → branch -D → add。

**监控方式：**
- `ps aux | grep acpx | wc -l`（每 2 进程 = 1 Worker）
- 轮询各 worktree 的 `git log -1`

## ACP 降级方案

如果 ACP 不可用（gateway 挂了、acpx 故障等），降级到 PTY 模式：

```bash
exec(
  command="cd /path/to/worktree && claude -p 'Your task prompt here'",
  pty=true,
  timeout=300
)
```

PTY 模式的区别：
- 可以直接看输出（不需要查 gateway log）
- 但不能并行（ACP 可以并行多个 Worker）
- 超时控制不如 ACP 精确

## 已知限制 & 排错

详见 `learnings/orchestration-acp-test-log.md` 和 `learnings/acp-setup-debug-guide.md`

**Top 3 坑（实测）：**
1. **Gateway service 路径不一致** — `openclaw gateway status | grep Command` 确认
2. **ACP cwd 必须预创建** — spawn 前 `mkdir -p`
3. **sessions_history 对 ACP 永远为空** — 用 git status 监控

## Project Type Support (v3.6)

The workflow is **project-type-agnostic**. Set `VERIFY_MODE` to match your project:

| Mode | Auto-detect | What it does | Projects |
|------|-------------|-------------|----------|
| `browser` | `.vercel/` or `vercel.json` | Vercel deploy + HTTP check + actionbook DOM/screenshot | Next.js, React, Vue, static sites |
| `api` | `Dockerfile` or `docker-compose.yml` | `npm test` + curl health check (`API_HEALTH_URL`) | Express, FastAPI, Go APIs |
| `test` | fallback | `npm test` only, no deploy | Libraries, CLI tools, packages |
| `none` | — | Skip verification | Infra, scripts, docs |

```bash
# Web app (auto-detected)
orchestrate.sh /tmp/flyme-new task prompt.md codex --yolo --deploy

# API backend
VERIFY_MODE=api API_HEALTH_URL=http://localhost:3000/health \
  orchestrate.sh /tmp/my-api task prompt.md codex --yolo --deploy

# Library (test only)
VERIFY_MODE=test orchestrate.sh /tmp/my-lib task prompt.md codex --yolo --deploy

# CLI tool (no verify)
VERIFY_MODE=none orchestrate.sh /tmp/my-cli task prompt.md codex --yolo
```

### Gate: Env Var Detection (v3.6)
Gate automatically scans for new `process.env.*` references in the diff.
If found, logs `env_var_warning` with the variable names — Orchestrator should
verify these are configured in the deployment environment before merging.

### Console Error Check (v3.6)
Browser verification now checks console errors after visiting all pages.
Known benign errors (Cesium skybox, favicon) are filtered. Critical errors
are reported in the output as `console_check` phase.

## Phase Roadmap

- **Phase 1（当前 v1.2）**: Skill 自动匹配 + AGENTS.md 兜底，ACP dispatch
- **Phase 2**: `command:new` hook 强制切流
- **Phase 3**: Lobster YAML 确定性 pipeline

## Changelog

### v1.8 (2026-03-03) — Debug Workflow + Smoke Test + ErrorBoundary 标准
- **新增**: Debug Task Card 模板（Bug Report 段必填：stack + 截图 + 疑似组件）
- **新增**: Debug Run Report 格式（含 Root Cause / Prevention 字段）
- **新增**: Smoke Test Macro（合并后 5 页面快速检查）
- **新增**: ErrorBoundary 标准（5 项要求，禁止 [object Object]）
- **新增**: Debug Stop Conditions（no stack + no repro → stop）
- **触发**: /explore 和 /map 的 [object Object] 错误暴露了信息不足问题

### v2.9 (2026-03-04) — 远程 SSH Worker + persistent-ssh-tmux 整合
- **WORKER_HOST=user@host**: worker-session.sh 透明支持本地/远程
- 远程模式使用 `persistent-ssh-tmux` skill（marker 机制 + shell 自动检测 + keepalive）
- 统一 API: start/send/read/status/stop/list — 本地远程同一接口
- Grumio VPS 验证: Codex 远程执行 + 结构化 JSON 反馈 + commit
- **ACP 最后优势（远程派活）被彻底替代**

### v2.8 (2026-03-04) — Prompt 文件化（零 CLI 参数传递）
- `orchestrate.sh` 第三个参数改为 `<prompt-file>`（.md 文件路径）
- Prompt 内容从头到尾不经过 shell 参数传递
- 来源: Arslan "把 prompt 藏文档里，让 agent 读文档"

### v2.7 (2026-03-04) — One-Command Orchestration (`orchestrate.sh`)
- **`orchestrate.sh`**: 一条命令跑全链路 — worktree → worker → poll → gate → merge → deploy → cleanup
- **用法**: `orchestrate.sh <repo> <task-id> <prompt> [agent] [--yolo] [--deploy] [--no-cleanup]`
- **auto-approve**: Parser 检测到 `waiting_input` 时自动发送 `p` 放行
- **两层完成检测**: `.task-result.json`（首选）→ `git commit`（fallback）
- **来源**: "还有什么优化的" — 把 10 步手动操作合并为 1 条命令

### v2.6 (2026-03-04) — 结构化 I/O 协议 + YOLO 模式
- **.task-prompt.md → .task-result.json**：文件协议，Worker 写 JSON 结果，Orchestrator 读 JSON 做 gate
- **WORKER_YOLO=1**：`--dangerously-bypass-approvals-and-sandbox`，零权限提示（仅限本地）
- **watchdog 升级**：检测 `.task-result.json` 作为首选完成信号
- **自动化 gate**：从 JSON 读 status + build_pass + commit → 自动判定通过/失败
- **来源**：Arslan "怎么拿到结构化反馈" + "YOLO 权限"

### v2.5 (2026-03-04) — Mode Selection Protocol（信号驱动 + 逃生路径）
- **入口信号表**: 每个 Mode 有硬性 AND/OR 条件，不靠直觉
- **快速判定法**: task card 5s 写不出完整 Steps → Mode 7
- **逃生路径**: Quick Fix 改不动 → ACP/Mode 7; ACP 超时 → Mode 7; Mode 7 太简单 → 降级 ACP
- **历史匹配**: run report 积累数据，同类任务自动推荐 Mode
- **来源**: Arslan 追问"切换怎么保证灵活精准"

### v2.4 (2026-03-04) — Mode 7 终端会话 + ACP/tmux 互补架构
- **Mode 7**: tmux/zellij 持久会话，实时上下文 + 多轮对话 + 可干预
- **worker-session.sh**: 统一抽象层，自动检测 tmux/zellij，JSON 输出
- **决策树升级**: 加入 Mode 7 节点（多轮迭代/实时观察/中途改方向）
- **ACP + 终端会话互补矩阵**: 明确各自优劣和适用场景
- **来源**: Arslan 指出 "tmux 和 ACP 可以互补，不要写死一种"

### v2.3 (2026-03-04) — 异步轮询模式（无 timeout 持久会话）
- **Mode 6**: `runTimeoutSeconds=0` + 异步 git 轮询，彻底解决 timeout kill 问题
- **实测验证**: `runTimeoutSeconds=0` 被 OpenClaw 接受，Worker 完成后自然退出
- **监控脚本模板**: 60s 轮询 git log + acpx 进程检测
- **并行工作**: Orchestrator 不再阻塞等待，可同时准备下一个 task
- **来源**: Arslan 提出"像 tmux 一样，启动后隔一会回来看"

### v2.2 (2026-03-03) — Worktree 卫生 + 摩擦点修复
- **Worktree 清理机制**: 每次新任务前清理已合并 worktree（实测 23 个堆积）
- **Step 2.5**: 新增 worktree 卫生步骤
- **发现的摩擦点**:
  1. worktree 堆积无上限 → 已修复（自动清理）
  2. npm install 每次 worktree 都要跑 (~20s) → 已知限制，无法避免
  3. task 编号手动管理 → 低优先级，目前可接受
  4. Worker 等待期 idle → 可并行准备下一个 task

### v2.1 (2026-03-03) — 灵活变通：执行模式决策树
- **核心变更**: 把"什么时候自己做 vs 什么时候派 Worker"写成决策树
- **5 种模式**: Quick Fix / ACP Worker / Worker+Inspector / 并行 / 诊断+修复
- **Quick Fix 标准放宽**: 从"≤3 行"改为"Orchestrator 完全理解改动 + 无需探索"
- **来源**: Arslan 指出 "灵活变通，skill 里应该也带这种思想"

### v2.0 (2026-03-03) — 完整 Debug 循环反思 + Quick Fix + 置信度
**5 个核心不丝滑点（实测发现）：**
1. Worker 无法做运行时验证 → 门禁加"部署后浏览器验证"（Orchestrator 职责）
2. Orchestrator 诊断错 → Worker fix 也错 → Debug Card 加 `Confidence` 字段
3. 1-3 行 fix 走 ACP 太重 → 新增 Quick Fix 判断标准
4. 每次部署验证 50s+ → 优先本地 dev 验证（受限于 sandbox 不能 localhost）
5. Console error 只有 Orchestrator 能抓 → Debug Card 必须贴完整 stack

**新增规则：**
- Debug Task Card 的 Root Cause 必须标注 `Confidence: high/medium/low`
- Confidence=low 时，Worker 步骤 1 改为"先读代码确认 root cause，不符则 STOP"
- **Quick Fix 标准**: Orchestrator 已完全定位 + ≤3 行改动 + 无副作用 → 直接改，不走 ACP
- 部署验证流程: build → deploy → 截图 → console errors → 确认无误 → 才算完成

### v1.9 (2026-03-03) — "Build Pass ≠ 运行时正确" + 部署验证
- **Issue #26**: build pass 但线上有运行时 bug → 强制浏览器验证
- **Issue #27**: Orchestrator 先诊断 root cause 再派 Worker
- **Issue #28**: CSS 层叠/z-index 问题 build 检测不到 → Smoke Test 截图必须做
- **新增**: 部署后验证步骤（Orchestrator 用浏览器截图，不能只信 build/HTTP 200）
- **新增**: 失败模式速查表追加 "runtime resource loading" 类别

### v1.8 (2026-03-03) — Debug Workflow + Smoke Test + ErrorBoundary 标准
- **新增**: Debug Task Card 模板（含 Root Cause / Regression Risk 字段）
- **新增**: Debug 前置条件（截图 + console stack + 缩小范围，缺一不可）
- **新增**: Smoke Test Macro（部署后快速检查 5 个页面）
- **新增**: ErrorBoundary 标准（error.message 兜底 + dev stack + 类型化）
- **新增**: 一致性检查规则（dynamic import → 必须 ErrorBoundary + Suspense）
- **Issue #23**: /explore 没包 ErrorBoundary 而 /map 包了 → 不一致
- **Issue #24**: 浏览器 error overlay 显示 [object Object] → Cesium 抛非 Error 实例

### v1.7 (2026-03-03) — "一次做对"策略 + 前置审查标准
- **核心变更**: 把 Inspector 审查标准内嵌到 Worker prompt（自检清单）
- **数据支撑**: 低质量+修复=15min/3功能, 高质量一次过=8min/3功能
- **删除**: 时间压力措辞，改为 "Quality > Speed > Completeness"
- **新增**: 5 项自检清单（commit 前必过）
- **新增**: 字段级 JSDoc 要求（不只是接口级）
- **新增**: unknown enum fallback 要求

### v1.6 (2026-03-03) — Quality > Speed + Inspector + 共享文件策略
- **修复**: Soft Deadline 改为 warning 模式（不牺牲 JSDoc/错误处理）
- **修复 Issue #22**: run report 只写一次，commit 后写
- **新增**: Inspector 角色模板（代码审查 task）
- **新增**: 共享文件冲突预防策略

### v1.5 (2026-03-03) — Orchestrator 防呆 + 模糊需求禁止 + 冲突解决
- **修复 Issue #19**: Orchestrator worktree 准备清单（npm install 强制）
- **修复 Issue #20**: Task card 禁止模糊步骤（"make it better" 无效）
- **新增**: worktree 准备步骤含依赖分支合并
- **新增**: Conflict Resolver 角色模板
- **发现 Issue #21**: ACP 超时静默退出（无法修，需上游支持）

### v1.4 (2026-03-03) — Run Report 格式统一 + 依赖追踪 + 失败重试
- **修复 Issue #15**: Run report 格式内联到 Prompt（不引用外部模板）
- **修复 Issue #16**: Task Card 新增 `depends_on` 字段 + 合并策略说明
- **修复 Issue #17**: 依赖追踪 — Worker 知道前置任务
- **新增**: "Previous Attempt Context" 段用于失败重试
- **新增**: Stop Condition 必须写具体场景（Issue #18）
- **新增**: 并行 Worker 章节（验证通过）
- **新增**: 合并前 worktree 准备步骤（merge 依赖分支）

### v1.3 (2026-03-03) — 代码质量 + 工作流防呆
- **新增**: Task Card "质量约束"字段（硬编码/loading/error/验证/JSDoc）
- **新增**: Prompt 模板 "Quality Standards" 段
- **新增**: 门禁项 #7 代码质量检查 + #8 run report 检查
- **新增**: Prompt 检查清单 3 项（Quality Standards/run report 顺序/npm install）
- **修复**: Issue #11 Stop Condition 必须写 run report
- **修复**: Issue #12 worktree 无 node_modules
- **修复**: run report 写入顺序（commit 后）
- **Hard Rules**: 8 → 9 条（#9 run report 强制）

### v1.2 (2026-03-03) — Flyme 端到端测试后优化
- **新增 Step 0**: 环境验证（ACP 健康检查）
- **Step 1**: 约束字段必须写框架版本行为；新增 timeout 和 .gitignore 字段
- **Step 2**: 新增 Prompt 组装检查清单
- **Step 3**: 详细 ACP spawn 流程，含 cwd 预创建、worktree 清理
- **Step 4**: 改用文件系统检查替代 sessions_history
- **Step 5**: 门禁项从 5 项扩展到 6 项，加 .omc 检查
- **Step 6**: 新增失败模式速查表
- **新增**: ACP 降级方案、已知限制 & 排错、Changelog
- **新增**: ACP 运行日志中转规范（acp-runs 统一目录 + 模板字段）
- **Hard Rules**: 6 → 9 条（新增 run report 规范）

### v1.1 (2026-03-02)
- 初版，基于 Flyme v3 回顾设计

### v3.2 (2026-03-04) — Engineering Standards Template
- **新增**: `templates/task-prompt.md` — 工程守则模板
  - 3 句话 approach 声明
  - assumptions 显式声明
  - surgical changes 规则（只改必要文件）
  - 3 edge cases 必填
  - test_pass 字段加入 .task-result.json
- **效果**: Worker 输出质量从 1 句 notes → 结构化工程报告
- **来源**: karpathy 4 原则 + superpowers systematic-debugging + Arslan 6 tips

### v3.1.4 (2026-03-04) — Gate 安全 + Cleanup
- **修复 #12**: Gate 检查 build_pass=false → reject
- **修复 #13**: Gate 检查 build_pass=null + 有 package.json → reject
- **修复 #14**: Gate fail + poll timeout 自动 cleanup worktree + branch

### v3.1.1 (2026-03-04) — Actionbook Browser Verification
- **新增**: `VERIFY_BROWSER=1` 启用 actionbook CLI headless 验证
- **新增**: `VERIFY_MANIFEST=file.json` per-page 期望 + 交互步骤
- **新增**: 自动截图存 `/tmp/deploy-shots/`
- **修复 #8**: merge output clean oneline + diff stat
- **修复 #9**: VERIFY_EXPECT 全局 → per-page manifest
- **修复 #10**: VERIFY_* env vars 透传到 deploy-verify.sh
- **修复 #11**: subshell 避免 cwd 问题
