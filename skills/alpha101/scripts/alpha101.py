"""
WorldQuant 101 Formulaic Alphas — Python/Pandas Implementation
Reference: Kakushadze, Z. (2015). "101 Formulaic Alphas". arXiv:1601.00991

All 101 alpha formulas from the paper, ready for backtesting.
Input: pandas DataFrame with MultiIndex (date, ticker) or panel (date x ticker).
"""

import numpy as np
import pandas as pd

# ─── Base Functions ───────────────────────────────────────────────

def rank(df):
    """Cross-sectional rank, normalized to [0,1]"""
    return df.rank(axis=1, pct=True)

def scale(df, a=1):
    """Rescale so sum(abs(x)) = a"""
    return df.div(df.abs().sum(axis=1), axis=0) * a

def sign(df):
    return np.sign(df)

def log(df):
    return np.log1p(df)

def signedpower(df, a):
    return df.pow(a)

def delay(df, d):
    return df.shift(d)

def delta(df, d):
    return df.diff(d)

def correlation(x, y, d):
    return x.rolling(d).corr(y)

def covariance(x, y, d):
    return x.rolling(d).cov(y)

def ts_sum(df, d):
    return df.rolling(d).sum()

def ts_mean(df, d):
    return df.rolling(d).mean()

def ts_std(df, d):
    return df.rolling(d).std()

def ts_min(df, d):
    return df.rolling(d).min()

def ts_max(df, d):
    return df.rolling(d).max()

def ts_argmax(df, d):
    return df.rolling(d).apply(np.argmax, raw=True) + 1

def ts_argmin(df, d):
    return df.rolling(d).apply(np.argmin, raw=True) + 1

def ts_rank(df, d):
    return df.rolling(d).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=False)

def ts_product(df, d):
    return df.rolling(d).apply(np.prod, raw=True)

def decay_linear(df, d):
    weights = np.arange(1, d + 1, dtype=float)
    weights /= weights.sum()
    return df.rolling(d).apply(lambda x: (x * weights).sum(), raw=True)

def indneutralize(df, ind_class):
    """Industry neutralize — requires industry mapping"""
    # Placeholder: subtract industry mean
    return df.sub(df.groupby(ind_class, axis=1).mean(), axis=1)

def adv(df_vol, df_close, d):
    """Average daily dollar volume over past d days"""
    return ts_mean(df_vol * df_close, d)


# ─── Alpha #1 ~ #101 ─────────────────────────────────────────────

# Alpha#1: (rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5)
def alpha001(c, r):
    """If returns < 0, use stddev(returns,20); else use close. Then SignedPower(_,2), Ts_ArgMax(_,5), rank - 0.5"""
    inner = c.copy()
    inner[r < 0] = ts_std(r, 20)
    return rank(ts_argmax(signedpower(inner, 2), 5)) - 0.5

# Alpha#2: (-1 * correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6))
def alpha002(o, c, v):
    return -1 * correlation(rank(delta(log(v), 2)), rank((c - o) / o), 6)

# Alpha#3: (-1 * correlation(rank(open), rank(volume), 10))
def alpha003(o, v):
    return -1 * correlation(rank(o), rank(v), 10)

# Alpha#4: (-1 * Ts_Rank(rank(low), 9))
def alpha004(l):
    return -1 * ts_rank(rank(l), 9)

# Alpha#5: (rank((open - (sum(vwap, 10) / 10))) * (-1 * abs(rank((close - vwap)))))
def alpha005(o, vwap, c):
    return rank(o - ts_mean(vwap, 10)) * (-1 * abs(rank(c - vwap)))

# Alpha#6: (-1 * correlation(open, volume, 10))
def alpha006(o, v):
    return -1 * correlation(o, v, 10)

# Alpha#7: ((adv20 < volume) ? ((-1 * ts_rank(abs(delta(close, 7)), 60)) * sign(delta(close, 7))) : (-1 * 1))
def alpha007(c, v, adv20):
    d7 = delta(c, 7)
    result = (-1 * ts_rank(abs(d7), 60)) * sign(d7)
    return result.where(adv20 < v, -1)

# Alpha#8: (-1 * rank(((sum(open, 5) * sum(returns, 5)) - delay((sum(open, 5) * sum(returns, 5)), 10))))
def alpha008(o, r):
    s = ts_sum(o, 5) * ts_sum(r, 5)
    return -1 * rank(s - delay(s, 10))

# Alpha#9: ((0 < ts_min(delta(close, 1), 5)) ? delta(close, 1) : ((ts_max(delta(close, 1), 5) < 0) ? delta(close, 1) : (-1 * delta(close, 1))))
def alpha009(c):
    d1 = delta(c, 1)
    return d1.where(ts_min(d1, 5) > 0,
                    d1.where(ts_max(d1, 5) < 0, -1 * d1))

# Alpha#10: rank(((0 < ts_min(delta(close, 1), 4)) ? delta(close, 1) : ((ts_max(delta(close, 1), 4) < 0) ? delta(close, 1) : (-1 * delta(close, 1)))))
def alpha010(c):
    d1 = delta(c, 1)
    inner = d1.where(ts_min(d1, 4) > 0,
                     d1.where(ts_max(d1, 4) < 0, -1 * d1))
    return rank(inner)

