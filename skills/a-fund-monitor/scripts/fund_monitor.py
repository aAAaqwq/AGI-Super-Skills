#!/usr/bin/env python3
"""
A股基金监控脚本（v3 · 2026-07-21）

⚠️ 历史：
- v1: 东方财富 fundgz.1234567.com.cn 盘中估值 API（2026-07 下线）
- v2: 统一走 NAV（盘中无估值）
- v3: 发现天天基金新接口 FundValuationLast（2026-07-21 发现于 leek-fund #677）

数据源（v3 双源混合）：
- 主（估值）：fundcomapi.tiantianfunds.com/mm/newCore/FundValuationLast
- 主（NAV）：api.fund.eastmoney.com/f10/lsjz
- 备：danjuanfunds.com/djapi/fund/growth

显示逻辑：
- 盘中（09:30-15:00 北京工作日）：优先显示估值；无估值的显示上一交易日 NAV
- 收盘后 / 非交易日：显示最新 NAV
"""
import sys
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")

FUNDS = [
    ("003304", "前海开源核心资源A", False),
    ("015790", "永赢高端装备C", False),
    ("015508", "兴业中证500增强C", False),
    ("000979", "景顺沪港深精选A", True),
    ("270042", "广发纳斯达克100联接A", True),
    ("519771", "交银优择回报C", False),
    ("014418", "西部利得芯片增强A", False),
    ("012414", "招商白酒LOF C", False),
    ("002943", "广发多因子混合", False),
    ("025209", "永赢先锋半导体C", False),
    ("000217", "华安黄金ETF联接C", True),
    ("012768", "华夏动漫游戏ETF联接A", False),
    ("025857", "华夏电网设备ETF联接C", False),
    ("026073", "广发研究智选C", False),
]

FIRE_EMOJI = "🔥"
QDII_EMOJI = "🌏"
EST_EMOJI = "📊"  # 估值标记


def fetch_with_retry(url, retries=2, timeout=10, headers=None):
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Referer": "https://h5.1234567.com.cn/",
    }
    if headers:
        default_headers.update(headers)
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=default_headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception:
            if i < retries:
                time.sleep(2)
                continue
            return None
    return None


def fetch_valuations(codes):
    """批量拉估值（一次请求所有基金）"""
    codes_str = ",".join(codes)
    url = (
        "https://fundcomapi.tiantianfunds.com/mm/newCore/FundValuationLast?"
        + urllib.parse.urlencode({
            "FCODES": codes_str,
            "FIELDS": "FCODE,SHORTNAME,GSZZL,GSZ,GSZTIME,FSRQ,DWJZ",
        })
    )
    text = fetch_with_retry(url, retries=2, timeout=10)
    if not text:
        return {}
    try:
        data = json.loads(text)
        result = {}
        for item in (data.get("data") or []):
            code = item.get("FCODE")
            if code:
                result[code] = item
        return result
    except Exception:
        return {}


def fetch_nav_eastmoney(code):
    url = f"https://api.fund.eastmoney.com/f10/lsjz?callback=&fundCode={code}&pageIndex=1&pageSize=3"
    text = fetch_with_retry(url, retries=2,
                           headers={"Referer": "https://fund.eastmoney.com/"})
    if not text:
        return None
    try:
        data = json.loads(text)
        items = data.get("Data", {}).get("LSJZList", [])
        if items:
            return items[0]
    except Exception:
        pass
    return None


def fetch_nav_danjuan(code):
    url = f"https://danjuanfunds.com/djapi/fund/growth/{{{{{code}}}}}"
    text = fetch_with_retry(url, retries=1, timeout=8)
    if not text:
        return None
    try:
        data = json.loads(text)
        records = data.get("data", {}).get("fund_nav_growth", [])
        if records:
            last = records[-1]
            return {
                "FSRQ": last.get("date", ""),
                "DWJZ": last.get("nav", ""),
                "JZZZL": last.get("percentage", "0"),
            }
    except Exception:
        return None
    return None


def fetch_nav(code):
    item = fetch_nav_eastmoney(code)
    if item and item.get("DWJZ"):
        return item
    return fetch_nav_danjuan(code)


def is_weekday_beijing():
    return datetime.now(BEIJING_TZ).weekday() < 5


def is_intraday_beijing():
    """北京时间盘中（工作日 09:30-15:00）"""
    now = datetime.now(BEIJING_TZ)
    if now.weekday() >= 5:
        return False
    # 09:30-15:00
    minutes = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= minutes <= 15 * 60


