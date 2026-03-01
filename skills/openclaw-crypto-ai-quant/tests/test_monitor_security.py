from __future__ import annotations

import io
import sys
import types

import pytest

import monitor.server as monitor_server


def test_check_api_auth_uses_constant_time_compare(monkeypatch) -> None:
    handler = object.__new__(monitor_server.Handler)
    handler.headers = {"Authorization": "Bearer super-secret"}
    handler._send_json = lambda obj, status=200: None

    monkeypatch.setenv("AIQ_MONITOR_TOKEN", "super-secret")
    called: dict[str, object] = {}

    def _fake_compare_digest(left: bytes, right: bytes) -> bool:
        called["left"] = left
        called["right"] = right
        return True

    monkeypatch.setattr(monitor_server.hmac, "compare_digest", _fake_compare_digest)

    assert handler._check_api_auth() is True
    assert called["left"] == b"Bearer super-secret"
    assert called["right"] == b"Bearer super-secret"


def test_check_api_auth_non_ascii_header_returns_401_without_exception(monkeypatch) -> None:
    handler = object.__new__(monitor_server.Handler)
    handler.headers = {"Authorization": "Bearer bad-\u2603"}

    sent: dict[str, object] = {}

    def _fake_send_json(obj, status: int = 200) -> None:
        sent["status"] = int(status)
        sent["obj"] = obj

    handler._send_json = _fake_send_json
    monkeypatch.setenv("AIQ_MONITOR_TOKEN", "super-secret")

    assert handler._check_api_auth() is False
    assert sent["status"] == 401


def test_do_post_rejects_payload_larger_than_limit(monkeypatch) -> None:
    handler = object.__new__(monitor_server.Handler)
    handler.path = "/api/v2/decisions/replay"
    handler.headers = {"Content-Length": "2048"}
    handler.rfile = io.BytesIO(b"{}")
    handler._reject_overloaded = lambda: False
    handler._check_api_rate_limit = lambda _path: True
    handler._check_api_auth = lambda: True
    handler._send_text = lambda text, status=200: None

    sent: dict[str, object] = {}

    def _fake_send_json(obj, status: int = 200) -> None:
        sent["status"] = int(status)
        sent["obj"] = obj

    handler._send_json = _fake_send_json
    monkeypatch.setattr(monitor_server, "_MAX_POST_BODY_BYTES", 1024)

    handler.do_POST()

    assert sent["status"] == 413
    payload = sent["obj"]
    assert isinstance(payload, dict)
    assert payload["error"] == "payload_too_large"
    assert payload["max_bytes"] == 1024


def test_monitor_bind_security_error_requires_tls_for_non_local_token() -> None:
    err = monitor_server._monitor_bind_security_error(bind="0.0.0.0", token="abc", tls_terminated=False)
    assert "TLS_TERMINATED=1" in err


def test_monitor_bind_security_error_allows_safe_cases() -> None:
    assert monitor_server._monitor_bind_security_error(bind="127.0.0.1", token="abc", tls_terminated=False) == ""
    assert monitor_server._monitor_bind_security_error(bind="0.0.0.0", token="", tls_terminated=False) == ""
    assert monitor_server._monitor_bind_security_error(bind="0.0.0.0", token="abc", tls_terminated=True) == ""


