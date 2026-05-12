# 🟡 Binance 热度猎杀 Skill v2.0

> 整合多数据源（0 浏览器依赖）→ 统一交易信号
> 
> 数据源：Fear&Greed API + 新闻 RSS + Binance Ticker + (可选) Browser快照

---

## 核心脚本

```
skills/binance-trending/scripts/
├── scan_square_hunt.py       # 整合主脚本（纯API，0浏览器依赖）
├── scrape_square.py          # Browser快照解析（补充数据）
├── scrape_binance_hot.py     # Binance热度（纯API）
└── scrape_news.py            # 新闻RSS（纯API）
```

---

## 使用方式

### 推荐：快速模式（无需浏览器）

```bash
python3 "$SKILL_DIR/scripts/scan_square_hunt.py"
```

**输出示例**：

```
📊 热度猎杀整合 | 2026-04-23 22:34
😐 恐惧贪婪: 46 (Fear) | 中性
₿ BTC: $77,843 -1.18%
Ξ ETH: $2,329 -3.03%
📰 新闻: BEARISH (9多/17空)

🔥 热搜机会: BONK-2%📉 | JUP-5%📉 | CHIP-6%📉 | WLD-3%📉
🐋 大户动态: $+70,386 做空 | $-14,026 做多亏损

📋 信号:
  🔴 [MEDIUM] BTC -1.2%+新闻偏空
     → 检查BTC below YES
```

---

## 数据源说明

| 数据 | 来源 | 依赖 |
|------|------|------|
| 恐惧贪婪指数 | Alternative.me API | ✅ 纯API |
| 新闻情绪 | CoinTelegraph + CoinDesk RSS | ✅ 纯API |
| BTC/ETH价格 | Binance data-api | ✅ 纯API |
| 热搜币排行 | Binance Square 页面 | ⚠️ Browser |
| 帖子盈亏 | Binance Square 页面 | ⚠️ Browser |

**Browser 数据为补充**，核心信号完全无需浏览器。

---

## 信号规则

| 条件 | 信号 | 操作 |
|------|------|------|
| BTC<-1.5% + 新闻偏空 | 🔴 BEARISH | 检查BTC below YES |
| BTC<-4% + 极度恐惧 | 🟢 HIGH | 观察BTC above抄底 |
| BTC>+2% + 极度贪婪 | ⚠️ CAUTION | 减少多头 |
| ETH<-4% | 🔴 ETH_DROP | 检查ETH below YES |

---

## 信号强度

| Edge | 触发条件 |
|------|---------|
| HIGH | BTC急跌+极度恐惧 或 BTC强势+贪婪 |
| MEDIUM | BTC下跌+新闻偏空 或 ETH急跌 |

---

## 完整 Cron 流程（无浏览器）

```
0,30 * * * * python3 $SKILL/scripts/scan_square_hunt.py
```

每30分钟自动运行，输出 `/tmp/hunt_signals.json`。

---

## Browser 增强模式（可选）

每6小时运行一次，获取热搜+帖子数据：

```bash
# 1. 打开页面
browser → open(url='https://www.binance.com/zh-CN/square/fear-and-greed-index')

# 2. 等待加载
browser → act(wait=6000ms)

# 3. 保存snapshot
browser → snapshot(compact=True) → 保存到 /tmp/binance_square_snapshot.txt

# 4. 运行完整模式
python3 $SKILL/scripts/scan_square_hunt.py --all
```

---

## JSON 输出

```json
{
  "scan_time": "2026-04-23 22:34",
  "fear_greed": {"value": 46, "label": "Fear"},
  "market_mood": "中性",
  "btc": {"price": 77843, "change_pct": -1.18},
  "eth": {"price": 2329, "change_pct": -3.03},
  "news": {"signal": "BEARISH", "bullish": 9, "bearish": 17},
  "signals": [{"type": "BEARISH", "edge": "MEDIUM", ...}],
  "hot_opportunities": ["CHIP-6%📉", "BONK-2%📉"],
  "whale_actions": ["$+70,386 做空", "$-14,026 做多亏损"]
}
```

---

## 文件结构

```
skills/binance-trending/
├── SKILL.md
└── scripts/
    ├── scan_square_hunt.py    # 整合主脚本
    ├── scrape_square.py       # Browser快照解析
    ├── scrape_binance_hot.py  # Binance热度(纯API)
    └── scrape_news.py         # 新闻RSS
```

---

## 注意事项

1. **推荐使用 `--fast` 模式**，0浏览器依赖，稳定可卡
2. Browser 数据为补充，每6h更新一次足够
3. 信号需结合 Polymarket 实际市场存在性判断
4. 单笔交易 ≤ $5（热度策略高风险）
