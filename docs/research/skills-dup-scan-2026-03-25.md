# Skills 架构扫描报告

- 生成时间: 2026-03-25 23:40:54 CST
- 扫描范围: `~/.agents/skills/`、`~/.openclaw/skills/`、`~/.openclaw/workspace-*/skills/`
- 扫描到目录总数: **141**（其中有效 skills: **139**，非标准目录: **2**）
- 同名重复 skill 数: **35**
- 完全相同（`SKILL.md` 哈希一致）重复 skill 数: **35**

## 1) 目录统计

### 按根目录统计
- `/home/aa/.agents/skills`: 57 个目录，57 个有效 skills，体量 1.9 MB
- `/home/aa/.openclaw/skills`: 58 个目录，57 个有效 skills，体量 4.5 MB
- `/home/aa/.openclaw/workspace-data/skills`: 1 个目录，1 个有效 skills，体量 5.3 KB
- `/home/aa/.openclaw/workspace-main/skills`: 1 个目录，1 个有效 skills，体量 14.7 KB
- `/home/aa/.openclaw/workspace-ops/skills`: 2 个目录，1 个有效 skills，体量 14.1 KB
- `/home/aa/.openclaw/workspace-quant/skills`: 9 个目录，9 个有效 skills，体量 66.5 KB
- `/home/aa/.openclaw/workspace-research/skills`: 13 个目录，13 个有效 skills，体量 509.0 KB

### 按建议分类统计
- global 通用（候选）: 86
- agent 专用: 28
- workspace 项目专用: 25

### 非标准目录（无 `SKILL.md`）
- `/home/aa/.openclaw/skills/.clawdhub` — 文件数 1，体量 499 B
- `/home/aa/.openclaw/workspace-ops/skills/dist` — 文件数 1，体量 4.5 KB

## 2) 同名重复项

### `agent-browser`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.openclaw/skills/agent-browser` | bucket=openclaw-global | sha16=04afeeb53a8b6ab9
  - `/home/aa/.openclaw/workspace-research/skills/agent-browser` | bucket=workspace-project | sha16=04afeeb53a8b6ab9

### `api-design`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/api-design` | bucket=agents-global | sha16=d2b090c4319e030f
  - `/home/aa/.openclaw/skills/api-design` | bucket=openclaw-global | sha16=d2b090c4319e030f

### `api-design-patterns`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/api-design-patterns` | bucket=agents-global | sha16=1d89932bee15231f
  - `/home/aa/.openclaw/skills/api-design-patterns` | bucket=openclaw-global | sha16=1d89932bee15231f

### `brainstorming`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/brainstorming` | bucket=agents-global | sha16=108ec2f11ec511b4
  - `/home/aa/.openclaw/skills/brainstorming` | bucket=openclaw-global | sha16=108ec2f11ec511b4

### `code-review-quality`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/code-review-quality` | bucket=agents-global | sha16=b18b79780e1bc7a9
  - `/home/aa/.openclaw/skills/code-review-quality` | bucket=openclaw-global | sha16=b18b79780e1bc7a9

### `deployment-automation`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/deployment-automation` | bucket=agents-global | sha16=542d86db66647369
  - `/home/aa/.openclaw/skills/deployment-automation` | bucket=openclaw-global | sha16=542d86db66647369

### `dispatching-parallel-agents`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/dispatching-parallel-agents` | bucket=agents-global | sha16=76806091c7f923ba
  - `/home/aa/.openclaw/skills/dispatching-parallel-agents` | bucket=openclaw-global | sha16=76806091c7f923ba

### `docker-containerization`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/docker-containerization` | bucket=agents-global | sha16=86af45d28bc4c485
  - `/home/aa/.openclaw/skills/docker-containerization` | bucket=openclaw-global | sha16=86af45d28bc4c485

### `e2e-testing-patterns`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/e2e-testing-patterns` | bucket=agents-global | sha16=12d1921c316a31d2
  - `/home/aa/.openclaw/skills/e2e-testing-patterns` | bucket=openclaw-global | sha16=12d1921c316a31d2

### `elite-longterm-memory`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/elite-longterm-memory` | bucket=agents-global | sha16=56bb341604f95198
  - `/home/aa/.openclaw/skills/elite-longterm-memory` | bucket=openclaw-global | sha16=56bb341604f95198

### `executing-plans`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/executing-plans` | bucket=agents-global | sha16=a711f83fb762e2ea
  - `/home/aa/.openclaw/skills/executing-plans` | bucket=openclaw-global | sha16=a711f83fb762e2ea

