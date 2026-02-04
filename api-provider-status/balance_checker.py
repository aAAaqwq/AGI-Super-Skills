#!/usr/bin/env python3
"""API 供应商余额查询器

支持的供应商及查询方式：
- anapi: https://anapi.9w7.cn/api/apikeys/query?key=<key>
- openrouter-vip: 待添加
- xingjiabiapi: 待添加
- zai: 待添加
"""

import json
import os
import subprocess
from pathlib import Path
from datetime import datetime

# 配置文件路径
AUTH_PROFILES = Path.home() / ".openclaw/agents/telegram-agent/agent/auth-profiles.json"

# 供应商查询配置
PROVIDERS = {
    "anapi": {
        "name": "Anapi (Claude)",
        "query_url": "https://anapi.9w7.cn/api/apikeys/query?key={key}",
        "method": "api",
    },
    "github-copilot": {
        "name": "GitHub Copilot Pro",
        "query_url": "https://github.com/settings/copilot",
        "method": "playwright",
        "user_data_dir": "~/.playwright-data/github",
    },
    "openrouter-vip": {
        "name": "OpenRouter VIP",
        "query_url": None,
        "method": "skip",  # 暂不查询
    },
    "xingjiabiapi": {
        "name": "性价比 API",
        "query_url": "https://xingjiabiapi.com/console",
        "method": "playwright",
        "user_data_dir": "~/.playwright-data/xingjiabiapi",
    },
    "zai": {
        "name": "ZAI (智谱)",
        "query_url": None,
        "method": "skip",  # 暂不查询
    },
}


def load_auth_profiles():
    """加载认证配置"""
    if AUTH_PROFILES.exists():
        return json.loads(AUTH_PROFILES.read_text())
    return {"profiles": {}}


def query_github_copilot() -> dict:
    """查询 GitHub Copilot Pro 用量"""
    import re
    import time
    
    user_data_dir = os.path.expanduser('~/.playwright-data/github')
    
    if not os.path.exists(user_data_dir):
        return {"success": False, "provider": "github-copilot", "error": "未登录，请先运行登录流程"}
    
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=True,
                timeout=60000
            )
            
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(30000)
            
            page.goto('https://github.com/settings/copilot', wait_until='domcontentloaded')
            time.sleep(3)
            
            text = page.inner_text('body')
            context.close()
            
            if not text:
                return {"success": False, "provider": "github-copilot", "error": "页面内容为空"}
            
            # 解析数据
            # Premium requests 5.0%
            usage_match = re.search(r'Premium requests\s*([\d.]+)%', text)
            is_active = 'Copilot Pro is active' in text or 'active Copilot Pro' in text
            
            return {
                "success": True,
                "provider": "github-copilot",
                "status": "Active" if is_active else "Inactive",
                "plan": "Copilot Pro (学生认证)",
                "premium_usage_pct": float(usage_match.group(1)) if usage_match else 0,
            }
    except ImportError:
        return {"success": False, "provider": "github-copilot", "error": "Playwright 未安装"}
    except Exception as e:
        return {"success": False, "provider": "github-copilot", "error": str(e)}


def query_xingjiabiapi() -> dict:
    """查询星价比 API 余额（需要已登录的 Playwright session）"""
    import re
    import time
    
    user_data_dir = os.path.expanduser('~/.playwright-data/xingjiabiapi')
    
    if not os.path.exists(user_data_dir):
        return {"success": False, "provider": "xingjiabiapi", "error": "未登录，请先运行登录流程"}
    
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir,
                headless=True,
                timeout=30000
            )
            
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(20000)
            
            page.goto('https://xingjiabiapi.com/console', wait_until='networkidle')
            time.sleep(2)  # 等待 JS 渲染
            
            # 获取页面文本
            text = page.locator('body').text_content()
            context.close()
            
            if not text:
                return {"success": False, "provider": "xingjiabiapi", "error": "页面内容为空"}
            
            # 解析数据
            # 当前余额💰43.08历史消耗💰62.56
            balance_match = re.search(r'当前余额💰([\d.]+)', text)
            consumed_match = re.search(r'历史消耗💰([\d.]+)', text)
            requests_match = re.search(r'请求次数(\d+)', text)
            tokens_match = re.search(r'总Tokens(\d+)', text)
            
            return {
                "success": True,
                "provider": "xingjiabiapi",
                "balance": float(balance_match.group(1)) if balance_match else 0,
                "consumed": float(consumed_match.group(1)) if consumed_match else 0,
                "requests": int(requests_match.group(1)) if requests_match else 0,
                "tokens": int(tokens_match.group(1)) if tokens_match else 0,
            }
    except ImportError:
        return {"success": False, "provider": "xingjiabiapi", "error": "Playwright 未安装"}
    except Exception as e:
        return {"success": False, "provider": "xingjiabiapi", "error": str(e)}


