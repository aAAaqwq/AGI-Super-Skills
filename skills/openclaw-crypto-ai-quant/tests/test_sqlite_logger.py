import io
import sqlite3
import sys
import threading
import time

import engine.sqlite_logger as sl


def _wait_for(pred, *, timeout_s: float = 2.0, sleep_s: float = 0.02) -> bool:
    deadline = time.time() + float(timeout_s)
    while time.time() < deadline:
        if pred():
            return True
        time.sleep(float(sleep_s))
    return False


def test_helpers(monkeypatch):
    now_ms = int(time.time() * 1000)
    assert "T" in sl._utc_iso(now_ms)
    # Force the exception branch (overflow / out-of-range timestamp).
    assert sl._utc_iso(10**20)

    monkeypatch.delenv("AIQ_TEST_INT", raising=False)
    assert sl._env_int("AIQ_TEST_INT", 5) == 5
    monkeypatch.setenv("AIQ_TEST_INT", "7")
    assert sl._env_int("AIQ_TEST_INT", 5) == 7
    monkeypatch.setenv("AIQ_TEST_INT", "nope")
    assert sl._env_int("AIQ_TEST_INT", 5) == 5

    assert sl._infer_level("", stream="stdout") == "info"
    assert sl._infer_level("🔥 boom", stream="stdout") == "error"
    assert sl._infer_level("Traceback (most recent call last)", stream="stdout") == "error"
    assert sl._infer_level("⚠️ warn", stream="stdout") == "warning"
    assert sl._infer_level("x", stream="stderr") == "warning"
    assert sl._infer_level("x", stream="stdout") == "info"


def test_line_buffering_writer_emits_lines():
    class FakeSink:
        def __init__(self):
            self.items = []

        def emit(self, *, stream: str, message: str) -> None:
            self.items.append((stream, message))

    sink = FakeSink()
    underlying = io.StringIO()
    w = sl._LineBufferingWriter(stream=underlying, sink=sink, stream_name="stdout")

    # io.StringIO may expose encoding/errors as None; just ensure access doesn't crash.
    _ = w.encoding
    _ = w.errors

    written = w.write("hello")
    assert written == 5
    assert sink.items == []

    w.write("\nworld\n")
    assert sink.items == [("stdout", "hello"), ("stdout", "world")]
    w.flush()

    class BadStream(io.StringIO):
        def isatty(self) -> bool:
            raise RuntimeError("boom")

    w2 = sl._LineBufferingWriter(stream=BadStream(), sink=sink, stream_name="stderr")
    assert w2.isatty() is False


def test_line_buffering_writer_emits_warning_when_stream_write_fails():
    class FakeSink:
        def __init__(self):
            self.items = []

        def emit(self, *, stream: str, message: str) -> None:
            self.items.append((stream, message))

    class BadWriteStream(io.StringIO):
        def write(self, _s: str) -> int:
            raise ValueError("write failure")

    sink = FakeSink()
    w = sl._LineBufferingWriter(stream=BadWriteStream(), sink=sink, stream_name="stdout")
    w.write("hello\n")

    assert any("stream write failed" in msg for _stream, msg in sink.items)


def test_line_buffering_writer_suppresses_broken_pipe_without_warning():
    class FakeSink:
        def __init__(self):
            self.items = []

        def emit(self, *, stream: str, message: str) -> None:
            self.items.append((stream, message))

    class BrokenPipeStream(io.StringIO):
        def write(self, _s: str) -> int:
            raise BrokenPipeError("pipe closed")

    sink = FakeSink()
    w = sl._LineBufferingWriter(stream=BrokenPipeStream(), sink=sink, stream_name="stdout")
    w.write("hello\n")

    assert not any("stream write failed" in msg for _stream, msg in sink.items)