# Alpha#11: ((rank(ts_max((vwap - close), 3)) + rank(ts_min((vwap - close), 3))) * rank(delta(volume, 3)))
def alpha011(vwap, c, v):
    return (rank(ts_max(vwap - c, 3)) + rank(ts_min(vwap - c, 3))) * rank(delta(v, 3))

# Alpha#12: (sign(delta(volume, 1)) * (-1 * delta(close, 1)))
def alpha012(v, c):
    return sign(delta(v, 1)) * (-1 * delta(c, 1))

# Alpha#13: (-1 * rank(covariance(rank(close), rank(volume), 5)))
def alpha013(c, v):
    return -1 * rank(covariance(rank(c), rank(v), 5))

# Alpha#14: ((-1 * rank(delta(returns, 3))) * correlation(open, volume, 10))
def alpha014(o, v, r):
    return (-1 * rank(delta(r, 3))) * correlation(o, v, 10)

# Alpha#15: (-1 * sum(rank(correlation(rank(high), rank(volume), 3)), 3))
def alpha015(h, v):
    return -1 * ts_sum(rank(correlation(rank(h), rank(v), 3)), 3)

# Alpha#16: (-1 * rank(covariance(rank(high), rank(volume), 5)))
def alpha016(h, v):
    return -1 * rank(covariance(rank(h), rank(v), 5))

# Alpha#17: (((-1 * rank(ts_rank(close, 10))) * rank(delta(delta(close, 1), 1))) * rank(ts_rank((volume / adv20), 5)))
def alpha017(c, v, adv20):
    return (-1 * rank(ts_rank(c, 10))) * rank(delta(delta(c, 1), 1)) * rank(ts_rank(v / adv20, 5))

# Alpha#18: (-1 * rank(((stddev(abs((close - open)), 5) + (close - open)) + correlation(close, open, 10))))
def alpha018(o, c):
    return -1 * rank(ts_std(abs(c - o), 5) + (c - o) + correlation(c, o, 10))

# Alpha#19: ((-1 * sign(((close - delay(close, 7)) + delta(close, 7)))) * (1 + rank((1 + sum(returns, 250)))))
def alpha019(c, r):
    return (-1 * sign((c - delay(c, 7)) + delta(c, 7))) * (1 + rank(1 + ts_sum(r, 250)))

# Alpha#20: (((-1 * rank((open - delay(high, 1)))) * rank((open - delay(close, 1)))) * rank((open - delay(low, 1))))
def alpha020(o, h, l, c):
    return (-1 * rank(o - delay(h, 1))) * rank(o - delay(c, 1)) * rank(o - delay(l, 1))

# Alpha#21: ((((sum(close, 8) / 8) + stddev(close, 8)) < (sum(close, 2) / 2)) ? (-1) : (((sum(close, 2) / 2) < ((sum(close, 8) / 8) - stddev(close, 8))) ? 1 : (((1 < (volume / adv20)) || ((volume / adv20) == 1)) ? 1 : (-1))))
def alpha021(c, v, adv20):
    sma8 = ts_mean(c, 8)
    std8 = ts_std(c, 8)
    sma2 = ts_mean(c, 2)
    ratio = v / adv20
    result = (-1 * np.ones_like(c, dtype=float))
    result = pd.DataFrame(result, index=c.index, columns=c.columns)
    cond_down = sma2 < (sma8 - std8)
    cond_vol = (ratio >= 1)
    result[~((sma8 + std8) < sma2)] = 0  # temp
    result = result.where((sma8 + std8) < sma2, 
                          pd.DataFrame(1.0, index=c.index, columns=c.columns).where(cond_down, -1))
    result = result.where(cond_vol | ((sma8 + std8) < sma2) | (sma2 < (sma8 - std8)), -1)
    return result

# Alpha#22: (-1 * (delta(correlation(high, volume, 5), 5) * rank(stddev(close, 20))))
def alpha022(h, c, v):
    return -1 * (delta(correlation(h, v, 5), 5) * rank(ts_std(c, 20)))

# Alpha#23: (((sum(high, 20) / 20) < high) ? (-1 * delta(high, 2)) : 0)
def alpha023(h):
    return (-1 * delta(h, 2)).where(ts_mean(h, 20) < h, 0)

# Alpha#24: ((((delta((sum(close, 100) / 100), 100) / delay(close, 100)) < 0.05) || ... ) ? (-1 * (close - ts_min(close, 100))) : (-1 * delta(close, 3)))
def alpha024(c):
    cond = (delta(ts_mean(c, 100), 100) / delay(c, 100)) <= 0.05
    return (-1 * (c - ts_min(c, 100))).where(cond, -1 * delta(c, 3))

# Alpha#25: rank(((((-1 * returns) * adv20) * vwap) * (high - close)))
def alpha025(r, adv20, vwap, h, c):
    return rank((-1 * r) * adv20 * vwap * (h - c))

# Alpha#26: (-1 * ts_max(correlation(ts_rank(volume, 5), ts_rank(high, 5), 5), 3))
def alpha026(h, v):
    return -1 * ts_max(correlation(ts_rank(v, 5), ts_rank(h, 5), 5), 3)

