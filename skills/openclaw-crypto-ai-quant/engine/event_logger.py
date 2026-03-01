from __future__ import annotations

import atexit
import hashlib
import json
import logging
import os
import queue
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


AIQ_ROOT = Path(__file__).resolve().parents[1]


def _utc_iso(ts_ms: int) -> str:
    try:
        return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _env_str(name: str, default: str = "") -> str:
    raw = os.getenv(name)
    return default if raw is None else str(raw)


def _enabled() -> bool:
    return _env_str("AI_QUANT_EVENT_LOG", "1").strip().lower() not in {"0", "false", "no", "off"}


def _default_event_log_path() -> Path:
    p = _env_str("AI_QUANT_EVENT_LOG_PATH", "").strip()
    if p:
        return Path(p).expanduser().resolve()
    d = _env_str("AI_QUANT_EVENT_LOG_DIR", "").strip()
    if d:
        return (Path(d).expanduser().resolve() / "events.jsonl").resolve()
    return (AIQ_ROOT / "artifacts" / "events" / "events.jsonl").resolve()


def _strategy_yaml_path() -> Path:
    p = _env_str("AI_QUANT_STRATEGY_YAML", "").strip()
    if p:
        return Path(p).expanduser().resolve()
    return (AIQ_ROOT / "config" / "strategy_overrides.yaml").resolve()


def _normalise_obj(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _normalise_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalise_obj(v) for v in obj]
    if isinstance(obj, tuple):
        return [_normalise_obj(v) for v in obj]
    return str(obj)


def _config_id_from_yaml_text(text: str) -> str:
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError("Expected YAML root mapping")
    payload = _normalise_obj(data)
    b = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


_CFG_CACHE_LOCK = threading.Lock()
_CFG_CACHE: dict[str, Any] = {"mtime_ns": None, "config_id": ""}


def _current_config_id() -> str:
    path = _strategy_yaml_path()
    try:
        st = path.stat()
    except Exception:
        return ""
    mtime_ns = int(st.st_mtime_ns)
    with _CFG_CACHE_LOCK:
        if _CFG_CACHE.get("mtime_ns") == mtime_ns:
            return str(_CFG_CACHE.get("config_id", "") or "")
    try:
        text = path.read_text(encoding="utf-8")
        cid = _config_id_from_yaml_text(text)
    except Exception:
        cid = ""
    with _CFG_CACHE_LOCK:
        _CFG_CACHE["mtime_ns"] = mtime_ns
        _CFG_CACHE["config_id"] = cid
    return str(cid)


def current_config_id() -> str:
    """Return the current config_id (sha256 of the normalised strategy YAML)."""
    try:
        return _current_config_id()
    except Exception:
        return ""


@dataclass(frozen=True)
class _EventItem:
    line: str


class _JsonlEventSink:
    def __init__(self, *, path: Path):
        self._path = Path(path).expanduser().resolve()

        self._max_queue = max(1000, int(float(_env_str("AI_QUANT_EVENT_LOG_MAX_QUEUE", "10000") or 10000)))
        self._flush_every_s = max(0.05, float(_env_str("AI_QUANT_EVENT_LOG_FLUSH_SECS", "0.25") or 0.25))
        self._batch_size = max(10, int(float(_env_str("AI_QUANT_EVENT_LOG_BATCH", "200") or 200)))

        self._q: queue.Queue[_EventItem] = queue.Queue(maxsize=self._max_queue)
        self._stop = threading.Event()

        self._t = threading.Thread(target=self._run, name="jsonl_event_sink", daemon=True)
        self._t.start()
        atexit.register(self.close)

    def emit(self, payload: dict[str, Any]) -> None:
        try:
            line = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        except Exception as e:
            logger.warning("event logger JSON serialization failed: %s", e, exc_info=True)
            return
        try:
            self._q.put_nowait(_EventItem(line=line))
        except queue.Full:
            return

    def close(self) -> None:
        if self._stop.is_set():
            return
        self._stop.set()
        with suppress(Exception):
            self._t.join(timeout=1.5)

    def _run(self) -> None:
        backoff_s = 0.05
        pending: list[_EventItem] = []
        f = None

        while True:
            try:
                if self._stop.is_set() and self._q.empty() and not pending:
                    break

                if not pending:
                    try:
                        item = self._q.get(timeout=self._flush_every_s)
                        pending.append(item)
                    except queue.Empty:
                        continue

                while len(pending) < self._batch_size:
                    try:
                        pending.append(self._q.get_nowait())
                    except queue.Empty:
                        break

                if f is None:
                    try:
                        self._path.parent.mkdir(parents=True, exist_ok=True)
                        f = self._path.open("a", encoding="utf-8")
                    except Exception as exc:
                        logger.error(
                            "event logger failed to create parent directory %s: %s",
                            self._path.parent,
                            exc,
                        )
                        time.sleep(backoff_s)
                        backoff_s = min(2.0, backoff_s * 1.8)
                        continue

                for it in pending:
                    f.write(it.line + "\n")
                f.flush()
                pending.clear()
                backoff_s = 0.05

            except Exception:
                with suppress(Exception):
                    if f is not None:
                        f.close()
                f = None
                pending.clear()
                time.sleep(backoff_s)
                backoff_s = min(2.0, backoff_s * 1.8)

        with suppress(Exception):
            if f is not None:
                f.close()


_SINK_LOCK = threading.Lock()
_SINK: _JsonlEventSink | None = None


def _get_sink() -> _JsonlEventSink | None:
    global _SINK
    if not _enabled():
        return None
    with _SINK_LOCK:
        if _SINK is not None:
            return _SINK
        _SINK = _JsonlEventSink(path=_default_event_log_path())
        return _SINK


def emit_event(*, kind: str, symbol: str | None = None, data: dict[str, Any] | None = None) -> None:
    """Best-effort structured event emission.

    This must never raise, and it must not block the trading loop.
    """
    try:
        sink = _get_sink()
        if sink is None:
            return

        ts_ms = int(time.time() * 1000)
        payload: dict[str, Any] = {
            "schema": "aiq_event_v1",
            "ts_ms": ts_ms,
            "ts": _utc_iso(ts_ms),
            "pid": int(os.getpid()),
            "mode": _env_str("AI_QUANT_MODE", "paper").strip().lower() or "paper",
            "run_id": _env_str("AI_QUANT_RUN_ID", "").strip(),
            "config_id": _current_config_id(),
            "kind": str(kind),
        }
        sym = (symbol or "").strip().upper()
        if sym:
            payload["symbol"] = sym
        if data:
            payload["data"] = data
        sink.emit(payload)
    except Exception:
        return


def _close_for_tests() -> None:
    """Close the global sink (used by unit tests)."""
    global _SINK
    with _SINK_LOCK:
        if _SINK is None:
            return
        _SINK.close()
        _SINK = None
