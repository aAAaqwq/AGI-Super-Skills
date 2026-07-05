# 5minbtc 引擎架构

## 引擎模块 (`5minbtc-engine-v5.7.py`)

- v5.7.3 HTTP 并行化: ThreadPoolExecutor 4 路 (klines+depth+FNG+chainlink) ~3s
- v5.7.4 TREND decel 约束
- 12 正交因子: momentum / meanrev / RSI / volume / fatigue / imbalance / microprice / decel / position / v_reversal / vol_breakout / half_body
- ATR 乘数 ×0.55, half_range 0.40
- Chainlink 价格对齐 (Coinbase BTC-USD 偏移补偿, 上限 ±$300)

## 引擎 JSON 输出结构 (LLM 读取)

v5.6输出示例（实际字段名）：
```

## v5.0 基础 (R14 审查 14 项修复)

- C-1: 正交因子替代共线指标
- C-2: 所有阈值 ATR 归一化
- C-3: 条件化 volume 信号
- C-4: 订单簿深度信号
- H-1: Sigmoid 压缩替代 ad-hoc 压制
- H-3: 百分比化信号
- H-4: 波动率 Regime 检测 (4 态)
- M-1~M-6: 数学修正 (BB std, 200K 线, vol 投影, RSI 动量, Wilder ATR, O(n) MACD)

## v5.0 升级路线图


> 详见 `references/quant-knowledge-index.md` 和 `~/.hermes/profiles/cqo/quant-knowledge/R12-integration-blueprint.md`

### v5.6 方向错误修复（✅ 已实施 2026-05-27）

基于2026-05-27深度复盘的3次方向错误分析，已全部落地到引擎代码：

| 优先级 | 修复项 | 状态 | 实现 |
|--------|--------|------|------|
| R0 | momentum/decel冲突检测 | ✅ `direction_rule_v5()` | saved_base模式动态降权mom→0.4, decel→0.9 |
| R1 | V型反转因子 | ✅ `v_reversal_detect()` | BASE_W=0.8, TREND/HIGH_VOL下加权至0.9/1.0 |
| R2 | 放量突破因子 | ✅ `vol_breakout_signal()` | 用最近3根完成K线，BASE_W=0.4 |
| R3 | Chainlink价格对齐 | ✅ `fetch_chainlink_ref()+run()` | Coinbase BTC-USD参考，偏移补偿上限±$300 |

**案例复盘要点**：
- 20:20巨量突破(vol=182%)：decel=+1.0正确预判反转，但mom=-0.98权重×1.0淹没反转信号 → **R0冲突检测修复**
- 20:25放量延续(vol=123%)：同上，momentum仍在消化15根K线的下跌斜率 → **R0冲突检测修复**
- 20:50低vol(vol=33%)：RANGE regime下meanrev权重放大推高bull，实际仅$2波动 → **v5.5 neutral区收缩已覆盖**

**实时验证**: 22:09 CST 运行恰好命中冲突场景(mom=-0.981, decel=+1.0)，输出bear conf=45% score=-1

### P0 — 立即实施（回测验证后的修订优先级）
1. **🔴 OFI微结构因子是唯一出路** — 回测证明纯价格因子无预测力。必须接入Binance WebSocket获取orderbook L2数据，实现OFI(Cont et al. 2014)和Stoikov microprice。学术文献R²=15-25%，是5分钟尺度唯一有实证支持的信号
2. **新闻脉冲信号** — 突发事件(Big发布/SEC/ETF)可在5分钟内产生方向性冲击，作为互补信号
3. **降低实盘仓位** — 在edge来源明确前，不应按66%胜率预期下注。实盘66%大概率是小样本+前视偏差的假象

### P1 — 2-4周
4. Regime-aware仓位 (HMM检测)
5. LightGBM自动化因子筛选
6. CVaR动态止损

### P2 — 1-2月
7. TFT多时间尺度模型 → 替代贝叶斯引擎
8. 期权IV信号 (Deribit)
9. 完整压力测试框架

### 关键数学升级
- OFI (Cont et al. 2014) → 替代纯价格指标
- Microprice (Stoikov 2018) → 替代 mid price
- Kalman滤波 → 动态EMA权重
- HMM Regime → 自适应仓位
- GPD尾部 → 替代固定止损