def test_main_refuses_non_local_bind_with_token_without_tls(monkeypatch) -> None:
    monkeypatch.setenv("AIQ_MONITOR_BIND", "0.0.0.0")
    monkeypatch.setenv("AIQ_MONITOR_TOKEN", "abc")
    monkeypatch.delenv("AIQ_MONITOR_TLS_TERMINATED", raising=False)

    def _should_not_start_server(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("server should not start")

    monkeypatch.setattr(monitor_server, "MonitorHTTPServer", _should_not_start_server)

    with pytest.raises(SystemExit, match="TLS"):
        monitor_server.main()


def test_log_message_suppresses_non_error_status(monkeypatch) -> None:
    handler = object.__new__(monitor_server.Handler)
    calls: list[tuple[str, tuple[object, ...]]] = []

    def _fake_base_log_message(self, fmt: str, *args) -> None:  # noqa: ARG001
        calls.append((fmt, args))

    monkeypatch.setattr(monitor_server.BaseHTTPRequestHandler, "log_message", _fake_base_log_message)

    handler.log_message('"%s" %s %s', "GET / HTTP/1.1", "200", "123")
    assert calls == []


def test_log_message_forwards_4xx_status(monkeypatch) -> None:
    handler = object.__new__(monitor_server.Handler)
    calls: list[tuple[str, tuple[object, ...]]] = []

    def _fake_base_log_message(self, fmt: str, *args) -> None:  # noqa: ARG001
        calls.append((fmt, args))

    monkeypatch.setattr(monitor_server.BaseHTTPRequestHandler, "log_message", _fake_base_log_message)

    handler.log_message('"%s" %s %s', "GET /api/unknown HTTP/1.1", "404", "19")
    assert len(calls) == 1
    assert calls[0][1][1] == "404"


def test_log_message_forwards_5xx_status(monkeypatch) -> None:
    handler = object.__new__(monitor_server.Handler)
    calls: list[tuple[str, tuple[object, ...]]] = []

    def _fake_base_log_message(self, fmt: str, *args) -> None:  # noqa: ARG001
        calls.append((fmt, args))

    monkeypatch.setattr(monitor_server.BaseHTTPRequestHandler, "log_message", _fake_base_log_message)

    handler.log_message('"%s" %s %s', "POST /api/v2/decisions/replay HTTP/1.1", "503", "57")
    assert len(calls) == 1
    assert calls[0][1][1] == "503"


def test_fetch_hl_balance_success_payload_does_not_expose_main_address(monkeypatch) -> None:
    monkeypatch.setenv("AIQ_MONITOR_HL_BALANCE_ENABLE", "1")
    monkeypatch.setattr(monitor_server, "_HL_BAL_CACHE", None)
    monkeypatch.setattr(monitor_server, "_HL_ADDR_CACHE", None)
    monkeypatch.setattr(monitor_server, "_infer_hl_main_address", lambda: "0x" + ("1" * 40))

    info_mod = types.ModuleType("hyperliquid.info")
    constants_mod = types.ModuleType("hyperliquid.utils.constants")
    utils_mod = types.ModuleType("hyperliquid.utils")
    constants_mod.MAINNET_API_URL = "https://example.invalid"
    utils_mod.constants = constants_mod

    class _FakeInfo:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003, ARG002
            pass

        def user_state(self, main_address: str) -> dict[str, object]:
            assert main_address.startswith("0x")
            return {
                "marginSummary": {"accountValue": 100.0, "totalMarginUsed": 40.0},
                "withdrawable": 60.0,
            }

    info_mod.Info = _FakeInfo
    monkeypatch.setitem(sys.modules, "hyperliquid.info", info_mod)
    monkeypatch.setitem(sys.modules, "hyperliquid.utils.constants", constants_mod)
    monkeypatch.setitem(sys.modules, "hyperliquid.utils", utils_mod)

    out = monitor_server.fetch_hl_balance()

    assert out is not None
    assert out["ok"] is True
    assert "main_address" not in out


def test_fetch_hl_balance_error_payload_does_not_expose_main_address(monkeypatch) -> None:
    monkeypatch.setenv("AIQ_MONITOR_HL_BALANCE_ENABLE", "1")
    monkeypatch.setattr(monitor_server, "_HL_BAL_CACHE", None)
    monkeypatch.setattr(monitor_server, "_HL_ADDR_CACHE", None)
    monkeypatch.setattr(monitor_server, "_infer_hl_main_address", lambda: "0x" + ("2" * 40))

    info_mod = types.ModuleType("hyperliquid.info")
    constants_mod = types.ModuleType("hyperliquid.utils.constants")
    utils_mod = types.ModuleType("hyperliquid.utils")
    constants_mod.MAINNET_API_URL = "https://example.invalid"
    utils_mod.constants = constants_mod

    class _BoomInfo:
        def __init__(self, *args, **kwargs):  # noqa: ANN002, ANN003, ARG002
            pass

        def user_state(self, main_address: str) -> dict[str, object]:  # noqa: ARG002
            raise RuntimeError("boom")

    info_mod.Info = _BoomInfo
    monkeypatch.setitem(sys.modules, "hyperliquid.info", info_mod)
    monkeypatch.setitem(sys.modules, "hyperliquid.utils.constants", constants_mod)
    monkeypatch.setitem(sys.modules, "hyperliquid.utils", utils_mod)

    out = monitor_server.fetch_hl_balance()

    assert out is not None
    assert out["ok"] is False
    assert "main_address" not in out
