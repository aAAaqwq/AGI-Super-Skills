#!/usr/bin/env python3
"""
Polymarket 能力测试脚本
测试小quant的三个核心能力：查询订单、查询余额、操控交易
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加项目路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"

# 钱包配置
WALLET_ADDRESS = "0xd91eF877D04ACB06a9dE22e536765D2Ace246A9b"
CHAIN_ID = 137  # Polygon

def get_api_creds():
    """获取API凭证（从pass或环境变量）"""
    import subprocess
    try:
        # 尝试从pass获取私钥
        result = subprocess.run(
            ["pass", "show", "api/polymarket-wallet"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return os.environ.get("POLYMARKET_PRIVATE_KEY", "")

def test_1_query_balance():
    """测试1: 查询余额"""
    print("\n" + "="*50)
    print("📊 测试1: 查询余额")
    print("="*50)
    
    results = {"test": "query_balance", "status": "unknown", "details": {}}
    
    try:
        from py_clob_client.client import ClobClient
        
        # 创建客户端（只读模式，不需要私钥也可以查询）
        client = ClobClient(
            host="https://clob.polymarket.com",
            key="",
            chain_id=CHAIN_ID
        )
        
        # 查询USDC余额
        try:
            # 方法1: 查询链上余额
            from web3 import Web3
            w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
            
            # USDC.e 合约 (Polymarket使用)
            usdc_e_address = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
            usdc_native_address = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
            
            # 简化的ERC20 ABI
            erc20_abi = '[{"inputs":[{"name":"_owner","type":"address"}],"name":"balanceOf","outputs":[{"name":"balance","type":"uint256"}],"stateMutability":"view","type":"function"}]'
            
            usdc_e = w3.eth.contract(address=usdc_e_address, abi=json.loads(erc20_abi))
            usdc_native = w3.eth.contract(address=usdc_native_address, abi=json.loads(erc20_abi))
            
            # 查询余额
            balance_e = usdc_e.functions.balanceOf(WALLET_ADDRESS).call()
            balance_native = usdc_native.functions.balanceOf(WALLET_ADDRESS).call()
            
            # 转换为可读格式 (6位小数)
            balance_e_usd = balance_e / 1e6
            balance_native_usd = balance_native / 1e6
            
            results["status"] = "success"
            results["details"]["usdc_e"] = f"${balance_e_usd:.2f}"
            results["details"]["usdc_native"] = f"${balance_native_usd:.2f}"
            
            print(f"✅ USDC.e (bridged): ${balance_e_usd:.2f}")
            print(f"✅ USDC (native): ${balance_native_usd:.2f}")
            
        except Exception as e:
            results["status"] = "partial"
            results["details"]["error"] = str(e)
            print(f"⚠️ 链上查询失败: {e}")
            
    except ImportError as e:
        results["status"] = "failed"
        results["details"]["error"] = f"缺少依赖: {e}"
        print(f"❌ 缺少依赖: {e}")
        
    return results

def test_2_query_orders():
    """测试2: 查询订单"""
    print("\n" + "="*50)
    print("📋 测试2: 查询交易订单")
    print("="*50)
    
    results = {"test": "query_orders", "status": "unknown", "details": {}}
    
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import OpenOrderParams
        
        # 创建客户端
        client = ClobClient(
            host="https://clob.polymarket.com",
            key="",
            chain_id=CHAIN_ID
        )
        
        # 查询订单需要签名，这里尝试查询公开订单
        try:
            # 查询市场订单簿（公开数据）
            # Fed March 市场 token ID
            token_id = "21742633143463906290569050155826241533067272736897614950488156847949938836455"  # 示例
            
            print("尝试查询订单簿...")
            # 由于没有签名密钥，这里只能查询公开数据
            results["status"] = "partial"
            results["details"]["note"] = "查询公开订单簿需要API签名，私钥查询受限"
            print("⚠️ 查询个人订单需要API签名")
            print("   可查询: 公开市场订单簿")
            print("   不可查询: 个人订单（需要私钥签名）")
            
        except Exception as e:
            results["status"] = "partial"
            results["details"]["error"] = str(e)
            print(f"⚠️ 订单查询受限: {e}")
            
    except ImportError as e:
        results["status"] = "failed"
        results["details"]["error"] = f"缺少依赖: {e}"
        print(f"❌ 缺少依赖: {e}")
        
    return results

def test_3_execute_trade():
    """测试3: 操控交易（模拟）"""
    print("\n" + "="*50)
    print("💸 测试3: 操控交易能力")
    print("="*50)
    
    results = {"test": "execute_trade", "status": "unknown", "details": {}}
    
    # 检查是否有私钥
    private_key = get_api_creds()
    
    if not private_key:
        results["status"] = "no_creds"
        results["details"]["error"] = "未找到私钥，无法执行交易"
        print("❌ 未找到私钥 (POLYMARKET_PRIVATE_KEY 或 pass api/polymarket-wallet)")
        print("   交易功能需要私钥签名")
        return results
    
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import OrderArgs, MarketOrderArgs
        
        print("✅ 私钥已获取")
        print("⚠️ 实际交易需要:")
        print("   1. 足够的USDC.e余额")
        print("   2. 市场流动性")
        print("   3. 用户确认")
        
        results["status"] = "ready"
        results["details"]["private_key"] = "已配置"
        results["details"]["note"] = "交易能力就绪，需要余额和用户确认"
        
    except ImportError as e:
        results["status"] = "failed"
        results["details"]["error"] = f"缺少依赖: {e}"
        print(f"❌ 缺少依赖: {e}")
        
    return results

def test_4_browser_use():
    """测试4: browser-use 浏览器自动化能力"""
    print("\n" + "="*50)
    print("🌐 测试4: browser-use 浏览器自动化")
    print("="*50)
    
    results = {"test": "browser_use", "status": "unknown", "details": {}}
    
    try:
        from browser_use import Agent, BrowserProfile, BrowserSession
        from browser_use.llm.anthropic.chat import ChatAnthropic
        
        print("✅ browser-use 已安装")
        results["details"]["browser_use"] = "已安装"
        
        # 检查Chrome
        import os
        chrome_path = "/usr/bin/google-chrome-stable"
        if os.path.exists(chrome_path):
            print(f"✅ Chrome 路径: {chrome_path}")
            results["details"]["chrome"] = "已安装"
        else:
            print("⚠️ Chrome 未找到")
            results["details"]["chrome"] = "未找到"
        
        # 检查API密钥
        xsc_key = os.environ.get("XSC_API_KEY") or Path.home().joinpath(".password-store/api/xingsuancode.gpg").exists()
        if xsc_key:
            print("✅ LLM API 密钥已配置")
            results["details"]["llm_api"] = "已配置"
        else:
            print("⚠️ LLM API 密钥未配置")
            results["details"]["llm_api"] = "未配置"
        
        results["status"] = "ready"
        results["details"]["note"] = "browser-use能力就绪"
        
    except ImportError as e:
        results["status"] = "failed"
        results["details"]["error"] = f"缺少依赖: {e}"
        print(f"❌ 缺少依赖: {e}")
        
    return results

def main():
    """运行所有测试"""
    print("="*60)
    print("🧪 Polymarket 能力测试")
    print(f"⏰ 测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"👛 钱包地址: {WALLET_ADDRESS}")
    print("="*60)
    
    all_results = []
    
    # 测试1: 查询余额
    r1 = test_1_query_balance()
    all_results.append(r1)
    
    # 测试2: 查询订单
    r2 = test_2_query_orders()
    all_results.append(r2)
    
    # 测试3: 操控交易
    r3 = test_3_execute_trade()
    all_results.append(r3)
    
    # 测试4: browser-use
    r4 = test_4_browser_use()
    all_results.append(r4)
    
    # 汇总报告
    print("\n" + "="*60)
    print("📊 测试汇总")
    print("="*60)
    
    for r in all_results:
        status_icon = {
            "success": "✅",
            "ready": "🟢",
            "partial": "⚠️",
            "no_creds": "🔴",
            "failed": "❌",
            "unknown": "❓"
        }.get(r["status"], "❓")
        
        print(f"{status_icon} {r['test']}: {r['status']}")
        if r['details'].get('error'):
            print(f"   错误: {r['details']['error']}")
        if r['details'].get('note'):
            print(f"   说明: {r['details']['note']}")
    
    # 保存结果
    result_file = DATA_DIR / "capability_test.json"
    with open(result_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "wallet": WALLET_ADDRESS,
            "results": all_results
        }, f, indent=2)
    
    print(f"\n📁 结果已保存: {result_file}")
    
    return all_results

if __name__ == "__main__":
    main()
