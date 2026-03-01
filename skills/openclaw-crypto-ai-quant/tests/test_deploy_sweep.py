import json
from pathlib import Path

from tools import deploy_sweep


def test_no_live_guard_blocks_live_yaml_target():
    err = deploy_sweep._no_live_guard_error(
        no_live=True,
        yaml_path=deploy_sweep.YAML_PATH,
        close_live=False,
        restart=False,
    )
    assert err is not None
    assert "live YAML" in err


def test_no_live_guard_allows_non_live_yaml_target(tmp_path):
    paper_yaml = tmp_path / "paper_overrides.yaml"
    err = deploy_sweep._no_live_guard_error(
        no_live=True,
        yaml_path=str(paper_yaml),
        close_live=False,
        restart=False,
    )
    assert err is None


def test_atomic_write_text_replaces_file(tmp_path):
    path = tmp_path / "cfg.yaml"
    deploy_sweep._atomic_write_text(str(path), "a: 1\n")
    assert path.read_text(encoding="utf-8") == "a: 1\n"
    deploy_sweep._atomic_write_text(str(path), "a: 2\n")
    assert path.read_text(encoding="utf-8") == "a: 2\n"


def test_write_deploy_event_tracks_hashes(tmp_path):
    prev_text = "global:\n  trade:\n    leverage: 2.0\n"
    next_text = "global:\n  trade:\n    leverage: 3.0\n"
    out_dir = deploy_sweep._write_deploy_event(
        artifacts_dir=str(tmp_path),
        yaml_path=str(tmp_path / "paper.yaml"),
        prev_text=prev_text,
        next_text=next_text,
        selected={"total_pnl": 123.4, "total_trades": 99},
        rank=1,
        no_live=True,
    )
    event_path = Path(out_dir) / "deploy_event.json"
    assert event_path.exists()
    event = json.loads(event_path.read_text(encoding="utf-8"))
    assert event["selection"]["config_id"] == deploy_sweep.config_id_from_yaml_text(next_text)
    assert event["hashes"]["prev_yaml_sha256"] == deploy_sweep._sha256_text(prev_text)
    assert event["hashes"]["next_yaml_sha256"] == deploy_sweep._sha256_text(next_text)

