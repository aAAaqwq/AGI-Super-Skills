#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scripts/5minbtc_trader.py - 5minbtc 预测 → 币安「Web3 Wallet 预测交易」桥接

读取 5minbtc 引擎 JSON 预测, 判定交易信号, 直接签名调用币安预测市场 API
(BTC 5min 涨跌市场, Polymarket 式 outcome token, 非合约).
引擎 bias=bull → 买 UP token; bias=bear → 买 DOWN token.

风险契约 (铁律, 预测交易没有 test 模式 — 下单即真实花钱):
- 默认行为 = 只取报价 (get-quote 不花钱), 绝不自动成交
- 成交必须人工确认: 每单输入 y 同意, 且 --live 另需启动时的 yes 双闸门
- 真实花钱的是 place-order-bundle (FOK 市价), 确认闸门就放在它前面
- 金额默认小注 2.0 USDT, 下单前校验余额, 不足即拒
- 市场过期保护: 每根K线只对当前 OPEN 的 btc-updown-5m 市场取价/下单

用法:
  # 单次: 读引擎 → 判定信号 → 发现市场 → 报价(不成交, 除非确认)
  python3 scripts/5minbtc_trader.py --once [--amount 2.0]
  # 持续监控 (每根K线第2/3/4分钟采样)
  python3 scripts/5minbtc_trader.py --loop [--rounds N]
  # 实盘 (危险! 启动需输 yes, 每单再输 y)
  python3 scripts/5minbtc_trader.py --once --live --amount 2.0

环境变量:
  BINANCE_API_KEY / BINANCE_API_SECRET   (必填, 签名用)
  BINANCE_PREDICT_WALLET                  (钱包地址, 默认已验证值)
  BINANCE_PREDICT_WALLET_ID               (钱包 ID,  默认已验证值)