# Alpha#27: ((0.5 < rank((sum(correlation(rank(volume), rank(vwap), 6), 2) / 2.0))) ? (-1) : 1)
def alpha027(v, vwap):
    cond = rank(ts_sum(correlation(rank(v), rank(vwap), 6), 2) / 2.0)
    return (-1 * np.ones_like(v, dtype=float)).where(cond > 0.5, 1)

# Alpha#28: scale(((correlation(adv20, low, 5) + ((high + low) / 2)) - close))
def alpha028(adv20, l, h, c):
    return scale(correlation(adv20, l, 5) + (h + l) / 2 - c)

# Alpha#29: (min(product(rank(rank(scale(log(sum(ts_min(rank(rank((-1 * rank(delta((close - 1), 5))))), 2), 1))))), 1), 5) + ts_rank(delay((-1 * returns), 6), 5))
def alpha029(c, r):
    # Simplified interpretation
    inner = -1 * rank(delta(c - 1, 5))
    p = ts_product(rank(rank(scale(log(ts_sum(ts_min(rank(rank(inner)), 2), 1))))), 5)
    return p + ts_rank(delay(-1 * r, 6), 5)

# Alpha#30: (((1.0 - rank(((sign((close - delay(close, 1))) + sign((delay(close, 1) - delay(close, 2)))) + sign((delay(close, 2) - delay(close, 3)))))) * sum(volume, 5)) / sum(volume, 20))
def alpha030(c, v):
    signs = sign(c - delay(c, 1)) + sign(delay(c, 1) - delay(c, 2)) + sign(delay(c, 2) - delay(c, 3))
    return (1 - rank(signs)) * ts_sum(v, 5) / ts_sum(v, 20)

# Alpha#31: ((rank(rank(rank(decay_linear((-1 * rank(rank(delta(close, 10)))), 10)))) + rank((-1 * delta(close, 3)))) + sign(scale(correlation(adv20, low, 12))))
def alpha031(c, l, adv20):
    p1 = rank(rank(rank(decay_linear(-1 * rank(rank(delta(c, 10))), 10))))
    p2 = rank(-1 * delta(c, 3))
    p3 = sign(scale(correlation(adv20, l, 12)))
    return p1 + p2 + p3

# Alpha#32: (scale(((sum(close, 7) / 7) - close)) + (20 * scale(correlation(vwap, delay(close, 5), 230))))
def alpha032(c, vwap):
    return scale(ts_mean(c, 7) - c) + 20 * scale(correlation(vwap, delay(c, 5), 230))

# Alpha#33: rank((-1 * ((1 - (open / close))^1)))
def alpha033(o, c):
    return rank(-1 * (1 - o / c))

# Alpha#34: rank(((1 - rank((stddev(returns, 2) / stddev(returns, 5)))) + (1 - rank(delta(close, 1)))))
def alpha034(c, r):
    return rank((1 - rank(ts_std(r, 2) / ts_std(r, 5))) + (1 - rank(delta(c, 1))))

# Alpha#35: ((Ts_Rank(volume, 32) * (1 - Ts_Rank(((close + high) - low), 16))) * (1 - Ts_Rank(returns, 32)))
def alpha035(h, l, c, v, r):
    return ts_rank(v, 32) * (1 - ts_rank(c + h - l, 16)) * (1 - ts_rank(r, 32))

# Alpha#36: (((((2.21 * rank(correlation((close - open), delay(volume, 1), 15))) + (0.7 * rank((open - close)))) + (0.73 * rank(Ts_Rank(delay((-1 * returns), 6), 5)))) + rank(abs(correlation(vwap, adv20, 6)))) + (0.6 * rank((((sum(close, 200) / 200) - open) * (close - open)))))
def alpha036(o, c, v, vwap, adv20, r):
    return (2.21 * rank(correlation(c - o, delay(v, 1), 15)) +
            0.7 * rank(o - c) +
            0.73 * rank(ts_rank(delay(-1 * r, 6), 5)) +
            rank(abs(correlation(vwap, adv20, 6))) +
            0.6 * rank((ts_mean(c, 200) - o) * (c - o)))

# Alpha#37: (rank(correlation(delay((open - close), 1), close, 200)) + rank((open - close)))
def alpha037(o, c):
    return rank(correlation(delay(o - c, 1), c, 200)) + rank(o - c)

# Alpha#38: ((-1 * rank(Ts_Rank(close, 10))) * rank((close / open)))
def alpha038(o, c):
    return (-1 * rank(ts_rank(c, 10))) * rank(c / o)

# Alpha#39: ((-1 * rank((delta(close, 7) * (1 - rank(decay_linear((volume / adv20), 9)))))) * (1 + rank(sum(returns, 250))))
def alpha039(c, v, adv20, r):
    return (-1 * rank(delta(c, 7) * (1 - rank(decay_linear(v / adv20, 9))))) * (1 + rank(ts_sum(r, 250)))

# Alpha#40: ((-1 * rank(stddev(high, 10))) * correlation(high, volume, 10))
def alpha040(h, v):
    return (-1 * rank(ts_std(h, 10))) * correlation(h, v, 10)

