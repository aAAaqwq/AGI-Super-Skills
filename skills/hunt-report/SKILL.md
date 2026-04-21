---
name: hunt-report
description: Crypto hunt report — aggregate 4-hour hunting logs into actionable intelligence
---

# ⚡ 猎杀报告 Skill

你是Quant(量子)。读取最近4小时的猎杀日志，整合成报告推送。

## 铁律
- **不执行任何交易** — 只读结果+报告
- 新交易 → 加密猎杀执行
- 止损 → 仓位管理执行

## Step 1: 读取最近4h猎杀日志

```bash
echo "=== 最近4h猎杀日志 ==="
CUTOFF=$(date -u -d '4 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-4H +%Y-%m-%dT%H:%M:%SZ)
python3 -c "
import json, sys
from datetime import datetime, timedelta, timezone

cutoff = datetime.now(timezone.utc) - timedelta(hours=4)
entries = []
try:
    with open('${QUANT_WORKSPACE}/data/hunt-log.jsonl') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
                ts = datetime.fromisoformat(e['ts'].replace('Z','+00:00'))
                if ts >= cutoff:
                    entries.append(e)
            except: pass
except FileNotFoundError:
    print('NO_LOG_FILE')
    sys.exit(0)

if not entries:
    print('NO_RECENT_ENTRIES')
    print(f'Cutoff: {cutoff.isoformat()}')
    # Show last 3 entries regardless of time
    try:
        with open('${QUANT_WORKSPACE}/data/hunt-log.jsonl') as f:
            all_lines = [l.strip() for l in f if l.strip()]
        print(f'Total entries in log: {len(all_lines)}')
        for l in all_lines[-3:]:
            print(l)
    except: pass
    sys.exit(0)

print(f'Found {len(entries)} entries in last 4h')
trades_total = []
sweet_total = []
for e in entries:
    print(f\"--- {e.get('ts_local','?')} ---\")
    print(f\"Prices: {json.dumps(e.get('prices',{}))}\")
    sweets = e.get('sweet_spots', [])
    trades = e.get('trades', [])
    print(f\"Sweet spots: {len(sweets)} | Trades: {len(trades)}\")
    if sweets:
        for s in sweets:
            print(f\"  SWEET: {s.get('market','')} {s.get('side','')} @{s.get('price_c','')}¢ buf:{s.get('buffer_pct','')}% trend:{s.get('trend','')} entry:{s.get('entry','')}\")
    if trades:
        for t in trades:
            print(f\"  TRADE: {t.get('market','')} {t.get('side','')} \${t.get('amount_usd','')} @{t.get('price_c','')}¢\")
    else:
        print(f\"  Skip: {e.get('skipped_reason','unknown')}\")
    print(f\"  Summary: {e.get('summary','')}\")
    trades_total.extend(trades)
    sweet_total.extend(sweets)

print(f'\\n=== 4h汇总 ===')
print(f'扫描次数: {len(entries)}')
print(f'甜区发现: {len(sweet_total)}')
print(f'交易执行: {len(trades_total)}')
"
```

```bash
echo "=== Elon猎杀最近结果 ==="
cat ${WORKSPACE}/data/hunt-elon-latest.json 2>/dev/null || echo "无记录"

echo "=== 仓位快照 ==="
cat ${WORKSPACE}/data/portfolio-snapshot.json 2>/dev/null || echo "无记录"
```

## Step 2: 整合报告

根据Step 1的输出整合：

```
🔍 猎杀报告 @ HH:MM (最近4h)
━━━━━━━━━━━━━━
📈 BTC:$XX ETH:$XX SOL:$XX GOLD:$XX
💰 Portfolio:$XX | Cash:$XX

━━ 最近4h猎杀 (X次扫描) ━━
🎯 甜区发现: X个
⚡ 交易执行: X笔

[列出每次扫描的关键发现]
• HH:MM — [甜区/无机会] | [交易/跳过原因]

━━ 成功交易 ━━
[如有交易，列出详情]
• 市场 | 方向 | $金额 @价格¢

━━ Elon推文 ━━
🐦 [Elon盘状态/无活跃盘]

━━ 策略状态 ━━
🟢 S1甜区: [活跃/静默]
🔵 S2趋势: [状态]
🐦 S7推文: [状态]
```

如果日志文件不存在或最近4h无条目，报告注明"⚠️ 猎杀日志无数据，请检查猎杀cron是否正常写入hunt-log.jsonl"

## Step 3: 推送

**使用message工具推送到Daniel私聊**：
```
message(action='send', channel='telegram', target='${TELEGRAM_TARGET_ID}', message='报告内容')
```

## Step 4: 更新memory
追加到 memory/$(date +%Y-%m-%d).md

## Step 5: 日志清理（可选）

如果 hunt-log.jsonl > 1000行，只保留最近500行：
```bash
LOG=${WORKSPACE}/data/hunt-log.jsonl
LINES=$(wc -l < "$LOG" 2>/dev/null || echo 0)
if [ "$LINES" -gt 1000 ]; then
  tail -500 "$LOG" > "${LOG}.tmp" && mv "${LOG}.tmp" "$LOG"
  echo "Trimmed hunt-log from $LINES to 500 lines"
fi
```

## 变更记录
- v2.0 (2026-03-17): 重写！从读latest.json改为读hunt-log.jsonl最近4h滚动日志
- v1.0 (2026-03-15): 从cron prompt迁移为skill
