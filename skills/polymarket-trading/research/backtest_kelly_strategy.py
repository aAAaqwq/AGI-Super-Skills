#!/usr/bin/env python3
"""
Polymarket Kelly Criterion Backtest Simulator
Theme C: 资金管理与凯利公式

基于研究结果：
- 1/8 Kelly 最保守（$4000→$6210，40天，75%胜率）
- Kelly 公式: f* = (b × p - q) / b
- 小资金策略：高胜率 + 小额复利
"""

import random
import math
from datetime import datetime

def kelly_fraction(odds, win_prob):
    """计算 Kelly 下注比例"""
    q = 1 - win_prob
    f = (odds * win_prob - q) / odds
    return max(0, f)  # 负数表示不下注

def simulate_trade(bankroll, kelly_pct, win_prob, odds, kelly_fraction_divisor=8):
    """模拟一次交易"""
    # 使用分数 Kelly
    bet_fraction = kelly_pct / kelly_fraction_divisor
    bet_amount = bankroll * bet_fraction
    
    # 模拟结果
    if random.random() < win_prob:
        # 赢
        profit = bet_amount * odds
        new_bankroll = bankroll + profit
        return new_bankroll, True, profit
    else:
        # 输
        new_bankroll = bankroll - bet_amount
        return new_bankroll, False, -bet_amount

def run_backtest(
    initial_bankroll=6.0,
    target_bankroll=18.0,
    num_trades=100,
    win_prob=0.70,
    odds=0.86,  # 典型预测市场赔率 (0.58 股价 → 0.42 利润/0.58 = 0.72赔率)
    kelly_fraction_divisor=8,
    min_bet=0.10,  # Polymarket 最小下注
    simulations=1000
):
    """
    运行回测模拟
    
    Args:
        initial_bankroll: 初始资金 ($6)
        target_bankroll: 目标资金 ($18)
        num_trades: 模拟交易次数
        win_prob: 胜率
        odds: 赔率 (利润/成本)
        kelly_fraction_divisor: Kelly 分数 (8 = 1/8 Kelly)
        min_bet: 最小下注金额
        simulations: 模拟次数
    """
    
    # 计算 Kelly 比例
    kelly_full = kelly_fraction(odds, win_prob)
    kelly_actual = kelly_full / kelly_fraction_divisor
    
    results = {
        'success_count': 0,
        'avg_final_bankroll': 0,
        'avg_trades_to_target': 0,
        'max_bankroll': 0,
        'min_bankroll': float('inf'),
        'ruin_count': 0,  # 资金归零次数
        'all_simulations': []
    }
    
    for sim in range(simulations):
        bankroll = initial_bankroll
        trades = 0
        trades_to_target = None
        max_b = bankroll
        min_b = bankroll
        
        for i in range(num_trades):
            if bankroll < min_bet:
                # 资金不足，停止
                break
                
            bankroll, won, pnl = simulate_trade(
                bankroll, kelly_full, win_prob, odds, kelly_fraction_divisor
            )
            trades += 1
            
            max_b = max(max_b, bankroll)
            min_b = min(min_b, bankroll)
            
            if bankroll >= target_bankroll and trades_to_target is None:
                trades_to_target = trades
                
            if bankroll <= 0.01:  # 近乎归零
                break
        
        results['all_simulations'].append({
            'final_bankroll': bankroll,
            'trades': trades,
            'trades_to_target': trades_to_target,
            'max_bankroll': max_b,
            'min_bankroll': min_b,
            'reached_target': bankroll >= target_bankroll
        })
        
        if bankroll >= target_bankroll:
            results['success_count'] += 1
        if bankroll < min_bet:
            results['ruin_count'] += 1
        results['avg_final_bankroll'] += bankroll
        if trades_to_target:
            results['avg_trades_to_target'] += trades_to_target
        results['max_bankroll'] = max(results['max_bankroll'], max_b)
        results['min_bankroll'] = min(results['min_bankroll'], min_b)
    
    results['avg_final_bankroll'] /= simulations
    if results['success_count'] > 0:
        results['avg_trades_to_target'] /= results['success_count']
    
    return results, {
        'kelly_full': kelly_full,
        'kelly_actual': kelly_actual,
        'bet_per_trade_pct': kelly_actual * 100,
        'bet_per_trade_dollars': initial_bankroll * kelly_actual
    }

