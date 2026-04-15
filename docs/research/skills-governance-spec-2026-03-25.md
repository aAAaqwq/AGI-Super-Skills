# skills 三层架构治理规范（草案）

- 版本：draft v0.1
- 日期：2026-03-25
- 状态：待评审
- 适用范围：skills 资产的新增、迁移、重构、审核、回滚

---

## 0. 目标与原则

### 0.1 目标

本规范用于解决 skills 资产长期混放、重复、命名失控、职责不清的问题。治理后，skills 必须稳定落入三层之一：

1. **agent 层**：面向某一类 agent 角色的行为约束、工作流、偏好和接口封装
2. **global 层**：跨项目、跨 agent 可复用的通用能力
3. **workspace 层**：某个项目/工作区特有的编排、集成和业务上下文

### 0.2 核心原则

- **能力归 global，配置归 agent，项目编排归 workspace**
- **宁可薄封装，不要重复实现**
- **一份能力只保留一个权威来源（single source of truth）**
- **目录先行，命名强约束，迁移可回滚**
- **没有通过放置判定流程的 skill，不得落库**

### 0.3 三分法总纲

在新增或迁移任一 skill 前，先回答三个问题：

1. 这是在定义 **谁来做**（角色/行为/偏好）？→ 倾向 **agent**
2. 这是在定义 **能做什么**（可复用能力）？→ 倾向 **global**
3. 这是在定义 **在某项目里如何串起来做**（项目编排/约束/上下文）？→ 倾向 **workspace**

---

## 1. 三层定义

## 1.1 Agent 层

### 定义

agent 层 skill 用于描述某一类 agent 的：

- 角色职责
- 输入输出约束
- 行为边界
- 使用哪些 global 能力
- 在什么顺序/风格下工作
- 与 workspace 的交互约定

### 典型内容

- PM agent 的交付格式要求
- reviewer agent 的审查清单
- researcher agent 的输出模板
- 某类 agent 的安全边界、升级路径、协作约定

### 非职责范围

agent 层 **不得** 承载：

- 具体业务规则
- 某个项目专属流程
- 通用能力本体实现
- 与多个项目重复复用的通用 schemas/shared/skills 内容

### 判定口径

如果删掉某个项目上下文，这个 skill 仍然成立；但删掉 agent 角色定义后就不成立，则应归入 **agent 层**。

---

## 1.2 Global 层

### 定义

global 层 skill 是可跨项目、跨 workspace、跨 agent 复用的通用能力资产。

### 典型内容

- GitHub 操作能力
- Notion 能力
- 浏览器自动化能力
- 调研、总结、代码审查、测试、发布等可复用方法论
- 通用模板、共享 schema、公共术语定义

### 非职责范围

global 层 **不得** 承载：

- 某个 agent 的角色偏好或语气规范
- 某个 workspace 的业务流程编排
- 某项目私有路径、私有环境变量约定、专属 SOP

### 判定口径

如果一个能力可以被两个及以上项目直接复用，并且不依赖特定业务上下文，则应归入 **global 层**。

---

## 1.3 Workspace 层

### 定义

workspace 层 skill 用于承载某个项目/工作区专属的：

- 业务上下文
- 项目流程编排
- 项目私有约束
- 项目集成方式
- 项目专属模板、目录、交付约定

### 典型内容

- 某产品线的内容生产 SOP
- 某项目的发布编排
- 某工作区的报告模板和命名规则
- 调用多个 global 能力形成的项目级工作流

### 非职责范围

workspace 层 **不得** 承载：

- 已经存在于 global 的通用能力副本
- 与项目无关的抽象方法论
- 某个 agent 的纯角色定义

### 判定口径

如果 skill 强依赖项目背景、目录、数据源、业务口径或交付物格式，离开该 workspace 就失效，则应归入 **workspace 层**。

---

## 2. 命名规范

## 2.1 命名总则

所有 skill 名称必须满足：

- 小写英文与连字符 `-`
- 禁止空格、下划线、中文、括号
- 名称表达“定位 + 作用”，避免模糊抽象词
- 名称应体现其所属层级

