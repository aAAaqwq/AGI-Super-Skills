"""
Alpha101 — 单因子回测
模拟多空组合（top decile long, bottom decile short）
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path


def backtest_single_alpha(
    alpha_df: pd.DataFrame,
    returns: pd.DataFrame,
    n_groups: int = 10,
    cost_bp: float = 10,
    holding_days: int = 1
) -> dict:
    """
    单因子分层回测
    
    alpha_df: date x ticker 因子值
    returns: date x ticker 日收益率
    n_groups: 分组数（默认10组）
    cost_bp: 单边交易成本（基点）
    holding_days: 持仓天数
    
    Returns: dict with performance metrics
    """
    # 截面分组
    ranked = alpha_df.rank(axis=1, pct=True)
    
    # 多空组合: top group long, bottom group short
    long_mask = ranked >= (1 - 1/n_groups)
    short_mask = ranked < (1/n_groups)
    
    # 日收益
    long_ret = returns.where(long_mask).mean(axis=1)
    short_ret = returns.where(short_mask).mean(axis=1)
    ls_ret = long_ret - short_ret
    
    # 换手率 → 扣成本
    long_pos = long_mask.astype(float)
    turnover = long_pos.diff().abs().sum(axis=1) / long_pos.sum(axis=1).replace(0, 1)
    cost = turnover * cost_bp / 10000
    
    ls_ret_net = ls_ret - cost
    
    # 统计
    cumulative = (1 + ls_ret_net).cumprod()
    
    return {
        'total_return': (1 + ls_ret_net).prod() - 1,
        'annual_return': ls_ret_net.mean() * 252,
        'sharpe': ls_ret_net.mean() / ls_ret_net.std() * np.sqrt(252) if ls_ret_net.std() > 0 else 0,
        'max_drawdown': ((cumulative / cumulative.cummax()) - 1).min(),
        'win_rate': (ls_ret_net > 0).mean(),
        'avg_daily_turnover': turnover.mean(),
        'long_return': (1 + long_ret).prod() - 1,
        'short_return': (1 - short_ret).prod() - 1,
        'daily_returns': ls_ret_net
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Alpha101 Single Alpha Backtest')
    parser.add_argument('--alpha', type=int, required=True, help='Alpha number (1-101)')
    parser.add_argument('--data', required=True, help='Path to pickle file with data dict')
    parser.add_argument('--n-groups', type=int, default=10)
    parser.add_argument('--cost-bp', type=float, default=10)
    args = parser.parse_args()
    
    data = pd.read_pickle(args.data)
    
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from alpha101 import compute_alphas
    
    alphas = compute_alphas(data)
    alpha_name = f'alpha{args.alpha:03d}'
    
    if alpha_name not in alphas:
        print(f"Alpha {alpha_name} not available (may require industry data)")
        sys.exit(1)
    
    result = backtest_single_alpha(
        alphas[alpha_name], data['returns'],
        n_groups=args.n_groups, cost_bp=args.cost_bp
    )
    
    print(f"\n{'='*40}")
    print(f"Alpha #{args.alpha} Backtest Results")
    print(f"{'='*40}")
    print(f"Total Return:  {result['total_return']:.2%}")
    print(f"Annual Return: {result['annual_return']:.2%}")
    print(f"Sharpe Ratio:  {result['sharpe']:.2f}")
    print(f"Max Drawdown:  {result['max_drawdown']:.2%}")
    print(f"Win Rate:      {result['win_rate']:.2%}")
    print(f"Avg Turnover:  {result['avg_daily_turnover']:.2%}")
    print(f"Long Return:   {result['long_return']:.2%}")
    print(f"Short Return:  {result['short_return']:.2%}")
