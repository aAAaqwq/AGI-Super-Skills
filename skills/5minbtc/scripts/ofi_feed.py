#!/usr/bin/env python3
"""真订单流 OFI 采集 v2 — 原生 aggressor (futures @trade 流 m 标记).

v2 相对 v1 的关键修复 (对抗审查 F1-F8):
- 原生 aggressor: futures @trade 每条 msg 自带 m (buyer is maker). m=False → 主动买(taker buy),
  m=True → 主动卖(taker sell). 100% 精确. 弃用 v1 的 tick 规则推断
  (实测仅 62.6% / 量加权 66.3%, 37% 成交判错边). @trade 流在本网络确认推送且带 m.
- 蜡烛对齐窗口: 从 trade 的 T (ms) 推导 UTC 5min 边界, 边界处重置 in-candle 累计量,
  不再用进程启动对齐的固定 300s 滚动桶 (修时间错配 F5).
- ofi_60: 最近 60s 净流环形缓冲, 作领先/新鲜度指标 (供引擎做新鲜度反转保护).
- 质量闸: classification_ratio + last_trade_ts 保鲜 + in-candle 最低量门槛.
- WS 稳定性: ping_interval 降到 15s + 指数退避重连 (1s/3s/10s) (修 1011 keepalive timeout).
- bookTicker 保留订阅 (网络零改动) 但不再参与 aggressor 判定, 仅作兜底与留档.

用法: python3 ofi_feed.py  (launchd 托管: com.daniel.ofi-feed)
"""
import asyncio
import json
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import websockets

WS = "wss://fstream.binance.com/ws/btcusdt@trade/btcusdt@bookTicker"
CACHE = Path.home() / "bb-auto" / "ofi.json"
CANDLE_MS = 300_000       # 5分钟蜡烛
OFI60_MS = 60_000         # 最近60s净流窗口
TRADE_KEEP_MS = 120_000   # 环形缓冲保留时长 (算 ofi_60 需要)
MIN_WINDOW_SEC = 45       # in-candle 决策至少 45s 窗口
MIN_VOL_BTC = 20.0        # in-candle 最低总成交量 (BTC), 防窗口重置后单笔噪声
BACKOFF = [1, 3, 10]      # 重连退避 (秒)


