---
name: domestic-acquisition
description: 聚焦中国大陆市场客户获取与线索转化的模块化 skills 包索引。用于规划、创建、验收和迭代国内获客相关子模块，如企业线索采集、社媒引流、私域转化、竞品监控、客户画像与触达自动化。
---

# 国内获客 Skills 包 v1

> 聚焦中国大陆市场的客户获取与线索转化，模块化可验收。

## 包结构

```
domestic-acquisition/
├── SKILL.md              ← 本文件（包索引 + 总览）
├── modules/              ← 子 skill 模块目录（逐个创建、逐个验收）
├── scripts/              ← 自动化脚本（跨模块复用）
├── templates/            ← 可复用模板
├── data/                 ← 静态数据/配置
└── references/           ← 参考资料
```

## 模块清单

| # | 模块名 | 路径 | 状态 | 负责人 |
|---|--------|------|------|--------|
| 1 | 企业线索采集 | `modules/lead-mining/SKILL.md` | ✅ 已验收 | 小data |
| 2 | 社媒引流运营 | `modules/social-funnel/SKILL.md` | ⬜ 待创建 | 小content |
| 3 | 私域转化话术 | `modules/private-traffic/SKILL.md` | ⬜ 待创建 | 小content |
| 4 | 竞品情报监控 | `modules/competitor-intel/SKILL.md` | ⬜ 待创建 | 小research |
| 5 | 客户画像构建 | `modules/customer-profile/SKILL.md` | ⬜ 待创建 | 小research |
| 6 | BD触达自动化 | `modules/outreach-automation/SKILL.md` | ⬜ 待创建 | 小market |

## 统一 Skill 规范

每个子模块 SKILL.md 统一基于模板创建：

- 模板路径：`templates/module-skill-template.md`
- 原则：单模块只解决一个问题；输入/输出/验收标准必须可量化；依赖关系必须显式写清。
- 状态推进：`待创建 → 草稿 → 可验收 → 已验收`

最小必备章节：

```markdown
## 模块元信息
## 目标
## 触发条件
## 输入
## 执行步骤
## 输出
## 验收标准
## 依赖
## 失败处理
```

其中 `模块元信息` 固定承载：状态、负责人、上游输入模块、下游输出模块、默认输出路径。用于统一结构、明确边界、方便逐个验收。

模块边界统一规范见：`references/module-boundaries.md`。

## 阅读 / 验收顺序

统一按以下顺序进入与验收，避免结构漂移：

1. 先读本文件，确认模块清单、状态与统一章节要求。
2. 再读 `references/module-boundaries.md`，确认该模块负责/不负责什么。
3. 如模块涉及结构化线索，再读 `references/lead-record-schema.md`，禁止自造字段名。
4. 创建新模块时从 `templates/module-skill-template.md` 起步，不从旧模块复制粘贴。
5. 验收时按“结构完整性 → 边界清晰度 → 输出可复用性”顺序逐项检查。

## 迭代日志

| 时间 | 增量 | 状态 |
|------|------|------|
| 2026-03-25 20:38 | 初始化包结构 + 模块清单 + 统一规范 | ✅ 完成 |
| 2026-03-25 20:58 | 新增子模块统一模板 `templates/module-skill-template.md`，补齐目标/失败处理/状态推进规范 | ✅ 完成 |
| 2026-03-25 21:16 | 将 `modules/`、`scripts/`、`data/`、`references/` 目录实际落地，包结构与索引声明对齐 | ✅ 完成 |
| 2026-03-25 21:21 | 新建首个子模块 `modules/lead-mining/SKILL.md`，补齐输入/输出/验收标准并推进到可验收 | ✅ 完成 |
| 2026-03-25 21:26 | 统一子模块元信息结构：模板与 `lead-mining` 增加“模块元信息”，固定状态/负责人/上下游/默认输出路径字段 | ✅ 完成 |
| 2026-03-25 21:51 | 完成首个模块 `lead-mining` 首次验收闭环，状态推进为“已验收”，补充验收记录 | ✅ 完成 |
| 2026-03-25 21:56 | 抽离跨模块线索字段规范 `references/lead-record-schema.md`，并让 `lead-mining` 输出显式引用，提升可复用性 | ✅ 完成 |
| 2026-03-25 22:14 | 新增包级模块边界规范 `references/module-boundaries.md`，并让包索引与 `lead-mining` 显式引用，统一职责切分口径 | ✅ 完成 |
| 2026-03-25 22:24 | 统一子模块模板的边界与字段复用钩子：模板默认引用 `module-boundaries.md` 与 `lead-record-schema.md`，降低后续模块结构漂移 | ✅ 完成 |
