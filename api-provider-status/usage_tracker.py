#!/usr/bin/env python3
"""API 用量和费用追踪器 - 从 OpenClaw 会话日志中统计实际用量"""

import json
import os
import glob
from datetime import datetime, timedelta
from pathlib import Path

# OpenClaw 会话日志目录
OPENCLAW_DIR = Path.home() / ".openclaw"
AGENTS_DIR = OPENCLAW_DIR / "agents"

# 价格配置 (每 1M tokens)
PRICING = {
    # Anthropic
    "claude-opus-4-5-20250514": {"input": 15.0, "output": 75.0, "currency": "USD"},
    "claude-sonnet-4-5-20250514": {"input": 3.0, "output": 15.0, "currency": "USD"},
    # ZAI
    "glm-4.7": {"input": 0.5, "output": 0.5, "currency": "CNY"},
    # OpenRouter
    "gpt-5.2": {"input": 2.0, "output": 8.0, "currency": "USD"},
    "gpt-5.2-codex": {"input": 2.0, "output": 8.0, "currency": "USD"},
    "gpt-5.1-codex-mini": {"input": 1.0, "output": 4.0, "currency": "USD"},
    # Gemini
    "gemini-3-pro-preview": {"input": 1.25, "output": 5.0, "currency": "USD"},
    "gemini-3-flash-preview": {"input": 0.075, "output": 0.3, "currency": "USD"},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.3, "currency": "USD"},
    # GitHub Copilot (免费)
    "github-copilot": {"input": 0, "output": 0, "currency": "USD"},
}

def get_all_session_files():
    """获取所有 agent 的会话日志文件"""
    files = []
    for agent_dir in AGENTS_DIR.iterdir():
        if agent_dir.is_dir():
            sessions_dir = agent_dir / "sessions"
            if sessions_dir.exists():
                files.extend(sessions_dir.glob("*.jsonl"))
    return files

def parse_session_file(file_path, since_timestamp=None):
    """解析单个会话文件，提取用量信息"""
    usage_records = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    
                    # 只处理 message 类型
                    if entry.get("type") != "message":
                        continue
                    
                    msg = entry.get("message", {})
                    
                    # 只处理 assistant 消息（有 usage 信息）
                    if msg.get("role") != "assistant":
                        continue
                    
                    usage = msg.get("usage", {})
                    if not usage or usage.get("totalTokens", 0) == 0:
                        continue
                    
                    # 检查时间戳
                    timestamp_str = entry.get("timestamp")
                    if timestamp_str:
                        try:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            if since_timestamp and timestamp < since_timestamp:
                                continue
                        except:
                            pass
                    
                    provider = msg.get("provider", "unknown")
                    model = msg.get("model", "unknown")
                    
                    # 跳过内部 mirror
                    if provider == "openclaw" or model == "delivery-mirror":
                        continue
                    
                    usage_records.append({
                        "provider": provider,
                        "model": model,
                        "tokens_in": usage.get("input", 0),
                        "tokens_out": usage.get("output", 0),
                        "cache_read": usage.get("cacheRead", 0),
                        "cache_write": usage.get("cacheWrite", 0),
                        "timestamp": timestamp_str
                    })
                    
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    
    return usage_records

def get_usage_since(hours=12):
    """获取最近 N 小时的用量统计"""
    since = datetime.now().astimezone() - timedelta(hours=hours)
    
    all_records = []
    for file_path in get_all_session_files():
        # 只处理最近修改的文件
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime).astimezone()
        if mtime < since:
            continue
        
        records = parse_session_file(file_path, since)
        all_records.extend(records)
    
    # 按 provider/model 聚合
    stats = {}
    for record in all_records:
        provider = record["provider"]
        model = record["model"]
        key = f"{provider}/{model}"
        
        if key not in stats:
            stats[key] = {
                "provider": provider,
                "model": model,
                "requests": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "cache_read": 0,
                "cache_write": 0,
            }
        
        stats[key]["requests"] += 1
        stats[key]["tokens_in"] += record["tokens_in"]
        stats[key]["tokens_out"] += record["tokens_out"]
        stats[key]["cache_read"] += record["cache_read"]
        stats[key]["cache_write"] += record["cache_write"]
    
    # 计算费用
    for key, data in stats.items():
        model = data["model"]
        if model in PRICING:
            price = PRICING[model]
            cost = (data["tokens_in"] / 1_000_000 * price["input"] + 
                    data["tokens_out"] / 1_000_000 * price["output"])
            data["cost"] = cost
            data["currency"] = price["currency"]
        else:
            data["cost"] = 0
            data["currency"] = "USD"
    
    return {
        "period_hours": hours,
        "since": since.isoformat(),
        "stats": stats,
        "total": {
            "requests": sum(s["requests"] for s in stats.values()),
            "tokens_in": sum(s["tokens_in"] for s in stats.values()),
            "tokens_out": sum(s["tokens_out"] for s in stats.values()),
        }
    }

def format_usage_report(hours=12) -> str:
    """生成用量报告"""
    data = get_usage_since(hours)
    
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        f"📊 API 用量统计 | 最近 {hours} 小时",
        f"⏰ 截至: {now}",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    
    if not data["stats"]:
        lines.append("📭 暂无 API 调用记录")
    else:
        total_cost_usd = 0
        total_cost_cny = 0
        
        # 按请求数排序
        sorted_stats = sorted(data["stats"].items(), key=lambda x: x[1]["requests"], reverse=True)
        
        for key, info in sorted_stats:
            requests = info["requests"]
            tokens_in = info["tokens_in"]
            tokens_out = info["tokens_out"]
            cost = info.get("cost", 0)
            currency = info.get("currency", "USD")
            
            # 格式化 tokens
            in_k = tokens_in / 1000
            out_k = tokens_out / 1000
            
            cost_str = ""
            if cost > 0:
                if currency == "USD":
                    cost_str = f" ~${cost:.3f}"
                    total_cost_usd += cost
                else:
                    cost_str = f" ~¥{cost:.3f}"
                    total_cost_cny += cost
            
            lines.append(f"• {key}")
            lines.append(f"  {requests}次 | {in_k:.1f}k↓ {out_k:.1f}k↑{cost_str}")
        
        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━",
            f"📈 合计: {data['total']['requests']} 次请求",
            f"🔢 Tokens: {data['total']['tokens_in']//1000}k↓ / {data['total']['tokens_out']//1000}k↑",
        ])
        
        if total_cost_usd > 0:
            lines.append(f"💵 USD: ~${total_cost_usd:.3f}")
        if total_cost_cny > 0:
            lines.append(f"💴 CNY: ~¥{total_cost_cny:.3f}")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    
    return "\n".join(lines)


def get_daily_summary(date_str=None):
    """获取某天的用量（兼容旧接口）"""
    if date_str is None:
        return get_usage_since(24)
    # 对于历史日期，暂时返回空
    return {"date": date_str, "stats": {}, "total": {"requests": 0, "tokens_in": 0, "tokens_out": 0}}


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("""
API 用量追踪器 (v2 - 从 OpenClaw 日志读取)

用法:
  python usage_tracker.py report [hours]     # 生成报告 (默认 12 小时)
  python usage_tracker.py stats [hours]      # JSON 格式统计
  python usage_tracker.py today              # 今日统计 (24h)
""")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "report":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 12
        print(format_usage_report(hours))
    elif cmd == "stats":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 12
        print(json.dumps(get_usage_since(hours), indent=2, ensure_ascii=False, default=str))
    elif cmd == "today":
        print(json.dumps(get_usage_since(24), indent=2, ensure_ascii=False, default=str))
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
