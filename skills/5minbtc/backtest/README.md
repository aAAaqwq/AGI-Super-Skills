# 5minbtc Backtest System

## 快速使用

```bash
# 一键回测 (下载最新数据 + 运行回测)
cd backtest && ./run.sh

# 快速回测 (每小时采样, 最近180天)
./run.sh --fast

# 只回测最近90天, 每6根K线采样
./run.sh --days 90 --sample=6

# 完整因子分析报告
./run.sh --full-report

# 跳过数据下载 (使用缓存)
./run.sh --skip-fetch

# 自定义 candle_progress (模拟K线完成度)
python3 run_backtest.py --progress=0.5
```

## 文件结构

```
backtest/
├── fetch_data.py        # Binance 历史数据下载器
├── run_backtest.py      # 回测引擎 (导入 v5.6 因子模块)
├── run.sh               # 一键运行脚本
├── README.md            # 本文件
├── data/                # 缓存的K线数据 (JSON)
│   └── btcusdt_5m.json  # 365天 x 288根/天 ≈ 105k 根
└── results/             # 回测结果
    ├── backtest_YYYYMMDD_HHMM.json  # 完整结果
    └── latest_summary.json          # 最新摘要
```

## 参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--sample=N` | 1 | 采样率: 1=每根K线, 6=每30min, 12=每小时 |
| `--days=N` | 全部 | 回测最近N天 |
| `--progress=F` | 0.01 | candle_progress: 0.01=刚开盘, 1.0=已完成 |
| `--fast` | - | 快速模式: sample=12 + days=180 |
| `--full-report` | - | 输出完整因子贡献分析 |
| `--force` | - | 强制重新下载数据 |

## 回测方法论

### 公平性保障
- **无前视偏差**: 当前K线价格信息被屏蔽 (c=h=l=open, v=0)
- **仅用历史数据**: 因子仅基于200根已完成K线计算
- **无 orderbook**: imbalance/microprice 设为0 (回测不可获取)

### 模式对比

| 模式 | candle_progress | 当前K线数据 | 含义 |
|------|----------------|-------------|------|
| 保守 (默认) | 0.01 | 屏蔽 | 模拟K线刚开盘, 最公平 |
| 中等 | 0.5 | 屏蔽 | 模拟K线中段 |
| 前视 | 1.0 | 使用实际值 | 含未来信息, 仅用于分析 |

### 指标体系
- **方向准确率**: bull/bear 预测与实际涨跌一致的比例
- **Regime 分析**: 按 TREND/RANGE/HIGH_VOL/LOW_VOL 分组
- **置信度分层**: 按 confidence 5分档统计准确率
- **因子贡献**: 每个因子在正确/错误预测中的信号强度差异
- **Baseline 对比**: vs Always-Bull / Always-Bear / Random(50%)

## ⚠️ 已知局限性

1. **无 orderbook 数据**: imbalance/microprice 始终为0, 可能低估实盘表现
2. **无 Chainlink 补偿**: 回测使用 Binance 价格, 未模拟 Coinbase 偏移
3. **无新闻信号**: news_factor 未集成
4. **K线模拟简化**: 实际实盘在 K线末段(progress=0.9+)有更多信息

---

*Created: 2026-05-27 | Engine: v5.6*
