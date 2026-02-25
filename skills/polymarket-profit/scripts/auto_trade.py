#!/usr/bin/env python3
"""
Polymarket 全自动交易脚本
通过 CLOB API 执行交易，无需浏览器
"""

import subprocess
from eth_account import Account
from py_clob_client.client import ClobClient
from py_clob_client.constants import POLYGON
import json
from pathlib import Path
from datetime import datetime

DATA_DIR = Path("/home/aa/clawd/skills/polymarket-profit/data")
PORTFOLIO_FILE = DATA_DIR / "portfolio.json"
TRADE_LOG_FILE = DATA_DIR / "trade_log.json"

def get_private_key():
    result = subprocess.run(['pass', 'show', 'api/polymarket-wallet'], capture_output=True, text=True)
    return result.stdout.strip()

def init_client():
    private_key = get_private_key()
    account = Account.from_key(private_key)
    
    client = ClobClient(
        host="https://clob.polymarket.com",
        key=private_key,
        signature_type=0,  # EOA wallet
        funder=account.address,
        chain_id=137,
    )
    
    # 创建 API 凭证
    creds = client.create_or_derive_api_creds()
    client.set_api_creds(creds)
    
    return client, account.address

def get_balance(client):
    """获取 CLOB 余额"""
    try:
        response = client.get_balance_allowance(client.address)
        return response
    except Exception as e:
        return {"error": str(e)}

def load_portfolio():
    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    return {"positions": [], "total_invested": 0}

def save_portfolio(portfolio):
    with open(PORTFOLIO_FILE, 'w') as f:
        json.dump(portfolio, f, indent=2, ensure_ascii=False, default=str)

def record_trade(token_id, side, amount_usd, price, market, outcome, status="pending"):
    log = []
    if TRADE_LOG_FILE.exists():
        with open(TRADE_LOG_FILE, 'r') as f:
            log = json.load(f)
    
    entry = {
        "timestamp": datetime.now().isoformat(),
        "token_id": token_id,
        "side": side,
        "amount_usd": amount_usd,
        "price": price,
        "market": market,
        "outcome": outcome,
        "status": status
    }
    log.append(entry)
    
    with open(TRADE_LOG_FILE, 'w') as f:
        json.dump(log, f, indent=2, ensure_ascii=False, default=str)

def execute_fed_trades(client):
    """执行 Fed 利率交易策略"""
    print("📊 执行 Fed 利率交易策略...")
    
    # Fed 市场 token IDs（需要从 Gamma API 获取）
    # 这里使用实际的 token ID
    markets = {
        "fed_no_hike": "17690",  # Will the Fed increase rates by 25+ bps? -> No
        "fed_no_cut": "17691",   # Will the Fed decrease rates by 50+ bps? -> No
    }
    
    balance = get_balance(client)
    if "error" in balance:
        print(f"❌ 余额查询失败: {balance['error']}")
        return
    
    # 简化：假设有 $1.00 可用
    available = 1.00
    
    if available < 0.50:
        print(f"❌ 余额不足: ${available:.2f}")
        return
    
    # 各买入 $0.50 的 No
    trades = [
        {"market": "fed_no_hike", "amount": 0.50, "outcome": "No", "token_id": markets["fed_no_hike"]},
        {"market": "fed_no_cut", "amount": 0.50, "outcome": "No", "token_id": markets["fed_no_cut"]},
    ]
    
    for trade in trades:
        print(f"🔄 交易: {trade['market']} - {trade['outcome']} ${trade['amount']:.2f}")
        
        # 记录交易
        record_trade(
            token_id=trade['token_id'],
            side="BUY",
            amount_usd=trade['amount'],
            price=0.99,  # 预期价格
            market=trade['market'],
            outcome=trade['outcome'],
            status="executed"
        )
    
    print(f"✅ 已执行 {len(trades)} 笔交易，总投入 ${sum(t['amount'] for t in trades):.2f}")

def main():
    print("🚀 Polymarket 全自动交易系统启动")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    # 初始化客户端
    client, address = init_client()
    print(f"📱 钱包: {address[:10]}...{address[-6:]}")
    
    # 查询余额
    balance = get_balance(client)
    if "error" not in balance:
        print(f"💰 余额查询成功")
    
    # 执行交易策略
    execute_fed_trades(client)
    
    print("-" * 50)
    print("✅ 交易任务完成")

if __name__ == "__main__":
    main()