### `find-skills`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/find-skills` | bucket=agents-global | sha16=54b44dc9539df865
  - `/home/aa/.openclaw/skills/find-skills` | bucket=openclaw-global | sha16=54b44dc9539df865

### `finishing-a-development-branch`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/finishing-a-development-branch` | bucket=agents-global | sha16=dd2f82c6dc8582b6
  - `/home/aa/.openclaw/skills/finishing-a-development-branch` | bucket=openclaw-global | sha16=dd2f82c6dc8582b6

### `ghost-scan-code`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/ghost-scan-code` | bucket=agents-global | sha16=8f6f2212ff4e60d2
  - `/home/aa/.openclaw/skills/ghost-scan-code` | bucket=openclaw-global | sha16=8f6f2212ff4e60d2

### `kubernetes-specialist`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/kubernetes-specialist` | bucket=agents-global | sha16=a53962a8d166ad68
  - `/home/aa/.openclaw/skills/kubernetes-specialist` | bucket=openclaw-global | sha16=a53962a8d166ad68

### `nginx-configuration`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/nginx-configuration` | bucket=agents-global | sha16=e1ab979bb9ce7a8b
  - `/home/aa/.openclaw/skills/nginx-configuration` | bucket=openclaw-global | sha16=e1ab979bb9ce7a8b

### `openclaw-browser-chain-debug`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.openclaw/skills/openclaw-browser-chain-debug` | bucket=openclaw-global | sha16=b94ae9a09fccc259
  - `/home/aa/.openclaw/workspace-ops/skills/openclaw-browser-chain-debug` | bucket=workspace-project | sha16=b94ae9a09fccc259

### `postgresql-database-engineering`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/postgresql-database-engineering` | bucket=agents-global | sha16=bad999f82d83cae3
  - `/home/aa/.openclaw/skills/postgresql-database-engineering` | bucket=openclaw-global | sha16=bad999f82d83cae3

### `react-expert`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/react-expert` | bucket=agents-global | sha16=bdaa978ac67ad074
  - `/home/aa/.openclaw/skills/react-expert` | bucket=openclaw-global | sha16=bdaa978ac67ad074

### `receiving-code-review`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/receiving-code-review` | bucket=agents-global | sha16=c9382e92b8f32363
  - `/home/aa/.openclaw/skills/receiving-code-review` | bucket=openclaw-global | sha16=c9382e92b8f32363

### `redis-inspect`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/redis-inspect` | bucket=agents-global | sha16=ee6e31378bfd79e5
  - `/home/aa/.openclaw/skills/redis-inspect` | bucket=openclaw-global | sha16=ee6e31378bfd79e5

### `requesting-code-review`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/requesting-code-review` | bucket=agents-global | sha16=a5ff68586ccf62d1
  - `/home/aa/.openclaw/skills/requesting-code-review` | bucket=openclaw-global | sha16=a5ff68586ccf62d1

### `skills-search`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/skills-search` | bucket=agents-global | sha16=9e1bc5989af8f68a
  - `/home/aa/.openclaw/skills/skills-search` | bucket=openclaw-global | sha16=9e1bc5989af8f68a

### `sql-optimization`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/sql-optimization` | bucket=agents-global | sha16=d87639dea8e0208e
  - `/home/aa/.openclaw/skills/sql-optimization` | bucket=openclaw-global | sha16=d87639dea8e0208e

### `subagent-driven-development`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/subagent-driven-development` | bucket=agents-global | sha16=081ad3869e55c80b
  - `/home/aa/.openclaw/skills/subagent-driven-development` | bucket=openclaw-global | sha16=081ad3869e55c80b

### `systematic-debugging`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/systematic-debugging` | bucket=agents-global | sha16=4999cb851360485e
  - `/home/aa/.openclaw/skills/systematic-debugging` | bucket=openclaw-global | sha16=4999cb851360485e

### `tailwindcss`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/tailwindcss` | bucket=agents-global | sha16=c2fa19b055945dc8
  - `/home/aa/.openclaw/skills/tailwindcss` | bucket=openclaw-global | sha16=c2fa19b055945dc8

### `test-driven-development`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/test-driven-development` | bucket=agents-global | sha16=7dee67b4af6bdccc
  - `/home/aa/.openclaw/skills/test-driven-development` | bucket=openclaw-global | sha16=7dee67b4af6bdccc

### `traffic-acquisition`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/traffic-acquisition` | bucket=agents-global | sha16=38a58bc73e4af79c
  - `/home/aa/.openclaw/skills/traffic-acquisition` | bucket=openclaw-global | sha16=38a58bc73e4af79c

