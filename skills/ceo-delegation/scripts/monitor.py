#!/usr/bin/env python3
"""
CEO Delegation Monitor - 子代理进度监控脚本
每分钟检查一次子代理状态并生成汇报

用法：
    python3 monitor.py [label_filter]

示例：
    python3 monitor.py              # 监控所有子代理
    python3 monitor.py chapter-20   # 只监控包含 chapter-20 的任务
"""
import sys
import json
import subprocess
from datetime import datetime

def get_sessions(label_filter=None):
    """获取当前活跃的子代理会话"""
    cmd = ["openclaw", "sessions", "list", "--message-limit", "2", "--json"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return []
        sessions = json.loads(result.stdout)
        if label_filter:
            sessions = [s for s in sessions if label_filter in s.get("label", "")]
        return sessions
    except Exception as e:
        print(f"❌ 获取会话失败: {e}")
        return []

def format_report(sessions):
    """格式化进度报告"""
    now = datetime.now().strftime("%H:%M:%S")
    report = [f"📊 **子代理进度报告** ({now})", ""]
    
    if not sessions:
        report.append("暂无活跃的子代理任务")
        return "\n".join(report)
    
    for s in sessions:
        label = s.get("label", "unnamed")
        status = s.get("status", "unknown")
        created = s.get("createdAt", "")
        messages = s.get("messages", [])
        
        status_emoji = "🟢" if status == "running" else "🔵" if status == "completed" else "🟡"
        
        report.append(f"{status_emoji} **{label}**")
        report.append(f"   状态: {status}")
        if messages:
            last_msg = messages[-1].get("content", "")[:100]
            report.append(f"   最新: {last_msg}...")
        report.append("")
    
    return "\n".join(report)

def main():
    label_filter = sys.argv[1] if len(sys.argv) > 1 else None
    sessions = get_sessions(label_filter)
    report = format_report(sessions)
    print(report)

if __name__ == "__main__":
    main()