def query_anapi(key: str) -> dict:
    """查询 anapi 余额"""
    import urllib.request
    import urllib.error
    
    url = f"https://anapi.9w7.cn/api/apikeys/query?key={key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return {
                "success": True,
                "provider": "anapi",
                "status": data.get("status_display", data.get("status")),
                "plan": data.get("plan_display", data.get("plan_type")),
                "expires_at": data.get("expires_at"),
                "daily_limit": data.get("global_daily_limit", 0),
                "daily_used": data.get("daily_success_count", 0),
                "total_success": data.get("success_count", 0),
                "total_fail": data.get("fail_count", 0),
                "success_rate": data.get("success_rate", 0),
                "total_hours": data.get("total_hours"),
                "used_hours": data.get("used_hours"),
                "raw": data,
            }
    except Exception as e:
        return {"success": False, "provider": "anapi", "error": str(e)}


def query_provider(provider: str) -> dict:
    """查询指定供应商的余额"""
    config = PROVIDERS.get(provider)
    if not config:
        return {"success": False, "provider": provider, "error": "不支持的供应商"}
    
    # GitHub Copilot 不需要 key
    if config["method"] == "playwright" and provider == "github-copilot":
        return query_github_copilot()
    
    # 性价比也不需要 key（用 session）
    if config["method"] == "playwright" and provider == "xingjiabiapi":
        return query_xingjiabiapi()
    
    # 跳过的供应商
    if config["method"] == "skip":
        return {"success": False, "provider": provider, "error": "暂不查询"}
    
    # 需要 key 的供应商
    auth = load_auth_profiles()
    profiles = auth.get("profiles", {})
    
    key = None
    for profile_id, profile in profiles.items():
        if profile.get("provider") == provider:
            key = profile.get("key")
            break
    
    if not key:
        return {"success": False, "provider": provider, "error": "未找到 API key"}
    
    if config["method"] == "api" and provider == "anapi":
        return query_anapi(key)
    
    return {
        "success": False,
        "provider": provider,
        "error": "需要手动查询",
        "method": config["method"],
    }


def query_all() -> dict:
    """查询所有供应商"""
    results = {}
    for provider in PROVIDERS:
        results[provider] = query_provider(provider)
    return results


def format_balance_report() -> str:
    """生成余额报告"""
    results = query_all()
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    lines = [
        f"💰 API 余额查询 | {now}",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    
    for provider, data in results.items():
        name = PROVIDERS[provider]["name"]
        
        if data.get("success"):
            status = data.get("status", "未知")
            plan = data.get("plan", "未知")
            
            lines.append(f"✅ **{name}**")
            
            # 性价比特殊处理
            if provider == "xingjiabiapi":
                balance = data.get("balance", 0)
                consumed = data.get("consumed", 0)
                requests = data.get("requests", 0)
                lines.append(f"   余额: 💰{balance:.2f}")
                lines.append(f"   已消耗: 💰{consumed:.2f}")
                lines.append(f"   请求次数: {requests}")
            # GitHub Copilot 特殊处理
            elif provider == "github-copilot":
                usage_pct = data.get("premium_usage_pct", 0)
                lines.append(f"   状态: {status} | 套餐: {plan}")
                lines.append(f"   Premium 用量: {usage_pct}%")
            else:
                lines.append(f"   状态: {status} | 套餐: {plan}")
            
            # 每日额度
            daily_limit = data.get("daily_limit", 0)
            daily_used = data.get("daily_used", 0)
            if daily_limit > 0:
                pct = daily_used / daily_limit * 100
                lines.append(f"   今日: {daily_used}/{daily_limit} ({pct:.1f}%)")
            
            # 到期时间
            expires = data.get("expires_at")
            if expires:
                exp_date = expires.split("T")[0]
                lines.append(f"   到期: {exp_date}")
            
            # 成功率
            rate = data.get("success_rate", 0)
            if rate > 0:
                lines.append(f"   成功率: {rate*100:.1f}%")
        else:
            error = data.get("error", "未知错误")
            lines.append(f"⚠️ **{name}**: {error}")
        
        lines.append("")
    
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━")
    
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("""
API 余额查询器

用法:
  python balance_checker.py report          # 生成报告
  python balance_checker.py query <provider> # 查询指定供应商
  python balance_checker.py all             # JSON 格式查询所有
""")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "report":
        print(format_balance_report())
    elif cmd == "query" and len(sys.argv) > 2:
        result = query_provider(sys.argv[2])
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    elif cmd == "all":
        print(json.dumps(query_all(), indent=2, ensure_ascii=False, default=str))
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
