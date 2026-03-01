from __future__ import annotations

import queue
import time

import pytest

import live.trader as live_trader


def _drain_discord_queue() -> None:
    while True:
        try:
            live_trader._DISCORD_QUEUE.get_nowait()
        except queue.Empty:
            return
        try:
            live_trader._DISCORD_QUEUE.task_done()
        except Exception:
            pass


def _wait_until(predicate, *, timeout_s: float = 2.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


@pytest.fixture(autouse=True)
def _reset_discord_worker_state():
    live_trader._stop_discord_worker(timeout_s=1.0)
    _drain_discord_queue()
    yield
    live_trader._stop_discord_worker(timeout_s=1.0)
    _drain_discord_queue()


def test_discord_worker_can_stop_and_restart(monkeypatch):
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        live_trader,
        "_send_discord_message_sync",
        lambda *, target, message: sent.append((target, message)),
    )

    live_trader._ensure_discord_worker_started()
    assert live_trader._DISCORD_WORKER_THREAD is not None
    assert live_trader._DISCORD_WORKER_THREAD.is_alive()

    live_trader._DISCORD_QUEUE.put_nowait(("ops", "alpha"))
    assert _wait_until(lambda: ("ops", "alpha") in sent)

    live_trader._stop_discord_worker(timeout_s=2.0)
    assert live_trader._DISCORD_WORKER_STARTED is False
    assert live_trader._DISCORD_WORKER_THREAD is None

    live_trader._ensure_discord_worker_started()
    live_trader._DISCORD_QUEUE.put_nowait(("ops", "beta"))
    assert _wait_until(lambda: ("ops", "beta") in sent)


def test_ensure_discord_worker_started_recovers_from_stale_state():
    live_trader._DISCORD_WORKER_STARTED = True
    live_trader._DISCORD_WORKER_THREAD = None

    live_trader._ensure_discord_worker_started()

    assert live_trader._DISCORD_WORKER_THREAD is not None
    assert live_trader._DISCORD_WORKER_THREAD.is_alive()