### `using-git-worktrees`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/using-git-worktrees` | bucket=agents-global | sha16=de9dcde34840eee0
  - `/home/aa/.openclaw/skills/using-git-worktrees` | bucket=openclaw-global | sha16=de9dcde34840eee0

### `verification-before-completion`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/verification-before-completion` | bucket=agents-global | sha16=ea52d15aabaf72bc
  - `/home/aa/.openclaw/skills/verification-before-completion` | bucket=openclaw-global | sha16=ea52d15aabaf72bc

### `video-generation`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/video-generation` | bucket=agents-global | sha16=2536e14c275c8eaa
  - `/home/aa/.openclaw/skills/video-generation` | bucket=openclaw-global | sha16=2536e14c275c8eaa

### `video-marketing`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/video-marketing` | bucket=agents-global | sha16=6348cac3e96b2ddb
  - `/home/aa/.openclaw/skills/video-marketing` | bucket=openclaw-global | sha16=6348cac3e96b2ddb

### `writing-plans`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/writing-plans` | bucket=agents-global | sha16=4a079ecfc750c5af
  - `/home/aa/.openclaw/skills/writing-plans` | bucket=openclaw-global | sha16=4a079ecfc750c5af

### `writing-skills`
- 副本数: 2
- `SKILL.md` 内容是否一致: **是**
  - `/home/aa/.agents/skills/writing-skills` | bucket=agents-global | sha16=d83a09d6a1c6976f
  - `/home/aa/.openclaw/skills/writing-skills` | bucket=openclaw-global | sha16=d83a09d6a1c6976f

## 3) 分类建议（agent 专用 / global 通用 / workspace 项目专用）

### 建议原则
- **workspace 项目专用**：放在 `workspace-*/skills`，与具体项目、数据源、工作流强绑定。
- **global 通用**：跨项目复用的通用能力，优先保留一份规范主副本。
- **agent 专用**：更偏 agent 编排、记忆、调度、评审、验证、browser chain 等控制面能力。

### 优先处理建议
- **先处理完全一致的重复项**：这些 skill 在多个全局层重复存在，维护成本高、收益低，适合确定一个 canonical 位置后其余改为引用/同步来源。
- 当前完全一致重复项（节选）: `agent-browser`, `api-design`, `api-design-patterns`, `brainstorming`, `code-review-quality`, `deployment-automation`, `dispatching-parallel-agents`, `docker-containerization`, `e2e-testing-patterns`, `elite-longterm-memory`, `executing-plans`, `find-skills`, `finishing-a-development-branch`, `ghost-scan-code`, `kubernetes-specialist`, `nginx-configuration`, `openclaw-browser-chain-debug`, `postgresql-database-engineering`, `react-expert`, `receiving-code-review`
- **workspace 内保留局部技能**：如 `polymarket-*`、`crypto-hunt`、`news-predictor` 等，明显是项目域能力，不建议上提到全局。
- **agent 控制面技能尽量收口**：如 `agent-browser`、`openclaw-browser-chain-debug`、`subagent-driven-development`、`verification-before-completion`，适合统一进 agent/global 控制层，而不是散落多处。

