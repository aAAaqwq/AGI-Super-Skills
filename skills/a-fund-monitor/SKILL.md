---
name: a-fund-monitor
description: "A股基金净值监控：盘中实时估值 + 盘后实际净值，定时推送到 Telegram 群。"
version: 2.0.0
triggers:
  - A股 基金 监控 预测 净值 估值
  - fund monitor A-share NAV estimate
  - 东方财富 基金 API
---

# A股基金监控

A股基金净值监控，支持盘中实时估值和盘后实际净值，推送到 Telegram。

## 架构

```
fund_monitor.py (纯 Python，无外部依赖)
  ├── estimate 模式 → fundgz.1234567.com.cn (盘中实时估值)
  └── nav 模式      → api.fund.eastmoney.com/f10/lsjz (收盘净值)

Cron wrapper scripts:
  fund_estimate.sh → python3 fund_monitor.py estimate
  fund_nav.sh      → python3 fund_monitor.py nav

Hermes cron (no_agent=true) → stdout 直接投递到 Telegram 群
```

**关键路径**: `~/.hermes/profiles/cfo/scripts/`

## 手动执行

```bash
# 盘中估值（控制台输出）
python3 ~/.hermes/profiles/cfo/scripts/fund_monitor.py estimate

# 收盘净值（控制台输出）
python3 ~/.hermes/profiles/cfo/scripts/fund_monitor.py nav
```

## Cron 定时任务

Hermes cron 使用 **本地时区**（北京时间），不需要 UTC 转换。

| 北京时间 | Cron 表达式 | 类型 | 数据源 |
|---------|------------|------|--------|
| 10:30 | `30 10 * * 1-5` | 盘中实时估值 | fundgz 接口 |
| 12:30 | `30 12 * * 1-5` | 盘中实时估值 | 同上 |
| 14:30 | `30 14 * * 1-5` | 盘中实时估值 | 同上 |
| 20:30 | `30 20 * * 1-5` | 收盘实际净值 | lsjz 接口 |

Cron job IDs（2026-05-22 重建）：
- `7bc48122678e` — 10:30 盘中估值
- `1a66e04aa9c9` — 12:30 盘中估值
- `909352d70c37` — 14:30 盘中估值
- `ac49f4b01fd6` — 20:30 收盘净值

**投递目标**: `telegram:-1003824568687`（NewsRobot 群）

## 添加/删除基金

编辑 `fund_monitor.py` 中的 `FUNDS` 列表：

```python
FUNDS = [
    ("003304", "前海开源核心资源A"),
    # ... 添加 ("代码", "简称")
]
```

## API 参考

详见 `references/eastmoney-api.md`。

## Pitfalls

- **Hermes cron 时区**：cron schedule 使用服务器本地时区（北京时间），不需要 UTC 转换。旧版本错误使用 UTC（`30 2 * * 1-5` = 北京 10:30），已修正。
- **NAV 涨跌幅字段**：东方财富 lsjz API 的涨跌幅字段是 `JZZZL`（净值增长率），不是 `NAVCHGRT`。
- **估值 API 返回 JSONP**：`fundgz.1234567.com.cn` 返回 `jsonpgz({...});` 格式，需正则提取 JSON。
- **HTTP 请求头**：两个 API 都需要 `Referer: https://fund.eastmoney.com/` 和 `User-Agent`，否则可能 403。
- **20:30 净值可能未更新**：部分基金净值延迟到 22:00 后才更新，QDII 基金（如广发纳斯达克100）更晚。
- **QDII 基金估值时间**：广发纳斯达克100联接的估值时间显示为 04:00（美股收盘时间），非 A 股 15:00。
- **周末/节假日**：cron `1-5` 仅排除周末，中国法定节假日仍会触发（产出的是上一交易日数据）。
- **Cron 脚本路径**：必须是 `~/.hermes/profiles/<profile>/scripts/` 下的相对文件名，不能是绝对路径。