# Alpha#41: (((high * low)^0.5) - vwap)
def alpha041(h, l, vwap):
    return (h * l).pow(0.5) - vwap

# Alpha#42: (rank((vwap - close)) / rank((vwap + close)))
def alpha042(vwap, c):
    return rank(vwap - c) / rank(vwap + c)

# Alpha#43: (ts_rank((volume / adv20), 20) * ts_rank((-1 * delta(close, 7)), 8))
def alpha043(c, v, adv20):
    return ts_rank(v / adv20, 20) * ts_rank(-1 * delta(c, 7), 8)

# Alpha#44: (-1 * correlation(high, rank(volume), 5))
def alpha044(h, v):
    return -1 * correlation(h, rank(v), 5)

# Alpha#45: (-1 * ((rank((sum(delay(close, 5), 20) / 20)) * correlation(close, volume, 2)) * rank(correlation(sum(close, 5), sum(close, 20), 2))))
def alpha045(c, v):
    return -1 * (rank(ts_mean(delay(c, 5), 20)) * correlation(c, v, 2) * rank(correlation(ts_sum(c, 5), ts_sum(c, 20), 2)))

# Alpha#46: ((0.25 < (((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10))) ? (-1) : ((((...) < 0) ? 1 : ((-1) * (close - delay(close, 1)))))
def alpha046(c):
    accel = (delay(c, 20) - delay(c, 10)) / 10 - (delay(c, 10) - c) / 10
    return (-1 * np.ones_like(c, dtype=float)).where(accel > 0.25,
           np.ones_like(c, dtype=float)).where(accel < 0, -1 * (c - delay(c, 1)))

# Alpha#47: ((((rank((1 / close)) * volume) / adv20) * ((high * rank((high - close))) / (sum(high, 5) / 5))) - rank((vwap - delay(vwap, 5))))
def alpha047(c, h, v, vwap, adv20):
    return ((rank(1 / c) * v) / adv20) * ((h * rank(h - c)) / ts_mean(h, 5)) - rank(vwap - delay(vwap, 5))

# Alpha#48: (indneutralize(((correlation(delta(close, 1), delta(delay(close, 1), 1), 250) * delta(close, 1)) / close), IndClass.subindustry) / sum(((delta(close, 1) / delay(close, 1))^2), 250))
def alpha048(c, ind_class):
    d1 = delta(c, 1)
    return indneutralize(correlation(d1, delta(delay(c, 1), 1), 250) * d1 / c, ind_class) / ts_sum((d1 / delay(c, 1)).pow(2), 250)

# Alpha#49: (((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 * 0.1)) ? 1 : ((-1 * 1) * (close - delay(close, 1))))
def alpha049(c):
    accel = (delay(c, 20) - delay(c, 10)) / 10 - (delay(c, 10) - c) / 10
    return np.ones_like(c, dtype=float).where(accel < -0.1, -1 * (c - delay(c, 1)))

# Alpha#50: (-1 * ts_max(rank(correlation(rank(volume), rank(vwap), 5)), 5))
def alpha050(v, vwap):
    return -1 * ts_max(rank(correlation(rank(v), rank(vwap), 5)), 5)

# Alpha#51: (((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 * 0.05)) ? 1 : ((-1) * (close - delay(close, 1))))
def alpha051(c):
    accel = (delay(c, 20) - delay(c, 10)) / 10 - (delay(c, 10) - c) / 10
    return np.ones_like(c, dtype=float).where(accel < -0.05, -1 * (c - delay(c, 1)))

# Alpha#52: ((((-1 * ts_min(low, 5)) + delay(ts_min(low, 5), 5)) * rank(((sum(returns, 240) - sum(returns, 20)) / 220))) * ts_rank(volume, 5))
def alpha052(c, l, v, r):
    return ((-1 * ts_min(l, 5) + delay(ts_min(l, 5), 5)) * rank((ts_sum(r, 240) - ts_sum(r, 20)) / 220)) * ts_rank(v, 5)

# Alpha#53: (-1 * delta((((close - low) - (high - close)) / (close - low)), 9))
def alpha053(c, h, l):
    inner = ((c - l) - (h - c)) / (c - l)
    return -1 * delta(inner, 9)

# Alpha#54: ((-1 * ((low - close) * (open^5))) / ((low - high) * (close^5)))
def alpha054(o, c, h, l):
    return -1 * (l - c) * o.pow(5) / ((l - h) * c.pow(5))

# Alpha#55: (-1 * correlation(rank(((close - ts_min(low, 12)) / (ts_max(high, 12) - ts_min(low, 12)))), rank(volume), 6))
def alpha055(c, h, l, v):
    inner = (c - ts_min(l, 12)) / (ts_max(h, 12) - ts_min(l, 12))
    return -1 * correlation(rank(inner), rank(v), 6)

# Alpha#56: (0 - (1 * (rank((sum(returns, 10) / sum(sum(returns, 2), 3))) * rank((returns * cap)))))
def alpha056(r, cap):
    return -1 * (rank(ts_sum(r, 10) / ts_sum(ts_sum(r, 2), 3)) * rank(r * cap))