### 各目录分类建议（摘要）
- `ads-agent` @ `/home/aa/.agents/skills/ads-agent` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `agent-browser` @ `/home/aa/.openclaw/skills/agent-browser` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `code-review-quality` @ `/home/aa/.agents/skills/code-review-quality` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `code-review-quality` @ `/home/aa/.openclaw/skills/code-review-quality` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `dispatching-parallel-agents` @ `/home/aa/.agents/skills/dispatching-parallel-agents` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `dispatching-parallel-agents` @ `/home/aa/.openclaw/skills/dispatching-parallel-agents` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `elite-longterm-memory` @ `/home/aa/.agents/skills/elite-longterm-memory` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `elite-longterm-memory` @ `/home/aa/.openclaw/skills/elite-longterm-memory` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `executing-plans` @ `/home/aa/.agents/skills/executing-plans` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `executing-plans` @ `/home/aa/.openclaw/skills/executing-plans` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `openclaw-browser-chain-debug` @ `/home/aa/.openclaw/skills/openclaw-browser-chain-debug` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `openclaw-memory-enhancer` @ `/home/aa/.openclaw/skills/openclaw-memory-enhancer` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `receiving-code-review` @ `/home/aa/.agents/skills/receiving-code-review` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `receiving-code-review` @ `/home/aa/.openclaw/skills/receiving-code-review` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `requesting-code-review` @ `/home/aa/.agents/skills/requesting-code-review` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `requesting-code-review` @ `/home/aa/.openclaw/skills/requesting-code-review` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `roadmap-planning` @ `/home/aa/.agents/skills/roadmap-planning` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `self-reflection` @ `/home/aa/.openclaw/skills/self-reflection` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `subagent-driven-development` @ `/home/aa/.agents/skills/subagent-driven-development` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `subagent-driven-development` @ `/home/aa/.openclaw/skills/subagent-driven-development` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `systematic-debugging` @ `/home/aa/.agents/skills/systematic-debugging` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `systematic-debugging` @ `/home/aa/.openclaw/skills/systematic-debugging` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `using-git-worktrees` @ `/home/aa/.agents/skills/using-git-worktrees` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `using-git-worktrees` @ `/home/aa/.openclaw/skills/using-git-worktrees` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `verification-before-completion` @ `/home/aa/.agents/skills/verification-before-completion` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `verification-before-completion` @ `/home/aa/.openclaw/skills/verification-before-completion` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `writing-plans` @ `/home/aa/.agents/skills/writing-plans` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `writing-plans` @ `/home/aa/.openclaw/skills/writing-plans` → **agent 专用**；名称更像编排/调度/agent 工作流能力，优先放 agent 自己的技能层。
- `ads` @ `/home/aa/.agents/skills/ads` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `api-design` @ `/home/aa/.agents/skills/api-design` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `api-design` @ `/home/aa/.openclaw/skills/api-design` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `api-design-patterns` @ `/home/aa/.agents/skills/api-design-patterns` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `api-design-patterns` @ `/home/aa/.openclaw/skills/api-design-patterns` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `api-quota-monitor` @ `/home/aa/.openclaw/skills/api-quota-monitor` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `apify-competitor-intelligence` @ `/home/aa/.agents/skills/apify-competitor-intelligence` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `brainstorming` @ `/home/aa/.agents/skills/brainstorming` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `brainstorming` @ `/home/aa/.openclaw/skills/brainstorming` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `brave-search` @ `/home/aa/.openclaw/skills/brave-search` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `btc-5min-scalper` @ `/home/aa/.openclaw/skills/btc-5min-scalper` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `cli-developer` @ `/home/aa/.agents/skills/cli-developer` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `competitive-analysis` @ `/home/aa/.agents/skills/competitive-analysis` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `competitor-alternatives` @ `/home/aa/.agents/skills/competitor-alternatives` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `competitor-price-tracker` @ `/home/aa/.agents/skills/competitor-price-tracker` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `content-ops-toolkit` @ `/home/aa/.agents/skills/content-ops-toolkit` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `ct-monitor` @ `/home/aa/.agents/skills/ct-monitor` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `deployment-automation` @ `/home/aa/.agents/skills/deployment-automation` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `deployment-automation` @ `/home/aa/.openclaw/skills/deployment-automation` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `design-thinking` @ `/home/aa/.agents/skills/design-thinking` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `docker-containerization` @ `/home/aa/.agents/skills/docker-containerization` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `docker-containerization` @ `/home/aa/.openclaw/skills/docker-containerization` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `e2e-testing-patterns` @ `/home/aa/.agents/skills/e2e-testing-patterns` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `e2e-testing-patterns` @ `/home/aa/.openclaw/skills/e2e-testing-patterns` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `ecommerce-competitor-analyzer` @ `/home/aa/.agents/skills/ecommerce-competitor-analyzer` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `find-skills` @ `/home/aa/.agents/skills/find-skills` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `find-skills` @ `/home/aa/.openclaw/skills/find-skills` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `finishing-a-development-branch` @ `/home/aa/.agents/skills/finishing-a-development-branch` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `finishing-a-development-branch` @ `/home/aa/.openclaw/skills/finishing-a-development-branch` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `ghost-scan-code` @ `/home/aa/.agents/skills/ghost-scan-code` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `ghost-scan-code` @ `/home/aa/.openclaw/skills/ghost-scan-code` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `gog` @ `/home/aa/.openclaw/skills/gog` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `google-ads` @ `/home/aa/.agents/skills/google-ads` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `google-analytics` @ `/home/aa/.agents/skills/google-analytics` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `humanizer` @ `/home/aa/.agents/skills/humanizer` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `jimeng-digital-human` @ `/home/aa/.openclaw/skills/jimeng-digital-human` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `jimeng-login` @ `/home/aa/.openclaw/skills/jimeng-login` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `jimeng-storyboard` @ `/home/aa/.openclaw/skills/jimeng-storyboard` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `key-rotation` @ `/home/aa/.openclaw/skills/key-rotation` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `kubernetes-specialist` @ `/home/aa/.agents/skills/kubernetes-specialist` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `kubernetes-specialist` @ `/home/aa/.openclaw/skills/kubernetes-specialist` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `meta-cognition` @ `/home/aa/.openclaw/skills/meta-cognition` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `moltbook-interact` @ `/home/aa/.openclaw/skills/moltbook-interact` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `nano-banana-pro` @ `/home/aa/.openclaw/skills/nano-banana-pro` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `nginx-configuration` @ `/home/aa/.agents/skills/nginx-configuration` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `nginx-configuration` @ `/home/aa/.openclaw/skills/nginx-configuration` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `notion` @ `/home/aa/.openclaw/skills/notion` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `poster-design-generation` @ `/home/aa/.agents/skills/poster-design-generation` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `postgresql-database-engineering` @ `/home/aa/.agents/skills/postgresql-database-engineering` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `postgresql-database-engineering` @ `/home/aa/.openclaw/skills/postgresql-database-engineering` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `prd-development` @ `/home/aa/.agents/skills/prd-development` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `prototype-prompt-generator` @ `/home/aa/.agents/skills/prototype-prompt-generator` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `react-expert` @ `/home/aa/.agents/skills/react-expert` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `react-expert` @ `/home/aa/.openclaw/skills/react-expert` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `redis-inspect` @ `/home/aa/.agents/skills/redis-inspect` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `redis-inspect` @ `/home/aa/.openclaw/skills/redis-inspect` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `relay-image-gen` @ `/home/aa/.openclaw/skills/relay-image-gen` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `relay-video-gen` @ `/home/aa/.openclaw/skills/relay-video-gen` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `self-improving` @ `/home/aa/.openclaw/skills/self-improving` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `skill-amazon-ads` @ `/home/aa/.agents/skills/skill-amazon-ads` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `skill-search-optimizer` @ `/home/aa/.openclaw/skills/skill-search-optimizer` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `skills-search` @ `/home/aa/.agents/skills/skills-search` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `skills-search` @ `/home/aa/.openclaw/skills/skills-search` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `sql-optimization` @ `/home/aa/.agents/skills/sql-optimization` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `sql-optimization` @ `/home/aa/.openclaw/skills/sql-optimization` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `summarize` @ `/home/aa/.openclaw/skills/summarize` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `synthetic-market-research` @ `/home/aa/.agents/skills/synthetic-market-research` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `tailwindcss` @ `/home/aa/.agents/skills/tailwindcss` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `tailwindcss` @ `/home/aa/.openclaw/skills/tailwindcss` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `test-driven-development` @ `/home/aa/.agents/skills/test-driven-development` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `test-driven-development` @ `/home/aa/.openclaw/skills/test-driven-development` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `traffic-acquisition` @ `/home/aa/.agents/skills/traffic-acquisition` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `traffic-acquisition` @ `/home/aa/.openclaw/skills/traffic-acquisition` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `user-story` @ `/home/aa/.agents/skills/user-story` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `using-superpowers` @ `/home/aa/.agents/skills/using-superpowers` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `video-generation` @ `/home/aa/.agents/skills/video-generation` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `video-generation` @ `/home/aa/.openclaw/skills/video-generation` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `video-marketing` @ `/home/aa/.agents/skills/video-marketing` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `video-marketing` @ `/home/aa/.openclaw/skills/video-marketing` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `video-merge-send` @ `/home/aa/.openclaw/skills/video-merge-send` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `vp-cpo-readiness-advisor` @ `/home/aa/.agents/skills/vp-cpo-readiness-advisor` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `weixin-channels-publish` @ `/home/aa/.openclaw/skills/weixin-channels-publish` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `work-to-skill` @ `/home/aa/.openclaw/skills/work-to-skill` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `writing-skills` @ `/home/aa/.agents/skills/writing-skills` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `writing-skills` @ `/home/aa/.openclaw/skills/writing-skills` → **global 通用（候选）**；位于 ~/.openclaw/skills，且不是明显 workspace 专用，适合做 OpenClaw 全局技能。
- `xiaohongshu-growth` @ `/home/aa/.agents/skills/xiaohongshu-growth` → **global 通用（候选）**；位于 ~/.agents/skills，且名称更像通用开发/分析能力，适合做共享全局技能。
- `agent-browser` @ `/home/aa/.openclaw/workspace-research/skills/agent-browser` → **workspace 项目专用**；位于 workspace skills (research)，默认应视为项目内聚能力，优先保持局部。
- `browser-automation` @ `/home/aa/.openclaw/workspace-research/skills/browser-automation` → **workspace 项目专用**；位于 workspace skills (research)，默认应视为项目内聚能力，优先保持局部。
- `browser-use` @ `/home/aa/.openclaw/workspace-research/skills/browser-use` → **workspace 项目专用**；位于 workspace skills (research)，默认应视为项目内聚能力，优先保持局部。
- `cicd-pipeline-generator` @ `/home/aa/.openclaw/workspace-research/skills/cicd-pipeline-generator` → **workspace 项目专用**；位于 workspace skills (research)，默认应视为项目内聚能力，优先保持局部。
- `crypto-hunt` @ `/home/aa/.openclaw/workspace-quant/skills/crypto-hunt` → **workspace 项目专用**；位于 workspace skills (quant)，默认应视为项目内聚能力，优先保持局部。
- `daily-portfolio` @ `/home/aa/.openclaw/workspace-quant/skills/daily-portfolio` → **workspace 项目专用**；位于 workspace skills (quant)，默认应视为项目内聚能力，优先保持局部。
- `daily-reflection` @ `/home/aa/.openclaw/workspace-quant/skills/daily-reflection` → **workspace 项目专用**；位于 workspace skills (quant)，默认应视为项目内聚能力，优先保持局部。
- `desearch-web-search` @ `/home/aa/.openclaw/workspace-research/skills/desearch-web-search` → **workspace 项目专用**；位于 workspace skills (research)，默认应视为项目内聚能力，优先保持局部。
- `docker-essentials` @ `/home/aa/.openclaw/workspace-research/skills/docker-essentials` → **workspace 项目专用**；位于 workspace skills (research)，默认应视为项目内聚能力，优先保持局部。
- `elon-tweets` @ `/home/aa/.openclaw/workspace-quant/skills/elon-tweets` → **workspace 项目专用**；位于 workspace skills (quant)，默认应视为项目内聚能力，优先保持局部。
- `exa-search` @ `/home/aa/.openclaw/workspace-research/skills/exa-search` → **workspace 项目专用**；位于 workspace skills (research)，默认应视为项目内聚能力，优先保持局部。
- `fast-browser-use` @ `/home/aa/.openclaw/workspace-research/skills/fast-browser-use` → **workspace 项目专用**；位于 workspace skills (research)，默认应视为项目内聚能力，优先保持局部。
- `gh-action-gen` @ `/home/aa/.openclaw/workspace-research/skills/gh-action-gen` → **workspace 项目专用**；位于 workspace skills (research)，默认应视为项目内聚能力，优先保持局部。
- `hunt-report` @ `/home/aa/.openclaw/workspace-quant/skills/hunt-report` → **workspace 项目专用**；位于 workspace skills (quant)，默认应视为项目内聚能力，优先保持局部。
- `news-predictor` @ `/home/aa/.openclaw/workspace-quant/skills/news-predictor` → **workspace 项目专用**；位于 workspace skills (quant)，默认应视为项目内聚能力，优先保持局部。
- `openclaw-browser-chain-debug` @ `/home/aa/.openclaw/workspace-ops/skills/openclaw-browser-chain-debug` → **workspace 项目专用**；位于 workspace skills (ops)，默认应视为项目内聚能力，优先保持局部。
- `perplexity-search` @ `/home/aa/.openclaw/workspace-research/skills/perplexity-search` → **workspace 项目专用**；位于 workspace skills (research)，默认应视为项目内聚能力，优先保持局部。
- `polymarket-api` @ `/home/aa/.openclaw/workspace-quant/skills/polymarket-api` → **workspace 项目专用**；位于 workspace skills (quant)，默认应视为项目内聚能力，优先保持局部。
- `polymarket-data` @ `/home/aa/.openclaw/workspace-data/skills/polymarket-data` → **workspace 项目专用**；位于 workspace skills (data)，默认应视为项目内聚能力，优先保持局部。
- `polymarket-trader` @ `/home/aa/.openclaw/workspace-research/skills/polymarket-trader` → **workspace 项目专用**；位于 workspace skills (research)，默认应视为项目内聚能力，优先保持局部。
- `polymarket-trading` @ `/home/aa/.openclaw/workspace-main/skills/polymarket-trading` → **workspace 项目专用**；位于 workspace skills (main)，默认应视为项目内聚能力，优先保持局部。
- `position-monitor` @ `/home/aa/.openclaw/workspace-quant/skills/position-monitor` → **workspace 项目专用**；位于 workspace skills (quant)，默认应视为项目内聚能力，优先保持局部。
- `tavily-search` @ `/home/aa/.openclaw/workspace-research/skills/tavily-search` → **workspace 项目专用**；位于 workspace skills (research)，默认应视为项目内聚能力，优先保持局部。
- `unified-search` @ `/home/aa/.openclaw/workspace-research/skills/unified-search` → **workspace 项目专用**；位于 workspace skills (research)，默认应视为项目内聚能力，优先保持局部。
- `weekly-review` @ `/home/aa/.openclaw/workspace-quant/skills/weekly-review` → **workspace 项目专用**；位于 workspace skills (quant)，默认应视为项目内聚能力，优先保持局部。

