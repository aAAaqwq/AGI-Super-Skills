---
name: code-moment-switch-model
description: "代码时刻切模型：当用户要改代码/写项目/重构/修 bug/新增功能/写 Dockerfile 或 docker-compose/nginx/caddy/systemd/部署运行时，自动切入 codex(=newapi/gpt-5.3-codex) 的分阶段工作流（A 流程），高过程可见性；支持\"默认确认\"自动继续，但遇到部署/重启/删除/鉴权路由变更必须显式确认。"
---

# 代码时刻：自动切 Codex（newapi/gpt-5.3-codex）工作台

> 目标：在**不改变主对话默认模型**的前提下，当识别到“编码/部署类任务”时，自动用 `sessions_spawn(...)` 进入 Codex 工作流（A 流程）。
> 约束：webchat 不支持 thread 绑定的持久 subagent session，所以采用 **分阶段多次 subagent run** 来模拟“工作台”。

## 0) 触发策略：泛口令 + 自动检测

优先级（从高到低）：
1. **显式禁止**（用户说不要用 codex）
2. **显式启用**（泛口令：强制进入代码时刻）
3. **自动检测触发**（根据意图/关键词/结构）

### A) 显式启用：泛口令（强制进入代码时刻）
用户任意一句包含以下表达，即视为强制触发：
- “代码时刻” / “进入代码时刻”
- “进入工作台” / “开工作台”
- “用 codex” / “切到 codex” / “codex 模式”
- “编程模式” / “写代码模式”

### B) 显式禁止（覆盖一切自动触发）
用户任意一句包含以下表达，则本次**不触发/不切换**：
- “不要 codex” / “别用 codex”
- “不要切模型” / “别切模型”
- “不用工作台”

### C) 自动检测触发（无口令也会触发）
满足任一条即可触发：
- 明确的编码意图：改代码/写功能/修 bug/重构/补测试/性能优化/代码审计
- 明确的工程/部署意图：Dockerfile、docker-compose、nginx/caddy、systemd、pm2、CI、构建失败、发布/回滚
- 明确的调试信号：stack trace、报错日志、编译错误、linter/test fail、`diff`/补丁需求
- 输入结构信号：出现代码块 ```、文件路径（如 `src/...`、`/etc/...`）、命令行输出、配置片段
- **明确需要多文件代码改动**（跨多个源码/配置文件联动）
- **明确需要 build / test / lint / restart 前验证的代码任务**

默认升级为 codex 的强信号（即使用户没说“代码时刻”也应触发）：
- 多文件代码修改 + build 验证
- 前端/后端状态机、路由、组件、接口等联动修改
- 需要“改代码 → 构建/测试 → 观察结果 → 再修补”的迭代任务

不触发（除非用户用泛口令强制）：
- 纯闲聊/观点讨论/产品对比/非落地方案
- 仅翻译/润色（无代码改动）

## 1) 工作台运行形态（subagent，多阶段 run）

### 1.1 优先选择：spawn 到 codex agent（推荐）
当运行环境已配置 `agentId=codex`（并且 `agents_list` 可见）时，**优先**这样启动：

```json
{
  "tool": "sessions_spawn",
  "runtime": "subagent",
  "agentId": "codex",
  "model": "newapi/gpt-5.3-codex",
  "mode": "run",
  "cleanup": "keep",
  "task": "..."
}
```

原因：把“编码工作台”的默认模型与边界固化在 `codex` 这个隔离 agent 里，减少主 agent 被污染的概率。

### 1.2 兜底：在 main 下直接 spawn
如果没有 `codex` agent（或 allowlist 不允许），才退化为：

```json
{
  "tool": "sessions_spawn",
  "runtime": "subagent",
  "model": "newapi/gpt-5.3-codex",
  "mode": "run"
}
```

### 1.3 WORKBENCH_READY 握手（可选但推荐）
在正式 Patch 前，可先发起一次最小握手，验证 subagent 运行链路：
- subagent task：**只回复** `WORKBENCH_READY`
- 主代理收到 announce 后再进入 Phase 1 Patch

## 2) A 流程（强制）

**Phase 0 — Plan（不改动）**
- 明确目标/验收标准/涉及文件/风险点/回滚思路

**Phase 1 — Patch（产出 diff）**
- 最小改动实现
- 输出文件列表 + 关键 diff/snippet

**Phase 2 — Verify（本地验证）**
- lint/test/build（能跑就跑）
- 输出命令 + 关键日志

**Phase 3 — Deploy（风险闸门）**
- 必须显式确认后才执行

**Phase 4 — Closeout（收尾）**
- 总结变更 + 验证结果 + 回滚步骤

## 3) 默认确认（AUTO_CONTINUE）

当用户说：
- “默认确认开启” / “默认确认” / “自动继续”

则：
- Phase 0→1→2 可以自动推进
- 但 **Phase 3（Deploy）/重启/删除/鉴权路由/防火墙** 仍必须逐项显式确认

## 4) 风险闸门（必须显式确认，即使开启默认确认）

- 任何 deploy/restart：`docker compose up -d`、`systemctl restart`、pm2 reload
- 任何 destructive：删文件、`git reset --hard`、删库/迁移
- 任何鉴权/路由/防火墙改动：nginx/caddy、token、端口、ufw/iptables

## 5) 过程可见性（硬性要求）

- 进入查资料/跑命令前：先说 `我在查 X，预计 N 秒`
- 命令结束（成功/失败都要）：`查到什么 / 下一步要你确认什么`
- 编码执行中：每 1–3 分钟汇报一次 `当前阶段/已完成/下一步/是否要你确认`

## 6) 兜底

如果 subagent spawning 不可用：
- 退化为让用户手动 `/model newapi/gpt-5.3-codex`，仍按 A 流程执行。