依赖: 纯 Python 标准库 (urllib/hmac/hashlib/json). 不打印密钥.
非投资建议 — 仅供量化研究, 市场风险自负.
"""
import argparse
import datetime
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # = skill 根 (5minbtc/)
ENGINE = ROOT / "5minbtc-engine-v5.7.py"

# ---- 币安预测 API ----
API_BASE = "https://api.binance.com"
API_KEY = os.environ.get("BINANCE_API_KEY", "")
API_SECRET = os.environ.get("BINANCE_API_SECRET", "")
WALLET = os.environ.get(
    "BINANCE_PREDICT_WALLET",
    "0x0000000000000000000000000000000000000000")   # 已验证钱包地址
WALLET_ID = os.environ.get(
    "BINANCE_PREDICT_WALLET_ID",
    "00000000000000000000000000000000")              # 已验证钱包 ID
ACCOUNT_TYPE = os.environ.get("BINANCE_PREDICT_ACCOUNT", "SPOT")  # SPOT|FUNDING

# ---- 信号门槛 ----
MIN_CONF = 55          # conf >= 55 才触发 (低于此区间横跳无意义)
ALLOWED_STRENGTHS = ("medium", "moderate", "strong")
TB_FILTER = True       # 方向必须与 taker_buy 一致

# ---- 下单参数 (预测交易, 无杠杆无止损) ----
DEFAULT_AMOUNT = 2.0      # 默认金额 USDT (小注)
MIN_ORDER_WEI = 1500000000000000000   # MARKET 单 ~1.5 USDT = 1.5e18 wei
SLIPPAGE_BPS = 200        # 滑点容忍 2%
WEI_18 = 10 ** 18
CLOSE_MARGIN_SEC = 45     # 距K线收盘 <45s 警告, <=0 拒绝 (防买已过期token)

SAMPLE_MINUTES = (2, 3, 4)   # 每根 5min K线采样分钟
SAMPLE_SECOND = 5


# ======================== 引擎 ========================

def _load_engine():
    """运行引擎, 返回 dict 或 None."""
    if not ENGINE.exists():
        print(f"ERROR engine not found: {ENGINE}", file=sys.stderr)
        return None
    try:
        out = subprocess_run()
        return json.loads(out)
    except Exception as e:  # noqa: BLE001
        print(f"engine error: {e}", file=sys.stderr)
        return None


def subprocess_run():
    import subprocess
    return subprocess.run(["python3", str(ENGINE)],
                          capture_output=True, text=True, timeout=45).stdout


def _signal(d):
    """从引擎输出判定预测交易信号. 返回 (token_side, reason) 或 (None, reason).
    token_side: "UP" | "DOWN"."""
    p = d["prediction"]
    f = d["factors"]
    bias, strength, conf = p["bias"], p["strength"], p["confidence"]
    tb = f.get("taker_buy", 0.0)

    if conf < MIN_CONF:
        return None, f"conf {conf} < {MIN_CONF}"
    if strength not in ALLOWED_STRENGTHS:
        return None, f"strength {strength} 不足"
    if bias == "neutral":
        return None, "neutral"

    if TB_FILTER:
        if bias == "bear" and tb >= 0:
            return None, f"bear 但 taker_buy {tb:+.2f} ≥ 0, 方向不一致"
        if bias == "bull" and tb <= 0:
            return None, f"bull 但 taker_buy {tb:+.2f} ≤ 0, 方向不一致"

    return ("DOWN" if bias == "bear" else "UP"), f"{bias}/{strength} conf={conf} tb={tb:+.2f}"


# ======================== 币安预测 API 客户端 (纯标准库) ========================

def _signed_request(method, path, params=None):
    """签名并发送币安 SAPI 请求. 返回解析后的 JSON dict.

    签名约定 (SAPI): 签名串 = 原始 urlencoded 参数串.
    GET  -> 签名串为 query string;  POST -> 签名串为 form body (原始串),
            服务器按原始字节验签 (见 batch-cancel 已知问题: 库自动转义括号导致 -1022).
    """
    if not API_KEY or not API_SECRET:
        raise RuntimeError("缺少 BINANCE_API_KEY / BINANCE_API_SECRET 环境变量")
    params = dict(params or {})
    params.setdefault("timestamp", int(time.time() * 1000))
    params.setdefault("recvWindow", 5000)
    # 排序保证签名与发送串一致 (服务器接受任意顺序, 只要匹配)
    qs = urllib.parse.urlencode(sorted(params.items()))
    sig = hmac.new(API_SECRET.encode(), qs.encode(), hashlib.sha256).hexdigest()
    headers = {"X-MBX-APIKEY": API_KEY, "User-Agent": "5minbtc-trader/1.0"}

    if method == "GET":
        url = API_BASE + path + "?" + qs + "&signature=" + sig
        data = None
    else:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        url = API_BASE + path
        data = (qs + "&signature=" + sig).encode()

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code} {path}: {body}") from e
    return json.loads(raw) if raw else {}


def _parse_amount(v):
    """解析余额/金额字段为 USDT float. 兼容 显示值 / 18位wei / hexwei."""
    if v is None:
        return 0.0
    s = str(v).strip()
    if not s:
        return 0.0
    try:
        if s.lower().startswith("0x"):
            return int(s, 16) / WEI_18
        f = float(s)
    except ValueError:
        return 0.0
    return f / WEI_18 if f > 1e12 else f


def get_payment_balance():
    """GET balance/payment-options -> {accountType: item}. item 含
    availableBalanceDisplay / enabled / accountType."""
    data = _signed_request("GET", "/sapi/v1/w3w/wallet/prediction/balance/payment-options")
    items = data.get("items") or data.get("data") or []
    if isinstance(items, dict):      # 容错: 可能是 {accountType: ...} 映射
        items = items.values()
    return {str(it.get("accountType")): it for it in items if isinstance(it, dict)}


def _usable_balance(bal):
    """可用余额 = 各启用 accountType 的 availableBalanceDisplay 之和 (USDT)."""
    return sum(_parse_amount(it.get("availableBalanceDisplay"))
               for it in bal.values() if it.get("enabled", True))


def _extract_outcome_tokens(market):
    """容错扫描 market dict 里的 UP/DOWN outcome token. 返回 (up_id, down_id)."""
    up = down = None
    lists = ("tokens", "tokenList", "outcomes", "variants", "outcomeTokens",
             "resultTokens", "underlyingTokens")
    for key in lists:
        for t in (market.get(key) or []):
            if not isinstance(t, dict):
                continue
            tid = (t.get("tokenId") or t.get("token_id") or t.get("token")
                   or t.get("resultToken") or t.get("id") or t.get("outcomeToken"))
            if not tid:
                continue
            name = " ".join(str(t.get(k) or "") for k in
                            ("name", "title", "outcome", "outcomeName",
                             "displayName", "side", "type", "symbol"))
            nl = name.lower().strip()
            # 方向判定用「词首/精确匹配」, 避免 "uptime"/"updatedAt" 等子串误判
            up_hit = (nl in ("up", "bull", "bullish", "y", "yes", "1")
                      or nl.startswith("up ") or nl.startswith("bull")
                      or nl.startswith("yes"))
            down_hit = (nl in ("down", "bear", "bearish", "n", "no", "0")
                        or nl.startswith("down ") or nl.startswith("bear")
                        or nl.startswith("no"))
            if up_hit:
                if up is None:
                    up = str(tid)
            elif down_hit:
                if down is None:
                    down = str(tid)
    # 兜底: 浅层递归扫描嵌套 dict 中形如 {tokenId, name含Up/Down} 的条目
    if up is None or down is None:
        stack = list(market.values())
        while stack and (up is None or down is None):
            v = stack.pop()
            if isinstance(v, dict):
                tid = (v.get("tokenId") or v.get("token_id") or v.get("token")
                       or v.get("resultToken") or v.get("id"))
                if tid:
                    name = " ".join(str(v.get(k) or "") for k in
                                    ("name", "title", "outcome", "outcomeName", "side"))
                    nl = name.lower().strip()
                    if up is None and (nl in ("up", "bull", "bullish", "y", "yes")
                                       or nl.startswith("up ") or nl.startswith("bull")):
                        up = str(tid)
                    elif down is None and (nl in ("down", "bear", "bearish", "n", "no")
                                           or nl.startswith("down ") or nl.startswith("bear")):
                        down = str(tid)
                stack.extend(v.values())
            elif isinstance(v, (list, tuple)):
                stack.extend(x for x in v if isinstance(x, (dict, list, tuple)))
    return up, down


def find_btc_5m_market():
    """发现当前 OPEN 的 btc-updown-5m 市场.
    返回 (marketTopicId, marketId, up_token_id, down_token_id) 或 None."""
    data = _signed_request("GET", "/sapi/v1/w3w/wallet/prediction/market/list",
                           {"pageSize": 50, "pageNum": 1})
    topics = data.get("marketTopics") or data.get("data") or []
    if isinstance(topics, dict):
        topics = topics.get("marketTopics") or topics.get("list") or []
    for t in topics:
        if not isinstance(t, dict):
            continue
        slug = str(t.get("slug") or "")
        if not slug.startswith("btc-updown-5m"):
            continue
        topic_id = t.get("marketTopicId")
        title = t.get("title") or slug
        for m in (t.get("markets") or []):
            if not isinstance(m, dict):
                continue
            if m.get("tradingStatus") != "OPEN":
                continue
            market_id = m.get("marketId") or m.get("id")
            up_tok, down_tok = _extract_outcome_tokens(m)
            if up_tok is None or down_tok is None:
                # 市场列表没带 token, 尝试 market/detail 补全
                try:
                    detail = _signed_request(
                        "GET", "/sapi/v1/w3w/wallet/prediction/market/detail",
                        {"marketId": market_id})
                    for cand in (detail.get("variants") or detail.get("data") or [detail]):
                        u, d = _extract_outcome_tokens(cand)
                        if up_tok is None:
                            up_tok = u
                        if down_tok is None:
                            down_tok = d
                except Exception as e:  # noqa: BLE001
                    print(f"market/detail 补全 token 失败: {e}", file=sys.stderr)
            if up_tok and down_tok:
                # 收盘时间: topic.endDate (epoch ms), market 层无此字段
                return (topic_id, market_id, up_tok, down_tok,
                        title, t.get("endDate") or m.get("endDate"))
    return None


def get_quote(wallet, token_id, side, amount_usdt, order_type="LIMIT",
              price_limit=None):
    """POST get-quote. 返回响应 dict (含 quoteId).
    side="BUY"|"SELL"; amountIn 用 18位 wei 字符串.
    order_type="LIMIT"(默认, 低挂) | "MARKET"(市价).
    LIMIT 需 price_limit (token 价格, 0~1), 默认 None 则用市价. """
    body = {
        "walletAddress": wallet,
        "tokenId": token_id,
        "side": side,
        "amountIn": str(int(round(amount_usdt * WEI_18))),
        "orderType": order_type,
        "slippageBps": SLIPPAGE_BPS,
    }
    if order_type == "LIMIT":
        if price_limit is None:
            raise ValueError("LIMIT 单需提供 price_limit (token 价格 0~1)")
        body["priceLimit"] = str(int(round(price_limit * WEI_18)))
    return _signed_request("POST", "/sapi/v1/w3w/wallet/prediction/trade/get-quote", body)


def place_order(wallet, wallet_id, quote_id, amount_usdt=None, account_type=ACCOUNT_TYPE,
                order_type="LIMIT"):
    """POST place-order-bundle (真实花钱). 返回响应 dict (含 orderId).
    LIMIT → timeInForce=GTC (挂单等成交); MARKET → FOK."""
    body = {
        "walletAddress": wallet,
        "walletId": wallet_id,
        "quoteId": quote_id,
        "timeInForce": "GTC" if order_type == "LIMIT" else "FOK",
        "accountType": account_type,
        "orderType": order_type,
        "slippageBps": SLIPPAGE_BPS,
    }
    if order_type == "LIMIT":
        # 限价挂单不自动划转 CEX 资金 (资金来自 MPC 钱包)
        pass
    else:
        if amount_usdt is not None:
            body["fundingSource"] = "CEX"
            body["fundTransferAmount"] = str(int(round(amount_usdt * WEI_18)))
    return _signed_request("POST", "/sapi/v1/w3w/wallet/prediction/trade/place-order-bundle",
                           body)


def _order_book(market_id, token_id=None, limit=5):
    """GET order-book: 确认 outcome token 的价格 (up+down≈1).
    需 marketId (+ tokenId). vendor 必填 (服务端约定 predict_fun)."""
    params = {"marketId": market_id, "limit": limit, "vendor": "predict_fun"}
    if token_id:
        params["tokenId"] = token_id
    data = _signed_request("GET", "/sapi/v1/w3w/wallet/prediction/order-book", params)
    return data


def get_positions():
    """GET position/list -> {summary, positions[]}. 当前活跃持仓."""
    data = _signed_request("GET", "/sapi/v1/w3w/wallet/prediction/position/list",
                           {"walletAddress": WALLET, "pageSize": 100, "pageNum": 1})
    return data


def sell_token(token_id, amount_usdt, market_id=None):
    """SELL 卖出持仓 token 锁利/止损 (真实成交). 返回响应 dict."""
    quote = get_quote(WALLET, token_id, "SELL", amount_usdt, order_type="MARKET")
    qid = quote.get("quoteId")
    if not qid:
        raise RuntimeError(f"SELL 报价失败: {quote}")
    return place_order(WALLET, WALLET_ID, qid, order_type="MARKET")


def get_btc_price():
    """GET 公开 ticker/price (免签名) -> BTC 实时价 (float)."""
    url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
    req = urllib.request.Request(url, headers={"User-Agent": "5minbtc-trader/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode())
    return float(data.get("price", 0))


# ======================== 重试机制 ========================

def _retry(fn, retries=10, base_delay=1.0, desc="操作"):
    """带退避的重试. 单次失败不致命, 重试 retries 次 (默认10), 间隔 1,2,4...s.
    全失败抛最后一个异常."""
    last = None
    for i in range(retries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            if i < retries - 1:
                delay = base_delay * (2 ** i)
                print(f"  {desc} 失败 (第{i+1}次): {str(e)[:120]}, {delay:.0f}s 后重试",
                      file=sys.stderr)
                time.sleep(delay)
    raise last if last else RuntimeError(f"{desc} 重试耗尽")


# ======================== 持仓监控 + 止盈止损 ========================

def _pos_field(p, *keys, default=None):
    """容错取持仓字段 (多 key 兼容不同响应结构)."""
    for k in keys:
        if k in p and p[k] not in (None, ""):
            return p[k]
    return default


def _pos_token_id(p):
    v = _pos_field(p, "tokenId", "token_id", "resultToken", "outcomeToken")
    return str(v) if v is not None else None


def _pos_market_id(p):
    return _pos_field(p, "marketId", "market_id")


def _pos_qty(p):
    v = _pos_field(p, "quantity", "qty", "amount", "shareQty", "makerShareQty")
    if v is None:
        return 0.0
    try:
        return float(v) / WEI_18 if float(v) > 1e12 else float(v)
    except (TypeError, ValueError):
        return 0.0


def _pos_price(p, *keys):
    v = _pos_field(p, *keys)
    if v is None:
        return None
    try:
        return float(v) / WEI_18 if float(v) > 1e12 else float(v)
    except (TypeError, ValueError):
        return None


def _pos_side(p):
    s = str(_pos_field(p, "side", "outcome", "outcomeName", "tokenSide", default="") or "").lower()
    if "down" in s or "bear" in s:
        return "DOWN"
    if "up" in s or "bull" in s:
        return "UP"
    return "?"


def monitor_positions(tp_mult=1.4, sl_mult=0.4, interval=10, live=False,
                      max_iters=None):
    """实时监控持仓: 面板 + 止盈/止损自动卖出.
    止盈/止损只在 tp_mult/sl_mult 都 >0 且显式启用时自动执行.
    全部卖出走 SELL, 带重试 (避免单次失败).
    返回: 卖出次数."""
    print(f"\n=== 持仓监控开始 (tp={tp_mult:.2f}x, sl={sl_mult:.2f}x, "
          f"interval={interval}s, live={'YES' if live else 'NO'}) ===")
    if not (tp_mult > 0 and sl_mult > 0):
        print("⚠️  未设定 TP/SL, 仅监控不自动卖出", file=sys.stderr)
    iters = 0
    sold = 0
    while max_iters is None or iters < max_iters:
        iters += 1
        try:
            # BTC 实时价
            try:
                btc = get_btc_price()
            except Exception as e:  # noqa: BLE001
                btc = None
                print(f"  BTC 价获取失败: {e}", file=sys.stderr)
            # 持仓
            data = _retry(get_positions, desc="查询持仓")
            summary = data.get("summary") or {}
            positions = data.get("positions") or []
            if isinstance(positions, dict):
                positions = positions.values()

            # 面板
            print("\n" + "-" * 56)
            print(f"[#{iters}] BTC={btc if btc else 'N/A'}"
                  f"  总资产={summary.get('totalValue', 'N/A')}"
                  f"  今日已实现盈亏={summary.get('todayRealizedPnl', 'N/A')}"
                  f" ({summary.get('todayRealizedPnlPercent', 'N/A')}%)")
            if not positions:
                print("  无活跃持仓")
            for p in positions:
                tid = _pos_token_id(p)
                mkt = _pos_market_id(p)
                side = _pos_side(p)
                qty = _pos_qty(p)
                cost = _pos_price(p, "avgPrice", "averagePrice", "entryPrice")
                cur = _pos_price(p, "currentPrice", "lastPrice", "price")
                upnl = _pos_price(p, "unrealizedPnl", "unrealizedProfit", "pnl")
                # 现价缺失则从 order-book 补
                if cur is None and mkt is not None and tid is not None:
                    try:
                        ob = _retry(lambda: _order_book(mkt, tid), desc="盘口")
                        asks = ob.get("asks") or []
                        bids = ob.get("bids") or []
                        cur = float(asks[0]["price"]) if asks else (
                            float(bids[0]["price"]) if bids else None)
                    except Exception as e:  # noqa: BLE001
                        print(f"  [盘口] {e}", file=sys.stderr)
                print(f"  [{side}] qty={qty:.4f}  cost={cost}  cur={cur}  "
                      f"uPnL={upnl}")
                # 止盈/止损判断
                if not (tp_mult > 0 and sl_mult > 0):
                    continue
                if cost is None or cur is None or qty <= 0:
                    continue
                mult = cur / cost
                action = None
                if mult >= tp_mult:
                    action = f"止盈 (现价/成本 = {mult:.2f} ≥ {tp_mult})"
                elif mult <= sl_mult:
                    action = f"止损 (现价/成本 = {mult:.2f} ≤ {sl_mult})"
                if action:
                    print(f"  ⚡ 触发{action} → 自动卖出 {side} qty={qty:.4f} "
                          f"@ {cur}")
                    if not live:
                        print("  (演练模式, 不实际卖出)")
                        continue
                    amt = max(cur * qty, 1.5)
                    try:
                        res = _retry(lambda: sell_token(tid, amt, mkt),
                                     desc=f"卖出 {side}")
                        sold += 1
                        print(f"  ✅ 卖出完成: {res}")
                    except Exception as e:  # noqa: BLE001
                        print(f"  ❌ 卖出失败: {e}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"监控轮次异常: {e}", file=sys.stderr)
        if max_iters is not None and iters >= max_iters:
            break
        time.sleep(interval)
    return sold


# ======================== 闸门 / 输出 ========================

def _market_expiry_ok(d, close_time=None):
    """市场过期校验. 返回 remaining_sec (>=0).
    优先用 market closeTime (epoch ms 或 ISO), 否则用引擎 remaining_sec.
    remaining_sec <= 0 表示已收盘, 应拒绝下单.
    """
    now_epoch = time.time()
    if close_time:
        try:
            if isinstance(close_time, str) and not close_time.isdigit():
                # ISO 时间 (如 2026-08-11T12:35:00Z)
                from datetime import timezone
                import datetime as _dt
                dt = _dt.datetime.fromisoformat(close_time.replace("Z", "+00:00"))
                close_epoch = dt.timestamp()
            else:
                close_epoch = float(close_time) / 1000  # epoch ms
            return close_epoch - now_epoch
        except Exception:  # noqa: BLE001
            pass
    return float(d.get("candle", {}).get("remaining_sec", 300))


def _confirm_place(title, token_side, token_id, amount_usdt, quote, live):
    """place-order 前的人工确认闸门. 返回 True=同意."""
    qid = quote.get("quoteId")
    print("\n--- 待确认下单 (预测交易, 无test模式, 下单即真实花钱) ---")
    print(f"  市场: {title}")
    print(f"  买入: {token_side} token  {token_id}")
    print(f"  金额: {amount_usdt:.2f} USDT")
    print(f"  quoteId: {qid}")
    for k in ("chance", "averagePrice", "minReceive", "totalFee", "maxAmountIn"):
        if quote.get(k) is not None:
            print(f"  {k}: {quote[k]}")
    if live:
        print("  ⚠️  实盘模式已开启")
    try:
        ans = input("  确认成交? [y/N]: ").strip().lower()
    except EOFError:
        ans = ""
    return ans in ("y", "yes")


# ======================== 主流程 ========================

def _print_quote_summary(title, token_side, token_id, amount_usdt, quote):
    print("\n=== 报价摘要 ===")
    print(f"  市场: {title}")
    print(f"  方向: BUY {token_side} token  {token_id}")
    print(f"  金额: {amount_usdt:.2f} USDT  (={int(round(amount_usdt*WEI_18))} wei)")
    print(f"  quoteId: {quote.get('quoteId')}")
    for k in ("chance", "averagePrice", "minReceive", "totalFee", "slippageBps"):
        if quote.get(k) is not None:
            print(f"  {k}: {quote[k]}")


def run_once(live=False, amount=DEFAULT_AMOUNT, order_type="LIMIT",
             limit_price=None):
    """单次: 读引擎 → 判信号 → 发现市场 → 校验余额 → 报价 → (确认后)下单."""
    d = _load_engine()
    if not d:
        return 1
    side, reason = _signal(d)
    c = d["candle"]
    p = d["prediction"]
    print(f"[{c.get('iso')} p{c.get('progress_pct', 0):.0f}%] "
          f"{p['bias']}/{p['strength']} conf={p['confidence']} "
          f"px={d['price']['current']} tb={d['factors'].get('taker_buy'):+.2f}")
    print(f"信号: {side or '无'}  ({reason})")
    if not side:
        return 0

    if amount < 1.5:
        print(f"金额 {amount:.2f} USDT < 最低 ~1.5 USDT, 拒绝", file=sys.stderr)
        return 1

    # 余额校验 (get-quote 前先看钱够不够)
    try:
        bal = get_payment_balance()
    except Exception as e:  # noqa: BLE001
        print(f"查询余额失败: {e}", file=sys.stderr)
        return 1
    usable = _usable_balance(bal)
    print("\n=== 余额 (payment-options) ===")
    for acc, it in bal.items():
        print(f"  {acc}: {_parse_amount(it.get('availableBalanceDisplay')):.2f} USDT"
              f"  enabled={it.get('enabled', True)}")
    print(f"  可用合计: {usable:.2f} USDT")
    if usable < amount:
        print(f"余额不足: 可用 {usable:.2f} < 需要 {amount:.2f}, 拒绝", file=sys.stderr)
        return 1

    # 发现当前 OPEN 市场 + token 映射
    try:
        found = find_btc_5m_market()
    except Exception as e:  # noqa: BLE001
        print(f"发现市场失败: {e}", file=sys.stderr)
        return 1
    if not found:
        print("未发现 OPEN 的 btc-updown-5m 市场 (可能已结算/暂停)", file=sys.stderr)
        return 1
    topic_id, market_id, up_tok, down_tok, title, close_time = found
    token_id = up_tok if side == "UP" else down_tok
    print("\n=== 市场 ===")
    print(f"  topic: {title}  (topicId={topic_id})")
    print(f"  marketId={market_id}  closeTime={close_time}")
    print(f"  UP token:   {up_tok}")
    print(f"  DOWN token: {down_tok}")
    print(f"  → 买入 {side}: {token_id}")

    # order-book 双重确认 token 映射 (响应带 outcome 字段, 最可靠)
    # 同时捕获目标 token 的 ask 价, 用于 LIMIT 低挂
    tok_ok = True
    token_ask = None
    for label, tid in (("UP", up_tok), ("DOWN", down_tok)):
        try:
            ob = _order_book(market_id, tid)
            bids = ob.get("bids") or []
            asks = ob.get("asks") or []
            b0 = bids[0].get("price") if bids else None
            a0 = asks[0].get("price") if asks else None
            outcome = ob.get("outcome")
            print(f"  [{label}] token={tid}  outcome={outcome}"
                  f"  top_bid={b0}  top_ask={a0}")
            if label == side and a0:
                token_ask = float(a0)
            # 强制校验: order-book outcome 必须与目标方向一致, 否则拒绝 (防误映射)
            if outcome:
                ol = str(outcome).lower()
                if label == "UP" and not (ol.startswith("up") or ol.startswith("bull") or ol == "y"):
                    tok_ok = False
                if label == "DOWN" and not (ol.startswith("down") or ol.startswith("bear") or ol == "n"):
                    tok_ok = False
        except Exception as e:  # noqa: BLE001
            print(f"  [{label}] order-book 查询失败: {e}", file=sys.stderr)
    if not tok_ok:
        print("order-book outcome 与目标方向不符, 拒绝下单 (token 映射可能错)", file=sys.stderr)
        return 1

    # 市场过期保护: 用 market closeTime (真实) + 引擎 remaining_sec 双校验
    remain = _market_expiry_ok(d, close_time)
    if remain <= 0:
        print(f"市场已收盘 (remaining_sec={remain:.0f}), 拒绝下单", file=sys.stderr)
        return 1
    if remain < CLOSE_MARGIN_SEC:
        print(f"⚠️  距收盘仅 {remain}s (< {CLOSE_MARGIN_SEC}s), 风险高, 请自行判断",
              file=sys.stderr)

    # 报价 (不花钱) — 默认 LIMIT 低挂
    lp = limit_price
    if lp is None and order_type == "LIMIT":
        if token_ask:
            lp = round(token_ask * 0.98, 4)   # 低于当前 ask 2% 接货
        else:
            print("无法获取盘口价, LIMIT 单无 priceLimit, 拒绝", file=sys.stderr)
            return 1
    if order_type == "LIMIT":
        print(f"\n限价单: 买入 {side} token @ {lp} (当前 ask={token_ask})")
    try:
        quote = get_quote(WALLET, token_id, "BUY", amount,
                          order_type=order_type, price_limit=lp)
    except Exception as e:  # noqa: BLE001
        print(f"获取报价失败: {e}", file=sys.stderr)
        return 1
    qid = quote.get("quoteId")
    _print_quote_summary(title, side, token_id, amount, quote)
    if not qid:
        print("get-quote 未返回 quoteId (可能余额不足或市场关闭)", file=sys.stderr)
        return 1

    # 确认闸门 (place-order 前, 即真实花钱前)
    if not _confirm_place(title, side, token_id, amount, quote, live):
        print("已取消下单")
        return 0
    try:
        res = place_order(WALLET, WALLET_ID, qid, amount_usdt=amount,
                          order_type=order_type)
    except Exception as e:  # noqa: BLE001
        print(f"下单失败: {e}", file=sys.stderr)
        return 1
    print("\n=== 下单结果 ===")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res.get("orderId"):
        print(f"成交! orderId={res['orderId']}")
    return 0


def run_loop(live=False, amount=DEFAULT_AMOUNT, rounds=None,
             order_type="LIMIT", limit_price=None):
    """持续监控: 每根K线第2/3/4分钟采样. 每根K线只处理一次."""
    seen = set()
    n = 0
    while rounds is None or n < rounds:
        now = datetime.datetime.now()
        if now.minute % 5 in SAMPLE_MINUTES and now.second >= SAMPLE_SECOND:
            d = _load_engine()
            if d:
                c = d["candle"]
                key = (c["iso"], now.minute // 5)
                if key not in seen:
                    seen.add(key)
                    n += 1
                    run_once(live=live, amount=amount, order_type=order_type,
                             limit_price=limit_price)
            time.sleep(20)
        else:
            time.sleep(10)
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="5minbtc→币安预测交易 桥接 (默认只报价不成交)")
    ap.add_argument("--once", action="store_true", help="单次: 判断+报价+确认+可选下单")
    ap.add_argument("--loop", action="store_true", help="持续监控(每根K线2/3/4分钟)")
    ap.add_argument("--monitor", action="store_true",
                    help="持仓监控: 实时面板 + 止盈止损自动卖出 (需显式 --tp-mult/--sl-mult)")
    ap.add_argument("--live", action="store_true", help="实盘模式(危险! 双确认)")
    ap.add_argument("--amount", type=float, default=DEFAULT_AMOUNT,
                    help=f"下单金额 USDT (默认 {DEFAULT_AMOUNT})")
    ap.add_argument("--rounds", type=int, default=None, help="loop 轮数上限(默认无限)")
    ap.add_argument("--order-type", choices=("LIMIT", "MARKET"), default="LIMIT",
                    help="买入单类型 (默认 LIMIT 低挂)")
    ap.add_argument("--limit-price", type=float, default=None,
                    help="LIMIT 单限价 (token 价格 0~1; 默认 = 当前 ask×0.98)")
    ap.add_argument("--tp-mult", type=float, default=0,
                    help="止盈倍率: 现价/成本 ≥ 此值自动卖出锁利 (如 1.4=+40%%; 0=不启用)")
    ap.add_argument("--sl-mult", type=float, default=0,
                    help="止损倍率: 现价/成本 ≤ 此值自动卖出 (如 0.4=跌60%%; 0=不启用)")
    ap.add_argument("--monitor-interval", type=int, default=10,
                    help="持仓监控轮询间隔秒 (默认 10)")
    ap.add_argument("--monitor-iters", type=int, default=None,
                    help="持仓监控轮数上限 (默认无限)")
    args = ap.parse_args()

    if not os.environ.get("BINANCE_API_KEY") or not os.environ.get("BINANCE_API_SECRET"):
        print("需要 BINANCE_API_KEY/BINANCE_API_SECRET 环境变量", file=sys.stderr)
        return 1

    print("\n⚠️  币安预测交易无 test 模式, 确认下单即真实花钱. 默认只报价不成交。\n")

    # 自动卖出闸门: 止盈/止损都必须显式设定, 否则禁止自动 SELL
    auto_sell = (args.tp_mult > 0 and args.sl_mult > 0)
    if args.monitor and not auto_sell:
        print("⚠️  未显式设定 --tp-mult 和 --sl-mult, 自动卖出未启用。")
        print("    将仅显示实时面板, 不执行止盈/止损卖出。")
        print("    启用自动卖出需: --monitor --tp-mult 1.4 --sl-mult 0.4 --live")
        if not args.live:
            pass  # 非 live 本就不会真实卖出

    if args.live:
        print("\n⚠️⚠️  实盘模式! 将真实下单。\n")
        try:
            confirm = input("确认真实下单? 输入 yes: ").strip().lower()
        except EOFError:
            confirm = ""
        if confirm != "yes":
            print("已取消")
            return 0

    if args.monitor:
        return monitor_positions(tp_mult=args.tp_mult, sl_mult=args.sl_mult,
                                 interval=args.monitor_interval, live=args.live,
                                 max_iters=args.monitor_iters)
    if args.once:
        return run_once(live=args.live, amount=args.amount,
                        order_type=args.order_type, limit_price=args.limit_price)
    if args.loop:
        return run_loop(live=args.live, amount=args.amount, rounds=args.rounds,
                        order_type=args.order_type, limit_price=args.limit_price)

    print("用法: --once 单次 | --loop 持续 | --monitor 持仓监控 | 加 --live 实盘(危险)")
    print("自动卖出止盈止损需: --monitor --tp-mult <x> --sl-mult <x> --live")
    return 0


if __name__ == "__main__":
    sys.exit(main())
