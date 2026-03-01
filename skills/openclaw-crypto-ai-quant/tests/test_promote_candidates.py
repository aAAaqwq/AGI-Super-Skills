"""Tests for _promote_candidates() — the 20→3 candidate promotion logic."""
from __future__ import annotations

from pathlib import Path

from factory_run import _promote_candidates


def _make_candidate(
    *,
    config_id: str,
    total_pnl: float,
    max_drawdown_pct: float,
    profit_factor: float,
    config_name: str | None = None,
) -> dict[str, object]:
    """Return a minimal mock candidate dict."""
    return {
        "config_id": config_id,
        "total_pnl": total_pnl,
        "max_drawdown_pct": max_drawdown_pct,
        "profit_factor": profit_factor,
        "config_path": "",  # will be patched per-test
        "path": "",
    }


def _write_dummy_configs(tmp_path: Path, candidates: list[dict[str, object]]) -> None:
    """Write dummy YAML config files and patch config_path on each candidate."""
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    for c in candidates:
        name = f"{c['config_id']}.yaml"
        cfg = configs_dir / name
        cfg.write_text(f"# config {c['config_id']}\nid: {c['config_id']}\n", encoding="utf-8")
        c["config_path"] = str(cfg)


# -----------------------------------------------------------------------
# Role assignment
# -----------------------------------------------------------------------


def test_primary_is_best_balanced_score(tmp_path: Path) -> None:
    """PRIMARY = highest PnL × (1 - max_dd) × profit_factor."""
    candidates = [
        _make_candidate(config_id="A", total_pnl=100, max_drawdown_pct=0.5, profit_factor=2.0),
        # B: 200 * (1 - 0.1) * 3.0 = 540  ← should be primary
        _make_candidate(config_id="B", total_pnl=200, max_drawdown_pct=0.1, profit_factor=3.0),
        _make_candidate(config_id="C", total_pnl=50, max_drawdown_pct=0.05, profit_factor=1.5),
    ]
    _write_dummy_configs(tmp_path, candidates)

    result = _promote_candidates(candidates, run_dir=tmp_path, promote_count=3)

    assert not result["skipped"]
    assert result["roles"]["primary"]["config_id"] == "B"


def test_fallback_is_lowest_dd_positive_pnl(tmp_path: Path) -> None:
    """FALLBACK = lowest max_drawdown_pct among positive-PnL candidates."""
    candidates = [
        _make_candidate(config_id="A", total_pnl=100, max_drawdown_pct=0.30, profit_factor=2.0),
        _make_candidate(config_id="B", total_pnl=200, max_drawdown_pct=0.20, profit_factor=3.0),
        # C has lowest DD
        _make_candidate(config_id="C", total_pnl=50, max_drawdown_pct=0.02, profit_factor=1.5),
    ]
    _write_dummy_configs(tmp_path, candidates)

    result = _promote_candidates(candidates, run_dir=tmp_path, promote_count=3)

    assert result["roles"]["fallback"]["config_id"] == "C"


def test_conservative_is_absolute_lowest_dd(tmp_path: Path) -> None:
    """CONSERVATIVE = lowest max_drawdown_pct with positive PnL."""
    candidates = [
        _make_candidate(config_id="A", total_pnl=100, max_drawdown_pct=0.30, profit_factor=2.0),
        _make_candidate(config_id="B", total_pnl=200, max_drawdown_pct=0.10, profit_factor=3.0),
        # C has lowest DD and positive PnL
        _make_candidate(config_id="C", total_pnl=10, max_drawdown_pct=0.01, profit_factor=1.1),
    ]
    _write_dummy_configs(tmp_path, candidates)

    result = _promote_candidates(candidates, run_dir=tmp_path, promote_count=3)

    assert result["roles"]["conservative"]["config_id"] == "C"


def test_negative_pnl_candidates_excluded(tmp_path: Path) -> None:
    """Candidates with non-positive PnL should be excluded from all roles."""
    candidates = [
        _make_candidate(config_id="bad", total_pnl=-50, max_drawdown_pct=0.01, profit_factor=0.5),
        _make_candidate(config_id="good", total_pnl=10, max_drawdown_pct=0.05, profit_factor=1.2),
    ]
    _write_dummy_configs(tmp_path, candidates)

    result = _promote_candidates(candidates, run_dir=tmp_path, promote_count=3)

    assert not result["skipped"]
    for role_info in result["roles"].values():
        assert role_info["config_id"] == "good"


# -----------------------------------------------------------------------
# YAML file output
# -----------------------------------------------------------------------


