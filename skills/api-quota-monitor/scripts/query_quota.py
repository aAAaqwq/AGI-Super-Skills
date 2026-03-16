#!/usr/bin/env python3
"""
API Quota Monitor - Query provider balances/usage.

Usage:
    python3 query_quota.py                    # Query all configured providers
    python3 query_quota.py xai                # Query specific provider
    python3 query_quota.py --type official    # Query only official providers
    python3 query_quota.py --type reseller    # Query only reseller platforms
    python3 query_quota.py --format json      # JSON output
    python3 query_quota.py --report           # Generate human-readable report
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any, List
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Provider configurations
OFFICIAL_PROVIDERS = {
    "zai": {
        "name": "ZAI (智谱)",
        "env_key": "ZAI_API_KEY",
        "alt_env_keys": ["ZHIPU_API_KEY"],
        "method": "browser",
        "browser_url": "https://open.bigmodel.cn/oa/userCenter",
        "note": "No public balance API, use console"
    },
    "minimax": {
        "name": "Minimax",
        "env_key": "MINIMAX_API_KEY",
        "extra_env": ["MINIMAX_GROUP_ID"],
        "api_url": "https://api.minimax.chat/v1/user/balance",
        "method": "api",
        "headers": lambda: {
            "Authorization": f"Bearer {os.environ.get('MINIMAX_API_KEY', '')}",
            "GroupId": os.environ.get("MINIMAX_GROUP_ID", ""),
        },
        "extract": lambda data: {
            "balance": data.get("data", {}).get("balance", 0),
            "unit": data.get("data", {}).get("unit", "CNY"),
        }
    },
    "openrouter": {
        "name": "OpenRouter",
        "env_key": "OPENROUTER_API_KEY",
        "api_url": "https://openrouter.ai/api/v1/auth/key",
        "method": "api",
        "extract": lambda data: {
            "limit_remaining": data.get("data", {}).get("limit_remaining", 0),
            "usage": data.get("data", {}).get("usage", 0),
        }
    },
    "xai": {
        "name": "xAI (Grok)",
        "env_key": "XAI_MGMT_KEY",  # Management API key (separate from inference key)
        "alt_env_keys": ["XAI_MANAGEMENT_KEY"],
        "extra_env": ["XAI_TEAM_ID"],
        "method": "api",
        "api_url": "https://management-api.x.ai/v1/billing/teams/{team_id}/prepaid/balance",
        "team_id_env": "XAI_TEAM_ID",
        "headers": lambda: {
            "Authorization": f"Bearer {os.environ.get('XAI_MGMT_KEY', '')}",
        },
        "extract": lambda data: {
            "prepaid_balance": float(data.get("total", {}).get("val", "0")) / -100,  # Negative cents to positive dollars
            "currency": "USD",
        },
        "note": "Requires Management API key from console.x.ai -> Settings -> Management Keys"
    },
    "gemini": {
        "name": "Google AI (Gemini)",
        "env_key": "GOOGLE_API_KEY",
        "alt_env_keys": ["GEMINI_API_KEY"],
        "method": "browser",
        "browser_url": "https://aistudio.google.com/apikey",
        "note": "No public usage API"
    },
    "anthropic": {
        "name": "Anthropic (Claude)",
        "env_key": "ANTHROPIC_API_KEY",
        "method": "browser",
        "browser_url": "https://console.anthropic.com/settings/billing",
        "note": "No public usage API"
    },
}

SERVICE_PROVIDERS = {
    "brave": {
        "name": "Brave Search API",
        "env_key": "BRAVE_API_KEY",
        "method": "api_headers",
        "api_url": "https://api.search.brave.com/res/v1/web/search?q=test&count=1",
        "headers": lambda: {
            "X-Subscription-Token": os.environ.get("BRAVE_API_KEY", ""),
            "Accept": "application/json",
        },
        "extract_headers": lambda headers: {
            "rate_limit": headers.get("x-ratelimit-limit", ""),
            "rate_remaining": headers.get("x-ratelimit-remaining", ""),
            "rate_reset_seconds": headers.get("x-ratelimit-reset", ""),
            "rate_policy": headers.get("x-ratelimit-policy", ""),
        },
        "note": "Usage info from response headers (x-ratelimit-*)"
    },
    "tavily": {
        "name": "Tavily API",
        "env_key": "TAVILY_API_KEY",
        "api_url": "https://api.tavily.com/balance",
        "method": "api",
    },
    "serper": {
        "name": "Serper API",
        "env_key": "SERPER_API_KEY",
        "api_url": "https://serper.dev/api/account",
        "method": "api",
        "headers": lambda: {
            "X-API-KEY": os.environ.get("SERPER_API_KEY", ""),
        },
    },
}

RESELLER_PROVIDERS = {
    "aixn": {
        "name": "AIXN (XAPI)",
        "method": "browser",
        "browser_url": "https://ai.9w7.cn/console",
        "indicators": ["余额", "消耗", "tokens"],
    },
    "xingjiabiapi": {
        "name": "性价比API",
        "method": "browser",
        "browser_url": "https://xingjiabiapi.com/home",
        "indicators": ["余额", "令牌"],
    },
}


def get_api_key(provider: Dict) -> Optional[str]:
    """Get API key from environment."""
    key = os.environ.get(provider.get("env_key", ""))
    if not key and "alt_env_keys" in provider:
        for alt_key in provider["alt_env_keys"]:
            key = os.environ.get(alt_key, "")
            if key:
                break
    return key


def query_api_headers(provider: Dict, key: str) -> Dict[str, Any]:
    """Query provider via API and extract info from response headers."""
    url = provider["api_url"]
    
    # Build headers
    headers = {"User-Agent": "OpenClaw-API-Quota-Monitor/1.0"}
    if "headers" in provider:
        provider_headers = provider["headers"]()
        headers.update(provider_headers)
    if "Authorization" not in headers and key:
        headers["Authorization"] = f"Bearer {key}"
    
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as response:
            resp_headers = {k.lower(): v for k, v in response.getheaders()}
            
            result = {
                "status": "ok",
                "raw_headers": {k: v for k, v in resp_headers.items() if "ratelimit" in k or "quota" in k},
            }
            
            if "extract_headers" in provider:
                result.update(provider["extract_headers"](resp_headers))
            
            return result
    except HTTPError as e:
        # Even on error, check headers
        if hasattr(e, 'headers'):
            resp_headers = {k.lower(): v for k, v in dict(e.headers).items()}
            rate_headers = {k: v for k, v in resp_headers.items() if "ratelimit" in k}
            if rate_headers:
                result = {
                    "status": "ok",
                    "note": f"HTTP {e.code} but headers available",
                    "raw_headers": rate_headers,
                }
                if "extract_headers" in provider:
                    result.update(provider["extract_headers"](resp_headers))
                return result
        return {"status": "error", "error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def query_api(provider: Dict, key: str) -> Dict[str, Any]:
    """Query provider via API."""
    url = provider["api_url"]
    
    # Handle team_id substitution in URL
    if "{team_id}" in url:
        team_id_env = provider.get("team_id_env", "XAI_TEAM_ID")
        team_id = os.environ.get(team_id_env, "")
        if not team_id:
            return {
                "status": "error",
                "error": f"Missing {team_id_env} environment variable",
            }
        url = url.replace("{team_id}", team_id)
    
    # Build headers - start with default User-Agent (some APIs require it)
    headers = {
        "User-Agent": "OpenClaw-API-Quota-Monitor/1.0"
    }
    # Add provider-specific headers
    if "headers" in provider:
        provider_headers = provider["headers"]()
        headers.update(provider_headers)
    # Add default Authorization if not already set
    if "Authorization" not in headers and key:
        headers["Authorization"] = f"Bearer {key}"
    
    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            
            result = {
                "status": "ok",
                "raw": data,
            }
            
            if "extract" in provider:
                result.update(provider["extract"](data))
            
            return result
    except HTTPError as e:
        return {
            "status": "error",
            "error": f"HTTP {e.code}: {e.reason}",
        }
    except URLError as e:
        return {
            "status": "error",
            "error": str(e.reason),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
        }


def query_browser(provider: Dict) -> Dict[str, Any]:
    """Query provider via browser (placeholder - actual implementation uses browser tool)."""
    return {
        "status": "browser_required",
        "url": provider.get("browser_url", ""),
        "indicators": provider.get("indicators", []),
        "note": provider.get("note", "Use browser tool to check"),
    }


def query_provider(provider_id: str, provider: Dict) -> Dict[str, Any]:
    """Query a single provider."""
    result = {
        "id": provider_id,
        "name": provider.get("name", provider_id),
        "queried_at": datetime.now().isoformat(),
    }
    
    # Check if API key exists
    key = get_api_key(provider)
    method = provider.get("method", "api")
    
    if method == "api":
        if not key:
            result["status"] = "no_key"
            result["note"] = f"Set {provider.get('env_key', 'API_KEY')} environment variable"
        else:
            api_result = query_api(provider, key)
            result.update(api_result)
    elif method == "api_headers":
        if not key:
            result["status"] = "no_key"
            result["note"] = f"Set {provider.get('env_key', 'API_KEY')} environment variable"
        else:
            api_result = query_api_headers(provider, key)
            result.update(api_result)
    elif method == "browser":
        if not key:
            result["status"] = "no_key"
            result["note"] = f"Set {provider.get('env_key', 'API_KEY')} or use browser automation"
        else:
            # Has key but no usage API - need browser
            browser_result = query_browser(provider)
            result.update(browser_result)
    else:
        result["status"] = "unknown_method"
    
    return result


def discover_configured_providers() -> Dict[str, List[str]]:
    """Discover which providers are configured based on environment variables."""
    configured = {"official": [], "service": [], "reseller": []}
    
    for pid, p in OFFICIAL_PROVIDERS.items():
        if get_api_key(p):
            configured["official"].append(pid)
    
    for pid, p in SERVICE_PROVIDERS.items():
        if get_api_key(p):
            configured["service"].append(pid)
    
    # Resellers are checked via auth-session-state.json
    auth_state = os.path.expanduser("~/.openclaw/auth-session-state.json")
    if os.path.exists(auth_state):
        try:
            with open(auth_state) as f:
                state = json.load(f)
            for pid in RESELLER_PROVIDERS:
                if pid in state and state[pid].get("status") == "ok":
                    configured["reseller"].append(pid)
        except:
            pass
    
    return configured


def generate_report(results: List[Dict], format: str = "text") -> str:
    """Generate a report from query results."""
    if format == "json":
        return json.dumps(results, indent=2, ensure_ascii=False)
    
    lines = ["📊 API Quota Report", f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}", ""]
    
    # Group by type
    official = [r for r in results if r["id"] in OFFICIAL_PROVIDERS]
    services = [r for r in results if r["id"] in SERVICE_PROVIDERS]
    resellers = [r for r in results if r["id"] in RESELLER_PROVIDERS]
    
    if official:
        lines.append("━━ 官方供应商 ━━")
        for r in official:
            status_icon = "✅" if r.get("status") == "ok" else "❌" if r.get("status") == "error" else "⚠️"
            # Check various balance field names
            balance = r.get("balance", r.get("prepaid_balance", r.get("limit_remaining", None)))
            unit = r.get("unit", r.get("currency", ""))
            if balance is not None and isinstance(balance, (int, float)):
                if unit:
                    lines.append(f"{status_icon} {r['name']}: ${balance:.2f} {unit}")
                else:
                    lines.append(f"{status_icon} {r['name']}: ${balance:.2f}")
            else:
                lines.append(f"{status_icon} {r['name']}: {r.get('status', '-')}")
        lines.append("")
    
    if services:
        lines.append("━━ 订阅服务 ━━")
        for r in services:
            status_icon = "✅" if r.get("status") == "ok" else "❌" if r.get("status") == "error" else "⚠️"
            # Handle rate limit info from headers (e.g., Brave)
            rate_remaining = r.get("rate_remaining", "")
            rate_limit = r.get("rate_limit", "")
            if rate_remaining and rate_limit:
                # Parse multi-value rate limits: "49, 0" → burst, monthly
                parts_remaining = [p.strip() for p in str(rate_remaining).split(",")]
                parts_limit = [p.strip() for p in str(rate_limit).split(",")]
                if len(parts_remaining) >= 2 and len(parts_limit) >= 2:
                    monthly_remaining = parts_remaining[1]
                    monthly_limit = parts_limit[1]
                    # 0/0 means unlimited or not tracked
                    if monthly_limit == "0" and monthly_remaining == "0":
                        burst_remaining = parts_remaining[0]
                        burst_limit = parts_limit[0]
                        lines.append(f"{status_icon} {r['name']}: ✓ active (burst: {burst_remaining}/{burst_limit} req/s)")
                    else:
                        lines.append(f"{status_icon} {r['name']}: 月剩余 {monthly_remaining}/{monthly_limit}")
                else:
                    lines.append(f"{status_icon} {r['name']}: remaining {rate_remaining}")
            else:
                balance = r.get("balance", r.get("limit_remaining", "-"))
                lines.append(f"{status_icon} {r['name']}: {balance}")
        lines.append("")
    
    if resellers:
        lines.append("━━ 中转站 (浏览器) ━━")
        for r in resellers:
            status_icon = "✅" if r.get("status") == "ok" else "🔍"
            lines.append(f"{status_icon} {r['name']}: {r.get('status', '-')}")
        lines.append("")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Query API provider quotas")
    parser.add_argument("provider", nargs="?", help="Specific provider to query")
    parser.add_argument("--type", choices=["official", "service", "reseller", "all"], 
                       default="all", help="Provider type to query")
    parser.add_argument("--format", choices=["text", "json"], default="text",
                       help="Output format")
    parser.add_argument("--report", action="store_true", help="Generate report")
    parser.add_argument("--discover", action="store_true", help="Only discover configured providers")
    
    args = parser.parse_args()
    
    if args.discover:
        configured = discover_configured_providers()
        print(json.dumps(configured, indent=2))
        return
    
    results = []
    
    if args.provider:
        # Query specific provider
        all_providers = {**OFFICIAL_PROVIDERS, **SERVICE_PROVIDERS, **RESELLER_PROVIDERS}
        if args.provider in all_providers:
            results.append(query_provider(args.provider, all_providers[args.provider]))
        else:
            print(f"Unknown provider: {args.provider}")
            print(f"Available: {', '.join(all_providers.keys())}")
            sys.exit(1)
    else:
        # Query all configured providers
        if args.type in ["official", "all"]:
            for pid, p in OFFICIAL_PROVIDERS.items():
                if get_api_key(p):
                    results.append(query_provider(pid, p))
        
        if args.type in ["service", "all"]:
            for pid, p in SERVICE_PROVIDERS.items():
                if get_api_key(p):
                    results.append(query_provider(pid, p))
        
        if args.type in ["reseller", "all"]:
            for pid, p in RESELLER_PROVIDERS.items():
                results.append(query_provider(pid, p))
    
    if args.format == "json":
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(generate_report(results, "text"))


if __name__ == "__main__":
    main()