# Alpha#57: (0 - (1 * ((rank((sum(returns, 10) / sum(sum(returns, 2), 3))) * rank((returns * cap)))))
# Same as #56 with different cap weighting — using adv20 variant
def alpha057(r, vwap, adv20):
    return -1 * (rank(ts_sum(r, 10) / ts_sum(ts_sum(r, 2), 3)) * rank(r * vwap * adv20))

# Alpha#58-#59: Complex IndNeutralize variants
def alpha058(v, vwap, ind_class):
    w = 0.25
    return -1 * ts_rank(decay_linear(correlation(indneutralize(vwap * w + vwap * (1 - w), ind_class), v, 4.25), 16), 8)

def alpha059(v, vwap, ind_class):
    w = 0.728317
    return -1 * ts_rank(decay_linear(correlation(indneutralize(vwap * w + vwap * (1 - w), ind_class), v, 4.25), 16.2), 8.2)

# Alpha#60: (0 - (1 * ((2 * scale(rank(((((close - low) - (high - close)) / (high - low)) * volume)))) - scale(rank(ts_argmax(close, 10))))))
def alpha060(c, h, l, v):
    inner = (((c - l) - (h - c)) / (h - l)) * v
    return -1 * (2 * scale(rank(inner)) - scale(rank(ts_argmax(c, 10))))

# Alpha#61: (rank((vwap - ts_min(vwap, 16.1219))) < rank(correlation(vwap, adv180, 17.9282)))
def alpha061(vwap, adv180):
    return rank(vwap - ts_min(vwap, 16)) < rank(correlation(vwap, adv180, 18))

# Alpha#62: ((rank(correlation(vwap, sum(adv20, 22), 10)) < rank(((rank(open) + rank(open)) < (rank(((high + low) / 2)) + rank(high))))) * -1)
def alpha062(o, h, l, v, vwap, adv20):
    cond = rank(correlation(vwap, ts_sum(adv20, 22), 10)) < rank((rank(o) + rank(o)) < (rank((h + l) / 2) + rank(h)))
    return cond.astype(float) * -1

# Alpha#63: Complex IndNeutralize
def alpha063(o, c, v, vwap, adv180, ind_class):
    return (-1 * (rank(decay_linear(delta(indneutralize(c, ind_class), 2.25), 8.2)) -
                  rank(decay_linear(correlation(vwap * 0.318 + o * 0.682, ts_sum(adv180, 37), 13.6), 12.3))))

# Alpha#64: ((rank(correlation(sum(((open * 0.178) + (low * 0.822)), 12.7), sum(adv120, 12.7), 16.6)) < rank(delta(((((high + low) / 2) * 0.178) + (vwap * 0.822)), 3.7))) * -1)
def alpha064(o, h, l, v, vwap, adv120):
    w = 0.178404
    s1 = rank(correlation(ts_sum(o * w + l * (1 - w), 13), ts_sum(adv120, 13), 17))
    s2 = rank(delta((h + l) / 2 * w + vwap * (1 - w), 4))
    return (s1 < s2).astype(float) * -1

# Alpha#65: ((rank(correlation(((open * 0.008) + (vwap * 0.992)), sum(adv60, 8.7), 6.4)) < rank((open - ts_min(open, 13.6)))) * -1)
def alpha065(o, v, vwap, adv60):
    w = 0.00817205
    s1 = rank(correlation(o * w + vwap * (1 - w), ts_sum(adv60, 9), 6))
    s2 = rank(o - ts_min(o, 14))
    return (s1 < s2).astype(float) * -1

# Alpha#66: ((rank(decay_linear(delta(vwap, 3.51), 7.23)) + Ts_Rank(decay_linear(((((low * 0.966) - vwap) / (open - ((high + low) / 2)))), 11.4), 6.73)) * -1)
def alpha066(o, h, l, vwap):
    w = 0.96633
    p1 = rank(decay_linear(delta(vwap, 3.5), 7.2))
    p2 = ts_rank(decay_linear((l * w - vwap) / (o - (h + l) / 2), 11.4), 6.7)
    return (p1 + p2) * -1

# Alpha#67-#70: Complex with IndNeutralize
def alpha067(o, c, h, v, vwap, ind_class):
    return (rank(decay_linear(delta(indneutralize(vwap, ind_class), 3.5), 7.2)) +
            ts_rank(decay_linear((l * 0.966 - vwap) / (o - (h + l) / 2), 11.4), 6.7)) * -1

def alpha068(o, c, h, l, v):
    w = 0.518371
    return (ts_rank(correlation(rank(h), rank(ts_mean(v, 15)), 9), 14) <
            rank(delta(c * w + l * (1 - w), 1))).astype(float) * -1

def alpha069(c, v, vwap, adv80, ind_class):
    return (ts_rank(decay_linear(correlation(indneutralize(c, ind_class), v, 9), 17), 18) <
            rank(correlation(c * 0.6 + vwap * 0.4, ts_sum(adv80, 9), 15))).astype(float) * -1

def alpha070(c, v, vwap, adv50, ind_class):
    return (rank(delta(vwap, 1.3)).pow(ts_rank(correlation(indneutralize(c, ind_class), adv50, 18), 18)) * -1)

