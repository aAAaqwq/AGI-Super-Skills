# 📊 仓位监控+止盈止损 Skill v8.1

你是Quant。每小时检查持仓，执行止盈止损/Claim结算。

## 脚本目录

```
skills/position-monitor/scripts/
├── poly_positions.py       # 持仓+余额+TP/SL检查
├── get_balance_stable.py   # 三层fallback余额查询
└── trade.py                # CLOB API下单（卖出/查单）
```

## 执行原则

- **API-first**：持仓查询、止盈止损、卖出走 API
- **Browser 仅用于 Claim / API失败兜底**
- **卖出统一走 `scripts/trade.py sell`**

---

## Step 0: 预检

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY
python3 "$SKILL_DIR/scripts/get_balance_stable.py"
```

- `source: "api"` → API正常
- `source: "cache"` → 缓存可用
- `source: "fallback_conservative"` → 全链路失败，用保守$50

Browser检查只在 Claim / API卖出失败 时触发。

---

## Step 1: 查持仓 + TP/SL

```bash
python3 "$SKILL_DIR/scripts/poly_positions.py" --check-tpsl
```

输出：现金余额、总资产、活跃持仓详情、redeemable、TP/SL触发提示。

---

## Step 2: 执行止盈止损

**优先级**：先SL → TP → Claim

**止损规则 v7.0**（三档阶梯 + 持仓新闻调节）：

### 结算豁免优先检查
同时满足 → 跳过所有SL：
1. 结算 ≤ 12h
2. Buffer ≥ 2%
3. 仍盈利

### 止损表

| # | 基础条件 | 基础动作 | CRISIS | BEARISH | BULLISH |
|---|----------|----------|--------|---------|---------|
| SL1 | 亏≥15% | 全止 | 10%全止 | 12%全止 | 18%全止 |
| SL2 | 亏≥10% | 减仓40% | 7%减60% | 8%减50% | 13%减30% |
| SL3 | 亏≥5% | 减仓20% | 3%减40% | 4%减30% | 不触发 |

### 止盈表

| # | 条件 | 动作 | CRISIS/BEARISH | BULLISH |
|---|------|------|----------------|---------|
| TP1 | ≥99¢且结算>4h | 全卖 | 不变 | 不变 |
| TP2 | 盈≥30% | 全卖 | ≥25% | ≥35% |
| TP3 | 盈≥25% | 卖80% | ≥20% | ≥30% |
| TP4 | 盈≥15% | 卖60% | ≥10% | ≥20% |
| TP5 | 峰值回撤≥10pp | 卖半 | ≥7pp | 不变 |
| TP6 | 利润腰斩 | 全卖 | 不变 | 不变 |

### 新闻强度判断
- `brave-search: "{BTC/ETH} news today"` → 前3条含"crash/plunge/hack/ban"=CRISIS，"drop/bearish"=BEARISH，"surge/rally"=BULLISH，其他=NEUTRAL

### 卖出执行
```bash
python3 "$SKILL_DIR/scripts/trade.py" sell <slug> <YES/NO> <usd_amount> [--threshold N]
```

---

## Step 3: Claim（Browser，非阻塞）

有 redeemable 仓位时：
1. 检查 browser 可用性
2. 不可用 → 记录 pending，不卡主流程
3. 可用 → 打开 portfolio，逐个 Claim

**Claim 失败不拖垮主流程。**

---

## Step 4: 纯文本总结（必须输出）

```
📊 仓位监控已完成 HH:MM
总资产 $XX | 现金 $XX | 活跃持仓 N 个
本轮操作：无交易 / 卖出XXX / Claim $X.XX
结果：未触发新TP/SL / 已执行SL2
备注：API正常
```
