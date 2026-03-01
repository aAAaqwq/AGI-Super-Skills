from __future__ import annotations

import queue
import threading

from engine import alerting


def test_note_alert_drop_thread_safe(monkeypatch):
    monkeypatch.setattr(alerting, "_ALERT_DROPPED_COUNT", 0)
    monkeypatch.setattr(alerting._alert_logger, "warning", lambda *args, **kwargs: None)

    workers = 12
    increments_per_worker = 4000
    start_barrier = threading.Barrier(workers)

    def _worker() -> None:
        start_barrier.wait()
        for _ in range(increments_per_worker):
            alerting._note_alert_drop()

    threads = [threading.Thread(target=_worker) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert alerting._ALERT_DROPPED_COUNT == workers * increments_per_worker


def test_shutdown_alert_worker_drains_queue_and_stops_worker(monkeypatch):
    sent: list[tuple[str, str, str]] = []

    monkeypatch.setattr(alerting, "_ALERT_QUEUE", queue.Queue(maxsize=10))
    monkeypatch.setattr(alerting, "_ALERT_WORKER_STARTED", False)
    monkeypatch.setattr(alerting, "_ALERT_WORKER_THREAD", None)
    monkeypatch.setattr(alerting, "_ALERT_ATEXIT_REGISTERED", False)
    monkeypatch.setattr(
        alerting,
        "_send_one_sync",
        lambda *, channel, target, message: sent.append((channel, target, message)),
    )

    alerting._ensure_worker_started()
    alerting._ALERT_QUEUE.put(("discord", "#ops", "alpha"))
    alerting._ALERT_QUEUE.put(("discord", "#ops", "beta"))
    alerting._shutdown_alert_worker(drain_timeout_s=1.0)

    assert ("discord", "#ops", "alpha") in sent
    assert ("discord", "#ops", "beta") in sent
    assert alerting._ALERT_WORKER_STARTED is False
    worker = alerting._ALERT_WORKER_THREAD
    assert worker is None or not worker.is_alive()


def test_ensure_worker_started_registers_atexit_once(monkeypatch):
    registrations: list[object] = []

    monkeypatch.setattr(alerting, "_ALERT_QUEUE", queue.Queue(maxsize=10))
    monkeypatch.setattr(alerting, "_ALERT_WORKER_STARTED", False)
    monkeypatch.setattr(alerting, "_ALERT_WORKER_THREAD", None)
    monkeypatch.setattr(alerting, "_ALERT_ATEXIT_REGISTERED", False)
    monkeypatch.setattr(alerting.atexit, "register", lambda fn: registrations.append(fn))
    monkeypatch.setattr(alerting, "_send_one_sync", lambda **_kwargs: None)

    alerting._ensure_worker_started()
    alerting._ensure_worker_started()
    alerting._shutdown_alert_worker(drain_timeout_s=0.2)

    assert len(registrations) == 1


def test_shutdown_alert_worker_keeps_started_state_when_stop_not_enqueued(monkeypatch):
    class _FakeThread:
        def __init__(self) -> None:
            self._alive = True

        def is_alive(self) -> bool:
            return self._alive

        def join(self, timeout=None) -> None:  # noqa: ANN001,ARG002
            return

    full_q: queue.Queue[object] = queue.Queue(maxsize=1)
    full_q.put("busy-item")
    fake_thread = _FakeThread()

    monkeypatch.setattr(alerting, "_ALERT_QUEUE", full_q)
    monkeypatch.setattr(alerting, "_ALERT_WORKER_STARTED", True)
    monkeypatch.setattr(alerting, "_ALERT_WORKER_THREAD", fake_thread)

    alerting._shutdown_alert_worker(drain_timeout_s=0.0)

    assert alerting._ALERT_WORKER_STARTED is True
    assert alerting._ALERT_WORKER_THREAD is fake_thread


def test_ensure_worker_started_recovers_from_stale_dead_worker_state(monkeypatch):
    class _DeadThread:
        def is_alive(self) -> bool:
            return False

    monkeypatch.setattr(alerting, "_ALERT_QUEUE", queue.Queue(maxsize=10))
    monkeypatch.setattr(alerting, "_ALERT_WORKER_STARTED", True)
    monkeypatch.setattr(alerting, "_ALERT_WORKER_THREAD", _DeadThread())
    monkeypatch.setattr(alerting, "_ALERT_ATEXIT_REGISTERED", False)
    monkeypatch.setattr(alerting.atexit, "register", lambda fn: None)
    monkeypatch.setattr(alerting, "_send_one_sync", lambda **_kwargs: None)

    alerting._ensure_worker_started()
    assert alerting._ALERT_WORKER_STARTED is True
    assert alerting._ALERT_WORKER_THREAD is not None
    assert alerting._ALERT_WORKER_THREAD.is_alive()

    alerting._shutdown_alert_worker(drain_timeout_s=0.2)
