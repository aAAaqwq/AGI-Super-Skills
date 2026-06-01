# Quant Knowledge Bank Index

> 50-round deep distillation (2026-05-23). 14 reports, ~80KB.
> Path: `~/.hermes/profiles/cqo/quant-knowledge/`
> Also synced to AGI-Super-Team repo `skills/5minbtc/reports/`

| File | Topic | Key Takeaways for 5minbtc |
|------|-------|---------------------------|
| R01-factor-theory.md | Alpha101, IC decay, Barra | IC衰减监控方法；LLM因子挖掘需防拥挤度 |
| R02-strategy-theory.md | OU过程, 协整, Kalman, OFI | Kalman滤波动态参数 → 替代固定EMA权重 |
| R03-crypto-quant-defi.md | 资金费率, 链上, MEV | 资金费率极值=过热信号；HODL Waves长周期 |
| R04-portfolio-theory.md | BL/HRP/Kelly | Kelly分数下注 → 最优仓位大小框架 |
| R05-ml-quant-trading.md | LightGBM, TFT, RL | TFT多时间尺度注意力 → 替代线性打分；Purged K-Fold防泄露 |
| R06-data-sources.md | Alt Data全景, 加密数据 | **P0免费源**: Arkham(鲸鱼), Binance WS(OFI), Deribit(IV) |
| R07-frontier-research.md | LLM因子, AI Agent | AlphaAgent开源可用；RFT技术2026最新；拥挤度风险 |
| R08-options-volatility.md | Greeks, 曲面, 隐含分布 | DVOL-RV spread → 波动率regime信号；周末IV低估 |
| R09-market-microstructure.md | LOB, OFI, Kyle, Almgren | **OFI 5min R²~15-25%** → 直接接入5minbtc；Microprice优于mid |
| R10-risk-management.md | CVaR, EVT, Regime, 压测 | HMM regime检测 → regime-aware仓位；GPD尾部止损 |
| R11-institutional-methodology.md | Simons, Citadel, Two Sigma | 信号仪表板+衰减检测+弱信号组合；DSR防过拟合 |
| R12-integration-blueprint.md | 知识图谱+升级蓝图 | **完整5阶段升级路径，P0→P2优先级** |
| R13-accuracy-optimization-plan.md | 178笔回盘+优化方案 | bull bias根因分析；Phase1修复→v4.1部署；5大优化方向 |
| R14-engine-audit-report.md | 顶尖量化审查 | 4个Critical缺陷(共线指标/过拟合/regime盲区/阈值硬编码)→v5.0架构设计基础 |

## P0 Upgrade Priorities (from R12)

1. **OFI微结构因子** — Binance WS → 订单流不平衡 → 5min预测R²~15-25%
2. **免费数据源接入** — Arkham(鲸鱼追踪), Binance WebSocket(LOB), Deribit API(IV)
3. **信号仪表板** — 监控所有因子IC/衰减率，Simons哲学核心实践

## Delegate Research Pattern

- **Timeout risk**: Research delegates with >35 web_search calls risk 600s timeout. Mitigation: split into smaller batches or write reports directly from domain knowledge + search results.
- **Incomplete output**: Delegates sometimes return search traces but not formatted reports. Mitigation: write reports directly from the search context already gathered.
