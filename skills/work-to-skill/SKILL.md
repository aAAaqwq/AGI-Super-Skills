---
name: work-to-skill
description: 工作即技能：每次完成一项有复用价值的工作后，自动评估并封装为可复用 Skill。让团队在工作中持续进化。
license: MIT
metadata:
  version: 1.0.0
  domains:
  - meta
  - self-improvement
  - skill-creation
  type: automation
author: Daniel Li
---
# Work-to-Skill — 工作即技能

- Author: Daniel Li
- Copyright © Daniel Li. All rights reserved.

> **核心理念：每一次有价值的工作，都可能成为团队永久的能力。**
> 完成任务不是终点，把任务沉淀为 Skill 才是闭环。

## 什么时候触发

**每次完成一项工作后，花 30 秒问自己这 3 个问题：**

| # | 问题 | 判断标准 |
|---|------|---------|
| 1 | **这个工作以后会重复吗？** | 同类任务出现过 ≥2 次，或预期会再出现 |
| 2 | **过程中有可复用的模式吗？** | 有固定步骤、固定命令、固定判断逻辑 |
| 3 | **别的 agent 也可能需要吗？** | 不是只有自己才用得上的一次性操作 |

**满足任意 2 条 → 创建 Skill。**

## 不该做成 Skill 的

- ❌ 一次性的数据查询（"帮我查下今天的天气"）
- ❌ 纯主观判断、没有可复用逻辑的决策
- ❌ 已有现成 Skill 能覆盖的能力（先搜 ClawHub）
- ❌ 涉及密钥/凭据的硬编码操作

## 创建流程

### Step 1: 评估（完成任务后立即）

在任务完成的回复中，附加一段自评：

```
📦 Skill 潜力评估：
- 任务类型：[数据采集/代码开发/内容创作/运维/分析/...]
- 可复用性：[高/中/低]
- 复用场景：[简述谁在什么场景下会再用]
- 判定：[✅ 值得封装 / ❌ 一次性任务]
```

### Step 2: 提取核心模式

从刚完成的工作中提取：
1. **输入**：这个任务需要什么输入？（参数/文件/URL/...）
2. **步骤**：核心步骤是什么？（按顺序列出）
3. **输出**：产出物是什么？（文件/消息/数据/...）
4. **踩坑点**：过程中有什么容易出错的地方？

### Step 3: 写 SKILL.md

在 `skills/<skill-name>/` 下创建：

```
<skill-name>/
├── SKILL.md          # 技能文档（必需）
├── scripts/          # 脚本（如有）
│   └── main.py/.sh/.js
└── examples/         # 示例（如有）
```

**SKILL.md 模板：**

```yaml
---
name: <skill-name>
description: "<一句话：做什么 + 什么场景用>"
license: MIT
metadata:
  version: 1.0.0
  domains: [<领域标签>]
  type: automation
---

# <Skill 名称>

## 什么时候用
- 场景 1
- 场景 2

## 使用方法

### 前置条件
- 需要的 API key / 工具 / 环境

### 步骤
1. ...
2. ...
3. ...

### 示例
```（具体命令或调用方式）```

## 注意事项
- 踩坑点 1
- 踩坑点 2

## 触发词
- "关键词1"
- "关键词2"（中英双语）
```

### Step 4: 注册到对应 Agent

如果 Skill 是通用的 → 放 `skills/`（全局生效）
如果 Skill 是某个角色专用的 → 放 `skills/` 并配到对应 agent 的 `agent.json`

### Step 5: 汇报

在在团队渠道中简要汇报新 Skill：
```
📦 新 Skill 已创建：<skill-name>
- 功能：一句话描述
- 位置：路径
- 适用：哪些 agent
- 来源：从什么任务中提炼的
```

## 质量标准

一个好的 Skill 必须满足：
- [ ] **自包含**：读 SKILL.md 就能直接用，不需要问别人
- [ ] **有示例**：至少一个完整的使用示例
- [ ] **有踩坑**：写明容易出错的地方和解决方案
- [ ] **无密钥**：所有密钥通过 `pass show` 引用，绝不硬编码
- [ ] **有触发词**：中英文触发词，方便 Agent 匹配

## 进阶：Skill 迭代

使用中发现 Skill 不好用？直接更新：
1. 修改 SKILL.md
2. 更新 version 号
3. 在团队渠道中通知：`📦 Skill 更新：<name> v1.0 → v1.1，改了什么`

## 反模式（绝对不要）

| ❌ 反模式 | ✅ 正确做法 |
|----------|-----------|
| Skill 里写死 API key | `pass show api/xxx` |
| 一个 Skill 做 10 件事 | 拆成多个聚焦的 Skill |
| 写了 Skill 但没人知道 | 群里汇报 + 更新团队记忆或相关文档 |
| 把所有代码都做成 Skill | 只做有复用价值的 |
| Skill 没有使用示例 | 至少一个可运行的 example |

## 触发词

- "创建 skill"、"封装技能"、"做成 skill"
- "这个以后还会用"、"这个可以复用"
- "create skill"、"package as skill"、"make reusable"
- "工作沉淀"、"能力封装"
