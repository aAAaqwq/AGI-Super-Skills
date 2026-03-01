from __future__ import annotations

import json
import sqlite3
import stat
from pathlib import Path

import factory_run

_FIXED_TS_MS = 1_700_000_000_000  # 2023-11-14T22:13:20Z — stable test anchor


_CANDLES_SCHEMA = """
CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    interval TEXT NOT NULL,
    t INTEGER NOT NULL,
    t_close INTEGER,
    o REAL,
    h REAL,
    l REAL,
    c REAL,
    v REAL,
    n INTEGER,
    updated_at TEXT,
    PRIMARY KEY (symbol, interval, t)
);
CREATE INDEX IF NOT EXISTS idx_candles_symbol_interval_t
ON candles(symbol, interval, t);
"""


_FUNDING_SCHEMA = """
CREATE TABLE IF NOT EXISTS funding_rates (
    symbol TEXT NOT NULL,
    time INTEGER NOT NULL,
    funding_rate REAL NOT NULL,
    premium REAL,
    PRIMARY KEY (symbol, time)
);
"""


def _mk_candles_db(path: Path, *, symbol: str, interval: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.executescript(_CANDLES_SCHEMA)
        interval_ms = 3_600_000 if interval == "1h" else 60_000
        now_ms = _FIXED_TS_MS
        anchor = (now_ms // interval_ms) * interval_ms

        # Generate enough contiguous history so default factory data checks pass (200 bars).
        bars_needed = 240
        start = anchor - ((bars_needed - 1) * interval_ms)
        rows = []
        for t in range(int(start), int(anchor) + interval_ms, interval_ms):
            rows.append(
                (
                    symbol,
                    interval,
                    int(t),
                    int(t + interval_ms),
                    float(100 + (t - start) / interval_ms),
                    float(101 + (t - start) / interval_ms),
                    float(99 + (t - start) / interval_ms),
                    float(100 + (t - start) / interval_ms),
                    1.0,
                )
            )
        con.executemany(
            "INSERT OR REPLACE INTO candles (symbol, interval, t, t_close, o, h, l, c, v) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        con.commit()
    finally:
        con.close()


def _mk_funding_db(path: Path, *, symbol: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.executescript(_FUNDING_SCHEMA)
        now_ms = _FIXED_TS_MS
        h = 3_600_000
        rows = []
        # Generate >72h of hourly rows to satisfy the default lookback window.
        for i in range(0, 80):
            rows.append((symbol, int(now_ms - (79 - i) * h), 0.0001))
        con.executemany(
            "INSERT OR REPLACE INTO funding_rates (symbol, time, funding_rate, premium) VALUES (?, ?, ?, NULL)",
            rows,
        )
        con.commit()
    finally:
        con.close()


def _mk_stub_backtester(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env python3
import json
import sys

def _arg(flag: str):
    try:
        i = sys.argv.index(flag)
        return sys.argv[i + 1]
    except Exception:
        return None

def main() -> int:
    if len(sys.argv) < 2:
        return 2
    cmd = sys.argv[1]
    if cmd == "sweep":
        out = _arg("--output")
        if not out:
            return 2
        # Keep total_trades >= 20 because tools/generate_config.py filters by --min-trades (default 20).
        rows = []
        for idx in range(30):
            n = idx + 1
            rows.append(
                {
                    "total_pnl": 10.0 - (idx * 0.15),
                    "final_balance": 10000.0 + 10.0 - (idx * 0.15),
                    "total_trades": 25,
                    "win_rate": 0.60 - (idx * 0.002),
                    "profit_factor": 1.20 - (idx * 0.005),
                    "max_drawdown_pct": 0.05 - (idx * 0.0005),
                    "sharpe_ratio": 0.10 - (idx * 0.001),
                    "overrides": [["trade.leverage", float(3.0 + idx)], ["indicators.ema_fast_window", float(21.0 + idx)]],
                }
            )
        with open(out, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\\n")
        return 0
    if cmd == "replay":
        out = _arg("--output")
        if not out:
            return 2
        rep = {
            "initial_balance": 10000.0,
            "final_balance": 10005.0,
            "total_pnl": 5.0,
            "total_trades": 25,
            "win_rate": 0.60,
            "profit_factor": 1.20,
            "max_drawdown_pct": 0.02,
            "total_fees": 1.0,
        }
        with open(out, "w", encoding="utf-8") as f:
            json.dump(rep, f)
        return 0
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
""",
        encoding="utf-8",
    )
    st = path.stat()
    path.chmod(st.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_factory_smoke_run_produces_artifacts(tmp_path, monkeypatch) -> None:
    artifacts_root = tmp_path / "artifacts"
    cfg = tmp_path / "base.yaml"
    cfg.write_text(
        "\n".join(
            [
                "global:",
                "  trade:",
                "    allocation_pct: 0.03",
                "    leverage: 3.0",
                "    sl_atr_mult: 2.0",
                "    tp_atr_mult: 4.0",
                "    slippage_bps: 10.0",
                "    max_open_positions: 20",
                "    max_total_margin_pct: 0.6",
                "    min_notional_usd: 10.0",
                "    min_atr_pct: 0.003",
                "    bump_to_min_notional: false",
                "  indicators:",
                "    adx_window: 14",
                "    ema_fast_window: 20",
                "    ema_slow_window: 50",
                "    bb_window: 20",
                "    atr_window: 14",
                "  thresholds:",
                "    entry:",
                "      min_adx: 22.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    candles_db = tmp_path / "candles_1h.db"
    _mk_candles_db(candles_db, symbol="BTC", interval="1h")

    funding_db = tmp_path / "funding_rates.db"
    _mk_funding_db(funding_db, symbol="BTC")

    bt_stub = tmp_path / "mei-backtester-stub.py"
    _mk_stub_backtester(bt_stub)

    monkeypatch.setenv("MEI_BACKTESTER_BIN", str(bt_stub))

    run_id = "test_smoke"
    rc = factory_run.main(
        [
            "--run-id",
            run_id,
            "--profile",
            "smoke",
            "--artifacts-dir",
            str(artifacts_root),
            "--config",
            str(cfg),
            "--interval",
            "1h",
            "--candles-db",
            str(candles_db),
            "--funding-db",
            str(funding_db),
            "--sweep-spec",
            str(tmp_path / "sweep.yaml"),
            "--shortlist-per-mode",
            "0",
            "--num-candidates",
            "2",
        ]
    )
    assert rc == 0

    metas = list(artifacts_root.rglob("run_metadata.json"))
    assert len(metas) == 1
    meta = json.loads(metas[0].read_text(encoding="utf-8"))
    assert meta["run_id"] == run_id

    run_dir = Path(meta["run_dir"])
    assert (run_dir / "reports" / "report.md").exists()
    assert (run_dir / "reports" / "report.json").exists()
    assert (run_dir / "reports" / "validation_report.md").exists()
    assert isinstance(meta.get("registry_db"), str)
    assert Path(str(meta.get("registry_db"))).exists()
    assert (artifacts_root / "registry" / "registry.sqlite").exists()

    candidates = meta.get("candidate_configs", [])
    assert isinstance(candidates, list)
    assert candidates, "candidate metadata should be recorded"
    assert candidates[0].get("sweep_stage") in {"cpu", "gpu", "gpu_tpe"}
    assert candidates[0].get("validation_gate") in {
        "replay_only",
        "score_v1+walk_forward",
        "score_v1+walk_forward+slippage",
    }
    assert "canonical_cpu_verified" in candidates[0]

    report = json.loads((run_dir / "reports" / "report.json").read_text(encoding="utf-8"))
    items = report.get("items", []) if isinstance(report, dict) else []
    assert items and isinstance(items[0], dict)
    assert "sweep_stage" in items[0]
    assert "replay_stage" in items[0]
    assert "canonical_cpu_verified" in items[0]
