from __future__ import annotations

import threading


def test_token_bucket_allow_uses_internal_lock():
    from engine.risk import TokenBucket

    bucket = TokenBucket(capacity=1.0, refill_per_s=0.0)
    started = threading.Event()
    finished = threading.Event()

    def _worker() -> None:
        started.set()
        bucket.allow(cost=1.0)
        finished.set()

    with bucket._lock:
        thread = threading.Thread(target=_worker)
        thread.start()
        assert started.wait(timeout=1.0)
        assert not finished.wait(timeout=0.05)

    thread.join(timeout=1.0)
    assert finished.is_set()


def test_token_bucket_concurrent_allow_respects_capacity():
    from engine.risk import TokenBucket

    bucket = TokenBucket(capacity=3.0, refill_per_s=0.0)
    workers = 32
    start_barrier = threading.Barrier(workers)
    results = [False] * workers

    def _worker(i: int) -> None:
        start_barrier.wait()
        results[i] = bucket.allow(cost=1.0)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(1 for ok in results if ok) == 3
