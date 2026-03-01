import logging
import pandas as pd  # noqa: F401  (re-exported for other modules)
import ta
import time
import datetime
import copy
import hashlib
import json
import os
import random
import shutil
import sqlite3
import tomllib
import yaml
from dataclasses import dataclass
from typing import Any

import exchange.ws as hyperliquid_ws
import exchange.meta as hyperliquid_meta
from engine.alerting import send_openclaw_message
from engine.kernel_shadow_report import ShadowReport

logger = logging.getLogger(__name__)

try:
    import bt_runtime as _bt_runtime

    _BT_RUNTIME_AVAILABLE = True
except ImportError:
    _bt_runtime = None  # type: ignore[assignment]
    _BT_RUNTIME_AVAILABLE = False


# ---------------------------------------------------------------------------
# IndicatorSnapshot bridge (AQC-811)
# ---------------------------------------------------------------------------

# Canonical field list matching Rust IndicatorSnapshot (bt-core indicators/mod.rs).
_INDICATOR_SNAPSHOT_FIELDS: list[tuple[str, type]] = [
    ("close", float),
    ("high", float),
    ("low", float),
    ("open", float),
    ("volume", float),
    ("t", int),
    ("ema_slow", float),
    ("ema_fast", float),
    ("ema_macro", float),
    ("adx", float),
    ("adx_pos", float),
    ("adx_neg", float),
    ("adx_slope", float),
    ("bb_upper", float),
    ("bb_lower", float),
    ("bb_width", float),
    ("bb_width_avg", float),
    ("bb_width_ratio", float),
    ("atr", float),
    ("atr_slope", float),
    ("avg_atr", float),
    ("rsi", float),
    ("stoch_rsi_k", float),
    ("stoch_rsi_d", float),
    ("macd_hist", float),
    ("prev_macd_hist", float),
    ("prev2_macd_hist", float),
    ("prev3_macd_hist", float),
    ("vol_sma", float),
    ("vol_trend", bool),
    ("prev_close", float),
    ("prev_ema_fast", float),
    ("prev_ema_slow", float),
    ("bar_count", int),
    ("funding_rate", float),
]


