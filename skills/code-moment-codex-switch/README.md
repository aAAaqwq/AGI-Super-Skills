# code-moment-codex-switch

[中文](#中文) | [ENGLISH](#english)

---

## 中文

一个用于 OpenClaw 的技能（skill），用于在任务进入“代码时刻”后，自动把执行升级到更适合工程工作的 Codex 工作台。

### 这是什么

这个仓库提供一个面向 OpenClaw 的 `SKILL.md`，目标是把以下两类任务区分开：

- **普通聊天 / 普通排查**：继续留在默认对话模型
- **重代码 / 工程实现任务**：自动切到 Codex 工作台

它的重点不是“所有任务都强制切模型”，而是只在任务跨过工程阈值时，才进入专门的编码流程。

### 适合解决什么问题

适合这种场景：

- 平时主要用通用模型聊天、排障、查配置
- 但一旦进入多文件改动、构建验证、持续修补的任务，就希望自动切到代码模型
- 希望把“日常对话”和“工程执行”分流，减少主会话被纯编码流程拖住

### 强触发信号

以下情况默认应升级到 Codex：

- 多文件代码修改
- 需要 `build` / `test` / `lint` / 重启前验证
- 前端/后端状态机、路由、组件、接口、配置联动修改
- 需要“改代码 → 构建/测试 → 看结果 → 再修补”的迭代任务
- Dockerfile、docker-compose、nginx、caddy、systemd、CI、构建失败排查

### 工作方式

这个 skill 的目标是让 OpenClaw 在识别到重代码任务时：

- 默认进入 Codex 工作台
- 保留分阶段流程（Plan / Patch / Verify / Deploy / Closeout）
- 在 deploy / restart / delete / 鉴权 / 路由修改这类高风险动作前继续要求确认

### 仓库内容

- `SKILL.md`：技能定义文件
- `README.md`：仓库说明文件

### 适用对象

适合希望把 OpenClaw 用成“聊天助手 + 工程工作台”双模式的人。

---

## English

An OpenClaw skill that upgrades coding-heavy tasks into a Codex-oriented engineering workbench flow.

### What this is

This repository provides a `SKILL.md` for OpenClaw. Its purpose is to separate two kinds of work:

- **normal chat / light investigation**: stay on the default chat model
- **heavier engineering execution**: switch to a Codex workbench by default

The goal is not to force every task onto another model, but to switch only when the task crosses the engineering threshold.

### What problem it solves

This is useful when:

- you want a general model for normal chat, troubleshooting, and config work
- but you want coding-heavy work to move to a dedicated code model automatically
- you want to separate daily conversation from deeper engineering execution

### Strong trigger signals

The following cases should default to Codex:

- multi-file code changes
- tasks requiring `build` / `test` / `lint` / pre-restart verification
- linked frontend/backend changes across state machines, routing, components, APIs, or configs
- iterative loops like: modify code → build/test → inspect result → patch again
- Dockerfile, docker-compose, nginx, caddy, systemd, CI, and build-failure debugging

### How it works

This skill is designed so that OpenClaw can:

- move coding-heavy tasks into a Codex workbench
- preserve a phased workflow (Plan / Patch / Verify / Deploy / Closeout)
- keep confirmation gates for deploy / restart / delete / auth / routing changes

### Repository contents

- `SKILL.md`: the skill definition
- `README.md`: repository documentation

### Intended audience

Useful for people who want OpenClaw to work as both a chat assistant and an engineering workbench.
