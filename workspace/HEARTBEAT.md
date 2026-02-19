# HEARTBEAT.md

## API 健康检查（每 6 小时）
检查 `~/.openclaw/heartbeat-state.json` 的 `lastApiCheck`，超 6h 则运行：
```bash
python3 ~/clawd/scripts/api_health_check.py
```
异常则通知用户。
