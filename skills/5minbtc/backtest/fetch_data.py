#!/usr/bin/env python3
"""5minbtc Backtest Data Fetcher — 从 Binance 下载历史5分钟K线数据

用法:
  python fetch_data.py              # 下载1年数据(默认)
  python fetch_data.py --days 180   # 下载180天
  python fetch_data.py --force      # 强制重新下载
  python fetch_data.py --status     # 查看缓存状态

数据源: Binance data-api.binance.vision (公开免费)
输出格式: data/btcusdt_5m.json
"""
import json, os, sys, time, urllib.request

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "btcusdt_5m.json")
BINANCE_API = "https://data-api.binance.vision/api/v3/klines"
BATCH_SIZE = 1000
RATE_LIMIT_SEC = 0.05  # 请求间隔 (Binance 公开API限制 1200 req/min)


def fetch_batch(symbol, interval, start_ms, end_ms):
    """获取一批K线数据（最多1000根）"""
    url = (f"{BINANCE_API}?symbol={symbol}&interval={interval}"
           f"&startTime={start_ms}&endTime={end_ms}&limit={BATCH_SIZE}")
    req = urllib.request.Request(url, headers={"User-Agent": "5minbtc-backtest/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def download(days=365, force=False):
    """下载指定期限的5分钟K线数据"""
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - days * 24 * 3600 * 1000

    # 检查缓存
    if not force and os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            cached = json.load(f)
        if cached:
            first_time = cached[0].get("ot", cached[0].get("ct", 0))
            last_time = cached[-1].get("ct", 0)
            cached_days = (last_time - first_time) / (24 * 3600 * 1000)
            age_hours = (now_ms - last_time) / (3600 * 1000)
            print(f"📦 缓存: {len(cached)} 根K线, 覆盖 {cached_days:.0f} 天, "
                  f"数据 {age_hours:.1f} 小时前")
            if age_hours < 24 and cached_days >= days * 0.9:
                print(f"✅ 缓存有效（<24h且覆盖>{days*0.9:.0f}天），跳过下载")
                print(f"   时间范围: {_ms_to_str(first_time)} ~ {_ms_to_str(last_time)}")
                return DATA_FILE
            print("⏳ 缓存过期或不足，重新下载...")

    print(f"🚀 下载 BTCUSDT 5m 数据: 最近 {days} 天")
    print(f"   预计 ~{days * 288:,} 根K线, ~{days * 288 // BATCH_SIZE + 1} 批请求")

    all_raw = []
    cursor = start_ms
    batch_num = 0

    while cursor < now_ms:
        try:
            batch = fetch_batch("BTCUSDT", "5m", cursor, now_ms)
        except Exception as e:
            print(f"❌ 请求失败 (batch {batch_num}): {e}")
            if batch_num > 0:
                print("   保留已下载的数据")
                break
            raise

        if not batch:
            break

        all_raw.extend(batch)
        batch_num += 1

        # 进度报告
        if batch_num % 10 == 0:
            last_ts = batch[-1][0]
            pct = (last_ts - start_ms) / (now_ms - start_ms) * 100
            print(f"   已下载 {len(all_raw):,} 根 ({pct:.0f}%) — "
                  f"batch {batch_num}, {_ms_to_str(last_ts)}")

        # 移动游标到最后一根K线的 close_time + 1
        cursor = batch[-1][6] + 1
        time.sleep(RATE_LIMIT_SEC)

    # 转换格式并去重
    candles = []
    for c in all_raw:
        candles.append({
            "ot": int(c[0]),     # Open time
            "o": float(c[1]),    # Open
            "h": float(c[2]),    # High
            "l": float(c[3]),    # Low
            "c": float(c[4]),    # Close
            "v": float(c[5]),    # Volume
            "ct": int(c[6]),     # Close time
        })

    # 按 open_time 去重
    seen = set()
    unique = []
    for c in candles:
        if c["ot"] not in seen:
            seen.add(c["ot"])
            unique.append(c)
    candles = sorted(unique, key=lambda x: x["ot"])

    # 保存
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w") as f:
        json.dump(candles, f)

    # 统计
    first = candles[0]
    last = candles[-1]
    days_covered = (last["ct"] - first["ot"]) / (24 * 3600 * 1000)
    size_mb = os.path.getsize(DATA_FILE) / 1024 / 1024

    print(f"\n✅ 下载完成!")
    print(f"   总K线数: {len(candles):,}")
    print(f"   时间范围: {_ms_to_str(first['ot'])} ~ {_ms_to_str(last['ct'])}")
    print(f"   覆盖天数: {days_covered:.0f} 天")
    print(f"   文件大小: {size_mb:.1f} MB")
    print(f"   保存路径: {DATA_FILE}")

    return DATA_FILE


def show_status():
    """显示缓存数据状态"""
    if not os.path.exists(DATA_FILE):
        print("❌ 无缓存数据")
        return

    with open(DATA_FILE) as f:
        data = json.load(f)

    if not data:
        print("❌ 缓存为空")
        return

    first = data[0]
    last = data[-1]
    days = (last["ct"] - first["ot"]) / (24 * 3600 * 1000)
    age_h = (time.time() * 1000 - last["ct"]) / (3600 * 1000)
    size_mb = os.path.getsize(DATA_FILE) / 1024 / 1024

    print(f"📊 缓存状态:")
    print(f"   K线数: {len(data):,}")
    print(f"   品种: BTCUSDT 5m")
    print(f"   时间范围: {_ms_to_str(first['ot'])} ~ {_ms_to_str(last['ct'])}")
    print(f"   覆盖天数: {days:.0f} 天")
    print(f"   数据时效: {age_h:.1f} 小时前")
    print(f"   文件大小: {size_mb:.1f} MB")

    # 价格范围
    prices = [c["c"] for c in data]
    print(f"   价格范围: ${min(prices):,.0f} ~ ${max(prices):,.0f}")


def _ms_to_str(ms):
    """毫秒时间戳转可读字符串"""
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ms / 1000))


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--status" in args:
        show_status()
    else:
        days = 365
        for a in args:
            if a.startswith("--days="):
                days = int(a.split("=")[1])
            elif a == "--days" and args.index(a) + 1 < len(args):
                days = int(args[args.index(a) + 1])
        force = "--force" in args
        download(days=days, force=force)
