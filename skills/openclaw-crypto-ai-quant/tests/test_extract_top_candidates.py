"""Tests for _extract_top_candidates() — single-pass streaming extraction."""

from __future__ import annotations

import json
from pathlib import Path

from factory_run import _extract_top_candidates


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )


def _read_jsonl(path: Path) -> list[dict]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _make_row(
    config_id: str,
    pnl: float = 0.0,
    trades: int = 50,
    pf: float = 1.0,
    dd: float = 0.10,
    wr: float = 0.50,
    sharpe: float = 0.5,
    overrides: dict | None = None,
) -> dict:
    return {
        "config_id": config_id,
        "total_pnl": pnl,
        "total_trades": trades,
        "profit_factor": pf,
        "max_drawdown_pct": dd,
        "win_rate": wr,
        "sharpe_ratio": sharpe,
        "overrides": overrides or {"trade.leverage": 5.0},
    }


# ---- Basic extraction ----


def test_extract_basic_pnl_ranking(tmp_path: Path) -> None:
    src = tmp_path / "sweep.jsonl"
    dst = tmp_path / "candidates.jsonl"
    rows = [
        _make_row("c1", pnl=100),
        _make_row("c2", pnl=300),
        _make_row("c3", pnl=200),
    ]
    _write_jsonl(src, rows)

    total, errors = _extract_top_candidates(
        src, dst, max_rank=2, modes=["pnl"]
    )
    assert total == 3
    assert errors == []

    result = _read_jsonl(dst)
    assert len(result) == 2
    ids = [r["config_id"] for r in result]
    assert ids[0] == "c2"  # best pnl
    assert ids[1] == "c3"  # 2nd best


def test_extract_multi_mode_dedup(tmp_path: Path) -> None:
    """Rows that rank high in multiple modes appear only once."""
    src = tmp_path / "sweep.jsonl"
    dst = tmp_path / "candidates.jsonl"
    rows = [
        _make_row("c1", pnl=300, dd=0.05),  # best pnl AND best dd
        _make_row("c2", pnl=200, dd=0.08),
        _make_row("c3", pnl=100, dd=0.03),  # 2nd best dd
        _make_row("c4", pnl=250, dd=0.20),
    ]
    _write_jsonl(src, rows)

    total, errors = _extract_top_candidates(
        src, dst, max_rank=2, modes=["pnl", "dd"]
    )
    assert total == 4
    assert errors == []

    result = _read_jsonl(dst)
    ids = [r["config_id"] for r in result]
    # c1 ranks top in pnl AND dd but should appear only once
    assert ids.count("c1") == 1
    # We should see candidates from both modes
    assert "c1" in ids  # top pnl + top dd
    assert len(result) <= 4  # max_rank=2 per mode, but deduped


def test_extract_dd_mode_prefers_low_dd(tmp_path: Path) -> None:
    src = tmp_path / "sweep.jsonl"
    dst = tmp_path / "candidates.jsonl"
    rows = [
        _make_row("high_dd", pnl=500, dd=0.50),
        _make_row("low_dd", pnl=100, dd=0.01),
        _make_row("mid_dd", pnl=200, dd=0.10),
    ]
    _write_jsonl(src, rows)

    total, _ = _extract_top_candidates(
        src, dst, max_rank=1, modes=["dd"]
    )
    assert total == 3

    result = _read_jsonl(dst)
    assert len(result) == 1
    assert result[0]["config_id"] == "low_dd"


def test_extract_balanced_mode(tmp_path: Path) -> None:
    src = tmp_path / "sweep.jsonl"
    dst = tmp_path / "candidates.jsonl"
    rows = [
        _make_row("balanced_best", pnl=150, pf=3.0, sharpe=2.0, dd=0.02, trades=100),
        _make_row("pnl_best", pnl=500, pf=1.0, sharpe=0.1, dd=0.50, trades=100),
    ]
    _write_jsonl(src, rows)

    total, _ = _extract_top_candidates(
        src, dst, max_rank=1, modes=["balanced"]
    )
    result = _read_jsonl(dst)
    assert len(result) == 1
    assert result[0]["config_id"] == "balanced_best"


# ---- min_trades filtering ----