---

## 2.2 Agent 层命名

### 规范

统一前缀：`agent-<role>-<capability-or-workflow>`

### 模板

```text
agent-<role>-<topic>
```

### 示例

- `agent-pm-delivery-governance`
- `agent-reviewer-code-quality`
- `agent-researcher-source-triage`
- `agent-ops-release-guardrails`

### 检查清单

- [ ] 是否包含 `agent-` 前缀
- [ ] 是否明确角色 `<role>`
- [ ] 名称是否描述该角色特有职责，而不是通用能力
- [ ] 是否避免把项目名塞进 agent 名称

---

## 2.3 Workspace 层命名

### 规范

统一前缀：`ws-<project>-<workflow-or-module>`

### 模板

```text
ws-<project>-<topic>
```

### 示例

- `ws-clawhub-skill-publishing`
- `ws-opencaio-reporting-flow`
- `ws-xhs-content-pipeline`
- `ws-quant-backtest-handoff`

### 检查清单

- [ ] 是否包含 `ws-` 前缀
- [ ] 是否明确 `<project>`
- [ ] 是否体现项目专属性，而非通用能力
- [ ] 是否避免用泛词如 `process`, `misc`, `helper`

---

## 2.4 Global 层命名

### 规范

global 层**不加层级前缀**，直接使用能力名。

### 模板

```text
<capability-name>
```

### 示例

- `github`
- `notion`
- `summarize`
- `coding-agent`
- `verification-before-completion`

### 检查清单

- [ ] 是否是跨项目可复用能力
- [ ] 是否不带 `agent-` / `ws-` 前缀
- [ ] 名称是否足够稳定，避免绑死某个项目或角色

---

## 2.5 禁止命名模式

以下命名一律禁止：

| 禁止模式 | 原因 | 示例 |
|---|---|---|
| `agent-xxx-project-yyy` | agent 层混入项目语义 | `agent-pm-clawhub-publish` |
| `ws-xxx-github` | workspace 层包装通用能力名 | `ws-opencaio-github` |
| `global-xxx` | global 不需要前缀 | `global-summary` |
| `misc` / `utils` / `helper` | 语义不清，不可治理 | `ws-foo-helper` |
| 同义重复命名 | 形成多源真相 | `summarize` / `summary-helper` |

---

## 3. 目录规范

## 3.1 标准目录骨架

三层架构必须统一收敛到以下骨架：

```text
<root>/
  agent/
    <role>/
      skills/
  global/
    skills/
    schemas/
    shared/
  workspace/
    <project>/
      skills/
      schemas/
      shared/
```

其中治理关注的最小标准目录为：

- `schemas/`
- `shared/`
- `skills/`

---

## 3.2 目录职责

| 目录 | 职责 | 可放内容 | 不可放内容 |
|---|---|---|---|
| `skills/` | skill 定义与说明 | SKILL.md、轻量 supporting docs | 大量业务数据、临时草稿 |
| `schemas/` | 结构定义 | JSON schema、YAML schema、字段规范 | 操作流程、角色说明 |
| `shared/` | 当前层内共享素材 | 模板、术语表、公共示例、复用片段 | 技能入口定义本体 |

---

## 3.3 目录放置规则

### Global

```text
global/
  skills/
  schemas/
  shared/
```

适用：跨项目复用的公共能力、公共 schema、公共模板。

### Agent

```text
agent/
  <role>/
    skills/
```

适用：角色相关 skill。agent 层默认**不单独发展项目业务 schemas/shared**；如确需复用模板，应优先引用 global/shared。

### Workspace

```text
workspace/
  <project>/
    skills/
    schemas/
    shared/
```

适用：项目特有编排、项目特有 schema、项目特有共享模板。

---

## 3.4 目录检查清单

- [ ] 每个 workspace 必须具备 `skills/` 目录
- [ ] 只要存在项目特有结构定义，必须落 `schemas/`
- [ ] 只要存在项目特有模板/示例/共享片段，必须落 `shared/`
- [ ] 通用能力不得散落在多个 workspace 的 `skills/`
- [ ] global 的 schema/template 不得复制到 workspace，除非经过显式覆写审批