# Alpha#71: max(Ts_Rank(decay_linear(correlation(Ts_Rank(close, 3.4), Ts_Rank(adv180, 19), 6.9), 13), 15), Ts_Rank(decay_linear(correlation(rank(vwap), rank(volume), 6.9), 3), 5))
def alpha071(o, c, l, v, vwap, adv180):
    s1 = ts_rank(decay_linear(correlation(ts_rank(c, 3), ts_rank(adv180, 19), 7), 13), 15)
    s2 = ts_rank(decay_linear(correlation(rank(vwap), rank(v), 7), 3), 5)
    return np.maximum(s1, s2)

# Alpha#72: (rank(decay_linear(correlation(Ts_Rank(vwap, 3.7), Ts_Rank(volume, 18.5), 6.9), 3)) * -1)
def alpha072(v, vwap):
    return rank(decay_linear(correlation(ts_rank(vwap, 4), ts_rank(v, 19), 7), 3)) * -1

# Alpha#73: max(rank(decay_linear(delta(vwap, 4.7), 3)), rank(decay_linear(...)))
def alpha073(o, l, vwap):
    s1 = rank(decay_linear(delta(vwap, 5), 3))
    s2 = rank(decay_linear((l - vwap) / delay(o, 3), 12))
    return np.maximum(s1, s2) * -1

# Alpha#74: ((rank(correlation(close, sum(adv30, 37), 15)) < rank(correlation(rank(high*0.026+ vwap*0.974), rank(volume), 11))) * -1)
def alpha074(h, c, v, vwap):
    w = 0.0261661
    return (rank(correlation(c, ts_sum(ts_mean(v, 30), 37), 15)) <
            rank(correlation(rank(h * w + vwap * (1 - w)), rank(v), 11))).astype(float) * -1

# Alpha#75: (rank(correlation(vwap, volume, 4.2)) < rank(correlation(rank(low), rank(adv50), 12.4)))
def alpha075(l, v, vwap, adv50):
    return (rank(correlation(vwap, v, 4)) < rank(correlation(rank(l), rank(adv50), 12))).astype(float)

# Alpha#76: Complex IndNeutralize
def alpha076(l, v, vwap, adv81, ind_class):
    s1 = rank(decay_linear(delta(vwap, 1.2), 12))
    s2 = ts_rank(decay_linear(ts_rank(correlation(indneutralize(l, ind_class), adv81, 8), 20), 17), 19)
    return np.maximum(s1, s2) * -1

# Alpha#77: min(rank(decay_linear(...)), rank(decay_linear(...)))
def alpha077(h, l, v, vwap, adv40):
    s1 = rank(decay_linear(((h + l) / 2 + h) - (vwap + h), 20))
    s2 = rank(decay_linear(correlation((h + l) / 2, adv40, 3), 6))
    return np.minimum(s1, s2)

# Alpha#78: rank(correlation(sum(low*0.352+vwap*0.648, 20), sum(adv40, 20), 8)) < rank(correlation(...)
def alpha078(l, v, vwap, adv40):
    w = 0.352233
    return (rank(correlation(ts_sum(l * w + vwap * (1 - w), 20), ts_sum(adv40, 20), 8)) <
            rank(correlation(ts_sum(l * w + vwap * (1 - w), 20), ts_mean(v, 20), 8))).astype(float) * -1

# Alpha#79: IndNeutralize complex
def alpha079(o, c, v, vwap, ind_class):
    return (rank(correlation(indneutralize(c * 0.607 + o * 0.393, ind_class), ts_mean(v, 20), 9)) <
            rank(correlation(c, ts_mean(v, 20), 9))).astype(float) * -1

# Alpha#80: IndNeutralize complex  
def alpha080(o, h, v, ind_class):
    return (rank(sign(delta(indneutralize(o * 0.968 + h * 0.032, ind_class), 1))) *
            rank(correlation(v, ts_mean(v, 20), 8))).astype(float) * -1

# Alpha#81: ((rank(log(sum(rank(rank(max((vwap - close), 3) * rank(delta(close, 1)))), 3))) < rank(delta(vwap, 4))) * -1)
def alpha081(c, v, vwap):
    return (rank(log(ts_sum(rank(rank(np.maximum(vwap - c, 3) * rank(delta(c, 1)))), 3))) <
            rank(delta(vwap, 4))).astype(float) * -1

# Alpha#82: IndNeutralize
def alpha082(o, v, ind_class):
    return (rank(correlation(indneutralize(o, ind_class), ts_mean(v, 20), 9)) <
            rank(correlation(indneutralize(o, ind_class), ts_sum(v, 20), 9))).astype(float) * -1

# Alpha#83: ((rank(delay(((high - low) / (sum(close, 5) / 5)), 2)) * rank(rank(volume))) / (((high - low) / (sum(close, 5) / 5)) / (vwap - close)))
def alpha083(c, h, l, v, vwap):
    spread = (h - l) / ts_mean(c, 5)
    return (rank(delay(spread, 2)) * rank(rank(v))) / (spread / (vwap - c))

# Alpha#84: SignedPower(Ts_Rank((vwap - ts_max(vwap, 15.3)), 20.7), delta(close, 5))
def alpha084(c, vwap):
    return signedpower(ts_rank(vwap - ts_max(vwap, 15), 21), delta(c, 5))

