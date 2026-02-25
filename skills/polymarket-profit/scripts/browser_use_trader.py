#!/usr/bin/env python3
"""
Polymarket 智能交易脚本 - 使用 browser-use
AI驱动的浏览器自动化，比传统Playwright更智能
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel

# 添加项目路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
CONFIG_DIR = PROJECT_DIR / "config"

# 确保数据目录存在
DATA_DIR.mkdir(exist_ok=True)

# Try to import browser_use
try:
    from browser_use import Agent, BrowserProfile, BrowserSession
    from browser_use.llm.anthropic.chat import ChatAnthropic as BUChatAnthropic
    HAS_BROWSER_USE = True
except ImportError:
    HAS_BROWSER_USE = False
    print("⚠️ browser-use not installed. Run: pip install browser-use")

HAS_LANGCHAIN = True  # browser-use has its own LLM wrappers


# 结构化输出模型
class MarketInfo(BaseModel):
    """市场信息"""
    question: str
    yes_price: float
    no_price: float
    volume_24h: str
    liquidity: str
    url: str


class TradingResult(BaseModel):
    """交易结果"""
    success: bool
    market: str
    action: str  # "buy_yes", "buy_no", "sell"
    amount: float
    price: float
    tx_hash: str | None = None
    error: str | None = None


class PortfolioStatus(BaseModel):
    """持仓状态"""
    total_value: float
    positions: list[dict]
    available_balance: float


class PolymarketTrader:
    """Polymarket 智能交易器"""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.llm = None
        self.browser = None
        
        # 加载配置
        self.config = self._load_config()
        
        # 登录态路径
        self.auth_path = Path.home() / ".playwright-data" / "polymarket" / "auth.json"
        
    def _load_config(self) -> dict:
        """加载配置"""
        config_file = CONFIG_DIR / "strategies.json"
        if config_file.exists():
            return json.loads(config_file.read_text())
        return {
            "max_trade_amount": 1.0,
            "min_no_price": 0.85,
            "target_markets": ["fed-decision-in-march-885"]
        }
    
    def _get_llm(self):
        """获取 LLM 实例"""
        if not HAS_LANGCHAIN:
            raise RuntimeError("langchain-openai not installed")
        
        # 使用 xingsuancode API (从环境变量或 pass 获取)
        api_key = os.environ.get("XSC_API_KEY")
        if not api_key:
            # 尝试从 pass 获取
            import subprocess
            try:
                result = subprocess.run(
                    ["pass", "show", "api/xingsuancode"],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    api_key = result.stdout.strip()
            except:
                pass
        
        if not api_key:
            raise ValueError("XSC_API_KEY not found. Set environment variable or store in pass")
        
        return BUChatAnthropic(
            model="claude-sonnet-4-6",
            base_url="https://cn.xingsuancode.com",
            api_key=api_key,
            temperature=0.1,
        )
    
    def _get_browser(self):
        """获取 Browser 实例"""
        if not HAS_BROWSER_USE:
            raise RuntimeError("browser-use not installed")
        
        # 使用用户真实的 Chrome 配置（复制了登录态）
        user_data_dir = str(Path.home() / ".config" / "google-chrome-browseruse")
        
        profile = BrowserProfile(
            executable_path="/usr/bin/google-chrome-stable",
            headless=self.headless,
            disable_security=True,
            user_data_dir=user_data_dir,
            profile_directory="Default",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )
        return BrowserSession(browser_profile=profile)
    
    async def check_market(self, market_slug: str) -> MarketInfo:
        """检查市场状态"""
        llm = self._get_llm()
        browser_session = self._get_browser()
        
        url = f"https://polymarket.com/event/{market_slug}"
        
        agent = Agent(
            task=f"""
            访问 Polymarket 市场: {url}
            
            提取以下信息：
            1. 市场问题（标题）
            2. Yes 的当前价格（0-1之间的小数）
            3. No 的当前价格（0-1之间的小数）
            4. 24小时交易量（如 "$1.2M"）
            5. 流动性（如 "$500K"）
            
            如果找不到某些信息，使用 "N/A"。
            """,
            llm=llm,
            browser_session=browser_session,
            output_model_schema=MarketInfo,
            use_vision=False,  # 节省 token
            max_actions_per_step=5,
        )
        
        result = await agent.run()
        # browser_session auto-cleanup
        
        return result
    
    async def execute_trade(
        self,
        market_slug: str,
        action: str,
        amount: float,
        price_condition: float | None = None
    ) -> TradingResult:
        """执行交易"""
        llm = self._get_llm()
        browser_session = self._get_browser()
        
        url = f"https://polymarket.com/event/{market_slug}"
        
        action_desc = {
            "buy_yes": f"买入 ${amount} 的 Yes",
            "buy_no": f"买入 ${amount} 的 No",
        }.get(action, action)
        
        price_check = ""
        if price_condition:
            if "yes" in action.lower():
                price_check = f"只有当 Yes 价格 ≤ {price_condition} 时才执行"
            else:
                price_check = f"只有当 No 价格 ≥ {price_condition} 时才执行"
        
        agent = Agent(
            task=f"""
            在 Polymarket 执行交易：
            
            1. 打开市场页面: {url}
            2. 检查当前价格
            3. {action_desc}
            4. {price_check}
            5. 确认交易
            6. 如果需要连接钱包，使用已保存的登录态
            
            如果价格条件不满足，取消交易并返回 success=false。
            如果交易成功，返回交易哈希。
            """,
            llm=llm,
            browser_session=browser_session,
            output_model_schema=TradingResult,
            use_vision=False,
            max_actions_per_step=10,
        )
        
        result = await agent.run()
        # browser_session auto-cleanup
        
        # 记录交易
        self._log_trade(result)
        
        return result
    
    async def get_portfolio(self) -> PortfolioStatus:
        """获取持仓状态"""
        llm = self._get_llm()
        browser_session = self._get_browser()
        
        agent = Agent(
            task="""
            访问 Polymarket 账户页面：
            https://polymarket.com/portfolio
            
            提取以下信息：
            1. 总资产价值（美元）
            2. 可用余额
            3. 所有持仓列表（市场名称、数量、平均价格、当前价格）
            
            如果需要登录，使用已保存的登录态。
            """,
            llm=llm,
            browser_session=browser_session,
            output_model_schema=PortfolioStatus,
            use_vision=False,
        )
        
        result = await agent.run()
        # browser_session auto-cleanup
        
        return result
    
    def _log_trade(self, result: TradingResult):
        """记录交易日志"""
        log_file = DATA_DIR / "trade_log.jsonl"
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "success": result.success,
            "market": result.market,
            "action": result.action,
            "amount": result.amount,
            "price": result.price,
            "tx_hash": result.tx_hash,
            "error": result.error,
        }
        
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Polymarket 智能交易")
    parser.add_argument("command", choices=["check", "trade", "portfolio"])
    parser.add_argument("--market", default="fed-decision-in-march-885", help="市场 slug")
    parser.add_argument("--action", choices=["buy_yes", "buy_no"], help="交易动作")
    parser.add_argument("--amount", type=float, default=0.5, help="交易金额")
    parser.add_argument("--price", type=float, help="价格条件")
    parser.add_argument("--headless", action="store_true", default=True, help="无头模式")
    parser.add_argument("--show", action="store_true", help="显示浏览器")
    
    args = parser.parse_args()
    
    if not HAS_BROWSER_USE or not HAS_LANGCHAIN:
        print("❌ 缺少依赖，请安装:")
        print("   pip install browser-use langchain-openai")
        sys.exit(1)
    
    trader = PolymarketTrader(headless=not args.show)
    
    try:
        if args.command == "check":
            print(f"📊 检查市场: {args.market}")
            result = await trader.check_market(args.market)
            print(f"\n市场: {result.question}")
            print(f"Yes 价格: {result.yes_price:.2f}")
            print(f"No 价格: {result.no_price:.2f}")
            print(f"24h 交易量: {result.volume_24h}")
            print(f"流动性: {result.liquidity}")
            
        elif args.command == "trade":
            if not args.action:
                print("❌ 请指定 --action (buy_yes 或 buy_no)")
                sys.exit(1)
            
            print(f"💰 执行交易: {args.action} ${args.amount}")
            result = await trader.execute_trade(
                args.market,
                args.action,
                args.amount,
                args.price
            )
            
            if result.success:
                print(f"✅ 交易成功!")
                print(f"   市场: {result.market}")
                print(f"   价格: {result.price}")
                if result.tx_hash:
                    print(f"   TX: {result.tx_hash}")
            else:
                print(f"❌ 交易失败: {result.error}")
                
        elif args.command == "portfolio":
            print("📋 获取持仓状态...")
            result = await trader.get_portfolio()
            print(f"\n总价值: ${result.total_value:.2f}")
            print(f"可用余额: ${result.available_balance:.2f}")
            print(f"\n持仓:")
            for pos in result.positions:
                print(f"  - {pos}")
                
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
