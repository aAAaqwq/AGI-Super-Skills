#!/usr/bin/env python3
"""
A股基金监控脚本
模式:
  estimate - 盘中估值 (10:30 / 12:30 / 14:30)
  nav      - 收盘净值 (22:00 推荐，避免 20:30 太早数据未发布)
"""
import sys
import json
import time
import urllib.request
import re
from datetime import datetime, date

# 基金池: (代码, 简称, 是否QDII)
# QDII 基金净值发布滞后 1 天（追踪海外/跨市场），属于合规设计
FUNDS = [
    ("003304", "前海开源核心资源A", False),
    ("015790", "永赢高端装备C", False),
    ("015508", "兴业中证500增强C", False),
    ("000979", "景顺沪港深精选A", True),    # 港股 QDII
    ("270042", "广发纳斯达克100联接A", True),  # 美股 QDII
    ("519771", "交银优择回报C", False),
    ("014418", "西部利得芯片增强A", False),
    ("012414", "招商白酒LOF C", False),
    ("002943", "广发多因子混合", False),
    ("025209", "永赢先锋半导体C", False),
    ("000217", "华安黄金ETF联接C", True),    # 黄金 QDII
    ("012768", "华夏动漫游戏ETF联接A", False),
    ("025857", "华夏电网设备ETF联接C", False),
    ("026073", "广发研究智选C", False),
]

FIRE_EMOJI = "🔥"
QDII_EMOJI = "🌏"


def fetch_with_retry(url, retries=2, timeout=10):
    """带重试的 HTTP GET（处理晚间 API 拥堵）"""
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Referer": "https://fund.eastmoney.com/",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8")
        except Exception:
            if i < retries:
                time.sleep(2)
                continue
            return None
    return None


def fetch_estimate(code):
    """获取盘中估值 (fundgz.1234567.com.cn)"""
    url = f"http://fundgz.1234567.com.cn/js/{code}.js"
    text = fetch_with_retry(url, retries=2)
    if not text:
        return None
    m = re.search(r'jsonpgz\((.+?)\);', text)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            return None
    return None


def fetch_nav(code):
    """获取最新收盘净值 (eastmoney lsjz API)"""
    url = f"https://api.fund.eastmoney.com/f10/lsjz?callback=&fundCode={code}&pageIndex=1&pageSize=1"
    text = fetch_with_retry(url, retries=2)
    if not text:
        return None
    try:
        data = json.loads(text)
        items = data.get("Data", {}).get("LSJZList", [])
        if items:
            item = items[0]
            return {
                "fundcode": code,
                "name": "",
                "dwjz": item.get("DWJZ", ""),
                "jzrq": item.get("FSRQ", ""),
                "jzzzl": item.get("JZZZL", ""),
            }
    except Exception:
        return None
    return None


def run_estimate():
    """盘中估值模式"""
    now = datetime.now().strftime("%H:%M")
    lines = []
    lines.append(f"📊 A股基金盘中估值 [{now}]")
    lines.append("━━━━━━━━━━━━━━")

    total_change = 0
    count = 0
    updated = 0

    for code, name, _is_qdii in FUNDS:
        data = fetch_estimate(code)
        if data and data.get("gsz"):
            gsz = data["gsz"]
            gszzl = data.get("gszzl", "0.00")
            gztime = data.get("gztime", "")

            try:
                change_pct = float(gszzl)
            except Exception:
                change_pct = 0.0

            total_change += change_pct
            count += 1

            fire = ""
            if abs(change_pct) >= 3.0:
                fire = f" {FIRE_EMOJI}"

            lines.append(f"{name} | 估值 {gsz} | {change_pct:+.2f}%{fire} ({gztime[-5:]})")
            updated += 1
        else:
            lines.append(f"{name} | ⏳ 暂无估值")

    if count > 0:
        avg = total_change / count
        lines.append("━━━━━━━━━━━━━━")
        lines.append(f"📈 平均估值涨跌: {avg:+.2f}% | 已更新: {updated}/{len(FUNDS)}")

    return "\n".join(lines)


def run_nav():
    """收盘净值模式 — 只统计今日已发布的 NAV，未发布基金明确标记"""
    now = datetime.now().strftime("%m-%d %H:%M")
    today = date.today().strftime("%Y-%m-%d")

    lines = []
    lines.append(f"📊 A股基金收盘净值 [{now}]")
    lines.append(f"📅 截止 {today} (北京时间)")
    lines.append("━━━━━━━━━━━━━━")

    total_change = 0
    today_count = 0
    pending_count = 0
    pending_qdii = 0
    pending_normal = 0

    for code, name, is_qdii in FUNDS:
        data = fetch_nav(code)
        if data:
            dwjz = data["dwjz"]
            jzrq = data["jzrq"]  # e.g. "2026-06-22"
            jzzzl = data.get("jzzzl", "")

            change_pct = 0.0
            if jzzzl:
                try:
                    change_pct = float(jzzzl)
                except Exception:
                    pass

            fire = ""
            if abs(change_pct) >= 3.0:
                fire = f" {FIRE_EMOJI}"

            if jzrq == today:
                # ✅ 今日 NAV 已发布
                lines.append(f"{name} | {dwjz} | {change_pct:+.2f}%{fire}")
                total_change += change_pct
                today_count += 1
            else:
                # ⏳ NAV 还没更新到今天
                qdii_mark = f" {QDII_EMOJI}QDII" if is_qdii else ""
                lines.append(f"{name} | ⏳ 待发布{qdii_mark} (上次: {jzrq})")
                pending_count += 1
                if is_qdii:
                    pending_qdii += 1
                else:
                    pending_normal += 1
        else:
            lines.append(f"{name} | ⚠️ 获取失败")
            pending_count += 1
            if is_qdii:
                pending_qdii += 1
            else:
                pending_normal += 1

    if today_count > 0:
        avg = total_change / today_count
        lines.append("━━━━━━━━━━━━━━")
        lines.append(f"📈 平均涨跌: {avg:+.2f}% | ✅ 今日: {today_count}/{len(FUNDS)}")
        if pending_count > 0:
            breakdown = []
            if pending_qdii > 0:
                breakdown.append(f"{QDII_EMOJI}QDII 滞后: {pending_qdii}")
            if pending_normal > 0:
                breakdown.append(f"⏳ 普通延迟: {pending_normal}")
            lines.append(f"⏳ 待发布: {pending_count}/{len(FUNDS)} ({' | '.join(breakdown)})")
    else:
        lines.append("━━━━━━━━━━━━━━")
        lines.append(f"⚠️ 今日暂无 NAV 发布（{pending_count}/{len(FUNDS)} 待发布）")

    lines.append("💰 CFO Buffett · AGI Super Team")
    return "\n".join(lines)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "estimate"

    if mode == "estimate":
        print(run_estimate())
    elif mode == "nav":
        print(run_nav())
    else:
        print(f"Unknown mode: {mode}. Use 'estimate' or 'nav'.")
        sys.exit(1)
