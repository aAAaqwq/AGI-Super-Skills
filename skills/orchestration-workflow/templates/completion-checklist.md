---
tags: [template, gate, checklist, orchestration]
version: v1.0
---

# ✅ Completion Checklist — 门禁清单

> Done = 全部满足。缺一项不算完成。

## 必须满足（硬门禁）

- [ ] **PR 已创建** — `gh pr create --fill`
- [ ] **分支已同步** — 无 merge conflicts
- [ ] **CI 通过** — lint + 类型检查 + 单元测试
- [ ] **E2E 测试通过**（如项目有）
- [ ] **Codex Reviewer 通过** — 无 critical 标记
- [ ] **Gemini Reviewer 通过** — 无安全问题
- [ ] **UI 截图附在 PR 描述**（如有 UI 改动）

## 建议满足（软门禁）

- [ ] Claude Reviewer 无 critical 标记（大部分建议可跳过）
- [ ] 回滚步骤明确（revert commit / feature flag）
- [ ] 性能无明显退化

## 人工 Review 前状态

当以上全部满足后，通知 Human：
> "PR #{N} ready — CI ✅ / Reviewers ✅ / Screenshots ✅"

Human review 预期时间：5-10 分钟。

---
*Template v1.0 | Source: orchestration-protocol.md*
