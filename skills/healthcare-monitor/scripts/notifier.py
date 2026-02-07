#!/usr/bin/env python3
"""
通知推送模块
支持 Telegram、飞书等渠道
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path


def load_config():
    """加载配置"""
    config_path = Path(__file__).parent.parent / "config" / "settings.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def send_alert(company_name, analysis_result):
    """
    发送融资告警
    
    Args:
        company_name: 公司名称
        analysis_result: 分析结果
    """
    config = load_config()
    
    # 生成告警消息
    message = format_alert_message(company_name, analysis_result)
    
    # Telegram 推送
    if config["notification"]["telegram"]["enabled"]:
        send_telegram(message, config["notification"]["telegram"])
    
    # 飞书推送
    if config["notification"]["feishu"]["enabled"]:
        send_feishu(message, config["notification"]["feishu"])
    
    # 记录日志
    log_alert(company_name, analysis_result, message)


def format_alert_message(company_name, result):
    """格式化告警消息"""
    
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    message = f"""🚨 **融资信号告警**

**企业**: {company_name}
**时间**: {now}
**置信度**: {result['confidence']}%

**AI 分析**:
- 融资轮次: {result.get('round_estimate', '未知')}
- 预估金额: {result.get('amount_estimate', '未知')}
"""
    
    if result.get('investors'):
        message += f"- 投资方: {', '.join(result['investors'])}\n"
    
    message += "\n**信号详情**:\n"
    for signal in result.get('signals', []):
        message += f"• {signal['description']}\n"
    
    message += f"\n📊 数据来源: 天眼查"
    
    return message


def send_telegram(message, config):
    """
    发送 Telegram 消息
    
    使用 OpenClaw message 工具
    """
    chat_id = config.get("chat_id", "8518085684")
    
    # 通过 OpenClaw 发送
    # 这里生成命令，实际执行需要通过 OpenClaw
    
    print(f"📤 发送 Telegram 告警到 {chat_id}")
    print(message)
    
    # 实际实现: 调用 OpenClaw message 工具
    # message action=send channel=telegram target={chat_id} message={message}
    
    return {
        "channel": "telegram",
        "chat_id": chat_id,
        "message": message,
        "status": "pending",
        "instructions": f"使用 OpenClaw message 工具发送到 Telegram {chat_id}"
    }


def send_feishu(message, config):
    """
    发送飞书消息
    
    使用 webhook 或 OpenClaw 飞书集成
    """
    webhook = config.get("webhook")
    
    if not webhook:
        print("⚠️ 飞书 webhook 未配置")
        return None
    
    # 转换为飞书卡片格式
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": "🚨 融资信号告警"
                },
                "template": "red"
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": message
                }
            ]
        }
    }
    
    print(f"📤 发送飞书告警")
    
    return {
        "channel": "feishu",
        "webhook": webhook,
        "card": card,
        "status": "pending"
    }


def log_alert(company_name, result, message):
    """记录告警日志"""
    log_dir = Path(__file__).parent.parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "alerts.log"
    
    log_entry = {
        "time": datetime.now().isoformat(),
        "company": company_name,
        "confidence": result["confidence"],
        "round": result.get("round_estimate"),
        "investors": result.get("investors", [])
    }
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def send_daily_report(date=None):
    """
    发送日报
    
    汇总当天的所有告警
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    
    # 读取当天的变更记录
    changes_dir = Path(__file__).parent.parent / "data" / "changes"
    
    daily_changes = []
    for f in changes_dir.glob(f"{date.replace('-', '')}*.json"):
        with open(f, "r", encoding="utf-8") as file:
            daily_changes.append(json.load(file))
    
    if not daily_changes:
        return None
    
    # 生成日报
    report = f"""📊 **医疗企业融资监控日报**

**日期**: {date}
**发现融资信号**: {len(daily_changes)} 个

---

"""
    
    for i, change in enumerate(daily_changes, 1):
        report += f"""
**{i}. {change['company']}**
- 置信度: {change['analysis']['confidence']}%
- 预估轮次: {change['analysis'].get('round_estimate', '未知')}
- 投资方: {', '.join(change['analysis'].get('investors', ['未知']))}

"""
    
    report += "---\n*由 OpenClaw 医疗监控系统自动生成*"
    
    return report


def send_weekly_report():
    """发送周报"""
    # 类似日报，汇总一周数据
    pass
