import json
import sqlite3
from types import SimpleNamespace

from tools.config_id import config_id_from_yaml_text
import tools.paper_deploy as paper_deploy
from tools.paper_deploy import deploy_paper_config


def _init_registry_db(path, *, config_id, yaml_text):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE IF NOT EXISTS configs (config_id TEXT PRIMARY KEY, yaml_text TEXT NOT NULL)"
        )
        con.execute(
            "INSERT OR REPLACE INTO configs (config_id, yaml_text) VALUES (?, ?)",
            (str(config_id), str(yaml_text)),
        )
        con.commit()
    finally:
        con.close()


def _init_target_db(path, *, balance):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, balance REAL)")
        con.execute("INSERT INTO trades (balance) VALUES (?)", (float(balance),))
        con.commit()
    finally:
        con.close()


def test_paper_deploy_writes_yaml_and_deploy_event(tmp_path):
    yaml_text = (
        "global:\n"
        "  trade:\n"
        "    allocation_pct: 0.20\n"
        "    leverage: 3.0\n"
        "    leverage_low: 1.0\n"
        "    leverage_medium: 3.0\n"
        "    leverage_high: 5.0\n"
        "    sl_atr_mult: 2.0\n"
        "    tp_atr_mult: 6.0\n"
        "    slippage_bps: 10.0\n"
        "    max_open_positions: 20\n"
        "    max_entry_orders_per_loop: 6\n"
        "    max_total_margin_pct: 0.60\n"
        "    min_notional_usd: 10.0\n"
        "    min_atr_pct: 0.003\n"
        "    bump_to_min_notional: true\n"
        "  indicators:\n"
        "    adx_window: 14\n"
        "    ema_fast_window: 20\n"
        "    ema_slow_window: 50\n"
        "    bb_window: 20\n"
        "    atr_window: 14\n"
        "  thresholds:\n"
        "    entry:\n"
        "      min_adx: 22.0\n"
        "  engine:\n"
        "    interval: 1h\n"
    )
    cid = config_id_from_yaml_text(yaml_text)

    artifacts_dir = tmp_path / "artifacts"
    registry_db = artifacts_dir / "registry" / "registry.sqlite"
    _init_registry_db(registry_db, config_id=cid, yaml_text=yaml_text)

    target_yaml = tmp_path / "strategy_overrides.yaml"
    target_yaml.write_text("global:\\n  engine:\\n    interval: 30m\\n", encoding="utf-8")

    out_dir = tmp_path / "deploy_out"
    deploy_dir = deploy_paper_config(
        config_id=cid,
        artifacts_dir=artifacts_dir,
        yaml_path=target_yaml,
        out_dir=out_dir,
        reason="unit test",
        restart="never",
        service="does-not-matter",
        dry_run=False,
        validate=True,
    )

    assert deploy_dir.exists()
    assert target_yaml.read_text(encoding="utf-8") == yaml_text

    event_path = deploy_dir / "deploy_event.json"
    assert event_path.exists()
    obj = json.loads(event_path.read_text(encoding="utf-8"))
    assert obj["what"]["config_id"] == cid
    assert obj["why"]["reason"] == "unit test"


