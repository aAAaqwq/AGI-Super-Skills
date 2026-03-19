#!/usr/bin/env python3
"""
Token Reporter — 每日 Token 消耗 + 产出上报
扫描 OpenClaw JSONL 日志，按模型聚合 token，写入飞书多维表格。

用法:
  python report.py --scan-only          # 只统计不上报
  python report.py --report             # 统计 + 飞书上报
  python report.py --date 2026-03-17   # 指定日期
  python report.py --config /path.json  # 指定配置
"""

import json
import os
import sys
import glob
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict

# ── 模型分类 ──────────────────────────────────────────────────────────────

# 模型匹配规则: key → (显示名, 匹配函数)
MODEL_PATTERNS = {
    "opus4.6": {
        "display": "opus4.6",
        "match": lambda p, m: "claude-opus-4-6" in m or "opus-4-6" in m or "xingsuancode/claude-opus-4-6" in m,
    },
    "sonnet4.6": {
        "display": "sonnet4.6",
        "match": lambda p, m: "claude-sonnet-4-6" in m or "sonnet-4-6" in m or "xingsuancode/claude-sonnet-4-6" in m,
    },
    "glm-5": {
        "display": "glm-5",
        "match": lambda p, m: "glm-5" in m and "glm-5-turbo" not in m,
    },
    "glm-5-turbo": {
        "display": "glm-5-turbo",
        "match": lambda p, m: "glm-5-turbo" in m or "zai/glm-5-turbo" in m,
    },
    "glm-4.7": {
        "display": "glm-4.7",
        "match": lambda p, m: "glm-4.7" in m or "zai/glm-4.7" in m,
    },
    "minimax": {
        "display": "minimax-M2.5",
        "match": lambda p, m: "MiniMax-M2.5" in m or "minimax" in m.lower() or "minimax/M2" in m,
    },
    "kimi": {
        "display": "kimi-k2.5",
        "match": lambda p, m: "kimi" in m.lower() or "moonshot" in m.lower() or "kimi-k2.5" in m,
    },
    "ollama": {
        "display": "ollama-qwen",
        "match": lambda p, m: "ollama" in m.lower() or "qwen" in m.lower(),
    },
    "gemini": {
        "display": "gemini-3-pro",
        "match": lambda p, m: "gemini" in m.lower() and ("3-pro" in m or "3_pro" in m),
    },
    "gemini-3-pro-preview": {
        "display": "gemini-3-pro-preview",
        "match": lambda p, m: "gemini-3-pro-preview" in m or "xingjiabiapi/gemini" in m,
    },
    "gpt5": {
        "display": "gpt-5.2",
        "match": lambda p, m: "gpt-5" in m or "gpt5" in m.lower(),
    },
}

# Agent ID → 显示名称映射
AGENT_NAME_MAP = {
    "main": "小a",
    "code": "小code",
    "ops": "小ops",
    "quant": "小quant",
    "content": "小content",
    "research": "小research",
    "pm": "小pm",
    "data": "小data",
    "market": "小market",
    "finance": "小finance",
    "law": "小law",
    "sales": "小sales",
    "product": "小product",
    "batch": "小batch",
    "xiaoresearch": "小research",
    "xiaotu": "小兔",
    "telegram-agent": "电报",
}


def classify_model(provider: str, model_id: str) -> str:
    """将 provider/model 分类到预定义模型组"""
    for key, info in MODEL_PATTERNS.items():
        if info["match"](provider, model_id):
            return key
    return "other"


def format_tokens(n: int) -> str:
    """格式化 token 数: 123456 → 123K"""
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    elif n >= 1000:
        return f"{n/1000:.0f}K" if n % 1000 < 100 else f"{n/1000:.1f}K"
    return str(n)


def format_cost(c: float) -> str:
    """格式化成本"""
    if c == 0:
        return "$0"
    if c < 0.01:
        return f"${c:.4f}"
    return f"${c:.2f}"


# ── JSONL 扫描 ────────────────────────────────────────────────────────────

OPENCLAW_DIR = os.path.expanduser("~/.openclaw")
AGENTS_DIR = os.path.join(OPENCLAW_DIR, "agents")
MEMORY_DIR = os.path.expanduser("~/clawd/memory")


