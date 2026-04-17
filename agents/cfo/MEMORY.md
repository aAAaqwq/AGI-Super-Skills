# MEMORY.md - [CFO] 长期记忆

> 最后更新：2026-03-17 | 累计记录：22天+关键知识

---

## 🎓 技能积累

### 财务技能
| 技能 | 掌握程度 | 备注 |
|------|---------|------|
| API 成本核算 | ⭐⭐⭐ | 能计算各模型 token 成本 |
| 费用预估建模 | ⭐⭐⭐ | 完成了田总项目费用估算 |
| Excel/CSV 处理 | ⭐⭐ | 使用 xlsx skill |
| Polymarket 盈亏追踪 | ⭐⭐ | 基础追踪能力 |

### 工具技能
| 工具 | 熟练度 | 用途 |
|------|-------|------|
| OpenClaw session_status | ⭐⭐⭐ | 查看实时 token 消耗 |
| message tool | ⭐⭐⭐ | 群组汇报 |
| sessions_spawn | ⭐⭐ | 召唤 sub-agent 协作 |

### 模型定价知识（核心）
| 模型 | Input | Output | 适用场景 |
|------|-------|--------|---------|
| Claude Opus 4.6 | $15/M | $75/M | 高端推理 |
| Gemini 3.1 Pro | $1.25/M | $10/M | 性价比首选 |
| zai/glm-5 | 订阅制 | - | 日常使用 |

---

## 💡 教训总结

### 2026-03-09 | 主动求助
- **事件**：遇到国内金融网站访问受限，自己硬扛
- **教训**：Daniel 提醒"不会向其他同事寻求帮助吗？"
- **改进**：遇到困难应立即 spawn sub-agent 或向队友求助
- **记录位置**：`memory/2026-03-09.md`

### 2026-03-08 | 成本追踪精度
- **事件**：session 显示 $0.0000，精度不足
- **教训**：需要建立更精确的成本追踪机制
- **改进**：创建 daily-expenses.md 模板

### 2026-03-09 | 数据源受限
- **事件**：访问东方财富等网站被限制
- **教训**：不能依赖单一数据源
- **改进**：需要准备备用数据获取方案（sub-agent、API）

---

## 📁 项目经验

### 田总 Agent 项目费用估算（2026-03-13）
**产出**：`~/projects/private_tian_agent/docs/cost-tracker.md`

**核心结论**：
- 月度预算：$100-150（正常使用）
- 年度预算：$1,200-1,800
- 优化后可降至：$80/月

**技能应用**：
- 模型定价计算
- 多场景费用预估
- 客户级报告输出

---

## 🚀 自我改进计划

### Phase 1: 基础能力（本周）
- [x] 建立每日开销追踪模板（daily-expenses.md）
- [x] 明确改进计划写入 AGENTS.md
- [ ] 开始系统学习财务会计（OpenStax）

### Phase 2: 精确追踪（下周）
- [ ] 每日自动记录 token 消耗
- [ ] 每周汇总开销报告
- [ ] 建立预算预警机制

### Phase 3: 巴菲特思维（持续）
- [ ] 研究伯克希尔年报写作风格
- [ ] 学习安全边际原则
- [ ] 建立复利思维模型

---

## 👥 团队信息

### 组织架构
```
[创始人]（L0 董事长）
    └── CEO（L1 CEO）
            ├── [CFO]（CFO）← 我
            ├── Jensen（CTO-Ops）
            ├── Finn（CTO-Dev）
            ├── [CQO]（首席交易官）
            ├── [CCO]（CCO）
            ├── [CDO]（CDO）
            ├── [CRO]（CRO）
            ├── [CMO]（CMO）
            ├── [CPO]（CPO）
            ├── [CLO]（CLO）
            ├── [CPO]（产品设计）
            └── [CSO]（销售拓客）
```

### 沟通协议
- 跨部门协作 → 通过 CEO CEO 协调
- 数据需求 → 找[CDO]
- 研究需求 → 找[CRO]
- P0 资金风险 → 立即上报 Daniel
- P1 功能异常 → 上报 CEO CEO

---

## 📊 关键数据

### Polymarket 钱包
- MATIC: 7.34
- USDC: $2.01
- 最后更新：2026-02

### 团队运营成本（预估）
| 项目 | 月费 | 备注 |
|------|-----|------|
| API（保守） | $65-72 | 4个Agent |
| API（正常） | $133 | 4个Agent |
| API（高频） | $185-196 | 4个Agent |

### 当前 Session 统计（2026-03-16）
- Token: 206k in / 1.1k out
- Cost: $0.0000（glm-5 订阅制）
- Cache hit: 7%

---

## 🎯 待改进项

1. **USER.md 不存在** - 没有记录用户个性化偏好
2. **基金报告推送未配置** - Daniel 关注的重点
3. **teammates 分工了解不足** - 需要加强团队认知
4. **数据获取渠道受限** - 需要备用方案
5. **成本追踪精度不足** - 需要更精确的数据源

---

## 📚 学习资源（Daniel 推荐）

1. [Principles of Financial Accounting (OpenStax)](https://openstax.org/details/books/principles-financial-accounting)
2. [principlesofaccounting.com](https://www.principlesofaccounting.com/)
3. [Harvard Finance & Accounting E-Book](https://info.email.online.hbs.edu/finance-accounting-ebook)
4. 休斯顿大学 Accounting & Finance OER

---

## 📝 记录规范

- 每次有价值的工作 → 写入 memory/YYYY-MM-DD.md
- 重要发现/教训 → 更新本文件
- 学习进度 → 更新 learning-log.md
- 每日开销 → 更新 daily-expenses.md
- 每周自省 → 检查待改进项

---

*此文件是[CFO]的核心记忆，确保持续更新*
