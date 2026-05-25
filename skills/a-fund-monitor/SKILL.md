---
name: a-fund-monitor
description: "A股基金净值监控：盘中实时估值 + 盘后实际净值，定时推送到 Telegram。"
version: 2.1.0
triggers:
  - A股 基金 监控 预测 净值 估值
  - fund monitor A-share NAV estimate
  - 东方财富 基金 API
---

# A股基金监控

A股基金净值监控，支持盘中实时估值和盘后实际净值，通过 OpenClaw cron 推送到 Telegram 私聊。

## 架构

```
fund_monitor.py (纯 Python，无外部依赖)
  ├── estimate 模式 → fundgz.1234567.com.cn (盘中实时估值)
  └── nav 模式      → api.fund.eastmoney.com/f10/lsjz (收盘净值)

OpenClaw cron (isolated agentTurn)
  ├── 09:30-19:00 → estimate 模式（收盘后先推估值，净值当晚才公布）
  └── 19:00 之后  → nav 模式（收盘实际净值）
  └── stdout → delivery announce → Telegram 私聊
```

**关键路径**: `skills/a-fund-monitor/scripts/`（本仓库）

## 手动执行

```bash
# 盘中估值（控制台输出）
python3 scripts/fund_monitor.py estimate

# 收盘净值（控制台输出）
python3 scripts/fund_monitor.py nav
```

## Cron 定时任务

OpenClaw cron，使用 **Asia/Shanghai** 时区。

| 北京时间 | 模式 | 数据源 |
|---------|------|--------|
| 10:30 | 盘中估值 | fundgz 接口 |
| 12:30 | 盘中估值 | 同上 |
| 14:30 | 盘中估值 | 同上 |
| 20:30 | 收盘净值 | lsjz 接口 |

**合并为 1 个 cron job**: `04a185b2-f8ae-454e-b454-bc1944ca5c00`

```
Cron:     30 10,12,14,20 * * 1-5 (Asia/Shanghai)
Runtime:  isolated agentTurn (changqing)
Timeout:  180s
Delivery: announce → telegram:8518085684 (Daniel 私聊)
```

### 模式判断逻辑

```
北京时间 ∈ [09:30, 19:00) → estimate
北京时间 ∈ [19:00, 次日)  → nav
```

**投递目标**: `telegram:8518085684`（Daniel Li 私聊），accountId `changqing`

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

## 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-05-25 | v2.1.0 | 4 个 cron 合并为 1 个(逗号分隔小时)；从 Hermes 迁移到 OpenClaw cron；推送目标改为 Daniel 私聊(8518085684)；超时提至 180s；19:00 前走估值避免陈旧数据 |
| 2026-05-22 | v2.0.0 | 初始 Hermes cron 版本 |

## Pitfalls

- **超时**：14 只基金顺序请求，API 偶发慢速，cron timeout 设为 180s。
- **NAV 涨跌幅字段**：东方财富 lsjz API 的涨跌幅字段是 `JZZZL`（净值增长率），不是 `NAVCHGRT`。
- **估值 API 返回 JSONP**：`fundgz.1234567.com.cn` 返回 `jsonpgz({...});` 格式，需正则提取 JSON。
- **HTTP 请求头**：两个 API 都需要 `Referer: https://fund.eastmoney.com/` 和 `User-Agent`，否则可能 403。
- **20:30 净值可能未更新**：部分基金净值延迟到 22:00 后才更新，QDII 基金（如广发纳斯达克100）更晚。19:00 前先用估值模式兜底。
- **QDII 基金估值时间**：广发纳斯达克100联接的估值时间显示为 04:00（美股收盘时间），非 A 股 15:00。
- **周末/节假日**：cron `1-5` 仅排除周末，中国法定节假日仍会触发（产出的是上一交易日数据）。
