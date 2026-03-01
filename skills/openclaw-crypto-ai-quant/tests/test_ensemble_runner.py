from pathlib import Path

import yaml

from tools.ensemble_runner import build_launch_plan


def test_build_launch_plan_writes_derived_yaml(tmp_path: Path):
    # Base strategy YAML
    base = tmp_path / "base.yaml"
    base.write_text(
        yaml.safe_dump(
            {
                "global": {
                    "trade": {"allocation_pct": 0.03, "slippage_bps": 10.0, "max_open_positions": 20, "min_atr_pct": 0.003, "min_notional_usd": 10.0, "leverage": 3.0, "sl_atr_mult": 2.0, "tp_atr_mult": 4.0, "max_total_margin_pct": 0.6, "bump_to_min_notional": False},
                    "indicators": {"adx_window": 14, "ema_fast_window": 20, "ema_slow_window": 50, "bb_window": 20, "atr_window": 14},
                    "thresholds": {"entry": {"min_adx": 22.0}},
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    spec_path = tmp_path / "ensemble.yaml"
    spec_path.write_text(
        yaml.safe_dump(
            {
                "strategies": [
                    {"name": "s1", "strategy_yaml": str(base), "overrides": {"trade.size_multiplier": 0.5}, "env": {"AI_QUANT_STRATEGY_MODE": "primary"}},
                    {"name": "s2", "strategy_yaml": str(base), "overrides": {"trade.size_multiplier": 0.25}, "env": {}},
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    plans = build_launch_plan(spec_path=spec_path, out_dir=tmp_path / "out", mode="dry_live", daemon_argv=["python3", "-m", "engine.daemon"])
    assert [p.name for p in plans] == ["s1", "s2"]

    for p in plans:
        assert p.derived_yaml_path.exists()
        obj = yaml.safe_load(p.derived_yaml_path.read_text(encoding="utf-8"))
        assert obj["global"]["trade"]["size_multiplier"] in {0.5, 0.25}
        assert p.env["AI_QUANT_MODE"] == "dry_live"
        assert p.env["AI_QUANT_STRATEGY_YAML"] == str(p.derived_yaml_path)

