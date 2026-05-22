#!/usr/bin/env python3
"""
A股基金监控脚本
模式:
  estimate - 盘中估值 (10:30 / 12:30 / 14:30)
  nav      - 收盘净值 (20:30)
"""
import sys
import json
import urllib.request
import re
from datetime import datetime

# 基金池: (代码, 简称)
FUNDS = [
    ("003304", "前海开源核心资源A"),
    ("015790", "永赢高端装备C"),
    ("015508", "兴业中证500增强C"),
    ("000979", "景顺沪港深精选A"),
    ("270042", "广发纳斯达克100联接A"),
    ("519771", "交银优择回报C"),
    ("014418", "西部利得芯片增强A"),
    ("012414", "招商白酒LOF C"),
    ("002943", "广发多因子混合"),
    ("025209", "永赢先锋半导体C"),
    ("000217", "华安黄金ETF联接C"),
    ("012768", "华夏动漫游戏ETF联接A"),
    ("025857", "华夏电网设备ETF联接C"),
    ("026073", "广发研究智选C"),
]

FIRE_EMOJI = "🔥"

def fetch_estimate(code):
    """获取盘中估值 (fundgz.1234567.com.cn)"""
    url = f"http://fundgz.1234567.com.cn/js/{code}.js"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://fund.eastmoney.com/"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode("utf-8")
        # Parse JSONP: jsonpgz({...});
        m = re.search(r'jsonpgz\((.+?)\);', text)
        if m:
            return json.loads(m.group(1))
    except Exception as e:
        return None
    return None

def fetch_nav(code):
    """获取最新收盘净值 (eastmoney lsjz API)"""
    url = f"https://api.fund.eastmoney.com/f10/lsjz?callback=&fundCode={code}&pageIndex=1&pageSize=1"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://fund.eastmoney.com/"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode("utf-8")
        data = json.loads(text)
        items = data.get("Data", {}).get("LSJZList", [])
        if items:
            item = items[0]
            return {
                "fundcode": code,
                "name": "",  # will use our name
                "dwjz": item.get("DWJZ", ""),
                "jzrq": item.get("FSRQ", ""),
                "jzzzl": item.get("JZZZL", ""),
            }
    except Exception as e:
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

    for code, name in FUNDS:
        data = fetch_estimate(code)
        if data and data.get("gsz"):
            gsz = data["gsz"]
            gszzl = data.get("gszzl", "0.00")
            gztime = data.get("gztime", "")
            dwjz = data.get("dwjz", "")
            
            try:
                change_pct = float(gszzl)
            except:
                change_pct = 0.0
            
            total_change += change_pct
            count += 1
            
            # Mark significant moves
            fire = ""
            if abs(change_pct) >= 3.0:
                fire = f" {FIRE_EMOJI}"
            
            arrow = "🔴" if change_pct < -1.5 else ("🟢" if change_pct > 1.5 else "")
            
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
    """收盘净值模式"""
    now = datetime.now().strftime("%m-%d %H:%M")
    lines = []
    lines.append(f"📊 A股基金收盘净值 [{now}]")
    lines.append("━━━━━━━━━━━━━━")

    total_change = 0
    count = 0

    for code, name in FUNDS:
        data = fetch_nav(code)
        if data:
            dwjz = data["dwjz"]
            jzrq = data["jzrq"]
            jzzzl = data.get("jzzzl", "")
            
            change_pct = 0.0
            if jzzzl:
                try:
                    change_pct = float(jzzzl)
                    total_change += change_pct
                    count += 1
                except:
                    pass

            fire = ""
            if abs(change_pct) >= 3.0:
                fire = f" {FIRE_EMOJI}"

            lines.append(f"{name} | {dwjz} | {change_pct:+.2f}%{fire} ({jzrq})")
        else:
            lines.append(f"{name} | ⏳ 获取失败")

    if count > 0:
        avg = total_change / count
        lines.append("━━━━━━━━━━━━━━")
        lines.append(f"📈 平均涨跌: {avg:+.2f}% | 成功: {count}/{len(FUNDS)}")

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
