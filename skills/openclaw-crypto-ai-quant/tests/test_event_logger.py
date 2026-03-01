import json
import threading
from pathlib import Path

from tools.config_id import config_id_from_yaml_text


def test_event_logger_writes_jsonl_and_includes_config_id(tmp_path, monkeypatch):
    cfg = tmp_path / "strategy_overrides.yaml"
    yaml_text = "global:\n  hello: world\n"
    cfg.write_text(yaml_text, encoding="utf-8")

    out = tmp_path / "events.jsonl"

    monkeypatch.setenv("AI_QUANT_STRATEGY_YAML", str(cfg))
    monkeypatch.setenv("AI_QUANT_EVENT_LOG", "1")
    monkeypatch.setenv("AI_QUANT_EVENT_LOG_PATH", str(out))
    monkeypatch.setenv("AI_QUANT_RUN_ID", "run_123")
    monkeypatch.setenv("AI_QUANT_MODE", "paper")

    from engine.event_logger import _close_for_tests, emit_event

    emit_event(kind="unit_test", symbol="btc", data={"x": 1})
    _close_for_tests()

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    evt = json.loads(lines[0])

    assert evt["schema"] == "aiq_event_v1"
    assert evt["kind"] == "unit_test"
    assert evt["symbol"] == "BTC"
    assert evt["run_id"] == "run_123"
    assert evt["config_id"] == config_id_from_yaml_text(yaml_text)


def test_event_logger_logs_error_when_parent_mkdir_fails(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(threading.Thread, "start", lambda self: None)

    from engine import event_logger as event_logger_mod

    sink = event_logger_mod._JsonlEventSink(path=tmp_path / "events" / "events.jsonl")
    target_parent = sink._path.parent  # noqa: SLF001
    orig_mkdir = Path.mkdir
    fail_once = {"left": 1}

    def _mkdir_maybe_fail(self, *args, **kwargs):  # noqa: ANN001
        if self == target_parent and fail_once["left"] > 0:
            fail_once["left"] -= 1
            raise OSError("mkdir denied")
        return orig_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _mkdir_maybe_fail)

    with caplog.at_level("ERROR"):
        sink.emit({"kind": "unit", "ok": True})
        sink._stop.set()  # noqa: SLF001
        sink._run()  # noqa: SLF001

    assert any("failed to create parent directory" in rec.message for rec in caplog.records)
    lines = sink._path.read_text(encoding="utf-8").splitlines()  # noqa: SLF001
    assert len(lines) == 1