---

## 4. 放置判定流程（配置 / 能力 / 项目编排三分法）

## 4.1 先做分类，再决定层级

任何 skill 在创建或迁移前，先判定它属于以下哪一类：

1. **配置类（Configuration）**
2. **能力类（Capability）**
3. **项目编排类（Project Orchestration）**

---

## 4.2 判定定义

| 分类 | 判断问题 | 默认归属层 |
|---|---|---|
| 配置类 | 它是在定义某类 agent 如何工作、遵循什么边界、输出什么格式吗？ | agent |
| 能力类 | 它是在定义一个跨项目可复用的能力或方法吗？ | global |
| 项目编排类 | 它是在定义某项目里如何组合多个能力完成业务目标吗？ | workspace |

---

## 4.3 决策表（强制使用）

| 判定题 | 是 | 否 |
|---|---|---|
| Q1. 是否强依赖具体项目名、目录、数据源、业务口径？ | 去 Q2（大概率 workspace） | 去 Q3 |
| Q2. 去掉该项目上下文后，skill 是否失效？ | **workspace** | 去 Q3 |
| Q3. 是否定义某个 agent 角色的职责、风格、边界、交付形式？ | **agent** | 去 Q4 |
| Q4. 是否可被两个及以上项目直接复用，且不依赖单一项目上下文？ | **global** | 去 Q5 |
| Q5. 是否只是把多个 global 能力按某项目顺序串起来？ | **workspace** | 去 Q6 |
| Q6. 是否只是某 agent 对 global 能力的使用约束/偏好？ | **agent** | 需要架构评审 |

---

## 4.4 快速决策 checklist

### 如果满足以下任意两项，优先归 agent

- [ ] 以角色为中心，而不是以项目为中心
- [ ] 主要内容是职责、约束、交付要求
- [ ] 可引用 global 能力，但不实现能力本体
- [ ] 脱离某项目仍然有效

### 如果满足以下任意两项，优先归 global

- [ ] 可跨两个及以上项目复用
- [ ] 主要内容是方法、工具、能力、通用模板
- [ ] 不绑定某个 agent 角色
- [ ] 不依赖单一 workspace 的数据或业务语境

### 如果满足以下任意两项，优先归 workspace

- [ ] 含项目名、业务名、专属路径或交付物命名规则
- [ ] 本质是项目 SOP / 流程编排 / 集成约定
- [ ] 复用了多个 global skill，但顺序和约束由项目决定
- [ ] 离开该项目没有意义

---

## 4.5 典型案例判定

| 场景 | 正确层级 | 原因 |
|---|---|---|
| “PM agent 输出周报时必须带风险/阻塞/决策” | agent | 这是角色交付规范 |
| “GitHub issue 创建与 PR 审查方法” | global | 通用能力 |
| “ClawHub 项目里如何串联 summarize + github + notion 出报告” | workspace | 项目编排 |
| “某项目专用报告字段 schema” | workspace/schemas | 项目结构定义 |
| “多个项目共享的报告 schema” | global/schemas | 公共结构定义 |
| “reviewer 角色如何调用 code-review-quality” | agent | 角色使用约束 |

---

## 5. 禁止事项

以下事项一律禁止，发现即整改。

## 5.1 Agent 层禁止事项

- [ ] 在 agent 层写项目业务逻辑
- [ ] 在 agent 层放项目专属 SOP
- [ ] 在 agent 层复制 global 能力全文
- [ ] 在 agent 层定义项目专属 schema/template
- [ ] 用 agent 层替代 workspace 编排层

### 明确禁止示例

| 禁止行为 | 为什么错 |
|---|---|
| `agent-pm-clawhub-publish` 内写 ClawHub 发布 SOP | agent 混入项目逻辑 |
| `agent-reviewer-github` 复制 GitHub 通用能力内容 | 重复 global |
| 在 agent 目录保存项目字段 schema | 配置层污染结构层 |