def build_indicator_snapshot(
    df: pd.DataFrame,
    symbol: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an IndicatorSnapshot dict matching the Rust schema from a pandas DataFrame.

    If bt_runtime is available, uses the Rust IndicatorBank for exact numerical
    match.  Otherwise, falls back to Python ta-based computation.

    Parameters
    ----------
    df : pd.DataFrame
        Must have columns: Open, High, Low, Close, Volume.
        The index should be a DatetimeIndex (or have a 'Timestamp' column) with
        millisecond-epoch semantics.
    symbol : str, optional
        Trading symbol (unused currently; reserved for per-symbol config lookup).
    config : dict, optional
        Indicator config override matching Rust ``IndicatorsConfig`` fields
        (e.g. ``ema_slow_window``, ``atr_window``).  ``None`` or ``{}`` uses
        defaults.

    Returns
    -------
    dict
        IndicatorSnapshot with all 35 fields matching the Rust schema.
    """
    if len(df) == 0:
        raise ValueError("DataFrame must not be empty")

    # --- resolve timestamp column ---
    if "Timestamp" in df.columns:
        timestamps = df["Timestamp"].values
    elif hasattr(df.index, "astype"):
        try:
            timestamps = df.index.astype("int64") // 10**6  # ns -> ms
        except Exception:
            timestamps = list(range(len(df)))
    else:
        timestamps = list(range(len(df)))

    # --- Rust path (preferred) ---
    if _BT_RUNTIME_AVAILABLE:
        candles = []
        for i in range(len(df)):
            row = df.iloc[i]
            candles.append(
                {
                    "t": int(timestamps[i]) if hasattr(timestamps, "__getitem__") else int(timestamps),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                }
            )
        candles_json = json.dumps(candles)
        config_json = json.dumps(config) if config else "{}"
        result_json = _bt_runtime.compute_indicators(candles_json, config_json)
        return json.loads(result_json)

    # --- Python fallback ---
    return _build_indicator_snapshot_python(df, timestamps, config)


def _build_indicator_snapshot_python(
    df: pd.DataFrame,
    timestamps: Any,
    config: dict[str, Any] | None,
) -> dict[str, Any]:
    """Pure-Python fallback using the ``ta`` library.

    Mirrors the Rust IndicatorBank computation as closely as possible given
    that ``ta`` uses pandas rolling windows (not incremental EMA seeding), so
    there will be small numerical differences vs Rust on early bars.
    """
    cfg = config or {}
    ema_slow_win = int(cfg.get("ema_slow_window", 50))
    ema_fast_win = int(cfg.get("ema_fast_window", 20))
    ema_macro_win = int(cfg.get("ema_macro_window", 200))
    adx_win = int(cfg.get("adx_window", 14))
    bb_win = int(cfg.get("bb_window", 20))
    bb_width_avg_win = int(cfg.get("bb_width_avg_window", 30))
    atr_win = int(cfg.get("atr_window", 14))
    rsi_win = int(cfg.get("rsi_window", 14))
    vol_sma_win = int(cfg.get("vol_sma_window", 20))
    vol_trend_win = int(cfg.get("vol_trend_window", 5))
    stoch_rsi_win = int(cfg.get("stoch_rsi_window", 14))
    stoch_rsi_s1 = int(cfg.get("stoch_rsi_smooth1", 3))
    stoch_rsi_s2 = int(cfg.get("stoch_rsi_smooth2", 3))
    ave_avg_atr_win = int(cfg.get("ave_avg_atr_window", 50))

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    ema_slow = ta.trend.ema_indicator(close, window=ema_slow_win)
    ema_fast = ta.trend.ema_indicator(close, window=ema_fast_win)
    ema_macro = ta.trend.ema_indicator(close, window=ema_macro_win)

    adx_obj = ta.trend.ADXIndicator(high, low, close, window=adx_win)
    adx_series = adx_obj.adx()
    adx_pos_series = adx_obj.adx_pos()
    adx_neg_series = adx_obj.adx_neg()

    bb_obj = ta.volatility.BollingerBands(close, window=bb_win)
    bb_upper = bb_obj.bollinger_hband()
    bb_lower = bb_obj.bollinger_lband()
    # Keep parity with Rust fallback behaviour: non-positive close yields neutral bb_width=0.
    safe_close = close.where(close > 0.0, 1.0)
    bb_spread = (bb_upper - bb_lower).where(close > 0.0, 0.0)
    bb_width = bb_spread / safe_close
    bb_width_avg = bb_width.rolling(window=bb_width_avg_win).mean()

    atr_series = ta.volatility.average_true_range(high, low, close, window=atr_win)
    avg_atr_series = atr_series.rolling(window=ave_avg_atr_win).mean()

    rsi_series = ta.momentum.rsi(close, window=rsi_win)

    stoch_rsi_obj = ta.momentum.StochRSIIndicator(
        close,
        window=stoch_rsi_win,
        smooth1=stoch_rsi_s1,
        smooth2=stoch_rsi_s2,
    )
    stoch_k_series = stoch_rsi_obj.stochrsi_k()
    stoch_d_series = stoch_rsi_obj.stochrsi_d()

    macd_obj = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    macd_hist = macd_obj.macd_diff()

    vol_sma_series = volume.rolling(window=vol_sma_win).mean()
    vol_trend_sma = volume.rolling(window=vol_trend_win).mean()

    n = len(df)
    last = n - 1

    def _safe_float(series, idx, default=0.0):
        try:
            v = float(series.iloc[idx])
            return v if v == v else default  # NaN check
        except Exception:
            return default

    adx_val = _safe_float(adx_series, last)
    prev_adx = _safe_float(adx_series, last - 1) if n > 1 else 0.0
    atr_val = _safe_float(atr_series, last)
    prev_atr = _safe_float(atr_series, last - 1) if n > 1 else 0.0

    bb_w = _safe_float(bb_width, last)
    bb_w_avg = _safe_float(bb_width_avg, last)
    bb_w_ratio = bb_w / bb_w_avg if bb_w_avg > 0 else 1.0

    vol_sma_val = _safe_float(vol_sma_series, last)
    vol_trend_short = _safe_float(vol_trend_sma, last)
    vol_trend_val = vol_trend_short > vol_sma_val

    return {
        "close": float(df["Close"].iloc[last]),
        "high": float(df["High"].iloc[last]),
        "low": float(df["Low"].iloc[last]),
        "open": float(df["Open"].iloc[last]),
        "volume": float(df["Volume"].iloc[last]),
        "t": int(timestamps[last]),
        "ema_slow": _safe_float(ema_slow, last),
        "ema_fast": _safe_float(ema_fast, last),
        "ema_macro": _safe_float(ema_macro, last),
        "adx": adx_val,
        "adx_pos": _safe_float(adx_pos_series, last),
        "adx_neg": _safe_float(adx_neg_series, last),
        "adx_slope": adx_val - prev_adx,
        "bb_upper": _safe_float(bb_upper, last),
        "bb_lower": _safe_float(bb_lower, last),
        "bb_width": bb_w,
        "bb_width_avg": bb_w_avg,
        "bb_width_ratio": bb_w_ratio,
        "atr": atr_val,
        "atr_slope": atr_val - prev_atr,
        "avg_atr": _safe_float(avg_atr_series, last),
        "rsi": _safe_float(rsi_series, last),
        "stoch_rsi_k": _safe_float(stoch_k_series, last),
        "stoch_rsi_d": _safe_float(stoch_d_series, last),
        "macd_hist": _safe_float(macd_hist, last),
        "prev_macd_hist": _safe_float(macd_hist, last - 1) if n > 1 else 0.0,
        "prev2_macd_hist": _safe_float(macd_hist, last - 2) if n > 2 else 0.0,
        "prev3_macd_hist": _safe_float(macd_hist, last - 3) if n > 3 else 0.0,
        "vol_sma": vol_sma_val,
        "vol_trend": bool(vol_trend_val),
        "prev_close": float(df["Close"].iloc[last - 1]) if n > 1 else 0.0,
        "prev_ema_fast": _safe_float(ema_fast, last - 1) if n > 1 else 0.0,
        "prev_ema_slow": _safe_float(ema_slow, last - 1) if n > 1 else 0.0,
        "bar_count": n - 1,  # Rust counts 0-based (bars fed before latest)
        "funding_rate": 0.0,
    }


def _json_default(o):
    try:
        if hasattr(o, "item"):
            return o.item()
    except Exception:
        pass
    try:
        if isinstance(o, (datetime.datetime, datetime.date)):
            return o.isoformat()
    except Exception:
        pass
    return str(o)


def _json_dumps_safe(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=_json_default)
    except Exception:
        try:
            return json.dumps(str(obj), ensure_ascii=False, separators=(",", ":"))
        except Exception:
            return ""


# ---------------------------------------------------------------------------
# Entry signal delegation to kernel Evaluate mode (AQC-812)
# ---------------------------------------------------------------------------


def build_gate_result(
    snap: dict, symbol: str, cfg: dict | None = None, btc_bullish: bool | None = None, ema_slow_slope_pct: float = 0.0
) -> dict:
    """Build a GateResult dict matching the Rust GateResult schema.

    Mirrors the gate evaluation logic from ``analyze()`` and the Rust
    ``bt_signals::gates::check_gates()`` function, producing a JSON-safe
    dict that can be passed to the kernel's ``Evaluate`` signal.

    Parameters
    ----------
    snap : dict
        IndicatorSnapshot dict (from ``build_indicator_snapshot``).
    symbol : str
        Trading symbol (e.g. "ETH").
    cfg : dict, optional
        Strategy config (from ``get_strategy_config``).  ``None`` uses defaults.
    btc_bullish : bool or None
        BTC trend direction.  ``None`` = unknown.
    ema_slow_slope_pct : float
        Pre-computed EMA-slow slope: ``(ema_slow_now - ema_slow_prev) / close_now``.

    Returns
    -------
    dict
        GateResult with all fields matching the Rust schema.
    """
    if cfg is None:
        cfg = _DEFAULT_STRATEGY_CONFIG

    flt = cfg.get("filters") or {}
    thr = cfg.get("thresholds") or {}
    thr_entry = thr.get("entry") or {}
    thr_ranging = thr.get("ranging") or {}
    tp = thr.get("tp_and_momentum") or {}
    trade_cfg = cfg.get("trade") or {}

    # Gate 1: Ranging filter
    bb_width_ratio = float(snap.get("bb_width_ratio", 1.0))
    is_ranging = False
    if bool(flt.get("enable_ranging_filter", True)):
        try:
            min_signals = max(1, int(thr_ranging.get("min_signals", 2)))
        except Exception:
            min_signals = 2
        votes = 0
        if snap.get("adx", 0) < float(thr_ranging.get("adx_below", 21.0)):
            votes += 1
        if bb_width_ratio < float(thr_ranging.get("bb_width_ratio_below", 0.8)):
            votes += 1
        rsi = float(snap.get("rsi", 50.0))
        if float(thr_ranging.get("rsi_low", 47.0)) < rsi < float(thr_ranging.get("rsi_high", 53.0)):
            votes += 1
        is_ranging = votes >= min_signals

    # Gate 2: Anomaly filter
    is_anomaly = False
    if bool(flt.get("enable_anomaly_filter", True)):
        thr_anomaly = thr.get("anomaly") or {}
        prev_close = float(snap.get("prev_close", 0.0))
        close_val = float(snap.get("close", 0.0))
        if prev_close > 0:
            price_change_pct = abs(close_val - prev_close) / prev_close
        else:
            price_change_pct = 0.0
        ema_fast = float(snap.get("ema_fast", 0.0))
        if ema_fast > 0:
            ema_dev_pct = abs(close_val - ema_fast) / ema_fast
        else:
            ema_dev_pct = 0.0
        is_anomaly = price_change_pct > float(thr_anomaly.get("price_change_pct_gt", 0.10)) or ema_dev_pct > float(
            thr_anomaly.get("ema_fast_dev_pct_gt", 0.50)
        )

    # Gate 3: Extension filter
    is_extended = False
    if bool(flt.get("enable_extension_filter", True)):
        ema_fast = float(snap.get("ema_fast", 0.0))
        close_val = float(snap.get("close", 0.0))
        max_dist = float(thr_entry.get("max_dist_ema_fast", 0.04))
        dist = abs(close_val - ema_fast) / ema_fast if ema_fast > 0 else 0.0
        is_extended = dist > max_dist

    # Gate 4: Volume confirmation
    vol_confirm = True
    if bool(flt.get("require_volume_confirmation", True)):
        vol = float(snap.get("volume", 0.0))
        vol_sma = float(snap.get("vol_sma", 0.0))
        vol_trend = bool(snap.get("vol_trend", False))
        if bool(flt.get("vol_confirm_include_prev", True)):
            vol_confirm = (vol > vol_sma) or vol_trend
        else:
            vol_confirm = (vol > vol_sma) and vol_trend

    # Gate 5: ADX rising (or saturated)
    is_trending_up = True
    if bool(flt.get("require_adx_rising", True)):
        saturation = float(flt.get("adx_rising_saturation", 40.0))
        adx_slope = float(snap.get("adx_slope", 0.0))
        adx_val = float(snap.get("adx", 0.0))
        is_trending_up = (adx_slope > 0.0) or (adx_val > saturation)

    # Gate 6: ADX threshold (effective_min_adx with TMC + AVE)
    try:
        min_adx = float(thr_entry.get("min_adx", 22.0))
    except Exception:
        min_adx = 22.0
    effective_min_adx = min_adx

    # TMC: if ADX slope > 0.5, cap at 25.0
    adx_slope = float(snap.get("adx_slope", 0.0))
    if adx_slope > 0.5:
        effective_min_adx = min(effective_min_adx, 25.0)

    # AVE: if ATR/avg_ATR > threshold, multiply by ave_adx_mult
    ave_enabled = bool(thr_entry.get("ave_enabled", True))
    avg_atr = float(snap.get("avg_atr", 0.0))
    if ave_enabled and avg_atr > 0:
        atr = float(snap.get("atr", 0.0))
        atr_ratio = atr / avg_atr
        ave_atr_ratio_gt = float(thr_entry.get("ave_atr_ratio_gt", 1.5))
        if atr_ratio > ave_atr_ratio_gt:
            ave_adx_mult = float(thr_entry.get("ave_adx_mult", 1.25))
            if ave_adx_mult > 0:
                effective_min_adx *= ave_adx_mult

    adx_val = float(snap.get("adx", 0.0))
    adx_above_min = adx_val > effective_min_adx

    # Gate 7: Alignment (EMA cross + optional macro)
    ema_fast_val = float(snap.get("ema_fast", 0.0))
    ema_slow_val = float(snap.get("ema_slow", 0.0))
    ema_macro_val = float(snap.get("ema_macro", 0.0))

    bullish_alignment = ema_fast_val > ema_slow_val
    bearish_alignment = ema_fast_val < ema_slow_val
    if bool(flt.get("require_macro_alignment", False)):
        bullish_alignment = bullish_alignment and (ema_slow_val > ema_macro_val)
        bearish_alignment = bearish_alignment and (ema_slow_val < ema_macro_val)

    # Gate 8: BTC alignment
    sym_u = str(symbol or "").upper()
    require_btc = bool(flt.get("require_btc_alignment", True))
    try:
        btc_adx_override = float(thr_entry.get("btc_adx_override", 40.0))
    except Exception:
        btc_adx_override = 40.0

    btc_ok_long = (
        (not require_btc)
        or (sym_u == "BTC")
        or (btc_bullish is None)
        or bool(btc_bullish)
        or (adx_val > btc_adx_override)
    )
    btc_ok_short = (
        (not require_btc)
        or (sym_u == "BTC")
        or (btc_bullish is None)
        or (not bool(btc_bullish))
        or (adx_val > btc_adx_override)
    )

    # Slow-drift ranging override
    enable_slow_drift = bool(thr_entry.get("enable_slow_drift_entries", False))
    slow_drift_min_slope = float(thr_entry.get("slow_drift_min_slope_pct", 0.0006))
    if enable_slow_drift and is_ranging and abs(ema_slow_slope_pct) >= slow_drift_min_slope:
        is_ranging = False

    # Dynamic TP multiplier
    tp_atr_mult = float(trade_cfg.get("tp_atr_mult", TP_ATR_MULT))
    if adx_val > float(tp.get("adx_strong_gt", 40.0)):
        dynamic_tp_mult = float(tp.get("tp_mult_strong", 7.0))
    elif adx_val < float(tp.get("adx_weak_lt", 30.0)):
        dynamic_tp_mult = float(tp.get("tp_mult_weak", 3.0))
    else:
        dynamic_tp_mult = tp_atr_mult

    # DRE: Dynamic RSI Elasticity
    adx_min_dre = float(thr_entry.get("min_adx", 22.0))
    adx_max_dre = float(tp.get("adx_strong_gt", 40.0))
    if adx_max_dre <= adx_min_dre:
        adx_max_dre = adx_min_dre + 1.0
    weight = max(0.0, min(1.0, (adx_val - adx_min_dre) / (adx_max_dre - adx_min_dre)))
    rsi_long_limit = float(tp.get("rsi_long_weak", 56.0)) + weight * (
        float(tp.get("rsi_long_strong", 52.0)) - float(tp.get("rsi_long_weak", 56.0))
    )
    rsi_short_limit = float(tp.get("rsi_short_weak", 44.0)) + weight * (
        float(tp.get("rsi_short_strong", 48.0)) - float(tp.get("rsi_short_weak", 44.0))
    )

    # StochRSI
    stoch_k = float(snap.get("stoch_rsi_k", 0.0))
    stoch_d = float(snap.get("stoch_rsi_d", 0.0))
    stoch_rsi_active = bool(flt.get("use_stoch_rsi_filter", True))

    # Combined check
    all_gates_pass = (
        adx_above_min and (not is_ranging) and (not is_anomaly) and (not is_extended) and vol_confirm and is_trending_up
    )

    return {
        "is_ranging": bool(is_ranging),
        "is_anomaly": bool(is_anomaly),
        "is_extended": bool(is_extended),
        "vol_confirm": bool(vol_confirm),
        "is_trending_up": bool(is_trending_up),
        "adx_above_min": bool(adx_above_min),
        "bullish_alignment": bool(bullish_alignment),
        "bearish_alignment": bool(bearish_alignment),
        "btc_ok_long": bool(btc_ok_long),
        "btc_ok_short": bool(btc_ok_short),
        "effective_min_adx": float(effective_min_adx),
        "bb_width_ratio": float(bb_width_ratio),
        "dynamic_tp_mult": float(dynamic_tp_mult),
        "rsi_long_limit": float(rsi_long_limit),
        "rsi_short_limit": float(rsi_short_limit),
        "stoch_k": float(stoch_k),
        "stoch_d": float(stoch_d),
        "stoch_rsi_active": bool(stoch_rsi_active),
        "all_gates_pass": bool(all_gates_pass),
    }


def compute_ema_slow_slope(df, cfg: dict | None = None) -> float:
    """Compute the EMA-slow slope percentage from a DataFrame.

    Returns ``(ema_slow_now - ema_slow_prev_N) / close_now`` over the
    configured ``slow_drift_slope_window``.

    Parameters
    ----------
    df : pd.DataFrame
        Must have a 'Close' column and enough rows for indicator computation.
    cfg : dict, optional
        Strategy config.  Uses ``thresholds.entry.slow_drift_slope_window``
        (default 20).

    Returns
    -------
    float
        EMA-slow slope as a fraction of current price.
    """
    import ta as _ta

    if cfg is None:
        cfg = _DEFAULT_STRATEGY_CONFIG
    thr_entry = (cfg.get("thresholds") or {}).get("entry") or {}
    ind = cfg.get("indicators") or {}
    try:
        slope_window = int(thr_entry.get("slow_drift_slope_window", 20))
    except Exception:
        slope_window = 20
    slope_window = max(3, min(slope_window, len(df) - 1))

    try:
        ema_slow_win = int(ind.get("ema_slow_window", 50))
    except Exception:
        ema_slow_win = 50

    ema_slow = _ta.trend.ema_indicator(df["Close"], window=ema_slow_win)
    try:
        ema_slow_now = float(ema_slow.iloc[-1])
        ema_slow_prev = float(ema_slow.iloc[-slope_window])
        close_now = float(df["Close"].iloc[-1])
        if close_now == 0:
            close_now = 1.0
        result = (ema_slow_now - ema_slow_prev) / close_now
        if result != result:  # NaN check
            return 0.0
        return result
    except Exception:
        return 0.0


def build_entry_params(cfg: dict | None = None) -> dict:
    """Build an EntryParams dict matching the Rust kernel's EntryParams schema.

    Parameters
    ----------
    cfg : dict, optional
        Strategy config.  ``None`` uses defaults.

    Returns
    -------
    dict
        EntryParams serializable to JSON for the kernel.
    """
    if cfg is None:
        cfg = _DEFAULT_STRATEGY_CONFIG
    thr = cfg.get("thresholds") or {}
    thr_entry = thr.get("entry") or {}
    stoch_rsi = thr.get("stoch_rsi") or {}

    macd_mode_str = str(thr_entry.get("macd_hist_entry_mode", "accel")).strip().lower()
    macd_mode = {"accel": 0, "sign": 1, "none": 2}.get(macd_mode_str, 0)

    pullback_conf_str = str(thr_entry.get("pullback_confidence", "low")).strip().lower()
    pullback_conf = {"low": 0, "medium": 1, "high": 2}.get(pullback_conf_str, 0)

    return {
        "macd_mode": macd_mode,
        "stoch_block_long_gt": float(stoch_rsi.get("block_long_if_k_gt", 0.85)),
        "stoch_block_short_lt": float(stoch_rsi.get("block_short_if_k_lt", 0.15)),
        "high_conf_volume_mult": float(thr_entry.get("high_conf_volume_mult", 2.5)),
        "enable_pullback": bool(thr_entry.get("enable_pullback_entries", False)),
        "pullback_confidence": pullback_conf,
        "pullback_min_adx": float(thr_entry.get("pullback_min_adx", 22.0)),
        "pullback_rsi_long_min": float(thr_entry.get("pullback_rsi_long_min", 50.0)),
        "pullback_rsi_short_max": float(thr_entry.get("pullback_rsi_short_max", 50.0)),
        "pullback_require_macd_sign": bool(thr_entry.get("pullback_require_macd_sign", True)),
        "enable_slow_drift": bool(thr_entry.get("enable_slow_drift_entries", False)),
        "slow_drift_min_slope_pct": float(thr_entry.get("slow_drift_min_slope_pct", 0.0006)),
        "slow_drift_min_adx": float(thr_entry.get("slow_drift_min_adx", 10.0)),
        "slow_drift_rsi_long_min": float(thr_entry.get("slow_drift_rsi_long_min", 50.0)),
        "slow_drift_rsi_short_max": float(thr_entry.get("slow_drift_rsi_short_max", 50.0)),
        "slow_drift_require_macd_sign": bool(thr_entry.get("slow_drift_require_macd_sign", True)),
    }


def evaluate_entry_kernel(
    df, symbol: str, state_json: str, params_json: str, btc_bullish: bool | None = None, cfg: dict | None = None
):
    """Evaluate entry signal using the Rust kernel's Evaluate mode.

    Flow: candles -> build_indicator_snapshot() -> build_gate_result() ->
    MarketEvent(Evaluate, indicators, gate_result) -> kernel step_decision()
    -> DecisionResult with diagnostics.

    Parameters
    ----------
    df : pd.DataFrame
        Candle data with Open, High, Low, Close, Volume columns.
    symbol : str
        Trading symbol (e.g. "ETH").
    state_json : str
        Current kernel StrategyState as JSON.
    params_json : str
        Current kernel KernelParams as JSON (must include ``entry_params``).
    btc_bullish : bool or None
        BTC trend direction.
    cfg : dict, optional
        Strategy config override.  ``None`` uses ``get_strategy_config(symbol)``.

    Returns
    -------
    tuple[str, str, dict]
        ``(signal, confidence, diagnostics)`` where signal is "BUY"/"SELL"/"NEUTRAL",
        confidence is "low"/"medium"/"high", and diagnostics is the full kernel
        diagnostics dict.

    Raises
    ------
    RuntimeError
        If bt_runtime is not available or the kernel returns an error.
    """
    if not _BT_RUNTIME_AVAILABLE or _bt_runtime is None:
        raise RuntimeError("bt_runtime is not available; cannot use kernel Evaluate mode")

    if cfg is None:
        cfg = get_strategy_config(symbol)

    # 1. Build indicator snapshot
    snap = build_indicator_snapshot(df, symbol=symbol, config=cfg.get("indicators"))

    # 2. Compute EMA-slow slope
    slope = compute_ema_slow_slope(df, cfg)

    # 3. Build gate result
    gate_result = build_gate_result(snap, symbol, cfg=cfg, btc_bullish=btc_bullish, ema_slow_slope_pct=slope)

    # 4. Build entry_params and merge into params
    entry_params = build_entry_params(cfg)
    params_dict = json.loads(params_json)
    params_dict["entry_params"] = entry_params
    merged_params_json = json.dumps(params_dict)

    # 5. Build MarketEvent
    state_dict = json.loads(state_json)
    event = {
        "schema_version": int(state_dict.get("schema_version", 1)),
        "event_id": int(snap.get("t", 0)),
        "timestamp_ms": int(snap.get("t", 0)),
        "symbol": str(symbol).upper(),
        "signal": "evaluate",
        "price": float(snap.get("close", 0.0)),
        "indicators": snap,
        "gate_result": gate_result,
        "ema_slow_slope_pct": float(slope),
    }
    event_json = json.dumps(event, default=_json_default)

    # 6. Call kernel
    result_json = _bt_runtime.step_decision(state_json, event_json, merged_params_json)
    result = json.loads(result_json)

    if not result.get("ok"):
        err = result.get("error", {})
        raise RuntimeError(f"Kernel Evaluate failed: {err.get('message', 'unknown')} details={err.get('details', [])}")

    decision = result.get("decision", {})
    diag = decision.get("diagnostics", {})

    # 7. Extract signal + confidence from diagnostics
    entry_signal_raw = str(diag.get("entry_signal", "neutral")).upper()
    signal = entry_signal_raw if entry_signal_raw in ("BUY", "SELL") else "NEUTRAL"

    conf_int = diag.get("entry_confidence", 0)
    confidence = {0: "low", 1: "medium", 2: "high"}.get(conf_int, "low")

    return signal, confidence, diag


def analyze_with_shadow(
    df, symbol: str, state_json: str, params_json: str, btc_bullish: bool | None = None, cfg: dict | None = None
):
    """Run both Python ``analyze()`` and kernel ``Evaluate``, log differences.

    The kernel result is authoritative.  Python's ``analyze()`` is run for
    shadow comparison only and its result is discarded (except for logging).

    Parameters
    ----------
    df : pd.DataFrame
        Candle data.
    symbol : str
        Trading symbol.
    state_json : str
        Kernel state JSON.
    params_json : str
        Kernel params JSON.
    btc_bullish : bool or None
        BTC trend direction.
    cfg : dict, optional
        Strategy config override.

    Returns
    -------
    tuple[str, str, dict]
        ``(signal, confidence, diagnostics)`` — always from the kernel.
    """
    # Python signal (best-effort; never let it break the kernel path)
    py_signal, py_conf = "NEUTRAL", "low"
    try:
        py_result = analyze(df, symbol, btc_bullish)
        py_signal = str(py_result[0]).upper()
        py_conf = str(py_result[1]).lower()
    except Exception as exc:
        logger.warning("[shadow] Python analyze() failed: %s", exc)

    # Kernel signal
    k_signal, k_conf, k_diag = evaluate_entry_kernel(
        df,
        symbol,
        state_json,
        params_json,
        btc_bullish=btc_bullish,
        cfg=cfg,
    )

    # Compare and log
    if py_signal != k_signal or py_conf != k_conf:
        logger.warning(
            "[shadow] Signal mismatch for %s: Python=%s/%s, Kernel=%s/%s",
            symbol,
            py_signal,
            py_conf,
            k_signal,
            k_conf,
        )
    else:
        logger.debug(
            "[shadow] Signal agreement for %s: %s/%s",
            symbol,
            k_signal,
            k_conf,
        )

    return k_signal, k_conf, k_diag


# ---------------------------------------------------------------------------
# Exit delegation to kernel PriceUpdate mode (AQC-813)
# ---------------------------------------------------------------------------


def build_exit_params(config=None):
    """Serialize strategy exit config to kernel ExitParams JSON dict.

    Maps fields from ``_DEFAULT_STRATEGY_CONFIG["trade"]`` (and ``filters``)
    to the Rust kernel ``ExitParams`` schema defined in ``kernel_exits.rs``.

    Parameters
    ----------
    config : dict, optional
        Full strategy config dict.  ``None`` uses ``_DEFAULT_STRATEGY_CONFIG``.

    Returns
    -------
    dict
        ExitParams dict serializable to JSON for the kernel.
    """
    if config is None:
        config = _DEFAULT_STRATEGY_CONFIG
    trade = config.get("trade") or {}
    flt = config.get("filters") or {}

    def _f(key, default):
        try:
            return float(trade.get(key, default))
        except Exception:
            return float(default)

    def _b(key, default):
        return bool(trade.get(key, default))

    return {
        "sl_atr_mult": _f("sl_atr_mult", 2.0),
        "tp_atr_mult": _f("tp_atr_mult", 4.0),
        "trailing_start_atr": _f("trailing_start_atr", 1.0),
        "trailing_distance_atr": _f("trailing_distance_atr", 0.8),
        "enable_partial_tp": _b("enable_partial_tp", True),
        "tp_partial_pct": _f("tp_partial_pct", 0.5),
        "tp_partial_atr_mult": _f("tp_partial_atr_mult", 0.0),
        "tp_partial_min_notional_usd": _f("tp_partial_min_notional_usd", 10.0),
        "enable_breakeven_stop": _b("enable_breakeven_stop", True),
        "breakeven_start_atr": _f("breakeven_start_atr", 0.7),
        "breakeven_buffer_atr": _f("breakeven_buffer_atr", 0.05),
        "enable_vol_buffered_trailing": _b("enable_vol_buffered_trailing", True),
        "block_exits_on_extreme_dev": _b("block_exits_on_extreme_dev", False),
        "glitch_price_dev_pct": _f("glitch_price_dev_pct", 0.40),
        "glitch_atr_mult": _f("glitch_atr_mult", 12.0),
        # Smart exits
        "smart_exit_adx_exhaustion_lt": _f("smart_exit_adx_exhaustion_lt", 18.0),
        "tsme_min_profit_atr": _f("tsme_min_profit_atr", 1.0),
        "tsme_require_adx_slope_negative": _b("tsme_require_adx_slope_negative", True),
        "enable_rsi_overextension_exit": _b("enable_rsi_overextension_exit", True),
        "rsi_exit_profit_atr_switch": _f("rsi_exit_profit_atr_switch", 1.5),
        "rsi_exit_ub_lo_profit": _f("rsi_exit_ub_lo_profit", 80.0),
        "rsi_exit_ub_hi_profit": _f("rsi_exit_ub_hi_profit", 70.0),
        "rsi_exit_lb_lo_profit": _f("rsi_exit_lb_lo_profit", 20.0),
        "rsi_exit_lb_hi_profit": _f("rsi_exit_lb_hi_profit", 30.0),
        # Low-confidence RSI overrides
        "rsi_exit_ub_lo_profit_low_conf": _f("rsi_exit_ub_lo_profit_low_conf", 0.0),
        "rsi_exit_lb_lo_profit_low_conf": _f("rsi_exit_lb_lo_profit_low_conf", 0.0),
        "rsi_exit_ub_hi_profit_low_conf": _f("rsi_exit_ub_hi_profit_low_conf", 0.0),
        "rsi_exit_lb_hi_profit_low_conf": _f("rsi_exit_lb_hi_profit_low_conf", 0.0),
        # Low-confidence ADX exhaustion
        "smart_exit_adx_exhaustion_lt_low_conf": _f("smart_exit_adx_exhaustion_lt_low_conf", 0.0),
        # Macro alignment (from filters)
        "require_macro_alignment": bool(flt.get("require_macro_alignment", False)),
        # Per-confidence trailing overrides
        "trailing_start_atr_low_conf": _f("trailing_start_atr_low_conf", 0.0),
        "trailing_distance_atr_low_conf": _f("trailing_distance_atr_low_conf", 0.0),
    }


def evaluate_exit_kernel(df, symbol, state_json, params_json, current_price, timestamp_ms, config=None):
    """Evaluate exit conditions using the Rust kernel's PriceUpdate mode.

    Flow:
        1. ``build_indicator_snapshot(df)`` -> IndicatorSnapshot
        2. ``build_exit_params(config)`` -> ExitParams
        3. Construct ``MarketEvent(signal=PriceUpdate, indicators=snapshot)``
        4. ``bt_runtime.step_full(state, event, params, exit_params)``
        5. Parse result: extract ``exit_context`` from diagnostics

    Parameters
    ----------
    df : pd.DataFrame
        Candle data with Open, High, Low, Close, Volume columns.
    symbol : str
        Trading symbol (e.g. "ETH").
    state_json : str
        Current kernel StrategyState as JSON.  Must contain a position for
        *symbol* if exit evaluation is to produce a non-hold result.
    params_json : str
        Kernel KernelParams as JSON.
    current_price : float
        Current market price for the exit evaluation.
    timestamp_ms : int
        Current timestamp in milliseconds.
    config : dict, optional
        Strategy config override.  ``None`` uses ``get_strategy_config(symbol)``.

    Returns
    -------
    tuple[str, dict | None, dict]
        ``(action, exit_context, diagnostics)`` where:
        - *action*: ``"hold"`` | ``"full_close"`` | ``"partial_close"``
        - *exit_context*: dict with exit_type, exit_reason, exit_price, etc.
          or ``None`` when action is ``"hold"``
        - *diagnostics*: full diagnostics dict from kernel

    Raises
    ------
    RuntimeError
        If bt_runtime is not available or the kernel returns an error.
    """
    if not _BT_RUNTIME_AVAILABLE or _bt_runtime is None:
        raise RuntimeError("bt_runtime is not available; cannot use kernel PriceUpdate mode")

    if config is None:
        config = get_strategy_config(symbol)

    # 1. Build indicator snapshot
    snap = build_indicator_snapshot(df, symbol=symbol, config=config.get("indicators"))

    # 2. Build exit params
    exit_params = build_exit_params(config)
    exit_params_json = json.dumps(exit_params, default=_json_default)

    # 3. Build MarketEvent with PriceUpdate signal
    state_dict = json.loads(state_json)
    event = {
        "schema_version": int(state_dict.get("schema_version", 1)),
        "event_id": int(timestamp_ms),
        "timestamp_ms": int(timestamp_ms),
        "symbol": str(symbol).upper(),
        "signal": "price_update",
        "price": float(current_price),
        "indicators": snap,
        "notional_hint_usd": None,
        "close_fraction": None,
        "fee_role": None,
        "funding_rate": None,
        "gate_result": None,
        "ema_slow_slope_pct": None,
    }
    event_json = json.dumps(event, default=_json_default)

    # 4. Call kernel step_full (merges exit_params into params)
    result_json = _bt_runtime.step_full(
        state_json,
        event_json,
        params_json,
        exit_params_json,
    )
    result = json.loads(result_json)

    if not result.get("ok"):
        err = result.get("error", {})
        raise RuntimeError(
            f"Kernel PriceUpdate failed: {err.get('message', 'unknown')} details={err.get('details', [])}"
        )

    decision = result.get("decision", {})
    diag = decision.get("diagnostics", {})
    exit_ctx = diag.get("exit_context")

    # 5. Determine action from kernel result
    fills = decision.get("fills", [])
    intents = decision.get("intents", [])

    if exit_ctx is not None:
        # Kernel triggered an exit — determine full vs partial
        # Check intents/fills for close_fraction hint
        is_partial = False
        for intent in intents:
            kind = str(intent.get("kind", "")).lower()
            if kind == "close":
                frac = intent.get("close_fraction")
                if frac is not None and 0.0 < float(frac) < 1.0:
                    is_partial = True
                    break
        # Also check if fills indicate partial (notional < position notional)
        if not is_partial and len(fills) > 0:
            for fill in fills:
                frac = fill.get("close_fraction")
                if frac is not None and 0.0 < float(frac) < 1.0:
                    is_partial = True
                    break

        action = "partial_close" if is_partial else "full_close"
    else:
        action = "hold"
        exit_ctx = None

    return action, exit_ctx, diag


def check_exit_with_kernel(
    df, symbol, state_json, params_json, current_price, timestamp_ms, indicators=None, config=None, btc_bullish=None
):
    """Run kernel exit evaluation as the single authoritative exit path.

    This function intentionally does not apply any Python smart-exit fallback
    after a kernel ``"hold"`` result.  Exit behaviour is delegated to the
    Rust decision kernel to keep live/paper/backtester parity deterministic.

    Parameters
    ----------
    df : pd.DataFrame
        Candle data.
    symbol : str
        Trading symbol.
    state_json : str
        Kernel state JSON (must have position for *symbol*).
    params_json : str
        Kernel params JSON.
    current_price : float
        Current market price.
    timestamp_ms : int
        Current timestamp in milliseconds.
    indicators : dict, optional
        Pre-computed indicator dict (Python-style keys like ``ADX``, ``RSI``,
        ``EMA_fast``, ``EMA_slow``).  If ``None``, will attempt to extract
        from the DataFrame.
    config : dict, optional
        Strategy config override.
    btc_bullish : bool or None
        BTC trend direction (unused currently; reserved for future gates).

    Returns
    -------
    tuple[str, dict | None, dict]
        ``(action, exit_context, diagnostics)`` with same schema as
        ``evaluate_exit_kernel``.
    """
    if config is None:
        config = get_strategy_config(symbol)

    # --- Step 1: Kernel basic exits ---
    action, exit_ctx, diag = evaluate_exit_kernel(
        df,
        symbol,
        state_json,
        params_json,
        current_price,
        timestamp_ms,
        config=config,
    )

    # Kernel decision is authoritative for all exit types in SSOT mode.
    return action, exit_ctx, diag


def check_exit_with_shadow(
    df, symbol, state_json, params_json, current_price, timestamp_ms, indicators=None, config=None, btc_bullish=None
):
    """Shadow comparison mode for exit evaluation.

    Runs kernel exit evaluation via ``evaluate_exit_kernel()``, performs a
    best-effort comparison against what simplified Python logic would decide,
    and logs mismatches.  Always returns the kernel result as authoritative.

    Parameters
    ----------
    df : pd.DataFrame
        Candle data.
    symbol : str
        Trading symbol.
    state_json : str
        Kernel state JSON.
    params_json : str
        Kernel params JSON.
    current_price : float
        Current market price.
    timestamp_ms : int
        Current timestamp in milliseconds.
    indicators : dict, optional
        Pre-computed indicator dict.
    config : dict, optional
        Strategy config override.
    btc_bullish : bool or None
        BTC trend direction.

    Returns
    -------
    tuple[str, dict | None, dict]
        ``(action, exit_context, diagnostics)`` -- always from the kernel.
    """
    if config is None:
        config = get_strategy_config(symbol)

    # --- Kernel exit (authoritative) ---
    k_action, k_exit_ctx, k_diag = evaluate_exit_kernel(
        df,
        symbol,
        state_json,
        params_json,
        current_price,
        timestamp_ms,
        config=config,
    )

    # --- Python simplified exit (best-effort shadow) ---
    py_action = "hold"
    try:
        ind = indicators or {}
        snap_diag = k_diag.get("indicator_snapshot") or {}

        def _sv(py_key, snap_key, default=0.0):
            v = ind.get(py_key)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
            v = snap_diag.get(snap_key)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
            return float(default)

        ema_fast = _sv("EMA_fast", "ema_fast", 0.0)
        ema_slow = _sv("EMA_slow", "ema_slow", 0.0)

        # Determine position side
        state_dict = json.loads(state_json)
        pos_data = (state_dict.get("positions") or {}).get(symbol.upper())
        if pos_data is not None:
            pos_side = str(pos_data.get("side", "")).lower()
            # Simple trend breakdown check
            if ema_fast > 0 and ema_slow > 0:
                if pos_side == "long" and ema_fast < ema_slow:
                    py_action = "full_close"
                elif pos_side == "short" and ema_fast > ema_slow:
                    py_action = "full_close"
    except Exception as exc:
        logger.warning("[exit-shadow] Python exit check failed: %s", exc)

    # --- Compare and log ---
    if k_action != py_action:
        logger.warning(
            "[exit-shadow] Exit mismatch for %s: Kernel=%s, Python=%s",
            symbol,
            k_action,
            py_action,
        )
    else:
        logger.debug(
            "[exit-shadow] Exit agreement for %s: %s",
            symbol,
            k_action,
        )

    return k_action, k_exit_ctx, k_diag


# ---------------------------------------------------------------------------
# Position lifecycle delegation to kernel SSOT (AQC-814)
# ---------------------------------------------------------------------------


def get_kernel_positions(state_json: str) -> dict:
    """Extract positions from kernel state JSON.

    Uses ``bt_runtime.get_positions()`` when available (parses and validates
    through Rust serde), falling back to direct JSON parsing.

    Parameters
    ----------
    state_json : str
        Kernel StrategyState as JSON string.

    Returns
    -------
    dict
        Mapping of symbol (str) -> kernel Position dict.
    """
    if _BT_RUNTIME_AVAILABLE and _bt_runtime is not None:
        try:
            positions_json = _bt_runtime.get_positions(state_json)
            return json.loads(positions_json)
        except Exception:
            pass  # fall through to Python fallback

    # Python fallback: parse state JSON directly
    try:
        state = json.loads(state_json)
        return dict(state.get("positions") or {})
    except Exception:
        return {}


def kernel_position_to_python(symbol: str, kernel_pos: dict) -> dict:
    """Convert a kernel Position dict to the Python position dict format.

    The Rust kernel ``Position`` struct has fields like ``quantity``,
    ``avg_entry_price``, ``side`` (``"long"``/``"short"``), while the Python
    ``PaperTrader.positions`` dict uses ``size``, ``entry_price``,
    ``type`` (``"LONG"``/``"SHORT"``).

    Parameters
    ----------
    symbol : str
        Trading symbol (e.g. "ETH").
    kernel_pos : dict
        Position dict as returned by ``get_kernel_positions()``.

    Returns
    -------
    dict
        Python-format position dict compatible with PaperTrader.
    """
    side_raw = str(kernel_pos.get("side", "long")).lower()
    py_type = "LONG" if side_raw == "long" else "SHORT"

    trailing_sl = kernel_pos.get("trailing_sl")
    if trailing_sl is not None:
        try:
            trailing_sl = float(trailing_sl)
        except (TypeError, ValueError):
            trailing_sl = None

    entry_atr = kernel_pos.get("entry_atr")
    if entry_atr is not None:
        try:
            entry_atr = float(entry_atr)
        except (TypeError, ValueError):
            entry_atr = 0.0
    else:
        entry_atr = 0.0

    entry_adx_threshold = kernel_pos.get("entry_adx_threshold")
    if entry_adx_threshold is not None:
        try:
            entry_adx_threshold = float(entry_adx_threshold)
        except (TypeError, ValueError):
            entry_adx_threshold = 0.0
    else:
        entry_adx_threshold = 0.0

    avg_entry = float(kernel_pos.get("avg_entry_price", 0.0))
    quantity = float(kernel_pos.get("quantity", 0.0))
    notional = abs(quantity) * avg_entry
    margin_usd = float(kernel_pos.get("margin_usd", 0.0))
    # Estimate leverage from margin if available
    if margin_usd > 0 and notional > 0:
        leverage = notional / margin_usd
    else:
        leverage = 1.0

    confidence_raw = kernel_pos.get("confidence")
    if confidence_raw is not None:
        # Kernel stores 0=Low, 1=Medium, 2=High
        conf_map = {0: "low", 1: "medium", 2: "high"}
        try:
            confidence = conf_map.get(int(confidence_raw), "medium")
        except (TypeError, ValueError, OverflowError):
            confidence = "medium"
    else:
        confidence = ""

    opened_at_ms = int(kernel_pos.get("opened_at_ms", 0))
    try:
        import datetime as _dt

        opened_at = (
            _dt.datetime.fromtimestamp(opened_at_ms / 1000.0, tz=_dt.timezone.utc).isoformat()
            if opened_at_ms > 0
            else ""
        )
    except Exception:
        opened_at = ""

    last_funding_ms = kernel_pos.get("last_funding_ms")
    last_funding_time = int(last_funding_ms) if last_funding_ms is not None else 0

    return {
        "type": py_type,
        "entry_price": avg_entry,
        "size": quantity,
        "confidence": confidence,
        "entry_atr": entry_atr,
        "entry_adx_threshold": entry_adx_threshold,
        "open_trade_id": None,  # not tracked by kernel
        "open_timestamp": opened_at,
        "trailing_sl": trailing_sl,
        "last_funding_time": last_funding_time,
        "leverage": leverage,
        "margin_used": margin_usd,
        "adds_count": int(kernel_pos.get("adds_count", 0)),
        "tp1_taken": int(kernel_pos.get("tp1_taken", False)),
        "last_add_time": 0,  # not tracked by kernel
    }


def python_position_to_kernel(symbol: str, py_pos: dict) -> dict:
    """Convert a Python position dict back to kernel Position format.

    Inverse of ``kernel_position_to_python``.

    Parameters
    ----------
    symbol : str
        Trading symbol (e.g. "ETH").
    py_pos : dict
        Python-format position dict from PaperTrader.

    Returns
    -------
    dict
        Kernel Position dict matching the Rust ``Position`` struct schema.
    """
    pos_type = str(py_pos.get("type", "LONG")).upper()
    side = "long" if pos_type == "LONG" else "short"

    entry_price = float(py_pos.get("entry_price", 0.0))
    size = float(py_pos.get("size", 0.0))
    leverage = float(py_pos.get("leverage", 1.0))
    leverage = max(1.0, leverage)
    notional = abs(size) * entry_price
    margin_usd = float(py_pos.get("margin_used", 0.0))
    if margin_usd <= 0 and entry_price > 0:
        margin_usd = notional / leverage

    trailing_sl = py_pos.get("trailing_sl")
    if trailing_sl is not None:
        try:
            trailing_sl = float(trailing_sl)
        except (TypeError, ValueError):
            trailing_sl = None

    entry_atr = py_pos.get("entry_atr")
    if entry_atr is not None:
        try:
            entry_atr = float(entry_atr)
        except (TypeError, ValueError):
            entry_atr = None

    entry_adx_threshold = py_pos.get("entry_adx_threshold")
    if entry_adx_threshold is not None:
        try:
            entry_adx_threshold = float(entry_adx_threshold)
        except (TypeError, ValueError):
            entry_adx_threshold = None

    confidence_str = str(py_pos.get("confidence", "")).strip().lower()
    conf_map = {"low": 0, "medium": 1, "high": 2}
    confidence = conf_map.get(confidence_str)

    opened_at = py_pos.get("open_timestamp", "")
    opened_at_ms = 0
    if opened_at:
        try:
            import datetime as _dt

            dt = _dt.datetime.fromisoformat(str(opened_at))
            opened_at_ms = int(dt.timestamp() * 1000)
        except Exception:
            opened_at_ms = 0

    last_funding_time = int(py_pos.get("last_funding_time", 0))

    return {
        "symbol": symbol,
        "side": side,
        "quantity": size,
        "avg_entry_price": entry_price,
        "opened_at_ms": opened_at_ms,
        "updated_at_ms": opened_at_ms,  # best approximation
        "notional_usd": notional,
        "margin_usd": margin_usd,
        "confidence": confidence,
        "entry_atr": entry_atr,
        "entry_adx_threshold": entry_adx_threshold,
        "adds_count": int(py_pos.get("adds_count", 0)),
        "tp1_taken": bool(int(py_pos.get("tp1_taken", 0))),
        "trailing_sl": trailing_sl,
        "mae_usd": 0.0,
        "mfe_usd": 0.0,
        "last_funding_ms": last_funding_time if last_funding_time > 0 else None,
    }


def sync_positions_from_kernel(state_json: str) -> dict:
    """Read kernel state and convert all positions to Python format.

    This is the main bridge function that allows Python code to read the
    kernel's SSOT position state in the familiar PaperTrader dict format.

    Parameters
    ----------
    state_json : str
        Kernel StrategyState as JSON string.

    Returns
    -------
    dict
        Mapping of symbol (str) -> Python position dict.
    """
    kernel_positions = get_kernel_positions(state_json)
    result = {}
    for symbol, kernel_pos in kernel_positions.items():
        result[symbol] = kernel_position_to_python(symbol, kernel_pos)
    return result


def build_position_state_for_db(state_json: str) -> list[dict]:
    """Extract position data from kernel state and format for SQLite persistence.

    Returns a list of dicts suitable for inserting into the ``position_state``
    table.  Each dict contains the columns expected by
    ``PaperTrader.upsert_position_state()``.

    Parameters
    ----------
    state_json : str
        Kernel StrategyState as JSON string.

    Returns
    -------
    list[dict]
        List of position dicts with keys matching the DB schema:
        ``symbol``, ``open_trade_id``, ``trailing_sl``, ``last_funding_time``,
        ``adds_count``, ``tp1_taken``, ``last_add_time``, ``entry_adx_threshold``.
    """
    import datetime as _dt

    kernel_positions = get_kernel_positions(state_json)
    rows = []
    for symbol, kernel_pos in kernel_positions.items():
        trailing_sl = kernel_pos.get("trailing_sl")
        if trailing_sl is not None:
            try:
                trailing_sl = float(trailing_sl)
            except (TypeError, ValueError):
                trailing_sl = None

        entry_adx_threshold = kernel_pos.get("entry_adx_threshold")
        if entry_adx_threshold is not None:
            try:
                entry_adx_threshold = float(entry_adx_threshold)
            except (TypeError, ValueError):
                entry_adx_threshold = 0.0
        else:
            entry_adx_threshold = 0.0

        last_funding_ms = kernel_pos.get("last_funding_ms")
        last_funding_time = int(last_funding_ms) if last_funding_ms is not None else 0

        rows.append(
            {
                "symbol": symbol,
                "open_trade_id": None,  # not tracked by kernel
                "trailing_sl": trailing_sl,
                "last_funding_time": last_funding_time,
                "adds_count": int(kernel_pos.get("adds_count", 0)),
                "tp1_taken": int(kernel_pos.get("tp1_taken", False)),
                "last_add_time": 0,  # not tracked by kernel
                "entry_adx_threshold": entry_adx_threshold,
                "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            }
        )
    return rows


# --------------------------------------------------------------------------------------
# Developer Notes (READ ME FIRST)
#
# This file provides the core strategy + PaperTrader implementation used by the unified daemon:
#   engine/daemon.py
#
# - Strategy tuning should be done via YAML overrides (hot-reloads by file mtime).
# - Python code changes require restarting the systemd service(s).
#
# Configuration (preferred)
# - Use YAML overrides instead of editing Python:
#     config/strategy_overrides.yaml
#   Override path with: AI_QUANT_STRATEGY_YAML=/path/to/strategy_overrides.yaml
#   Merge order (deep-merge / inheritance):
#     defaults (in this file) ← global ← symbols.<SYMBOL>
# - TOML overrides are deprecated:
#     config/strategy_overrides.toml
#   Override path with: AI_QUANT_STRATEGY_TOML=/path/to/strategy_overrides.toml
#
# Watchlist / Universe
# - Default watchlist is the top 50 Hyperliquid perps by 24h notional volume (dayNtlVlm).
#   Adjust with: AI_QUANT_TOP_N=50
# - You can override explicitly without editing code:
#     AI_QUANT_SYMBOLS="BTC,ETH,SOL,..."
#
# Balances (paper) — AQC-755: kernel is sole accounting authority
# - `self.balance` = property delegating to Rust kernel `cash_usd` (via bt_runtime)
# - `get_live_balance()` = equity from kernel + fee estimate
#
# Perps-style positions
# - One NET position per symbol (like real perps), but multiple fills/tranches are supported:
#     OPEN   : open a new net position
#     ADD    : scale-in (pyramiding) and re-average entry
#     REDUCE : partial close (realizes PnL on the reduced size)
#     CLOSE  : final close (implemented as REDUCE of remaining size)
#     FUNDING: hourly funding cashflow (realizes directly into cash)
#
# Data + execution simulation
# - Market data uses Hyperliquid websocket streams (allMids, bbo, candle) via `hyperliquid_ws.py`.
# - Fill prices prefer BBO; then mid; then fallback to candle price.
# - Fees and slippage are applied per fill; tune with HL_* env vars below.
# - Funding uses the Hyperliquid SDK `Info.funding_history()` (REST) because funding is hourly
#   and not latency-sensitive. Disable via: HL_FUNDING_ENABLED=0
#
# Backfills / recompute
# - If you changed fee/leverage logic or introduced ADD/REDUCE, you may need to rebuild paper balances
#   (this repo does not ship a recompute script).
# --------------------------------------------------------------------------------------

# Paths
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))

# Strategy version history: strategy_changelog.json
# Universe / Watchlist
#
# Default behavior:
# - If `AI_QUANT_SYMBOLS` is set: use that exact list.
# - Otherwise: auto-select the top-N Hyperliquid perps by 24h notional volume (dayNtlVlm).
#   Configure N with: `AI_QUANT_TOP_N` (default: 50).
#
# Why: a static list gets stale and can be "too quiet" as markets rotate.
_FALLBACK_SYMBOLS = [
    "BTC",
    "ETH",
    "SOL",
    "HYPE",
    "XRP",
    "ARB",
    "OP",
    "SUI",
    "AVAX",
    "APT",
    "LINK",
    "NEAR",
    "LTC",
    "BCH",
    "XLM",
    "ADA",
    "DOT",
    "STX",
    "POL",
    "TIA",
]


def _parse_symbol_list(raw: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for part in str(raw or "").replace("\n", ",").split(","):
        sym = part.strip().upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


def _get_default_symbols() -> list[str]:
    # In "sidecar-only" market-data mode, avoid direct HL REST calls from python.
    # (Orders/execution can still use REST elsewhere.)
    rest_enabled = str(os.getenv("AI_QUANT_REST_ENABLE", "1") or "1").strip().lower() in {"1", "true", "yes", "y", "on"}
    if not rest_enabled:
        return list(_FALLBACK_SYMBOLS)
    try:
        top_n = int(os.getenv("AI_QUANT_TOP_N", "50"))
    except Exception:
        top_n = 50
    top_n = max(1, min(200, top_n))
    try:
        syms = hyperliquid_meta.top_symbols_by_day_notional_volume(top_n)
        if syms:
            return syms
    except Exception as e:
        logger.warning(f"⚠️ Failed to auto-select top {top_n} symbols from Hyperliquid: {e}")
    return list(_FALLBACK_SYMBOLS)


_env_symbols = os.getenv("AI_QUANT_SYMBOLS", "").strip()
SYMBOLS = _parse_symbol_list(_env_symbols) if _env_symbols else _get_default_symbols()

INTERVAL = str(os.getenv("AI_QUANT_INTERVAL", "1h") or "1h").strip() or "1h"
try:
    LOOKBACK_HOURS = int(os.getenv("AI_QUANT_LOOKBACK_BARS", "200"))
except Exception:
    LOOKBACK_HOURS = 200
LOOKBACK_HOURS = int(max(50, min(10_000, LOOKBACK_HOURS)))
try:
    PAPER_BALANCE = float(os.getenv("AI_QUANT_PAPER_BALANCE", "10000.0"))
except Exception:
    PAPER_BALANCE = 10000.0
SL_ATR_MULT = 1.5
TP_ATR_MULT = 4.0  # Match Rust backtester default
DB_PATH = os.getenv(
    "AI_QUANT_DB_PATH",
    os.path.join(_THIS_DIR, "..", "trading_engine.db"),
)
try:
    _DB_TIMEOUT_S = float(os.getenv("AI_QUANT_DB_TIMEOUT_S", "30"))
except Exception:
    _DB_TIMEOUT_S = 30.0
DISCORD_CHANNEL = os.getenv("AI_QUANT_DISCORD_CHANNEL", "")

# Multi-trade allocation (paper perps): margin allocated per position (notional ≈ margin × leverage).
# Default (code-level): 3% margin per position. Prefer overriding via YAML:
#   config/strategy_overrides.yaml
# NOTE: This is a hardcoded fallback. Prefer overriding via get_strategy_config() / YAML.
try:
    ALLOCATION_PCT = float(os.getenv("AI_QUANT_ALLOCATION_PCT", "0.03"))
except Exception:
    ALLOCATION_PCT = 0.03  # Match Rust backtester default

# --- Hyperliquid (Perps) Costs ---
# Defaults from Hyperliquid fee schedule (VIP 0, Base): Taker 0.045%, Maker 0.015%.
# Adjust via env vars to match your account's 14d volume tier + staking tier discounts.
#
# Rate format is a decimal fraction, e.g. 0.00045 == 0.045%.
HL_PERP_TAKER_FEE_RATE = float(os.getenv("HL_PERP_TAKER_FEE_RATE", "0.00045"))
HL_PERP_MAKER_FEE_RATE = float(os.getenv("HL_PERP_MAKER_FEE_RATE", "0.00015"))
# Optional referral discount (e.g. 4 means 4% off the protocol fee).
HL_REFERRAL_DISCOUNT_PCT = float(os.getenv("HL_REFERRAL_DISCOUNT_PCT", "0"))
# Optional builder fee (additional fee rate, e.g. 0.0001 == 1bp == 0.01%).
HL_BUILDER_FEE_RATE = float(os.getenv("HL_BUILDER_FEE_RATE", "0.0"))
# Paper trader assumes marketable execution by default (taker).
HL_FEE_MODE = os.getenv("HL_FEE_MODE", "taker").strip().lower()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


# Funding is exchanged hourly between longs and shorts for perps.
HL_FUNDING_ENABLED = _env_bool("HL_FUNDING_ENABLED", True)
HL_DEFAULT_LEVERAGE = float(os.getenv("HL_DEFAULT_LEVERAGE", "3.0"))  # Match Rust default
HL_SLIPPAGE_BPS = float(os.getenv("HL_SLIPPAGE_BPS", "10.0"))  # Match Rust default


def _effective_fee_rate() -> float:
    """Returns the configured all-in fee rate for a single fill (protocol fee +/- discounts + optional builder fee)."""
    protocol_rate = HL_PERP_TAKER_FEE_RATE if HL_FEE_MODE != "maker" else HL_PERP_MAKER_FEE_RATE
    discount_mult = 1.0 - max(0.0, min(100.0, HL_REFERRAL_DISCOUNT_PCT)) / 100.0
    return (protocol_rate * discount_mult) + HL_BUILDER_FEE_RATE


# --- Strategy Overrides (Global + Per-Symbol) ---
# Strategy overrides live in YAML (preferred):
#   config/strategy_overrides.yaml
#
# Merge order: defaults ← global ← symbols.<SYMBOL>
# Only the fields you specify are overridden; everything else is inherited.
#
# DEPRECATED: TOML overrides are still supported for backward compatibility.
#   config/strategy_overrides.toml
STRATEGY_YAML_PATH = os.getenv(
    "AI_QUANT_STRATEGY_YAML", os.path.join(_THIS_DIR, "..", "config", "strategy_overrides.yaml")
)
STRATEGY_TOML_PATH = os.getenv(
    "AI_QUANT_STRATEGY_TOML", os.path.join(_THIS_DIR, "..", "config", "strategy_overrides.toml")
)

_DEFAULT_STRATEGY_CONFIG = {
    "trade": {
        "allocation_pct": ALLOCATION_PCT,
        "sl_atr_mult": 2.0,
        "tp_atr_mult": TP_ATR_MULT,
        "leverage": HL_DEFAULT_LEVERAGE,
        # v5.018: RSI Entry Extreme Filter (REEF) - block overextended entries.
        # v5.020: REEF v2 - Dynamic RSI limits based on ADX.
        "enable_reef_filter": True,
        "reef_long_rsi_block_gt": 70.0,  # baseline (ADX < 45)
        "reef_short_rsi_block_lt": 30.0,  # baseline (ADX < 45)
        "reef_adx_threshold": 45.0,
        "reef_long_rsi_extreme_gt": 75.0,  # extreme (ADX >= 45)
        "reef_short_rsi_extreme_lt": 25.0,  # extreme (ADX >= 45)
        # Dynamic leverage: scales leverage by signal confidence for NEW positions.
        # Adds (pyramiding) reuse existing position leverage to avoid thrash.
        "leverage_low": 1.0,
        "leverage_medium": 3.0,
        "leverage_high": 5.0,
        "slippage_bps": HL_SLIPPAGE_BPS,
        "use_bbo_for_fills": True,
        "min_notional_usd": 10.0,
        "bump_to_min_notional": False,
        "max_total_margin_pct": 0.60,
        # Dynamic sizing (less aggressive): scales margin by confidence + trend strength + volatility.
        "enable_dynamic_sizing": True,
        "confidence_mult_high": 1.0,
        "confidence_mult_medium": 0.7,
        "confidence_mult_low": 0.5,
        "adx_sizing_min_mult": 0.6,
        "adx_sizing_full_adx": 40.0,
        "vol_baseline_pct": 0.01,
        "vol_scalar_min": 0.5,
        "vol_scalar_max": 1.0,
        # Position building / scaling
        "enable_pyramiding": True,
        "max_adds_per_symbol": 2,
        "add_fraction_of_base_margin": 0.5,
        "add_cooldown_minutes": 60,
        "add_min_profit_atr": 0.5,
        "add_min_confidence": "medium",
        "entry_min_confidence": "high",
        # Partial exits (take-profit ladder)
        "enable_partial_tp": True,
        "tp_partial_pct": 0.5,
        "tp_partial_min_notional_usd": 10.0,
        "tp_partial_atr_mult": 0.0,  # 0 = use tp_atr_mult (same level). >0 = separate partial TP level.
        "trailing_start_atr": 1.0,
        "trailing_distance_atr": 0.8,
        # v5.037: Make SSF and breakeven configurable (defaults preserve prior behavior).
        "enable_ssf_filter": True,
        "enable_breakeven_stop": True,
        "breakeven_start_atr": 0.7,
        "breakeven_buffer_atr": 0.05,
        # v5.046: RSI Overextension Exit is now configurable (defaults preserve prior behavior).
        # This is a *smart exit* (not an entry filter) used to take profit in extreme RSI regimes.
        "enable_rsi_overextension_exit": True,
        "rsi_exit_profit_atr_switch": 1.5,
        "rsi_exit_ub_lo_profit": 80.0,
        "rsi_exit_ub_hi_profit": 70.0,
        "rsi_exit_lb_lo_profit": 20.0,
        "rsi_exit_lb_hi_profit": 30.0,
        # v5.015: ADX-Adaptive PESC.
        # v5.017: SRC - Increased minimums to filter noise.
        # v5.018: Enhanced weak-trend cooldown (ADX < 25 => 180m).
        "reentry_cooldown_minutes": 60,
        "reentry_cooldown_min_mins": 45,
        "reentry_cooldown_max_mins": 180,
        # v5.015: Volatility-Buffered Trailing Stop.
        "enable_vol_buffered_trailing": True,
        # v5.001: Trend Saturation Momentum Exit (TSME) extra gate
        # Only allow the "ADX>50 + momentum contraction" exit if:
        # - the position has at least `tsme_min_profit_atr` profit, AND
        # - ADX slope is negative (trend strength is no longer accelerating),
        # to reduce premature exits on normal pullbacks within strong trends.
        "tsme_min_profit_atr": 1.0,
        "tsme_require_adx_slope_negative": True,
        "min_atr_pct": 0.003,
        "reverse_entry_signal": False,
        "block_exits_on_extreme_dev": False,
        "glitch_price_dev_pct": 0.40,
        "glitch_atr_mult": 12.0,
        # --- Per-confidence trailing overrides (0 = use main value) ---
        "trailing_start_atr_low_conf": 0.0,
        "trailing_distance_atr_low_conf": 0.0,
        # --- Smart exit ADX exhaustion ---
        "smart_exit_adx_exhaustion_lt": 18.0,
        "smart_exit_adx_exhaustion_lt_low_conf": 0.0,
        # --- RSI overextension exit - low confidence overrides (0 = use main) ---
        "rsi_exit_ub_lo_profit_low_conf": 0.0,
        "rsi_exit_ub_hi_profit_low_conf": 0.0,
        "rsi_exit_lb_lo_profit_low_conf": 0.0,
        "rsi_exit_lb_hi_profit_low_conf": 0.0,
        # --- Rate limits / capacity ---
        "max_open_positions": 20,
        "entry_cooldown_s": 20,
        "exit_cooldown_s": 15,
        "max_entry_orders_per_loop": 6,
    },
    "indicators": {
        "ema_slow_window": 50,
        "ema_fast_window": 20,
        "ema_macro_window": 200,
        "adx_window": 14,
        "bb_window": 20,
        "bb_width_avg_window": 30,
        "atr_window": 14,
        "rsi_window": 14,
        "vol_sma_window": 20,
        "vol_trend_window": 5,
        "stoch_rsi_window": 14,
        "stoch_rsi_smooth1": 3,
        "stoch_rsi_smooth2": 3,
    },
    "filters": {
        "enable_ranging_filter": True,
        "enable_anomaly_filter": True,
        # v5.042: Extension filter toggle (distance-to-EMA_fast gate).
        "enable_extension_filter": True,
        "require_adx_rising": True,
        "adx_rising_saturation": 40.0,
        "require_volume_confirmation": False,
        "vol_confirm_include_prev": True,
        "use_stoch_rsi_filter": True,
        "require_btc_alignment": True,
        "require_macro_alignment": False,
    },
    "market_regime": {
        "enable_regime_filter": False,
        "breadth_block_short_above": 90.0,
        "breadth_block_long_below": 10.0,
        "enable_auto_reverse": False,
        "auto_reverse_breadth_low": 10.0,
        "auto_reverse_breadth_high": 90.0,
        # Global regime gate (engine-only): block entries when the regime is not trend OK.
        "enable_regime_gate": False,
        "regime_gate_breadth_low": 20.0,
        "regime_gate_breadth_high": 80.0,
        "regime_gate_btc_adx_min": 20.0,
        "regime_gate_btc_atr_pct_min": 0.003,
        "regime_gate_fail_open": False,
    },
    "watchlist_exclude": [],
    "thresholds": {
        "entry": {
            "min_adx": 22.0,
            "high_conf_volume_mult": 2.5,
            "btc_adx_override": 40.0,
            "max_dist_ema_fast": 0.04,
            # v5.042: Adaptive Volatility Entry (AVE) is now configurable.
            "ave_enabled": True,
            "ave_atr_ratio_gt": 1.5,
            "ave_adx_mult": 1.25,
            "ave_avg_atr_window": 50,
            # v5.042: MACD gating mode for trend entries.
            # - accel: require MACD_hist > prev_MACD_hist (legacy)
            # - sign : require MACD_hist > 0 for BUY, < 0 for SELL
            # - none : ignore MACD_hist gate
            "macd_hist_entry_mode": "accel",
            # v5.042: Pullback continuation entries (off by default).
            "enable_pullback_entries": False,
            "pullback_confidence": "low",
            "pullback_min_adx": 22.0,
            "pullback_rsi_long_min": 50.0,
            "pullback_rsi_short_max": 50.0,
            "pullback_require_macd_sign": True,
            # v5.040: Slow drift entry mode (off by default; enable via YAML).
            # Goal: capture low-vol grind regimes as low-confidence entries.
            "enable_slow_drift_entries": False,
            "slow_drift_slope_window": 20,
            "slow_drift_min_slope_pct": 0.0006,
            "slow_drift_min_adx": 10.0,
            "slow_drift_rsi_long_min": 50.0,
            "slow_drift_rsi_short_max": 50.0,
            "slow_drift_require_macd_sign": True,
        },
        "ranging": {
            "min_signals": 2,
            "adx_below": 21.0,
            "bb_width_ratio_below": 0.8,
            "rsi_low": 47.0,
            "rsi_high": 53.0,
        },
        "anomaly": {
            "price_change_pct_gt": 0.10,
            "ema_fast_dev_pct_gt": 0.50,
        },
        "tp_and_momentum": {
            "adx_strong_gt": 40.0,
            "adx_weak_lt": 30.0,
            "tp_mult_strong": 7.0,
            "tp_mult_weak": 3.0,
            "rsi_long_strong": 52.0,
            "rsi_long_weak": 56.0,
            "rsi_short_strong": 48.0,
            "rsi_short_weak": 44.0,
        },
        "stoch_rsi": {
            "block_long_if_k_gt": 0.85,
            "block_short_if_k_lt": 0.15,
        },
    },
}

# v5 StrategyManager integration:
# - hot reloads YAML by file mtime (no module reload required)
# - provides a unified watchlist source for the unified engine loop
_strategy_mgr = None
# Prefer the newest StrategyManager if multiple versions exist.
try:
    from engine.strategy_manager import StrategyManager as _QTStrategyManager
except ImportError:
    try:
        from quant_trader_v4.strategy_manager import StrategyManager as _QTStrategyManager
    except ImportError:
        try:
            from quant_trader_v3.strategy_manager import StrategyManager as _QTStrategyManager
        except ImportError:
            _QTStrategyManager = None

if _QTStrategyManager is not None:
    try:
        _strategy_mgr = _QTStrategyManager.bootstrap(
            defaults=_DEFAULT_STRATEGY_CONFIG,
            yaml_path=STRATEGY_YAML_PATH,
            changelog_path=os.path.join(_THIS_DIR, "..", "strategy_changelog.json"),
            watchlist_refresh_s=float(os.getenv("AI_QUANT_WATCHLIST_REFRESH_S", "60")),
        )
    except Exception as e:
        logger.warning(f"⚠️ StrategyManager bootstrap failed; falling back to legacy overrides. Error: {e}")
        _strategy_mgr = None


_RUN_FINGERPRINT = str(os.getenv("AI_QUANT_RUN_FINGERPRINT", "") or "").strip() or None


def set_run_fingerprint(value: str | None) -> None:
    """Set the process-wide run fingerprint used for audit persistence."""
    global _RUN_FINGERPRINT
    text = str(value or "").strip()
    _RUN_FINGERPRINT = text or None
    if text:
        os.environ["AI_QUANT_RUN_FINGERPRINT"] = text
    else:
        os.environ.pop("AI_QUANT_RUN_FINGERPRINT", None)


def get_run_fingerprint() -> str:
    """Return the current run fingerprint, or ``"unknown"`` when unset."""
    global _RUN_FINGERPRINT
    if _RUN_FINGERPRINT:
        return _RUN_FINGERPRINT
    text = str(os.getenv("AI_QUANT_RUN_FINGERPRINT", "") or "").strip()
    if text:
        _RUN_FINGERPRINT = text
        return text
    return "unknown"


def _canonical_action_code_for_reason(action: str, pos_type: str | None) -> str:
    act = str(action or "").strip().upper()
    side = str(pos_type or "").strip().upper()
    if act in {"OPEN", "ADD", "CLOSE", "REDUCE"} and side in {"LONG", "SHORT"}:
        return f"{act}_{side}"
    if act == "FUNDING":
        return "FUNDING"
    return act


def canonical_reason_code_for_trade(action: str, pos_type: str | None, reason: str | None) -> str:
    """Return canonical machine-readable reason code for a trade event."""
    try:
        from tools.reason_codes import classify_reason_code
    except Exception:
        return "unknown"
    action_code = _canonical_action_code_for_reason(action, pos_type)
    if not action_code:
        return "unknown"
    try:
        code = str(classify_reason_code(action_code, str(reason or "")) or "").strip().lower()
    except Exception:
        code = ""
    return code or "unknown"


def _deep_merge(base: dict, override: dict) -> dict:
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base


def _load_strategy_overrides() -> dict:
    try:
        if os.path.exists(STRATEGY_YAML_PATH):
            with open(STRATEGY_YAML_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return data if isinstance(data, dict) else {}

        if os.path.exists(STRATEGY_TOML_PATH):
            with open(STRATEGY_TOML_PATH, "rb") as f:
                return tomllib.load(f)
        return {}
    except Exception as e:
        logger.warning(
            f"⚠️ Failed to load strategy overrides (yaml={STRATEGY_YAML_PATH}, toml={STRATEGY_TOML_PATH}): {e}"
        )
        return {}


# Legacy path (used only if StrategyManager failed to bootstrap):
# overrides are loaded once at import time and will NOT hot-reload.
_STRATEGY_OVERRIDES = _load_strategy_overrides()


def get_strategy_config(symbol: str) -> dict:
    symbol = (symbol or "").upper()

    # Preferred path: StrategyManager (YAML hot reload without module reload).
    if _strategy_mgr is not None:
        cfg = _strategy_mgr.get_config(symbol)
    else:
        cfg = copy.deepcopy(_DEFAULT_STRATEGY_CONFIG)
        overrides = _STRATEGY_OVERRIDES or {}

        _deep_merge(cfg, overrides.get("global") or {})
        _deep_merge(cfg, (overrides.get("symbols") or {}).get(symbol) or {})

        # Live mode can override settings separately (safer for small accounts).
        mode = str(os.getenv("AI_QUANT_MODE", "paper") or "paper").strip().lower()
        if mode in {"live", "dry_live"}:
            live_over = overrides.get("live") or {}
            if isinstance(live_over, dict):
                if "global" in live_over or "symbols" in live_over:
                    _deep_merge(cfg, live_over.get("global") or {})
                    _deep_merge(cfg, (live_over.get("symbols") or {}).get(symbol) or {})
                else:
                    # Shorthand: live: {trade: {...}, filters: {...}, ...}
                    _deep_merge(cfg, live_over)

    # Safe defaults for live (override via YAML `live:` or env vars).
    mode2 = str(os.getenv("AI_QUANT_MODE", "paper") or "paper").strip().lower()
    if mode2 in {"live", "dry_live"}:
        trade_cfg = cfg.get("trade") or {}
        if "max_open_positions" not in trade_cfg:
            try:
                trade_cfg["max_open_positions"] = int(os.getenv("AI_QUANT_LIVE_MAX_OPEN_POSITIONS", "1"))
            except Exception:
                trade_cfg["max_open_positions"] = 1
        if "max_notional_usd_per_order" not in trade_cfg:
            try:
                trade_cfg["max_notional_usd_per_order"] = float(
                    os.getenv("AI_QUANT_LIVE_MAX_NOTIONAL_USD_PER_ORDER", "15.0")
                )
            except Exception:
                trade_cfg["max_notional_usd_per_order"] = 15.0
        if "min_margin_usd" not in trade_cfg:
            try:
                trade_cfg["min_margin_usd"] = float(os.getenv("AI_QUANT_LIVE_MIN_MARGIN_USD", "6.0"))
            except Exception:
                trade_cfg["min_margin_usd"] = 6.0
        cfg["trade"] = trade_cfg

    # Normalize the top-level keys so downstream code can assume dicts.
    for key in ("trade", "indicators", "filters", "thresholds", "market_regime"):
        if not isinstance(cfg.get(key), dict):
            cfg[key] = {}

    # ── Sync indicators.ave_avg_atr_window ↔ thresholds.entry.ave_avg_atr_window ──
    # The Rust backtester keeps both in lock-step (set_ave_avg_atr_window).
    # The Python engine only reads thresholds.entry.ave_avg_atr_window, so
    # propagate a sweep-set indicators value into the threshold path.
    # If the user explicitly set the threshold path, that takes precedence.
    try:
        _ind_aaw = cfg["indicators"].get("ave_avg_atr_window")
        _thr_entry = cfg["thresholds"].setdefault("entry", {})
        _thr_aaw = _thr_entry.get("ave_avg_atr_window")
        if _ind_aaw is not None and _thr_aaw is None:
            _thr_entry["ave_avg_atr_window"] = int(_ind_aaw)
        elif _ind_aaw is not None and _thr_aaw is not None:
            # Both set: indicators path takes precedence (matches Rust sweep
            # behaviour where either path calls set_ave_avg_atr_window and
            # syncs both).  Only override when they differ.
            if int(_ind_aaw) != int(_thr_aaw):
                _thr_entry["ave_avg_atr_window"] = int(_ind_aaw)
    except Exception:
        pass

    return cfg


def get_trade_params(symbol: str) -> dict:
    return get_strategy_config(symbol).get("trade") or {}


def _safe_float(val, default: float | None = None) -> float | None:
    try:
        if val is None:
            return default
        v = float(val)
        if v != v:  # NaN check
            return default
        return v
    except Exception:
        return default


_CONF_RANK = {"low": 0, "medium": 1, "high": 2}


def _conf_ok(confidence: str | None, *, min_confidence: str) -> bool:
    c = str(confidence or "low").strip().lower()
    m = str(min_confidence or "low").strip().lower()
    return _CONF_RANK.get(c, 0) >= _CONF_RANK.get(m, 0)


def _conf_bucket(confidence: str | None) -> str:
    c = str(confidence or "low").strip().lower()
    if c.startswith("h"):
        return "high"
    if c.startswith("m"):
        return "medium"
    return "low"


def _select_leverage(trade_cfg: dict, confidence: str | None) -> float:
    """
    Returns the leverage to use for a NEW position.
    Always uses leverage_low/medium/high by confidence bucket.
    Falls back to `trade.leverage` if the per-tier key is missing.
    NOTE: Adds (pyramiding) reuse the existing position leverage to avoid thrash.
    """
    try:
        fallback = float(trade_cfg.get("leverage", HL_DEFAULT_LEVERAGE))
    except Exception:
        fallback = float(HL_DEFAULT_LEVERAGE or 1.0)

    b = _conf_bucket(confidence)
    key = "leverage_high" if b == "high" else ("leverage_medium" if b == "medium" else "leverage_low")
    try:
        lev = float(trade_cfg.get(key, fallback))
    except Exception:
        lev = fallback

    try:
        lev = float(lev)
    except Exception:
        lev = 1.0
    return max(1.0, lev)


@dataclass(frozen=True)
class EntrySizing:
    margin_usd: float
    leverage: float
    desired_notional_usd: float


def compute_entry_sizing(
    *,
    symbol: str,
    equity_base: float,
    price: float,
    confidence: str | None,
    atr: float,
    indicators: dict | None,
    trade_cfg: dict,
    thresholds: dict,
) -> EntrySizing:
    """
    Shared sizing logic for NEW positions (paper + live).

    - `allocation_pct` is treated as MARGIN allocation (not notional).
    - Notional ≈ margin × leverage.
    - Dynamic sizing (optional) scales margin by confidence + ADX + volatility.
    - Dynamic leverage (optional) scales leverage by confidence.

    The caller is responsible for:
    - checking portfolio-level margin caps / available margin
    - enforcing per-order notional caps (live)
    - computing size from notional using a fill price and rounding rules
    """
    sym = str(symbol or "").strip().upper()
    try:
        equity = float(equity_base)
    except Exception:
        equity = 0.0
    equity = max(0.0, equity)

    try:
        px = float(price)
    except Exception:
        px = 0.0
    px = max(0.0, px)

    try:
        allocation_pct = float(trade_cfg.get("allocation_pct", ALLOCATION_PCT))
    except Exception:
        # Fallback: should come from get_strategy_config() / YAML, not this hardcoded constant.
        allocation_pct = float(ALLOCATION_PCT or 0.0)
        logger.warning("Using hardcoded ALLOCATION_PCT fallback (%.4f) — check strategy config", allocation_pct)
    allocation_pct = max(0.0, allocation_pct)

    margin_target = equity * allocation_pct

    # Dynamic sizing: scale margin by confidence + trend strength + volatility.
    if bool(trade_cfg.get("enable_dynamic_sizing", True)):
        # 1) Confidence scaling.
        b = _conf_bucket(confidence)
        key = (
            "confidence_mult_high"
            if b == "high"
            else ("confidence_mult_medium" if b == "medium" else "confidence_mult_low")
        )
        try:
            conf_mult = float(trade_cfg.get(key, 1.0))
        except Exception:
            conf_mult = 1.0
        margin_target *= max(0.0, conf_mult)

        # 2) ADX scaling (smaller size near the entry threshold).
        adx_val = None
        if indicators is not None:
            adx_val = _safe_float(indicators.get("ADX"), None)
        min_adx = _safe_float(((thresholds.get("entry") or {}).get("min_adx")), 0.0) or 0.0
        try:
            full_adx = float(trade_cfg.get("adx_sizing_full_adx", 40.0))
        except Exception:
            full_adx = 40.0
        try:
            min_mult = float(trade_cfg.get("adx_sizing_min_mult", 0.6))
        except Exception:
            min_mult = 0.6
        if adx_val is not None and full_adx > min_adx:
            t = (float(adx_val) - float(min_adx)) / (float(full_adx) - float(min_adx))
            t = max(0.0, min(1.0, t))
            adx_mult = min_mult + t * (1.0 - min_mult)
            margin_target *= max(0.0, adx_mult)

    # ATR-Based sizing: keep approx dollar risk stable across vol regimes.
    try:
        atr_f = float(atr or 0.0)
    except Exception:
        atr_f = 0.0
    if atr_f > 0 and px > 0:
        try:
            baseline_pct = float(trade_cfg.get("vol_baseline_pct", 0.01))
        except Exception:
            baseline_pct = 0.01
        baseline_vol = px * baseline_pct
        if baseline_vol > 0:
            vol_scalar = baseline_vol / atr_f
            try:
                vol_min = float(trade_cfg.get("vol_scalar_min", 0.5))
            except Exception:
                vol_min = 0.5
            try:
                vol_max = float(trade_cfg.get("vol_scalar_max", 1.0))
            except Exception:
                vol_max = 1.0
            vol_scalar = max(vol_min, min(vol_max, vol_scalar))
            margin_target *= max(0.0, vol_scalar)

    # Optional size multiplier (used for live rollout ramps, etc).
    try:
        size_mult = float(trade_cfg.get("size_multiplier", 1.0))
    except Exception:
        size_mult = 1.0
    size_mult = max(0.0, float(size_mult))
    margin_target *= float(size_mult)

    # Optional floor clamp (primarily for live so you clear min-notional after rounding).
    min_margin = _safe_float(trade_cfg.get("min_margin_usd"), None)
    if min_margin is not None and float(min_margin) > 0:
        margin_target = max(float(margin_target), float(min_margin))

    lev = _select_leverage(trade_cfg, confidence)
    desired_notional = float(margin_target) * float(lev)

    # Cap to max leverage tier (best-effort, based on desired notional before rounding).
    max_lev = hyperliquid_meta.max_leverage(sym, desired_notional)
    if max_lev is not None and lev > float(max_lev):
        lev = max(1.0, float(max_lev))
        desired_notional = float(margin_target) * float(lev)

    return EntrySizing(
        margin_usd=float(margin_target), leverage=float(lev), desired_notional_usd=float(desired_notional)
    )


def size_for_notional_bounds(
    symbol: str,
    *,
    price: float,
    desired_notional: float,
    min_notional: float,
    max_notional: float | None = None,
) -> float:
    """
    Computes an order size that:
    - is rounded to szDecimals
    - satisfies min_notional (after rounding)
    - respects max_notional (if provided)

    Preference: stay close to desired_notional without violating constraints.
    """
    sym = str(symbol or "").strip().upper()
    try:
        px = float(price)
    except Exception:
        px = 0.0
    if not sym or px <= 0:
        return 0.0

    try:
        desired = float(desired_notional)
    except Exception:
        desired = 0.0
    try:
        min_ntl = float(min_notional)
    except Exception:
        min_ntl = 0.0
    if min_ntl <= 0:
        min_ntl = 0.0

    min_sz = hyperliquid_meta.min_size_for_notional(sym, min_ntl, px)
    if min_sz <= 0:
        return 0.0

    max_ntl = None if max_notional is None else _safe_float(max_notional, None)
    if max_ntl is not None and float(max_ntl) > 0:
        max_sz = hyperliquid_meta.round_size(sym, float(max_ntl) / px)
        if max_sz <= 0 or (min_sz - max_sz) > 1e-12:
            return 0.0
        target_sz = hyperliquid_meta.round_size(sym, desired / px)
        sz = max(min_sz, min(target_sz, max_sz))
        return float(sz)

    target_sz = hyperliquid_meta.round_size(sym, desired / px)
    return float(max(min_sz, target_sz))


def _get_fill_price(
    symbol: str,
    side: str,
    fallback_price: float,
    *,
    slippage_bps: float,
    use_bbo_for_fills: bool,
) -> float:
    """
    Approximates execution price using WS BBO (bid/ask) + optional slippage.
    - Taker-style (default): BUY fills at ask, SELL fills at bid
    - Maker-style (`HL_FEE_MODE=maker`): BUY fills at bid, SELL fills at ask (assumes immediate passive fill)
    """
    sym = (symbol or "").upper()
    side_u = (side or "").upper()

    px = None
    if use_bbo_for_fills:
        # BBO can be stale for thin markets; treat old quotes as missing.
        bbo = hyperliquid_ws.hl_ws.get_bbo(sym, max_age_s=15.0)
        if bbo is not None:
            bid, ask = bbo
            if bid and ask and bid > 0 and ask > 0:
                # Maker fills are typically at the passive side of the spread.
                if HL_FEE_MODE == "maker":
                    px = bid if side_u == "BUY" else ask
                else:
                    px = ask if side_u == "BUY" else bid

    if px is None:
        mid = hyperliquid_ws.hl_ws.get_mid(sym, max_age_s=10.0)
        px = float(mid) if mid is not None else float(fallback_price)

    # Market impact slippage (bps). Apply only for taker-style execution.
    slip_bps = float(slippage_bps or 0.0)
    if slip_bps > 0 and HL_FEE_MODE != "maker":
        slip = slip_bps / 10000.0
        px = px * (1.0 + slip) if side_u == "BUY" else px * (1.0 - slip)

    return float(px)


def get_data(symbol):
    """
    Primary data fetcher: Hyperliquid websocket candle stream (backed by local DB cache).
    """
    sym = (symbol or "").upper()
    hyperliquid_ws.hl_ws.ensure_started(
        symbols=[sym],
        interval=INTERVAL,
        candle_limit=LOOKBACK_HOURS + 50,
    )
    return hyperliquid_ws.hl_ws.get_candles_df(sym, INTERVAL, min_rows=LOOKBACK_HOURS)


def ensure_db():
    conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id TEXT PRIMARY KEY,
            applied_at TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            type TEXT, -- LONG / SHORT
            action TEXT, -- OPEN / ADD / REDUCE / CLOSE / FUNDING / SYSTEM ...
            price REAL,
            size REAL,
            notional REAL,
            reason TEXT,
            reason_code TEXT,
            confidence TEXT,
            pnl REAL,
            fee_usd REAL,
            fee_token TEXT,
            fee_rate REAL,
            balance REAL,
            entry_atr REAL,
            leverage REAL,
            margin_used REAL,
            meta_json TEXT,
            run_fingerprint TEXT,
            fill_hash TEXT,
            fill_tid INTEGER
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS position_state (
            symbol TEXT PRIMARY KEY,
            open_trade_id INTEGER,
            trailing_sl REAL,
            last_funding_time INTEGER,
            updated_at TEXT
        )
        """
    )

    # Migration: ensure `last_funding_time` exists (legacy DBs)
    cursor.execute("PRAGMA table_info(position_state)")
    state_cols = {row[1] for row in cursor.fetchall()}
    if "last_funding_time" not in state_cols:
        cursor.execute("ALTER TABLE position_state ADD COLUMN last_funding_time INTEGER")
    if "adds_count" not in state_cols:
        cursor.execute("ALTER TABLE position_state ADD COLUMN adds_count INTEGER")
    if "tp1_taken" not in state_cols:
        cursor.execute("ALTER TABLE position_state ADD COLUMN tp1_taken INTEGER")
    if "last_add_time" not in state_cols:
        cursor.execute("ALTER TABLE position_state ADD COLUMN last_add_time INTEGER")
    if "entry_adx_threshold" not in state_cols:
        cursor.execute("ALTER TABLE position_state ADD COLUMN entry_adx_threshold REAL")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS position_state_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_ts_ms INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            symbol TEXT NOT NULL,
            open_trade_id INTEGER,
            trailing_sl REAL,
            last_funding_time INTEGER,
            adds_count INTEGER,
            tp1_taken INTEGER,
            last_add_time INTEGER,
            entry_adx_threshold REAL,
            event_type TEXT NOT NULL,
            run_fingerprint TEXT
        )
        """
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_position_state_history_symbol_ts ON position_state_history(symbol, event_ts_ms)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_position_state_history_open_trade_ts ON position_state_history(open_trade_id, event_ts_ms)"
    )

    # Helpful indexes for restart-safe position reconstruction.
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol_action_id ON trades(symbol, action, id)")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            signal TEXT,
            confidence TEXT,
            price REAL,
            rsi REAL,
            ema_fast REAL,
            ema_slow REAL,
            meta_json TEXT,
            run_fingerprint TEXT
        )
        """
    )

    # Migration: ensure `entry_atr` exists (legacy DBs)
    cursor.execute("PRAGMA table_info(trades)")
    cols = {row[1] for row in cursor.fetchall()}
    if "entry_atr" not in cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN entry_atr REAL")
    if "fee_usd" not in cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN fee_usd REAL")
    if "fee_token" not in cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN fee_token TEXT")
    if "fee_rate" not in cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN fee_rate REAL")
    if "leverage" not in cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN leverage REAL")
    if "margin_used" not in cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN margin_used REAL")
    if "fill_hash" not in cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN fill_hash TEXT")
    if "fill_tid" not in cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN fill_tid INTEGER")
    if "meta_json" not in cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN meta_json TEXT")
    if "run_fingerprint" not in cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN run_fingerprint TEXT")
    if "reason_code" not in cols:
        cursor.execute("ALTER TABLE trades ADD COLUMN reason_code TEXT")

    # Dedup live fills (userFills snapshots / reconnects) when available.
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_trades_fill_hash_tid ON trades(fill_hash, fill_tid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_run_fingerprint ON trades(run_fingerprint)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_trades_reason_code ON trades(reason_code)")

    # Live WS event capture (no-op for paper if unused).
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ws_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER,
            channel TEXT,
            data_json TEXT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ws_events_ts ON ws_events(ts)")

    # Structured audit events (paper + live). Prefer this for machine-auditable "why" logs
    # (entry blocks, order rejects, safety gates). For human-readable daemon output, see `runtime_logs`.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            symbol TEXT,
            event TEXT,
            level TEXT,
            data_json TEXT,
            run_fingerprint TEXT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_ts ON audit_events(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_symbol_ts ON audit_events(symbol, timestamp)")

    # Human-readable runtime logs captured from stdout/stderr (daemon, monitor, etc).
    # Prefer `audit_events` for structured, machine-auditable decision breadcrumbs.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_ms INTEGER NOT NULL,
            ts TEXT NOT NULL,
            pid INTEGER,
            mode TEXT,
            stream TEXT,
            level TEXT,
            message TEXT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_runtime_logs_ts_ms ON runtime_logs(ts_ms)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_runtime_logs_mode_ts_ms ON runtime_logs(mode, ts_ms)")

    # Persisted runtime cooldown state for deterministic restart/sync behaviour.
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_cooldowns (
            symbol TEXT PRIMARY KEY,
            last_entry_attempt_s REAL,
            last_exit_attempt_s REAL,
            updated_at TEXT
        )
        """
    )
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_runtime_cooldowns_updated_at ON runtime_cooldowns(updated_at)")

    # Migration: ensure `meta_json` exists on signals (optional, but useful for audits).
    cursor.execute("PRAGMA table_info(signals)")
    sig_cols = {row[1] for row in cursor.fetchall()}
    if "meta_json" not in sig_cols:
        cursor.execute("ALTER TABLE signals ADD COLUMN meta_json TEXT")
    if "run_fingerprint" not in sig_cols:
        cursor.execute("ALTER TABLE signals ADD COLUMN run_fingerprint TEXT")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_run_fingerprint ON signals(run_fingerprint)")

    cursor.execute("PRAGMA table_info(audit_events)")
    audit_cols = {row[1] for row in cursor.fetchall()}
    if "run_fingerprint" not in audit_cols:
        cursor.execute("ALTER TABLE audit_events ADD COLUMN run_fingerprint TEXT")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_run_fingerprint ON audit_events(run_fingerprint)")

    # One-time backfill for legacy rows (pre leverage/margin columns).
    migration_id = "2026-02-04_backfill_leverage_margin_used"
    cursor.execute("SELECT 1 FROM schema_migrations WHERE id = ?", (migration_id,))
    if cursor.fetchone() is None:
        cursor.execute("UPDATE trades SET leverage = 1.0 WHERE leverage IS NULL")
        cursor.execute(
            """
            UPDATE trades
            SET margin_used = notional / COALESCE(leverage, 1.0)
            WHERE margin_used IS NULL
              AND notional IS NOT NULL
              AND action IN ('OPEN', 'CLOSE')
            """
        )
        cursor.execute(
            "INSERT INTO schema_migrations (id, applied_at) VALUES (?, ?)",
            (migration_id, datetime.datetime.now(datetime.timezone.utc).isoformat()),
        )

    # ── Decision traceability tables (AQC-801) ───────────────────────────

    # Every decision point (entry signal, exit check, gate block, fill)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_events (
            id TEXT PRIMARY KEY,                    -- ULID for time-sortability
            timestamp_ms INTEGER NOT NULL,
            symbol TEXT NOT NULL,
            event_type TEXT NOT NULL,               -- 'entry_signal', 'exit_check', 'gate_block', 'fill', 'funding'
            status TEXT NOT NULL,                   -- 'executed', 'blocked', 'rejected', 'hold'
            decision_phase TEXT NOT NULL,           -- 'signal_generation', 'gate_evaluation', 'risk_check', 'execution'
            parent_decision_id TEXT,                -- chain to previous decision
            trade_id INTEGER,                       -- FK to trades.id if resulted in trade
            triggered_by TEXT,                      -- 'schedule', 'price_update', 'signal_flip', 'stop_loss'
            action_taken TEXT,                      -- 'open_long', 'close_short', 'hold', 'blocked'
            rejection_reason TEXT,                  -- if blocked/rejected
            reason_code TEXT,                       -- canonical machine-readable reason code
            config_fingerprint TEXT,                -- strategy config fingerprint at decision time
            run_fingerprint TEXT,                   -- process/run fingerprint at decision time
            context_json TEXT                       -- full indicator + threshold snapshot
        )
        """
    )
    cursor.execute("PRAGMA table_info(decision_events)")
    decision_event_cols = {str(row[1]) for row in cursor.fetchall()}
    if "config_fingerprint" not in decision_event_cols:
        cursor.execute("ALTER TABLE decision_events ADD COLUMN config_fingerprint TEXT")
    if "run_fingerprint" not in decision_event_cols:
        cursor.execute("ALTER TABLE decision_events ADD COLUMN run_fingerprint TEXT")
    if "reason_code" not in decision_event_cols:
        cursor.execute("ALTER TABLE decision_events ADD COLUMN reason_code TEXT")

    # Normalized indicator values at decision time (queryable without JSON parsing)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_context (
            decision_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            price REAL, rsi REAL, adx REAL, adx_slope REAL,
            macd_hist REAL, ema_fast REAL, ema_slow REAL, ema_macro REAL,
            bb_width_ratio REAL, stoch_k REAL, stoch_d REAL,
            atr REAL, atr_slope REAL, volume REAL, vol_sma REAL,
            -- Dynamic thresholds that were applied
            rsi_entry_threshold REAL,
            min_adx_threshold REAL,
            sl_price REAL, tp_price REAL, trailing_sl REAL,
            -- Gate status
            gate_ranging INTEGER, gate_anomaly INTEGER, gate_extension INTEGER,
            gate_adx INTEGER, gate_volume INTEGER, gate_adx_rising INTEGER,
            gate_btc_alignment INTEGER,
            -- Alignment
            bullish_alignment INTEGER, bearish_alignment INTEGER,
            FOREIGN KEY (decision_id) REFERENCES decision_events(id)
        )
        """
    )

    # Per-gate evaluation detail
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS gate_evaluations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT NOT NULL,
            gate_name TEXT NOT NULL,
            gate_passed INTEGER NOT NULL,           -- 0 or 1
            metric_value REAL,
            threshold_value REAL,
            operator TEXT,                           -- '<', '>', 'between', '=='
            explanation TEXT,
            FOREIGN KEY (decision_id) REFERENCES decision_events(id)
        )
        """
    )

    # Links signals to trades to exits (full lifecycle)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_lineage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_decision_id TEXT,                -- decision_events.id for entry signal
            entry_trade_id INTEGER,                 -- trades.id for OPEN fill
            exit_decision_id TEXT,                  -- decision_events.id for exit
            exit_trade_id INTEGER,                  -- trades.id for CLOSE fill
            exit_reason TEXT,
            duration_ms INTEGER,                    -- time from entry to exit
            FOREIGN KEY (signal_decision_id) REFERENCES decision_events(id),
            FOREIGN KEY (exit_decision_id) REFERENCES decision_events(id)
        )
        """
    )

    # Decision traceability indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_de_symbol_ts ON decision_events(symbol, timestamp_ms)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_de_event_type ON decision_events(event_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_de_trade_id ON decision_events(trade_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_de_config_fingerprint ON decision_events(config_fingerprint)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_de_run_fingerprint ON decision_events(run_fingerprint)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_de_reason_code ON decision_events(reason_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ge_decision ON gate_evaluations(decision_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dl_entry ON decision_lineage(entry_trade_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dl_exit ON decision_lineage(exit_trade_id)")

    conn.commit()
    try:
        os.chmod(DB_PATH, 0o600)
    except OSError:
        pass
    conn.close()


# ── ULID generator (AQC-801) ────────────────────────────────────────────

_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_ulid() -> str:
    """Generate a ULID (Universally Unique Lexicographically Sortable Identifier).

    Returns a 26-character, time-sortable unique ID using Crockford's Base32.
    No external dependency required.
    """
    t = int(time.time() * 1000)
    time_part = ""
    for _ in range(10):
        time_part = _ULID_ALPHABET[t & 0x1F] + time_part
        t >>= 5
    rand_part = "".join(random.choices(_ULID_ALPHABET, k=16))
    return time_part + rand_part


# ── Decision traceability helpers (AQC-801) ──────────────────────────────


def create_decision_event(
    symbol: str,
    event_type: str,
    status: str,
    phase: str,
    *,
    parent_decision_id: str | None = None,
    trade_id: int | None = None,
    triggered_by: str | None = None,
    action_taken: str | None = None,
    rejection_reason: str | None = None,
    reason_code: str | None = None,
    config_fingerprint: str | None = None,
    run_fingerprint: str | None = None,
    context: dict | None = None,
    timestamp_ms: int | None = None,
) -> str:
    """Create a decision event row and return its ULID.

    Parameters
    ----------
    symbol : str
        Trading symbol (e.g. "ETH").
    event_type : str
        One of 'entry_signal', 'exit_check', 'gate_block', 'fill', 'funding'.
    status : str
        One of 'executed', 'blocked', 'rejected', 'hold'.
    phase : str
        One of 'signal_generation', 'gate_evaluation', 'risk_check', 'execution'.
    parent_decision_id : str, optional
        ULID of a preceding decision in the chain.
    trade_id : int, optional
        FK to trades.id if this decision resulted in a trade.
    triggered_by : str, optional
        What triggered this decision ('schedule', 'price_update', 'signal_flip', 'stop_loss').
    action_taken : str, optional
        What the engine did ('open_long', 'close_short', 'hold', 'blocked').
    rejection_reason : str, optional
        Human-readable reason if status is 'blocked' or 'rejected'.
    context : dict, optional
        Full indicator + threshold snapshot (stored as JSON).
    timestamp_ms : int, optional
        Epoch ms; defaults to now.

    Returns
    -------
    str
        The ULID of the created decision event.
    """
    def _extract_config_fingerprint(ctx: dict | None, sym: str) -> str | None:
        if not isinstance(ctx, dict):
            ctx = {}

        def _as_dict(value: object) -> dict:
            return value if isinstance(value, dict) else {}

        audit = _as_dict(ctx.get("audit"))
        audit_strategy = _as_dict(audit.get("strategy"))
        direct_strategy = _as_dict(ctx.get("strategy"))
        meta_strategy = _as_dict(_as_dict(ctx.get("meta")).get("strategy"))

        sha_candidates = [
            audit_strategy.get("overrides_sha1"),
            direct_strategy.get("overrides_sha1"),
            meta_strategy.get("overrides_sha1"),
            ctx.get("strategy_overrides_sha1"),
        ]
        for candidate in sha_candidates:
            text = str(candidate or "").strip()
            if text:
                return text

        version_candidates = [
            audit_strategy.get("version"),
            direct_strategy.get("version"),
            meta_strategy.get("version"),
            ctx.get("strategy_version"),
        ]
        for candidate in version_candidates:
            text = str(candidate or "").strip()
            if text:
                return f"version:{text}"

        try:
            snap = _strategy_mgr.snapshot if _strategy_mgr is not None else None
            if snap is not None:
                text = str(getattr(snap, "overrides_sha1", "") or "").strip()
                if text:
                    return text
                version_text = str(getattr(snap, "version", "") or "").strip()
                if version_text:
                    return f"version:{version_text}"
        except Exception:
            pass

        try:
            cfg = get_strategy_config(sym)
            payload = json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            if payload:
                return hashlib.sha1(payload.encode("utf-8")).hexdigest()
        except Exception:
            pass
        try:
            payload = json.dumps(_DEFAULT_STRATEGY_CONFIG, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            if payload:
                return hashlib.sha1(payload.encode("utf-8")).hexdigest()
        except Exception:
            pass
        return "unknown"

    decision_id = generate_ulid()
    ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    cfg_fp = str(config_fingerprint or "").strip() or _extract_config_fingerprint(context, symbol)
    run_fp = str(run_fingerprint or "").strip() or get_run_fingerprint()
    raw_action = str(action_taken or "").strip().lower()
    raw_reason = str(rejection_reason or "").strip()
    ctx_dict = context if isinstance(context, dict) else {}

    def _extract_reason_hint(ctx: dict) -> str:
        candidates: list[object] = [
            ctx.get("rejection_reason"),
            ctx.get("reason"),
            ctx.get("gate_reason"),
            ctx.get("exit_reason"),
        ]
        meta = ctx.get("meta")
        if isinstance(meta, dict):
            candidates.extend(
                [
                    meta.get("rejection_reason"),
                    meta.get("reason"),
                    meta.get("gate_reason"),
                    meta.get("exit_reason"),
                ]
            )
            order = meta.get("order")
            if isinstance(order, dict):
                candidates.extend(
                    [
                        order.get("rejection_reason"),
                        order.get("reason"),
                    ]
                )
        for item in candidates:
            text = str(item or "").strip()
            if text:
                return text
        return ""

    def _extract_exit_kind_hint(ctx: dict) -> str:
        candidates: list[object] = [
            ctx.get("_exit_kind"),
            ctx.get("exit_kind"),
            ctx.get("exit_reason"),
            ctx.get("reason"),
        ]
        meta = ctx.get("meta")
        if isinstance(meta, dict):
            candidates.extend(
                [
                    meta.get("_exit_kind"),
                    meta.get("exit_kind"),
                    meta.get("exit_reason"),
                    meta.get("reason"),
                ]
            )
            order = meta.get("order")
            if isinstance(order, dict):
                candidates.extend(
                    [
                        order.get("_exit_kind"),
                        order.get("exit_kind"),
                        order.get("reason"),
                    ]
                )
        for item in candidates:
            text = str(item or "").strip().lower()
            if text:
                return text
        return ""

    if not raw_reason:
        raw_reason = _extract_reason_hint(ctx_dict)

    rc_text = str(reason_code or "").strip().lower()
    if not rc_text:
        if raw_action.startswith("open"):
            rc_text = "entry_signal"
        elif raw_action.startswith("add"):
            rc_text = "entry_pyramid"
        elif raw_action.startswith("close") or raw_action.startswith("reduce"):
            if not raw_reason:
                kind = _extract_exit_kind_hint(ctx_dict)
                if "stop" in kind and "trail" not in kind:
                    raw_reason = "Stop Loss"
                elif "trail" in kind:
                    raw_reason = "Trailing Stop"
                elif "take" in kind or "profit" in kind or "tp" == kind:
                    raw_reason = "Take Profit"
                elif "flip" in kind or "signal" in kind:
                    raw_reason = "Signal Flip"
            rc_text = canonical_reason_code_for_trade(raw_action, None, raw_reason)
        elif raw_action == "blocked":
            rc_text = "exit_filter" if raw_reason else "hold"
        elif raw_action == "hold":
            rc_text = "hold"
        elif raw_action in {"apply_funding", "funding"}:
            rc_text = "funding_payment"
        else:
            rc_text = "unknown"
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
        conn.execute(
            """
            INSERT INTO decision_events
                (id, timestamp_ms, symbol, event_type, status, decision_phase,
                 parent_decision_id, trade_id, triggered_by, action_taken,
                 rejection_reason, reason_code, config_fingerprint, run_fingerprint, context_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                ts,
                symbol.strip().upper(),
                event_type,
                status,
                phase,
                parent_decision_id,
                trade_id,
                triggered_by,
                action_taken,
                rejection_reason,
                rc_text,
                cfg_fp,
                run_fp,
                _json_dumps_safe(context) if context else None,
            ),
        )
        conn.commit()
    finally:
        if conn is not None:
            conn.close()
    return decision_id


