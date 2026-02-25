#!/usr/bin/env python3
"""
Polymarket 自动交易模块
使用 CLOB API 执行真实交易
"""

import json
import subprocess
from pathlib import Path
from py_clob_client.constants import POLYGON
from py_clob_client.client import ClobClient
from eth_account import Account
import sys

DATA_DIR = Path("/home/aa/clawd/skills/polymarket-profit/data")
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
TRADE_LOG_FILE = DATA_DIR / "trade_log.json"

# 从 pass 获取私钥
def get_private_key():
    result = subprocess.run(['pass', 'show', 'api/polymarket-wallet'], capture_output=True, text=True)
    return result.stdout.strip()

# 初始化 CLOB 客户端
def init_client():
    private_key = get_private_key()
    account = Account.from_key(private_key)

    # 创建客户端
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        signature_type=2,  # Polymarket 使用签名类型 2 (eth_signTypedData_v4)
        funder=account.address,
        chain_id=137,  # Polygon
    )
    return client, account.address

def get_balance(client):
    """获取账户余额"""
    try:
        balance = client.get_balance()
        return balance
    except Exception as e:
        print(f"获取余额失败: {e}")
        return None

def get_markets():
    """获取活跃市场"""
    try:
        markets = client.get_markets()
        return markets
    except Exception as e:
        print(f"获取市场失败: {e}")
        return None

def place_order(client, token_id, side, price, size):
    """下单"""
    try:
        # side: "BUY" or "SELL"
        # price: 价格 (0-1)
        # size: 数量 (shares)
        order = client.create_order(
            token_id=token_id,
            side=side,
            price=price,
            size=size,
        )
        return order
    except Exception as e:
        print(f"下单失败: {e}")
        return None

if __name__ == "__main__":
    print("初始化 Polymarket CLOB 客户端...")
    client, address = init_client()
    print(f"钱包地址: {address}")

    # 测试连接
    balance = get_balance(client)
    if balance:
        print(f"余额: {balance}")

    # 测试获取市场
    print("\n测试获取市场...")
    markets = get_markets()
    if markets:
        print(f"成功获取 {len(markets)} 个市场")