def main():
    print("=" * 60)
    print("Polymarket Kelly Criterion Backtest")
    print("Theme C: 资金管理与凯利公式")
    print("=" * 60)
    
    # 场景 1: 保守策略 (70% 胜率, 1/8 Kelly)
    print("\n📊 场景 1: 保守策略 (70%胜率, 1/8 Kelly)")
    print("-" * 50)
    results1, params1 = run_backtest(
        initial_bankroll=6.0,
        target_bankroll=18.0,
        win_prob=0.70,
        odds=0.72,  # 约 58% 股价
        kelly_fraction_divisor=8,
        num_trades=100,
        simulations=1000
    )
    print(f"Kelly 完整值: {params1['kelly_full']*100:.1f}%")
    print(f"1/8 Kelly: {params1['kelly_actual']*100:.2f}%")
    print(f"每笔下注: ${params1['bet_per_trade_dollars']:.2f}")
    print(f"达到目标($18)概率: {results1['success_count']/10:.1f}%")
    print(f"平均最终资金: ${results1['avg_final_bankroll']:.2f}")
    print(f"达到目标平均交易数: {results1['avg_trades_to_target']:.0f}")
    print(f"资金归零次数: {results1['ruin_count']}/1000")
    
    # 场景 2: 中等策略 (65% 胜率, 1/4 Kelly)
    print("\n📊 场景 2: 中等策略 (65%胜率, 1/4 Kelly)")
    print("-" * 50)
    results2, params2 = run_backtest(
        initial_bankroll=6.0,
        target_bankroll=18.0,
        win_prob=0.65,
        odds=0.72,
        kelly_fraction_divisor=4,
        num_trades=100,
        simulations=1000
    )
    print(f"Kelly 完整值: {params2['kelly_full']*100:.1f}%")
    print(f"1/4 Kelly: {params2['kelly_actual']*100:.2f}%")
    print(f"每笔下注: ${params2['bet_per_trade_dollars']:.2f}")
    print(f"达到目标($18)概率: {results2['success_count']/10:.1f}%")
    print(f"平均最终资金: ${results2['avg_final_bankroll']:.2f}")
    print(f"达到目标平均交易数: {results2['avg_trades_to_target']:.0f}")
    print(f"资金归零次数: {results2['ruin_count']}/1000")
    
    # 场景 3: 高胜率策略 (80% 胜率, 1/8 Kelly)
    print("\n📊 场景 3: 高胜率策略 (80%胜率, 1/8 Kelly)")
    print("-" * 50)
    results3, params3 = run_backtest(
        initial_bankroll=6.0,
        target_bankroll=18.0,
        win_prob=0.80,
        odds=0.25,  # 约 80% 股价，低赔率但高胜率
        kelly_fraction_divisor=8,
        num_trades=100,
        simulations=1000
    )
    print(f"Kelly 完整值: {params3['kelly_full']*100:.1f}%")
    print(f"1/8 Kelly: {params3['kelly_actual']*100:.2f}%")
    print(f"每笔下注: ${params3['bet_per_trade_dollars']:.2f}")
    print(f"达到目标($18)概率: {results3['success_count']/10:.1f}%")
    print(f"平均最终资金: ${results3['avg_final_bankroll']:.2f}")
    print(f"达到目标平均交易数: {results3['avg_trades_to_target']:.0f}")
    print(f"资金归零次数: {results3['ruin_count']}/1000")
    
    # 场景 4: Medium 文章实战参数 (75% 胜率, 1/8 Kelly)
    print("\n📊 场景 4: Medium 实战参数 (75%胜率, 1/8 Kelly)")
    print("-" * 50)
    results4, params4 = run_backtest(
        initial_bankroll=6.0,
        target_bankroll=18.0,
        win_prob=0.75,
        odds=0.43,  # 约 70% 股价
        kelly_fraction_divisor=8,
        num_trades=100,
        simulations=1000
    )
    print(f"Kelly 完整值: {params4['kelly_full']*100:.1f}%")
    print(f"1/8 Kelly: {params4['kelly_actual']*100:.2f}%")
    print(f"每笔下注: ${params4['bet_per_trade_dollars']:.2f}")
    print(f"达到目标($18)概率: {results4['success_count']/10:.1f}%")
    print(f"平均最终资金: ${results4['avg_final_bankroll']:.2f}")
    print(f"达到目标平均交易数: {results4['avg_trades_to_target']:.0f}")
    print(f"资金归零次数: {results4['ruin_count']}/1000")
    
    print("\n" + "=" * 60)
    print("📈 结论")
    print("=" * 60)
    best_scenario = max([
        (results1['success_count'], "场景1(70%胜率,1/8Kelly)"),
        (results2['success_count'], "场景2(65%胜率,1/4Kelly)"),
        (results3['success_count'], "场景3(80%胜率,1/8Kelly)"),
        (results4['success_count'], "场景4(75%胜率,1/8Kelly)")
    ], key=lambda x: x[0])
    print(f"最佳策略: {best_scenario[1]}")
    print(f"达到目标概率: {best_scenario[0]/10:.1f}%")

if __name__ == "__main__":
    random.seed(42)  # 可重复性
    main()