def get_recent_trading_day(today):
    d = today
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def run_report():
    now_dt = datetime.now(BEIJING_TZ)
    now_str = now_dt.strftime("%m-%d %H:%M")
    today = now_dt.date()
    today_str = today.strftime("%Y-%m-%d")
    bj_hour = now_dt.hour

    intraday = is_intraday_beijing()

    # 拉估值（批量一次）
    codes = [f[0] for f in FUNDS]
    valuations = fetch_valuations(codes) if intraday else {}

    # Header
    lines = []
    if intraday:
        lines.append(f"📊 A股基金盘中实时估值 [{now_str} 北京]")
        lines.append("⏰ 交易时段 · 数据来自天天基金 FundValuationLast")
    else:
        # 收盘后或非交易日
        d = get_recent_trading_day(today)
        expected_nav_date = d.strftime("%Y-%m-%d")
        if bj_hour >= 19:
            lines.append(f"📊 A股基金收盘净值 [{now_str} 北京]")
            lines.append(f"📅 截止 {today_str} (北京时间)")
        else:
            lines.append(f"📊 A股基金最新净值 [{now_str} 北京]")
            lines.append(f"⏰ 非交易时段 · 最新可得 NAV: {expected_nav_date}")
    lines.append("━━━━━━━━━━━━━━")

    total_change = 0.0
    valid_count = 0
    has_estimate = 0
    has_nav = 0
    failed = 0
    pending = 0

    for code, name, is_qdii in FUNDS:
        v = valuations.get(code, {})
        gsz = v.get("GSZ")
        gszzl = v.get("GSZZL")
        gszt = v.get("GSZTIME")

        # 优先用估值（仅盘中）
        if intraday and gsz and gszzl is not None:
            try:
                pct = float(gszzl)
            except Exception:
                pct = 0.0
            fire = f" {FIRE_EMOJI}" if abs(pct) >= 3.0 else ""
            tag = f"{EST_EMOJI}估值"
            lines.append(f"{name} | {gsz} | {pct:+.2f}%{fire} ({tag})")
            total_change += pct
            valid_count += 1
            has_estimate += 1
            continue

        # 拉 NAV
        nav = fetch_nav(code)
        if not nav:
            lines.append(f"{name} | ⚠️ 获取失败")
            failed += 1
            pending += 1
            continue

        dwjz = nav.get("DWJZ", "")
        jzrq = nav.get("FSRQ", "")
        jzzzl = nav.get("JZZZL", "")
        try:
            pct = float(jzzzl) if jzzzl else 0.0
        except Exception:
            pct = 0.0

        fire = f" {FIRE_EMOJI}" if abs(pct) >= 3.0 else ""

        # 判断数据日期
        if intraday:
            # 盘中显示上一交易日 NAV，标注日期
            qdii_mark = f" {QDII_EMOJI}QDII" if is_qdii else ""
            lines.append(f"{name} | {dwjz} | {pct:+.2f}%{fire} (NAV {jzrq[5:]}{qdii_mark})")
            total_change += pct
            valid_count += 1
            has_nav += 1
        else:
            # 收盘后/非交易日：用 expected date 判断
            d = get_recent_trading_day(today)
            expected = today_str if bj_hour >= 19 else d.strftime("%Y-%m-%d")
            if jzrq == expected:
                lines.append(f"{name} | {dwjz} | {pct:+.2f}%{fire}")
                total_change += pct
                valid_count += 1
                has_nav += 1
            else:
                qdii_mark = f" {QDII_EMOJI}QDII" if is_qdii else ""
                lines.append(f"{name} | ⏳ 待发布{qdii_mark} (上次: {jzrq})")
                pending += 1

    # Summary
    lines.append("━━━━━━━━━━━━━━")
    if valid_count > 0:
        avg = total_change / valid_count
        breakdown = []
        if has_estimate > 0:
            breakdown.append(f"{EST_EMOJI}估值: {has_estimate}")
        if has_nav > 0:
            breakdown.append(f"NAV: {has_nav}")
        lines.append(f"📈 平均涨跌: {avg:+.2f}% | ✅ {valid_count}/{len(FUNDS)} ({' | '.join(breakdown)})")
        if pending > 0:
            lines.append(f"⏳ 待发布: {pending}/{len(FUNDS)}")
    else:
        lines.append(f"⚠️ 暂无数据（{pending}/{len(FUNDS)} 待发布）")

    lines.append("💰 CFO Buffett · AGI Super Team")
    return "\n".join(lines)


if __name__ == "__main__":
    if not is_weekday_beijing():
        bj_now = datetime.now(BEIJING_TZ).strftime("%A %H:%M")
        print(f"⏭️ 周末跳过（北京当前: {bj_now}）")
        sys.exit(0)
    print(run_report())