def save_decision_context(
    decision_id: str,
    symbol: str,
    indicators: dict,
    thresholds: dict | None = None,
    gates: dict | None = None,
) -> None:
    """Save normalized indicator, threshold, and gate snapshots for a decision.

    Parameters
    ----------
    decision_id : str
        The ULID of the decision event.
    symbol : str
        Trading symbol.
    indicators : dict
        Keys may include: price, rsi, adx, adx_slope, macd_hist, ema_fast,
        ema_slow, ema_macro, bb_width_ratio, stoch_k, stoch_d, atr,
        atr_slope, volume, vol_sma.
    thresholds : dict, optional
        Keys may include: rsi_entry_threshold, min_adx_threshold, sl_price,
        tp_price, trailing_sl.
    gates : dict, optional
        Keys may include: gate_ranging, gate_anomaly, gate_extension,
        gate_adx, gate_volume, gate_adx_rising, gate_btc_alignment,
        bullish_alignment, bearish_alignment.  Values should be 0/1.
    """
    thresholds = thresholds or {}
    gates = gates or {}
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
        conn.execute(
            """
            INSERT OR REPLACE INTO decision_context
                (decision_id, symbol,
                 price, rsi, adx, adx_slope, macd_hist,
                 ema_fast, ema_slow, ema_macro,
                 bb_width_ratio, stoch_k, stoch_d,
                 atr, atr_slope, volume, vol_sma,
                 rsi_entry_threshold, min_adx_threshold,
                 sl_price, tp_price, trailing_sl,
                 gate_ranging, gate_anomaly, gate_extension,
                 gate_adx, gate_volume, gate_adx_rising,
                 gate_btc_alignment,
                 bullish_alignment, bearish_alignment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                symbol.strip().upper(),
                indicators.get("price"),
                indicators.get("rsi"),
                indicators.get("adx"),
                indicators.get("adx_slope"),
                indicators.get("macd_hist"),
                indicators.get("ema_fast"),
                indicators.get("ema_slow"),
                indicators.get("ema_macro"),
                indicators.get("bb_width_ratio"),
                indicators.get("stoch_k"),
                indicators.get("stoch_d"),
                indicators.get("atr"),
                indicators.get("atr_slope"),
                indicators.get("volume"),
                indicators.get("vol_sma"),
                thresholds.get("rsi_entry_threshold"),
                thresholds.get("min_adx_threshold"),
                thresholds.get("sl_price"),
                thresholds.get("tp_price"),
                thresholds.get("trailing_sl"),
                gates.get("gate_ranging"),
                gates.get("gate_anomaly"),
                gates.get("gate_extension"),
                gates.get("gate_adx"),
                gates.get("gate_volume"),
                gates.get("gate_adx_rising"),
                gates.get("gate_btc_alignment"),
                gates.get("bullish_alignment"),
                gates.get("bearish_alignment"),
            ),
        )
        conn.commit()
    finally:
        if conn is not None:
            conn.close()


def save_gate_evaluation(
    decision_id: str,
    gate_name: str,
    gate_passed: bool,
    *,
    metric_value: float | None = None,
    threshold_value: float | None = None,
    operator: str | None = None,
    explanation: str | None = None,
) -> None:
    """Record a single gate evaluation for a decision.

    Parameters
    ----------
    decision_id : str
        The ULID of the decision event.
    gate_name : str
        Name of the gate (e.g. 'ranging', 'anomaly', 'adx_rising').
    gate_passed : bool
        Whether this gate passed.
    metric_value : float, optional
        The actual metric value evaluated.
    threshold_value : float, optional
        The threshold the metric was compared against.
    operator : str, optional
        Comparison operator ('<', '>', 'between', '==').
    explanation : str, optional
        Human-readable explanation of the gate result.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
        conn.execute(
            """
            INSERT INTO gate_evaluations
                (decision_id, gate_name, gate_passed, metric_value,
                 threshold_value, operator, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision_id,
                gate_name,
                1 if gate_passed else 0,
                metric_value,
                threshold_value,
                operator,
                explanation,
            ),
        )
        conn.commit()
    finally:
        if conn is not None:
            conn.close()


def _log_gates_batch(decision_id: str, gates: list[dict]) -> None:
    """Batch-insert multiple gate evaluations for a single decision event.

    Each entry in *gates* is a dict with keys matching :func:`save_gate_evaluation`'s
    parameters: ``gate_name``, ``gate_passed``, and optional ``metric_value``,
    ``threshold_value``, ``operator``, ``explanation``.

    Uses a single transaction for minimal I/O overhead on the hot path.
    """
    if not gates:
        return
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executemany(
            """
            INSERT INTO gate_evaluations
                (decision_id, gate_name, gate_passed, metric_value,
                 threshold_value, operator, explanation)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    decision_id,
                    g["gate_name"],
                    1 if g.get("gate_passed") else 0,
                    g.get("metric_value"),
                    g.get("threshold_value"),
                    g.get("operator"),
                    g.get("explanation"),
                )
                for g in gates
            ],
        )
        conn.commit()
    except Exception as exc:
        logger.debug("_log_gates_batch: failed for decision %s: %s", decision_id, exc)
    finally:
        if conn is not None:
            conn.close()


