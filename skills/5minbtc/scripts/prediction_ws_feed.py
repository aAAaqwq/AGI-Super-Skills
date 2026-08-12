#!/usr/bin/env python3
"""币安 w3w-prediction WebSocket 实时价格源 → 本地 JSON 缓存.

订阅 orderbook 流 (聚合所有市场 topic=web3_prediction_orderbook_data, <200ms 实时),
维护每个 marketId 的最新盘口, 并周期性 (每根 5min K线) 用 REST 快照刷新当前
BTC Up/Down 市场的 UP/DOWN token 权威价。消费方 (5minbtc_watch / paper-monitor)
直接读 ~/bb-auto/prediction-ws.json 即可, 无需各自连 WS 或轮询 REST。

密钥: 从 ~/bb-auto/prediction.env 或 launchctl getenv 加载 (未就绪则等待)。
用法:
  python3 prediction_ws_feed.py            # 前台
  (launchd 托管: com.daniel.prediction-ws-feed)
"""
import asyncio
import hashlib
import hmac
import json
import os
import random
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ENV_FILE = Path.home() / "bb-auto" / "prediction.env"
CACHE = Path.home() / "bb-auto" / "prediction-ws.json"
BASE = "wss://api.binance.com/sapi/wss"
TOPIC = "web3_prediction_orderbook_data"   # 聚合所有市场
REST_REFRESH_SEC = 300                      # 每根 5min K线刷新一次 UP/DOWN 权威价
WS_PING = 30                                # 心跳秒


def _load_env():
    if ENV_FILE.exists():
        try:
            for line in ENV_FILE.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
        except Exception:
            pass
    for v in ("BINANCE_API_KEY", "BINANCE_API_SECRET"):
        if not os.environ.get(v):
            val = _launchctl_getenv(v)
            if val:
                os.environ[v] = val


def _launchctl_getenv(k):
    try:
        out = subprocess.run(["launchctl", "getenv", k], capture_output=True,
                             text=True, timeout=5).stdout.strip()
        return out or None
    except Exception:
        return None


def keys_ready():
    return bool(os.environ.get("BINANCE_API_KEY")
                and os.environ.get("BINANCE_API_SECRET"))


def sign_url(topic):
    params = {"random": str(random.random()), "topic": topic,
              "recvWindow": "30000", "timestamp": str(int(time.time() * 1000))}
    qs = urllib.parse.urlencode(sorted(params.items()))
    sig = hmac.new(os.environ["BINANCE_API_SECRET"].encode(), qs.encode(),
                   hashlib.sha256).hexdigest()
    return f"{BASE}?{qs}&signature={sig}"


def rest_current():
    """REST 快照当前 BTC 5m 预测市场的 UP/DOWN token 价 (权威)."""
    try:
        sys.path.insert(0, str(Path.home() / ".claude/skills/5minbtc/scripts"))
        import importlib
        trader = importlib.import_module("5minbtc_trader")
        found = trader.find_btc_5m_market()
        if not found:
            return None
        _, market_id, up_tok, down_tok, _, _ = found
        return {"market_id": market_id, "up_token": up_tok, "down_token": down_tok,
                "up_ask": trader._token_price(market_id, up_tok),
                "down_ask": trader._token_price(market_id, down_tok),
                "ts": int(time.time() * 1000)}
    except Exception as e:
        print(f"REST 快照失败: {e}", file=sys.stderr)
        return None


class Feed:
    def __init__(self):
        self.cache = {"updated_ms": 0, "markets": {}, "current": None}
        self.last_write = 0.0

    def write(self):
        now = time.time()
        if now - self.last_write < 0.2:      # ~200ms 节流
            return
        self.last_write = now
        self.cache["updated_ms"] = int(time.time() * 1000)
        try:
            CACHE.write_text(json.dumps(self.cache, ensure_ascii=False))
        except Exception as e:
            print(f"写缓存失败: {e}", file=sys.stderr)

    async def run(self):
        import websockets
        while True:
            try:
                url = sign_url(TOPIC)
                print(f"WS 连接: {url.split('?')[0]} (topic={TOPIC})", flush=True)
                async with websockets.connect(
                        url, additional_headers={"X-MBX-APIKEY": os.environ["BINANCE_API_KEY"]},
                        ping_interval=WS_PING, ping_timeout=WS_PING * 2) as ws:
                    # 连接后立即 REST 刷新当前市场 UP/DOWN 权威价 (不等 300s)
                    cur = rest_current()
                    if cur:
                        self.cache["current"] = cur
                        self.write()
                        print(f"REST 初始刷新: market={cur['market_id']} "
                              f"UP={cur['up_ask']} DOWN={cur['down_ask']}", flush=True)
                    last_rest = time.time()
                    while True:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=WS_PING * 3)
                        except asyncio.TimeoutError:
                            continue
                        try:
                            env = json.loads(raw)
                        except Exception:
                            continue
                        if env.get("type") != "TOPIC":
                            continue
                        try:
                            data = json.loads(env.get("data") or "{}")
                        except Exception:
                            continue
                        if data.get("msgType") != "orderbook":
                            continue
                        mid = data.get("marketId")
                        asks = data.get("asks") or []
                        bids = data.get("bids") or []
                        self.cache["markets"][str(mid)] = {
                            "best_ask": asks[0][0] if asks else None,
                            "best_bid": bids[0][0] if bids else None,
                            "asks": asks, "bids": bids,
                            "ts": data.get("updateTimestampMs"),
                        }
                        self.write()

                        # 周期性 REST 刷新当前市场 UP/DOWN 权威价 (每根K线)
                        if time.time() - last_rest >= REST_REFRESH_SEC:
                            cur = rest_current()
                            if cur:
                                self.cache["current"] = cur
                                last_rest = time.time()
                                self.write()
                                print(f"REST 刷新: market={cur['market_id']} "
                                      f"UP={cur['up_ask']} DOWN={cur['down_ask']}", flush=True)
            except Exception as e:
                print(f"WS 断开/异常: {e}, 3s 后重连", file=sys.stderr)
                await asyncio.sleep(3)


def main():
    _load_env()
    while not keys_ready():
        print(f"[{time.strftime('%F %T')}] ⏳ 等待币安预测API密钥 "
              f"(写入 {ENV_FILE})...", flush=True)
        time.sleep(30)
        _load_env()
    print(f"✅ 密钥就绪, 启动 WS 实时价格源 → {CACHE}", flush=True)
    asyncio.run(Feed().run())


if __name__ == "__main__":
    main()
