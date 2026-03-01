from __future__ import annotations

from pathlib import Path

import factory_run


def test_resolve_path_for_backtester_resolves_repo_root_relative_paths() -> None:
    p = factory_run._resolve_path_for_backtester("config/strategy_overrides.yaml")
    assert p is not None
    pp = Path(p)
    assert pp.is_absolute()
    assert pp.exists()
    assert pp.name == "strategy_overrides.yaml"


def test_resolve_path_for_backtester_resolves_backtester_relative_sweep_specs() -> None:
    p = factory_run._resolve_path_for_backtester("sweeps/smoke.yaml")
    assert p is not None
    pp = Path(p)
    assert pp.is_absolute()
    assert pp.exists()
    assert pp.name == "smoke.yaml"


def test_normalise_candles_db_dir_for_backtester_expands_to_candle_db_files(tmp_path) -> None:
    c1 = tmp_path / "candles_1m.db"
    c2 = tmp_path / "candles_5m.db"
    funding = tmp_path / "funding_rates.db"
    c1.write_text("", encoding="utf-8")
    c2.write_text("", encoding="utf-8")
    funding.write_text("", encoding="utf-8")

    out = factory_run._normalise_candles_db_arg_for_backtester(str(tmp_path))
    assert out is not None
    parts = out.split(",")
    assert str(c1.resolve()) in parts
    assert str(c2.resolve()) in parts
    assert str(funding.resolve()) not in parts