def _log_gates_for_decision(decision_id: str, gates_dict: dict, values_dict: dict) -> None:
    """Log all gate evaluations for a decision event.

    Translates the ``audit["gates"]`` and ``audit["values"]`` dicts produced by
    :func:`analyze` into individual :table:`gate_evaluations` rows.

    Parameters
    ----------
    decision_id : str
        ULID of the parent decision event.
    gates_dict : dict
        The ``latest["audit"]["gates"]`` dict from analyze().
    values_dict : dict
        The ``latest["audit"]["values"]`` dict from analyze().
    """
    rows: list[dict] = []

    def _g(name: str, passed: bool, metric=None, threshold=None, op=None, expl=None):
        rows.append(
            {
                "gate_name": name,
                "gate_passed": passed,
                "metric_value": None if metric is None else float(metric),
                "threshold_value": None if threshold is None else float(threshold),
                "operator": op,
                "explanation": expl,
            }
        )

    try:
        adx_v = float(gates_dict.get("adx", 0))
        eff_min_adx = float(gates_dict.get("effective_min_adx", 0))
        _g("adx_gate", adx_v > eff_min_adx, adx_v, eff_min_adx, ">", f"ADX {adx_v:.2f} vs min {eff_min_adx:.2f}")

        _g(
            "ranging_filter",
            not gates_dict.get("is_ranging", False),
            explanation="composite: ADX+BB+RSI ranging signals",
        )

        _g(
            "anomaly_filter",
            not gates_dict.get("is_anomaly", False),
            explanation="composite: price_change_pct + ema_deviation",
        )

        is_ext = gates_dict.get("is_extended", False)
        dist_pct = float(gates_dict.get("dist_ema_fast", 0))
        max_dist = float(gates_dict.get("max_dist_ema_fast", 0.04))
        _g(
            "extension_filter",
            not is_ext,
            dist_pct,
            max_dist,
            "<=",
            f"dist_ema_fast={dist_pct:.4f} vs max={max_dist:.4f}",
        )

        _g("volume_confirm", bool(gates_dict.get("vol_confirm", False)), explanation="volume > vol_sma check")

        is_trending = gates_dict.get("is_trending_up", False)
        adx_slope = float(values_dict.get("adx_slope", 0))
        _g(
            "adx_rising",
            bool(is_trending),
            adx_slope,
            0,
            ">",
            f"adx_slope={adx_slope:.4f} or ADX>{gates_dict.get('adx', 0):.1f} saturated",
        )

        btc_ok_l = gates_dict.get("btc_ok_long", True)
        btc_ok_s = gates_dict.get("btc_ok_short", True)
        _g("btc_alignment", bool(btc_ok_l and btc_ok_s), explanation=f"btc_ok_long={btc_ok_l}, btc_ok_short={btc_ok_s}")

        ema_f = float(values_dict.get("ema_fast", 0))
        ema_s = float(values_dict.get("ema_slow", 0))
        _g(
            "ema_alignment",
            ema_f != ema_s,
            ema_f,
            ema_s,
            ">" if ema_f > ema_s else "<",
            f"ema_fast={ema_f:.4f} vs ema_slow={ema_s:.4f}",
        )

        if gates_dict.get("require_macro_alignment", False):
            ema_macro = float(values_dict.get("ema_macro", 0))
            _g(
                "macro_alignment",
                ema_s > ema_macro if ema_macro > 0 else True,
                ema_s,
                ema_macro,
                ">",
                f"ema_slow={ema_s:.4f} vs ema_macro={ema_macro:.4f}",
            )

    except Exception as exc:
        logger.debug("_log_gates_for_decision: gate build failed: %s", exc)

    _log_gates_batch(decision_id, rows)


def link_decision_to_trade(decision_id: str, trade_id: int) -> None:
    """Link an existing decision event to a trade by updating its trade_id."""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
        conn.execute(
            "UPDATE decision_events SET trade_id = ? WHERE id = ?",
            (trade_id, decision_id),
        )
        conn.commit()
    finally:
        if conn is not None:
            conn.close()


def create_lineage(
    signal_decision_id: str,
    entry_trade_id: int,
) -> int:
    """Start a lineage record when a new trade is opened.

    Parameters
    ----------
    signal_decision_id : str
        The ULID of the entry signal decision event.
    entry_trade_id : int
        The trades.id for the OPEN fill.

    Returns
    -------
    int
        The rowid of the created lineage record.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
        cur = conn.execute(
            """
            INSERT INTO decision_lineage
                (signal_decision_id, entry_trade_id)
            VALUES (?, ?)
            """,
            (signal_decision_id, entry_trade_id),
        )
        conn.commit()
        return cur.lastrowid  # type: ignore[return-value]
    finally:
        if conn is not None:
            conn.close()


def complete_lineage(
    entry_trade_id: int,
    exit_decision_id: str,
    exit_trade_id: int,
    exit_reason: str,
    duration_ms: int | None = None,
) -> None:
    """Complete a lineage record when a trade is closed.

    Parameters
    ----------
    entry_trade_id : int
        The trades.id for the OPEN fill (used to find the lineage row).
    exit_decision_id : str
        The ULID of the exit decision event.
    exit_trade_id : int
        The trades.id for the CLOSE fill.
    exit_reason : str
        Why the trade was closed (e.g. 'signal_flip', 'stop_loss', 'take_profit').
    duration_ms : int, optional
        Time from entry to exit in milliseconds.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
        conn.execute(
            """
            UPDATE decision_lineage
            SET exit_decision_id = ?,
                exit_trade_id = ?,
                exit_reason = ?,
                duration_ms = ?
            WHERE entry_trade_id = ?
              AND exit_decision_id IS NULL
            """,
            (exit_decision_id, exit_trade_id, exit_reason, duration_ms, entry_trade_id),
        )
        conn.commit()
    finally:
        if conn is not None:
            conn.close()


def get_decision_chain(trade_id: int) -> list[dict]:
    """Return the full decision chain for a given trade.

    Walks the ``decision_lineage`` row keyed by *entry_trade_id* (or
    *exit_trade_id*) and collects every linked ``decision_events`` row in
    chronological order (by ``timestamp_ms``).

    The returned chain typically contains:
      signal_decision -> entry_trade -> exit_decision -> exit_trade

    Parameters
    ----------
    trade_id : int
        The ``trades.id`` to look up.  Matches against both
        ``entry_trade_id`` and ``exit_trade_id`` in ``decision_lineage``.

    Returns
    -------
    list[dict]
        Each dict has keys matching the ``decision_events`` columns:
        ``id``, ``timestamp_ms``, ``symbol``, ``event_type``, ``status``,
        ``decision_phase``, ``parent_decision_id``, ``trade_id``,
        ``triggered_by``, ``action_taken``, ``rejection_reason``,
        ``context_json``.  Empty list when no lineage exists.
    """
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
        conn.row_factory = sqlite3.Row

        # Find lineage rows that reference this trade (as entry or exit).
        lineage_rows = conn.execute(
            """
            SELECT signal_decision_id, exit_decision_id,
                   entry_trade_id, exit_trade_id
            FROM decision_lineage
            WHERE entry_trade_id = ? OR exit_trade_id = ?
            """,
            (trade_id, trade_id),
        ).fetchall()

        if not lineage_rows:
            return []

        # Collect all decision IDs and trade IDs referenced by lineage.
        decision_ids: set[str] = set()
        trade_ids: set[int] = set()
        for row in lineage_rows:
            if row["signal_decision_id"]:
                decision_ids.add(row["signal_decision_id"])
            if row["exit_decision_id"]:
                decision_ids.add(row["exit_decision_id"])
            if row["entry_trade_id"] is not None:
                trade_ids.add(row["entry_trade_id"])
            if row["exit_trade_id"] is not None:
                trade_ids.add(row["exit_trade_id"])

        # Also include any decision_events directly linked to these trade_ids.
        if trade_ids:
            placeholders = ",".join("?" for _ in trade_ids)
            trade_linked = conn.execute(
                f"SELECT id FROM decision_events WHERE trade_id IN ({placeholders})",
                list(trade_ids),
            ).fetchall()
            for r in trade_linked:
                decision_ids.add(r["id"])

        if not decision_ids:
            return []

        # Fetch all matching decision events, ordered chronologically.
        placeholders = ",".join("?" for _ in decision_ids)
        events = conn.execute(
            f"""
            SELECT id, timestamp_ms, symbol, event_type, status,
                   decision_phase, parent_decision_id, trade_id,
                   triggered_by, action_taken, rejection_reason, context_json
            FROM decision_events
            WHERE id IN ({placeholders})
            ORDER BY timestamp_ms ASC, id ASC
            """,
            list(decision_ids),
        ).fetchall()

        return [dict(e) for e in events]
    finally:
        if conn is not None:
            conn.close()


def _compute_duration_ms(open_timestamp: str | None) -> int | None:
    """Compute milliseconds elapsed since *open_timestamp* until now.

    Parameters
    ----------
    open_timestamp : str or None
        ISO-8601 timestamp (with or without trailing ``Z``).

    Returns
    -------
    int or None
        Duration in milliseconds, or ``None`` if *open_timestamp* is falsy
        or cannot be parsed.
    """
    if not open_timestamp:
        return None
    try:
        ots = str(open_timestamp).replace("Z", "+00:00")
        odt = datetime.datetime.fromisoformat(ots)
        if odt.tzinfo is None:
            odt = odt.replace(tzinfo=datetime.timezone.utc)
        return int((datetime.datetime.now(datetime.timezone.utc) - odt).total_seconds() * 1000)
    except Exception:
        return None


def log_audit_event(
    symbol: str,
    event: str,
    *,
    level: str = "info",
    data: dict | None = None,
    timestamp: str | None = None,
) -> None:
    """
    Writes a structured audit event to SQLite.

    Use this for "decision chain" breadcrumbs (why we skipped an entry, why an order was rejected, etc).
    Keep payloads small and JSON-safe.
    """
    conn = None
    try:
        # Audit logs must never stall the engine loop (live mode) due to sqlite busy waits.
        try:
            timeout_s = float(os.getenv("AI_QUANT_AUDIT_DB_TIMEOUT_S", "0.2"))
        except Exception:
            timeout_s = 0.2
        timeout_s = float(max(0.01, min(2.0, timeout_s)))

        # Avoid calling ensure_db() here: it's relatively heavy and can take schema locks.
        # If the table is missing, the insert will fail and we drop the audit row.
        conn = sqlite3.connect(DB_PATH, timeout=timeout_s)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            pass
        cur = conn.cursor()
        ts = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()
        sym = str(symbol or "").strip().upper() or None
        cur.execute(
            "INSERT INTO audit_events (timestamp, symbol, event, level, data_json, run_fingerprint) VALUES (?, ?, ?, ?, ?, ?)",
            (
                ts,
                sym,
                str(event or ""),
                str(level or "info"),
                _json_dumps_safe(data) if data else None,
                get_run_fingerprint(),
            ),
        )
        conn.commit()

        # Best-effort structured event log (JSONL). This must never block trading.
        try:
            from engine.event_logger import emit_event

            emit_event(
                kind="audit",
                symbol=sym or symbol,
                data={
                    "event": str(event or ""),
                    "level": str(level or "info"),
                    "data": data or None,
                },
            )
        except Exception:
            pass
    except Exception:
        # Never let audit logging impact trading logic.
        pass
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


