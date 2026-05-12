# ⚡ 猎杀报告 Skill

你是Quant。读取最近4小时的猎杀日志，整合成报告推送。

## 铁律
- **不执行任何交易** — 只读结果+报告
- 新交易 → crypto-hunt skill 执行
- 止损 → position-monitor skill 执行

## Step 1: 读取最近4h猎杀日志

```bash
export HUNT_LOG_PATH="$WORKSPACE/data/hunt-log.jsonl"
python3 <<'PY'
import json, os, sys
from datetime import datetime, timedelta, timezone

log_path = os.environ.get("HUNT_LOG_PATH", "")
cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
entries = []

try:
    with open(log_path) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
                ts = datetime.fromisoformat(e['ts'].replace('Z', '+00:00'))
                if ts >= cutoff: entries.append(e)
            except: pass
except FileNotFoundError:
    print('NO_LOG_FILE'); sys.exit(0)

if not entries:
    print('NO_RECENT_ENTRIES'); sys.exit(0)

print(f'Found {len(entries)} entries')
for e in entries:
    print(f"--- {e.get('ts_local','?')} ---")
    print(f"Prices: {json.dumps(e.get('prices',{}), ensure_ascii=False)}")
    spots = e.get('tier_spots', e.get('sweet_spots', []))
    trades = e.get('trades', [])
    print(f"Spots: {len(spots)} | Trades: {len(trades)}")
    for s in spots:
        print(f"  {s.get('market','')} {s.get('side','')} edge:{s.get('edge_pct','')}% rec:{s.get('recommend','')}")
    for t in trades:
        print(f"  TRADE: {t.get('market','')} {t.get('side','')} ${t.get('amount_usd','')} @{t.get('price_c','')}¢")
    if not trades:
        print(f"  Skip: {e.get('skipped_reason','unknown')}")
    print(f"  Summary: {e.get('summary','')}")
PY
```

补充数据：
```bash
cat "$WORKSPACE/data/hunt-elon-latest.json" 2>/dev/null || echo "无Elon记录"
cat "$WORKSPACE/data/portfolio-snapshot.json" 2>/dev/null || echo "无仓位快照"
```

## Step 2: 整合报告

```
🔍 猎杀报告 @ HH:MM (最近4h)
━━━━━━━━━━━━━━
📈 BTC:$XX ETH:$XX
💰 Portfolio:$XX | Cash:$XX

━━ 最近4h猎杀 (X次扫描) ━━
🎯 甜区发现: X个
⚡ 交易执行: X笔

• HH:MM — [发现/跳过原因]

━━ 成功交易 ━━
• 市场 | 方向 | $金额 @价格¢

━━ Elon推文 ━━
🐦 [状态/无活跃盘]

━━ 策略状态 ━━
🟢 S1甜区: [活跃/静默]
🔵 S2趋势: [状态]
🐦 S7推文: [状态]
```

## Step 3: 推送

```
message(action='send', channel='telegram', target='YOUR_TELEGRAM_CHAT_ID', message='报告内容')
```

## Step 4: 更新 memory/$(date +%Y-%m-%d).md

## Step 5: 日志清理（>1000行时保留最近500行）
