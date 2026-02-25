#!/usr/bin/env python3
"""
Polymarket 存款脚本
通过 CTF Exchange 合约存入 USDC.e
"""

import subprocess
import json
from web3 import Web3

# 配置
RPC_URL = "https://polygon-bor-rpc.publicnode.com"
WALLET_ADDRESS = "0xd91eF877D04ACB06a9dE22e536765D2Ace246A9b"
USDC_E_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

# ERC20 ABI (approve, balanceOf)
ERC20_ABI = json.loads('''[
    {"inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "name": "approve", "outputs": [{"name": "", "type": "bool"}], "stateMutability": "nonpayable", "type": "function"},
    {"inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"},
    {"inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "name": "allowance", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}
]''')

# CTF Exchange ABI (deposit)
CTF_EXCHANGE_ABI = json.loads('''[
    {"inputs": [{"name": "amount", "type": "uint256"}], "name": "deposit", "outputs": [], "stateMutability": "nonpayable", "type": "function"}
]''')

def get_private_key():
    result = subprocess.run(['pass', 'show', 'api/polymarket-wallet'], capture_output=True, text=True)
    return result.stdout.strip()

def main():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    private_key = get_private_key()
    
    # 合约实例
    usdc_e = w3.eth.contract(address=Web3.to_checksum_address(USDC_E_ADDRESS), abi=ERC20_ABI)
    ctf_exchange = w3.eth.contract(address=Web3.to_checksum_address(CTF_EXCHANGE_ADDRESS), abi=CTF_EXCHANGE_ABI)
    
    # 检查 USDC.e 余额
    balance = usdc_e.functions.balanceOf(WALLET_ADDRESS).call()
    balance_usd = balance / 1e6
    print(f"USDC.e 余额: ${balance_usd:.2f}")
    
    if balance == 0:
        print("❌ 没有余额，无法存款")
        return
    
    # 检查授权额度
    allowance = usdc_e.functions.allowance(WALLET_ADDRESS, CTF_EXCHANGE_ADDRESS).call()
    allowance_usd = allowance / 1e6
    print(f"当前授权: ${allowance_usd:.2f}")
    
    # 如果授权不足，先 approve
    if allowance < balance:
        print(f"步骤 1: 授权 USDC.e 给 CTF Exchange...")
        approve_amount = balance  # 授权全部余额
        nonce = w3.eth.get_transaction_count(WALLET_ADDRESS)
        
        approve_tx = usdc_e.functions.approve(
            Web3.to_checksum_address(CTF_EXCHANGE_ADDRESS),
            approve_amount
        ).build_transaction({
            'from': WALLET_ADDRESS,
            'nonce': nonce,
            'gas': 100000,
            'gasPrice': w3.eth.gas_price
        })
        
        signed_tx = w3.eth.account.sign_transaction(approve_tx, private_key)
        approve_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        print(f"Approve TX: {approve_hash.hex()}")
        
        # 等待确认
        receipt = w3.eth.wait_for_transaction_receipt(approve_hash)
        if receipt['status'] == 1:
            print("✅ Approve 成功!")
        else:
            print("❌ Approve 失败")
            return
    else:
        print("✅ 已有足够授权")
    
    # 存款
    print(f"步骤 2: 存款 ${balance_usd:.2f} 到 Polymarket...")
    nonce = w3.eth.get_transaction_count(WALLET_ADDRESS)
    
    deposit_tx = ctf_exchange.functions.deposit(balance).build_transaction({
        'from': WALLET_ADDRESS,
        'nonce': nonce,
        'gas': 200000,
        'gasPrice': w3.eth.gas_price
    })
    
    signed_tx = w3.eth.account.sign_transaction(deposit_tx, private_key)
    deposit_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Deposit TX: {deposit_hash.hex()}")
    
    # 等待确认
    receipt = w3.eth.wait_for_transaction_receipt(deposit_hash)
    if receipt['status'] == 1:
        print(f"✅ 存款成功! ${balance_usd:.2f} 已存入 Polymarket")
    else:
        print("❌ 存款失败")
        print(f"检查交易: https://polygonscan.com/tx/{deposit_hash.hex()}")

if __name__ == "__main__":
    main()
