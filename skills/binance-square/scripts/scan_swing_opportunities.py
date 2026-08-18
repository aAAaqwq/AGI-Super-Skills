#!/usr/bin/env python3
"""短线波段机会扫描（1-2 天持仓）。

直连 Binance Futures 公共行情 API（绕过 macOS 系统代理），
扫描全市场 USDT 永续合约，识别 1-2 天持仓机会。

v2 特性：
  - 过滤股票代币（contractType == TRADIFI_PERPETUAL，如 MSFT/GOOGL/TSLA/AMD）
  - 多空双向信号（做多 3 类 + 做空 3 类）
  - 质量门（RR≥1.3 + 排除接飞刀/追高/追空）
  - 1h 级别入场触发确认（把机会池拆成「可执行 confirmed / 观察 waiting」）

产出 JSON：{"confirmed": [...], "waiting": [...]}
纯标准库实现，不依赖 numpy/pandas。
"""

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

FAPI = "https://fapi.binance.com"
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _get(path: str, params: dict[str, str] | None = None, timeout: float = 10) -> Any:
    url = FAPI + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    req = urllib.request.Request(url, headers={"User-Agent": "swing-scanner/1.0"})
    with _OPENER.open(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _candles(rows: list[list[Any]]) -> list[dict]:
    out = []
    for r in rows:
        out.append({
            "open": float(r[1]),
            "high": float(r[2]),
            "low": float(r[3]),
            "close": float(r[4]),
            "volume": float(r[5]),
            "quote_volume": float(r[7]),
        })
    return out


def _sma(vals: list[float], n: int) -> float:
    return sum(vals[-n:]) / n


def _ema(vals: list[float], n: int) -> list[float]:
    k = 2 / (n + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def _rsi(closes: list[float], n: int = 14) -> float:
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    if len(gains) < n:
        return 50.0
    avg_g = sum(gains[-n:]) / n
    avg_l = sum(losses[-n:]) / n
    if avg_l == 0:
        return 100.0
    rs = avg_g / avg_l
    return 100 - 100 / (1 + rs)


def _atr(candles: list[dict], n: int = 14) -> float:
    trs = []
    for i in range(1, len(candles)):
        c = candles[i]
        p = candles[i - 1]
        tr = max(c["high"] - c["low"], abs(c["high"] - p["close"]), abs(c["low"] - p["close"]))
        trs.append(tr)
    return sum(trs[-n:]) / n if trs else 0.0


def _bollinger(closes: list[float], n: int = 20) -> tuple[float, float, float]:
    mid = _sma(closes, n)
    var = sum((c - mid) ** 2 for c in closes[-n:]) / n
    std = var ** 0.5
    return mid - 2 * std, mid, mid + 2 * std


def fetch_tickers(min_quote_volume: float = 20_000_000.0) -> list[dict]:
    """拉全市场 24hr ticker，过滤 USDT 永续 + 流动性阈值。

    只保留加密货币永续（contractType == PERPETUAL），排除股票代币
    （TRADIFI_PERPETUAL，如 MSFT/GOOGL/TSLA/AMD，波动小不适合波段）。
    """
    crypto_syms: set[str] | None = None
    try:
        ei = _get("/fapi/v1/exchangeInfo")
        crypto_syms = {
            s["symbol"]
            for s in ei.get("symbols", [])
            if s.get("contractType") == "PERPETUAL"
            and s.get("quoteAsset") == "USDT"
            and s.get("status") == "TRADING"
        }
    except Exception:
        crypto_syms = None
    raw = _get("/fapi/v1/ticker/24hr")
    out = []
    for t in raw:
        sym = t.get("symbol", "")
        if crypto_syms is not None and sym not in crypto_syms:
            continue  # 排除股票代币等非加密币合约
        if not sym.endswith("USDT"):
            continue
        base = sym[:-4]
        # 排除杠杆代币 / 特殊合约
        if any(x in base for x in ("UP", "DOWN", "BULL", "BEAR", "_", "1000")):
            if base.endswith(("UP", "DOWN", "BULL", "BEAR")) or base.endswith("1000"):
                # 1000SHIB 等是正常合约，保留；UP/DOWN/BULL/BEAR 杠杆代币排除
                if base.endswith(("UP", "DOWN", "BULL", "BEAR")):
                    continue
        try:
            qv = float(t.get("quoteVolume", 0))
            pct = float(t.get("priceChangePercent", 0))
            last = float(t.get("lastPrice", 0))
        except (TypeError, ValueError):
            continue
        if qv < min_quote_volume or last <= 0:
            continue
        out.append({"symbol": sym, "last": last, "pct": pct, "quote_volume": qv})
    out.sort(key=lambda x: x["quote_volume"], reverse=True)
    return out


def analyze(sym: str, last: float) -> dict | None:
    """拉 4h klines，计算指标，识别机会。"""
    try:
        rows = _get("/fapi/v1/klines", {"symbol": sym, "interval": "4h", "limit": "120"})
    except Exception:
        return None
    if not isinstance(rows, list) or len(rows) < 60:
        return None
    candles = _candles(rows)
    closes = [c["close"] for c in candles]
    ema20 = _ema(closes, 20)
    ema50 = _ema(closes, 50)
    rsi = _rsi(closes)
    atr = _atr(candles)
    lower, mid, upper = _bollinger(closes)
    price = closes[-1]
    if price <= 0 or atr <= 0:
        return None
    atr_pct = atr / price

    signal = None
    # 类型1：多头趋势回调买入
    if ema20[-1] > ema50[-1] and ema20[-2] <= ema50[-2]:
        pass  # 刚金叉，趋势未稳，暂不作为主要信号
    uptrend = ema20[-1] > ema50[-1]
    pullback = uptrend and price <= ema20[-1] * 1.01 and price >= ema20[-1] * 0.985 and 35 <= rsi <= 55
    if pullback:
        entry = price
        sl = min(ema50[-1] * 0.99, price - atr * 1.8)
        tp = price + atr * 2.8
        signal = {
            "type": "趋势回调做多",
            "direction": "long",
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "rr": (tp - entry) / (entry - sl) if entry > sl else 0,
            "rsi": rsi,
            "atr_pct": atr_pct,
        }

    # 类型2：超卖反弹
    if signal is None and rsi < 32 and price <= lower * 1.01:
        entry = price
        sl = price - atr * 1.5
        tp = price + atr * 2.5
        signal = {
            "type": "超卖反弹做多",
            "direction": "long",
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "rr": (tp - entry) / (entry - sl) if entry > sl else 0,
            "rsi": rsi,
            "atr_pct": atr_pct,
        }

    # 类型3：放量突破布林上轨（动量做多，激进）
    if signal is None:
        vol_avg = _sma([c["quote_volume"] for c in candles], 20)
        vol_now = candles[-1]["quote_volume"]
        if price >= upper and vol_now >= vol_avg * 1.8 and rsi >= 60:
            entry = price
            sl = price - atr * 1.6
            tp = price + atr * 2.2
            signal = {
                "type": "放量突破做多",
                "direction": "long",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "rr": (tp - entry) / (entry - sl) if entry > sl else 0,
                "rsi": rsi,
                "atr_pct": atr_pct,
            }

    # 类型4：空头趋势反弹做空（稳健）
    downtrend = ema20[-1] < ema50[-1]
    rally = downtrend and price >= ema20[-1] * 0.99 and price <= ema20[-1] * 1.015 and 45 <= rsi <= 65
    if signal is None and rally:
        entry = price
        sl = max(ema50[-1] * 1.01, price + atr * 1.8)
        tp = price - atr * 2.8
        signal = {
            "type": "趋势反弹做空",
            "direction": "short",
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "rr": (entry - tp) / (sl - entry) if sl > entry else 0,
            "rsi": rsi,
            "atr_pct": atr_pct,
        }

    # 类型5：超买回落做空（激进）
    if signal is None and rsi > 68 and price >= upper * 0.99:
        entry = price
        sl = price + atr * 1.5
        tp = price - atr * 2.5
        signal = {
            "type": "超买回落做空",
            "direction": "short",
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "rr": (entry - tp) / (sl - entry) if sl > entry else 0,
            "rsi": rsi,
            "atr_pct": atr_pct,
        }

    # 类型6：放量跌破布林下轨（动量做空）
    if signal is None:
        vol_avg = _sma([c["quote_volume"] for c in candles], 20)
        vol_now = candles[-1]["quote_volume"]
        if price <= lower and vol_now >= vol_avg * 1.8 and rsi <= 40:
            entry = price
            sl = price + atr * 1.6
            tp = price - atr * 2.2
            signal = {
                "type": "放量跌破做空",
                "direction": "short",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "rr": (entry - tp) / (sl - entry) if sl > entry else 0,
                "rsi": rsi,
                "atr_pct": atr_pct,
            }

    if signal is None:
        return None
    return {
        "symbol": sym,
        "last": price,
        "pct24h": None,
        "atr_pct": atr_pct,
        "rsi": rsi,
        "ema20": ema20[-1],
        "ema50": ema50[-1],
        **signal,
    }


def _passes_quality_gate(r: dict, pct24h: float) -> bool:
    """质量门：盈亏比达标 + 排除接飞刀/追高。"""
    if r["rr"] < 1.3:
        return False
    # 超卖反弹但 24h 暴跌超 15% = 接飞刀，不是正常超卖
    if r["type"] == "超卖反弹做多" and pct24h < -15:
        return False
    # 放量突破但 RSI > 75 = 追高
    if r["type"] == "放量突破做多" and r["rsi"] > 75:
        return False
    # 超买回落但 24h 暴涨超 15% = 追空接刀
    if r["type"] == "超买回落做空" and pct24h > 15:
        return False
    # 放量跌破但 RSI < 25 = 追空
    if r["type"] == "放量跌破做空" and r["rsi"] < 25:
        return False
    return True


def _entry_trigger(sym: str, direction: str) -> dict | None:
    """1h 级别入场触发确认。

    返回 {'status': 'confirmed'|'waiting', 'trigger': float, 'note': str}
    - long : 价格站上 1h EMA20 → confirmed（顺势确认）
    - short: 价格跌破 1h EMA20 → confirmed（顺势确认）
    """
    try:
        rows = _get("/fapi/v1/klines", {"symbol": sym, "interval": "1h", "limit": "60"})
    except Exception:
        return None
    if not isinstance(rows, list) or len(rows) < 30:
        return None
    closes = [float(r[4]) for r in rows]
    ema20 = _ema(closes, 20)
    price = closes[-1]
    ema = ema20[-1]
    if direction == "long":
        if price > ema:
            return {"status": "confirmed", "trigger": ema, "note": f"已站上1h EMA20({ema:g})"}
        return {"status": "waiting", "trigger": ema, "note": f"等站上1h EMA20({ema:g})再进"}
    else:
        if price < ema:
            return {"status": "confirmed", "trigger": ema, "note": f"已跌破1h EMA20({ema:g})"}
        return {"status": "waiting", "trigger": ema, "note": f"等跌破1h EMA20({ema:g})再空"}


def main() -> int:
    print(f"[SCAN] 拉取全市场 ticker @ {datetime.now(timezone.utc).isoformat()}", file=sys.stderr)
    tickers = fetch_tickers()
    print(f"[SCAN] 流动性过滤后候选: {len(tickers)} 个加密币 USDT 永续", file=sys.stderr)
    # 只扫前 120 个高流动性币，控制请求量
    results = []
    for t in tickers[:120]:
        r = analyze(t["symbol"], t["last"])
        if r and _passes_quality_gate(r, t["pct"]):
            r["pct24h"] = t["pct"]
            r["trigger"] = _entry_trigger(t["symbol"], r["direction"])
            results.append(r)
    # 分两组：可执行（1h 已确认）vs 观察（等触发）
    confirmed = [r for r in results if r["trigger"] and r["trigger"]["status"] == "confirmed"]
    waiting = [r for r in results if r["trigger"] and r["trigger"]["status"] == "waiting"]
    confirmed.sort(key=lambda x: x["rr"], reverse=True)
    waiting.sort(key=lambda x: x["rr"], reverse=True)
    out = {"confirmed": confirmed, "waiting": waiting}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"[SCAN] 命中 {len(results)}：可执行 {len(confirmed)} / 观察 {len(waiting)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