def test_yaml_files_written(tmp_path: Path) -> None:
    candidates = [
        _make_candidate(config_id="A", total_pnl=100, max_drawdown_pct=0.10, profit_factor=2.0),
        _make_candidate(config_id="B", total_pnl=200, max_drawdown_pct=0.20, profit_factor=3.0),
        _make_candidate(config_id="C", total_pnl=50, max_drawdown_pct=0.05, profit_factor=1.5),
    ]
    _write_dummy_configs(tmp_path, candidates)

    result = _promote_candidates(candidates, run_dir=tmp_path, promote_count=3)

    promote_dir = tmp_path / "promoted_configs"
    assert promote_dir.is_dir()

    for role in ("primary", "fallback", "conservative"):
        yaml_path = promote_dir / f"{role}.yaml"
        assert yaml_path.is_file(), f"{role}.yaml not found"
        content = yaml_path.read_text(encoding="utf-8")
        assert content.strip()  # non-empty

    assert result["promoted_count"] == 3


def test_custom_promote_dir(tmp_path: Path) -> None:
    candidates = [
        _make_candidate(config_id="X", total_pnl=50, max_drawdown_pct=0.05, profit_factor=1.5),
    ]
    _write_dummy_configs(tmp_path, candidates)

    _promote_candidates(candidates, run_dir=tmp_path, promote_dir="my_promoted", promote_count=3)

    assert (tmp_path / "my_promoted" / "primary.yaml").is_file()


# -----------------------------------------------------------------------
# Skip / edge-cases
# -----------------------------------------------------------------------


def test_promote_count_zero_skips(tmp_path: Path) -> None:
    candidates = [
        _make_candidate(config_id="A", total_pnl=100, max_drawdown_pct=0.10, profit_factor=2.0),
    ]
    _write_dummy_configs(tmp_path, candidates)

    result = _promote_candidates(candidates, run_dir=tmp_path, promote_count=0)

    assert result["skipped"] is True
    assert not (tmp_path / "promoted_configs").exists()


def test_no_positive_pnl_skips(tmp_path: Path) -> None:
    candidates = [
        _make_candidate(config_id="A", total_pnl=-10, max_drawdown_pct=0.10, profit_factor=0.5),
        _make_candidate(config_id="B", total_pnl=0, max_drawdown_pct=0.05, profit_factor=0.0),
    ]
    _write_dummy_configs(tmp_path, candidates)

    result = _promote_candidates(candidates, run_dir=tmp_path, promote_count=3)

    assert result["skipped"] is True


def test_empty_candidates_skips(tmp_path: Path) -> None:
    result = _promote_candidates([], run_dir=tmp_path, promote_count=3)
    assert result["skipped"] is True


def test_single_candidate_fills_all_roles(tmp_path: Path) -> None:
    """When there's only one positive-PnL candidate, it fills all three roles."""
    candidates = [
        _make_candidate(config_id="solo", total_pnl=100, max_drawdown_pct=0.10, profit_factor=2.0),
    ]
    _write_dummy_configs(tmp_path, candidates)

    result = _promote_candidates(candidates, run_dir=tmp_path, promote_count=3)

    assert not result["skipped"]
    assert result["promoted_count"] == 3
    for role in ("primary", "fallback", "conservative"):
        assert result["roles"][role]["config_id"] == "solo"


def test_promote_count_limits_output(tmp_path: Path) -> None:
    """promote_count=1 should only write the primary role."""
    candidates = [
        _make_candidate(config_id="A", total_pnl=100, max_drawdown_pct=0.10, profit_factor=2.0),
        _make_candidate(config_id="B", total_pnl=200, max_drawdown_pct=0.20, profit_factor=3.0),
    ]
    _write_dummy_configs(tmp_path, candidates)

    result = _promote_candidates(candidates, run_dir=tmp_path, promote_count=1)

    assert result["promoted_count"] == 1
    assert "primary" in result["roles"]
    assert "fallback" not in result["roles"]


def test_promotion_metadata_fields(tmp_path: Path) -> None:
    """Verify that promotion metadata includes expected fields per role."""
    candidates = [
        _make_candidate(config_id="A", total_pnl=100, max_drawdown_pct=0.10, profit_factor=2.0),
    ]
    _write_dummy_configs(tmp_path, candidates)

    result = _promote_candidates(candidates, run_dir=tmp_path, promote_count=3)

    for role_name, role_info in result["roles"].items():
        assert "config_id" in role_info
        assert "promoted_path" in role_info
        assert "total_pnl" in role_info
        assert "max_drawdown_pct" in role_info
        assert "profit_factor" in role_info
        assert "balanced_score" in role_info
