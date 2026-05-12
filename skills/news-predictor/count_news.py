import json

NEWS_DATA = [
    {"ts": "2026-05-05T20:56:31+08:00", "headline": "Bitcoin absorbed $200 million profit-taking at $80,000 in a bullish sign for BTC", "source": "coindesk", "sentiment": "bullish", "impact": 5, "signal": "OPPORTUNITY", "assets": ["BTC"]},
    {"ts": "2026-05-05T19:39:54+08:00", "headline": "Toncoin surges 36% as Telegram replaces TON Foundation and slashes fees", "source": "coindesk", "sentiment": "bullish", "impact": 5, "signal": "OPPORTUNITY", "assets": []},
    {"ts": "2026-05-05T18:05:51+08:00", "headline": "Bitcoin tops $80,000 as altcoins rally and risk appetite returns", "source": "coindesk", "sentiment": "bullish", "impact": 5, "signal": "OPPORTUNITY", "assets": ["BTC", "ETH", "SOL"]},
    {"ts": "2026-05-05T16:18:23+08:00", "headline": "DeFi lender Aave asks court to block $71 million crypto seizure tied to North Korea claims", "source": "coindesk", "sentiment": "bearish", "impact": 6, "signal": "CAUTION", "assets": ["ETH", "BTC", "SOL"]},
    {"ts": "2026-05-05T14:45:26+08:00", "headline": "Bitcoin used to hate inflation. Now it might be the opposite", "source": "coindesk", "sentiment": "bullish", "impact": 5, "signal": "OPPORTUNITY", "assets": ["BTC", "ETH", "SOL"]},
    {"ts": "2026-05-05T14:12:38+08:00", "headline": "Ripple to share North Korean threat intelligence with crypto firms", "source": "coindesk", "sentiment": "bearish", "impact": 6, "signal": "CAUTION", "assets": ["BTC", "ETH", "SOL"]},
    {"ts": "2026-05-05T13:50:16+08:00", "headline": "Bitcoin crosses $81,000, ETH, SOL, DOGE steady as options desks bid on further price jump", "source": "coindesk", "sentiment": "bullish", "impact": 6, "signal": "OPPORTUNITY", "assets": ["BTC", "ETH", "SOL", "GOLD", "OIL"]},
    {"ts": "2026-05-05T13:16:24+08:00", "headline": "XRP slips below $1.40 on heavy volume, tightening range puts breakout in focus", "source": "coindesk", "sentiment": "bullish", "impact": 5, "signal": "OPPORTUNITY", "assets": []},
    {"ts": "2026-05-05T10:05:26+08:00", "headline": "Bitcoin tests $80,000 as Asia's bid fades and Hong Kong AI IPOs surge", "source": "coindesk", "sentiment": "bullish", "impact": 6, "signal": "OPPORTUNITY", "assets": ["BTC"]},
    {"ts": "2026-05-05T01:34:28+08:00", "headline": "Circle, Coinbase lead crypto stocks rally amid Clarity Act progress, bitcoin hitting $80,000", "source": "coindesk", "sentiment": "bullish", "impact": 6, "signal": "OPPORTUNITY", "assets": ["BTC", "ETH", "SOL"]},
    {"ts": "2026-05-05T00:30:00+08:00", "headline": "The government should promote innovation, not punish it", "source": "coindesk", "sentiment": "bullish", "impact": 5, "signal": "OPPORTUNITY", "assets": ["BTC", "ETH", "SOL"]}
]

high_impact = [item for item in NEWS_DATA if item['impact'] >= 6]
bearish_high = sum(1 for item in high_impact if item['sentiment'] == 'bearish')
bullish_high = sum(1 for item in high_impact if item['sentiment'] == 'bullish')

print(f"High-impact news count: {len(high_impact)}")
print(f"Bearish high count: {bearish_high}")
print(f"Bullish high count: {bullish_high}")

# Determine sentiment and risk level
if bearish_high >= 2:
    sentiment = "BEARISH"
    risk_level = "HIGH_VOL"
elif bullish_high >= 2:
    sentiment = "BULLISH"  
    risk_level = "LOW_RISK"
else:
    sentiment = "NEUTRAL"
    risk_level = "NORMAL"

print(f"Sentiment: {sentiment}")
print(f"Risk Level: {risk_level}")