def test_paper_deploy_dry_run_does_not_modify_yaml(tmp_path):
    yaml_text = (
        "global:\n"
        "  trade:\n"
        "    allocation_pct: 0.20\n"
        "    leverage: 3.0\n"
        "    leverage_low: 1.0\n"
        "    leverage_medium: 3.0\n"
        "    leverage_high: 5.0\n"
        "    sl_atr_mult: 2.0\n"
        "    tp_atr_mult: 6.0\n"
        "    slippage_bps: 10.0\n"
        "    max_open_positions: 20\n"
        "    max_entry_orders_per_loop: 6\n"
        "    max_total_margin_pct: 0.60\n"
        "    min_notional_usd: 10.0\n"
        "    min_atr_pct: 0.003\n"
        "    bump_to_min_notional: true\n"
        "  indicators:\n"
        "    adx_window: 14\n"
        "    ema_fast_window: 20\n"
        "    ema_slow_window: 50\n"
        "    bb_window: 20\n"
        "    atr_window: 14\n"
        "  thresholds:\n"
        "    entry:\n"
        "      min_adx: 22.0\n"
        "  engine:\n"
        "    interval: 1h\n"
    )
    cid = config_id_from_yaml_text(yaml_text)

    artifacts_dir = tmp_path / "artifacts"
    registry_db = artifacts_dir / "registry" / "registry.sqlite"
    _init_registry_db(registry_db, config_id=cid, yaml_text=yaml_text)

    target_yaml = tmp_path / "strategy_overrides.yaml"
    original = "global:\\n  engine:\\n    interval: 30m\\n"
    target_yaml.write_text(original, encoding="utf-8")

    out_dir = tmp_path / "deploy_out"
    deploy_paper_config(
        config_id=cid,
        artifacts_dir=artifacts_dir,
        yaml_path=target_yaml,
        out_dir=out_dir,
        reason="dry run",
        restart="never",
        service="does-not-matter",
        dry_run=True,
        validate=True,
    )

    assert target_yaml.read_text(encoding="utf-8") == original


def test_paper_deploy_mirrors_state_on_config_change_without_interval_restart(tmp_path, monkeypatch):
    yaml_text = (
        "global:\n"
        "  trade:\n"
        "    allocation_pct: 0.20\n"
        "    leverage: 3.0\n"
        "    leverage_low: 1.0\n"
        "    leverage_medium: 3.0\n"
        "    leverage_high: 5.0\n"
        "    sl_atr_mult: 2.0\n"
        "    tp_atr_mult: 6.0\n"
        "    slippage_bps: 10.0\n"
        "    max_open_positions: 20\n"
        "    max_entry_orders_per_loop: 6\n"
        "    max_total_margin_pct: 0.60\n"
        "    min_notional_usd: 10.0\n"
        "    min_atr_pct: 0.003\n"
        "    bump_to_min_notional: true\n"
        "  indicators:\n"
        "    adx_window: 14\n"
        "    ema_fast_window: 20\n"
        "    ema_slow_window: 50\n"
        "    bb_window: 20\n"
        "    atr_window: 14\n"
        "  thresholds:\n"
        "    entry:\n"
        "      min_adx: 22.0\n"
        "  engine:\n"
        "    interval: 1h\n"
    )
    cid = config_id_from_yaml_text(yaml_text)

    artifacts_dir = tmp_path / "artifacts"
    registry_db = artifacts_dir / "registry" / "registry.sqlite"
    _init_registry_db(registry_db, config_id=cid, yaml_text=yaml_text)

    target_yaml = tmp_path / "strategy_overrides.yaml"
    target_yaml.write_text("global:\\n  engine:\\n    interval: 1h\\n  trade:\\n    allocation_pct: 0.10\\n", encoding="utf-8")

    mirror_source = tmp_path / "live.db"
    mirror_source.write_text("", encoding="utf-8")
    target_db = tmp_path / "paper.db"
    _init_target_db(target_db, balance=321.0)

    restart_calls = []
    mirror_calls = []
    baseline_updates = []

    monkeypatch.setattr(paper_deploy, "_service_environment", lambda _service: {"AI_QUANT_DB_PATH": str(target_db)})
    monkeypatch.setattr(
        paper_deploy,
        "_update_service_env_file",
        lambda service, key, value: baseline_updates.append((service, key, value)),
    )
    monkeypatch.setattr(
        paper_deploy,
        "orchestrate_interval_restart",
        lambda **kwargs: restart_calls.append(kwargs) or [],
    )

    def _fake_subprocess_run(*args, **kwargs):
        mirror_calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paper_deploy.subprocess, "run", _fake_subprocess_run)

    out_dir = tmp_path / "deploy_out"
    deploy_dir = deploy_paper_config(
        config_id=cid,
        artifacts_dir=artifacts_dir,
        yaml_path=target_yaml,
        out_dir=out_dir,
        reason="mirror changed config",
        restart="never",
        service="openclaw-ai-quant-trader-v8-paper1",
        dry_run=False,
        validate=True,
        mirror_source=str(mirror_source),
        mirror_on_config_change=True,
    )

    assert deploy_dir.exists()
    assert len(mirror_calls) == 1
    assert len(restart_calls) == 1
    assert baseline_updates == [("openclaw-ai-quant-trader-v8-paper1", "AI_QUANT_NOTIFY_BASELINE_USD", "321.0")]
    event = json.loads((deploy_dir / "deploy_event.json").read_text(encoding="utf-8"))
    assert event["what"]["config_changed"] is True