def test_extract_min_trades_filtering(tmp_path: Path) -> None:
    src = tmp_path / "sweep.jsonl"
    dst = tmp_path / "candidates.jsonl"
    rows = [
        _make_row("low_trades", pnl=999, trades=5),
        _make_row("ok_trades", pnl=100, trades=50),
    ]
    _write_jsonl(src, rows)

    total, _ = _extract_top_candidates(
        src, dst, max_rank=10, modes=["pnl"], min_trades=20
    )
    assert total == 2

    result = _read_jsonl(dst)
    assert len(result) == 1
    assert result[0]["config_id"] == "ok_trades"


# ---- Schema validation ----


def test_extract_with_schema_validation(tmp_path: Path) -> None:
    src = tmp_path / "sweep.jsonl"
    dst = tmp_path / "candidates.jsonl"
    rows = [
        {
            "schema_version": 1,
            "config_id": "cfg-ok",
            "output_mode": "candidate",
            "candidate_mode": True,
            "total_pnl": 100,
            "total_trades": 50,
            "profit_factor": 1.5,
            "max_drawdown_pct": 0.05,
            "overrides": {"trade.leverage": 5.0},
        },
        {
            "config_id": "cfg-bad",
            "output_mode": "full",
            "candidate_mode": False,
            "total_pnl": 200,
            "total_trades": 50,
            "profit_factor": 2.0,
            "max_drawdown_pct": 0.03,
            "overrides": {},
        },
    ]
    _write_jsonl(src, rows)

    total, errors = _extract_top_candidates(
        src, dst, max_rank=10, modes=["pnl"], validate_schema=True
    )
    # Only the valid row is extracted; the bad row produces schema errors.
    assert total == 1
    assert len(errors) > 0
    assert any("candidate_mode is not true" in e for e in errors)

    result = _read_jsonl(dst)
    assert len(result) == 1
    assert result[0]["config_id"] == "cfg-ok"


# ---- Edge cases ----


def test_extract_empty_file(tmp_path: Path) -> None:
    src = tmp_path / "sweep.jsonl"
    dst = tmp_path / "candidates.jsonl"
    src.write_text("", encoding="utf-8")

    total, errors = _extract_top_candidates(
        src, dst, max_rank=10, modes=["pnl"]
    )
    assert total == 0
    assert errors == []

    result = _read_jsonl(dst)
    assert result == []


def test_extract_fewer_rows_than_max_rank(tmp_path: Path) -> None:
    src = tmp_path / "sweep.jsonl"
    dst = tmp_path / "candidates.jsonl"
    rows = [_make_row("c1", pnl=100)]
    _write_jsonl(src, rows)

    total, _ = _extract_top_candidates(
        src, dst, max_rank=100, modes=["pnl"]
    )
    assert total == 1

    result = _read_jsonl(dst)
    assert len(result) == 1


def test_extract_preserves_row_data(tmp_path: Path) -> None:
    """Verify that extracted rows are identical to source rows."""
    src = tmp_path / "sweep.jsonl"
    dst = tmp_path / "candidates.jsonl"
    original = _make_row("c1", pnl=123.456, trades=42, pf=2.5)
    _write_jsonl(src, [original])

    _extract_top_candidates(src, dst, max_rank=10, modes=["pnl"])

    result = _read_jsonl(dst)
    assert len(result) == 1
    assert result[0] == original


def test_extract_large_scale_memory_bounded(tmp_path: Path) -> None:
    """Simulate a larger sweep to verify heap eviction works correctly."""
    src = tmp_path / "sweep.jsonl"
    dst = tmp_path / "candidates.jsonl"

    rows = [_make_row(f"c{i}", pnl=float(i), dd=1.0 / (i + 1)) for i in range(500)]
    _write_jsonl(src, rows)

    total, _ = _extract_top_candidates(
        src, dst, max_rank=10, modes=["pnl", "dd"]
    )
    assert total == 500

    result = _read_jsonl(dst)
    ids = {r["config_id"] for r in result}

    # Top 10 by pnl should be c499..c490
    for i in range(490, 500):
        assert f"c{i}" in ids, f"c{i} should be in top-10 by pnl"

    # Top 10 by dd (lowest dd = highest score) should be c499..c490
    # (dd = 1/(i+1), so higher i = lower dd = better)
    # These overlap with pnl top-10, so dedup means fewer total rows
    assert len(result) <= 20  # max 10 per mode, deduped
