import sqlite3

DB_PAPER = '/home/fol2hk/.openclaw/workspace/dev/ai_quant/trading_engine.db'

conn = sqlite3.connect(DB_PAPER)
c = conn.cursor()
c.execute("SELECT timestamp, action, type, pnl FROM trades ORDER BY id DESC LIMIT 5")
rows = c.fetchall()
print("Sample trades:")
for row in rows:
    print(row)
conn.close()
