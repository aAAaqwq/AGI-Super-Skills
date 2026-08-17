#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v5.8 引擎测试 — 契约、因子数值、多时刻采样、稳定性"""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent  # scripts/ 的上一级 = skill 根
ENGINE = SKILL / "5minbtc-engine-v5.7.py"
MONITOR = HERE / "5minbtc-monitor.py"

spec = importlib.util.spec_from_file_location("eng", ENGINE)
eng = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eng)


# ---------------- 契约 ----------------

def run_engine_subprocess(timeout=60):
    out = subprocess.run(["python3", str(ENGINE)], capture_output=True,
                         text=True, timeout=timeout)
    assert out.returncode == 0, f"engine exit={out.returncode} stderr={out.stderr}"
    return json.loads(out.stdout)


def test_version_is_580():
    assert eng.__file__ or True  # module loads
    # version 来自运行时 JSON
    d = run_engine_subprocess()
    assert d["version"] == "5.8.0"


def test_prediction_contract():
    d = run_engine_subprocess()
    pred = d["prediction"]
    for k in ("bias", "strength", "confidence", "score",
              "pred_close", "pred_high", "pred_low"):
        assert k in pred, f"prediction missing {k}"
    assert pred["bias"] in ("bull", "neutral", "bear")
    assert pred["strength"] in ("weak", "medium", "moderate", "strong")
    assert 0 <= pred["confidence"] <= 100


def test_top_level_contract():
    d = run_engine_subprocess()
    for k in ("version", "candle", "price", "recent_candles", "indicators",
              "fng", "factors", "regime", "chainlink_offset", "atr_spike",
              "fng_black_swan", "news_risk", "prediction"):
        assert k in d, f"top-level missing {k}"
    p = d["price"]
    assert p["low"] <= p["current"] <= p["high"]


def test_taker_buy_in_factors():
    d = run_engine_subprocess()
    assert "taker_buy" in d["factors"]
    assert -1.0 <= d["factors"]["taker_buy"] <= 1.0


def test_taker_buy_in_weights():
    assert "taker_buy" in eng.BASE_W
    assert eng.BASE_W["taker_buy"] > 0
    for regime, adj in eng.REGIME_ADJ.items():
        assert "taker_buy" in adj, f"REGIME_ADJ[{regime}] missing taker_buy"


# ---------------- 因子数值 ----------------

def test_taker_buy_signal_math():
    # 全主动买: tb=v → ratio=1 → 2*(1-0.5)*3=3 → clamp 1.0
    candles = [{"o": 100, "h": 101, "l": 99, "c": 101, "v": 10, "tb": 10, "ct": 0}] * 6
    assert eng.taker_buy_signal(candles) == 1.0
    # 全主动卖: tb=0 → ratio=0 → 2*(0-0.5)*3=-3 → clamp -1.0 (v>0 有效)
    candles0 = [{"o": 100, "h": 101, "l": 99, "c": 99, "v": 10, "tb": 0, "ct": 0}] * 6
    assert eng.taker_buy_signal(candles0) == -1.0
    # 均衡 0.5 → 0
    candles_mid = [{"o": 100, "h": 101, "l": 99, "c": 100, "v": 10, "tb": 5, "ct": 0}] * 6
    assert eng.taker_buy_signal(candles_mid) == 0.0
    # 用已完成 K线 (排除当前未完成)
    done = [{"o": 100, "h": 101, "l": 99, "c": 100, "v": 10, "tb": 10, "ct": 0}] * 5
    cur = [{"o": 100, "h": 101, "l": 99, "c": 100, "v": 10, "tb": 0, "ct": 0}]
    assert eng.taker_buy_signal(done + cur) == 1.0  # 当前 tb=0 被排除
    # 数据容错: tb>v 时钳制到 v → ratio=1
    c_over = [{"o": 100, "h": 101, "l": 99, "c": 101, "v": 10, "tb": 99, "ct": 0}] * 6
    assert eng.taker_buy_signal(c_over) == 1.0


def test_taker_buy_signal_edges():
    # 空列表
    assert eng.taker_buy_signal([]) == 0.0
    # v=0 全跳过
    c = [{"o": 100, "h": 101, "l": 99, "c": 100, "v": 0, "tb": 0, "ct": 0}] * 6
    assert eng.taker_buy_signal(c) == 0.0
    # 无 tb 字段向后兼容 (fetch_klines 守卫不足时)
    c2 = [{"o": 100, "h": 101, "l": 99, "c": 100, "v": 10}] * 6
    assert eng.taker_buy_signal(c2) == 0.0


# ---------------- 订单簿多时刻采样 ----------------

def test_fetch_depth_avg_merges_and_truncates(monkeypatch):
    calls = {"n": 0}
    snaps = [
        {"bids": [(100.0, 1.0), (99.5, 2.0)], "asks": [(100.5, 3.0)]},
        {"bids": [(100.0, 3.0), (99.5, 1.0)], "asks": [(100.5, 1.0)]},
        None,  # 失败采样应被跳过
    ]
    def fake_depth(*a, **k):
        s = snaps[calls["n"] % len(snaps)]
        calls["n"] += 1
        return s
    monkeypatch.setattr(eng, "fetch_depth", fake_depth)
    monkeypatch.setattr(eng, "time", _FakeTime())
    res = eng.fetch_depth_avg(limit=20, samples=3, interval_s=0.0)
    assert res is not None
    # 同价位取平均: (1+3)/2=2 (第3次None被跳过 → got=2)
    assert res["bids"][0] == (100.0, 2.0)
    assert res["bids"][1] == (99.5, 1.5)
    assert res["asks"][0] == (100.5, 2.0)


def test_fetch_depth_avg_all_fail(monkeypatch):
    monkeypatch.setattr(eng, "fetch_depth", lambda *a, **k: None)
    monkeypatch.setattr(eng, "time", _FakeTime())
    assert eng.fetch_depth_avg(samples=3, interval_s=0.0) is None


def test_fetch_depth_avg_limit_truncation(monkeypatch):
    # 3 次采样价位漂移 → 合并后层数 > limit, 必须截断到 limit
    def fake_depth(*a, **k):
        return {"bids": [(float(i), 1.0) for i in range(100, 0, -1)],
                "asks": [(float(i), 1.0) for i in range(101, 201)]}
    monkeypatch.setattr(eng, "fetch_depth", fake_depth)
    monkeypatch.setattr(eng, "time", _FakeTime())
    res = eng.fetch_depth_avg(limit=20, samples=3, interval_s=0.0)
    assert len(res["bids"]) == 20
    assert len(res["asks"]) == 20


class _FakeTime:
    def sleep(self, *_a, **_k):
        return None


# ---------------- 稳定性 (可跳过) ----------------

@pytest.mark.slow
def test_multiple_runs_stable():
    biases = []
    for _ in range(3):
        d = run_engine_subprocess()
        biases.append(d["prediction"]["bias"])
        assert "taker_buy" in d["factors"]
    # 只断言不崩, 不做 bias 一致性断言 (market 实时变化)


def test_monitor_dry_run_compatible():
    out = subprocess.run(["python3", str(MONITOR), "--dry-run"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, f"monitor dry-run failed: {out.stderr}"
    assert "DRY" in out.stdout
    assert "[20" in out.stdout or "progress" in out.stdout or "conf=" in out.stdout


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
