"""
core/filters.py — 三重过滤器实现
使用方式: from core.filters import FilterResult, apply_filters
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import numpy as np


class FilterLevel(Enum):
    PASS = "PASS"
    WARN = "WARN"
    BLOCK = "BLOCK"


@dataclass
class FilterResult:
    """单个过滤器的判定结果"""
    name: str
    level: FilterLevel
    reason: str = ""
    score_impact: int = 0


@dataclass
class CombinedFilterResult:
    """三重过滤器组合结果"""
    passed: bool
    confidence: str  # HIGH / MEDIUM / LOW
    total_score: int  # 0-6
    results: list[FilterResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocks: list[str] = field(default_factory=list)

    def __bool__(self):
        return self.passed


def trend_filter(bb_1h_slope: float, direction: str,
                 slope_max: float = 0.0003,
                 slope_loose: float = 0.0006) -> FilterResult:
    """
    🔴 过滤器一：趋势过滤
    检查 1h 中轨斜率是否配合交易方向
    """
    if direction == "LONG":
        if bb_1h_slope < -slope_loose:
            return FilterResult("趋势过滤", FilterLevel.BLOCK,
                              f"1h中轨下行({bb_1h_slope:.4%})，禁止做多", -2)
        elif bb_1h_slope > slope_max:
            return FilterResult("趋势过滤", FilterLevel.PASS,
                              f"1h中轨上行({bb_1h_slope:.4%})，顺风推多", +1)
        else:
            return FilterResult("趋势过滤", FilterLevel.PASS,
                              f"1h中轨走平({bb_1h_slope:.4%})")
    else:  # SHORT
        if bb_1h_slope > slope_loose:
            return FilterResult("趋势过滤", FilterLevel.BLOCK,
                              f"1h中轨上行({bb_1h_slope:.4%})，禁止做空", -2)
        elif bb_1h_slope < -slope_max:
            return FilterResult("趋势过滤", FilterLevel.PASS,
                              f"1h中轨下行({bb_1h_slope:.4%})，顺风推空", +1)
        else:
            return FilterResult("趋势过滤", FilterLevel.PASS,
                              f"1h中轨走平({bb_1h_slope:.4%})")


def rsi_filter(rsi_val: float, direction: str,
               rsi_long_max: float = 55,
               rsi_short_min: float = 45) -> FilterResult:
    """
    🟡 过滤器二：RSI 确认
    """
    if direction == "LONG":
        if 30 < rsi_val < 45:
            return FilterResult("RSI确认", FilterLevel.PASS,
                              f"RSI {rsi_val:.0f} 超卖区域，反弹概率大", +1)
        elif rsi_val > rsi_long_max:
            return FilterResult("RSI确认", FilterLevel.WARN,
                              f"RSI {rsi_val:.0f} 偏高，买入风险", -1)
        else:
            return FilterResult("RSI确认", FilterLevel.PASS,
                              f"RSI {rsi_val:.0f} 中性")
    else:  # SHORT
        if 55 < rsi_val < 70:
            return FilterResult("RSI确认", FilterLevel.PASS,
                              f"RSI {rsi_val:.0f} 超买区域，回落概率大", +1)
        elif rsi_val < rsi_short_min:
            return FilterResult("RSI确认", FilterLevel.WARN,
                              f"RSI {rsi_val:.0f} 偏低，做空风险", -1)
        else:
            return FilterResult("RSI确认", FilterLevel.PASS,
                              f"RSI {rsi_val:.0f} 中性")


def sweet_spot_filter(bb_width: float,
                      sweet_min: float = 0.008,
                      sweet_max: float = 0.025) -> FilterResult:
    """
    🟢 过滤器三：BB 甜区
    """
    if bb_width < sweet_min:
        return FilterResult("BB甜区", FilterLevel.BLOCK,
                          f"宽度 {bb_width:.2%} < {sweet_min:.1%}，空间不足", -2)
    elif bb_width > sweet_max:
        return FilterResult("BB甜区", FilterLevel.WARN,
                          f"宽度 {bb_width:.2%} > {sweet_max:.1%}，非真横盘", -1)
    else:
        return FilterResult("BB甜区", FilterLevel.PASS,
                          f"宽度 {bb_width:.2%}，甜区 ✅")


def apply_filters(bb_width: float, rsi_val: float,
                  bb_1h_slope: float, direction: str,
                  config: Optional[dict] = None) -> CombinedFilterResult:
    """
    运行三重过滤器，返回组合结果

    Args:
        bb_width: 15m BB 宽度
        rsi_val: RSI(14) 值
        bb_1h_slope: 1h 中轨斜率
        direction: 'LONG' / 'SHORT'
        config: 可选配置覆盖

    Returns:
        CombinedFilterResult 包含通过/置信度/评分/警告列表
    """
    cfg = config or {}
    results = []

    # 过滤器一：趋势
    tf = trend_filter(bb_1h_slope, direction,
                      cfg.get("trend_slope_max", 0.0003),
                      cfg.get("trend_slope_loose", 0.0006))
    results.append(tf)

    # 过滤器二：RSI
    rf = rsi_filter(rsi_val, direction,
                    cfg.get("rsi_long_max", 55),
                    cfg.get("rsi_short_min", 45))
    results.append(rf)

    # 过滤器三：甜区
    sf = sweet_spot_filter(bb_width,
                           cfg.get("sweet_min", 0.008),
                           cfg.get("sweet_max", 0.025))
    results.append(sf)

    # 汇总
    blocks = [r for r in results if r.level == FilterLevel.BLOCK]
    warnings = [r.reason for r in results if r.level in (FilterLevel.WARN, FilterLevel.BLOCK)]
    total_score = sum(r.score_impact for r in results)
    has_block = any(r.level == FilterLevel.BLOCK for r in results)

    # 置信度
    if not has_block and total_score >= 3:
        conf = "HIGH"
    elif not has_block and total_score >= 1:
        conf = "MEDIUM"
    else:
        conf = "LOW"

    return CombinedFilterResult(
        passed=not has_block,
        confidence=conf,
        total_score=total_score,
        results=results,
        warnings=warnings,
        blocks=[r.reason for r in blocks],
    )