class PaperTrader:
    def __init__(self):
        self._seed_balance: float = PAPER_BALANCE  # only for kernel init seeding
        self.positions = {}  # symbol -> position_dict
        # Simulated rate-limit state (mirrors LiveTrader friction).
        self._last_entry_attempt_at_s: dict[str, float] = {}
        self._last_exit_attempt_at_s: dict[str, float] = {}
        self._entry_budget_remaining: int | None = None
        # Set when get_live_balance falls back to entry_price (WS + REST both failed).
        # execute_trade checks this before opening new positions.
        self._data_stale: bool = False
        # --- Rust kernel state delegation (AQC-742) ---
        self._kernel_state_json: str | None = None
        self._kernel_params_json: str | None = None
        self._kernel_available: bool = False
        self._shadow_report: ShadowReport = ShadowReport()
        self._init_kernel()
        ensure_db()
        self.load_state()

    @property
    def balance(self) -> float:
        """Authoritative realized balance from Rust kernel (AQC-755).

        All callers that previously read the manually-tracked ``self.balance``
        now transparently receive the kernel's ``cash_usd`` value.
        """
        if self._kernel_available:
            kb = self.get_kernel_balance()
            if kb is not None:
                return kb
        return self._seed_balance

    def _init_kernel(self) -> None:
        """Initialize Rust kernel state — kernel is the sole accounting authority (AQC-755)."""
        if not _BT_RUNTIME_AVAILABLE:
            logger.critical("[kernel] bt_runtime not available — CANNOT operate without kernel")
            self._kernel_available = False
            return
        try:
            now_ms = int(time.time() * 1000)
            self._kernel_state_json = _bt_runtime.default_kernel_state_json(float(self._seed_balance), now_ms)
            self._kernel_params_json = _bt_runtime.default_kernel_params_json()
            self._kernel_available = True
            logger.info("[kernel] Rust kernel state initialized (balance=%.2f)", self._seed_balance)
        except Exception as e:
            logger.critical("[kernel] Failed to initialize kernel state: %s — CANNOT operate", e)
            self._kernel_available = False

    def _kernel_sync_event(
        self,
        *,
        symbol: str,
        signal: str,
        price: float,
        size: float,
        timestamp_ms: int,
        funding_rate: float | None = None,
    ) -> None:
        """Feed an event to the Rust kernel — kernel is sole accounting authority (AQC-755)."""
        if not self._kernel_available or self._kernel_state_json is None:
            return
        try:
            if funding_rate is not None:
                new_state_json = _bt_runtime.apply_funding(
                    self._kernel_state_json,
                    symbol,
                    float(funding_rate),
                    float(price),
                    self._kernel_params_json,
                )
                self._kernel_state_json = new_state_json
            else:
                event = {
                    "schema_version": 1,
                    "event_id": int(timestamp_ms),
                    "timestamp_ms": int(timestamp_ms),
                    "symbol": str(symbol).upper(),
                    "signal": str(signal).upper(),
                    "price": float(price),
                }
                result_json = _bt_runtime.step_full(
                    self._kernel_state_json,
                    json.dumps(event),
                    self._kernel_params_json,
                    "{}",
                )
                result = json.loads(result_json)
                if result.get("ok") and "decision" in result:
                    new_state = result["decision"].get("state")
                    if new_state is not None:
                        self._kernel_state_json = (
                            json.dumps(new_state) if isinstance(new_state, dict) else str(new_state)
                        )
                else:
                    err = result.get("error", {})
                    logger.debug("[kernel] step rejected: %s", err.get("message", result_json[:200]))
                    return

            # --- Shadow report: log kernel balance for audit (AQC-755) ---
            # Old Python-vs-kernel comparison removed; kernel is now sole authority.
            # Future: compare kernel vs exchange data when available.
        except Exception as e:
            logger.warning("[kernel] sync event failed: %s", e)

    def get_kernel_balance(self) -> float | None:
        """Extract cash_usd from the kernel state JSON."""
        if not self._kernel_available or self._kernel_state_json is None:
            return None
        try:
            state = json.loads(self._kernel_state_json)
            return float(state.get("cash_usd", 0.0))
        except Exception:
            return None

    def get_kernel_equity(self, prices: dict[str, float] | None = None) -> float | None:
        """Mark-to-market equity from the kernel (cash + unrealized PnL)."""
        if not self._kernel_available or self._kernel_state_json is None:
            return None
        if prices is None:
            return self.get_kernel_balance()
        try:
            return _bt_runtime.get_equity(
                self._kernel_state_json,
                json.dumps(prices),
            )
        except Exception as e:
            logger.debug("[kernel] get_equity failed: %s", e)
            return None

    @staticmethod
    def _instance_state_path(basename: str, *, legacy_db_dir: bool = False) -> str:
        """Derive per-instance runtime state path using AI_QUANT_INSTANCE_TAG.

        Without a tag the path falls back to the original shared name
        (backward-compatible for single-instance deployments).
        """
        if legacy_db_dir:
            base_dir = os.path.dirname(DB_PATH)
        else:
            # Keep runtime state outside the repo/worktree by default.
            base_dir = str(os.getenv("AI_QUANT_KERNEL_STATE_DIR", "~/.mei") or "~/.mei").strip() or "~/.mei"
            base_dir = os.path.expanduser(base_dir)
            if not os.path.isabs(base_dir):
                base_dir = os.path.abspath(os.path.join(os.path.dirname(DB_PATH), base_dir))
        tag = os.getenv("AI_QUANT_INSTANCE_TAG", "").strip()
        if tag:
            stem, ext = os.path.splitext(basename)
            basename = f"{stem}_{tag}{ext}"
        return os.path.join(base_dir, basename)

    def _kernel_persist(self) -> None:
        """Save kernel state to disk."""
        if not self._kernel_available or self._kernel_state_json is None:
            return
        state_path = self._instance_state_path("kernel_state.json")
        legacy_state_path = self._instance_state_path("kernel_state.json", legacy_db_dir=True)
        try:
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            _bt_runtime.save_state(self._kernel_state_json, state_path)
        except Exception as e:
            logger.warning("[kernel] persist failed at %s: %s", state_path, e)
            if legacy_state_path != state_path:
                try:
                    os.makedirs(os.path.dirname(legacy_state_path), exist_ok=True)
                    _bt_runtime.save_state(self._kernel_state_json, legacy_state_path)
                    logger.info("[kernel] persisted runtime state via legacy fallback %s", legacy_state_path)
                except Exception as e2:
                    logger.warning("[kernel] legacy persist fallback failed: %s", e2)
        # Persist shadow report alongside kernel state (AQC-752)
        report_path = self._instance_state_path("kernel_shadow_report.json")
        legacy_report_path = self._instance_state_path("kernel_shadow_report.json", legacy_db_dir=True)
        try:
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            self._shadow_report.to_json(report_path)
        except Exception as e:
            logger.warning("[shadow] persist failed at %s: %s", report_path, e)
            if legacy_report_path != report_path:
                try:
                    os.makedirs(os.path.dirname(legacy_report_path), exist_ok=True)
                    self._shadow_report.to_json(legacy_report_path)
                    logger.info("[shadow] persisted report via legacy fallback %s", legacy_report_path)
                except Exception as e2:
                    logger.warning("[shadow] legacy persist fallback failed: %s", e2)

    def _kernel_restore(self) -> None:
        """Attempt to restore kernel state from disk; re-init with DB balance if missing."""
        if not _BT_RUNTIME_AVAILABLE:
            return
        try:
            state_path = self._instance_state_path("kernel_state.json")
            legacy_state_path = self._instance_state_path("kernel_state.json", legacy_db_dir=True)
            load_candidates: list[str] = []
            if os.path.isfile(state_path):
                load_candidates.append(state_path)
            if legacy_state_path != state_path and os.path.isfile(legacy_state_path):
                load_candidates.append(legacy_state_path)

            restored = False
            for load_path in load_candidates:
                try:
                    self._kernel_state_json = _bt_runtime.load_state(load_path)
                    self._kernel_available = True
                    kb = self.get_kernel_balance()
                    logger.info("[kernel] Restored kernel state from disk (cash_usd=%.2f)", kb or 0.0)
                    if load_path != state_path:
                        try:
                            os.makedirs(os.path.dirname(state_path), exist_ok=True)
                            shutil.copy2(load_path, state_path)
                            logger.info("[kernel] migrated legacy runtime state to %s", state_path)
                        except Exception as e:
                            logger.debug("[kernel] legacy state migration skipped: %s", e)
                    restored = True
                    break
                except Exception as e:
                    logger.warning("[kernel] state load failed from %s: %s", load_path, e)

            if not restored:
                # No persisted kernel state (e.g. first run after migration
                # or after switching to per-instance state paths).
                # Re-init with the authoritative balance (live-synced).
                self._seed_balance = PAPER_BALANCE
                logger.info("[kernel] No state file found — re-initializing with seed balance %.2f", self._seed_balance)
                self._init_kernel()

            # AQC-FIX: Reconcile kernel cash_usd with the authoritative
            # paper balance.  Use the module-level PAPER_BALANCE which
            # reflects the live-synced value (daemon sets AI_QUANT_PAPER_BALANCE
            # from the Hyperliquid account before strategy import when
            # PAPER_BALANCE_FROM_LIVE=1).  This takes precedence over
            # _seed_balance which load_state() may have overwritten with a
            # stale DB value from a previous buggy session.
            _auth_balance = PAPER_BALANCE
            if self._kernel_available and self._kernel_state_json:
                try:
                    _st = json.loads(self._kernel_state_json)
                    disk_cash = float(_st.get("cash_usd", 0.0))
                    if abs(disk_cash - _auth_balance) > 0.01:
                        logger.info(
                            "[kernel] Reconciling cash_usd: %.2f → %.2f (live balance)",
                            disk_cash,
                            _auth_balance,
                        )
                        _st["cash_usd"] = _auth_balance
                        self._kernel_state_json = json.dumps(
                            _st,
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                        # Keep _seed_balance in sync so self.balance reads
                        # the correct value even before any kernel step.
                        self._seed_balance = _auth_balance
                except Exception as e:
                    logger.warning("[kernel] cash_usd reconciliation failed: %s", e)

            # Restore shadow report (AQC-752)
            report_path = self._instance_state_path("kernel_shadow_report.json")
            legacy_report_path = self._instance_state_path("kernel_shadow_report.json", legacy_db_dir=True)
            report_load_candidates: list[str] = []
            if os.path.isfile(report_path):
                report_load_candidates.append(report_path)
            if legacy_report_path != report_path and os.path.isfile(legacy_report_path):
                report_load_candidates.append(legacy_report_path)

            for report_load_path in report_load_candidates:
                try:
                    self._shadow_report = ShadowReport.from_json(report_load_path)
                    s = self._shadow_report.summary()
                    logger.info(
                        "[shadow] Restored report: %d checks, %d failures, converged=%s",
                        s["total_checks"],
                        s["failures"],
                        self._shadow_report.is_converged(),
                    )
                    if report_load_path != report_path:
                        try:
                            os.makedirs(os.path.dirname(report_path), exist_ok=True)
                            shutil.copy2(report_load_path, report_path)
                            logger.info("[shadow] migrated legacy report to %s", report_path)
                        except Exception as e:
                            logger.debug("[shadow] legacy report migration skipped: %s", e)
                    break
                except Exception as e:
                    logger.warning("[shadow] report load failed from %s: %s", report_load_path, e)
        except Exception as e:
            logger.warning("[kernel] restore failed, re-initializing: %s", e)
            self._init_kernel()

    def load_state(self):
        ensure_db()
        conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
        cursor = conn.cursor()

        # Get latest balance from DB — used as seed for kernel init only (AQC-755).
        cursor.execute("SELECT balance FROM trades ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            self._seed_balance = float(row[0])

        # Load all currently open positions (even if the symbol isn't in the configured watchlist).
        cursor.execute(
            """
            SELECT t.id, t.timestamp, t.symbol, t.type, t.price, t.size, t.confidence, t.entry_atr, t.leverage, t.margin_used
            FROM trades t
            JOIN (
                SELECT symbol, MAX(id) AS open_id
                FROM trades
                WHERE action = 'OPEN'
                GROUP BY symbol
            ) lo ON lo.symbol = t.symbol AND lo.open_id = t.id
            LEFT JOIN (
                SELECT symbol, MAX(id) AS close_id
                FROM trades
                WHERE action = 'CLOSE'
                GROUP BY symbol
            ) lc ON lc.symbol = t.symbol
            WHERE lc.close_id IS NULL OR t.id > lc.close_id
            """
        )

        for (
            open_trade_id,
            open_ts,
            sym_raw,
            pos_type_raw,
            open_px,
            open_sz,
            conf,
            open_atr,
            lev,
            m_used,
        ) in cursor.fetchall():
            symbol = (sym_raw or "").upper()
            if not symbol:
                continue

            pos_type = str(pos_type_raw or "").upper()
            if pos_type not in {"LONG", "SHORT"}:
                continue

            try:
                avg_entry = float(open_px)
                net_size = float(open_sz)
            except Exception:
                continue
            if avg_entry <= 0 or net_size <= 0:
                continue

            try:
                entry_atr = float(open_atr or 0.0)
            except Exception:
                entry_atr = 0.0

            # Rebuild net position (avg entry + size) by replaying fills since the OPEN.
            cursor.execute(
                """
                SELECT action, price, size, entry_atr
                FROM trades
                WHERE symbol = ?
                  AND id > ?
                  AND action IN ('ADD', 'REDUCE')
                ORDER BY id ASC
                """,
                (symbol, open_trade_id),
            )
            for act, px, sz, fill_atr in cursor.fetchall():
                try:
                    px = float(px)
                    sz = float(sz)
                except Exception:
                    continue
                if px <= 0 or sz <= 0:
                    continue
                if act == "ADD":
                    new_total = net_size + sz
                    if new_total > 0:
                        avg_entry = ((avg_entry * net_size) + (px * sz)) / new_total
                        if fill_atr is not None:
                            try:
                                fill_atr = float(fill_atr)
                            except Exception:
                                fill_atr = None
                        if fill_atr and fill_atr > 0:
                            if entry_atr > 0:
                                entry_atr = ((entry_atr * net_size) + (fill_atr * sz)) / new_total
                            else:
                                entry_atr = fill_atr
                        net_size = new_total
                elif act == "REDUCE":
                    net_size -= sz
                    if net_size <= 0:
                        net_size = 0.0
                        break

            if net_size <= 0:
                continue

            cursor.execute(
                """
                SELECT open_trade_id, trailing_sl, last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold
                FROM position_state
                WHERE symbol = ?
                """,
                (symbol,),
            )
            state = cursor.fetchone()
            trailing_sl = state[1] if state and state[0] == open_trade_id else None
            last_funding_time = state[2] if state and state[0] == open_trade_id else None
            adds_count = state[3] if state and state[0] == open_trade_id else None
            tp1_taken = state[4] if state and state[0] == open_trade_id else None
            last_add_time = state[5] if state and state[0] == open_trade_id else None
            entry_adx_threshold = (
                float(state[6] or 0) if state and len(state) > 6 and state[0] == open_trade_id else 0.0
            )
            if last_funding_time is None:
                try:
                    last_funding_time = int(datetime.datetime.fromisoformat(open_ts).timestamp() * 1000)
                except Exception:
                    last_funding_time = int(time.time() * 1000)

            try:
                leverage = float(lev) if lev is not None else 1.0
            except Exception:
                leverage = 1.0
            if leverage <= 0:
                leverage = 1.0

            try:
                margin_used = float(m_used) if m_used is not None else None
            except Exception:
                margin_used = None
            if margin_used is None:
                try:
                    margin_used = abs(net_size) * avg_entry / leverage
                except Exception:
                    margin_used = 0.0

            self.positions[symbol] = {
                "open_trade_id": open_trade_id,
                "open_timestamp": open_ts,
                "type": pos_type,
                "entry_price": avg_entry,
                "size": net_size,
                "confidence": conf,
                "entry_atr": entry_atr,  # Handle legacy rows
                "entry_adx_threshold": float(entry_adx_threshold or 0),
                "trailing_sl": trailing_sl,
                "last_funding_time": last_funding_time,
                "leverage": leverage,
                "margin_used": abs(net_size) * avg_entry / leverage if avg_entry > 0 else margin_used,
                "adds_count": int(adds_count or 0),
                "tp1_taken": int(tp1_taken or 0),
                "last_add_time": int(last_add_time or 0),
            }

        # Restore persisted runtime cooldown maps (state-sync deterministic continuation).
        self._last_entry_attempt_at_s = {}
        self._last_exit_attempt_at_s = {}
        try:
            cursor.execute(
                """
                SELECT symbol, last_entry_attempt_s, last_exit_attempt_s
                FROM runtime_cooldowns
                """
            )
            now_s = time.time()
            for sym_raw, last_entry_s_raw, last_exit_s_raw in cursor.fetchall():
                symbol = str(sym_raw or "").strip().upper()
                if not symbol:
                    continue

                def _normalise_runtime_ts_s(raw_val):
                    if raw_val is None:
                        return None
                    try:
                        v = float(raw_val)
                    except Exception:
                        return None
                    if v <= 0.0:
                        return None
                    if v > 10_000_000_000:
                        v /= 1000.0
                    # Defensive guard against corrupted future timestamps.
                    if v > (now_s + 86400.0):
                        return None
                    return v

                last_entry_s = _normalise_runtime_ts_s(last_entry_s_raw)
                if last_entry_s is not None:
                    self._last_entry_attempt_at_s[symbol] = last_entry_s
                last_exit_s = _normalise_runtime_ts_s(last_exit_s_raw)
                if last_exit_s is not None:
                    self._last_exit_attempt_at_s[symbol] = last_exit_s
        except Exception as e:
            logger.debug("runtime_cooldowns restore skipped: %s", e)
        conn.close()
        # Restore kernel state from disk if available (AQC-742).
        self._kernel_restore()

    # -- Simulated rate-limit helpers (mirrors LiveTrader friction) --

    def _can_attempt_entry(self, symbol: str) -> bool:
        """Check per-symbol entry cooldown AND per-loop budget."""
        cfg = get_strategy_config(symbol)
        trade_cfg = cfg.get("trade") or {}

        cooldown_s = float(trade_cfg.get("entry_cooldown_s", 0))
        if cooldown_s > 0:
            last = self._last_entry_attempt_at_s.get(symbol, 0.0)
            if (time.time() - last) < cooldown_s:
                logger.debug(
                    f"⏳ ENTRY_SKIP_COOLDOWN: {symbol} entry blocked — rate-limit cooldown ({cooldown_s:.0f}s) active"
                )
                log_audit_event(
                    symbol,
                    "ENTRY_SKIP_COOLDOWN",
                    data={
                        "cooldown_s": float(cooldown_s),
                        "elapsed_s": float(time.time() - last),
                    },
                )
                return False

        if self._entry_budget_remaining is not None and self._entry_budget_remaining <= 0:
            logger.debug(f"⏳ ENTRY_SKIP_BUDGET: {symbol} entry blocked — max_entry_orders_per_loop budget exhausted")
            log_audit_event(
                symbol,
                "ENTRY_SKIP_BUDGET",
                data={"budget_remaining": 0},
            )
            return False

        return True

    def _can_attempt_exit(self, symbol: str) -> bool:
        """Check per-symbol exit cooldown."""
        cfg = get_strategy_config(symbol)
        trade_cfg = cfg.get("trade") or {}

        cooldown_s = float(trade_cfg.get("exit_cooldown_s", 0))
        if cooldown_s > 0:
            last = self._last_exit_attempt_at_s.get(symbol, 0.0)
            if (time.time() - last) < cooldown_s:
                return False

        return True

    def _note_entry_attempt(self, symbol: str) -> None:
        """Record timestamp + decrement budget after a successful entry/add."""
        self._last_entry_attempt_at_s[symbol] = time.time()
        self._upsert_runtime_cooldown_state(symbol)
        if self._entry_budget_remaining is not None and self._entry_budget_remaining > 0:
            self._entry_budget_remaining -= 1

    def _note_exit_attempt(self, symbol: str) -> None:
        """Record timestamp after a successful exit."""
        self._last_exit_attempt_at_s[symbol] = time.time()
        self._upsert_runtime_cooldown_state(symbol)

    def _upsert_runtime_cooldown_state(self, symbol: str) -> None:
        sym = str(symbol or "").strip().upper()
        if not sym:
            return
        ensure_db()
        conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO runtime_cooldowns (
                    symbol, last_entry_attempt_s, last_exit_attempt_s, updated_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(symbol) DO UPDATE SET
                    last_entry_attempt_s = excluded.last_entry_attempt_s,
                    last_exit_attempt_s = excluded.last_exit_attempt_s,
                    updated_at = excluded.updated_at
                """,
                (
                    sym,
                    self._last_entry_attempt_at_s.get(sym),
                    self._last_exit_attempt_at_s.get(sym),
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        except Exception as e:
            logger.debug("runtime_cooldowns upsert skipped for %s: %s", sym, e)
        finally:
            conn.close()

    def upsert_position_state(self, symbol):
        pos = self.positions.get(symbol)
        if not pos:
            return

        ensure_db()
        conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
        cursor = conn.cursor()
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now_dt.isoformat()
        now_ms = int(now_dt.timestamp() * 1000)
        sym = str(symbol or "").strip().upper()
        cursor.execute(
            """
            INSERT INTO position_state (
                symbol, open_trade_id, trailing_sl, last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                open_trade_id = excluded.open_trade_id,
                trailing_sl = excluded.trailing_sl,
                last_funding_time = excluded.last_funding_time,
                adds_count = excluded.adds_count,
                tp1_taken = excluded.tp1_taken,
                last_add_time = excluded.last_add_time,
                entry_adx_threshold = excluded.entry_adx_threshold,
                updated_at = excluded.updated_at
            """,
            (
                sym,
                pos.get("open_trade_id"),
                pos.get("trailing_sl"),
                pos.get("last_funding_time"),
                pos.get("adds_count"),
                pos.get("tp1_taken"),
                pos.get("last_add_time"),
                pos.get("entry_adx_threshold"),
                now_iso,
            ),
        )
        cursor.execute(
            """
            INSERT INTO position_state_history (
                event_ts_ms, updated_at, symbol, open_trade_id, trailing_sl,
                last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold,
                event_type, run_fingerprint
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now_ms,
                now_iso,
                sym,
                pos.get("open_trade_id"),
                pos.get("trailing_sl"),
                pos.get("last_funding_time"),
                pos.get("adds_count"),
                1 if bool(pos.get("tp1_taken")) else 0,
                pos.get("last_add_time"),
                pos.get("entry_adx_threshold"),
                "upsert",
                get_run_fingerprint(),
            ),
        )
        conn.commit()
        conn.close()

    def clear_position_state(self, symbol):
        ensure_db()
        conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
        cursor = conn.cursor()
        sym = str(symbol or "").strip().upper()
        row = cursor.execute(
            """
            SELECT open_trade_id, trailing_sl, last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold
            FROM position_state
            WHERE symbol = ?
            LIMIT 1
            """,
            (sym,),
        ).fetchone()
        if row:
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            now_iso = now_dt.isoformat()
            now_ms = int(now_dt.timestamp() * 1000)
            cursor.execute(
                """
                INSERT INTO position_state_history (
                    event_ts_ms, updated_at, symbol, open_trade_id, trailing_sl,
                    last_funding_time, adds_count, tp1_taken, last_add_time, entry_adx_threshold,
                    event_type, run_fingerprint
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_ms,
                    now_iso,
                    sym,
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                    row[6],
                    "clear",
                    get_run_fingerprint(),
                ),
            )
        cursor.execute("DELETE FROM position_state WHERE symbol = ?", (sym,))
        conn.commit()
        conn.close()

    def log_trade(
        self,
        symbol,
        action,
        type,
        price,
        size,
        reason,
        confidence,
        pnl=0.0,
        entry_atr=None,
        fee_usd=0.0,
        fee_rate=None,
        leverage=None,
        margin_used=None,
        *,
        timestamp_override: str | None = None,
        notify: bool = True,
        meta: dict | None = None,
    ):
        ensure_db()
        conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
        cursor = conn.cursor()
        timestamp = timestamp_override or datetime.datetime.now(datetime.timezone.utc).isoformat()
        notional = price * size
        meta_json = _json_dumps_safe(meta) if meta else None
        reason_code = ""
        if isinstance(meta, dict):
            reason_code = str(meta.get("reason_code") or "").strip().lower()
        if not reason_code:
            reason_code = canonical_reason_code_for_trade(str(action), str(type), str(reason))

        cursor.execute(
            """
            INSERT INTO trades (timestamp, symbol, type, action, price, size, notional, reason, reason_code, confidence, pnl, fee_usd, fee_rate, balance, entry_atr, leverage, margin_used, meta_json, run_fingerprint)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                timestamp,
                symbol,
                type,
                action,
                price,
                size,
                notional,
                reason,
                reason_code,
                confidence,
                pnl,
                fee_usd,
                fee_rate,
                self.balance,
                entry_atr,
                leverage,
                margin_used,
                meta_json,
                get_run_fingerprint(),
            ),
        )
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # Best-effort structured event log (JSONL). This must never block trading.
        try:
            from engine.event_logger import emit_event

            emit_event(
                kind="trade_fill",
                symbol=symbol,
                data={
                    "trade_id": int(trade_id or 0),
                    "action": str(action or ""),
                    "pos_type": str(type or ""),
                    "price": float(price or 0.0),
                    "size": float(size or 0.0),
                    "notional": float(notional or 0.0),
                    "pnl_usd": float(pnl or 0.0),
                    "fee_usd": float(fee_usd or 0.0),
                    "fee_rate": None if fee_rate is None else float(fee_rate),
                    "balance": float(self.balance or 0.0),
                    "reason": str(reason or ""),
                    "confidence": str(confidence or ""),
                    "meta_json": meta_json,
                },
            )
        except Exception:
            pass

        if not notify:
            return trade_id

        # Calculate equity + realised/unrealised breakdown for notification display.
        equity = self.get_live_balance()
        cash_realised = float(self.balance or 0.0)
        unrealised = float(equity or 0.0) - cash_realised
        try:
            baseline_usd = float(PAPER_BALANCE)
        except Exception:
            baseline_usd = 0.0
        if baseline_usd <= 1e-9:
            baseline_usd = 0.0

        def _pct(v: float, *, is_return: bool = False) -> str:
            if baseline_usd <= 0:
                return "n/a"
            if is_return:
                p = ((float(v) - baseline_usd) / baseline_usd) * 100.0
            else:
                p = (float(v) / baseline_usd) * 100.0
            return f"{p:+.2f}%"

        # --- DIRECT NOTIFICATION (CANTONESE) ---
        action_map = {
            "OPEN": "開倉",
            "ADD": "加倉",
            "REDUCE": "部分平倉",
            "CLOSE": "平倉",
            "FUNDING": "資金費 (Funding)",
        }
        action_hk = action_map.get(action, action)

        emoji = "🚀"
        if action == "ADD":
            emoji = "➕"
        elif action in {"REDUCE", "CLOSE"}:
            emoji = "💰" if pnl > 0 else "🛑"
        elif action == "FUNDING":
            emoji = "💸"

        # Translate Reason for the notification
        reason_map = {
            "Signal Trigger": "信號觸發",
            "Pyramid Add": "加倉 (Pyramid Add)",
            "Stop Loss": "止蝕 (Stop Loss)",
            "Take Profit": "止盈 (Take Profit)",
            "Take Profit (Partial)": "止盈 (部分平倉)",
            "Trailing Stop": "移動止損 (Trailing Stop)",
            "Signal Flip": "信號反轉",
        }
        reason_hk = reason_map.get(reason, reason)
        if "Signal Flip" in reason:
            reason_hk = reason.replace("Signal Flip", "信號反轉")

        discord_label = str(os.getenv("AI_QUANT_DISCORD_LABEL", "") or os.getenv("AI_QUANT_INSTANCE_TAG", "")).strip()
        header = f"{emoji} **紙上交易：{action_hk}** | {symbol}"
        if discord_label:
            header = f"[{discord_label}] {header}"
        msg = f"{header}\n"
        msg += f"• 類型: `{type}`\n"
        msg += f"• 價格: `${price:,.4f}`\n"
        msg += f"• 規模: `{size:.4f}` (`${notional:,.2f} USD`)\n"
        try:
            lev_f = None if leverage is None else float(leverage)
        except Exception:
            lev_f = None
        if lev_f is not None and lev_f > 0:
            msg += f"• 槓桿 (Lev): `{lev_f:.0f}x`\n"
        try:
            margin_f = None if margin_used is None else float(margin_used)
        except Exception:
            margin_f = None
        if margin_f is not None and abs(margin_f) > 1e-9:
            if action in {"OPEN", "ADD"} and margin_f > 0:
                msg += f"• 保證金 (Margin est.): `${margin_f:,.2f}`\n"
            elif action in {"REDUCE", "CLOSE"}:
                msg += f"• 保證金變化 (ΔMargin est.): `${margin_f:+,.2f}`\n"
        if fee_usd:
            rate_str = "" if fee_rate is None else f" ({fee_rate * 100:.4f}%)"
            msg += f"• 手續費 (Fee): `${fee_usd:,.4f}`{rate_str}\n"
        msg += f"• 原因: *{reason_hk}*\n"
        if action in {"CLOSE", "REDUCE"}:
            msg += f"• 損益 (PnL): **${pnl:,.2f}**\n"

        msg += f"• **淨值 (Equity, est.):** `${equity:,.2f}` ({_pct(float(equity or 0.0), is_return=True)})\n"
        msg += f"• **未實現 (Unrealised):** `${unrealised:,.2f}` ({_pct(float(unrealised), is_return=False)})\n"
        msg += f"• **現金 (Cash, realised):** `${cash_realised:,.2f}` ({_pct(float(cash_realised), is_return=True)})"

        try:
            try:
                timeout_s = float(os.getenv("AI_QUANT_DISCORD_SEND_TIMEOUT_S", "6"))
            except Exception:
                timeout_s = 6.0
            timeout_s = max(1.0, min(30.0, timeout_s))
            send_openclaw_message(
                channel="discord",
                target=DISCORD_CHANNEL,
                message=msg,
                timeout_s=timeout_s,
            )
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
        return trade_id

    def apply_funding_payments(self, *, now_ms: int | None = None) -> float:
        """
        Applies realized perps funding payments to cash balance and logs them in `trades` as action='FUNDING'.

        Funding rule (Hyperliquid): paid every hour. When funding_rate > 0, longs pay shorts; when < 0, shorts pay longs.
        Cash delta is approximated as: -signed_position_size * oracle_price * funding_rate.
        """
        if not HL_FUNDING_ENABLED:
            return 0.0
        if not self.positions:
            return 0.0

        now_ms = int(now_ms or (time.time() * 1000))

        try:
            from hyperliquid.info import Info
            from hyperliquid.utils import constants
        except Exception as e:
            logger.warning("apply_funding_payments: hyperliquid SDK not available, skipping funding")
            logger.warning(f"⚠️ Funding sync unavailable (hyperliquid SDK import failed): {e}")
            return 0.0

        def _funding_price_from_candles(symbol: str, t_ms: int) -> float | None:
            try:
                conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
                cur = conn.cursor()
                cur.execute(
                    """
                    SELECT c
                    FROM candles
                    WHERE symbol = ? AND interval = ? AND t_close IS NOT NULL AND t_close <= ?
                    ORDER BY t_close DESC
                    LIMIT 1
                    """,
                    (symbol, INTERVAL, int(t_ms)),
                )
                row = cur.fetchone()
                conn.close()
                if row and row[0] is not None:
                    return float(row[0])
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass
            return None

        info = Info(constants.MAINNET_API_URL, skip_ws=True)

        total_delta = 0.0
        for symbol, pos in list(self.positions.items()):
            try:
                last_ms = int(pos.get("last_funding_time") or 0)
            except Exception:
                last_ms = 0
            if last_ms <= 0:
                last_ms = now_ms

            # Funding is paid on hourly boundaries. Avoid hammering the REST API by only
            # querying once we have crossed at least one hour boundary since last sync.
            next_hour_ms = ((last_ms // 3_600_000) + 1) * 3_600_000
            if now_ms < next_hour_ms:
                continue

            try:
                events = info.funding_history(symbol, last_ms, now_ms) or []
            except Exception as e:
                logger.warning(f"⚠️ Funding history failed for {symbol}: {e}")
                continue

            applied_any = False
            for ev in events:
                try:
                    ev_time = int(ev.get("time"))
                except Exception:
                    continue
                if ev_time <= last_ms:
                    continue

                try:
                    rate = float(ev.get("fundingRate"))
                except Exception:
                    continue

                px = _funding_price_from_candles(symbol, ev_time)
                if px is None:
                    mid = hyperliquid_ws.hl_ws.get_mid(symbol, max_age_s=10.0)
                    if mid is not None:
                        px = float(mid)
                    else:
                        px = float(pos.get("entry_price", 0.0))
                        logger.warning("funding: using entry_price fallback for %s (mark price unavailable)", symbol)

                try:
                    size = float(pos.get("size", 0.0))
                except Exception:
                    size = 0.0

                if size <= 0 or px <= 0:
                    last_ms = ev_time
                    continue

                pos_type = str(pos.get("type", "")).upper()
                signed_size = size if pos_type == "LONG" else -size
                delta = -(signed_size * px * rate)

                # AQC-755: kernel handles balance — sync BEFORE log so self.balance reads post-trade.
                self._kernel_sync_event(
                    symbol=symbol,
                    signal="FUNDING",
                    price=px,
                    size=size,
                    timestamp_ms=int(ev_time),
                    funding_rate=rate,
                )
                total_delta += delta
                applied_any = True

                ts_iso = datetime.datetime.fromtimestamp(ev_time / 1000).isoformat()
                self.log_trade(
                    symbol,
                    "FUNDING",
                    pos_type,
                    px,
                    size,
                    f"Funding ({rate:+.10f})",
                    "N/A",
                    pnl=delta,
                    fee_usd=0.0,
                    fee_rate=0.0,
                    leverage=pos.get("leverage"),
                    margin_used=pos.get("margin_used"),
                    timestamp_override=ts_iso,
                    meta={
                        "funding_rate": float(rate),
                        "delta_usd": float(delta),
                        "event_time_ms": int(ev_time),
                    },
                    notify=False,
                )

                # AQC-804: funding decision event
                try:
                    create_decision_event(
                        symbol=symbol,
                        event_type="funding",
                        status="executed",
                        phase="execution",
                        triggered_by="schedule",
                        action_taken="apply_funding",
                        timestamp_ms=int(ev_time),
                        context={
                            "rate": float(rate),
                            "delta_usd": float(delta),
                            "price": float(px),
                            "size": float(size),
                            "pos_type": str(pos_type),
                        },
                    )
                except Exception as _fde:
                    logger.debug("AQC-804: funding decision event failed: %s", _fde)

                last_ms = ev_time

            if applied_any:
                pos["last_funding_time"] = last_ms
                self.upsert_position_state(symbol)

        self._kernel_persist()
        return total_delta

    def get_live_balance(self):
        """Equity from kernel (cash + unrealized PnL) minus estimated close fees (AQC-755).

        Gathers live mid prices via WS/REST, delegates PnL to kernel via
        ``get_kernel_equity(prices)``, then subtracts estimated close fees.
        """
        try:
            hyperliquid_ws.hl_ws.ensure_started(
                symbols=SYMBOLS,
                interval=INTERVAL,
                candle_limit=LOOKBACK_HOURS + 50,
            )

            prices: dict[str, float] = {}
            est_close_fees = 0.0
            _any_stale = False
            fee_rate = _effective_fee_rate()
            try:
                mid_max_age_s = float(
                    os.getenv(
                        "AI_QUANT_EQUITY_MID_MAX_AGE_S",
                        os.getenv("AI_QUANT_WS_STALE_MIDS_S", "60"),
                    )
                )
            except Exception:
                mid_max_age_s = 60.0
            mid_max_age_s = max(0.0, float(mid_max_age_s))

            rest_mids: dict[str, float] | None = None

            def _get_rest_mids() -> dict[str, float]:
                nonlocal rest_mids
                if rest_mids is not None:
                    return rest_mids
                rest_enabled = str(os.getenv("AI_QUANT_REST_ENABLE", "1") or "1").strip().lower() in {
                    "1",
                    "true",
                    "yes",
                    "y",
                    "on",
                }
                if not rest_enabled:
                    rest_mids = {}
                    return rest_mids

                try:
                    ttl_s = float(os.getenv("AI_QUANT_EQUITY_REST_MIDS_TTL_S", "5"))
                except Exception:
                    ttl_s = 5.0
                ttl_s = max(0.0, float(ttl_s))
                now_ms = int(time.time() * 1000)

                try:
                    cached = getattr(self, "_rest_mids_cache", None)
                    cached_at = int(getattr(self, "_rest_mids_cache_at_ms", 0) or 0)
                    if isinstance(cached, dict) and cached and (now_ms - cached_at) <= int(ttl_s * 1000):
                        rest_mids = {str(k).upper(): float(v) for k, v in cached.items()}
                        return rest_mids
                except Exception:
                    pass

                try:
                    from engine.rest_client import HyperliquidRestClient

                    try:
                        timeout_s = float(os.getenv("AI_QUANT_EQUITY_REST_TIMEOUT_S", "3"))
                    except Exception:
                        timeout_s = 3.0
                    timeout_s = max(0.5, min(10.0, float(timeout_s)))

                    res = HyperliquidRestClient(timeout_s=timeout_s).all_mids()
                    raw = res.data or {}
                    if isinstance(raw, dict) and isinstance(raw.get("mids"), dict):
                        raw = raw.get("mids") or {}

                    out: dict[str, float] = {}
                    if isinstance(raw, dict):
                        for k, v in raw.items():
                            try:
                                out[str(k).upper()] = float(v)
                            except Exception:
                                continue

                    rest_mids = out
                    try:
                        setattr(self, "_rest_mids_cache", dict(out))
                        setattr(self, "_rest_mids_cache_at_ms", int(res.fetched_at_ms or now_ms))
                    except Exception:
                        pass
                    return rest_mids
                except Exception:
                    rest_mids = {}
                    return rest_mids

            for symbol, pos in self.positions.items():
                sym_u = str(symbol or "").strip().upper()
                if not sym_u:
                    continue

                current_price = hyperliquid_ws.hl_ws.get_mid(sym_u, max_age_s=mid_max_age_s)
                if current_price is None:
                    current_price = hyperliquid_ws.hl_ws.get_mid(sym_u, max_age_s=None)
                if current_price is None:
                    mid_map = _get_rest_mids()
                    try:
                        current_price = mid_map.get(sym_u)
                    except Exception:
                        current_price = None
                if current_price is None:
                    logger.warning("get_live_balance: using entry_price fallback for %s — data may be stale", symbol)
                    _any_stale = True
                    try:
                        current_price = float(pos.get("entry_price") or 0.0)
                    except Exception:
                        current_price = 0.0

                try:
                    current_price = float(current_price)
                except Exception:
                    current_price = 0.0
                if current_price <= 0:
                    continue

                prices[sym_u] = current_price

                # Estimate close fees (not tracked by kernel).
                size = float(pos.get("size") or 0.0)
                if size > 0:
                    est_close_fees += abs(size) * current_price * fee_rate

            self._data_stale = _any_stale

            # AQC-755: delegate equity calculation to kernel.
            kernel_equity = self.get_kernel_equity(prices) if prices else self.get_kernel_balance()
            if kernel_equity is not None:
                return kernel_equity - est_close_fees

            # Fallback: kernel balance minus fees (no position PnL available).
            return self.balance - est_close_fees
        except Exception as e:
            logger.error(f"Error calculating live balance: {e}")
            return self.balance

    def _estimate_margin_used(self, symbol: str, pos: dict, *, mark_price: float | None = None) -> float:
        """Approx initial margin used (isolated): notional / leverage."""
        try:
            lev = float(pos.get("leverage") or 1.0)
        except Exception:
            lev = 1.0
        if lev <= 0:
            lev = 1.0

        try:
            sz = float(pos.get("size") or 0.0)
        except Exception:
            sz = 0.0
        if sz <= 0:
            return 0.0

        px = None
        if mark_price is not None:
            px = mark_price
        else:
            mid = hyperliquid_ws.hl_ws.get_mid(symbol, max_age_s=10.0)
            if mid is not None:
                px = float(mid)
            else:
                bbo = hyperliquid_ws.hl_ws.get_bbo(symbol, max_age_s=15.0)
                if bbo is not None:
                    bid, ask = bbo
                    if bid > 0 and ask > 0:
                        px = (bid + ask) / 2.0
        if px is None:
            try:
                px = float(pos.get("entry_price") or 0.0)
            except Exception:
                px = 0.0

        if px <= 0:
            return 0.0
        return abs(sz) * float(px) / lev

    def add_to_position(self, symbol, price, timestamp, confidence, *, atr=0.0, indicators=None) -> bool:
        """Scales into an existing net position (pyramiding). Returns True if an add was executed."""
        if symbol not in self.positions:
            return False

        pos = self.positions[symbol]
        pos_type = str(pos.get("type") or "").upper()
        if pos_type not in {"LONG", "SHORT"}:
            return False

        cfg = get_strategy_config(symbol)
        trade_cfg = cfg.get("trade") or {}
        thr = cfg.get("thresholds") or {}

        if not bool(trade_cfg.get("enable_pyramiding", True)):
            return False

        try:
            max_adds = int(trade_cfg.get("max_adds_per_symbol", 2))
        except Exception:
            max_adds = 2
        adds_count = int(pos.get("adds_count") or 0)
        if adds_count >= max(0, max_adds):
            return False

        min_conf = str(trade_cfg.get("add_min_confidence", "medium"))
        if not _conf_ok(confidence, min_confidence=min_conf):
            return False

        now_ms = int(time.time() * 1000)
        cooldown_m = float(trade_cfg.get("add_cooldown_minutes", 60))
        last_add_time = int(pos.get("last_add_time") or 0)
        if last_add_time > 0 and cooldown_m > 0 and (now_ms - last_add_time) < (cooldown_m * 60_000):
            return False

        # Require the position to be at least slightly in profit before adding.
        min_profit_atr = float(trade_cfg.get("add_min_profit_atr", 0.5))

        # v5.005: 動態加倉增敏 (Dynamic Pyramid Sensitivity - DPS)
        # 如果趨勢正在強烈加速 (ADX_slope > 0.75)，下調 50% 的獲利門檻需求，及早加倉。
        # v5.006: 加倉波動過濾 (Pyramid Volatility Filter - PVF)
        # 如果 ATR_slope > 0 (波動正在擴大)，則不執行 DPS 增敏，防止在劇烈波動中過早加倉導致被掃損。
        # v5.007: 分批止盈後的加倉禁令 (Post-Partial-Exit Add Block - PPEB)
        # 如果當前倉位已經執行過部分止盈 (tp1_taken > 0)，則禁止再次加倉。
        # 這能防止系統在強趨勢末端的震盪中，一邊止盈一邊又加倉，導致頭寸暴露在反轉風險中。
        if int(pos.get("tp1_taken") or 0) > 0:
            return False

        entry = float(pos.get("entry_price") or 0.0)
        if entry <= 0:
            return False
        current_atr = float(indicators.get("ATR", atr) or atr or 0.0) if indicators is not None else float(atr or 0.0)
        if current_atr <= 0:
            current_atr = float(pos.get("entry_atr") or 0.0) or (entry * 0.005)
        if current_atr <= 0:
            return False

        # Mark price for checks (prefer live mid/bbo mid, fallback to provided price).
        mid = hyperliquid_ws.hl_ws.get_mid(symbol, max_age_s=10.0)
        mark = float(mid) if mid is not None else float(price)

        # v5.008: 加倉距離止損過濾 (Pyramid-Stop Proximity Filter - PSPF)
        # 如果當前價格距離移動止損 (Trailing Stop) 或 止損位 (Stop Loss) 低於 0.5 ATR，則禁止執行 Pyramid Add。
        # 這能防止在價格已經接近被掃損的邊緣時仍然加碼，避免無謂的磨損。
        sl_price = float(pos.get("trailing_sl") or 0.0)
        if sl_price <= 0:
            sl_mult = float(trade_cfg.get("sl_atr_mult", 1.5))
            sl_price = entry - (current_atr * sl_mult) if pos_type == "LONG" else entry + (current_atr * sl_mult)

        dist_to_sl_atr = abs(mark - sl_price) / current_atr if current_atr > 0 else 0
        if dist_to_sl_atr < 0.5:
            return False

        # v5.009: 加倉動量過濾 (Pyramid Momentum Filter - PMF)
        # 只有當 MACD Histogram 喺持倉方向仲係「擴張」緊嘅時候先准加倉。
        # 防止喺趨勢動力轉弱時加碼，減少加倉後即刻被回撤掃損嘅風險。
        if indicators is not None:
            macd_h = indicators.get("MACD_hist", 0)
            prev_macd_h = indicators.get("prev_MACD_hist", 0)
            is_momentum_expanding = (pos_type == "LONG" and macd_h > prev_macd_h) or (
                pos_type == "SHORT" and macd_h < prev_macd_h
            )
            if not is_momentum_expanding:
                return False

        # v5.021: 加倉 RSI 守護 (Pyramiding RSI Guard - PRG)
        # 防止喺極端 RSI 區間（力竭區）繼續加碼，減少追漲殺跌嘅回撤。
        rsi_val = indicators.get("RSI", 50) if indicators is not None else 50
        if (pos_type == "LONG" and rsi_val > 75.0) or (pos_type == "SHORT" and rsi_val < 25.0):
            return False

        # Simulated rate-limit gate (cooldown + budget).
        if not self._can_attempt_entry(symbol):
            return False

        if indicators is not None and indicators.get("ADX_slope", 0) > 0.75:
            atr_slope = indicators.get("ATR_slope", 0)
            if atr_slope <= 0:
                # v5.021: 如果 RSI 已經進入極端區 (Long > 65, Short < 35)，禁用 DPS 增敏，維持門檻。
                is_rsi_extreme = (pos_type == "LONG" and rsi_val > 65.0) or (pos_type == "SHORT" and rsi_val < 35.0)
                if not is_rsi_extreme:
                    min_profit_atr *= 0.5
        profit_atr = (mark - entry) / current_atr if pos_type == "LONG" else (entry - mark) / current_atr
        if profit_atr < min_profit_atr:
            return False

        # allocation_pct should come from get_strategy_config() / YAML, not the hardcoded constant.
        if "allocation_pct" not in trade_cfg:
            logger.warning("Using hardcoded ALLOCATION_PCT fallback — check strategy config")
        allocation_pct = float(trade_cfg.get("allocation_pct", ALLOCATION_PCT))
        add_frac = float(trade_cfg.get("add_fraction_of_base_margin", 0.5))
        add_frac = max(0.0, min(2.0, add_frac))

        leverage = float(pos.get("leverage") or trade_cfg.get("leverage") or HL_DEFAULT_LEVERAGE)
        leverage = max(1.0, leverage)
        slippage_bps = float(trade_cfg.get("slippage_bps", HL_SLIPPAGE_BPS))
        use_bbo = bool(trade_cfg.get("use_bbo_for_fills", True))
        min_notional = float(trade_cfg.get("min_notional_usd", 10.0))
        max_total_margin_pct = float(trade_cfg.get("max_total_margin_pct", 0.60))

        equity_base = _safe_float(self.get_live_balance(), None)
        if equity_base is None or equity_base <= 0:
            equity_base = max(0.0, float(self.balance or 0.0))
            if equity_base <= 0:
                logger.warning("attempt_add_to_position: equity_base is zero/negative, skipping %s", symbol)
                return False
        base_margin = equity_base * allocation_pct
        margin_target = base_margin * add_frac

        # Apply the same dynamic sizing scalars as entries.
        if bool(trade_cfg.get("enable_dynamic_sizing", True)):
            conf_s = str(confidence or "").strip().lower()
            if conf_s.startswith("h"):
                conf_mult = float(trade_cfg.get("confidence_mult_high", 1.0))
            elif conf_s.startswith("m"):
                conf_mult = float(trade_cfg.get("confidence_mult_medium", 0.7))
            else:
                conf_mult = float(trade_cfg.get("confidence_mult_low", 0.5))
            margin_target *= max(0.0, conf_mult)

            adx_val = _safe_float(indicators.get("ADX"), None) if indicators is not None else None
            min_adx = _safe_float(((thr.get("entry") or {}).get("min_adx")), 0.0) or 0.0
            full_adx = float(trade_cfg.get("adx_sizing_full_adx", 40.0))
            min_mult = float(trade_cfg.get("adx_sizing_min_mult", 0.6))
            if adx_val is not None and full_adx > min_adx:
                t = (float(adx_val) - float(min_adx)) / (float(full_adx) - float(min_adx))
                t = max(0.0, min(1.0, t))
                adx_mult = min_mult + t * (1.0 - min_mult)
                margin_target *= max(0.0, adx_mult)

        if current_atr > 0:
            baseline_vol = float(price) * float(trade_cfg.get("vol_baseline_pct", 0.01))
            vol_scalar = baseline_vol / float(current_atr)
            vol_min = float(trade_cfg.get("vol_scalar_min", 0.5))
            vol_max = float(trade_cfg.get("vol_scalar_max", 1.0))
            vol_scalar = max(vol_min, min(vol_max, vol_scalar))
            margin_target *= max(0.0, vol_scalar)

        # Optional size multiplier (used for live rollout ramps, etc).
        try:
            size_mult = float(trade_cfg.get("size_multiplier", 1.0))
        except Exception:
            size_mult = 1.0
        size_mult = max(0.0, float(size_mult))
        margin_target *= float(size_mult)

        # Margin cap across all symbols (use live marks if possible).
        current_margin = 0.0
        for sym, p in self.positions.items():
            current_margin += self._estimate_margin_used(sym, p)
        if (current_margin + margin_target) > (equity_base * max_total_margin_pct):
            return False

        bump_to_min = bool(trade_cfg.get("bump_to_min_notional", False))
        target_notional = margin_target * leverage
        if target_notional < min_notional:
            if bump_to_min:
                target_notional = min_notional
            else:
                return False

        # Check leverage tiers for resulting notional (avoid exceeding HL max leverage).
        try:
            current_size = float(pos.get("size") or 0.0)
        except Exception:
            current_size = 0.0
        approx_total_notional = (abs(current_size) * mark) + target_notional
        max_lev = hyperliquid_meta.max_leverage(symbol, approx_total_notional)
        if max_lev is not None and leverage > float(max_lev):
            return False

        side = "BUY" if pos_type == "LONG" else "SELL"
        fill_price = _get_fill_price(
            symbol,
            side,
            float(price),
            slippage_bps=slippage_bps,
            use_bbo_for_fills=use_bbo,
        )
        add_size = size_for_notional_bounds(
            symbol,
            price=fill_price,
            desired_notional=target_notional,
            min_notional=min_notional,
        )
        if add_size <= 0:
            return False

        notional = abs(add_size) * fill_price
        if notional < min_notional:
            return False

        fee_rate = _effective_fee_rate()
        fee_usd = notional * fee_rate
        # AQC-755: self.balance no longer manually updated — kernel is authoritative.

        # Weighted average entry update
        new_total_size = float(pos.get("size") or 0.0) + add_size
        if new_total_size <= 0:
            return False
        old_notional = entry * float(pos.get("size") or 0.0)
        new_entry = (old_notional + (fill_price * add_size)) / new_total_size
        pos["entry_price"] = float(new_entry)
        pos["size"] = float(new_total_size)

        # Update entry ATR (size-weighted), so stops reflect the blended position.
        old_entry_atr = float(pos.get("entry_atr") or 0.0)
        if old_entry_atr > 0 and current_atr > 0:
            pos["entry_atr"] = (
                (old_entry_atr * (new_total_size - add_size)) + (current_atr * add_size)
            ) / new_total_size
        elif current_atr > 0:
            pos["entry_atr"] = current_atr

        pos["adds_count"] = adds_count + 1
        pos["last_add_time"] = now_ms
        # TP ladder should be available again after adding.
        pos["tp1_taken"] = 0

        # Approx margin used at blended entry
        pos["margin_used"] = (abs(new_total_size) * float(new_entry)) / leverage if new_entry > 0 else 0.0
        self.upsert_position_state(symbol)
        self._note_entry_attempt(symbol)

        audit = None
        if indicators is not None:
            try:
                audit = indicators.get("audit")
            except Exception:
                audit = None
        kernel_reason_code = ""
        try:
            kernel_reason_code = str(
                (indicators if indicators is not None else {}).get("_kernel_reason_code") or ""
            ).strip().lower()
        except Exception:
            kernel_reason_code = ""

        meta = {
            "audit": audit if isinstance(audit, dict) else None,
            "add": {
                "adds_count_before": int(adds_count),
                "adds_count_after": int(adds_count + 1),
                "max_adds_per_symbol": int(max_adds),
                "profit_atr": float(profit_atr),
                "min_profit_atr": float(min_profit_atr),
                "dist_to_sl_atr": float(dist_to_sl_atr),
                "momentum_expanding": bool(
                    (indicators is not None)
                    and (
                        (
                            (pos_type == "LONG")
                            and (indicators.get("MACD_hist", 0) > indicators.get("prev_MACD_hist", 0))
                        )
                        or (
                            (pos_type == "SHORT")
                            and (indicators.get("MACD_hist", 0) < indicators.get("prev_MACD_hist", 0))
                        )
                    )
                ),
                "ppeb_tp1_taken": int(pos.get("tp1_taken") or 0),
            },
        }
        if kernel_reason_code:
            meta["reason_code"] = kernel_reason_code

        # AQC-755: sync kernel BEFORE log so self.balance reads post-trade value.
        add_signal = "BUY" if pos_type == "LONG" else "SELL"
        self._kernel_sync_event(
            symbol=symbol,
            signal=add_signal,
            price=fill_price,
            size=add_size,
            timestamp_ms=now_ms,
        )
        self.log_trade(
            symbol,
            "ADD",
            pos_type,
            fill_price,
            add_size,
            "Pyramid Add",
            confidence,
            pnl=0.0,
            entry_atr=current_atr,
            fee_usd=fee_usd,
            fee_rate=fee_rate,
            leverage=leverage,
            margin_used=(notional / leverage) if leverage > 0 else 0.0,
            meta=meta,
            notify=False,
        )
        margin_est = (notional / leverage) if leverage > 0 else 0.0
        logger.info(
            f"➕ ADD {pos_type} {symbol} px={fill_price:.4f} size={add_size:.6f} "
            f"notional~=${notional:.2f} lev={leverage:.0f} margin~=${margin_est:.2f} "
            f"fee=${fee_usd:.4f} conf={confidence}"
        )
        # FLOW-2: create decision event for ADD fills (traceability)
        try:
            create_decision_event(
                symbol=symbol,
                event_type="fill",
                status="executed",
                phase="execution",
                action_taken="add",
                context={
                    "add_price": fill_price,
                    "confidence": confidence,
                    "adds_count": int(pos.get("adds_count", 0)),
                },
            )
        except Exception:
            pass
        self._kernel_persist()
        return True

    def reduce_position(
        self, symbol, reduce_size, price, timestamp, reason, *, confidence="N/A", meta: dict | None = None
    ) -> bool:
        """Partially closes a position (or fully closes if reduce_size >= remaining size).

        Side-effect: on success, stores the resulting trade_id on ``self._last_close_trade_id``
        so callers (e.g. lineage tracking) can reference the fill.
        """
        self._last_close_trade_id = None
        if symbol not in self.positions:
            return False

        pos = self.positions[symbol]
        entry = float(pos["entry_price"])
        pos_type = str(pos["type"]).upper()
        leverage = float(pos.get("leverage") or 1.0)
        leverage = max(1.0, leverage)

        try:
            size = float(pos["size"])
        except Exception:
            return False
        if size <= 0:
            return False

        try:
            reduce_size = float(reduce_size)
        except Exception:
            return False
        reduce_size = max(0.0, min(size, reduce_size))
        reduce_size = hyperliquid_meta.round_size(symbol, reduce_size)
        if reduce_size <= 0:
            return False

        trade_cfg = get_trade_params(symbol)
        slippage_bps = float(trade_cfg.get("slippage_bps", HL_SLIPPAGE_BPS))
        use_bbo = bool(trade_cfg.get("use_bbo_for_fills", True))
        min_notional = float(trade_cfg.get("min_notional_usd", 10.0))

        close_side = "SELL" if pos_type == "LONG" else "BUY"
        fill_price = _get_fill_price(
            symbol,
            close_side,
            float(price),
            slippage_bps=slippage_bps,
            use_bbo_for_fills=use_bbo,
        )

        notional = abs(reduce_size) * fill_price

        # v5.012: 殘留倉位清理 (Dust Residue Cleanup - DRC)
        # 如果平倉後剩餘嘅金額細過 $3.0，就直接全平，防止出現「喪屍倉位」。
        remaining_test = size - reduce_size
        if remaining_test > 0 and (remaining_test * fill_price) < 3.0:
            reduce_size = size
            notional = abs(reduce_size) * fill_price

        # Never block a full close due to min_notional; only apply it to partial reductions.
        if notional < min_notional and reduce_size < size:
            return False

        gross_pnl = ((fill_price - entry) * reduce_size) if pos_type == "LONG" else ((entry - fill_price) * reduce_size)

        fee_rate = _effective_fee_rate()
        fee_usd = notional * fee_rate
        pnl = gross_pnl - fee_usd
        # AQC-755: self.balance no longer manually updated — kernel is authoritative.

        remaining = size - reduce_size
        is_final = remaining <= 0

        # Update / clear position
        if is_final:
            self.clear_position_state(symbol)
            del self.positions[symbol]
        else:
            pos["size"] = remaining
            # Approx margin used at entry price (cap logic uses live marks separately).
            pos["margin_used"] = (abs(remaining) * entry) / leverage if entry > 0 else 0.0
            self.upsert_position_state(symbol)

        # AQC-755: sync kernel BEFORE log so self.balance reads post-trade value.
        close_signal = "SELL" if pos_type == "LONG" else "BUY"
        self._kernel_sync_event(
            symbol=symbol,
            signal=close_signal,
            price=fill_price,
            size=reduce_size,
            timestamp_ms=int(time.time() * 1000),
        )

        # Log fill
        action = "CLOSE" if is_final else "REDUCE"
        margin_delta = -(notional / leverage) if leverage > 0 else 0.0
        close_trade_id = self.log_trade(
            symbol,
            action,
            pos_type,
            fill_price,
            reduce_size,
            reason,
            confidence,
            pnl,
            fee_usd=fee_usd,
            fee_rate=fee_rate,
            leverage=leverage,
            margin_used=margin_delta,
            meta=meta,
        )
        self._last_close_trade_id = close_trade_id
        logger.info(
            f"✅ {action} {pos_type} {symbol} px={fill_price:.4f} size={reduce_size:.6f} "
            f"notional~=${notional:.2f} lev={leverage:.0f} Δmargin~=${margin_delta:+.2f} | "
            f"Reason: {reason} | GrossPnL={gross_pnl:.2f} | Fee={fee_usd:.4f} | NetPnL={pnl:.2f}"
        )
        self._kernel_persist()
        return True

    def execute_trade(
        self,
        symbol,
        signal,
        price,
        timestamp,
        confidence,
        atr=0.0,
        indicators=None,
        *,
        action=None,
        target_size=None,
        reason=None,
        mode=None,
    ):
        del mode
        kernel_reason_code = ""
        try:
            kernel_reason_code = str(
                (indicators if indicators is not None else {}).get("_kernel_reason_code") or ""
            ).strip().lower()
        except Exception:
            kernel_reason_code = ""
        # Runtime SSOT hardening: entry decisions come from Rust kernel intents.
        # Keep Python execution/risk rails and audit logging, but disable legacy
        # Python entry-gate decision filters (confidence/PESC/SSF/REEF).
        python_entry_gates_enabled = False

        action_upper = str(action or "").strip().upper()
        if action_upper not in {"OPEN", "ADD", "CLOSE", "REDUCE"}:
            logger.debug(
                "execute_trade: skip legacy signal-only path for %s (action=%r)",
                symbol,
                action,
            )
            return

        # action kwarg: "OPEN", "CLOSE", "ADD", "REDUCE" — Rust-kernel SSOT dispatch.
        if action_upper == "CLOSE":
            if symbol in self.positions:
                close_meta = {"reason_code": kernel_reason_code} if kernel_reason_code else None
                self.close_position(symbol, price, timestamp, reason=reason or "Action CLOSE", meta=close_meta)
            return
        if action_upper == "ADD":
            if symbol in self.positions:
                self.add_to_position(symbol, price, timestamp, confidence, atr=atr, indicators=indicators)
            return
        if action_upper == "REDUCE":
            if symbol in self.positions:
                pos = self.positions[symbol]
                reduce_sz = float(target_size) if target_size is not None else float(pos.get("size", 0))
                reduce_meta = {"reason_code": kernel_reason_code} if kernel_reason_code else None
                self.reduce_position(
                    symbol,
                    reduce_sz,
                    price,
                    timestamp,
                    reason=reason or "Action REDUCE",
                    confidence=confidence,
                    meta=reduce_meta,
                )
            return
        if action_upper == "OPEN":
            if symbol in self.positions:
                return  # already open — skip (match LiveTrader)

        # Normalise indicators: pandas Series → dict (avoids truth-value crash)
        if indicators is not None and not isinstance(indicators, dict):
            try:
                indicators = indicators.to_dict()
            except Exception:
                indicators = {}
        # Log all valid signals to the signals table for audit
        if signal != "NEUTRAL":
            ensure_db()
            conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
            cursor = conn.cursor()
            audit = None
            if indicators is not None:
                try:
                    audit = indicators.get("audit")
                except Exception:
                    audit = None
            meta_json = _json_dumps_safe(audit) if audit else None
            cursor.execute(
                """
                INSERT INTO signals (timestamp, symbol, signal, confidence, price, rsi, ema_fast, ema_slow, meta_json, run_fingerprint)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    symbol,
                    signal,
                    confidence,
                    price,
                    indicators.get("RSI", 0) if indicators is not None else 0,
                    indicators.get("EMA_fast", 0) if indicators is not None else 0,
                    indicators.get("EMA_slow", 0) if indicators is not None else 0,
                    meta_json,
                    get_run_fingerprint(),
                ),
            )
            conn.commit()
            conn.close()

        # OPEN path is kernel-action driven; do not run legacy signal flip/add logic.
        if symbol in self.positions:
            return

        if signal == "NEUTRAL":
            return

        # Open new position if no position for this symbol
        if symbol not in self.positions:
            # Block new entries when market data is stale (WS + REST both failed).
            if getattr(self, "_data_stale", False):
                logger.warning("execute_trade: blocking new entry for %s — market data is stale", symbol)
                log_audit_event(
                    symbol,
                    "ENTRY_SKIP_DATA_STALE",
                    data={"signal": str(signal or "").upper(), "confidence": str(confidence or "")},
                )
                # AQC-804: blocked entry decision
                try:
                    create_decision_event(
                        symbol=symbol,
                        event_type="entry_signal",
                        status="blocked",
                        phase="gate_evaluation",
                        triggered_by="signal",
                        action_taken="blocked",
                        rejection_reason="data_stale",
                        context={"signal": str(signal or ""), "confidence": str(confidence or "")},
                    )
                except Exception:
                    pass
                return

            cfg = get_strategy_config(symbol)
            trade_cfg = cfg.get("trade") or {}
            thr = cfg.get("thresholds") or {}

            # AQC-803: Resolve parent decision_id from analyze() for gate tracing.
            _parent_did = None
            try:
                if indicators is not None:
                    _parent_did = indicators.get("_decision_id")
            except Exception:
                pass
            # Accumulate execution gate results; flushed on success or first failure.
            _exec_gates: list[dict] = []

            # v5.035: Entry confidence gate.
            min_entry_conf = str(trade_cfg.get("entry_min_confidence", "high"))
            if python_entry_gates_enabled and not _conf_ok(confidence, min_confidence=min_entry_conf):
                logger.warning(f"🟡 Skipping {symbol} entry: confidence '{confidence}' < '{min_entry_conf}'")
                log_audit_event(
                    symbol,
                    "ENTRY_SKIP_LOW_CONFIDENCE",
                    data={
                        "signal": str(signal or "").upper(),
                        "confidence": str(confidence or "").lower(),
                        "min_entry_confidence": str(min_entry_conf).lower(),
                    },
                )
                # AQC-803: log blocked confidence gate
                try:
                    _conf_rank = {"low": 1, "medium": 2, "high": 3}
                    _did = create_decision_event(
                        symbol=symbol,
                        event_type="gate_block",
                        status="blocked",
                        phase="gate_evaluation",
                        parent_decision_id=_parent_did,
                        triggered_by="schedule",
                        action_taken="blocked",
                        rejection_reason=f"confidence {confidence} < {min_entry_conf}",
                    )
                    _log_gates_batch(
                        _did,
                        [
                            {
                                "gate_name": "confidence_gate",
                                "gate_passed": False,
                                "metric_value": float(_conf_rank.get(str(confidence or "").lower(), 0)),
                                "threshold_value": float(_conf_rank.get(str(min_entry_conf).lower(), 3)),
                                "operator": ">=",
                                "explanation": f"confidence '{confidence}' < min '{min_entry_conf}'",
                            }
                        ],
                    )
                except Exception:
                    pass
                return

            # Optional hard limit: max concurrent net positions across all symbols.
            try:
                max_open_positions = int(trade_cfg.get("max_open_positions", 0) or 0)
            except Exception:
                max_open_positions = 0
            if max_open_positions > 0 and len(self.positions or {}) >= max_open_positions:
                logger.warning(f"🟡 Skipping {symbol} entry: max_open_positions={max_open_positions} reached")
                log_audit_event(
                    symbol,
                    "ENTRY_SKIP_MAX_OPEN_POSITIONS",
                    data={
                        "signal": str(signal or "").upper(),
                        "confidence": str(confidence or "").lower(),
                        "max_open_positions": int(max_open_positions),
                        "open_positions": int(len(self.positions or {})),
                    },
                )
                # AQC-803: log blocked max_positions gate
                try:
                    _n_open = len(self.positions or {})
                    _did = create_decision_event(
                        symbol=symbol,
                        event_type="gate_block",
                        status="blocked",
                        phase="risk_check",
                        parent_decision_id=_parent_did,
                        triggered_by="schedule",
                        action_taken="blocked",
                        rejection_reason=f"max_open_positions {_n_open}>={max_open_positions}",
                    )
                    _log_gates_batch(
                        _did,
                        [
                            {
                                "gate_name": "max_positions",
                                "gate_passed": False,
                                "metric_value": float(_n_open),
                                "threshold_value": float(max_open_positions),
                                "operator": "<",
                                "explanation": f"open={_n_open} >= max={max_open_positions}",
                            }
                        ],
                    )
                except Exception:
                    pass
                return

            # v5.014: 同向平倉後進場冷卻 (Post-Exit Same-Direction Cooldown - PESC)
            # v5.015: ADX 自適應冷卻 (ADX-Adaptive PESC)
            # v5.018: 弱趨勢 PESC 加強 (ADX < 25 時延長至 max_cd；強趨勢 ADX >= 40 縮短至 min_cd)。
            base_cooldown = float(trade_cfg.get("reentry_cooldown_minutes", 30))
            if python_entry_gates_enabled and base_cooldown > 0:
                adx_val = indicators.get("ADX", 30) if indicators is not None else 30
                min_cd = float(trade_cfg.get("reentry_cooldown_min_mins", 45))
                max_cd = float(trade_cfg.get("reentry_cooldown_max_mins", 180))

                # 線性插值：ADX 25->40 對應 CD max_cd->min_cd
                if adx_val >= 40:
                    reentry_cooldown = min_cd
                elif adx_val <= 25:
                    reentry_cooldown = max_cd
                else:
                    t = (adx_val - 25) / (40 - 25)
                    reentry_cooldown = max_cd - t * (max_cd - min_cd)

                last_ts_s = None
                last_type = None
                last_reason = None
                try:
                    conn = sqlite3.connect(DB_PATH, timeout=_DB_TIMEOUT_S)
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        SELECT timestamp, type, reason
                        FROM trades
                        WHERE symbol = ? AND action = 'CLOSE'
                        ORDER BY id DESC LIMIT 1
                        """,
                        (symbol,),
                    )
                    row = cursor.fetchone()
                    conn.close()

                    if row:
                        last_ts, last_type, last_reason = row
                        try:
                            ts_s = str(last_ts or "").strip()
                            if ts_s.endswith("Z"):
                                ts_s = ts_s[:-1] + "+00:00"
                            dt = datetime.datetime.fromisoformat(ts_s)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=datetime.timezone.utc)
                            last_ts_s = float(dt.timestamp())
                            last_type = str(last_type or "").upper()
                            last_reason = str(last_reason or "")
                        except Exception:
                            last_ts_s = None
                except Exception as e:
                    logger.warning(f"⚠️ PESC db query failed for {symbol}: {e}")
                    try:
                        conn.close()
                    except Exception:
                        pass

                if last_ts_s is not None and last_type:
                    diff_mins = max(0.0, (time.time() - float(last_ts_s)) / 60.0)
                    target_type = "LONG" if signal == "BUY" else "SHORT"
                    if (
                        diff_mins < reentry_cooldown
                        and str(last_type).upper() == target_type
                        and "Signal Flip" not in (last_reason or "")
                    ):
                        logger.debug(
                            f"⏳ PESC: Skipping {symbol} {target_type} re-entry. Cooldown active "
                            f"({diff_mins:.1f}/{reentry_cooldown:.1f}m, ADX: {float(adx_val):.1f})"
                        )
                        log_audit_event(
                            symbol,
                            "ENTRY_SKIP_PESC",
                            data={
                                "signal": str(signal or "").upper(),
                                "confidence": str(confidence or "").lower(),
                                "adx": float(adx_val),
                                "cooldown_mins": float(reentry_cooldown),
                                "diff_mins": float(diff_mins),
                                "last_close_ts": None if last_ts_s is None else float(last_ts_s),
                                "last_type": str(last_type or ""),
                                "last_reason": str(last_reason or ""),
                            },
                        )
                        # AQC-803: log blocked PESC gate
                        try:
                            _did = create_decision_event(
                                symbol=symbol,
                                event_type="gate_block",
                                status="blocked",
                                phase="gate_evaluation",
                                parent_decision_id=_parent_did,
                                triggered_by="schedule",
                                action_taken="blocked",
                                rejection_reason=f"PESC cooldown {diff_mins:.1f}/{reentry_cooldown:.1f}m",
                            )
                            _log_gates_batch(
                                _did,
                                [
                                    {
                                        "gate_name": "pesc_cooldown",
                                        "gate_passed": False,
                                        "metric_value": float(diff_mins),
                                        "threshold_value": float(reentry_cooldown),
                                        "operator": ">=",
                                        "explanation": f"elapsed {diff_mins:.1f}m < cooldown {reentry_cooldown:.1f}m (ADX {float(adx_val):.1f})",
                                    }
                                ],
                            )
                        except Exception:
                            pass
                        return

            # v5.017: 信號穩定性過濾 (Signal Stability Filter - SSF)
            # 進場前檢查 MACD Histogram 嘅動量方向。
            # v5.037: Make SSF configurable via YAML (`trade.enable_ssf_filter`).
            enable_ssf = bool(trade_cfg.get("enable_ssf_filter", True))
            if python_entry_gates_enabled and enable_ssf and indicators is not None:
                macd_h = indicators.get("MACD_hist", 0)
                if signal == "BUY" and macd_h < 0:
                    # 做多但 MACD 仲係負數，代表動量仲未轉正。
                    logger.debug(f"⏳ SSF: Skipping {symbol} BUY. MACD_hist ({macd_h:.6f}) is negative.")
                    log_audit_event(
                        symbol,
                        "ENTRY_SKIP_SSF",
                        data={
                            "signal": "BUY",
                            "confidence": str(confidence or "").lower(),
                            "macd_hist": float(macd_h),
                        },
                    )
                    # AQC-803: log blocked SSF gate
                    try:
                        _did = create_decision_event(
                            symbol=symbol,
                            event_type="gate_block",
                            status="blocked",
                            phase="gate_evaluation",
                            parent_decision_id=_parent_did,
                            triggered_by="schedule",
                            action_taken="blocked",
                            rejection_reason=f"SSF: MACD_hist {macd_h:.6f} negative for BUY",
                        )
                        _log_gates_batch(
                            _did,
                            [
                                {
                                    "gate_name": "ssf_filter",
                                    "gate_passed": False,
                                    "metric_value": float(macd_h),
                                    "threshold_value": 0.0,
                                    "operator": ">",
                                    "explanation": f"BUY requires MACD_hist > 0, got {macd_h:.6f}",
                                }
                            ],
                        )
                    except Exception:
                        pass
                    return
                if signal == "SELL" and macd_h > 0:
                    # 做空但 MACD 仲係正數。
                    logger.debug(f"⏳ SSF: Skipping {symbol} SELL. MACD_hist ({macd_h:.6f}) is positive.")
                    log_audit_event(
                        symbol,
                        "ENTRY_SKIP_SSF",
                        data={
                            "signal": "SELL",
                            "confidence": str(confidence or "").lower(),
                            "macd_hist": float(macd_h),
                        },
                    )
                    # AQC-803: log blocked SSF gate
                    try:
                        _did = create_decision_event(
                            symbol=symbol,
                            event_type="gate_block",
                            status="blocked",
                            phase="gate_evaluation",
                            parent_decision_id=_parent_did,
                            triggered_by="schedule",
                            action_taken="blocked",
                            rejection_reason=f"SSF: MACD_hist {macd_h:.6f} positive for SELL",
                        )
                        _log_gates_batch(
                            _did,
                            [
                                {
                                    "gate_name": "ssf_filter",
                                    "gate_passed": False,
                                    "metric_value": float(macd_h),
                                    "threshold_value": 0.0,
                                    "operator": "<",
                                    "explanation": f"SELL requires MACD_hist < 0, got {macd_h:.6f}",
                                }
                            ],
                        )
                    except Exception:
                        pass
                    return

            # v5.018: RSI 進場極端過濾 (REEF)
            # 做多時 RSI 太高 (overbought) 或做空時 RSI 太低 (oversold) 禁止進場。
            if python_entry_gates_enabled and bool(trade_cfg.get("enable_reef_filter", True)) and indicators is not None:
                rsi_v = _safe_float(indicators.get("RSI"), None)
                if rsi_v is not None:
                    long_block = _safe_float(trade_cfg.get("reef_long_rsi_block_gt"), 70.0) or 70.0
                    short_block = _safe_float(trade_cfg.get("reef_short_rsi_block_lt"), 30.0) or 30.0
                    if signal == "BUY" and float(rsi_v) > float(long_block):
                        logger.info(
                            f"⛔ REEF: Skipping {symbol} BUY. RSI ({float(rsi_v):.1f}) > {float(long_block):.1f}"
                        )
                        log_audit_event(
                            symbol,
                            "ENTRY_SKIP_REEF",
                            data={
                                "signal": "BUY",
                                "confidence": str(confidence or "").lower(),
                                "rsi": float(rsi_v),
                                "threshold_gt": float(long_block),
                            },
                        )
                        # AQC-803: log blocked REEF gate
                        try:
                            _did = create_decision_event(
                                symbol=symbol,
                                event_type="gate_block",
                                status="blocked",
                                phase="gate_evaluation",
                                parent_decision_id=_parent_did,
                                triggered_by="schedule",
                                action_taken="blocked",
                                rejection_reason=f"REEF: RSI {float(rsi_v):.1f} > {float(long_block):.1f}",
                            )
                            _log_gates_batch(
                                _did,
                                [
                                    {
                                        "gate_name": "reef_filter",
                                        "gate_passed": False,
                                        "metric_value": float(rsi_v),
                                        "threshold_value": float(long_block),
                                        "operator": "<=",
                                        "explanation": f"BUY blocked: RSI {float(rsi_v):.1f} > {float(long_block):.1f}",
                                    }
                                ],
                            )
                        except Exception:
                            pass
                        return
                    if signal == "SELL" and float(rsi_v) < float(short_block):
                        logger.info(
                            f"⛔ REEF: Skipping {symbol} SELL. RSI ({float(rsi_v):.1f}) < {float(short_block):.1f}"
                        )
                        log_audit_event(
                            symbol,
                            "ENTRY_SKIP_REEF",
                            data={
                                "signal": "SELL",
                                "confidence": str(confidence or "").lower(),
                                "rsi": float(rsi_v),
                                "threshold_lt": float(short_block),
                            },
                        )
                        # AQC-803: log blocked REEF gate
                        try:
                            _did = create_decision_event(
                                symbol=symbol,
                                event_type="gate_block",
                                status="blocked",
                                phase="gate_evaluation",
                                parent_decision_id=_parent_did,
                                triggered_by="schedule",
                                action_taken="blocked",
                                rejection_reason=f"REEF: RSI {float(rsi_v):.1f} < {float(short_block):.1f}",
                            )
                            _log_gates_batch(
                                _did,
                                [
                                    {
                                        "gate_name": "reef_filter",
                                        "gate_passed": False,
                                        "metric_value": float(rsi_v),
                                        "threshold_value": float(short_block),
                                        "operator": ">=",
                                        "explanation": f"SELL blocked: RSI {float(rsi_v):.1f} < {float(short_block):.1f}",
                                    }
                                ],
                            )
                        except Exception:
                            pass
                        return

            # Simulated rate-limit gate (cooldown + budget).
            if not self._can_attempt_entry(symbol):
                return

            slippage_bps = float(trade_cfg.get("slippage_bps", HL_SLIPPAGE_BPS))
            use_bbo = bool(trade_cfg.get("use_bbo_for_fills", True))
            min_notional = float(trade_cfg.get("min_notional_usd", 10.0))
            max_total_margin_pct = float(trade_cfg.get("max_total_margin_pct", 0.60))

            equity_base = _safe_float(self.get_live_balance(), None)
            if equity_base is None or equity_base <= 0:
                equity_base = max(0.0, float(self.balance or 0.0))
                if equity_base <= 0:
                    logger.warning("execute_trade: equity_base is zero/negative, skipping %s", symbol)
                    return
            sizing = compute_entry_sizing(
                symbol=symbol,
                equity_base=equity_base,
                price=float(price),
                confidence=confidence,
                atr=float(atr or 0.0),
                indicators=indicators,
                trade_cfg=trade_cfg,
                thresholds=thr,
            )
            margin_target = float(sizing.margin_usd)
            leverage = float(sizing.leverage)

            current_margin = 0.0
            for sym, p in self.positions.items():
                current_margin += self._estimate_margin_used(sym, p)

            if (current_margin + margin_target) > (equity_base * max_total_margin_pct):
                logger.warning(
                    f"🟡 Skipping {symbol} entry: margin cap hit "
                    f"({current_margin + margin_target:.2f} > {equity_base * max_total_margin_pct:.2f})"
                )
                log_audit_event(
                    symbol,
                    "ENTRY_SKIP_MARGIN_CAP",
                    data={
                        "signal": str(signal or "").upper(),
                        "confidence": str(confidence or "").lower(),
                        "equity_base": float(equity_base),
                        "current_margin": float(current_margin),
                        "margin_target": float(margin_target),
                        "max_total_margin_pct": float(max_total_margin_pct),
                        "cap_margin": float(equity_base * max_total_margin_pct),
                    },
                )
                # AQC-803: log blocked margin gate
                try:
                    _total_margin = current_margin + margin_target
                    _cap = equity_base * max_total_margin_pct
                    _did = create_decision_event(
                        symbol=symbol,
                        event_type="gate_block",
                        status="blocked",
                        phase="risk_check",
                        parent_decision_id=_parent_did,
                        triggered_by="schedule",
                        action_taken="blocked",
                        rejection_reason=f"margin {_total_margin:.2f} > cap {_cap:.2f}",
                    )
                    _log_gates_batch(
                        _did,
                        [
                            {
                                "gate_name": "margin_limit",
                                "gate_passed": False,
                                "metric_value": float(_total_margin),
                                "threshold_value": float(_cap),
                                "operator": "<=",
                                "explanation": f"margin_needed={_total_margin:.2f} > cap={_cap:.2f} ({max_total_margin_pct:.0%} of equity)",
                            }
                        ],
                    )
                except Exception:
                    pass
                return

            # Notional with leverage (perps). Fees are charged on notional.
            bump_to_min = bool(trade_cfg.get("bump_to_min_notional", False))
            target_notional = float(sizing.desired_notional_usd)
            if target_notional < min_notional:
                if bump_to_min:
                    target_notional = min_notional
                else:
                    log_audit_event(
                        symbol,
                        "ENTRY_SKIP_MIN_NOTIONAL",
                        data={
                            "signal": str(signal or "").upper(),
                            "confidence": str(confidence or "").lower(),
                            "desired_notional": float(target_notional),
                            "min_notional": float(min_notional),
                            "leverage": float(leverage),
                            "margin_target": float(margin_target),
                        },
                    )
                    # AQC-804: blocked entry decision
                    try:
                        create_decision_event(
                            symbol=symbol,
                            event_type="entry_signal",
                            status="blocked",
                            phase="risk_check",
                            triggered_by="signal",
                            action_taken="blocked",
                            rejection_reason=f"min_notional ({target_notional:.2f} < {min_notional:.2f})",
                            context={"signal": str(signal or ""), "confidence": str(confidence or "")},
                        )
                    except Exception:
                        pass
                    return

            fill_price = _get_fill_price(
                symbol,
                "BUY" if signal == "BUY" else "SELL",
                float(price),
                slippage_bps=slippage_bps,
                use_bbo_for_fills=use_bbo,
            )
            max_notional = _safe_float(trade_cfg.get("max_notional_usd_per_order"), None)
            size = size_for_notional_bounds(
                symbol,
                price=fill_price,
                desired_notional=target_notional,
                min_notional=min_notional,
                max_notional=max_notional,
            )
            if size <= 0:
                return

            notional = abs(size) * fill_price
            if notional < min_notional:
                return

            # Recompute effective margin used after rounding.
            margin_used = notional / leverage if leverage > 0 else notional

            fee_rate = _effective_fee_rate()
            fee_usd = notional * fee_rate
            # AQC-755: self.balance no longer manually updated — kernel is authoritative.

            opened_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.positions[symbol] = {
                "type": "LONG" if signal == "BUY" else "SHORT",
                "entry_price": fill_price,
                "size": size,
                # Store entry confidence so exits can optionally behave differently (e.g. slow-drift low-conf).
                "confidence": str(confidence or "").strip().lower(),
                "entry_atr": atr,
                # ADX threshold used at entry — exit ADX exhaustion uses this value
                # so entry and exit can never contradict each other.
                "entry_adx_threshold": float(indicators.get("entry_adx_threshold", 0) or 0) if indicators else 0.0,
                "open_trade_id": None,
                "open_timestamp": opened_at,
                "trailing_sl": None,  # Initialize trailing SL
                "last_funding_time": int(time.time() * 1000),
                "leverage": leverage,
                "margin_used": margin_used,
                "adds_count": 0,
                "tp1_taken": 0,
                "last_add_time": 0,
            }
            # AQC-755: sync kernel BEFORE log so self.balance reads post-trade value.
            self._kernel_sync_event(
                symbol=symbol,
                signal=signal,
                price=fill_price,
                size=size,
                timestamp_ms=int(time.time() * 1000),
            )
            audit = None
            if indicators is not None:
                try:
                    audit = indicators.get("audit")
                except Exception:
                    audit = None
            default_open_reason = (
                "Signal Trigger [REVERSED]" if (indicators or {}).get("_reversed_entry") is True else "Signal Trigger"
            )
            open_reason = str(reason or default_open_reason).strip() or default_open_reason
            trade_meta = dict(audit) if isinstance(audit, dict) else {}
            if kernel_reason_code:
                trade_meta["reason_code"] = kernel_reason_code
            trade_id = self.log_trade(
                symbol,
                "OPEN",
                "LONG" if signal == "BUY" else "SHORT",
                fill_price,
                size,
                open_reason,
                confidence,
                entry_atr=atr,
                fee_usd=fee_usd,
                fee_rate=fee_rate,
                leverage=leverage,
                margin_used=margin_used,
                timestamp_override=opened_at,
                meta=trade_meta or None,
            )
            self.positions[symbol]["open_trade_id"] = trade_id
            self.upsert_position_state(symbol)
            self._note_entry_attempt(symbol)
            _rev_tag = " [REVERSED]" if (indicators or {}).get("_reversed_entry") is True else ""
            logger.info(
                f"🚀 OPEN {('LONG' if signal == 'BUY' else 'SHORT')} {symbol} "
                f"px={fill_price:.4f} size={size:.6f} notional~=${notional:.2f} "
                f"lev={leverage:.0f} margin~=${margin_used:.2f} fee=${fee_usd:.4f} conf={confidence}{_rev_tag}"
            )
            log_audit_event(
                symbol,
                "ENTRY_OPEN",
                data={
                    "signal": str(signal or "").upper(),
                    "confidence": str(confidence or "").lower(),
                    "px": float(fill_price),
                    "size": float(size),
                    "notional": float(notional),
                    "leverage": float(leverage),
                    "margin_used": float(margin_used),
                    "fee_usd": float(fee_usd or 0.0),
                    "fee_rate": float(fee_rate or 0.0),
                    "reversed_entry": True if (indicators or {}).get("_reversed_entry") is True else False,
                },
            )
            # AQC-803: log all execution gates as passed + link decision to trade
            try:
                _exec_did = create_decision_event(
                    symbol=symbol,
                    event_type="fill",
                    status="executed",
                    phase="execution",
                    parent_decision_id=_parent_did,
                    trade_id=trade_id,
                    triggered_by="schedule",
                    action_taken="open_long" if signal == "BUY" else "open_short",
                )
                _rsi_v = float(indicators.get("RSI", 0)) if indicators else 0.0
                _macd_h = float(indicators.get("MACD_hist", 0)) if indicators else 0.0
                _reef_ok = True
                if bool(trade_cfg.get("enable_reef_filter", True)) and indicators:
                    _reef_thr = _safe_float(trade_cfg.get("reef_long_rsi_block_gt"), 70.0) or 70.0
                    if signal == "BUY":
                        _reef_ok = _rsi_v <= _reef_thr
                    else:
                        _reef_thr = _safe_float(trade_cfg.get("reef_short_rsi_block_lt"), 30.0) or 30.0
                        _reef_ok = _rsi_v >= _reef_thr
                _ssf_ok = True
                if bool(trade_cfg.get("enable_ssf_filter", True)) and indicators:
                    if signal == "BUY":
                        _ssf_ok = _macd_h >= 0
                    else:
                        _ssf_ok = _macd_h <= 0
                _cap = equity_base * max_total_margin_pct
                _exec_rows = [
                    {
                        "gate_name": "reef_filter",
                        "gate_passed": _reef_ok,
                        "metric_value": _rsi_v,
                        "operator": "<=" if signal == "BUY" else ">=",
                        "explanation": f"RSI {_rsi_v:.1f} passed REEF",
                    },
                    {
                        "gate_name": "ssf_filter",
                        "gate_passed": _ssf_ok,
                        "metric_value": _macd_h,
                        "threshold_value": 0.0,
                        "operator": ">=" if signal == "BUY" else "<=",
                        "explanation": f"MACD_hist {_macd_h:.6f} sign-aligned",
                    },
                    {
                        "gate_name": "confidence_gate",
                        "gate_passed": True,
                        "explanation": f"confidence '{confidence}' >= min '{str(trade_cfg.get('entry_min_confidence', 'high'))}'",
                    },
                    {
                        "gate_name": "max_positions",
                        "gate_passed": True,
                        "metric_value": float(len(self.positions or {})),
                        "explanation": "within max_open_positions",
                    },
                    {
                        "gate_name": "margin_limit",
                        "gate_passed": True,
                        "metric_value": float(current_margin + margin_used),
                        "threshold_value": float(_cap),
                        "operator": "<=",
                        "explanation": f"margin {current_margin + margin_used:.2f} <= cap {_cap:.2f}",
                    },
                ]
                _log_gates_batch(_exec_did, _exec_rows)
                # Link parent signal decision to this trade
                if _parent_did:
                    link_decision_to_trade(_parent_did, trade_id)
            except Exception:
                pass

            # AQC-804: Decision lineage — entry signal → trade
            try:
                _ind_ctx = {}
                if indicators is not None:
                    for _k in (
                        "RSI",
                        "ADX",
                        "ADX_slope",
                        "MACD_hist",
                        "EMA_fast",
                        "EMA_slow",
                        "EMA_macro",
                        "ATR",
                        "ATR_slope",
                        "bb_width_ratio",
                        "stoch_k",
                        "stoch_d",
                        "volume",
                        "vol_sma",
                        "funding_rate",
                    ):
                        _v = indicators.get(_k)
                        if _v is not None:
                            try:
                                _ind_ctx[_k] = float(_v)
                            except Exception:
                                pass
                _entry_decision_id = create_decision_event(
                    symbol=symbol,
                    event_type="entry_signal",
                    status="executed",
                    phase="execution",
                    triggered_by="signal",
                    action_taken=f"open_{'long' if signal == 'BUY' else 'short'}",
                    parent_decision_id=_parent_did,
                    context={
                        "signal": str(signal or ""),
                        "confidence": str(confidence or ""),
                        "price": float(fill_price),
                        "size": float(size),
                        "atr": float(atr or 0.0),
                        "indicators": _ind_ctx,
                    },
                )
                if trade_id is not None:
                    link_decision_to_trade(_entry_decision_id, int(trade_id))
                    create_lineage(signal_decision_id=_entry_decision_id, entry_trade_id=int(trade_id))
            except Exception as _dle:
                logger.debug("AQC-804: entry lineage logging failed: %s", _dle)
            self._kernel_persist()

    def check_exit_conditions(
        self, symbol, current_price, timestamp, is_anomaly=False, dynamic_tp_mult=None, indicators=None
    ):
        # Normalise indicators: pandas Series → dict
        if indicators is not None and not isinstance(indicators, dict):
            try:
                indicators = indicators.to_dict()
            except Exception:
                indicators = {}
        pos = self.positions.get(symbol)
        if not pos:
            return

        # AQC-804: capture open_trade_id early (before position may be deleted by close).
        _open_trade_id = pos.get("open_trade_id")
        _open_timestamp = pos.get("open_timestamp")

        # AQC-804: helper to log exit decision + complete lineage after a full close.
        def _log_exit_lineage(exit_reason: str, *, is_partial: bool = False) -> None:
            try:
                close_trade_id = getattr(self, "_last_close_trade_id", None)
                exit_decision_id = create_decision_event(
                    symbol=symbol,
                    event_type="exit_check",
                    status="executed",
                    phase="execution",
                    triggered_by=exit_reason,
                    action_taken="reduce" if is_partial else "close",
                    trade_id=close_trade_id,
                    context={
                        "exit_reason": exit_reason,
                        "exit_price": float(current_price),
                        "entry_trade_id": _open_trade_id,
                        "is_partial": is_partial,
                    },
                )
                if not is_partial and _open_trade_id is not None and close_trade_id is not None:
                    complete_lineage(
                        entry_trade_id=int(_open_trade_id),
                        exit_decision_id=exit_decision_id,
                        exit_trade_id=int(close_trade_id),
                        exit_reason=exit_reason,
                        duration_ms=_compute_duration_ms(_open_timestamp),
                    )
            except Exception as _dle:
                logger.debug("AQC-804: exit lineage logging failed: %s", _dle)

        # AQC-804: throttle counter for hold decisions (only log every 10th check).
        _exit_check_key = f"_exit_check_count_{symbol}"
        _exit_check_count = getattr(self, _exit_check_key, 0)
        setattr(self, _exit_check_key, _exit_check_count + 1)

        cfg = get_strategy_config(symbol)
        trade_cfg = cfg.get("trade") or {}
        flt = cfg.get("filters") or {}

        sl_atr_mult = float(trade_cfg.get("sl_atr_mult", SL_ATR_MULT))
        tp_atr_mult = float(trade_cfg.get("tp_atr_mult", TP_ATR_MULT))
        trailing_start_atr = float(trade_cfg.get("trailing_start_atr", 1.0))
        trailing_distance_atr = float(trade_cfg.get("trailing_distance_atr", 0.8))
        glitch_price_dev_pct = float(trade_cfg.get("glitch_price_dev_pct", 0.40))
        glitch_atr_mult = float(trade_cfg.get("glitch_atr_mult", 12.0))

        pos_conf = str(pos.get("confidence") or "").strip().lower()

        # Optional: per-confidence exit tuning (useful for low-confidence slow-drift entries).
        if pos_conf.startswith("l"):
            try:
                v = float(trade_cfg.get("trailing_start_atr_low_conf", 0.0) or 0.0)
                if v > 0:
                    trailing_start_atr = v
            except Exception:
                pass
            try:
                v = float(trade_cfg.get("trailing_distance_atr_low_conf", 0.0) or 0.0)
                if v > 0:
                    trailing_distance_atr = v
            except Exception:
                pass

        # Smart-exit ADX exhaustion threshold: use the entry's ADX threshold so
        # entry and exit can never contradict (e.g. slow-drift enters at ADX=10,
        # so ADX exhaustion only fires below 10, not at the old fixed 18).
        # Falls back to trade_cfg value for positions opened before this change.
        _entry_adx_thr = float(pos.get("entry_adx_threshold", 0) or 0)
        if _entry_adx_thr > 0:
            adx_exhaustion_lt = _entry_adx_thr
        else:
            # Legacy fallback for positions without entry_adx_threshold.
            try:
                adx_exhaustion_lt = float(trade_cfg.get("smart_exit_adx_exhaustion_lt", 18.0))
            except Exception:
                adx_exhaustion_lt = 20.0
            if pos_conf.startswith("l") and ("smart_exit_adx_exhaustion_lt_low_conf" in trade_cfg):
                try:
                    adx_exhaustion_lt = float(trade_cfg.get("smart_exit_adx_exhaustion_lt_low_conf"))
                except Exception:
                    pass
        adx_exhaustion_lt = float(max(0.0, adx_exhaustion_lt))

        # Exits should generally still run during high-volatility candles (more realistic).
        # If you want to freeze exits during anomaly flags, toggle this in YAML:
        #   global.filters.block_exits_on_anomaly: true
        if is_anomaly and bool(flt.get("block_exits_on_anomaly", False)):
            logger.info(f"🛡️ Blocking exit for {symbol} due to anomaly flag: {current_price}")
            return

        # Simulated exit cooldown (mirrors live exchange rate limits).
        # WARN-X1: Hard SL must bypass cooldown to prevent uncapped losses.
        if not self._can_attempt_exit(symbol):
            _cd_entry = pos["entry_price"]
            _cd_atr = pos.get("entry_atr", 0.0)
            if _cd_atr != _cd_atr:  # NaN guard
                _cd_atr = 0.0
            if _cd_atr <= 0:
                _cd_atr = _cd_entry * 0.005
            _cd_sl = (
                _cd_entry - (_cd_atr * sl_atr_mult) if pos["type"] == "LONG" else _cd_entry + (_cd_atr * sl_atr_mult)
            )
            _cd_sl_hit = (pos["type"] == "LONG" and current_price <= _cd_sl) or (
                pos["type"] == "SHORT" and current_price >= _cd_sl
            )
            if not _cd_sl_hit:
                return

        entry = pos["entry_price"]
        atr = pos.get("entry_atr", 0.0)
        if atr != atr:  # NaN guard
            atr = 0.0

        # Fallback for legacy trades with no ATR
        if atr <= 0:
            atr = entry * 0.005  # Default to 0.5% volatility if unknown

        # Optional glitch guardrail (defaults off): blocks exits if price is *extremely* far from entry.
        # Prefer using WS mids/BBO for robustness instead of freezing exits by default.
        if bool(trade_cfg.get("block_exits_on_extreme_dev", False)):
            price_dev_pct = abs(current_price - entry) / entry
            if price_dev_pct > glitch_price_dev_pct or (
                atr > 0 and abs(current_price - entry) > (atr * glitch_atr_mult)
            ):
                logger.warning(
                    f"⚠️ Extreme price deviation detected for {symbol} (${current_price}). Possible glitch. Blocking exit."
                )
                return

        pos_type = pos["type"]

        # 1. Standard ATR-based Stop Loss
        current_sl_atr_mult = sl_atr_mult

        # v3.3: ADX Slope-Adjusted Stop (ASE)
        # If trend is weakening (ADX slope < 0) and position is underwater, tighten stop by 20%
        is_underwater = (pos_type == "LONG" and current_price < entry) or (
            pos_type == "SHORT" and current_price > entry
        )
        if indicators is not None and indicators.get("ADX_slope", 0) < 0 and is_underwater:
            current_sl_atr_mult *= 0.8

        # v5.005: 資金費率利好緩衝 (Funding Tailwind Buffer - FTB)
        # 如果正喺度收緊高額資金費率 (> 0.005%/hr)，將止損 ATR 倍數放寬 20%，避免被短暫嘅插針洗出局。
        funding_rate = indicators.get("funding_rate", 0.0) if indicators is not None else 0.0
        is_tailwind = (pos_type == "LONG" and funding_rate < 0) or (pos_type == "SHORT" and funding_rate > 0)
        if is_tailwind and abs(funding_rate) > 0.00005:
            current_sl_atr_mult *= 1.2

        # v5.016: ADX-Adaptive Stop Expansion (DASE)
        adx_val = indicators.get("ADX", 0) if indicators is not None else 0
        if adx_val > 40.0:
            px_delta_atr = abs(current_price - entry) / atr if atr > 0 else 0
            if px_delta_atr > 0.5:
                current_sl_atr_mult *= 1.15

        # v5.019: 強趨勢止損保護 (Stop Loss Buffer - SLB)
        # 如果 ADX > 45 (進入飽和/強趨勢區)，將整體止損空間放寬 10%。
        # 配合 DASE，提升喺極端波動（插針）中嘅生存率。
        if adx_val > 45.0:
            current_sl_atr_mult *= 1.10

        # v5.016: RSI Trend-Guard
        rsi_val = indicators.get("RSI", 50) if indicators is not None else 50
        min_trailing_dist = 0.5
        if (pos_type == "LONG" and rsi_val > 60.0) or (pos_type == "SHORT" and rsi_val < 40.0):
            min_trailing_dist = 0.7

        sl_price = entry - (atr * current_sl_atr_mult) if pos_type == "LONG" else entry + (atr * current_sl_atr_mult)

        # 1.1 Breakeven Stop (configurable)
        be_enabled = bool(trade_cfg.get("enable_breakeven_stop", True))
        try:
            be_start_atr = float(trade_cfg.get("breakeven_start_atr", 0.7))
        except Exception:
            be_start_atr = 0.7
        try:
            be_buffer_atr = float(trade_cfg.get("breakeven_buffer_atr", 0.05))
        except Exception:
            be_buffer_atr = 0.05

        if be_enabled and be_start_atr > 0:
            if pos_type == "LONG":
                if (current_price - entry) >= (atr * be_start_atr):
                    sl_price = max(sl_price, entry + (atr * be_buffer_atr))
            else:
                if (entry - current_price) >= (atr * be_start_atr):
                    sl_price = min(sl_price, entry - (atr * be_buffer_atr))

        # 2. Trailing Stop Logic (v3.1 Optimization)
        # Use tighter trailing distance when in high profit or when trend weakens
        effective_trailing_dist = trailing_distance_atr
        profit_atr = (current_price - entry) / atr if pos_type == "LONG" else (entry - current_price) / atr

        # v5.015: 波動率緩衝移動止損 (Volatility-Buffered Trailing Stop)
        # 如果 bb_width_ratio > 1.2 (代表波動率正在顯著擴張)，放寬移動止損距離 25%，減少被插針掃出的機會。
        if bool(trade_cfg.get("enable_vol_buffered_trailing", True)) and indicators is not None:
            bb_width = indicators.get("bb_width", 0)
            avg_bb_width = indicators.get("avg_bb_width", 0)
            bb_width_ratio = bb_width / avg_bb_width if avg_bb_width > 0 else 1.0
            if bb_width_ratio > 1.2:
                effective_trailing_dist *= 1.25

        if profit_atr > 2.0:
            # v5.006: 移動止損獲利保護修正 (Trailing Stop Profit-Vol Fix - TSPV)
            # 如果 ATR_slope > 0 (波動擴張)，收緊幅度由 50% 降至 25%，增加容錯空間。
            # v5.013: 趨勢加速保護 (Trend-Acceleration Trailing Protection - TATP)
            # 如果趨勢正處於強勁加速期 (ADX > 35 且 ADX_slope > 0)，則暫停收緊移動止損，給予更多呼吸空間。
            tighten_mult = 0.5
            adx_val = indicators.get("ADX", 0) if indicators is not None else 0
            adx_slope = indicators.get("ADX_slope", 0) if indicators is not None else 0
            atr_slope = indicators.get("ATR_slope", 0) if indicators is not None else 0

            if adx_val > 35 and adx_slope > 0:
                tighten_mult = 1.0  # 不收緊
            elif atr_slope > 0.0:
                tighten_mult = 0.75

            effective_trailing_dist = trailing_distance_atr * tighten_mult
        elif indicators is not None and indicators.get("ADX", 50) < 25:
            effective_trailing_dist = trailing_distance_atr * 0.7  # Tighten by 30% if trend fades

        if pos_type == "LONG":
            if profit_atr >= trailing_start_atr:
                potential_ts = current_price - (atr * max(min_trailing_dist, effective_trailing_dist))
                if pos["trailing_sl"] is None or potential_ts > pos["trailing_sl"]:
                    pos["trailing_sl"] = potential_ts
                    self.upsert_position_state(symbol)
        else:
            if profit_atr >= trailing_start_atr:
                potential_ts = current_price + (atr * max(min_trailing_dist, effective_trailing_dist))
                if pos["trailing_sl"] is None or potential_ts < pos["trailing_sl"]:
                    pos["trailing_sl"] = potential_ts
                    self.upsert_position_state(symbol)

        if pos["trailing_sl"]:
            sl_price = pos["trailing_sl"]

        # 3. Take Profit
        tp_mult = dynamic_tp_mult or tp_atr_mult
        tp_price = entry + (atr * tp_mult) if pos_type == "LONG" else entry - (atr * tp_mult)

        # Separate partial TP level (when configured). 0 = use tp_price (legacy).
        tp_partial_atr_mult_val = float(trade_cfg.get("tp_partial_atr_mult", 0))
        tp1_taken = int(pos.get("tp1_taken") or 0)
        if tp_partial_atr_mult_val > 0 and tp1_taken == 0:
            tp_check_price = (
                entry + (atr * tp_partial_atr_mult_val)
                if pos_type == "LONG"
                else entry - (atr * tp_partial_atr_mult_val)
            )
        else:
            tp_check_price = tp_price

        # 4. Smart Exits (v2.8 Refactor)
        smart_exit_reason = None
        if indicators is not None:
            ema_f = indicators.get("EMA_fast", 0)
            ema_s = indicators.get("EMA_slow", 0)
            ema_m = indicators.get("EMA_macro", 0)
            adx = indicators.get("ADX", 0)
            rsi = indicators.get("RSI", 50)

            # Trend Breakdown (v2.5) / v4.0: Trend Breakdown Buffer (TBB)
            # Relax the EMA cross exit if the cross is very shallow (< 0.1%) and ADX is still strong (> 25).
            ema_dev = abs(ema_f - ema_s) / ema_s if ema_s > 0 else 0
            is_weak_cross = (ema_dev < 0.001) and (adx > 25)

            exhausted = bool(adx_exhaustion_lt > 0 and adx < adx_exhaustion_lt)
            if pos_type == "LONG" and ((ema_f < ema_s and not is_weak_cross) or exhausted):
                if ema_f < ema_s and not is_weak_cross:
                    smart_exit_reason = "Trend Breakdown (EMA Cross)"
                else:
                    smart_exit_reason = f"Trend Exhaustion (ADX < {adx_exhaustion_lt:g})"
            elif pos_type == "SHORT" and ((ema_f > ema_s and not is_weak_cross) or exhausted):
                if ema_f > ema_s and not is_weak_cross:
                    smart_exit_reason = "Trend Breakdown (EMA Cross)"
                else:
                    smart_exit_reason = f"Trend Exhaustion (ADX < {adx_exhaustion_lt:g})"

            # EMA Macro Breakdown (v2.6)
            # Only enforce if macro alignment is required by config.
            # If counter-trend entries are allowed, we shouldn't exit just because it's counter-trend.
            if not smart_exit_reason and ema_m > 0 and bool(flt.get("require_macro_alignment", False)):
                if pos_type == "LONG" and current_price < ema_m:
                    smart_exit_reason = "EMA Macro Breakdown"
                elif pos_type == "SHORT" and current_price > ema_m:
                    smart_exit_reason = "EMA Macro Breakout"

            # v3.1: Low-Volatility Stagnation Exit
            if not smart_exit_reason:
                current_atr = indicators.get("ATR", atr)
                if current_atr < (atr * 0.70):  # Volatility dropped by 30%
                    is_underwater = (pos_type == "LONG" and current_price < entry) or (
                        pos_type == "SHORT" and current_price > entry
                    )
                    if is_underwater:
                        # v5.084: Exception for PaxG (Gold-pegged) to avoid volatility-drop exits in stable assets.
                        if str(symbol or "").upper() != "PAXG":
                            smart_exit_reason = f"Stagnation Exit (Low Vol: {current_atr:.2f} < {atr * 0.70:.2f})"

            # Funding Headwind Exit (v2.7/2.8/2.9/3.0)
            funding_rate = indicators.get("funding_rate", 0.0)
            if not smart_exit_reason and funding_rate != 0:
                is_headwind = (pos_type == "LONG" and funding_rate > 0) or (pos_type == "SHORT" and funding_rate < 0)
                if is_headwind:
                    price_diff_atr = abs(current_price - entry) / (atr or 1.0)

                    # v4.1: Adaptive Funding Ladder (AFL) - More granular sensitivity
                    if abs(funding_rate) > 0.0001:  # Extreme funding (> 0.01%/hr)
                        headwind_threshold = 0.15
                    elif abs(funding_rate) > 0.00006:
                        headwind_threshold = 0.25
                    elif abs(funding_rate) > 0.00004:
                        headwind_threshold = 0.40
                    elif abs(funding_rate) > 0.00002:
                        headwind_threshold = 0.60
                    elif abs(funding_rate) < 0.00001:
                        # v4.1: Near-Zero Funding Buffer (NZF)
                        headwind_threshold = 0.95
                    else:
                        headwind_threshold = 0.80

                    # v3.0: Volatility-Adjusted Sensitivity
                    # If current volatility (ATR) is higher than entry volatility, tighten leash
                    current_atr = indicators.get("ATR", atr)
                    if current_atr > (atr * 1.2):
                        headwind_threshold *= 0.6  # Reduce threshold by 40% if vol expands against us

                    # v3.2/v3.7: Time-Decay Headwind (TDH) with Floor
                    open_ts = pos.get("open_timestamp")
                    if open_ts:
                        try:
                            # Parse ISO 8601, handle possible Z or +00:00
                            ts_str = open_ts.replace("Z", "+00:00")
                            open_dt = datetime.datetime.fromisoformat(ts_str)
                            # Ensure open_dt is aware if current is aware (naive vs aware mismatch)
                            if open_dt.tzinfo is None:
                                open_dt = open_dt.replace(tzinfo=datetime.timezone.utc)

                            duration_hrs = (
                                datetime.datetime.now(datetime.timezone.utc) - open_dt
                            ).total_seconds() / 3600

                            if duration_hrs > 1.0:  # Start decay after 1 hour
                                # v3.7: Extend window to 12h and add 0.35 ATR floor
                                decay_factor = max(0.0, 1.0 - (duration_hrs - 1.0) / 11.0)
                                headwind_threshold = max(0.35, headwind_threshold * decay_factor)

                            # v5.003: Trend Loyalty Funding Buffer (TLFB)
                            # 如果趨勢排列 (EMA Fast/Slow) 仍然正確且 ADX > 25，
                            # 則將 Funding Headwind 門檻保底設為 0.75 ATR，無視時間衰減。
                            # 避免在趨勢未變的情況下因為「時間到」而被洗出局。
                            ema_f = indicators.get("EMA_fast", 0)
                            ema_s = indicators.get("EMA_slow", 0)
                            adx_val = indicators.get("ADX", 0)
                            is_trend_valid = (pos_type == "LONG" and ema_f > ema_s) or (
                                pos_type == "SHORT" and ema_f < ema_s
                            )
                            if is_trend_valid and adx_val > 25:
                                headwind_threshold = max(0.75, headwind_threshold)
                        except Exception as e:
                            logger.warning(f"⚠️ TDH Error: {e}")

                    # v3.4/v3.7: Momentum-Filtered Funding Exit (MFE)
                    # If momentum is still improving in our direction, increase threshold by 50%
                    macd_h = indicators.get("MACD_hist", 0)
                    prev_macd_h = indicators.get("prev_MACD_hist", 0)
                    is_momentum_improving = (pos_type == "LONG" and macd_h > prev_macd_h) or (
                        pos_type == "SHORT" and macd_h < prev_macd_h
                    )
                    if is_momentum_improving:
                        headwind_threshold *= 1.5
                        # v3.7: MFE Floor - 只要動量仲改善緊，起碼留 0.5 ATR 空間
                        headwind_threshold = max(0.50, headwind_threshold)

                    # v3.7: ADX-Boosted Funding Threshold (ABF)
                    # 如果趨勢極強 (ADX > 35)，放寬 Funding 離場閾值 40%
                    adx = indicators.get("ADX", 0)
                    if adx > 35:
                        headwind_threshold *= 1.4

                    # v3.8: High-Confidence Funding Buffer (HCFB)
                    # 如果係高信心信號，額外放寬 25% 空間
                    if pos.get("confidence") == "high":
                        headwind_threshold *= 1.25

                    # v3.6: Macro-Trend Filtered Funding Exit (MTF)
                    # 如果大趨勢 (EMA 200) 仍然支持持倉方向，放寬 Funding 離場閾值 30%
                    is_macro_aligned = False
                    ema_m = indicators.get("EMA_macro", 0)
                    if ema_m > 0:
                        is_macro_aligned = (pos_type == "LONG" and current_price > ema_m) or (
                            pos_type == "SHORT" and current_price < ema_m
                        )
                        if is_macro_aligned:
                            headwind_threshold *= 1.3

                    # v4.2: Triple Confirmation Funding Buffer (TCFB)
                    # 如果同時具備 MACD 改良 (MFE)、強勢大趨勢 (MTF) 及 高信心 (HCFB)，額外增加 50% 緩衝空間
                    # 避免在最強勢的趨勢中因為微小的資金費率波動被洗出局
                    is_triple_confirmed = (
                        is_momentum_improving and is_macro_aligned and (pos.get("confidence") == "high")
                    )
                    if is_triple_confirmed:
                        headwind_threshold *= 1.5

                    # v4.3: Volatility-Scaled Funding Tolerance (VSFT)
                    # 如果波動率極低 (ATR/Price < 0.2%)，顯示市場處於極度壓縮狀態，放寬 25% 空間以等待突破
                    current_atr = indicators.get("ATR", atr)
                    if (current_atr / current_price) < 0.002:
                        headwind_threshold *= 1.25

                    # v4.4: Counter-Trend Exhaustion Buffer (CTEB)
                    # 如果 RSI 顯示反向運動可能接近枯竭（例如做空時 RSI > 65），額外放寬 30% 空間，等待均值回歸
                    rsi = indicators.get("RSI", 50)
                    if (pos_type == "SHORT" and rsi > 65) or (pos_type == "LONG" and rsi < 35):
                        headwind_threshold *= 1.3

                    # v4.5: 極端趨勢資金費率屏蔽 (Extreme Trend Funding Shield - ETFS)
                    # 如果 ADX > 45 (極強趨勢)，額外放寬 60% 空間。
                    # 確保在最強勁的行情中唔會因為雞毛蒜皮嘅利息支出而錯失大行情。
                    if adx > 45:
                        headwind_threshold *= 1.6

                    # v4.8: 趨勢加速離場屏蔽 (Trend Acceleration Exit Shield - TAES)
                    # 如果 ADX 斜率 > 1.0 (代表趨勢正在強勁加速)，額外放寬 40% 空間。
                    # 確保在行情進入加速段時，系統不會因為資金費率的小額成本而過早離場。
                    adx_slope = indicators.get("ADX_slope", 0)
                    if adx_slope > 1.0:
                        headwind_threshold *= 1.4

                    # v5.019: 動態資金費率守護 (Dynamic Funding Guard - DFG)
                    # 如果 ADX > 40 (極強趨勢)，再額外放寬 25% 空間。
                    # 配合 ETFS (ADX>45)，確保最強趨勢中嘅 Funding Headwind 門檻有足夠韌性。
                    if adx > 40:
                        headwind_threshold *= 1.25

                    # v5.002: 收益波動屏蔽 (Profit-Vol Shield - PVS)
                    # 如果持倉已有超過 +1.5 ATR 的利潤，且當前 ATR 正在上升 (ATR_slope > 0)，
                    # 代表行情進入加速期且對我有利。在這種情況下，將 Funding Headwind 離場閾值額外放寬 50%。
                    atr_slope = indicators.get("ATR_slope", 0)
                    if profit_atr > 1.5 and atr_slope > 0:
                        headwind_threshold *= 1.5

                    # v5.010: 獲利保底資金費緩衝 (Profit-Based Funding Buffer - PBFB)
                    # 無視 ATR 斜率，只要浮盈超過 +2.0 ATR，將 Funding Headwind 離場閾值放寬 50%。
                    # 如果浮盈超過 +3.0 ATR，則放寬 100% (即 2.0x 門檻)。
                    # 確保大賺單唔會喺盤整期因為利息成本被掃出局。
                    if profit_atr > 3.0:
                        headwind_threshold *= 2.0
                    elif profit_atr > 2.0:
                        headwind_threshold *= 1.5

                    # v5.004: 趨勢轉弱資金費率增敏 (Trend Weakening Funding Sensitivity - TWFS)
                    # 當 ADX 斜率為負 (ADX_slope < 0，代表趨勢強度正在減弱) 且持倉面臨資金費率逆風時，
                    # 將 Funding Headwind 離場閾值縮減 25%。這能確保在趨勢動能消退時，系統對資金費率成本更敏感，及早離場。
                    if adx_slope < 0:
                        headwind_threshold *= 0.75

                    # If underwater with headwind
                    if (pos_type == "LONG" and current_price < entry) or (
                        pos_type == "SHORT" and current_price > entry
                    ):
                        if price_diff_atr > headwind_threshold:
                            smart_exit_reason = f"Funding Headwind Exit (FR: {funding_rate:.6f}, Thr: {headwind_threshold:.2f}, Dur: {duration_hrs:.1f}h)"

            # v5.001: 趨勢飽和動量離場 (Trend Saturation Momentum Exit - TSME)
            # Extra gate (reduce premature exits on normal pullbacks):
            # - only fire if profit >= N ATR, AND
            # - ADX slope is negative (trend strength no longer accelerating).
            if not smart_exit_reason and adx > 50:
                try:
                    tsme_min_profit_atr = float(trade_cfg.get("tsme_min_profit_atr", 1.0))
                except Exception:
                    tsme_min_profit_atr = 1.0
                tsme_req_adx_slope_neg = bool(trade_cfg.get("tsme_require_adx_slope_negative", True))

                profit_atr_now = (current_price - entry) / atr if pos_type == "LONG" else (entry - current_price) / atr
                adx_slope_now = indicators.get("ADX_slope", 0)

                gate_profit_ok = profit_atr_now >= tsme_min_profit_atr
                gate_slope_ok = (adx_slope_now < 0) if tsme_req_adx_slope_neg else True

                if gate_profit_ok and gate_slope_ok:
                    macd_h = indicators.get("MACD_hist", 0)
                    p_macd_h = indicators.get("prev_MACD_hist", 0)
                    pp_macd_h = indicators.get("prev2_MACD_hist", 0)

                    # Check for two consecutive periods of momentum contraction in the saturated zone
                    is_exhausted = False
                    if pos_type == "LONG":
                        if macd_h < p_macd_h < pp_macd_h:
                            is_exhausted = True
                    else:
                        if macd_h > p_macd_h > pp_macd_h:
                            is_exhausted = True

                    if is_exhausted:
                        smart_exit_reason = (
                            f"Trend Saturation Momentum Exhaustion (ADX: {adx:.1f}, ADX_slope: {adx_slope_now:.2f})"
                        )

            # v5.012: MACD 動量背離止盈 (MACD Momentum Divergence Exit - MMDE)
            # v5.013: 增加背離深度確認 (Persistent Divergence)
            # 如果已經有 +1.5 ATR 浮盈，且 ADX > 35 (強趨勢)，
            # 若 MACD Histogram 連續 3 次向反方向運動，視為頂部/底部背離。
            if not smart_exit_reason and profit_atr > 1.5 and adx > 35:
                macd_h = indicators.get("MACD_hist", 0)
                p_macd_h = indicators.get("prev_MACD_hist", 0)
                pp_macd_h = indicators.get("prev2_MACD_hist", 0)
                ppp_macd_h = indicators.get("prev3_MACD_hist", 0)

                is_diverging = False
                if pos_type == "LONG":
                    if macd_h < p_macd_h < pp_macd_h < ppp_macd_h:
                        is_diverging = True
                else:
                    if macd_h > p_macd_h > pp_macd_h > ppp_macd_h:
                        is_diverging = True

                if is_diverging:
                    smart_exit_reason = f"MACD Persistent Divergence (Profit: {profit_atr:.2f} ATR)"

            # RSI Overextension Exit (v2.7/2.8/2.9/3.0) — now configurable.
            if not smart_exit_reason and bool(trade_cfg.get("enable_rsi_overextension_exit", True)):
                profit_atr = (current_price - entry) / atr if pos_type == "LONG" else (entry - current_price) / atr
                try:
                    sw = float(trade_cfg.get("rsi_exit_profit_atr_switch", 1.5))
                except Exception:
                    sw = 1.5
                sw = float(max(0.0, sw))

                def _cfg_float(name: str, default: float) -> float:
                    try:
                        return float(trade_cfg.get(name, default))
                    except Exception:
                        return float(default)

                if profit_atr < sw:
                    rsi_ub = _cfg_float("rsi_exit_ub_lo_profit", 80.0)
                    rsi_lb = _cfg_float("rsi_exit_lb_lo_profit", 20.0)
                    # Optional per-confidence overrides.
                    if pos_conf.startswith("l"):
                        v = _cfg_float("rsi_exit_ub_lo_profit_low_conf", 0.0)
                        if v > 0:
                            rsi_ub = v
                        v = _cfg_float("rsi_exit_lb_lo_profit_low_conf", 0.0)
                        if v > 0:
                            rsi_lb = v
                else:
                    rsi_ub = _cfg_float("rsi_exit_ub_hi_profit", 70.0)
                    rsi_lb = _cfg_float("rsi_exit_lb_hi_profit", 30.0)
                    if pos_conf.startswith("l"):
                        v = _cfg_float("rsi_exit_ub_hi_profit_low_conf", 0.0)
                        if v > 0:
                            rsi_ub = v
                        v = _cfg_float("rsi_exit_lb_hi_profit_low_conf", 0.0)
                        if v > 0:
                            rsi_lb = v

                if pos_type == "LONG" and rsi > rsi_ub:
                    smart_exit_reason = f"RSI Overbought ({rsi:.1f}, Thr: {rsi_ub:g})"
                elif pos_type == "SHORT" and rsi < rsi_lb:
                    smart_exit_reason = f"RSI Oversold ({rsi:.1f}, Thr: {rsi_lb:g})"

        # ── AQC-803: Log exit gate evaluations when an exit fires ──────────
        _exit_fires = False
        _exit_kind = None
        if smart_exit_reason:
            _exit_fires = True
            _exit_kind = "smart_exit"
        elif pos_type == "LONG" and current_price <= sl_price:
            _exit_fires = True
            _exit_kind = "trailing_stop" if pos.get("trailing_sl") else "stop_loss"
        elif pos_type == "LONG" and current_price >= (tp_check_price):
            _exit_fires = True
            _exit_kind = "take_profit"
        elif pos_type == "SHORT" and current_price >= sl_price:
            _exit_fires = True
            _exit_kind = "trailing_stop" if pos.get("trailing_sl") else "stop_loss"
        elif pos_type == "SHORT" and current_price <= (tp_check_price):
            _exit_fires = True
            _exit_kind = "take_profit"

        if _exit_fires:
            try:
                _exit_did = create_decision_event(
                    symbol=symbol,
                    event_type="exit_check",
                    status="executed",
                    phase="gate_evaluation",
                    triggered_by=_exit_kind or "price_update",
                    action_taken="close_long" if pos_type == "LONG" else "close_short",
                    context={
                        "exit_kind": _exit_kind,
                        "smart_exit_reason": smart_exit_reason,
                        "entry_price": float(entry),
                        "current_price": float(current_price),
                        "sl_price": float(sl_price),
                        "tp_price": float(tp_price),
                        "trailing_sl": None if pos.get("trailing_sl") is None else float(pos["trailing_sl"]),
                    },
                )
                _exit_rows: list[dict] = []
                # Stop loss gate
                _sl_hit = (pos_type == "LONG" and current_price <= sl_price) or (
                    pos_type == "SHORT" and current_price >= sl_price
                )
                _exit_rows.append(
                    {
                        "gate_name": "stop_loss",
                        "gate_passed": _sl_hit,
                        "metric_value": float(current_price),
                        "threshold_value": float(sl_price),
                        "operator": "<=" if pos_type == "LONG" else ">=",
                        "explanation": f"price {current_price:.4f} vs SL {sl_price:.4f}",
                    }
                )
                # Take profit gate
                _tp_hit = (pos_type == "LONG" and current_price >= tp_price) or (
                    pos_type == "SHORT" and current_price <= tp_price
                )
                _exit_rows.append(
                    {
                        "gate_name": "take_profit",
                        "gate_passed": _tp_hit,
                        "metric_value": float(current_price),
                        "threshold_value": float(tp_price),
                        "operator": ">=" if pos_type == "LONG" else "<=",
                        "explanation": f"price {current_price:.4f} vs TP {tp_price:.4f}",
                    }
                )
                # Trailing stop gate
                _ts_val = pos.get("trailing_sl")
                _ts_hit = False
                if _ts_val is not None:
                    _ts_hit = (pos_type == "LONG" and current_price <= _ts_val) or (
                        pos_type == "SHORT" and current_price >= _ts_val
                    )
                _exit_rows.append(
                    {
                        "gate_name": "trailing_stop",
                        "gate_passed": _ts_hit,
                        "metric_value": float(current_price),
                        "threshold_value": None if _ts_val is None else float(_ts_val),
                        "operator": "<=" if pos_type == "LONG" else ">=",
                        "explanation": f"trailing_sl={'N/A' if _ts_val is None else f'{_ts_val:.4f}'}",
                    }
                )
                # Breakeven stop gate
                _be_active = be_enabled and be_start_atr > 0
                _be_engaged = False
                if _be_active:
                    if pos_type == "LONG":
                        _be_engaged = (current_price - entry) >= (atr * be_start_atr)
                    else:
                        _be_engaged = (entry - current_price) >= (atr * be_start_atr)
                _exit_rows.append(
                    {
                        "gate_name": "breakeven_stop",
                        "gate_passed": _be_engaged,
                        "metric_value": float(profit_atr),
                        "threshold_value": float(be_start_atr),
                        "operator": ">=",
                        "explanation": f"breakeven {'engaged' if _be_engaged else 'not engaged'} (start={be_start_atr:.2f} ATR)",
                    }
                )
                # Smart exit gate
                _exit_rows.append(
                    {
                        "gate_name": "smart_exit",
                        "gate_passed": smart_exit_reason is not None,
                        "explanation": str(smart_exit_reason) if smart_exit_reason else "no smart exit triggered",
                    }
                )
                _log_gates_batch(_exit_did, _exit_rows)
            except Exception as _ex_exc:
                logger.debug("check_exit_conditions: exit gate logging failed: %s", _ex_exc)

        # Check Hits
        if smart_exit_reason:
            audit = None
            if indicators is not None:
                try:
                    audit = indicators.get("audit")
                except Exception:
                    audit = None
            self.close_position(
                symbol,
                current_price,
                timestamp,
                reason=smart_exit_reason,
                meta={
                    "audit": audit if isinstance(audit, dict) else None,
                    "exit": {
                        "kind": "SMART_EXIT",
                        "reason": str(smart_exit_reason),
                        "pos_type": str(pos_type),
                        "entry_price": float(entry),
                        "current_price": float(current_price),
                        "entry_atr": float(atr),
                        "sl_price": float(sl_price),
                        "tp_price": float(tp_price),
                        "trailing_sl": None if pos.get("trailing_sl") is None else float(pos.get("trailing_sl")),
                    },
                },
            )
            _log_exit_lineage(smart_exit_reason)
        elif pos_type == "LONG":
            if current_price <= sl_price:
                reason = "Trailing Stop" if pos["trailing_sl"] else "Stop Loss"
                audit = None
                if indicators is not None:
                    try:
                        audit = indicators.get("audit")
                    except Exception:
                        audit = None
                self.close_position(
                    symbol,
                    current_price,
                    timestamp,
                    reason=reason,
                    meta={
                        "audit": audit if isinstance(audit, dict) else None,
                        "exit": {
                            "kind": "TRAILING_STOP" if pos.get("trailing_sl") else "STOP_LOSS",
                            "reason": str(reason),
                            "pos_type": str(pos_type),
                            "entry_price": float(entry),
                            "current_price": float(current_price),
                            "entry_atr": float(atr),
                            "sl_price": float(sl_price),
                            "tp_price": float(tp_price),
                            "trailing_sl": None if pos.get("trailing_sl") is None else float(pos.get("trailing_sl")),
                        },
                    },
                )
                _log_exit_lineage(reason)
            elif current_price >= tp_check_price:
                # Take-profit ladder (partial TP once, then trail the remainder).
                if bool(trade_cfg.get("enable_partial_tp", True)) and tp1_taken == 0:
                    try:
                        pct = float(trade_cfg.get("tp_partial_pct", 0.5))
                    except Exception:
                        pct = 0.5
                    pct = max(0.0, min(1.0, pct))

                    if 0.0 < pct < 1.0:
                        try:
                            total_sz = float(pos.get("size") or 0.0)
                        except Exception:
                            total_sz = 0.0
                        partial_sz = hyperliquid_meta.round_size(symbol, total_sz * pct)
                        partial_min_ntl = float(trade_cfg.get("tp_partial_min_notional_usd", 10.0))

                        # WARN-X4: If remaining notional after partial TP < min_notional,
                        # convert to full close to prevent zombie positions.
                        _remaining_after = total_sz - partial_sz
                        _min_ntl_usd = float(trade_cfg.get("min_notional_usd", 10.0))
                        if partial_sz > 0 and partial_sz < total_sz and _remaining_after > 0:
                            if (_remaining_after * current_price) < _min_ntl_usd:
                                partial_sz = total_sz  # promote to full close

                        if partial_sz > 0 and (partial_sz * current_price) >= partial_min_ntl and partial_sz < total_sz:
                            audit = None
                            if indicators is not None:
                                try:
                                    audit = indicators.get("audit")
                                except Exception:
                                    audit = None
                            ok = self.reduce_position(
                                symbol,
                                partial_sz,
                                current_price,
                                timestamp,
                                reason="Take Profit (Partial)",
                                confidence="N/A",
                                meta={
                                    "audit": audit if isinstance(audit, dict) else None,
                                    "exit": {
                                        "kind": "TAKE_PROFIT_PARTIAL",
                                        "reason": "Take Profit (Partial)",
                                        "pos_type": str(pos_type),
                                        "entry_price": float(entry),
                                        "current_price": float(current_price),
                                        "entry_atr": float(atr),
                                        "sl_price": float(sl_price),
                                        "tp_price": float(tp_price),
                                        "partial_pct": float(pct),
                                        "partial_size": float(partial_sz),
                                        "tp_partial_min_notional_usd": float(partial_min_ntl),
                                    },
                                },
                            )
                            if ok and symbol in self.positions:
                                pos2 = self.positions.get(symbol) or {}
                                pos2["tp1_taken"] = 1
                                # Lock breakeven (or better) on remaining size.
                                if pos2.get("trailing_sl") is None:
                                    pos2["trailing_sl"] = entry
                                else:
                                    pos2["trailing_sl"] = max(float(pos2["trailing_sl"]), entry)
                                self.upsert_position_state(symbol)
                                _log_exit_lineage("Take Profit (Partial)", is_partial=True)
                            return

                # If partial TP was already taken:
                # - tp_partial_atr_mult > 0: fall through to full TP close.
                # - tp_partial_atr_mult == 0: hold (trailing manages remainder). Legacy behavior.
                if bool(trade_cfg.get("enable_partial_tp", True)) and tp1_taken == 1:
                    if tp_partial_atr_mult_val <= 0:
                        return

                audit = None
                if indicators is not None:
                    try:
                        audit = indicators.get("audit")
                    except Exception:
                        audit = None
                self.close_position(
                    symbol,
                    current_price,
                    timestamp,
                    reason="Take Profit",
                    meta={
                        "audit": audit if isinstance(audit, dict) else None,
                        "exit": {
                            "kind": "TAKE_PROFIT",
                            "reason": "Take Profit",
                            "pos_type": str(pos_type),
                            "entry_price": float(entry),
                            "current_price": float(current_price),
                            "entry_atr": float(atr),
                            "sl_price": float(sl_price),
                            "tp_price": float(tp_price),
                            "trailing_sl": None if pos.get("trailing_sl") is None else float(pos.get("trailing_sl")),
                        },
                    },
                )
                _log_exit_lineage("Take Profit")
        else:
            if current_price >= sl_price:
                reason = "Trailing Stop" if pos["trailing_sl"] else "Stop Loss"
                audit = None
                if indicators is not None:
                    try:
                        audit = indicators.get("audit")
                    except Exception:
                        audit = None
                self.close_position(
                    symbol,
                    current_price,
                    timestamp,
                    reason=reason,
                    meta={
                        "audit": audit if isinstance(audit, dict) else None,
                        "exit": {
                            "kind": "TRAILING_STOP" if pos.get("trailing_sl") else "STOP_LOSS",
                            "reason": str(reason),
                            "pos_type": str(pos_type),
                            "entry_price": float(entry),
                            "current_price": float(current_price),
                            "entry_atr": float(atr),
                            "sl_price": float(sl_price),
                            "tp_price": float(tp_price),
                            "trailing_sl": None if pos.get("trailing_sl") is None else float(pos.get("trailing_sl")),
                        },
                    },
                )
                _log_exit_lineage(reason)
            elif current_price <= tp_check_price:
                if bool(trade_cfg.get("enable_partial_tp", True)) and tp1_taken == 0:
                    try:
                        pct = float(trade_cfg.get("tp_partial_pct", 0.5))
                    except Exception:
                        pct = 0.5
                    pct = max(0.0, min(1.0, pct))

                    if 0.0 < pct < 1.0:
                        try:
                            total_sz = float(pos.get("size") or 0.0)
                        except Exception:
                            total_sz = 0.0
                        partial_sz = hyperliquid_meta.round_size(symbol, total_sz * pct)
                        partial_min_ntl = float(trade_cfg.get("tp_partial_min_notional_usd", 10.0))

                        # WARN-X4: If remaining notional after partial TP < min_notional,
                        # convert to full close to prevent zombie positions.
                        _remaining_after = total_sz - partial_sz
                        _min_ntl_usd = float(trade_cfg.get("min_notional_usd", 10.0))
                        if partial_sz > 0 and partial_sz < total_sz and _remaining_after > 0:
                            if (_remaining_after * current_price) < _min_ntl_usd:
                                partial_sz = total_sz  # promote to full close

                        if partial_sz > 0 and (partial_sz * current_price) >= partial_min_ntl and partial_sz < total_sz:
                            audit = None
                            if indicators is not None:
                                try:
                                    audit = indicators.get("audit")
                                except Exception:
                                    audit = None
                            ok = self.reduce_position(
                                symbol,
                                partial_sz,
                                current_price,
                                timestamp,
                                reason="Take Profit (Partial)",
                                confidence="N/A",
                                meta={
                                    "audit": audit if isinstance(audit, dict) else None,
                                    "exit": {
                                        "kind": "TAKE_PROFIT_PARTIAL",
                                        "reason": "Take Profit (Partial)",
                                        "pos_type": str(pos_type),
                                        "entry_price": float(entry),
                                        "current_price": float(current_price),
                                        "entry_atr": float(atr),
                                        "sl_price": float(sl_price),
                                        "tp_price": float(tp_price),
                                        "partial_pct": float(pct),
                                        "partial_size": float(partial_sz),
                                        "tp_partial_min_notional_usd": float(partial_min_ntl),
                                    },
                                },
                            )
                            if ok and symbol in self.positions:
                                pos2 = self.positions.get(symbol) or {}
                                pos2["tp1_taken"] = 1
                                if pos2.get("trailing_sl") is None:
                                    pos2["trailing_sl"] = entry
                                else:
                                    pos2["trailing_sl"] = min(float(pos2["trailing_sl"]), entry)
                                self.upsert_position_state(symbol)
                                _log_exit_lineage("Take Profit (Partial)", is_partial=True)
                            return

                if bool(trade_cfg.get("enable_partial_tp", True)) and tp1_taken == 1:
                    if tp_partial_atr_mult_val <= 0:
                        return

                audit = None
                if indicators is not None:
                    try:
                        audit = indicators.get("audit")
                    except Exception:
                        audit = None
                self.close_position(
                    symbol,
                    current_price,
                    timestamp,
                    reason="Take Profit",
                    meta={
                        "audit": audit if isinstance(audit, dict) else None,
                        "exit": {
                            "kind": "TAKE_PROFIT",
                            "reason": "Take Profit",
                            "pos_type": str(pos_type),
                            "entry_price": float(entry),
                            "current_price": float(current_price),
                            "entry_atr": float(atr),
                            "sl_price": float(sl_price),
                            "tp_price": float(tp_price),
                            "trailing_sl": None if pos.get("trailing_sl") is None else float(pos.get("trailing_sl")),
                        },
                    },
                )
                _log_exit_lineage("Take Profit")

        # AQC-804: Hold decision (throttled — every 10th check to reduce noise).
        if symbol in self.positions:
            _check_count = getattr(self, _exit_check_key, 0)
            if _check_count % 10 == 0:
                try:
                    create_decision_event(
                        symbol=symbol,
                        event_type="exit_check",
                        status="hold",
                        phase="evaluation",
                        triggered_by="price_update",
                        action_taken="hold",
                        context={
                            "price": float(current_price),
                            "sl_price": float(sl_price),
                            "tp_price": float(tp_price),
                            "trailing_sl": None if pos.get("trailing_sl") is None else float(pos.get("trailing_sl")),
                            "check_count": int(_check_count),
                        },
                    )
                except Exception:
                    pass

    def close_position(self, symbol, price, timestamp, reason, *, meta: dict | None = None):
        if symbol not in self.positions:
            return
        try:
            sz = float(self.positions[symbol].get("size") or 0.0)
        except Exception:
            return
        if sz <= 0:
            return
        self.reduce_position(symbol, sz, price, timestamp, reason, confidence="N/A", meta=meta)
        self._note_exit_attempt(symbol)


def analyze(df, symbol, btc_bullish=None):
    cfg = get_strategy_config(symbol)
    trade_cfg = cfg["trade"]
    ind = cfg["indicators"]
    flt = cfg["filters"]
    thr = cfg["thresholds"]

    # Trend
    df["EMA_slow"] = ta.trend.ema_indicator(df["Close"], window=int(ind["ema_slow_window"]))
    df["EMA_fast"] = ta.trend.ema_indicator(df["Close"], window=int(ind["ema_fast_window"]))
    df["EMA_macro"] = ta.trend.ema_indicator(df["Close"], window=int(ind["ema_macro_window"]))

    # ADX for trend strength
    adx_obj = ta.trend.ADXIndicator(df["High"], df["Low"], df["Close"], window=int(ind["adx_window"]))
    df["ADX"] = adx_obj.adx()
    df["ADX_pos"] = adx_obj.adx_pos()
    df["ADX_neg"] = adx_obj.adx_neg()

    # Volatility - Bollinger Band width
    bb = ta.volatility.BollingerBands(df["Close"], window=int(ind["bb_window"]))
    df["bb_high"] = bb.bollinger_hband()
    df["bb_low"] = bb.bollinger_lband()
    df["bb_width"] = (df["bb_high"] - df["bb_low"]) / df["Close"]
    df["avg_bb_width"] = df["bb_width"].rolling(window=int(ind["bb_width_avg_window"])).mean()

    # ATR for dynamic stop losses
    df["ATR"] = ta.volatility.average_true_range(df["High"], df["Low"], df["Close"], window=int(ind["atr_window"]))

    # Momentum
    df["RSI"] = ta.momentum.rsi(df["Close"], window=int(ind["rsi_window"]))
    macd = ta.trend.MACD(df["Close"])
    df["MACD_hist"] = macd.macd_diff()

    # Volume trend
    df["vol_sma"] = df["Volume"].rolling(window=int(ind["vol_sma_window"])).mean()
    df["vol_trend"] = df["Volume"].rolling(window=int(ind["vol_trend_window"])).mean() > df["vol_sma"]

    if len(df) < 5:
        return "NEUTRAL", "low"

    latest = df.iloc[-1].copy()
    prev = df.iloc[-2]

    # ADX Slope for trend strength trend (v3.3)
    latest["ADX_slope"] = latest["ADX"] - prev["ADX"]
    # ATR Slope for volatility trend (v5.002)
    latest["ATR_slope"] = latest["ATR"] - prev["ATR"]
    # Prev MACD Hist for momentum filtering (v3.4)
    latest["prev_MACD_hist"] = prev["MACD_hist"]
    # v5.001: Prev2 MACD Hist for momentum exhaustion check
    latest["prev2_MACD_hist"] = df["MACD_hist"].iloc[-3] if len(df) >= 3 else 0.0
    # v5.013: Prev3 MACD Hist for persistent divergence check
    latest["prev3_MACD_hist"] = df["MACD_hist"].iloc[-4] if len(df) >= 4 else 0.0

    signal, conf = "NEUTRAL", "low"

    # 1) Ranging filter
    bb_width_ratio = latest["bb_width"] / latest["avg_bb_width"] if latest["avg_bb_width"] > 0 else 1.0
    is_ranging = False
    if latest["avg_bb_width"] == 0:
        is_ranging = True
    elif bool(flt.get("enable_ranging_filter", True)):
        r = thr["ranging"]
        # Less strict: require N "ranging signals" instead of any single one.
        # (Old behavior was effectively min_signals=1.)
        try:
            min_signals = int(r.get("min_signals", 2))
        except Exception:
            min_signals = 2

        signals = 0
        if latest["ADX"] < float(r["adx_below"]):
            signals += 1
        if bb_width_ratio < float(r["bb_width_ratio_below"]):
            signals += 1
        if float(r["rsi_low"]) < latest["RSI"] < float(r["rsi_high"]):
            signals += 1
        is_ranging = signals >= max(1, min_signals)

    # 2) Anomaly filter
    is_anomaly = False
    if bool(flt.get("enable_anomaly_filter", True)):
        a = thr["anomaly"]
        price_change_pct = abs(latest["Close"] - prev["Close"]) / prev["Close"]
        ema_dev_pct = abs(latest["Close"] - latest["EMA_fast"]) / latest["EMA_fast"] if latest["EMA_fast"] > 0 else 0
        is_anomaly = (price_change_pct > float(a["price_change_pct_gt"])) or (
            ema_dev_pct > float(a["ema_fast_dev_pct_gt"])
        )

    # 3) Dynamic TP multipliers (returned to the trader)
    tp = thr["tp_and_momentum"]
    dynamic_tp_mult = float(trade_cfg.get("tp_atr_mult", TP_ATR_MULT))
    if latest["ADX"] > float(tp["adx_strong_gt"]):
        dynamic_tp_mult = float(tp["tp_mult_strong"])
    elif latest["ADX"] < float(tp["adx_weak_lt"]):
        dynamic_tp_mult = float(tp["tp_mult_weak"])

    # 4) Entry gating (trend strength + confirmation)
    thr_entry = thr.get("entry") or {}
    try:
        min_adx = float(thr_entry.get("min_adx", 22.0))
    except Exception:
        min_adx = 22.0

    # v4.7: Adaptive Volatility Entry (AVE)
    # 如果當前 ATR 比平均 ATR 高出 50%，代表波動率異常爆發，將進場門檻提高以防止追逐極端行情。
    ave_enabled = bool(thr_entry.get("ave_enabled", True))
    try:
        ave_atr_ratio_gt = float(thr_entry.get("ave_atr_ratio_gt", 1.5) or 1.5)
    except Exception:
        ave_atr_ratio_gt = 1.5
    try:
        ave_adx_mult = float(thr_entry.get("ave_adx_mult", 1.25) or 1.25)
    except Exception:
        ave_adx_mult = 1.25
    try:
        ave_window = int(thr_entry.get("ave_avg_atr_window", 50) or 50)
    except Exception:
        ave_window = 50
    ave_window = max(5, min(500, ave_window))

    df["avg_atr"] = df["ATR"].rolling(window=ave_window).mean()
    _raw_avg_atr = df["avg_atr"].iloc[-1]
    latest_avg_atr = 0.0 if (_raw_avg_atr != _raw_avg_atr) else float(_raw_avg_atr)
    atr_ratio = None
    vol_spike_mult = 1.0
    if ave_enabled and latest_avg_atr > 0:
        try:
            atr_ratio = float(latest["ATR"]) / float(latest_avg_atr)
        except Exception:
            atr_ratio = None
        if atr_ratio is not None and float(atr_ratio) > float(ave_atr_ratio_gt):
            vol_spike_mult = float(ave_adx_mult) if float(ave_adx_mult) > 0 else 1.0

    # v4.6: Trend Momentum Confirmation (TMC)
    # 如果 ADX 正在快速上升 (Slope > 0.5)，將 min_adx 閾值從 28.0 放寬至 25.0。
    # 這能讓系統在強勢趨勢剛剛露頭時及早進場。
    effective_min_adx = min_adx
    if latest.get("ADX_slope", 0) > 0.5:
        effective_min_adx = min(effective_min_adx, 25.0)

    effective_min_adx *= vol_spike_mult

    is_trending_up = True
    if bool(flt.get("require_adx_rising", True)):
        # Allow entry if ADX is rising OR if trend is already strong (even if flattening).
        saturation = float(flt.get("adx_rising_saturation", 40.0))
        is_trending_up = (latest["ADX"] > prev["ADX"]) or (latest["ADX"] > saturation)

    vol_confirm = True
    if bool(flt.get("require_volume_confirmation", True)):
        include_prev = bool(flt.get("vol_confirm_include_prev", True))
        if include_prev:
            vol_confirm = ((latest["Volume"] > latest["vol_sma"]) or (prev["Volume"] > prev["vol_sma"])) and (
                bool(latest["vol_trend"]) or bool(prev["vol_trend"])
            )
        else:
            vol_confirm = (latest["Volume"] > latest["vol_sma"]) and bool(latest["vol_trend"])

    sym_u = str(symbol or "").upper()
    macd_mode = str(thr_entry.get("macd_hist_entry_mode", "accel") or "accel").strip().lower()
    if macd_mode not in {"accel", "sign", "none"}:
        macd_mode = "accel"

    # Alignment gates (used by both trend entries and slow-drift fallback).
    bullish_alignment = latest["EMA_fast"] > latest["EMA_slow"]
    bearish_alignment = latest["EMA_fast"] < latest["EMA_slow"]
    if bool(flt.get("require_macro_alignment", False)):
        bullish_alignment = bullish_alignment and (latest["EMA_slow"] > latest["EMA_macro"])
        bearish_alignment = bearish_alignment and (latest["EMA_slow"] < latest["EMA_macro"])

    # BTC alignment check (optional). Compute it even when trend-gate fails so audits reflect reality.
    require_btc = bool(flt.get("require_btc_alignment", True))
    try:
        btc_adx_override = float(thr_entry.get("btc_adx_override", 40.0))
    except Exception:
        btc_adx_override = 40.0
    btc_ok_long = (
        (not require_btc)
        or (sym_u == "BTC")
        or (btc_bullish is None)
        or bool(btc_bullish)
        or (latest["ADX"] > btc_adx_override)
    )
    btc_ok_short = (
        (not require_btc)
        or (sym_u == "BTC")
        or (btc_bullish is None)
        or (not bool(btc_bullish))
        or (latest["ADX"] > btc_adx_override)
    )

    # v5.042: Pullback continuation entry config (optional).
    pullback_enabled = bool(thr_entry.get("enable_pullback_entries", False))
    pullback_used = False
    pullback_conf = str(thr_entry.get("pullback_confidence", "low") or "low").strip().lower()
    if pullback_conf not in {"low", "medium", "high"}:
        pullback_conf = "low"
    try:
        pullback_min_adx = float(thr_entry.get("pullback_min_adx", min_adx) or min_adx)
    except Exception:
        pullback_min_adx = float(min_adx)
    try:
        pullback_rsi_long_min = float(thr_entry.get("pullback_rsi_long_min", 50.0) or 50.0)
    except Exception:
        pullback_rsi_long_min = 50.0
    try:
        pullback_rsi_short_max = float(thr_entry.get("pullback_rsi_short_max", 50.0) or 50.0)
    except Exception:
        pullback_rsi_short_max = 50.0
    pullback_require_macd_sign = bool(thr_entry.get("pullback_require_macd_sign", True))

    # v5.040: Slow drift entry config (optional).
    slow_enabled = bool(thr_entry.get("enable_slow_drift_entries", False))
    slow_used = False

    try:
        slow_slope_window = int(thr_entry.get("slow_drift_slope_window", 20) or 20)
    except Exception:
        slow_slope_window = 20
    slow_slope_window = max(3, min(slow_slope_window, len(df) - 1))

    try:
        slow_min_slope_pct = float(thr_entry.get("slow_drift_min_slope_pct", 0.0006) or 0.0006)
    except Exception:
        slow_min_slope_pct = 0.0006

    try:
        slow_min_adx = float(thr_entry.get("slow_drift_min_adx", 10.0) or 10.0)
    except Exception:
        slow_min_adx = 10.0

    try:
        slow_rsi_long_min = float(thr_entry.get("slow_drift_rsi_long_min", 50.0) or 50.0)
    except Exception:
        slow_rsi_long_min = 50.0

    try:
        slow_rsi_short_max = float(thr_entry.get("slow_drift_rsi_short_max", 50.0) or 50.0)
    except Exception:
        slow_rsi_short_max = 50.0

    slow_require_macd_sign = bool(thr_entry.get("slow_drift_require_macd_sign", True))

    ema_slow_slope_pct = 0.0
    try:
        ema_slow_now = float(latest["EMA_slow"])
        ema_slow_prev = float(df["EMA_slow"].iloc[-slow_slope_window])
        close_now = float(latest["Close"]) if float(latest["Close"]) != 0 else 1.0
        ema_slow_slope_pct = (ema_slow_now - ema_slow_prev) / close_now
    except Exception:
        ema_slow_slope_pct = 0.0

    # If ranging misclassified a slow drift, let EMA_slow slope override it.
    if slow_enabled and is_ranging and abs(float(ema_slow_slope_pct)) >= float(slow_min_slope_pct):
        is_ranging = False

    stoch_k = None
    stoch_d = None
    rsi_long_limit = None
    rsi_short_limit = None

    # 5) Mean Reversion / Extension Filter (Don't chase if too far from EMA)
    enable_ext_filter = bool(flt.get("enable_extension_filter", True))
    max_dist = float(thr_entry.get("max_dist_ema_fast", 0.04))
    dist_ema_fast = abs(latest["Close"] - latest["EMA_fast"]) / latest["EMA_fast"] if latest["EMA_fast"] > 0 else 0
    is_extended = enable_ext_filter and (dist_ema_fast > max_dist)

    if (
        latest["ADX"] > effective_min_adx
        and (not is_ranging)
        and (not is_anomaly)
        and (not is_extended)
        and vol_confirm
        and is_trending_up
    ):
        # Stochastic RSI filter (optional)
        if bool(flt.get("use_stoch_rsi_filter", True)):
            stoch_rsi = ta.momentum.StochRSIIndicator(
                df["Close"],
                window=int(ind["stoch_rsi_window"]),
                smooth1=int(ind["stoch_rsi_smooth1"]),
                smooth2=int(ind["stoch_rsi_smooth2"]),
            )
            try:
                _sk = stoch_rsi.stochrsi_k().iloc[-1]
                stoch_k = 0.0 if (_sk != _sk) else float(_sk)
            except (IndexError, KeyError):
                stoch_k = None
            try:
                _sd = stoch_rsi.stochrsi_d().iloc[-1]
                stoch_d = 0.0 if (_sd != _sd) else float(_sd)
            except (IndexError, KeyError):
                stoch_d = None

        # v4.1: Dynamic RSI Elasticity (DRE) - Linear interpolation for RSI gating
        adx_val = latest["ADX"]
        adx_min = float(min_adx)
        adx_max = float(tp["adx_strong_gt"])
        if adx_max <= adx_min:
            adx_max = adx_min + 1.0
        weight = max(0.0, min(1.0, (adx_val - adx_min) / (adx_max - adx_min)))

        rsi_long_limit = float(tp["rsi_long_weak"]) + weight * (
            float(tp["rsi_long_strong"]) - float(tp["rsi_long_weak"])
        )
        rsi_short_limit = float(tp["rsi_short_weak"]) + weight * (
            float(tp["rsi_short_strong"]) - float(tp["rsi_short_weak"])
        )

        high_conf_mult = float(thr_entry.get("high_conf_volume_mult", 2.5))

        # LONG
        if bullish_alignment and latest["Close"] > latest["EMA_fast"]:
            # NOTE: REEF (RSI extreme entry filter) is enforced at execution-time (PaperTrader/LiveTrader),
            # so it never blocks exits / signal-flip closes.
            if latest["RSI"] > rsi_long_limit:
                macd_ok = True
                if macd_mode == "accel":
                    macd_ok = latest["MACD_hist"] > prev["MACD_hist"]
                elif macd_mode == "sign":
                    macd_ok = latest["MACD_hist"] > 0
                elif macd_mode == "none":
                    macd_ok = True

                if macd_ok:
                    stoch_ok = True
                    if bool(flt.get("use_stoch_rsi_filter", True)) and stoch_k is not None:
                        stoch_ok = stoch_k < float(thr["stoch_rsi"]["block_long_if_k_gt"])
                    if stoch_ok and btc_ok_long:
                        signal, conf = "BUY", "medium"
                        if latest["Volume"] > (latest["vol_sma"] * high_conf_mult):
                            conf = "high"

        # SHORT
        elif bearish_alignment and latest["Close"] < latest["EMA_fast"]:
            # NOTE: REEF is execution-time only (entry gate), not a signal-generation filter.
            if latest["RSI"] < rsi_short_limit:
                macd_ok = True
                if macd_mode == "accel":
                    macd_ok = latest["MACD_hist"] < prev["MACD_hist"]
                elif macd_mode == "sign":
                    macd_ok = latest["MACD_hist"] < 0
                elif macd_mode == "none":
                    macd_ok = True

                if macd_ok:
                    stoch_ok = True
                    if bool(flt.get("use_stoch_rsi_filter", True)) and stoch_k is not None:
                        stoch_ok = stoch_k > float(thr["stoch_rsi"]["block_short_if_k_lt"])
                    if stoch_ok and btc_ok_short:
                        signal, conf = "SELL", "medium"
                        if latest["Volume"] > (latest["vol_sma"] * high_conf_mult):
                            conf = "high"

    # --- v5.042: Pullback continuation entry (capture trend continuation without chasing extension) ---
    if (
        pullback_enabled
        and signal == "NEUTRAL"
        and (not is_anomaly)
        and (not is_extended)
        and (not is_ranging)
        and bool(vol_confirm)
        and float(latest["ADX"]) >= float(pullback_min_adx)
    ):
        try:
            prev_close = float(prev.get("Close", 0.0) or 0.0)
        except Exception:
            prev_close = 0.0
        try:
            prev_ema_fast = float(prev.get("EMA_fast", 0.0) or 0.0)
        except Exception:
            prev_ema_fast = 0.0
        try:
            close_v = float(latest.get("Close", 0.0) or 0.0)
        except Exception:
            close_v = 0.0
        try:
            ema_fast_v = float(latest.get("EMA_fast", 0.0) or 0.0)
        except Exception:
            ema_fast_v = 0.0
        try:
            rsi_v = float(latest.get("RSI", 0.0) or 0.0)
        except Exception:
            rsi_v = 0.0
        try:
            macd_h = float(latest.get("MACD_hist", 0.0) or 0.0)
        except Exception:
            macd_h = 0.0

        cross_up = (prev_close <= prev_ema_fast) and (close_v > ema_fast_v)
        cross_dn = (prev_close >= prev_ema_fast) and (close_v < ema_fast_v)

        # Long pullback continuation
        if cross_up and bullish_alignment and btc_ok_long:
            macd_ok = (macd_h > 0.0) if pullback_require_macd_sign else True
            if macd_ok and (rsi_v >= float(pullback_rsi_long_min)):
                signal, conf = "BUY", str(pullback_conf)
                pullback_used = True

        # Short pullback continuation
        elif cross_dn and bearish_alignment and btc_ok_short:
            macd_ok = (macd_h < 0.0) if pullback_require_macd_sign else True
            if macd_ok and (rsi_v <= float(pullback_rsi_short_max)):
                signal, conf = "SELL", str(pullback_conf)
                pullback_used = True

    # --- v5.040: Slow Drift Entry (capture low-vol grind) ---
    if (
        slow_enabled
        and signal == "NEUTRAL"
        and (not is_anomaly)
        and (not is_extended)
        and (not is_ranging)
        and bool(vol_confirm)
        and float(latest["ADX"]) >= float(slow_min_adx)
    ):
        try:
            macd_h = float(latest.get("MACD_hist", 0.0) or 0.0)
        except Exception:
            macd_h = 0.0
        try:
            rsi_v = float(latest.get("RSI", 0.0) or 0.0)
        except Exception:
            rsi_v = 0.0

        # Long drift: requires slope >= +threshold
        if (
            bullish_alignment
            and float(latest["Close"]) > float(latest["EMA_slow"])
            and btc_ok_long
            and ema_slow_slope_pct >= float(slow_min_slope_pct)
        ):
            macd_ok = (macd_h > 0.0) if slow_require_macd_sign else True
            if macd_ok and rsi_v >= float(slow_rsi_long_min):
                signal, conf = "BUY", "low"
                slow_used = True

        # Short drift: requires slope <= -threshold
        elif (
            bearish_alignment
            and float(latest["Close"]) < float(latest["EMA_slow"])
            and btc_ok_short
            and ema_slow_slope_pct <= -float(slow_min_slope_pct)
        ):
            macd_ok = (macd_h < 0.0) if slow_require_macd_sign else True
            if macd_ok and rsi_v <= float(slow_rsi_short_max):
                signal, conf = "SELL", "low"
                slow_used = True

    latest = latest.copy()
    latest["macd_entry_mode"] = str(macd_mode)
    latest["ave_enabled"] = bool(ave_enabled)
    latest["atr_ratio"] = None if atr_ratio is None else float(atr_ratio)
    latest["vol_spike_mult"] = float(vol_spike_mult)
    latest["pullback_enabled"] = bool(pullback_enabled)
    latest["pullback_used"] = bool(pullback_used)
    latest["slow_drift_enabled"] = bool(slow_enabled)
    latest["slow_drift_used"] = bool(slow_used)
    latest["ema_slow_slope_pct"] = float(ema_slow_slope_pct)
    # Effective ADX threshold used at entry time — exits use this instead of a
    # separate parameter so entry and exit can never contradict each other.
    if slow_used:
        latest["entry_adx_threshold"] = float(slow_min_adx)
    elif pullback_used:
        latest["entry_adx_threshold"] = float(pullback_min_adx)
    else:
        latest["entry_adx_threshold"] = float(effective_min_adx)
    if stoch_k is not None:
        latest["stoch_k"] = stoch_k
    if stoch_d is not None:
        latest["stoch_d"] = stoch_d
    latest["tp_mult"] = dynamic_tp_mult
    latest["is_anomaly"] = is_anomaly

    # Audit context (stored into SQLite `signals.meta_json` and `trades.meta_json`).
    # Keep this JSON-safe (plain Python types) so it can be persisted for later review/debug.
    try:
        tags: list[str] = []

        adx_v = float(latest.get("ADX", 0.0) or 0.0)
        ema_fast_v = float(latest.get("EMA_fast", 0.0) or 0.0)
        ema_slow_v = float(latest.get("EMA_slow", 0.0) or 0.0)
        ema_macro_v = float(latest.get("EMA_macro", 0.0) or 0.0)
        close_v = float(latest.get("Close", 0.0) or 0.0)
        rsi_v = float(latest.get("RSI", 0.0) or 0.0)
        macd_v = float(latest.get("MACD_hist", 0.0) or 0.0)
        prev_macd_v = float(latest.get("prev_MACD_hist", 0.0) or 0.0)

        # Gate tags (why a signal is allowed to form).
        if bool(is_ranging):
            tags.append("gate:ranging")
        else:
            tags.append("gate:not_ranging")
        if bool(is_anomaly):
            tags.append("gate:anomaly")
        else:
            tags.append("gate:not_anomaly")
        if bool(is_extended):
            tags.append("gate:extended")
        else:
            tags.append("gate:not_extended")
        if bool(vol_confirm):
            tags.append("gate:volume_ok")
        else:
            tags.append("gate:volume_block")
        if bool(is_trending_up):
            tags.append("gate:adx_rising_or_saturated")
        else:
            tags.append("gate:adx_not_rising")
        if adx_v > float(effective_min_adx or 0.0):
            tags.append("gate:adx>=min")
        else:
            tags.append("gate:adx<min")

        # Alignment tags
        if ema_fast_v > 0 and ema_slow_v > 0:
            if ema_fast_v > ema_slow_v:
                tags.append("align:bullish")
            elif ema_fast_v < ema_slow_v:
                tags.append("align:bearish")
        if bool(flt.get("require_macro_alignment", False)):
            tags.append("filter:macro_required")
            if ema_macro_v > 0 and ema_slow_v > 0:
                if ema_slow_v > ema_macro_v:
                    tags.append("align:macro_bull")
                elif ema_slow_v < ema_macro_v:
                    tags.append("align:macro_bear")

        # Signal tags
        if signal == "BUY":
            tags.append("signal:BUY")
            if close_v > ema_fast_v:
                tags.append("cond:close>ema_fast")
            if rsi_long_limit is not None and rsi_v > float(rsi_long_limit):
                tags.append("cond:rsi_long_ok")
            if macd_v > prev_macd_v:
                tags.append("cond:macd_hist_rising")
            if btc_ok_long:
                tags.append("cond:btc_ok")
            if conf == "high":
                tags.append("conf:high_volume")
        elif signal == "SELL":
            tags.append("signal:SELL")
            if close_v < ema_fast_v:
                tags.append("cond:close<ema_fast")
            if rsi_short_limit is not None and rsi_v < float(rsi_short_limit):
                tags.append("cond:rsi_short_ok")
            if macd_v < prev_macd_v:
                tags.append("cond:macd_hist_falling")
            if btc_ok_short:
                tags.append("cond:btc_ok")
            if conf == "high":
                tags.append("conf:high_volume")
        else:
            tags.append("signal:NEUTRAL")

        if bool(slow_used):
            tags.append("mode:slow_drift")
        if bool(pullback_used):
            tags.append("mode:pullback")

        # v5.018: REEF (entry extreme RSI filter) — do not mutate signal here; just expose for audits.
        # v5.020: REEF v2 — ADX-adaptive: use extreme thresholds when ADX >= reef_adx_threshold.
        reef_enabled = bool(trade_cfg.get("enable_reef_filter", True))
        try:
            reef_long_block_gt = float(trade_cfg.get("reef_long_rsi_block_gt", 70.0))
        except Exception:
            reef_long_block_gt = 70.0
        try:
            reef_short_block_lt = float(trade_cfg.get("reef_short_rsi_block_lt", 30.0))
        except Exception:
            reef_short_block_lt = 30.0
        try:
            reef_adx_thr = float(trade_cfg.get("reef_adx_threshold", 45.0))
        except Exception:
            reef_adx_thr = 45.0
        try:
            reef_long_extreme_gt = float(trade_cfg.get("reef_long_rsi_extreme_gt", 75.0))
        except Exception:
            reef_long_extreme_gt = 75.0
        try:
            reef_short_extreme_lt = float(trade_cfg.get("reef_short_rsi_extreme_lt", 25.0))
        except Exception:
            reef_short_extreme_lt = 25.0

        # Select tier based on ADX strength.
        if adx_v >= reef_adx_thr:
            reef_long_threshold = reef_long_extreme_gt
            reef_short_threshold = reef_short_extreme_lt
        else:
            reef_long_threshold = reef_long_block_gt
            reef_short_threshold = reef_short_block_lt

        reef_blocks_entry = False
        if not reef_enabled:
            tags.append("reef:disabled")
        elif signal in {"BUY", "SELL"}:
            if signal == "BUY" and rsi_v > reef_long_threshold:
                reef_blocks_entry = True
                tags.append("reef:block_buy")
            elif signal == "SELL" and rsi_v < reef_short_threshold:
                reef_blocks_entry = True
                tags.append("reef:block_sell")
            else:
                tags.append("reef:pass")
        else:
            tags.append("reef:n/a")

        latest["audit"] = {
            "symbol": str(symbol or "").upper(),
            "signal": str(signal or "").upper(),
            "confidence": str(conf or "").lower(),
            "tags": tags,
            "gates": {
                "adx": adx_v,
                "effective_min_adx": float(effective_min_adx or 0.0),
                "is_ranging": bool(is_ranging),
                "is_anomaly": bool(is_anomaly),
                "is_extended": bool(is_extended),
                "vol_confirm": bool(vol_confirm),
                "is_trending_up": bool(is_trending_up),
                "enable_extension_filter": bool(enable_ext_filter),
                "dist_ema_fast": float(dist_ema_fast or 0.0),
                "max_dist_ema_fast": float(max_dist or 0.0),
                "macd_hist_entry_mode": str(macd_mode),
                "ave_enabled": bool(ave_enabled),
                "ave_avg_atr_window": int(ave_window),
                "ave_atr_ratio": None if atr_ratio is None else float(atr_ratio),
                "ave_atr_ratio_gt": float(ave_atr_ratio_gt),
                "ave_adx_mult": float(ave_adx_mult),
                "vol_spike_mult": float(vol_spike_mult),
                "require_macro_alignment": bool(flt.get("require_macro_alignment", False)),
                "require_btc_alignment": bool(flt.get("require_btc_alignment", True)),
                "btc_bullish": None if btc_bullish is None else bool(btc_bullish),
                "btc_ok_long": bool(btc_ok_long),
                "btc_ok_short": bool(btc_ok_short),
                "pullback_enabled": bool(pullback_enabled),
                "pullback_min_adx": float(pullback_min_adx),
                "pullback_confidence": str(pullback_conf),
                "pullback_require_macd_sign": bool(pullback_require_macd_sign),
                "pullback_rsi_long_min": float(pullback_rsi_long_min),
                "pullback_rsi_short_max": float(pullback_rsi_short_max),
                "pullback_used": bool(pullback_used),
                "slow_drift_enabled": bool(slow_enabled),
                "slow_drift_min_adx": float(slow_min_adx),
                "slow_drift_min_slope_pct": float(slow_min_slope_pct),
                "slow_drift_slope_window": int(slow_slope_window),
                "slow_drift_require_macd_sign": bool(slow_require_macd_sign),
                "slow_drift_rsi_long_min": float(slow_rsi_long_min),
                "slow_drift_rsi_short_max": float(slow_rsi_short_max),
                "reef_enabled": bool(reef_enabled),
                "reef_long_rsi_block_gt": float(reef_long_block_gt),
                "reef_short_rsi_block_lt": float(reef_short_block_lt),
                "reef_blocks_entry": bool(reef_blocks_entry),
            },
            "values": {
                "close": close_v,
                "ema_fast": ema_fast_v,
                "ema_slow": ema_slow_v,
                "ema_macro": ema_macro_v,
                "rsi": rsi_v,
                "rsi_long_limit": None if rsi_long_limit is None else float(rsi_long_limit),
                "rsi_short_limit": None if rsi_short_limit is None else float(rsi_short_limit),
                "macd_hist": macd_v,
                "prev_macd_hist": prev_macd_v,
                "bb_width_ratio": float(bb_width_ratio or 0.0),
                "tp_mult": float(dynamic_tp_mult or 0.0),
                "stoch_k": None if stoch_k is None else float(stoch_k),
                "stoch_d": None if stoch_d is None else float(stoch_d),
                "adx_slope": float(latest.get("ADX_slope", 0.0) or 0.0),
                "atr": float(latest.get("ATR", 0.0) or 0.0),
                "atr_slope": float(latest.get("ATR_slope", 0.0) or 0.0),
                "slow_drift_used": bool(slow_used),
                "ema_slow_slope_pct": float(ema_slow_slope_pct),
            },
        }
    except Exception:
        pass

    # ── AQC-803: Create decision event and log gate evaluations ──────────
    try:
        _all_gates_pass = (
            not is_ranging
            and not is_anomaly
            and not is_extended
            and vol_confirm
            and is_trending_up
            and (latest.get("ADX", 0) > effective_min_adx)
        )
        _status = "executed" if signal != "NEUTRAL" else ("blocked" if not _all_gates_pass else "hold")
        _action = {
            "BUY": "open_long",
            "SELL": "open_short",
        }.get(signal, "hold")
        _rejection = None
        if _status == "blocked":
            _blocked_gates = []
            if is_ranging:
                _blocked_gates.append("ranging")
            if is_anomaly:
                _blocked_gates.append("anomaly")
            if is_extended:
                _blocked_gates.append("extension")
            if not vol_confirm:
                _blocked_gates.append("volume")
            if not is_trending_up:
                _blocked_gates.append("adx_rising")
            if latest.get("ADX", 0) <= effective_min_adx:
                _blocked_gates.append("adx_gate")
            _rejection = "blocked by: " + ", ".join(_blocked_gates) if _blocked_gates else None

        _decision_id = create_decision_event(
            symbol=str(symbol or ""),
            event_type="entry_signal",
            status=_status,
            phase="signal_generation",
            triggered_by="schedule",
            action_taken=_action,
            rejection_reason=_rejection,
            context=latest.get("audit") if hasattr(latest, "get") else None,
        )
        latest["_decision_id"] = _decision_id

        # Log individual gate evaluations against this decision.
        _audit = latest.get("audit") if hasattr(latest, "get") else None
        if _audit and isinstance(_audit, dict):
            _log_gates_for_decision(
                _decision_id,
                _audit.get("gates", {}),
                _audit.get("values", {}),
            )
    except Exception as _de_exc:
        logger.debug("analyze: decision event logging failed: %s", _de_exc)

    # ── reverse_entry_signal: flip BUY↔SELL (matches Rust apply_reverse) ──
    # Allows the sweep to optimise a contrarian mode without touching the
    # signal generation logic.  auto_reverse (breadth-based) takes precedence
    # when enabled, mirroring the Rust engine behaviour.
    try:
        mr = cfg.get("market_regime") or {}
        _should_reverse = bool(trade_cfg.get("reverse_entry_signal", False))
        if bool(mr.get("enable_auto_reverse", False)):
            _ar_lo = float(mr.get("auto_reverse_breadth_low", 10.0))
            _ar_hi = float(mr.get("auto_reverse_breadth_high", 90.0))
            # breadth_pct is not available in per-symbol analyze(); the engine
            # handles auto_reverse at the decision routing level.  Here we only
            # apply the static reverse_entry_signal toggle.
            pass  # auto_reverse defers to engine/core.py
        if _should_reverse and signal in ("BUY", "SELL"):
            signal = "SELL" if signal == "BUY" else "BUY"
            latest["_reversed_signal"] = True
            # BUG-S2: patch audit/decision to reflect post-reversal signal
            _audit = latest.get("audit") if hasattr(latest, "get") else None
            if isinstance(_audit, dict):
                _audit["signal"] = signal
                _audit["action_taken"] = "open_short" if signal == "SELL" else "open_long"
    except Exception:
        pass

    return signal, conf, latest
