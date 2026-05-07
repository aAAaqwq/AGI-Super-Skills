"""
Alpha101 — 因子IC/IR计算工具
计算各因子的Information Coefficient和Information Ratio
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path


def compute_ic(alpha_df: pd.DataFrame, forward_returns: pd.DataFrame, method='spearman') -> pd.Series:
    """
    计算因子IC（截面相关系数的时间序列均值）
    
    alpha_df: date x ticker DataFrame, 因子值
    forward_returns: date x ticker DataFrame, 未来N日收益率
    method: 'spearman' (rank IC) 或 'pearson'
    """
    if method == 'spearman':
        ic = alpha_df.rank(axis=1, pct=True).corrwith(forward_returns.rank(axis=1, pct=True), axis=1)
    else:
        ic = alpha_df.corrwith(forward_returns, axis=1)
    return ic


def compute_ir(ic_series: pd.Series) -> float:
    """IC均值 / IC标准差"""
    return ic_series.mean() / ic_series.std() if ic_series.std() > 0 else 0


def compute_turnover(alpha_df: pd.DataFrame) -> pd.Series:
    """因子换手率：相邻两期排名变化的绝对值均值"""
    ranked = alpha_df.rank(axis=1, pct=True)
    return ranked.diff().abs().mean(axis=1)


def screen_alphas(data: dict, forward_days: int = 5, ic_threshold: float = 0.03) -> pd.DataFrame:
    """
    批量筛选因子
    
    data: 包含因子值和价格数据的dict
    forward_days: 前瞻收益天数
    ic_threshold: IC绝对值阈值
    
    Returns: DataFrame with columns [alpha, mean_ic, ic_std, ir, mean_turnover, hit_rate]
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from alpha101 import compute_alphas
    
    alphas = compute_alphas(data)
    forward_returns = data['close'].pct_change(forward_days).shift(-forward_days)
    
    results = []
    for name, alpha_df in alphas.items():
        ic = compute_ic(alpha_df, forward_returns)
        ir = compute_ir(ic)
        mean_ic = ic.mean()
        turnover = compute_turnover(alpha_df)
        hit_rate = (ic > 0).mean()
        
        results.append({
            'alpha': name,
            'mean_ic': mean_ic,
            'ic_std': ic.std(),
            'ir': ir,
            'mean_turnover': turnover.mean(),
            'hit_rate': hit_rate,
            'abs_ic': abs(mean_ic)
        })
    
    df = pd.DataFrame(results).sort_values('abs_ic', ascending=False)
    return df[df['abs_ic'] >= ic_threshold]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Alpha101 IC Screening')
    parser.add_argument('--data', required=True, help='Path to pickle file with data dict')
    parser.add_argument('--forward-days', type=int, default=5)
    parser.add_argument('--ic-threshold', type=float, default=0.03)
    parser.add_argument('--output', default='ic_results.csv')
    args = parser.parse_args()
    
    data = pd.read_pickle(args.data)
    results = screen_alphas(data, args.forward_days, args.ic_threshold)
    results.to_csv(args.output, index=False)
    print(f"Screened {len(results)} alphas above IC={args.ic_threshold}")
    print(results[['alpha', 'mean_ic', 'ir', 'hit_rate']].to_string(index=False))
