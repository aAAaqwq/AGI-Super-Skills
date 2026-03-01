from __future__ import annotations

import engine.daemon as daemon


class _DummyLock:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


def test_register_lock_cleanup_registers_close_callback() -> None:
    seen: dict[str, object] = {}
    lock = _DummyLock()

    def _fake_register(fn, *args):
        seen["fn"] = fn
        seen["args"] = args

    daemon._register_lock_cleanup(lock, register_fn=_fake_register)

    assert seen["fn"] is daemon._close_lock_file
    assert seen["args"] == (lock,)


def test_close_lock_file_is_best_effort() -> None:
    class _BadLock:
        def close(self) -> None:
            raise RuntimeError("boom")

    daemon._close_lock_file(_BadLock())