---

## 5.2 Workspace 层禁止事项

- [ ] 复制 global 能力形成“本地副本”
- [ ] 将通用能力改名后冒充项目能力
- [ ] 用 workspace 承载纯角色规范
- [ ] 多个 workspace 分别维护同一通用 schema
- [ ] 在 workspace 写与项目无关的方法论 skill

### 明确禁止示例

| 禁止行为 | 为什么错 |
|---|---|
| 在 `ws-opencaio-*` 下复制 `summarize` | workspace 复制 global 能力 |
| `ws-foo-github-review` 实际只是 GitHub 通用操作 | 应上提 global |
| 三个 workspace 各自维护同一报告 schema | 失去 single source of truth |

---

## 5.3 Global 层禁止事项

- [ ] 写死项目目录、项目变量、项目口径
- [ ] 写死某个 agent 的角色偏好
- [ ] 将项目编排伪装成通用能力
- [ ] 接受未经抽象就直接上提的项目私货

---

## 5.4 治理红线总表

| 红线 | 处理动作 |
|---|---|
| agent 层出现业务逻辑 | 必迁出到 workspace 或拆分 |
| workspace 复制 global 能力 | 删除副本，改为引用 |
| global 带项目耦合 | 下沉到 workspace，或抽象后重建 |
| 命名不符合规范 | 统一重命名并做映射 |
| 无法判断归属 | 提交架构评审，不得直接落库 |

---

## 6. 实施规范

## 6.1 新增 skill 的准入 checklist

- [ ] 已完成“配置 / 能力 / 项目编排”三分法判定
- [ ] 已使用 4.3 决策表给出归属结论
- [ ] 命名符合层级规范
- [ ] 目录落点符合 `schemas/shared/skills` 规范
- [ ] 未复制已有 global 能力
- [ ] 若为 workspace skill，已明确其引用的 global skill 列表
- [ ] 若为 agent skill，已明确其服务角色与边界
- [ ] 若存在争议，已提交架构评审记录

---

## 6.2 迁移现有 skill 的执行 checklist

- [ ] 盘点现有 skill 清单
- [ ] 标注当前路径、建议层级、建议名称
- [ ] 识别重复项与同义项
- [ ] 先抽 global，再瘦身 agent，再收敛 workspace
- [ ] 为重命名/迁移建立映射表
- [ ] 保留至少一轮回滚窗口
- [ ] 完成消费者验证后再清理旧路径

---

## 6.3 映射表最小格式

| 旧路径/旧名 | 新层级 | 新路径/新名 | 迁移动作 | 回滚方式 |
|---|---|---|---|---|
| `old-a` | global | `global/skills/github` | move | restore old symlink |
| `old-b` | workspace | `workspace/foo/skills/ws-foo-publish-flow` | split + move | revert mapping |

---

## 7. Phase 1 / Phase 2 / 回滚门槛

## 7.1 Phase 1：结构收敛（不大改内容）

### 目标

先把“放在哪、叫什么、谁拥有”收敛掉，不追求一次性内容重写。

### 范围

- 建立三层目录骨架
- 完成命名规范落地
- 为现有 skill 建立归属清单
- 识别重复能力与错误放置
- 建立旧名到新名映射

### Phase 1 完成标准 checklist

- [ ] 100% skill 已标注归属层级
- [ ] 100% 新增命名符合规范
- [ ] 三层目录骨架已建立
- [ ] 重复能力清单已产出
- [ ] 高风险错放项已识别
- [ ] 迁移映射表已形成
- [ ] 至少完成一轮抽样消费者验证

### Phase 1 不做的事

- 不强制重写全部 skill 内容
- 不一次性清除所有旧文件
- 不在无映射和无验证的情况下硬切换

---

## 7.2 Phase 2：内容治理（抽象、去重、引用化）

### 目标

在结构稳定后，处理内容层面的重复、耦合和抽象不足问题。

### 范围

