#!/usr/bin/env python3
"""
Polymarket 凯利公式回测模拟
模拟 $6 → $18 的复利增长路径
"""

import json
import random
from datetime import datetime, timedelta

# 初始条件
INITIAL_CAPITAL = 6.0
TARGET_CAPITAL = 18.0

# 策略参数
STRATEGIES = {
    "conservative_no": {
        "name": "保守 No 策略 (1/4 Kelly)",
        "buy_side": "No",
        "min_price": 0.85,  # No ≥ 85%
        "true_prob": 0.92,  # 估计真实概率
        "kelly_fraction": 0.25,  # 1/4 Kelly
        "win_rate": 0.88,  # 实际胜率
    },
    "moderate_no": {
        "name": "中等 No 策略 (1/2 Kelly)",
        "buy_side": "No",
        "min_price": 0.80,
        "true_prob": 0.88,
        "kelly_fraction": 0.50,
        "win_rate": 0.82,
    },
    "aggressive_no": {
        "name": "激进 No 策略 (Full Kelly)",
        "buy_side": "No",
        "min_price": 0.85,
        "true_prob": 0.92,
        "kelly_fraction": 1.0,
        "win_rate": 0.88,
    },
}


def calculate_kelly(price, true_prob):
    """计算 Kelly 百分比"""
    if true_prob > price:  # 买入该边
        edge = true_prob - price
        kelly = edge / (1 - price)
        return max(0, kelly)
    return 0


def simulate_strategy(strategy, capital, num_trades=100, num_sims=1000):
    """模拟策略表现"""
    results = []
    
    for _ in range(num_sims):
        current = capital
        trades_made = 0
        max_drawdown = 0
        peak = capital
        history = [capital]
        
        while current < TARGET_CAPITAL and trades_made < num_trades and current > 0.5:
            # 计算下注比例
            price = strategy["min_price"]  # 简化：假设总是以最低价格买入
            true_prob = strategy["true_prob"]
            
            kelly = calculate_kelly(price, true_prob)
            bet_fraction = kelly * strategy["kelly_fraction"]
            bet_fraction = min(bet_fraction, 0.50)  # 最大 50% 仓位
            
            bet_amount = current * bet_fraction
            
            # 模拟结果
            if random.random() < strategy["win_rate"]:
                # 赢：获得 (1-price)/price 的收益
                profit_ratio = (1 - price) / price
                current += bet_amount * profit_ratio
            else:
                # 输：损失全部下注
                current -= bet_amount
            
            trades_made += 1
            
            # 跟踪回撤
            if current > peak:
                peak = current
            drawdown = (peak - current) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            
            history.append(current)
            
            # 破产检查
            if current < 0.10:
                break
        
        results.append({
            "final": current,
            "trades": trades_made,
            "max_drawdown": max_drawdown,
            "success": current >= TARGET_CAPITAL,
            "history": history,
        })
    
    return results


def analyze_results(results):
    """分析模拟结果"""
    success_rate = sum(1 for r in results if r["success"]) / len(results)
    avg_trades = sum(r["trades"] for r in results) / len(results)
    avg_final = sum(r["final"] for r in results) / len(results)
    avg_drawdown = sum(r["max_drawdown"] for r in results) / len(results)
    bankruptcy_rate = sum(1 for r in results if r["final"] < 0.5) / len(results)
    
    return {
        "success_rate": success_rate,
        "avg_trades": avg_trades,
        "avg_final": avg_final,
        "avg_max_drawdown": avg_drawdown,
        "bankruptcy_rate": bankruptcy_rate,
    }


def main():
    print("=" * 60)
    print("Polymarket 凯利公式回测模拟")
    print(f"目标: ${INITIAL_CAPITAL} → ${TARGET_CAPITAL} (3倍)")
    print("=" * 60)
    print()
    
    for key, strategy in STRATEGIES.items():
        print(f"\n策略: {strategy['name']}")
        print("-" * 40)
        
        results = simulate_strategy(strategy, INITIAL_CAPITAL)
        analysis = analyze_results(results)
        
        print(f"成功率 (达到 $18): {analysis['success_rate']*100:.1f}%")
        print(f"平均交易次数: {analysis['avg_trades']:.1f}")
        print(f"平均最终资金: ${analysis['avg_final']:.2f}")
        print(f"平均最大回撤: {analysis['avg_max_drawdown']*100:.1f}%")
        print(f"破产率: {analysis['bankruptcy_rate']*100:.1f}%")
        
        # 计算预期完成时间
        if analysis['avg_trades'] > 0:
            weeks = analysis['avg_trades'] / 4  # 假设每周 4 笔
            print(f"预计完成时间: ~{weeks:.1f} 周")
    
    print("\n" + "=" * 60)
    print("结论:")
    print("- 1/4 Kelly 策略: 安全但慢，适合小资金初学者")
    print("- 1/2 Kelly 策略: 平衡风险和收益，推荐")
    print("- Full Kelly 策略: 高风险，破产率高，不推荐")
    print("=" * 60)


if __name__ == "__main__":
    random.seed(42)  # 可重复性
    main()
