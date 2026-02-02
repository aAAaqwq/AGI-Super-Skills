#!/usr/bin/env python3
"""
API Provider Balance Query Script
查询各 API 供应商的余额（通过已知 API 端点）
"""

import json
import sys
import os
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# 供应商配置
PROVIDERS = {
    "openrouter-vip": {
        "name": "OpenRouter VIP",
        "balance_url": None,  # 需要浏览器登录
        "dashboard": "https://openrouter.vip/dashboard"
    },
    "zai": {
        "name": "智谱 ZAI",
        "balance_url": None,  # 需要浏览器登录
        "dashboard": "https://open.bigmodel.cn/console/account"
    },
    "anapi": {
        "name": "Anapi",
        "balance_url": None,  # 需要浏览器登录
        "dashboard": "https://anapi.9w7.cn/dashboard"
    },
    "openrouter": {
        "name": "OpenRouter",
        "balance_url": "https://openrouter.ai/api/v1/auth/key",
        "dashboard": "https://openrouter.ai/settings/keys"
    },
    "anthropic": {
        "name": "Anthropic",
        "balance_url": None,
        "dashboard": "https://console.anthropic.com/settings/billing"
    },
    "openai": {
        "name": "OpenAI",
        "balance_url": None,
        "dashboard": "https://platform.openai.com/usage"
    }
}

def query_openrouter_balance(api_key: str) -> dict:
    """Query OpenRouter balance via API"""
    url = "https://openrouter.ai/api/v1/auth/key"
    req = Request(url, headers={"Authorization": f"Bearer {api_key}"})
    try:
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return {
                "success": True,
                "balance": data.get("data", {}).get("limit_remaining"),
                "usage": data.get("data", {}).get("usage"),
                "raw": data
            }
    except (URLError, HTTPError) as e:
        return {"success": False, "error": str(e)}

def get_provider_info(provider_id: str) -> dict:
    """Get provider info and dashboard URL"""
    return PROVIDERS.get(provider_id, {
        "name": provider_id,
        "balance_url": None,
        "dashboard": None
    })

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"providers": list(PROVIDERS.keys())}))
        return
    
    provider = sys.argv[1]
    api_key = sys.argv[2] if len(sys.argv) > 2 else None
    
    info = get_provider_info(provider)
    result = {
        "provider": provider,
        "name": info["name"],
        "dashboard": info["dashboard"],
        "balance_api_available": info["balance_url"] is not None
    }
    
    if provider == "openrouter" and api_key:
        balance_result = query_openrouter_balance(api_key)
        result.update(balance_result)
    
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
