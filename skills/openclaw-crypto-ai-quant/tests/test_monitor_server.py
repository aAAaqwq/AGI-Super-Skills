from __future__ import annotations

import http.client
import json
import threading
import time
from typing import Any

import pytest

import monitor.server as monitor_server


class _StubMids:
    def snapshot(self) -> dict[str, Any]:
        return {"BTC": 100_000.0}

    def wait_snapshot_since(self, *, after_seq: int, timeout_s: float = 15.0) -> dict[str, Any]:
        _ = after_seq
        time.sleep(min(max(float(timeout_s), 0.0), 0.05))
        return {"BTC": 100_000.0}


class _StubState:
    def __init__(self) -> None:
        self.mids = _StubMids()


def _request(
    port: int,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5.0)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        response = conn.getresponse()
        payload = response.read()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, payload
    finally:
        conn.close()


@pytest.fixture()
def monitor_http_server(monkeypatch):
    monkeypatch.setenv("AIQ_MONITOR_TOKEN", "integration-token")
    monkeypatch.setattr(monitor_server, "_API_RATE_LIMIT_ENABLED", False)
    monkeypatch.setattr(monitor_server, "_ACTIVE_REQUEST_LIMITER", monitor_server._ActiveRequestLimiter(max_active=32))
    monkeypatch.setattr(monitor_server, "STATE", _StubState())

    server = monitor_server.MonitorHTTPServer(("127.0.0.1", 0), monitor_server.Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield int(server.server_address[1])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3.0)


def test_api_health_requires_bearer_auth_and_accepts_valid_token(monitor_http_server) -> None:
    status, headers, payload = _request(monitor_http_server, "GET", "/api/health")
    assert status == 401
    assert headers["content-type"].startswith("application/json")
    assert json.loads(payload.decode("utf-8"))["error"] == "unauthorized"

    ok_status, ok_headers, ok_payload = _request(
        monitor_http_server,
        "GET",
        "/api/health",
        headers={"Authorization": "Bearer integration-token"},
    )
    assert ok_status == 200
    assert ok_headers["content-type"].startswith("application/json")
    parsed = json.loads(ok_payload.decode("utf-8"))
    assert parsed["ok"] is True
    assert parsed["ws"] == {"BTC": 100_000.0}


def test_static_path_traversal_is_rejected(monitor_http_server) -> None:
    status, headers, payload = _request(monitor_http_server, "GET", "/static/../AGENTS.md")
    assert status == 400
    assert headers["content-type"].startswith("text/plain")
    assert payload.decode("utf-8") == "bad path"


def test_metrics_endpoint_serves_prometheus_text(monkeypatch, monitor_http_server) -> None:
    monkeypatch.setattr(
        monitor_server,
        "build_prometheus_metrics",
        lambda mode: (
            "# HELP aiq_integration_metric Integration metric\n"
            "# TYPE aiq_integration_metric gauge\n"
            f'aiq_integration_metric{{mode="{mode}"}} 1\n'
        ),
    )

    status, headers, payload = _request(monitor_http_server, "GET", "/metrics?mode=paper")
    assert status == 200
    assert headers["content-type"].startswith("text/plain")
    text = payload.decode("utf-8")
    assert "# HELP aiq_integration_metric" in text
    assert '# TYPE aiq_integration_metric gauge' in text
    assert 'aiq_integration_metric{mode="paper"} 1' in text


def test_mids_stream_emits_sse_frame(monitor_http_server) -> None:
    conn = http.client.HTTPConnection("127.0.0.1", monitor_http_server, timeout=5.0)
    try:
        conn.request("GET", "/api/mids/stream", headers={"Authorization": "Bearer integration-token"})
        resp = conn.getresponse()
        assert resp.status == 200
        headers = {k.lower(): v for k, v in resp.getheaders()}
        assert headers["content-type"].startswith("text/event-stream")

        retry_line = resp.fp.readline().decode("utf-8")
        event_line = resp.fp.readline().decode("utf-8")
        data_line = resp.fp.readline().decode("utf-8")
        assert retry_line.startswith("retry:")
        assert event_line.strip() == "event: mids"
        assert data_line.startswith("data: ")
        payload = json.loads(data_line[len("data: ") :])
        assert payload == {"BTC": 100_000.0}
    finally:
        conn.close()
