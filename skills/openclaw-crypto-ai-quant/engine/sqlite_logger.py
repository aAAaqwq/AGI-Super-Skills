from __future__ import annotations

import atexit
import io
import os
import queue
import sqlite3
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


def _utc_iso(ts_ms: int) -> str:
    try:
        return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return int(default)
    try:
        return int(str(raw).strip())
    except Exception:
        return int(default)


def _infer_level(line: str, *, stream: str) -> str:
    s = (line or "").lstrip()
    if not s:
        return "info"
    if s.startswith("🔥") or "traceback (most recent call last)" in s.lower():
        return "error"
    if s.startswith("⚠️") or s.startswith("❌"):
        return "warning"
    if stream == "stderr":
        return "warning"
    return "info"


def _ensure_runtime_logs_schema(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS runtime_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_ms INTEGER NOT NULL,
            ts TEXT NOT NULL,
            pid INTEGER,
            mode TEXT,
            stream TEXT,
            level TEXT,
            message TEXT
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_runtime_logs_ts_ms ON runtime_logs(ts_ms)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_runtime_logs_mode_ts_ms ON runtime_logs(mode, ts_ms)")
    con.commit()


@dataclass(frozen=True)
class _LogItem:
    ts_ms: int
    stream: str
    level: str
    message: str


class _SqliteLogSink:
    def __init__(self, *, db_path: str, mode: str | None, pid: int):
        self._db_path = str(db_path)
        self._mode = (mode or "").strip().lower() or None
        self._pid = int(pid)

        self._max_queue = max(1000, _env_int("AI_QUANT_SQLITE_LOG_MAX_QUEUE", 10_000))
        self._max_chars = max(200, _env_int("AI_QUANT_SQLITE_LOG_MAX_CHARS", 8_000))
        self._flush_every_s = max(0.05, float(os.getenv("AI_QUANT_SQLITE_LOG_FLUSH_SECS", "0.25") or 0.25))
        self._batch_size = max(10, _env_int("AI_QUANT_SQLITE_LOG_BATCH", 200))

        self._q: queue.Queue[_LogItem] = queue.Queue(maxsize=self._max_queue)
        self._stop = threading.Event()

        # Create the DB + schema synchronously so readers never observe a DB
        # file without the expected tables (reduces test/runtime races).
        with suppress(sqlite3.Error, OSError):
            con = self._open_con()
            con.close()

        self._t = threading.Thread(target=self._run, name="sqlite_log_sink", daemon=True)
        self._t.start()
        atexit.register(self.close)

    def emit(self, *, stream: str, message: str) -> None:
        msg = (message or "").rstrip("\n")
        if not msg.strip():
            return
        if len(msg) > self._max_chars:
            msg = msg[: self._max_chars] + "…(truncated)"
        ts_ms = int(time.time() * 1000)
        item = _LogItem(
            ts_ms=ts_ms,
            stream=str(stream or "stdout"),
            level=_infer_level(msg, stream=str(stream or "stdout")),
            message=msg,
        )
        try:
            self._q.put_nowait(item)
        except queue.Full:
            return

    def close(self) -> None:
        if self._stop.is_set():
            return
        self._stop.set()
        with suppress(RuntimeError):
            self._t.join(timeout=1.5)

    def _open_con(self) -> sqlite3.Connection:
        db_p = Path(self._db_path).expanduser().resolve()
        db_p.parent.mkdir(parents=True, exist_ok=True)
        timeout_s = max(0.1, min(5.0, float(os.getenv("AI_QUANT_SQLITE_LOG_TIMEOUT_S", "0.5") or 0.5)))
        con = sqlite3.connect(str(db_p), timeout=timeout_s)
        with suppress(sqlite3.Error):
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA synchronous=NORMAL")
        _ensure_runtime_logs_schema(con)
        try:
            import logging as _logging
            import os as _os

            _os.chmod(str(db_p), 0o600)
        except OSError as _perm_exc:
            _logging.getLogger(__name__).warning("Failed to set DB permissions on %s: %s", db_p, _perm_exc)
        return con

    def _run(self) -> None:
        con: sqlite3.Connection | None = None
        backoff_s = 0.05
        pending: list[_LogItem] = []

        while True:
            try:
                if self._stop.is_set() and self._q.empty() and not pending:
                    break

                # Collect a batch.
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

                if con is None:
                    con = self._open_con()

                rows = [
                    (it.ts_ms, _utc_iso(it.ts_ms), self._pid, self._mode, it.stream, it.level, it.message)
                    for it in pending
                ]
                con.executemany(
                    "INSERT INTO runtime_logs (ts_ms, ts, pid, mode, stream, level, message) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )
                con.commit()
                pending.clear()
                backoff_s = 0.05

            except Exception:
                # Best-effort. Never block the main trading loop.
                with suppress(sqlite3.Error, AttributeError):
                    con.close()  # type: ignore[union-attr]
                con = None
                pending.clear()
                time.sleep(backoff_s)
                backoff_s = min(2.0, backoff_s * 1.8)

        with suppress(sqlite3.Error, AttributeError):
            con.close()  # type: ignore[union-attr]


class _LineBufferingWriter(io.TextIOBase):
    def __init__(self, *, stream: TextIO, sink: _SqliteLogSink, stream_name: str):
        self._stream = stream
        self._sink = sink
        self._stream_name = stream_name
        self._buf = ""

    @property
    def encoding(self):  # type: ignore[override]
        return getattr(self._stream, "encoding", "utf-8")

    @property
    def errors(self):  # type: ignore[override]
        return getattr(self._stream, "errors", "replace")

    def isatty(self) -> bool:  # type: ignore[override]
        with suppress(OSError, ValueError, RuntimeError):
            return bool(self._stream.isatty())
        return False

    def write(self, s: str) -> int:  # type: ignore[override]
        try:
            self._stream.write(s)
        except BrokenPipeError:
            # Legitimate when stdout/stderr pipe consumer exits early.
            pass
        except Exception as exc:
            try:
                self._sink.emit(
                    stream="stderr",
                    message=(
                        "sqlite_logger stream write failed: "
                        f"{exc.__class__.__name__}: {exc}"
                    ),
                )
            except Exception:
                pass

        with suppress(TypeError, ValueError):
            self._buf += str(s)
            if "\n" not in self._buf:
                return len(s)
            parts = self._buf.split("\n")
            self._buf = parts.pop()  # trailing partial
            for ln in parts:
                self._sink.emit(stream=self._stream_name, message=ln)
        return len(s)

    def flush(self) -> None:  # type: ignore[override]
        with suppress(OSError, ValueError, RuntimeError):
            self._stream.flush()


def install_sqlite_stdio_logger(*, db_path: str, mode: str | None = None) -> _SqliteLogSink | None:
    """Tee stdout/stderr into SQLite runtime_logs.

    Safe-by-default: failures are swallowed and never crash the daemon.
    """
    enabled = os.getenv("AI_QUANT_SQLITE_LOG", "1").strip().lower() not in {"0", "false", "no", "off"}
    if not enabled:
        return None

    sink = _SqliteLogSink(db_path=db_path, mode=mode, pid=os.getpid())
    try:
        import sys

        sys.stdout = _LineBufferingWriter(stream=sys.stdout, sink=sink, stream_name="stdout")  # type: ignore[assignment]
        sys.stderr = _LineBufferingWriter(stream=sys.stderr, sink=sink, stream_name="stderr")  # type: ignore[assignment]
    except Exception:
        sink.close()
        return None
    return sink
