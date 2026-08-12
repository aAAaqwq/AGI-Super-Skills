# 5minbtc → Telegram 推送监控（含预测记录与结算）

本地持久化监控 daemon，把 5minbtc 引擎预测实时推送到 Telegram，并**记录预测 + 收盘结算**，
用于验证每日预测战绩。

## 脚本（本 skill `scripts/`）

| 脚本 | 作用 |
|------|------|
| `5minbtc_watch.py` | 持续监控 daemon：每根 5min K 线第 2/3/4 分钟采样引擎，事件驱动推送 + 记录 + 结算 |
| `5minbtc_day_stats.py` | 预测战绩查询（今日/指定日期/全部），`--push` 推送到 Telegram |
| `telegram_push.py` | 通用 Telegram 推送助手（从 `~/.cc-connect/config.toml` 读 bot token + chat_id） |

## 用法

```bash
# 持续监控（事件驱动 + 每小时心跳 + 每日战绩推送）
python3 scripts/5minbtc_watch.py

# 每根K线都推完整预测（约 288 条/天，慎用）
python3 scripts/5minbtc_watch.py --every-candle

# 查询今日战绩 / 指定日期 / 全部，推送到 Telegram
python3 scripts/5minbtc_day_stats.py
python3 scripts/5minbtc_day_stats.py --date 2026-08-12 --push
python3 scripts/5minbtc_day_stats.py --all
```

## 记录与结算（验证以最终确认结果为准）

- **记录**：每根 K 线记录首次成功采样的预测到 `logs/5minbtc-log.jsonl`（经 `5minbtc-log.py log`）
  - 字段：candle ISO / pred_close / pred_range / confidence / bias / news / vol_pct
- **结算**：新 K 线开始时对上一根已收盘 K 线执行 `settle-all`，写入最终确认的
  actual_close / actual_high / actual_low，并计算：
  - `direction_correct` — 方向命中（看多→实际收>开，看空→实际收<开）
  - `in_range` — 收盘价是否落在预测区间
  - `error_pct` — 预测收盘误差 %
- **每日 00:00**（CST）自动推送前一天战绩汇总：方向命中率 / 区间命中率 / MAE

## 事件推送类型

| 事件 | 含义 |
|------|------|
| START | 首次采样基线方向 |
| DIR-CHANGE | 方向 bull/neutral/bear 翻转 |
| CLEAR-SIGNAL | 达到明确信号门槛（bias!=neutral + strength∈medium+ + conf≥50） |
| TB-FLIP | 主动买卖力 taker_buy 正负翻转 |
| 心跳 | 每小时一次，确认 daemon 存活 |

## 依赖

纯标准库（引擎只依赖 stdlib，无 pip 依赖）。`telegram_push.py` 需要本机装有 cc-connect 配置。

## 持久化（launchd 示例）

```bash
# ~/Library/LaunchAgents/com.daniel.5minbtc-watch.plist
# ProgramArguments: /usr/bin/python3 <SKILL>/scripts/5minbtc_watch.py
# RunAtLoad=true, KeepAlive=true（开机自启 + 崩溃自动重启）
```
