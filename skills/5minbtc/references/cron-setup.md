# 5minbtc Cron Job 配置

## Cron Job 列表

| Job ID | Name | Schedule | Model | Provider |
|--------|------|----------|-------|----------|
| d8058223a1e0 | 5minbtc v5.7 半K线策略 | `2,7,12,17,22,27,32,37,42,47,52,57 20-22 * * *` | glm-5.2 | zai |
| 9b07cd139f70 | 5minbtc 每日复盘 (23:15) | `15 23 * * *` | glm-5.2 | zai |

## 版本同步规则
升级引擎后必须同步更新 cron job 的 `name` 字段。cron 不自动感知引擎文件版本——它只执行 `5minbtc-engine-v5.7.py`，文件内容变了 cron 就跑新代码，但 job name 仍是旧标签，导致复盘时混淆实际运行的引擎版本。

操作: 每次 engine 升级后，执行 `cronjob(action='update', job_id=..., name='5minbtc vX.Y')`。

## LLM Provider 失效诊断与切换
详见: [references/cron-llm-provider-failure.md](cron-llm-provider-failure.md)

简要:
- 症状: cron job `last_status=error`, `last_error` 401/402
- 真实根因常是: 主 provider 欠费 (402) 触发 fallback, fallback 链上某个 key 解析失败
- 修复: `hermes logs errors -n 30` + `hermes logs --component cron -n 50` 看瀑布
- 切 provider 模板: `for jid in <JIDs>; do hermes cron update --job-id $jid --model glm-5.2 --provider zai; done`
- 立即验证: `hermes cron run --job-id <JID>` (不等 schedule)

## 高延迟网络 (SSL 超时) 处理
详见: [references/high-latency-network-handling.md](high-latency-network-handling.md)

简述: ping 8.8.8.8 > 250ms 时, 两个 Binance 端点都 SSL 超时, 需临时把 `5minbtc-engine-v5.7.py` 内 `timeout=10` 改为 `timeout=25`, 跑完务必恢复。
