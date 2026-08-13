#!/usr/bin/env python3
"""真订单流 OFI 采集 — trade + bookTicker 组合流, tick 规则推断主动买卖.

aggTrade 流(带 m aggressor 标记)在本网络不推送, 改用:
  订阅 btcusdt@trade + btcusdt@bookTicker
  每笔成交价 >= 卖一价 → 主动买(buy aggressor); <= 买一价 → 主动卖
  OFI = (主动买量 - 主动卖量) / 总量, 归一化 [-1,1], 5分钟滚动窗口.
写缓存 ~/bb-auto/ofi.json 供 5minbtc 引擎读, 做 half_body 延续确认.

用法: python3 ofi_feed.py  (launchd 托管: com.daniel.ofi-feed)
"""
import asyncio
import json
import sys
import time
from pathlib import Path

import websockets

WS = "wss://fstream.binance.com/ws/btcusdt@trade/btcusdt@bookTicker"
CACHE = Path.home() / "bb-auto" / "ofi.json"
WINDOW_SEC = 300  # 5分钟滚动窗口


class OfiFeed:
    def __init__(self):
        self.buy_vol = 0.0
        self.sell_vol = 0.0
        self.window_start = time.time()
        self.last_write = 0.0
        self.best_bid = 0.0
        self.best_ask = 0.0

    def write(self):
        total = self.buy_vol + self.sell_vol
        ofi = (self.buy_vol - self.sell_vol) / total if total > 0 else 0.0
        data = {
            "ofi": round(ofi, 4),
            "buy_vol": round(self.buy_vol, 2),
            "sell_vol": round(self.sell_vol, 2),
            "net": round(self.buy_vol - self.sell_vol, 2),
            "window_sec": round(time.time() - self.window_start),
            "ts": int(time.time() * 1000),
        }
        try:
            CACHE.write_text(json.dumps(data))
        except Exception as e:
            print(f"写缓存失败: {e}", file=sys.stderr)

    def classify(self, price):
        """tick 规则: 成交价 vs 最优买卖价 → 主动买/卖/不确定."""
        if self.best_ask > 0 and price >= self.best_ask:
            return "buy"
        if self.best_bid > 0 and price <= self.best_bid:
            return "sell"
        # 价差内: 用 mid 判断
        if self.best_bid > 0 and self.best_ask > 0:
            mid = (self.best_bid + self.best_ask) / 2
            return "buy" if price >= mid else "sell"
        return None

    async def run(self):
        print(f"OFI 采集启动: {WS} → {CACHE}", flush=True)
        while True:
            try:
                async with websockets.connect(WS, ping_interval=20, ping_timeout=20) as ws:
                    print("OFI WS 已连接 (trade+bookTicker)", flush=True)
                    while True:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=60)
                        except asyncio.TimeoutError:
                            continue
                        msg = json.loads(raw)
                        e = msg.get("e", "")
                        if e == "bookTicker":
                            self.best_bid = float(msg.get("b", 0) or 0)
                            self.best_ask = float(msg.get("a", 0) or 0)
                        elif e == "trade":
                            price = float(msg.get("p", 0) or 0)
                            qty = float(msg.get("q", 0) or 0)
                            side = self.classify(price)
                            if side == "buy":
                                self.buy_vol += qty
                            elif side == "sell":
                                self.sell_vol += qty
                        # 5分钟滚动窗口重置
                        if time.time() - self.window_start >= WINDOW_SEC:
                            self.buy_vol = self.sell_vol = 0.0
                            self.window_start = time.time()
                        # 节流写缓存 (1s)
                        if time.time() - self.last_write >= 1.0:
                            self.write()
                            self.last_write = time.time()
            except Exception as e:
                print(f"OFI WS 断开: {e}, 3s 重连", file=sys.stderr)
                await asyncio.sleep(3)


if __name__ == "__main__":
    asyncio.run(OfiFeed().run())