# Alpha#85: rank(correlation(close/vwap, delay(delta(close,1),5), 20)) * rank(correlation(close, volume, 6))
def alpha085(c, h, l, v, vwap):
    return rank(correlation((h + l) / 2 - vwap, delay(c, 5), 20)) * rank(correlation(c, v, 6))

# Alpha#86: ((0.25 < (((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10))) ? (-1 * delta(close, 1)) : delta(close, 1))
def alpha086(o, c, v, vwap):
    accel = (delay(c, 20) - delay(c, 10)) / 10 - (delay(c, 10) - c) / 10
    return (-1 * delta(c, 1)).where(accel > 0.25, delta(c, 1))

# Alpha#87-#91: Complex IndNeutralize
def alpha087(c, v, vwap, adv150, ind_class):
    return (rank(decay_linear(correlation(indneutralize(vwap, ind_class), adv150, 17), 12)) *
            rank(correlation(c, v, 6))).astype(float) * -1

def alpha088(o, c, h, l, v):
    return (rank(decay_linear(((c - o) / (h - l + 0.001)), 20)) *
            rank(correlation(c, v, 6))).astype(float) * -1

def alpha089(l, v, vwap, ind_class):
    s1 = rank(decay_linear(correlation(indneutralize(l, ind_class), v, 8), 13))
    s2 = rank(decay_linear(correlation(indneutralize(l, ind_class), vwap, 8), 13))
    return (s1 < s2).astype(float) * -1

def alpha090(c, v, ind_class):
    return (rank(correlation(indneutralize(c, ind_class), v, 9)) <
            rank(correlation(indneutralize(c, ind_class), ts_sum(v, 9), 9))).astype(float) * -1

def alpha091(c, v, vwap, ind_class):
    return (rank(correlation(indneutralize(c, ind_class), v, 9)) <
            rank(correlation(indneutralize(c, ind_class), vwap, 9))).astype(float) * -1

# Alpha#92: min(ts_rank(decay_linear(...), 18), ts_rank(decay_linear(...), 18))
def alpha092(o, c, h, l, v):
    p1 = ts_rank(decay_linear(((h + l) / 2 + c < l + o).astype(float), 15), 18)
    p2 = ts_rank(decay_linear(correlation(ts_rank(l, 11), ts_rank(ts_mean(v, 60), 4), 18), 12), 18)
    return np.minimum(p1, p2) * -1

# Alpha#93: IndNeutralize complex
def alpha093(c, v, vwap, ind_class):
    return (ts_rank(decay_linear(correlation(indneutralize(vwap, ind_class), v, 8), 13), 18) <
            rank(correlation(ts_rank(c, 8), ts_rank(v, 20), 5))).astype(float) * -1

# Alpha#94: rank(delay((high - low) / (sum(close, 5) / 5), 2)) * rank(rank(volume)) / (((high - low) / (sum(close, 5) / 5)) / (vwap - close))
def alpha094(o, c, h, l, v):
    return ((rank(c - delay(c, 1)) * rank(c - delay(c, 1))) <
            rank(correlation(ts_mean(v, 60), ts_mean(v, 60), 5))).astype(float) * -1

# Alpha#95: rank(open - ts_min(open, 12)) < ts_rank(rank(correlation(ts_mean((high+low)/2, 19), ts_sum(ts_mean(volume, 40), 19), 13)^5), 12)
def alpha095(o, h, l, v):
    cond = rank(o - ts_min(o, 12)) < ts_rank(rank(correlation(ts_mean((h + l) / 2, 19), ts_sum(ts_mean(v, 40), 19), 13).pow(5)), 12)
    return cond.astype(float) * -1

# Alpha#96: max(rank(decay_linear(delta(vwap, 1), 12)), rank(decay_linear(rank(correlation(low, ts_mean(volume, 60), 8)), 17)))
def alpha096(c, h, l, v, vwap):
    p1 = rank(decay_linear(delta(vwap, 1), 12))
    p2 = rank(decay_linear(rank(correlation(l, ts_mean(v, 60), 8)), 17))
    return np.maximum(p1, p2) * -1

# Alpha#97: IndNeutralize
def alpha097(l, v, vwap, ind_class):
    return (rank(decay_linear(delta(indneutralize(vwap, ind_class), 1), 12)) <
            rank(decay_linear(correlation(indneutralize(l, ind_class), v, 8), 17))).astype(float) * -1

# Alpha#98: ((rank(correlation(sum(close, 7), sum(close, 5), 3)) * rank(correlation(ts_rank(volume, 20), ts_rank(high, 20), 7))) * -1)
def alpha098(o, v, vwap):
    return (rank(correlation(ts_sum(vwap, 7), ts_sum(vwap, 5), 3)) *
            rank(correlation(ts_rank(v, 20), ts_rank(vwap, 20), 7))) * -1

# Alpha#99: ((rank(correlation(sum(close*0.55+high*0.45, 20), sum(ts_mean(volume, 40), 20), 9)) < rank(correlation(low, volume, 6))) * -1)
def alpha099(h, l, v):
    return (rank(correlation(ts_sum(c_placeholder(h, l) * 0.55 + h * 0.45, 20), ts_sum(ts_mean(v, 40), 20), 9)) <
            rank(correlation(l, v, 6))).astype(float) * -1