## 4) 疑似 cron / 脚本硬编码依赖风险

共发现 **12** 条疑似风险：
- [file] `/home/aa/clawd/projects/content-factory/scripts/run_daily.sh`:7 — 命中 skills 路径/安装模式，属于潜在硬编码依赖。
  - 命中: `/home/aa/clawd(?:/[^\s'\"]+)?/skills(?:/[^\s'\"]+)?`
  - 片段: `AGGREGATOR="/home/aa/clawd/skills/content-source-aggregator"`
- [file] `/home/aa/clawd/projects/openclaw-knowledge-hub/.astro/data-store.json`:1 — 命中 skills 路径/安装模式，且带具体技能名，迁移/重命名时更脆弱。
  - 命中: `~/.agents/skills|/home/aa/.agents/skills; npx\s+skills\s+add; skills\s+add\s+[\w./@-]+`
  - 片段: `[["Map",1,2,1338,1339],"docs",["Map",3,4,41,42,61,62,102,103,152,153,218,219,263,264,300,301,338,339,433,434,468,469,504,505,542,543,573,574,634,635,691,692,716,717,745,746,777,778,804,805,830,831,857`
- [file] `/home/aa/.openclaw/cron/jobs.json`:219 — 命中 skills 路径/安装模式，且带具体技能名，迁移/重命名时更脆弱。
  - 命中: `workspace-[^/\s'\"]*/skills`
  - 片段: `"message": "读取并严格执行以下skill文件中的全部步骤：\n\n```bash\ncat /home/aa/.openclaw/workspace-quant/skills/daily-portfolio/SKILL.md\n```\n\n先用上面的命令读取skill内容，然后按照skill中的步骤逐步执行。不要跳过任何步骤。",`
