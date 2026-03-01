from __future__ import annotations

import os
import socket
from pathlib import Path

from engine.systemd_watchdog import SystemdWatchdog


def _recv(sock: socket.socket) -> str:
    data = sock.recv(1024)
    return data.decode("utf-8")


def test_systemd_watchdog_sends_ready_watchdog_and_stopping(tmp_path: Path) -> None:
    sock_path = tmp_path / "notify.sock"
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    srv.bind(str(sock_path))
    srv.settimeout(1.0)
    try:
        watchdog = SystemdWatchdog(
            service_name="unit-test",
            notify_socket=str(sock_path),
            watchdog_interval_s=None,
        )
        watchdog.start()
        msg1 = _recv(srv)
        msg2 = _recv(srv)
        assert "READY=1" in {msg1, msg2}
        assert any(m.startswith("STATUS=unit-test") for m in (msg1, msg2))

        watchdog.ping()
        assert _recv(srv) == "WATCHDOG=1"

        watchdog.stop()
        assert _recv(srv) == "STOPPING=1"
    finally:
        srv.close()


def test_watchdog_interval_respects_watchdog_pid(monkeypatch) -> None:
    monkeypatch.setenv("NOTIFY_SOCKET", "/tmp/fake-notify-sock")
    monkeypatch.setenv("WATCHDOG_USEC", "4000000")
    monkeypatch.setenv("WATCHDOG_PID", str(os.getpid()))
    enabled = SystemdWatchdog(service_name="pid-ok")
    assert enabled.watchdog_interval_s == 2.0

    monkeypatch.setenv("WATCHDOG_PID", str(os.getpid() + 1))
    disabled = SystemdWatchdog(service_name="pid-mismatch")
    assert disabled.watchdog_interval_s is None