def test_paper_deploy_skips_mirror_when_config_unchanged(tmp_path, monkeypatch):
    yaml_text = (
        "global:\n"
        "  trade:\n"
        "    allocation_pct: 0.20\n"
        "    leverage: 3.0\n"
        "    leverage_low: 1.0\n"
        "    leverage_medium: 3.0\n"
        "    leverage_high: 5.0\n"
        "    sl_atr_mult: 2.0\n"
        "    tp_atr_mult: 6.0\n"
        "    slippage_bps: 10.0\n"
        "    max_open_positions: 20\n"
        "    max_entry_orders_per_loop: 6\n"
        "    max_total_margin_pct: 0.60\n"
        "    min_notional_usd: 10.0\n"
        "    min_atr_pct: 0.003\n"
        "    bump_to_min_notional: true\n"
        "  indicators:\n"
        "    adx_window: 14\n"
        "    ema_fast_window: 20\n"
        "    ema_slow_window: 50\n"
        "    bb_window: 20\n"
        "    atr_window: 14\n"
        "  thresholds:\n"
        "    entry:\n"
        "      min_adx: 22.0\n"
        "  engine:\n"
        "    interval: 1h\n"
    )
    cid = config_id_from_yaml_text(yaml_text)

    artifacts_dir = tmp_path / "artifacts"
    registry_db = artifacts_dir / "registry" / "registry.sqlite"
    _init_registry_db(registry_db, config_id=cid, yaml_text=yaml_text)

    target_yaml = tmp_path / "strategy_overrides.yaml"
    target_yaml.write_text(yaml_text, encoding="utf-8")

    mirror_source = tmp_path / "live.db"
    mirror_source.write_text("", encoding="utf-8")
    target_db = tmp_path / "paper.db"
    _init_target_db(target_db, balance=654.0)

    restart_calls = []
    mirror_calls = []

    monkeypatch.setattr(paper_deploy, "_service_environment", lambda _service: {"AI_QUANT_DB_PATH": str(target_db)})
    monkeypatch.setattr(
        paper_deploy,
        "orchestrate_interval_restart",
        lambda **kwargs: restart_calls.append(kwargs) or [],
    )

    def _fake_subprocess_run(*args, **kwargs):
        mirror_calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(paper_deploy.subprocess, "run", _fake_subprocess_run)

    out_dir = tmp_path / "deploy_out"
    deploy_dir = deploy_paper_config(
        config_id=cid,
        artifacts_dir=artifacts_dir,
        yaml_path=target_yaml,
        out_dir=out_dir,
        reason="unchanged config",
        restart="never",
        service="openclaw-ai-quant-trader-v8-paper1",
        dry_run=False,
        validate=True,
        mirror_source=str(mirror_source),
        mirror_on_config_change=True,
    )

    assert deploy_dir.exists()
    assert mirror_calls == []
    assert restart_calls == []
    event = json.loads((deploy_dir / "deploy_event.json").read_text(encoding="utf-8"))
    assert event["what"]["config_changed"] is False