def scan_jsonl_for_date(target_date: str) -> dict:
    """
    扫描所有 agent 的 JSONL 文件，提取当日 token 使用量。

    Returns:
        {
            "agents": {
                "main": {"model_key": {"input": N, "output": N, ...}, ...},
                "code": {...},
            },
            "models": {
                "model_key": {"input": N, "output": N, ...},
            },
            "total": {"input": N, "output": N, ...},
            "session_count": N,
        }
    """
    # Parse target date
    try:
        dt = datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError:
        print(f"❌ 无效日期格式: {target_date}，使用 YYYY-MM-DD")
        return {}

    # Date range for filtering (UTC)
    day_start = datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    agents_data = defaultdict(lambda: defaultdict(lambda: {
        "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0,
        "totalTokens": 0, "cost_total": 0.0, "message_count": 0,
    }))
    models_data = defaultdict(lambda: {
        "input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0,
        "totalTokens": 0, "cost_total": 0.0, "message_count": 0,
    })

    session_count = 0
    files_scanned = 0
    lines_scanned = 0

    # Iterate agents
    if not os.path.isdir(AGENTS_DIR):
        print(f"❌ Agents 目录不存在: {AGENTS_DIR}")
        return {}

    agent_dirs = [d for d in os.listdir(AGENTS_DIR)
                  if os.path.isdir(os.path.join(AGENTS_DIR, d))
                  and not d.endswith("TEMPLATE")]

    for agent_name in sorted(agent_dirs):
        sessions_dir = os.path.join(AGENTS_DIR, agent_name, "sessions")
        if not os.path.isdir(sessions_dir):
            continue

        jsonl_files = glob.glob(os.path.join(sessions_dir, "*.jsonl"))

        for jf in jsonl_files:
            files_scanned += 1
            # Track current model in this file
            current_provider = ""
            current_model = ""
            file_has_today_data = False

            try:
                with open(jf, "r", encoding="utf-8") as f:
                    for line in f:
                        lines_scanned += 1
                        try:
                            obj = json.loads(line.strip())
                        except json.JSONDecodeError:
                            continue

                        obj_type = obj.get("type", "")

                        # Track model changes
                        if obj_type == "model_change":
                            current_provider = obj.get("provider", "")
                            current_model = obj.get("modelId", "")
                            continue

                        # Skip non-messages
                        if obj_type != "message":
                            continue

                        msg = obj.get("message", {})
                        if msg.get("role") != "assistant":
                            continue

                        # Parse timestamp
                        ts_str = obj.get("timestamp", "")
                        if not ts_str:
                            continue

                        try:
                            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        except ValueError:
                            continue

                        # Filter by date
                        if ts < day_start or ts >= day_end:
                            continue

                        # Check for usage
                        usage = msg.get("usage")
                        if not usage:
                            continue

                        file_has_today_data = True

                        # Classify model
                        model_key = classify_model(current_provider, current_model)

                        # Accumulate
                        fields = ["input", "output", "cacheRead", "cacheWrite", "totalTokens"]
                        for field in fields:
                            val = usage.get(field, 0)
                            agents_data[agent_name][model_key][field] += val
                            models_data[model_key][field] += val

                        cost = usage.get("cost", {})
                        cost_val = cost.get("total", 0)
                        agents_data[agent_name][model_key]["cost_total"] += cost_val
                        models_data[model_key]["cost_total"] += cost_val

                        agents_data[agent_name][model_key]["message_count"] += 1
                        models_data[model_key]["message_count"] += 1

                if file_has_today_data:
                    session_count += 1

            except Exception as e:
                print(f"⚠️ 读取文件失败 {jf}: {e}")

    # Compute totals
    total = {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 0, "cost_total": 0.0}
    for model_key, data in models_data.items():
        for field in ["input", "output", "cacheRead", "cacheWrite", "totalTokens"]:
            total[field] += data[field]
        total["cost_total"] += data["cost_total"]

    return {
        "agents": dict(agents_data),
        "models": dict(models_data),
        "total": total,
        "session_count": session_count,
        "files_scanned": files_scanned,
        "lines_scanned": lines_scanned,
    }


# ── 产出收集 ──────────────────────────────────────────────────────────────