- 抽取通用能力到 global
- 删除 workspace 对 global 的复制
- 把 agent 中的业务逻辑下沉到 workspace
- 将 schema/template 按 `schemas/shared/skills` 归位
- 将项目编排显式改写为“引用 global + 项目补充”结构

### Phase 2 完成标准 checklist

- [ ] 重复 global 能力副本已消除
- [ ] agent 中业务逻辑已迁出
- [ ] workspace skill 改为编排而非复制能力
- [ ] 公共 schema 已上提到 global/schemas
- [ ] 项目特有 schema 已收敛到 workspace/schemas
- [ ] 公共模板已收敛到 global/shared
- [ ] 每个 workspace 只保留项目差异化内容

---

## 7.3 回滚门槛

只有满足以下任一条件，才触发回滚：

| 回滚触发条件 | 门槛 |
|---|---|
| 消费方无法在约定时间内定位关键 skill | 关键路径失败率 ≥ 20% |
| 迁移后出现大面积命名失配/引用断裂 | 影响 2 个及以上 workspace 或 2 个及以上 agent |
| 关键交付流程不可用 | 连续 1 个工作日无法恢复 |
| 无法确认 single source of truth | 同一能力出现 2 个及以上活跃写入口 |
| 迁移成本超过治理收益 | 经评审确认需要暂停并回退 |

### 回滚动作 checklist

- [ ] 恢复旧路径映射或别名
- [ ] 暂停删除旧 skill 文件
- [ ] 回退最新一批迁移提交
- [ ] 标注失败原因：命名 / 目录 / 引用 / 归属判定
- [ ] 补充判定规则后再重启迁移

---

## 8. 审核机制

## 8.1 新增审核

任一新增 skill 必须经过以下审核：

| 审核项 | 必须回答的问题 |
|---|---|
| 层级审核 | 为什么是 agent/global/workspace，而不是另外两层？ |
| 命名审核 | 是否符合强制命名模式？ |
| 目录审核 | 是否正确落入 `schemas/shared/skills` 之一？ |
| 去重审核 | 是否已检查现有同类能力？ |
| 依赖审核 | 是否明确依赖哪些 global skill？ |

---

## 8.2 迁移审核

- [ ] 是否有旧新映射表
- [ ] 是否有消费者影响面评估
- [ ] 是否有回滚预案
- [ ] 是否完成抽样验证
- [ ] 是否避免“边迁移边新增重复”

---

## 9. 最终执行口径（可直接宣贯）

### 一句话版本

> skills 只分三层：**agent 管角色配置，global 管通用能力，workspace 管项目编排**。

### 落地口径

- 能力本体，放 **global**
- 角色约束，放 **agent**
- 项目流程，放 **workspace**
- 公共结构，放 **global/schemas**
- 项目结构，放 **workspace/<project>/schemas**
- 公共模板，放 **global/shared**
- 项目模板，放 **workspace/<project>/shared**

### 不允许再争论的红线

- agent 层不放业务逻辑
- workspace 不复制 global 能力
- global 不携带项目耦合
- 命名不符合规范不得入库
- 判定不清先评审，不允许“先放着再说”

---

## 10. 附：简版决策卡（适合贴在 PR 模板）

### 新 skill 决策卡

- [ ] 它是在定义角色怎么做事？→ `agent-<role>-...`
- [ ] 它是在定义通用能力？→ `global/<ability>`
- [ ] 它是在定义某项目如何编排能力？→ `ws-<project>-...`
- [ ] 它是否需要 `schemas/`？
- [ ] 它是否需要 `shared/`？
- [ ] 它是否复制了已有 global？如果是，停止提交
- [ ] 它是否把业务逻辑放进 agent？如果是，停止提交

---

## 11. 建议的下一步（供主负责人决策）

1. 先做一次 **全量 inventory**，给所有现有 skill 打三层标签
2. 先执行 **Phase 1**，只收敛命名、目录、归属，不重写内容
3. 选 1 个 workspace 试点执行 **Phase 2**，验证“引用 global、保留项目差异”可行性
4. 验证通过后，再推广到其他 workspace
