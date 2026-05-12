#!/usr/bin/env python3
"""
稳定余额查询 — 三层fallback
1. ClobClient API（最准确）
2. 本地缓存 data/balance-cache.json
3. $50 保守估算（绝对兜底）

用法: python3 get_balance_stable.py
输出: {"cash": 48.44, "source": "api", "ts": "..."}
"""
# Proxy fix: remove ALL_PROXY (socks://) to avoid httpx crash (2026-04-15)
import os
for _k in ['ALL_PROXY', 'all_proxy']:
    os.environ.pop(_k, None)

import sys, json
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent  # scripts/xxx.py → skills/xxx/
CACHE_FILE = WORKSPACE / 'data' / 'balance-cache.json'
ENV_FILE = WORKSPACE / '.env.poly'

def load_env():
    from dotenv import load_dotenv
    load_dotenv(ENV_FILE)

def get_api_balance():
    """通过ClobClient获取真实余额"""
    try:
        # 先清除代理，避免httpx socks冲突（在import之前清除）
        for k in list(os.environ.keys()):
            if 'proxy' in k.lower() and k not in ('NO_PROXY', 'no_proxy', 'GOPROXY'):
                del os.environ[k]
        
        sys.path.insert(0, str(Path.home() / '.local/lib/python3.12/site-packages'))
        from dotenv import load_dotenv
        load_dotenv(str(ENV_FILE))
        
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
        
        PK = os.environ['POLY_PRIVATE_KEY']
        PROXY = os.environ['POLY_PROXY_WALLET']
        
        client = ClobClient(
            host='https://clob.polymarket.com',
            key=PK,
            chain_id=137,
            signature_type=1,
            funder=PROXY
        )
        client.set_api_creds(client.create_or_derive_api_creds())
        
        bal = client.get_balance_allowance(
            BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
        )
        cash = float(bal.get('balance', 0)) / 1e6
        
        # 同时检查open orders（CLOB）
        orders = client.get_orders()
        open_positions = len(orders)
        
        # 尝试用Data API获取完整持仓列表（备选，不影响主流程）
        data_api_positions = []
        try:
            import requests
            r = requests.get(
                f"https://data-api.polymarket.com/positions?user={PROXY}",
                headers={"Accept": "application/json"},
                timeout=5
            )
            if r.status_code == 200:
                raw = r.json()
                if isinstance(raw, list):
                    data_api_positions = raw
        except:
            pass
        
        return {
            'cash': round(cash, 2),
            'open_positions': open_positions,
            'source': 'api'
        }
    except Exception as e:
        return {'error': str(e), 'source': 'api_failed'}

def read_cache():
    """读取本地缓存"""
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE) as f:
                return json.load(f)
    except:
        pass
    return None

def write_cache(data):
    """写入本地缓存"""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except:
        pass

def main():
    from datetime import datetime, timezone
    
    result = {
        'ts': datetime.now(timezone.utc).isoformat(),
    }
    
    # Layer 1: ClobClient API
    api_data = get_api_balance()
    if 'error' not in api_data:
        result.update(api_data)
        write_cache(result)
        print(json.dumps(result, indent=2))
        return
    
    # Layer 2: 本地缓存
    cache = read_cache()
    if cache:
        result.update(cache)
        result['source'] = 'cache'
        result['cache_age'] = f"age: {datetime.now(timezone.utc) - datetime.fromisoformat(cache['ts'])}"
        print(json.dumps(result, indent=2))
        return
    
    # Layer 3: 绝对兜底
    result['cash'] = 50.0
    result['open_positions'] = 0
    result['source'] = 'fallback_conservative'
    result['note'] = 'API和缓存都失败，使用保守估算$50'
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
