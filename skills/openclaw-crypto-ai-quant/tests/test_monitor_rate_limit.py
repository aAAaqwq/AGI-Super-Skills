from __future__ import annotations

import monitor.server as monitor_server


def test_per_ip_token_bucket_limiter_enforces_burst_and_refill() -> None:
    limiter = monitor_server._PerIpTokenBucketLimiter(rate_per_s=2.0, burst=2.0, max_ips=10)

    assert limiter.allow("1.2.3.4", now_s=0.0) is True
    assert limiter.allow("1.2.3.4", now_s=0.0) is True
    assert limiter.allow("1.2.3.4", now_s=0.0) is False
    # 0.5s at 2 tokens/s refills one token.
    assert limiter.allow("1.2.3.4", now_s=0.5) is True


def test_active_request_limiter_caps_and_releases() -> None:
    limiter = monitor_server._ActiveRequestLimiter(max_active=2)

    assert limiter.acquire() is True
    assert limiter.acquire() is True
    assert limiter.acquire() is False
    limiter.release()
    assert limiter.acquire() is True


def test_handler_api_rate_limit_returns_429(monkeypatch) -> None:
    handler = object.__new__(monitor_server.Handler)
    handler.client_address = ("10.9.8.7", 12345)

    sent: dict[str, object] = {}

    def _fake_send_json(obj, status: int = 200) -> None:
        sent["status"] = int(status)
        sent["obj"] = obj

    handler._send_json = _fake_send_json

    class _DenyLimiter:
        def __init__(self) -> None:
            self.ips: list[str] = []

        def allow(self, ip: str, *, now_s: float | None = None) -> bool:
            self.ips.append(str(ip))
            return False

    deny_limiter = _DenyLimiter()
    monkeypatch.setattr(monitor_server, "_API_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(monitor_server, "_API_RATE_LIMITER", deny_limiter)

    allowed = handler._check_api_rate_limit("/api/snapshot")

    assert allowed is False
    assert sent["status"] == 429
    payload = sent["obj"]
    assert isinstance(payload, dict)
    assert payload["error"] == "rate_limited"
    assert deny_limiter.ips == ["10.9.8.7"]


def test_monitor_request_queue_size_is_clamped(monkeypatch) -> None:
    monkeypatch.setenv("AIQ_MONITOR_REQUEST_QUEUE_SIZE", "0")
    assert monitor_server._monitor_request_queue_size() == 1

    monkeypatch.setenv("AIQ_MONITOR_REQUEST_QUEUE_SIZE", "50000")
    assert monitor_server._monitor_request_queue_size() == 1024

    monkeypatch.setenv("AIQ_MONITOR_REQUEST_QUEUE_SIZE", "64")
    assert monitor_server._monitor_request_queue_size() == 64

    assert 1 <= monitor_server.MonitorHTTPServer.request_queue_size <= 1024