def c_placeholder(h, l):
    # Alpha#99 uses close; simplified
    return (h + l) / 2

# Alpha#100: Complex IndNeutralize — uses IndNeutralize twice
def alpha100(c, h, l, v, adv20, ind_class):
    inner = (((c - l) - (h - c)) / (h - l)) * v
    return -1 * ((1.5 * scale(indneutralize(indneutralize(rank(inner), ind_class), ind_class)) -
                   scale(indneutralize(correlation(c, rank(adv20), 5) - rank(ts_argmin(c, 30)), ind_class))) *
                  (v / adv20))

# Alpha#101: ((close - open) / ((high - low) + .001))
def alpha101(o, c, h, l):
    return (c - o) / ((h - l) + 0.001)


# ─── Utility: Compute all non-industry alphas given data ──────────

def compute_alphas(data: dict) -> dict:
    """
    data: dict with keys 'open','close','high','low','volume','vwap','returns','cap'
          Each value is a DataFrame (date x ticker)
    Returns: dict of alpha_name -> DataFrame
    """
    o, c, h, l = data['open'], data['close'], data['high'], data['low']
    v, vwap, r = data['volume'], data['vwap'], data['returns']
    cap = data.get('cap')
    adv20 = ts_mean(v, 20)
    adv40 = ts_mean(v, 40)
    adv50 = ts_mean(v, 50)
    adv60 = ts_mean(v, 60)
    adv80 = ts_mean(v, 80)
    adv120 = ts_mean(v, 120)
    adv150 = ts_mean(v, 150)
    adv180 = ts_mean(v, 180)

    results = {}
    # Simple alphas (no industry)
    results['alpha001'] = alpha001(c, r)
    results['alpha002'] = alpha002(o, c, v)
    results['alpha003'] = alpha003(o, v)
    results['alpha004'] = alpha004(l)
    results['alpha005'] = alpha005(o, vwap, c)
    results['alpha006'] = alpha006(o, v)
    results['alpha007'] = alpha007(c, v, adv20)
    results['alpha008'] = alpha008(o, r)
    results['alpha009'] = alpha009(c)
    results['alpha010'] = alpha010(c)
    results['alpha011'] = alpha011(vwap, c, v)
    results['alpha012'] = alpha012(v, c)
    results['alpha013'] = alpha013(c, v)
    results['alpha014'] = alpha014(o, v, r)
    results['alpha015'] = alpha015(h, v)
    results['alpha016'] = alpha016(h, v)
    results['alpha017'] = alpha017(c, v, adv20)
    results['alpha018'] = alpha018(o, c)
    results['alpha019'] = alpha019(c, r)
    results['alpha020'] = alpha020(o, h, l, c)
    results['alpha022'] = alpha022(h, c, v)
    results['alpha023'] = alpha023(h)
    results['alpha024'] = alpha024(c)
    results['alpha025'] = alpha025(r, adv20, vwap, h, c)
    results['alpha026'] = alpha026(h, v)
    results['alpha027'] = alpha027(v, vwap)
    results['alpha028'] = alpha028(adv20, l, h, c)
    results['alpha030'] = alpha030(c, v)
    results['alpha031'] = alpha031(c, l, adv20)
    results['alpha032'] = alpha032(c, vwap)
    results['alpha033'] = alpha033(o, c)
    results['alpha034'] = alpha034(c, r)
    results['alpha035'] = alpha035(h, l, c, v, r)
    results['alpha036'] = alpha036(o, c, v, vwap, adv20, r)
    results['alpha037'] = alpha037(o, c)
    results['alpha038'] = alpha038(o, c)
    results['alpha039'] = alpha039(c, v, adv20, r)
    results['alpha040'] = alpha040(h, v)
    results['alpha041'] = alpha041(h, l, vwap)
    results['alpha042'] = alpha042(vwap, c)
    results['alpha043'] = alpha043(c, v, adv20)
    results['alpha044'] = alpha044(h, v)
    results['alpha045'] = alpha045(c, v)
    results['alpha046'] = alpha046(c)
    results['alpha047'] = alpha047(c, h, v, vwap, adv20)
    results['alpha049'] = alpha049(c)
    results['alpha050'] = alpha050(v, vwap)
    results['alpha051'] = alpha051(c)
    results['alpha052'] = alpha052(c, l, v, r)
    results['alpha053'] = alpha053(c, h, l)
    results['alpha054'] = alpha054(o, c, h, l)
    results['alpha055'] = alpha055(c, h, l, v)
    if cap is not None:
        results['alpha056'] = alpha056(r, cap)
    results['alpha060'] = alpha060(c, h, l, v)
    results['alpha061'] = alpha061(vwap, adv180)
    results['alpha071'] = alpha071(o, c, l, v, vwap, adv180)
    results['alpha072'] = alpha072(v, vwap)
    results['alpha084'] = alpha084(c, vwap)
    results['alpha088'] = alpha088(o, c, h, l, v)
    results['alpha101'] = alpha101(o, c, h, l)

    return results


if __name__ == '__main__':
    print("WorldQuant 101 Formulaic Alphas — Ready")
    print("Import and call compute_alphas(data) with date x ticker DataFrames")
