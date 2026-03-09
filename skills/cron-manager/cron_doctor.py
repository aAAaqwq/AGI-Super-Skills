#!/usr/bin/env python3
"""
Cron Doctor - 定时任务诊断和修复工具

功能：
1. 列出所有任务及状态
2. 诊断失败任务
3. 提供修复建议
4. 生成健康报告

用法：
    python3 cron_doctor.py              # 完整诊断
    python3 cron_doctor.py --report     # 生成简洁报告
    python3 cron_doctor.py --json       # JSON 输出
"""

import json
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

# 颜色输出
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def color(text: str, c: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{c}{text}{Colors.RESET}"

# 常见错误模式及修复建议
ERROR_PATTERNS = {
    "chat not found": {
        "cause": "Bot 未加入群组，或群组 ID 错误",
        "fix": "检查 bot 是否在群组中，或改用私聊 ID (YOUR_TELEGRAM_ID)",
        "auto_fix": "change_to_private_chat"
    },
    "model not allowed": {
        "cause": "Agent 配置中未允许该模型",
        "fix": "使用 agent 允许的模型，推荐: xingjiabiapi/gemini-3-flash-preview",
        "auto_fix": "change_model"
    },
    "timeout": {
        "cause": "任务执行时间超过限制",
        "fix": "增加 timeoutSeconds 或优化任务脚本",
        "auto_fix": "increase_timeout"
    },
    "ECONNREFUSED": {
        "cause": "网络连接被拒绝",
        "fix": "检查网络或目标服务状态",
        "auto_fix": None
    },
    "rate limit": {
        "cause": "API 调用频率超限",
        "fix": "降低调用频率或更换模型",
        "auto_fix": "change_model"
    }
}

# 推荐模型
RECOMMENDED_MODELS = [
    "xingjiabiapi/gemini-3-flash-preview",
    "xingjiabiapi/gemini-2.5-flash",
    "anapi/claude-opus-4-5-20250514",
    "moonshot/kimi-k2.5",
]

OWNER_CHAT_ID = "YOUR_TELEGRAM_ID"


def diagnose_job(job: dict) -> dict:
    """诊断单个任务"""
    issues = []
    warnings = []
    
    job_id = job.get("id", "unknown")
    name = job.get("name", "未命名")
    enabled = job.get("enabled", False)
    state = job.get("state", {})
    payload = job.get("payload", {})
    
    # 1. 检查是否启用
    if not enabled:
        issues.append({
            "type": "disabled",
            "message": "任务未启用",
            "fix": "设置 enabled: true",
            "auto_fix": "enable"
        })
    
    # 2. 检查最近执行状态
    last_status = state.get("lastStatus")
    last_error = state.get("lastError", "")
    
    if last_status == "error":
        error_info = None
        for pattern, info in ERROR_PATTERNS.items():
            if pattern.lower() in last_error.lower():
                error_info = info
                break
        
        issues.append({
            "type": "execution_error",
            "message": f"最近执行失败: {last_error[:80]}...",
            "cause": error_info["cause"] if error_info else "未知原因",
            "fix": error_info["fix"] if error_info else "检查日志详情",
            "auto_fix": error_info.get("auto_fix") if error_info else None
        })
    
    # 3. 检查是否从未执行
    if not state:
        warnings.append({
            "type": "never_run",
            "message": "任务从未执行过",
            "fix": "检查 schedule 配置是否正确，或手动触发测试"
        })
    
    # 4. 检查模型配置
    model = payload.get("model", "")
    if not model:
        warnings.append({
            "type": "no_model",
            "message": "未指定模型",
            "fix": "建议明确指定模型: xingjiabiapi/gemini-3-flash-preview"
        })
    
    # 5. 检查超时配置
    timeout = payload.get("timeoutSeconds", 0)
    if timeout and timeout < 60:
        warnings.append({
            "type": "short_timeout",
            "message": f"超时时间较短 ({timeout}s)",
            "fix": "建议设置至少 120s"
        })
    
    # 6. 检查推送目标
    to = payload.get("to", "")
    if to and to.startswith("-100"):
        if "chat not found" in last_error.lower():
            issues.append({
                "type": "invalid_chat",
                "message": f"群组 {to} 不可达",
                "fix": f"改用私聊 ID: {OWNER_CHAT_ID}",
                "auto_fix": "change_to_private_chat"
            })
    
    return {
        "id": job_id,
        "name": name,
        "enabled": enabled,
        "last_status": last_status,
        "last_error": last_error[:100] if last_error else None,
        "issues": issues,
        "warnings": warnings,
        "healthy": len(issues) == 0 and enabled
    }


def generate_report(jobs: list) -> str:
    """生成健康报告"""
    total = len(jobs)
    healthy = 0
    with_issues = 0
    disabled = 0
    
    lines = ["📊 Cron 任务健康报告", f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    
    for job in jobs:
        diag = diagnose_job(job)
        
        if not job.get("enabled", False):
            disabled += 1
            status = "⏸️"
        elif diag["healthy"]:
            healthy += 1
            status = "✅"
        else:
            with_issues += 1
            status = "❌"
        
        lines.append(f"{status} {diag['name']}")
        
        if diag["issues"]:
            for issue in diag["issues"]:
                lines.append(f"   └─ {issue['message'][:60]}")
    
    lines.insert(3, f"总计: {total} | ✅ 正常: {healthy} | ❌ 异常: {with_issues} | ⏸️ 禁用: {disabled}")
    lines.insert(4, "━" * 40)
    
    return "\n".join(lines)


def generate_fix_commands(jobs: list) -> list:
    """生成修复命令"""
    commands = []
    
    for job in jobs:
        diag = diagnose_job(job)
        job_id = job.get("id")
        
        for issue in diag["issues"]:
            auto_fix = issue.get("auto_fix")
            if not auto_fix:
                continue
            
            if auto_fix == "enable":
                commands.append({
                    "job": diag["name"],
                    "action": "启用任务",
                    "patch": {"enabled": True}
                })
            elif auto_fix == "change_to_private_chat":
                payload = job.get("payload", {}).copy()
                payload["to"] = OWNER_CHAT_ID
                commands.append({
                    "job": diag["name"],
                    "action": "改用私聊推送",
                    "patch": {"payload": payload}
                })
            elif auto_fix == "change_model":
                payload = job.get("payload", {}).copy()
                payload["model"] = RECOMMENDED_MODELS[0]
                commands.append({
                    "job": diag["name"],
                    "action": "更换模型",
                    "patch": {"payload": payload}
                })
            elif auto_fix == "increase_timeout":
                payload = job.get("payload", {}).copy()
                current = payload.get("timeoutSeconds", 120)
                payload["timeoutSeconds"] = max(current * 2, 300)
                commands.append({
                    "job": diag["name"],
                    "action": "增加超时时间",
                    "patch": {"payload": payload}
                })
    
    return commands


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Cron 任务诊断工具")
    parser.add_argument("--report", action="store_true", help="生成简洁报告")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--fixes", action="store_true", help="生成修复建议")
    parser.add_argument("jobs_json", nargs="?", help="任务列表 JSON (stdin if -)")
    args = parser.parse_args()
    
    # 从 stdin 或参数读取任务列表
    if args.jobs_json == "-" or not sys.stdin.isatty():
        jobs_data = sys.stdin.read()
    elif args.jobs_json:
        jobs_data = args.jobs_json
    else:
        print("用法: 通过 stdin 传入任务 JSON，或使用 --help 查看帮助")
        print("示例: openclaw cron list --json | python3 cron_doctor.py --report")
        return
    
    try:
        data = json.loads(jobs_data)
        jobs = data.get("jobs", data) if isinstance(data, dict) else data
    except json.JSONDecodeError as e:
        print(f"JSON 解析错误: {e}")
        return
    
    if not jobs:
        print("未找到任何 cron 任务")
        return
    
    # 生成报告模式
    if args.report:
        print(generate_report(jobs))
        return
    
    # 生成修复建议
    if args.fixes:
        fixes = generate_fix_commands(jobs)
        print(json.dumps(fixes, indent=2, ensure_ascii=False))
        return
    
    # 完整诊断
    results = []
    for job in jobs:
        diag = diagnose_job(job)
        results.append(diag)
        
        if args.json:
            continue
        
        status_icon = "✅" if diag["healthy"] else "❌"
        if not job.get("enabled", False):
            status_icon = "⏸️"
        
        print(f"\n{status_icon} {color(diag['name'], Colors.BLUE)} ({diag['id'][:8]}...)")
        
        if diag["issues"]:
            for issue in diag["issues"]:
                print(f"  {color('问题:', Colors.RED)} {issue['message']}")
                if issue.get("cause"):
                    print(f"  {color('原因:', Colors.YELLOW)} {issue['cause']}")
                print(f"  {color('修复:', Colors.GREEN)} {issue['fix']}")
        
        if diag["warnings"]:
            for warning in diag["warnings"]:
                print(f"  {color('警告:', Colors.YELLOW)} {warning['message']}")
    
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
        return
    
    # 总结
    healthy = sum(1 for r in results if r["healthy"])
    print(f"\n{'━' * 40}")
    print(f"总计: {len(results)} 任务 | ✅ 正常: {healthy} | ❌ 异常: {len(results) - healthy}")


if __name__ == "__main__":
    main()