def test_sink_writes_rows_to_sqlite(tmp_path, monkeypatch):
    db_path = tmp_path / "runtime_logs.db"
    monkeypatch.setenv("AI_QUANT_SQLITE_LOG_MAX_CHARS", "200")
    monkeypatch.setenv("AI_QUANT_SQLITE_LOG_FLUSH_SECS", "0.05")
    monkeypatch.setenv("AI_QUANT_SQLITE_LOG_BATCH", "50")

    sink = sl._SqliteLogSink(db_path=str(db_path), mode="paper", pid=999)
    try:
        sink.emit(stream="stdout", message="hello\n")
        sink.emit(stream="stderr", message="⚠️ warn\n")
        sink.emit(stream="stdout", message="   \n")  # ignored
        sink.emit(stream="stdout", message="x" * 500)

        def _rows():
            if not db_path.exists():
                return []
            con = sqlite3.connect(str(db_path))
            try:
                return list(con.execute("SELECT stream, level, message FROM runtime_logs ORDER BY id"))
            finally:
                con.close()

        assert _wait_for(lambda: len(_rows()) >= 3)
        rows = _rows()
        assert rows[0][0] == "stdout"
        assert rows[0][1] == "info"
        assert rows[0][2] == "hello"

        assert rows[1][0] == "stderr"
        assert rows[1][1] == "warning"
        assert rows[1][2] == "⚠️ warn"

        assert rows[2][2].endswith("(truncated)")
    finally:
        sink.close()


def test_sink_emit_drops_when_queue_full(tmp_path, monkeypatch):
    # Prevent the background thread from draining the queue so we can deterministically
    # hit the queue.Full path in emit().
    monkeypatch.setattr(threading.Thread, "start", lambda self: None)
    monkeypatch.setenv("AI_QUANT_SQLITE_LOG_MAX_QUEUE", "1000")

    sink = sl._SqliteLogSink(db_path=str(tmp_path / "noop.db"), mode=None, pid=1)
    try:
        for _ in range(sink._max_queue):
            sink.emit(stream="stdout", message="x\n")
        assert sink._q.full()
        size_before = sink._q.qsize()
        # Queue is full; this emit should drop silently.
        sink.emit(stream="stdout", message="drop\n")
        assert sink._q.full()
        assert sink._q.qsize() == size_before
    finally:
        sink.close()
        sink.close()  # idempotent


def test_sink_run_error_path(tmp_path, monkeypatch):
    # Using a directory path as the "db file" forces sqlite3.connect to fail,
    # exercising the best-effort error/backoff path in _run().
    bad_db = tmp_path / "db_dir"
    bad_db.mkdir()

    monkeypatch.setenv("AI_QUANT_SQLITE_LOG_FLUSH_SECS", "0.05")
    sink = sl._SqliteLogSink(db_path=str(bad_db), mode="paper", pid=1)
    try:
        sink.emit(stream="stdout", message="hello\n")
        time.sleep(0.08)
    finally:
        sink.close()


def test_install_sqlite_stdio_logger_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_QUANT_SQLITE_LOG", "0")
    assert sl.install_sqlite_stdio_logger(db_path=str(tmp_path / "x.db"), mode="paper") is None


def test_install_sqlite_stdio_logger_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_QUANT_SQLITE_LOG", "1")
    db_path = tmp_path / "stdio.db"

    orig_out = sys.stdout
    orig_err = sys.stderr
    sink = sl.install_sqlite_stdio_logger(db_path=str(db_path), mode="paper")
    assert sink is not None
    try:
        print("hello stdio")
        sys.stderr.write("⚠️ stderr line\n")
        sys.stdout.flush()
        sys.stderr.flush()
        assert _wait_for(lambda: db_path.exists())
    finally:
        sys.stdout = orig_out
        sys.stderr = orig_err
        sink.close()


def test_install_sqlite_stdio_logger_wrap_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_QUANT_SQLITE_LOG", "1")

    class BoomWriter:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(sl, "_LineBufferingWriter", BoomWriter)
    assert sl.install_sqlite_stdio_logger(db_path=str(tmp_path / "boom.db"), mode=None) is None