- [file] `/home/aa/.openclaw/cron/jobs.json`:261 — 命中 skills 路径/安装模式，且带具体技能名，迁移/重命名时更脆弱。
  - 命中: `workspace-[^/\s'\"]*/skills`
  - 片段: `"message": "读取并严格执行以下skill文件中的全部步骤：\n\n```bash\ncat /home/aa/.openclaw/workspace-quant/skills/weekly-review/SKILL.md\n```\n\n先用上面的命令读取skill内容，然后按照skill中的步骤逐步执行。不要跳过任何步骤。\n\n额外执行约束：\n- 这是 cron 任务，先完成数据`
- [file] `/home/aa/.openclaw/cron/jobs.json`:375 — 命中 skills 路径/安装模式，且带具体技能名，迁移/重命名时更脆弱。
  - 命中: `workspace-[^/\s'\"]*/skills`
  - 片段: `"message": "读取并严格执行以下skill文件中的全部步骤：\n\n```bash\ncat /home/aa/.openclaw/workspace-quant/skills/position-monitor/SKILL.md\n```\n\n先用上面的命令读取skill内容，然后按照skill中的步骤逐步执行。不要跳过任何步骤。",`
- [file] `/home/aa/.openclaw/cron/jobs.json`:655 — 命中 skills 路径/安装模式，且带具体技能名，迁移/重命名时更脆弱。
  - 命中: `workspace-[^/\s'\"]*/skills`
  - 片段: `"message": "读取并严格执行以下skill文件中的全部步骤：\n\n```bash\ncat /home/aa/.openclaw/workspace-quant/skills/elon-tweets/SKILL.md\n```\n\n先用上面的命令读取skill内容，然后按照skill中的步骤逐步执行。不要跳过任何步骤。",`
