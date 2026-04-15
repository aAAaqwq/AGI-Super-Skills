# 团队架构优化报告 2026-03-08

## 一、现状诊断

### 🔴 严重问题

| # | 问题 | 影响 | 原因 |
|---|------|------|------|
| 1 | **ZAI glm-4.7 频繁429限流** | 所有agent主模型不可用，全靠fallback | Coding plan并发限制 |
| 2 | **Session文件膨胀** | quant 42MB/144个session, ops 13MB/54个 | 无自动清理，context token飙升 |
| 3 | **SOUL.md/MEMORY.md 为空** | Agent无身份认知、无记忆积累 | 创建了文件但未写入内容 |
| 4 | **Fallback链不一致** | 部分agent fallback到昂贵的opus-4-6 | 手动配置不统一 |
| 5 | **glm-5作为fallback第一位** | 限流模型在fallback链里也会触发429 | 配置未更新 |

### 🟡 效率问题

| # | 问题 | 影响 |
|---|------|------|
| 6 | sessions_send 默认timeout太短 | 大部分请求返回timeout（实际agent在后台成功） |
| 7 | Agent AGENTS.md 99行相同模板 | 通用但缺乏角色特化的协作指引 |
| 8 | 无任务队列/优先级机制 | CEO串行派活，无法高效并发调度 |
| 9 | Skills过多（quant 14个） | 增加prompt体积，降低响应速度 |

## 二、优化方案

### A. 模型策略优化（立即执行）

**分层模型策略：**

| 层级 | 模型 | 用途 | 成本 |
|------|------|------|------|
| **主力** | `minimax/MiniMax-M2.5` | 日常任务，稳定可靠 | 低 |
| **推理** | `zai/glm-4.7` | 需要深度思考时 | 中 |
| **高端** | `moonshot/kimi-k2.5` | 复杂分析，中文优化 | 中 |
| **顶级** | `xingsuancode/claude-opus-4-6` | 仅code/quant关键任务 | 高 |

**统一Fallback链：**
```
主力: minimax/MiniMax-M2.5
fallback: [zai/glm-4.7, moonshot/kimi-k2.5, xingjiabiapi/gemini-3-pro-preview]
```

code/quant 特殊链（需要强推理）：
```
主力: minimax/MiniMax-M2.5
fallback: [zai/glm-4.7, moonshot/kimi-k2.5, xingsuancode/claude-opus-4-6]
```

### B. Session清理（立即执行）

- 删除超过7天的session文件
- 设置定期清理cron

### C. Agent身份强化（立即执行）

为每个agent写入SOUL.md，明确：
- 角色定位和专长
- 工作风格和输出标准
- 与其他agent的协作接口

### D. 通信效率优化

- sessions_send 不带 timeoutSeconds（fire-and-forget模式）
- agent完成后自动发群里（已有机制）
- CEO不等回复，批量派发后统一收结果

### E. Skills精简

移除重复/不活跃的skills，每个agent保留核心5-8个

## 三、实施清单

- [x] A. 模型策略 — 全部切M2.5主力 + 统一fallback
- [x] B. Session清理 — 清理旧文件
- [x] C. SOUL.md — 9个agent写入身份
- [x] D. 通信规范 — 更新AGENTS.md调度原则
- [ ] E. Skills精简 — 后续逐步优化
