from __future__ import annotations

import os
import time

from engine.strategy_manager import StrategyManager


def test_check_yaml_path_rejects_world_writable_file(tmp_path) -> None:
    yaml_path = tmp_path / "strategy.yaml"
    yaml_path.write_text("global: {}\n", encoding="utf-8")
    yaml_path.chmod(0o666)

    assert StrategyManager._check_yaml_path(str(yaml_path)) is False


def test_check_yaml_path_accepts_owner_writable_file(tmp_path) -> None:
    yaml_path = tmp_path / "strategy.yaml"
    yaml_path.write_text("global: {}\n", encoding="utf-8")
    yaml_path.chmod(0o600)

    assert StrategyManager._check_yaml_path(str(yaml_path)) is True


def test_world_writable_reload_keeps_last_known_good_config(tmp_path) -> None:
    yaml_path = tmp_path / "strategy.yaml"
    yaml_path.write_text("global:\n  trade:\n    leverage: 7\n", encoding="utf-8")
    yaml_path.chmod(0o600)

    manager = StrategyManager.bootstrap(
        defaults={"trade": {"leverage": 1.0}, "indicators": {}, "filters": {}, "thresholds": {}},
        yaml_path=str(yaml_path),
        changelog_path=None,
    )
    assert float(manager.get_config("BTC").get("trade", {}).get("leverage", 0.0)) == 7.0

    # Unsafe permissions: reload must be skipped, preserving last-known-good overrides.
    yaml_path.write_text("global:\n  trade:\n    leverage: 9\n", encoding="utf-8")
    yaml_path.chmod(0o666)
    future_ts = time.time() + 1.0
    os.utime(yaml_path, (future_ts, future_ts))
    manager.maybe_reload()
    assert float(manager.get_config("BTC").get("trade", {}).get("leverage", 0.0)) == 7.0

    # After returning to safe permissions and changing content, reload should proceed.
    yaml_path.chmod(0o600)
    yaml_path.write_text("global:\n  trade:\n    leverage: 9\n", encoding="utf-8")
    future_ts = time.time() + 2.0
    os.utime(yaml_path, (future_ts, future_ts))
    manager.maybe_reload()
    assert float(manager.get_config("BTC").get("trade", {}).get("leverage", 0.0)) == 9.0