class OfiFeed:
    def __init__(self):
        self.candle_buy = 0.0
        self.candle_sell = 0.0
        self.candle_amb = 0.0          # 无法判定的量 (m 缺失时兜底, 正常为 0)
        self.candle_start_ms = 0       # 当前 5m 蜡烛起点 (UTC ms)
        self.candle_iso = ""
        self.trades = deque()          # (ts_ms, qty, is_buy), 最近 ~120s
        self.last_trade_ms = 0
        self.last_write = 0.0
        self.agg_native = True         # m 字段可用 → 真 OFI
        self.best_bid = 0.0            # 仅兜底 classify 用
        self.best_ask = 0.0
        # 对齐到当前 5m 边界, 保证首写就有正确的 window_sec
        now_ms = int(time.time() * 1000)
        self.candle_start_ms = (now_ms // CANDLE_MS) * CANDLE_MS
        self.candle_iso = self._iso(self.candle_start_ms)

    @staticmethod
    def _iso(ms):
        return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ---- 蜡烛对齐 (v2: 从 trade 的 T 推导 5min 边界) ----
    def _sync_candle(self, ts_ms):
        boundary = (ts_ms // CANDLE_MS) * CANDLE_MS
        if boundary != self.candle_start_ms:
            self.candle_start_ms = boundary
            self.candle_buy = self.candle_sell = self.candle_amb = 0.0
            self.candle_iso = self._iso(boundary)

    # ---- 最近60s 净流 (领先/新鲜度指标) ----
    def _ofi_60(self, now_ms):
        while self.trades and now_ms - self.trades[0][0] > TRADE_KEEP_MS:
            self.trades.popleft()
        buy = sum(q for _, q, is_buy in self.trades if is_buy)
        sell = sum(q for _, q, is_buy in self.trades if not is_buy)
        total = buy + sell
        if total <= 0:
            return 0.0, 0.0
        return (buy - sell) / total, total

    def write(self):
        now_ms = int(time.time() * 1000)
        ofi_60, vol_60 = self._ofi_60(now_ms)
        total_c = self.candle_buy + self.candle_sell
        window_sec = round((now_ms - self.candle_start_ms) / 1000) if self.candle_start_ms else 0
        low_vol = total_c < MIN_VOL_BTC
        ofi_candle = (self.candle_buy - self.candle_sell) / total_c if total_c > 0 else 0.0
        if low_vol:
            ofi_candle = 0.0  # 流量不足 → 信号置中性, 引擎不会把它当冲突
        fresh = (now_ms - self.last_trade_ms) < 10_000
        cr = total_c / (total_c + self.candle_amb) if (total_c + self.candle_amb) > 0 else 1.0
        data = {
            "ofi": round(ofi_candle, 4),             # 向后兼容旧字段
            "ofi_candle": round(ofi_candle, 4),      # 蜡烛对齐净流 (主字段)
            "ofi_60": round(ofi_60, 4),              # 最近60s净流 (领先指标)
            "buy_vol": round(self.candle_buy, 2),
            "sell_vol": round(self.candle_sell, 2),
            "net": round(self.candle_buy - self.candle_sell, 2),
            "window_sec": window_sec,
            "candle_iso": self.candle_iso,
            "classification_ratio": round(cr, 4),
            "agg_native": self.agg_native,
            "feed_fresh": fresh,
            "low_vol": low_vol,
            "last_trade_ts": self.last_trade_ms,
            "ts": now_ms,
        }
        try:
            CACHE.write_text(json.dumps(data))
        except Exception as e:
            print(f"写缓存失败: {e}", file=sys.stderr)

    def classify(self, price):
        """兜底 tick 规则 (仅当 msg 无 m 字段时). 正常路径用原生 m, 不走这里."""
        if self.best_ask > 0 and price >= self.best_ask:
            return "buy"
        if self.best_bid > 0 and price <= self.best_bid:
            return "sell"
        if self.best_bid > 0 and self.best_ask > 0:
            mid = (self.best_bid + self.best_ask) / 2
            return "buy" if price >= mid else "sell"
        return None

    def _on_trade(self, msg):
        ts = int(msg.get("T", 0) or 0)
        qty = float(msg.get("q", 0) or 0)
        if qty <= 0:
            return
        if ts > 0:
            self._sync_candle(ts)  # 先对齐蜡烛 (边界处重置 in-candle 累计)
        m = msg.get("m")
        if m is False:
            # 原生: m=False → 主动买 (taker buy)
            self.candle_buy += qty
            is_buy = True
        elif m is True:
            # 原生: m=True → 主动卖 (taker sell)
            self.candle_sell += qty
            is_buy = False
        else:
            # m 缺失 (理论不发生) → 兜底 tick 规则
            side = self.classify(float(msg.get("p", 0) or 0))
            if side == "buy":
                self.candle_buy += qty
                is_buy = True
            elif side == "sell":
                self.candle_sell += qty
                is_buy = False
            else:
                self.candle_amb += qty
                self.agg_native = False
                self.last_trade_ms = ts
                return
        self.trades.append((ts, qty, is_buy))
        self.last_trade_ms = ts

    async def run(self):
        print(f"真OFI 采集启动: {WS} → {CACHE} (原生 m aggressor)", flush=True)
        attempt = 0
        while True:
            try:
                async with websockets.connect(WS, ping_interval=15, ping_timeout=20) as ws:
                    print("真OFI WS 已连接 (trade+bookTicker, 原生 m)", flush=True)
                    attempt = 0
                    while True:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=60)
                        except asyncio.TimeoutError:
                            continue
                        msg = json.loads(raw)
                        e = msg.get("e", "")
                        if e == "bookTicker":
                            # 仅兜底用, 不参与原生 m 判定
                            self.best_bid = float(msg.get("b", 0) or 0)
                            self.best_ask = float(msg.get("a", 0) or 0)
                        elif e == "trade":
                            self._on_trade(msg)
                        # 节流写缓存 (1s)
                        if time.time() - self.last_write >= 1.0:
                            self.write()
                            self.last_write = time.time()
            except Exception as e:
                delay = BACKOFF[min(attempt, len(BACKOFF) - 1)]
                print(f"真OFI WS 断开: {e}, {delay}s 重连", file=sys.stderr)
                attempt += 1
                await asyncio.sleep(delay)


if __name__ == "__main__":
    asyncio.run(OfiFeed().run())
