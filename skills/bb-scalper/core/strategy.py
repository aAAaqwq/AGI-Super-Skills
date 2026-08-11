"""
core/strategy.py — BB 双向套利策略核心逻辑
使用方式:
    from core.strategy import Strategy, Signal
    s = Strategy(config)
    signals = s.analyze("NEARUSDT")
"""
from dataclasses import dataclass
from typing import Optional
import numpy as np


@dataclass
class BBResult:
    """布林带计算结果"""
    middle: float
    upper: float
    lower: float
    width: float       # (upper-lower)/middle
    slope: float       # 中轨斜率
    pct_b: float       # 价格在 BB 中的位置 (0=下轨, 1=上轨)
    std: float


@dataclass
class Signal:
    """交易信号"""
    symbol: str
    direction: str           # LONG / SHORT / PENDING_LONG / PENDING_SHORT
    price: float
    market_type: str         # RANGING_TIGHT / RANGING_LOOSE / TRENDING_UP / TRENDING_DOWN / VOLATILE
    bb_width: float
    bb_pct_b: float
    rsi: float
    trend_slope: float       # 1h 中轨斜率
    entry_low: float         # 入场区下限
    entry_high: float        # 入场区上限
    stop_loss: float
    take_profit: float
    risk_pct: float          # 价格风险 %
    reward_pct: float        # 价格收益 %
    rr_ratio: float
    position_usd: float      # 建议名义仓位
    leverage: int
    confidence: str          # HIGH / MEDIUM / LOW
    filter_score: int        # 三重过滤得分
    warnings: list
    blocks: list


class Strategy:
    """BB 双向套利策略"""

    def __init__(self, config: dict):
        self.cfg = config

    # ── 指标计算 ──
    @staticmethod
    def calc_bollinger(closes: np.ndarray, period: int = 20, std_mult: float = 2.0) -> Optional[BBResult]:
        if len(closes) < period:
            return None
        sma = np.mean(closes[-period:])
        std = np.std(closes[-period:], ddof=1)
        upper, lower = sma + std_mult * std, sma - std_mult * std
        width = (upper - lower) / sma
        slope = 0.0
        if len(closes) >= 8:
            y = closes[-8:]
            slope = np.polyfit(np.arange(len(y)), y, 1)[0] / sma
        pct_b = (closes[-1] - lower) / (upper - lower) if (upper - lower) > 0 else 0.5
        return BBResult(middle=sma, upper=upper, lower=lower,
                        width=width, slope=slope, pct_b=pct_b, std=std)

    @staticmethod
    def calc_rsi(closes: np.ndarray, period: int = 14) -> Optional[float]:
        if len(closes) < period + 1:
            return None
        deltas = np.diff(closes[-period-1:])
        gains = np.maximum(deltas, 0)
        losses = np.maximum(-deltas, 0)
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        return 100.0 - 100.0 / (1.0 + avg_gain / avg_loss) if avg_loss > 0 else 100.0

    # ── 市场分类 ──
    def classify_market(self, bb: BBResult, rsi: float,
                        bb_1h: Optional[BBResult] = None) -> str:
        """RANGING_TIGHT | RANGING_LOOSE | TRENDING_UP | TRENDING_DOWN | VOLATILE"""
        w, s, r = bb.width, bb.slope, rsi
        trend = bb_1h.slope if bb_1h else s
        sq = self.cfg["bb"]["squeeze_max"]
        sl = self.cfg["bb"]["squeeze_loose"]
        ts = self.cfg["filters"]["trend_slope_max"]
        tl = self.cfg["filters"]["trend_slope_loose"]

        if w < sq:
            if abs(trend) < ts and 35 < r < 65:  return "RANGING_TIGHT"
            elif trend > tl:                       return "TRENDING_UP"
            elif trend < -tl:                      return "TRENDING_DOWN"
            else:                                  return "RANGING_TIGHT"
        elif w < sl:
            if abs(trend) < tl and 35 < r < 65:   return "RANGING_LOOSE"
            elif trend > tl:                       return "TRENDING_UP"
            elif trend < -tl:                      return "TRENDING_DOWN"
            else:                                  return "RANGING_LOOSE"
        return "VOLATILE"

    # ── 信号生成 ──
    def generate_signal(self, symbol: str, bb: BBResult, rsi: float,
                        bb_1h: Optional[BBResult], market: str) -> Signal:
        """基于参数生成长/空信号"""
        direction = "LONG" if bb.pct_b < 0.15 else "SHORT"
        lower, upper = bb.lower, bb.upper
        et = self.cfg["trade"]["entry_threshold"]
        sb = self.cfg["trade"]["stop_buffer"]

        if direction == "LONG":
            entry_low, entry_high = lower, lower * (1 + et)
            sl_price = lower * (1 - sb)
            tp_price = upper
            risk = (entry_high - sl_price) / entry_high
            reward = (tp_price - entry_high) / entry_high
        else:
            entry_low, entry_high = upper * (1 - et), upper
            sl_price = upper * (1 + sb)
            tp_price = lower
            risk = (sl_price - entry_low) / entry_low
            reward = (entry_low - tp_price) / entry_low

        rr = reward / risk if risk > 0 else 0

        # 仓位
        cap = self.cfg["risk"]["simulated_capital"]
        rpt = self.cfg["risk"]["risk_per_trade"]
        max_pos = self.cfg["risk"]["max_position_usd"]
        pos = min(cap * rpt / risk, max_pos) if risk > 0 else 0

        trend_slope = bb_1h.slope if bb_1h else 0.0

        return Signal(
            symbol=symbol, direction=direction, price=bb.middle,  # placeholder
            market_type=market, bb_width=bb.width, bb_pct_b=bb.pct_b,
            rsi=rsi, trend_slope=trend_slope,
            entry_low=entry_low, entry_high=entry_high,
            stop_loss=sl_price, take_profit=tp_price,
            risk_pct=risk, reward_pct=reward, rr_ratio=rr,
            position_usd=pos, leverage=self.cfg["trade"]["leverage"],
            confidence="LOW", filter_score=0, warnings=[], blocks=[],
        )
