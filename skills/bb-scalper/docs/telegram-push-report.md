# bb-scalper → Telegram 模拟盘 6h 报告（含地区限制修复）

本地持久化模拟盘 daemon 的 Telegram 推送与 geo 修复说明。

## 地区限制修复（重要）

Binance **合约** REST 端点 `fapi.binance.com` 在部分区域返回 **HTTP 451**（Unavailable for
Legal Reasons），会导致 `cli/paper.py` 的历史 K 线暖机失败 → 策略永远无信号。

已在 `cli/paper.py` 把暖机与兜底询价改用不受限的现货端点：

| 位置 | 原端点（451） | 修复后 |
|------|--------------|--------|
| 暖机 15m/1h klines | `fapi.binance.com/fapi/v1/klines` | `data-api.binance.vision/api/v3/klines` |
| 兜底询价（trade 流稀疏时） | `fapi.binance.com/fapi/v1/ticker/price` | `data-api.binance.vision/api/v3/ticker/price` |

WebSocket 行情流 `fstream.binance.com` 不受影响，无需改动。
现货/合约收盘价对主流币差异可忽略，不影响 BB/RSI/趋势过滤计算。

## Telegram 推送脚本（本 skill `scripts/`）

| 脚本 | 作用 |
|------|------|
| `bb_report.py` | 读取模拟平仓记录，生成 6h 汇总（胜率/PnL/分币种/实时价/最近几笔）推送到 Telegram |
| `telegram_push.py` | 通用 Telegram 推送助手（从 `~/.cc-connect/config.toml` 读 bot token + chat_id） |

## 用法

```bash
# 6h 报告（默认读 ~/bb-auto/paper_trades.json）
python3 scripts/bb_report.py

# 指定交易记录文件
BB_PAPER_TRADES=/path/to/paper_trades.json python3 scripts/bb_report.py
```

## 模拟盘 daemon 参考

```bash
# 持续运行（launchd 托管，崩溃自动重启）
python3 cli/paper.py \
  --symbols SOLUSDT,BTCUSDT,XRPUSDT,NEARUSDT,DOTUSDT \
  --capital 500 --log ~/bb-auto/paper_trades.json
```

每 6h 调用一次 `scripts/bb_report.py` 推送报告即可（可用 launchd StartCalendarInterval 或
外层监督脚本 sleep 21600 循环）。
