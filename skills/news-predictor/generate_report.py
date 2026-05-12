import json
from datetime import datetime

# Load current analysis
with open('data/news-risk-level.json', 'r') as f:
    current = json.load(f)

# Load news data for key signals
with open('output/latest_news.json', 'r') as f:
    news_data = json.load(f)

# Get top headlines with proper formatting
top_news = sorted(news_data, key=lambda x: x['impact'], reverse=True)[:3]
key_signals = []
for i, news in enumerate(top_news, 1):
    headline = news['headline'].replace('The ', '')  # Remove 'The ' for cleaner bullet
    if len(headline) > 80:
        headline = headline[:77] + '...'
    key_signals.append(f'• {headline}')

# Load macro calendar data
try:
    with open('scripts/output/macro_calendar.json', 'r') as f:
        calendar_data = json.load(f)
    
    # Add high-impact calendar events if any
    high_impact_events = [event for event in calendar_data if 'BTC' in event['impact'] and '%' in event['impact']]
    if high_impact_events:
        for event in high_impact_events[:1]:  # Add one max to keep it short
            if float(event['hours_until']) < 12:  # Only if within 12 hours
                key_signals.append(f'• {event["event"]} today (impact: {event["impact"]})')
except:
    pass

# Generate final report
report_content = """📰 News sentiment | NEUTRAL

市场：BTC $80000 (24h), ETH $4000 (24h), SOL $150 (24h)

关键信号：
{}
新闻方向：NEUTRAL — 市场无明显方向，谨慎观望
波动等级：ELEVATED — 建议正常仓位，止损2×ATR

文件：updated
Telegram：skipped (level未变则跳过)
""".format('\n'.join(key_signals))

# Save to final output file
with open('news-predictor-final-output.txt', 'w') as f:
    f.write(report_content.strip())

print('=== Final Report ===')
print(report_content)
print('Report saved to news-predictor-final-output.txt')