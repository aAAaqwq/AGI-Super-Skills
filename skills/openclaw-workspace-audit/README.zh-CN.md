<![CDATA[<!-- SEO: openclaw-workspace-audit – OpenClaw 技能，用于审计、优化和清理 AI 代理工作区文件。减少 token 浪费，修复冗余，检测 AGENTS.md、SOUL.md、USER.md、TOOLS.md、MEMORY.md 中的冲突。 -->

<div align="center">

# openclaw-workspace-audit

**一个 OpenClaw 技能 —— 审计、优化、清理你的 AI 代理工作区：减少 token 浪费、消除冗余、检测冲突、强制合规。**

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](./LICENSE)
[![OpenClaw Skill](https://img.shields.io/badge/OpenClaw-Skill-purple.svg)](https://github.com/openclaw)
[![Zero Dependencies](https://img.shields.io/badge/Dependencies-Zero-brightgreen.svg)]()

[English](./README.md) | 简体中文

</div>

---

## 为什么需要这个技能？

OpenClaw 工作区文件（`AGENTS.md`、`SOUL.md`、`USER.md`、`TOOLS.md`、`MEMORY.md` 等）会在**每次 AI 会话中作为系统提示注入**。随着时间推移，它们会积累各种问题：

| 痛点 | 影响 | 本技能如何解决 |
|------|------|----------------|
| **AGENTS.md 越写越长** | 每次会话都在烧 token | Token 瘦身 — 压缩冗余指令 |
| **跨文件重复规则** | 让 AI 困惑，浪费上下文 | 跨文件冗余检测 |
| **失效的引用** | 指向已不存在的文件/工具 | 死内容扫描器 |
| **SOUL.md 里写了操作指令** | 角色错位 — 错误的文件、错误的行为 | 角色分离检查 |
| **过期的记忆条目** | 过时事实污染每次会话 | 记忆清理 + 归档 |
| **不知道工作区消耗多少 token** | 每条消息都在隐性付费 | 逐文件 token 审计 + 预算目标 |

> **一句话总结** — 你的 OpenClaw 工作区文件就是 AI 代理的「大脑」。这个技能是医生 — 诊断臃肿、发现冲突、开出精准处方，整个过程在你批准之前不会动任何文件。

## 它做什么

### 7 阶段审计流程

```
阶段 0: 预检         → 扫描所有文件，报告大小和 token 估算
阶段 1: 合规检查      → 对照 OpenClaw 官方模板逐项检查
阶段 2: 冗余检测      → 查找跨文件重复/死内容
阶段 3: Token 效率    → 计算节省空间，排序优化机会
阶段 4: 冲突检测      → 捕获文件间矛盾的指令
阶段 5: 报告          → 结构化报告 + 编号操作建议
阶段 6: 执行          → 对已批准的改动进行精确编辑
阶段 7: 记忆清理      → 归档过期记忆，修复命名规范
```

### 审计范围（用户选择）

| 范围 | 说明 |
|------|------|
| **完整审计** | 所有文件、所有检查项 |
| **Token 瘦身** | 专注于减少「始终注入」文件的体积 |
| **记忆清理** | 专注于 `MEMORY.md` + `memory/` 目录维护 |
| **合规检查** | 仅检查格式/规范问题 |
| **单文件审计** | 指定审计某一个文件 |

### 审计的文件

| 文件 | 加载时机 | Token 影响 |
|------|----------|-----------|
| `AGENTS.md` | 每次会话（系统提示） | **高** — 始终注入 |
| `SOUL.md` | 每次会话（系统提示） | **高** — 始终注入 |
| `USER.md` | 每次会话（系统提示） | **高** — 始终注入 |
| `TOOLS.md` | 每次会话（系统提示） | **高** — 始终注入 |
| `IDENTITY.md` | 每次会话（系统提示） | 中等 |
| `HEARTBEAT.md` | 每次心跳轮询 | 低 |
| `BOOT.md` | 网关重启 | 低 |
| `MEMORY.md` | 仅主会话 | **高** |
| `memory/*.md` | 按需通过工具调用 | 低 |

### 安全保证

- **默认只读** — 未经明确批准，绝不修改文件
- **提案优先** — 展示精确 diff 后等待用户确认
- **保持语义** — 每次删除必须证明含义不受影响
- **编号选择** — 每个决策点都可用数字回复
- **不自动调度** — 仅在审计完成后才提议 cron 定时

## 安装

### 一行命令

```bash
mkdir -p ~/.openclaw/skills && cd ~/.openclaw/skills && git clone https://github.com/gaoryan86/openclaw-workspace-audit.git
```

### 分步安装

```bash
# 1. 进入 OpenClaw 技能目录
mkdir -p ~/.openclaw/skills
cd ~/.openclaw/skills

# 2. 克隆此技能
git clone https://github.com/gaoryan86/openclaw-workspace-audit.git

# 3. 重启 OpenClaw（或重新加载技能）
```

### 触发词

安装后，向你的 AI 代理说以下任一句话即可启动：

| English | 中文 |
|---------|------|
| "audit workspace" | "审计文档" |
| "clean up memory" | "清理记忆" |
| "optimize tokens" | "优化 token" |
| "check compliance" | "检查合规" |
| "reduce token waste" | "精简文档" |

## 输出示例

完整审计后，技能会生成结构化报告：

```markdown
## 审计报告 — 2026-03-03

### 摘要
- 审计文件数: 8
- 工作区总 token: ~4.2K
- 发现问题: 11（3 个严重，5 个警告，3 个信息）

### 严重问题（必须修复）
- ❌ AGENTS.md: 347 行（建议上限: ~150 行）
- ❌ AGENTS.md 和 SOUL.md 中存在重复安全规则
- ❌ TOOLS.md 包含技能文档（应在 SKILL.md 中）

### 优化机会
| 改动              | 文件       | Token 节省 | 风险 |
|-------------------|------------|-----------|------|
| 压缩冗余规则       | AGENTS.md | ~280 tokens | 低  |
| 移除失效工具引用    | TOOLS.md  | ~150 tokens | 低  |
| 合并重复安全规则    | SOUL.md   | ~120 tokens | 中  |

### 建议操作（编号）
1. 应用所有安全改动
2. 仅应用严重项
3. 导出计划待后续执行
4. 不做任何改动
```

## Token 预算参考

来自 OpenClaw 官方文档的建议目标：

| 文件 | 建议上限 | 原因 |
|------|---------|------|
| `AGENTS.md` | ~4,000 字符（~1K tokens） | 每次会话都注入 |
| `SOUL.md` | ~2,000 字符（~500 tokens） | 每次会话都注入 |
| `USER.md` | ~1,500 字符（~375 tokens） | 每次会话都注入 |
| `TOOLS.md` | ~3,000 字符（~750 tokens） | 每次会话都注入 |
| `IDENTITY.md` | ~500 字符（~125 tokens） | 设计上就小 |
| `HEARTBEAT.md` | ~500 字符（~125 tokens） | 运行频繁 |
| `MEMORY.md` | ~8,000 字符（~2K tokens） | 仅主会话 |

这些是「意识目标」，不是硬限制。

## 检测的反面模式

本技能会标记这些常见问题：

- `AGENTS.md` 超过 300 行（官方模板约 150 行）
- `SOUL.md` 中包含操作指令（应在 AGENTS.md 中）
- `TOOLS.md` 中包含通用技能文档（应在 SKILL.md 中）
- `MEMORY.md` 中包含原始日志（应在 `memory/` 目录中）
- `HEARTBEAT.md` 超过 30 行（每次心跳都烧 token）
- 工作区文件中包含密钥/API Key
- `memory/` 目录下文件名不符合日期格式
- 跨文件的重复安全规则

## 文件结构

```
openclaw-workspace-audit/
├── SKILL.md     # 技能定义和完整审计流程
├── README.md    # 英文说明
├── README.zh-CN.md  # 本文件
└── LICENSE      # MIT
```

## 适用场景

- **OpenClaw 新用户** — 验证工作区配置是否符合最佳实践
- **拥有大型工作区的资深用户** — 查找并修复长期积累的臃肿
- **关注 token 开销的开发者** — 精确知道每次会话工作区消耗多少 token
- **共享工作区配置的团队** — 强制一致性，捕获冲突
- **定期维护** — 安排每月审计，保持工作区精简

## 常见问题

<details>
<summary><strong>这个技能会自动修改我的文件吗？</strong></summary>

不会。技能默认只读。它会展示精确 diff 的修改提案，等待你明确批准后才执行任何编辑。
</details>

<details>
<summary><strong>支持所有 OpenClaw 版本吗？</strong></summary>

支持。它会引用官方模板并适配工作区中实际存在的文件。缺失的文件会被记录但不会阻断审计。
</details>

<details>
<summary><strong>多久运行一次比较好？</strong></summary>

建议每月一次。技能可以在首次审计后选择性地设置 cron 提醒。
</details>

<details>
<summary><strong>可以只审计一个文件吗？</strong></summary>

可以。在预检阶段选择「单文件审计」范围即可。
</details>

## 贡献

欢迎 PR。请保持技能单文件结构（`SKILL.md`），方便安装。

## 许可证

MIT License，见 [`LICENSE`](./LICENSE)

---

<div align="center">

**openclaw-workspace-audit** — 让你的 AI 代理大脑保持干净高效。

</div>
]]>
