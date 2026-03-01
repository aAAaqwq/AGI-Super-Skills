from __future__ import annotations

import os
import socket
import threading
from typing import Final


_MIN_WATCHDOG_INTERVAL_S: Final[float] = 1.0
_MAX_WATCHDOG_INTERVAL_S: Final[float] = 300.0


def _watchdog_interval_from_env() -> float | None:
    notify_socket = str(os.getenv("NOTIFY_SOCKET", "") or "").strip()
    if not notify_socket:
        return None

    pid_raw = str(os.getenv("WATCHDOG_PID", "") or "").strip()
    if pid_raw:
        try:
            if int(pid_raw) != os.getpid():
                return None
        except Exception:
            return None

    raw = str(os.getenv("WATCHDOG_USEC", "") or "").strip()
    if not raw:
        return None
    try:
        usec = int(raw)
    except Exception:
        return None
    if usec <= 0:
        return None

    interval = (float(usec) / 1_000_000.0) / 2.0
    return float(max(_MIN_WATCHDOG_INTERVAL_S, min(_MAX_WATCHDOG_INTERVAL_S, interval)))


class SystemdWatchdog:
    """Best-effort systemd READY/WATCHDOG notifier.

    This helper is intentionally no-fail: notification errors are swallowed so
    runtime behaviour is unchanged when systemd notify is unavailable.
    """

    def __init__(
        self,
        *,
        service_name: str,
        notify_socket: str | None = None,
        watchdog_interval_s: float | None = None,
    ) -> None:
        self._service_name = str(service_name or "service")
        self._notify_socket = (
            str(notify_socket).strip()
            if notify_socket is not None
            else str(os.getenv("NOTIFY_SOCKET", "") or "").strip()
        )
        if watchdog_interval_s is None:
            self._watchdog_interval_s = _watchdog_interval_from_env()
        else:
            try:
                interval = float(watchdog_interval_s)
            except Exception:
                interval = 0.0
            self._watchdog_interval_s = interval if interval > 0 else None

        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        return bool(self._notify_socket)

    @property
    def watchdog_interval_s(self) -> float | None:
        return self._watchdog_interval_s

    def start(self) -> None:
        if not self.enabled:
            return
        self._stop.clear()
        self._notify("READY=1")
        self._notify(f"STATUS={self._service_name} running")

        if self._watchdog_interval_s is None:
            return
        if self._thread and self._thread.is_alive():
            return

        thread = threading.Thread(
            target=self._run,
            name=f"aiq-systemd-watchdog-{self._service_name}",
            daemon=True,
        )
        self._thread = thread
        thread.start()

    def ping(self) -> None:
        if not self.enabled:
            return
        self._notify("WATCHDOG=1")

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            try:
                thread.join(timeout=1.0)
            except Exception:
                pass
        if self.enabled:
            self._notify("STOPPING=1")

    def _run(self) -> None:
        interval_s = self._watchdog_interval_s
        if interval_s is None:
            return
        while not self._stop.wait(float(interval_s)):
            self.ping()

    def _notify(self, state: str) -> None:
        notify_socket = self._notify_socket
        if not notify_socket:
            return

        addr: str | bytes = notify_socket
        if notify_socket.startswith("@"):
            addr = b"\0" + notify_socket[1:].encode("utf-8")
        payload = str(state).encode("utf-8")
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
                sock.connect(addr)
                sock.sendall(payload)
        except Exception:
            return
