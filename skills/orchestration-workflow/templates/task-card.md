---
tags: [template, task-card, orchestration]
version: v1.1
updated: 2026-03-03
changelog: v1.1 新增 contracts + assumption checklist（防假设漂移）
---

# 📋 Task Card — {任务名}

## 基本信息
- **ID**: feat-{task-name}
- **日期**: YYYY-MM-DD
- **优先级**: P0/P1/P2
- **风险等级**: 普通 / 高风险（跨服务/数据库迁移）
- **Orchestrator**: {谁编排}
- **Worker**: {谁执行}（参考 agent-matrix.md）

## 目标
{一句话描述要做什么}

## 非目标
{明确不做什么，防止 Worker 跑偏}
- ❌ 不要 ...
- ❌ 不要 ...

## 上下文
- **项目**: {repo name}
- **分支**: feat/{task-name}
- **相关文件**:
  - `src/path/to/file1.ts`
  - `src/path/to/file2.ts`
- **类型定义**: `src/types/xxx.ts`（关键 interface）
- **业务背景**: {为什么做这个，给谁用}

## Contracts（依赖契约）

### Upstream（我依赖谁）
| 来源 | 接口/数据格式 | 状态 |
|------|-------------|------|
| {上游模块} | {输入格式，如 `{ type: "COMMENT", userId: string }`} | ✅ 已确认 / ⚠️ 待确认 |

### Downstream（谁依赖我）
| 消费方 | 期望输出 | 状态 |
|--------|---------|------|
| {下游模块} | {输出格式} | ✅ 已确认 / ⚠️ 待确认 |

> 无跨模块依赖的单文件任务可留空。

## Assumption Checklist（假设问答）
<!-- 普通任务 ≥5 条；高风险任务 ≥8 条 -->
<!-- Orchestrator 必须在发给 Worker 前填完 -->

1. **Q**: {关键假设问题1}  **A**: {确认的答案}
2. **Q**: {关键假设问题2}  **A**: {确认的答案}
3. **Q**: {关键假设问题3}  **A**: {确认的答案}
4. **Q**: {关键假设问题4}  **A**: {确认的答案}
5. **Q**: {关键假设问题5}  **A**: {确认的答案}

> 典型问题：用什么框架版本？错误处理走哪种模式？命名规范？测试用哪个 runner？数据格式是什么？

## 依赖（v1.3 新增）
- depends_on: {前置任务 ID，如 T08, T09；无依赖写 "none"}
- 合并策略: {merge 顺序说明，或 "独立"}

## 约束
- 不要修改 {禁止文件/目录}
- 测试文件在 {test path}
- 风格遵循 {lint 规则}
- 提交格式：conventional commits

## 质量约束（v1.3 新增）
- [ ] 无硬编码常量（提取到 config/constants）
- [ ] 交互组件有 loading 状态
- [ ] 异步操作有 error handling
- [ ] 表单有基础验证
- [ ] 公共组件有 JSDoc 注释
- [ ] 无通用占位链接

## 验收标准
- [ ] 功能实现并通过测试
- [ ] `gh pr create --fill`
- [ ] CI 全绿
- [ ] UI 变更附截图（如有）
- [ ] 编排层 review 通过
- [ ] **即使触发 Stop Condition，也必须写 run report**

## 风险点（最多 3 条）
1. {风险1}
2. {风险2}
3. {风险3}

---
*Template v1.1 | Source: orchestration-protocol.md*
