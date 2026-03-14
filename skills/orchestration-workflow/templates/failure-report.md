---
tags: [template, failure, learning, orchestration]
version: v1.0
---

# ❌ Failure Report — {任务 ID}

## 基本信息
- **任务 ID**: feat-{task}
- **日期**: YYYY-MM-DD
- **Worker**: {谁执行}
- **重试次数**: {N}/3

## 失败类型
<!-- 选一个 -->
- [ ] 需求误解 — Worker 理解错了目标
- [ ] 路径错误 — 找不到文件或改错文件
- [ ] 测试失败 — 代码写了但测试不过
- [ ] Context rot — session 上下文过长导致质量下降
- [ ] 依赖缺失 — 缺少类型定义/接口/环境
- [ ] 权限/安全 — 触碰了禁改文件
- [ ] 其他: {描述}

## 失败现象
{具体发生了什么，CI log / review 评论 / diff 摘要}

## 修正动作
{Orchestrator 怎么调整了 prompt}

### 原始 prompt（摘要）
```
{失败时的 prompt 关键部分}
```

### 修正后 prompt（摘要）
```
{修正后的 prompt 关键部分}
```

## 下次默认策略
{这类失败以后默认怎么防}

---
*归档到 learnings/YYYY-MM-DD-{task}-failure.md*
*Template v1.0 | Source: orchestration-protocol.md*