- [file] `/home/aa/.openclaw/cron/jobs.json`:699 — 命中 skills 路径/安装模式，且带具体技能名，迁移/重命名时更脆弱。
  - 命中: `~/.openclaw/skills|/home/aa/.openclaw/skills`
  - 片段: `"message": "BTC 5min纸盘训练轮次。执行以下步骤：\n1. 读取 skill ~/.openclaw/skills/btc-5min-scalper/SKILL.md\n2. 运行 `unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY && bash ~/.openclaw/skills/`
- [file] `/home/aa/.openclaw/cron/jobs.json`:1528 — 命中 skills 路径/安装模式，且带具体技能名，迁移/重命名时更脆弱。
  - 命中: `~/.openclaw/skills|/home/aa/.openclaw/skills`
  - 片段: `"message": "【每日内容生产任务】\n\n你是CCO（首席创意官），Daniel Li的内容Agent。\n\n## 任务\n按SOP执行每日内容生产，产出9篇高质量内容（3平台×3篇）。\n\n## SOP路径\n阅读 ~/clawd/docs/content-engineering-sop.md 获取完整流程。\n\n## Daniel人设\n读取 ~/.openclaw/works`
- [file] `/home/aa/.openclaw/cron/jobs.json`:1570 — 命中 skills 路径/安装模式，且带具体技能名，迁移/重命名时更脆弱。
  - 命中: `~/.openclaw/skills|/home/aa/.openclaw/skills`
  - 片段: `"message": "【小红书每日内容生产 · {date}】\n\n你是CCO，Daniel Li的内容Agent。\n\n## 任务\n产出3篇小红书高质量内容。\n\n## SOP\n阅读 ~/clawd/docs/content-engineering-sop.md\n人设：~/.openclaw/workspace-content/USER.md\n飞书方法论：~/clawd/memo`
