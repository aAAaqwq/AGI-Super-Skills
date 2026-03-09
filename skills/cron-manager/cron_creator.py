#!/usr/bin/env python3
"""
Cron Creator - 快速创建定时任务

用法：
    python3 cron_creator.py "每天9点执行xxx脚本"
    python3 cron_creator.py --interactive
"""

import json
import re
import sys
from datetime import datetime, timedelta

# 时间解析规则
TIME_PATTERNS = {
    # 每天
    r"每天\s*(\d{1,2})[点:：](\d{0,2})": lambda m: f"{m.group(2) or '0'} {m.group(1)} * * *",
    r"每天\s*(\d{1,2})\s*点": lambda m: f"0 {m.group(1)} * * *",
    
    # 工作日
    r"工作日\s*(\d{1,2})[点:：](\d{0,2})": lambda m: f"{m.group(2) or '0'} {m.group(1)} * * 1-5",
    r"工作日\s*(\d{1,2})\s*点": lambda m: f"0 {m.group(1)} * * 1-5",
    
    # 周末
    r"周末\s*(\d{1,2})[点:：](\d{0,2})": lambda m: f"{m.group(2) or '0'} {m.group(1)} * * 0,6",
    r"周末\s*(\d{1,2})\s*点": lambda m: f"0 {m.group(1)} * * 0,6",
    
    # 每小时
    r"每小时": lambda m: "0 * * * *",
    r"每(\d+)小时": lambda m: None,  # 需要用 every
    
    # 每分钟
    r"每(\d+)分钟": lambda m: None,  # 需要用 every
    
    # 多次
    r"每天\s*(\d{1,2})[点:：]?\s*[,、和]\s*(\d{1,2})[点:：]?\s*[,、和]\s*(\d{1,2})[点:：]?": 
        lambda m: f"0 {m.group(1)},{m.group(2)},{m.group(3)} * * *",
    r"每天\s*(\d{1,2})[点:：]?\s*[,、和]\s*(\d{1,2})[点:：]?": 
        lambda m: f"0 {m.group(1)},{m.group(2)} * * *",
}

INTERVAL_PATTERNS = {
    r"每(\d+)分钟": lambda m: int(m.group(1)) * 60 * 1000,
    r"每(\d+)小时": lambda m: int(m.group(1)) * 60 * 60 * 1000,
    r"每(\d+)天": lambda m: int(m.group(1)) * 24 * 60 * 60 * 1000,
}


def parse_time(text: str) -> dict:
    """解析时间描述，返回 schedule 配置"""
    
    # 尝试匹配间隔模式
    for pattern, converter in INTERVAL_PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            return {
                "kind": "every",
                "everyMs": converter(match)
            }
    
    # 尝试匹配 cron 模式
    for pattern, converter in TIME_PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            expr = converter(match)
            if expr:
                return {
                    "kind": "cron",
                    "expr": expr,
                    "tz": "Asia/Shanghai"
                }
    
    return None


def create_job_config(
    name: str,
    schedule: dict,
    message: str,
    model: str = "xingjiabiapi/gemini-3-flash-preview",
    timeout: int = 180,
    to: str = "YOUR_TELEGRAM_ID"
) -> dict:
    """创建任务配置"""
    return {
        "name": name,
        "agentId": "telegram-agent",
        "enabled": True,
        "schedule": schedule,
        "sessionTarget": "isolated",
        "payload": {
            "kind": "agentTurn",
            "message": message,
            "model": model,
            "timeoutSeconds": timeout,
            "deliver": True,
            "channel": "telegram",
            "to": to
        }
    }


def main():
    if len(sys.argv) < 2:
        print("用法: python3 cron_creator.py <任务描述>")
        print("示例: python3 cron_creator.py '每天9点执行基金监控'")
        return
    
    description = " ".join(sys.argv[1:])
    
    # 解析时间
    schedule = parse_time(description)
    if not schedule:
        print(f"无法解析时间: {description}")
        print("支持的格式: 每天9点, 工作日14:30, 每3小时, 每30分钟")
        return
    
    print(f"解析结果: {json.dumps(schedule, ensure_ascii=False)}")
    
    # 生成任务配置
    config = create_job_config(
        name=description[:20],
        schedule=schedule,
        message=f"执行任务: {description}"
    )
    
    print(f"\n任务配置:\n{json.dumps(config, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