def collect_output(target_date: str) -> str:
    """从 memory 文件收集当日产出摘要"""
    memory_file = os.path.join(MEMORY_DIR, f"{target_date}.md")
    if not os.path.exists(memory_file):
        return "无 memory 记录"

    try:
        with open(memory_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return "读取 memory 失败"

    if not content.strip():
        return "当日 memory 为空"

    # Extract agent work summaries (look for section headers with agent names)
    agent_mentions = defaultdict(list)
    known_agents = [
        "小code", "小ops", "小quant", "小content", "小data",
        "小research", "小market", "小pm", "小finance", "小law",
        "小sales", "小product", "小a",
    ]

    lines = content.split("\n")
    for i, line in enumerate(lines):
        for agent in known_agents:
            if agent in line and any(
                kw in line.lower()
                for kw in ["完成", "发布", "修复", "部署", "输出", "启动", "创建",
                           "推送", "提交", "巡检", "分析", "报告", "同步"]
            ):
                # Take this line and maybe the next one
                snippet = line.strip().lstrip("#•-* ").strip()
                if len(snippet) > 80:
                    snippet = snippet[:80] + "…"
                if snippet and snippet not in agent_mentions[agent]:
                    agent_mentions[agent].append(snippet)

    if not agent_mentions:
        # Fallback: extract all ## sections, take first 3 non-header lines
        sections = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# ") or stripped.startswith("## "):
                continue
            if stripped and len(stripped) > 5:
                clean = stripped.lstrip("-*•# ").strip()
                if clean and len(clean) > 10:
                    sections.append(clean)
        summary = " | ".join(sections[:5])
        return summary if summary else "无具体产出记录"

    # Format
    parts = []
    for agent in sorted(agent_mentions.keys()):
        items = agent_mentions[agent][:3]  # Max 3 items per agent
        parts.append(f"{agent}: {' | '.join(items)}")

    return " | ".join(parts[:5])  # Max 5 agents in summary


# ── 格式化输出 ────────────────────────────────────────────────────────────

def format_token_detail(models_data: dict, total: dict) -> str:
    """格式化所有模型 token 明细"""
    lines = []
    # 按优先级排序显示
    priority_keys = ["opus4.6", "sonnet4.6", "glm-5-turbo", "glm-5", "glm-4.7", "minimax", "kimi", "ollama", "gemini", "gemini-3-pro-preview", "gpt5"]
    
    for key in priority_keys:
        data = models_data.get(key)
        display = MODEL_PATTERNS.get(key, {}).get("display", key)

        if data and data["message_count"] > 0:
            inp = data["input"]
            out = data["output"]
            cache_read = data["cacheRead"]
            cache_write = data["cacheWrite"]
            cost = data["cost_total"]

            total_input = inp + cache_read + cache_write
            cache_pct = (cache_read / total_input * 100) if total_input > 0 else 0

            lines.append(
                f"{display}: input {format_tokens(inp)} / output {format_tokens(out)} "
                f"/ cache {cache_pct:.0f}% / {format_cost(cost)}"
            )

    # Add "other" summary if exists (models not matched)
    other = models_data.get("other")
    if other and other["message_count"] > 0:
        lines.append(
            f"其他: {other['message_count']}次调用, "
            f"input {format_tokens(other['input'])} / output {format_tokens(other['output'])}"
        )

    return "\n".join(lines)


def format_report(data: dict, date: str, output: str) -> str:
    """生成完整报告文本"""
    report = f"📊 Token 日报 — {date}\n"
    report += f"{'='*40}\n\n"

    # Token detail
    report += "## Token 明细\n"
    report += format_token_detail(data["models"], data["total"]) + "\n\n"

    # Total
    t = data["total"]
    report += f"## 总计\n"
    report += f"input: {format_tokens(t['input'])} | output: {format_tokens(t['output'])} | "
    report += f"total: {format_tokens(t['totalTokens'])} | cost: {format_cost(t['cost_total'])}\n\n"

    # Agent breakdown
    report += f"## Agent 用量 Top 5\n"
    agent_totals = []
    for agent_name, models in data["agents"].items():
        agent_total = sum(m["totalTokens"] for m in models.values())
        if agent_total > 0:
            # 使用友好名称
            friendly_name = AGENT_NAME_MAP.get(agent_name, agent_name)
            agent_totals.append((friendly_name, agent_total, agent_name))  # 保留原始ID用于debug
    
    agent_totals.sort(key=lambda x: x[1], reverse=True)

    for friendly_name, tokens, original_id in agent_totals[:5]:
        report += f"  {friendly_name}: {format_tokens(tokens)}\n"
    report += "\n"

    # Output
    report += f"## 产出\n{output}\n\n"

    # Meta
    report += f"## 扫描统计\n"
    report += f"文件: {data.get('files_scanned', 0)} | 行: {data.get('lines_scanned', 0)} | "
    report += f"活跃 session: {data.get('session_count', 0)}\n"

    return report


# ── 飞书上报 ──────────────────────────────────────────────────────────────

def report_to_feishu(token_detail: str, output: str, date: str, config: dict) -> bool:
    """
    写入飞书多维表格。
    注意: 实际飞书写入需要通过 lark-mcp 工具（由 agent 调用），
    这里生成 JSON 供 agent 使用 mcp__lark-mcp_createRecord 调用。
    """
    record = {
        "fields": {
            "员工名称": config.get("person", ""),
            "Token明细": token_detail,
            "产出": output,
            "时间": date,
            "个人总结": "",
            "评分": "",
        }
    }

    # Output the record as JSON for agent consumption
    output_path = os.path.join(os.path.dirname(__file__), f"report_{date}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print(f"📄 飞书记录已生成: {output_path}")
    print(f"\n📋 请使用 lark-mcp 工具写入飞书多维表格:")
    print(f"   App Token: {config.get('bitable_app_token', '未配置')}")
    print(f"   Table ID: {config.get('bitable_table_id', '未配置')}")
    print(f"\n   mcp__lark-mcp_createRecord(")
    print(f"     app_token='{config.get('bitable_app_token')}',")
    print(f"     table_id='{config.get('bitable_table_id')}',")
    print(f"     fields={json.dumps(record['fields'], ensure_ascii=False, indent=6)}")
    print(f"   )")

    return True


# ── 主入口 ────────────────────────────────────────────────────────────────

def load_config(config_path: str) -> dict:
    """加载配置"""
    # Default locations
    default_paths = [
        config_path,
        os.path.join(os.path.dirname(__file__), "..", "config.json"),
    ]

    for p in default_paths:
        if p and os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)

    # Return minimal config
    return {"person": "unknown", "instance": "unknown"}


def main():
    parser = argparse.ArgumentParser(description="Token Reporter — 每日 Token 消耗 + 产出上报")
    parser.add_argument("--scan-only", action="store_true", help="只统计不上报")
    parser.add_argument("--report", action="store_true", help="统计 + 生成飞书记录")
    parser.add_argument("--date", default=None, help="目标日期 (YYYY-MM-DD)")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--json", action="store_true", help="输出原始 JSON 数据")

    args = parser.parse_args()

    # Date
    today = datetime.now().strftime("%Y-%m-%d")
    target_date = args.date or today

    print(f"📊 Token Reporter — {target_date}")
    print("=" * 40)

    # Scan JSONL
    print(f"🔍 扫描 JSONL 日志...")
    data = scan_jsonl_for_date(target_date)

    if not data:
        print("❌ 未找到数据")
        sys.exit(1)

    print(f"✅ 扫描完成: {data['files_scanned']} 文件, {data['lines_scanned']} 行, {data['session_count']} 活跃 session")

    # Collect output
    print(f"📝 收集产出...")
    output = collect_output(target_date)

    # Format report
    token_detail = format_token_detail(data["models"], data["total"])
    report_text = format_report(data, target_date, output)

    print(f"\n{report_text}")

    # JSON output
    if args.json:
        print(f"\n## Raw JSON")
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))

    # Feishu report
    if args.report:
        config = load_config(args.config)
        print(f"\n🚀 生成飞书记录...")
        report_to_feishu(token_detail, output, target_date, config)

    if args.scan_only and not args.report:
        print("\nℹ️ 使用 --report 生成飞书上报记录")


if __name__ == "__main__":
    main()