- [file] `/home/aa/.openclaw/cron/jobs.json`:1613 — 命中 skills 路径/安装模式，且带具体技能名，迁移/重命名时更脆弱。
  - 命中: `~/.openclaw/skills|/home/aa/.openclaw/skills`
  - 片段: `"message": "【公众号每日内容生产 · {date}】\n\n你是CCO，Daniel Li的内容Agent。\n\n## 任务\n产出3篇微信公众号高质量深度文章。\n\n## SOP\n阅读 ~/clawd/docs/content-engineering-sop.md\n人设：~/.openclaw/workspace-content/USER.md\n飞书方法论：~/clawd/`
- [file] `/home/aa/.openclaw/cron/jobs.json`:1742 — 命中 skills 路径/安装模式，且带具体技能名，迁移/重命名时更脆弱。
  - 命中: `workspace-[^/\s'\"]*/skills`
  - 片段: `"message": "读取并严格执行以下skill文件中的全部步骤：\n\n```bash\ncat /home/aa/.openclaw/workspace-quant/skills/crypto-hunt/SKILL.md\n```\n\n先用上面的命令读取skill内容，然后按照skill中的步骤逐步执行。不要跳过任何步骤。",`
- [file] `/home/aa/.openclaw/cron/jobs.json`:1783 — 命中 skills 路径/安装模式，且带具体技能名，迁移/重命名时更脆弱。
  - 命中: `workspace-[^/\s'\"]*/skills`
  - 片段: `"message": "读取并严格执行以下skill文件中的全部步骤：\n\n```bash\ncat /home/aa/.openclaw/workspace-quant/skills/hunt-report/SKILL.md\n```\n\n先用上面的命令读取skill内容，然后按照skill中的步骤逐步执行。不要跳过任何步骤。",`

## 5) 核心发现

1. 当前 skills 目录存在 **35** 组同名重复项，其中 **35** 组 `SKILL.md` 内容完全一致，说明有明显的双份维护现象。
2. `~/.agents/skills` 与 `~/.openclaw/skills` 之间存在大量镜像式重复，更像是安装/同步策略未收口，而不是有意分层。
3. workspace 层 skills 总体数量不大，但领域边界明显，适合继续按项目局部管理；反而全局层需要去重和明确 canonical source。
4. 发现 **2** 个非标准目录（如无 `SKILL.md` 的 `.clawdhub`、`dist`），建议纳入 hygiene 清单，避免扫描器或加载器误判。
5. 检出 **12** 条疑似脚本/cron 依赖风险；其中最值得注意的是直接写死 skills 绝对路径的自动化脚本，后续迁移目录时最容易失效。

## 6) 最小可用整改方向（不改目录，仅建议）

- 先选定一处 **global canonical root**（更像 `~/.openclaw/skills` 或 agent 自己技能树），把另一处重复项视为镜像/待淘汰层。
- 对完全一致重复项，后续可逐步改成：单源维护 + 同步脚本 / 软链接 / manifest。
- 给 workspace skills 增加 `owner` / `scope` / `project` 元数据字段，降低未来误上提概率。
- 把 cron / shell 中的绝对路径依赖抽到环境变量或配置文件，尤其是任何 `/home/aa/.../skills/...` 风格引用。
