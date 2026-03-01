from __future__ import annotations

import json

import pytest

import exchange.sidecar as sidecar


class _BaseFile:
    def __init__(self) -> None:
        self._last_line: bytes = b""

    def write(self, line: bytes) -> None:
        self._last_line = bytes(line)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        return None


class _FailingReadFile(_BaseFile):
    def readline(self) -> bytes:
        raise ConnectionError("sidecar closed")


class _SuccessFile(_BaseFile):
    def __init__(self, result):
        super().__init__()
        self._result = result

    def readline(self) -> bytes:
        req = json.loads(self._last_line.decode("utf-8").strip())
        return (
            json.dumps({"id": int(req["id"]), "ok": True, "result": self._result}, separators=(",", ":")) + "\n"
        ).encode("utf-8")


class _ErrorResponseFile(_BaseFile):
    def readline(self) -> bytes:
        req = json.loads(self._last_line.decode("utf-8").strip())
        return (json.dumps({"id": int(req["id"]), "ok": False, "error": "sidecar error"}) + "\n").encode("utf-8")


class _DummySock:
    def settimeout(self, _timeout_s: float) -> None:
        return None

    def close(self) -> None:
        return None


def _mk_client_with_connect_sequence(files: list[_BaseFile]):
    client = sidecar.SidecarWSClient(sock_path="/tmp/aiq-sidecar-test.sock")
    connect_calls: list[float] = []
    close_calls: list[int] = []
    it = iter(files)

    def _fake_connect(*, timeout_s: float) -> None:
        connect_calls.append(float(timeout_s))
        client._sock = _DummySock()
        client._f = next(it)
        client._rpc_timeout_s = float(timeout_s)
        client._connected = True

    def _fake_close() -> None:
        close_calls.append(1)
        client._sock = None
        client._f = None
        client._connected = False

    client._connect = _fake_connect  # type: ignore[method-assign]
    client._close = _fake_close  # type: ignore[method-assign]
    return client, connect_calls, close_calls


def test_rpc_retries_once_after_connection_error_then_succeeds():
    client, connects, closes = _mk_client_with_connect_sequence([_FailingReadFile(), _SuccessFile({"ok": 1})])

    out = client._rpc("health", {}, timeout_s=1.0)

    assert out == {"ok": 1}
    assert len(connects) == 2
    assert len(closes) == 1


def test_rpc_does_not_retry_non_retryable_sidecar_error_response():
    client, connects, closes = _mk_client_with_connect_sequence([_ErrorResponseFile()])

    with pytest.raises(RuntimeError, match="sidecar error"):
        client._rpc("health", {}, timeout_s=1.0)

    assert len(connects) == 1
    assert len(closes) == 1


def test_rpc_retries_only_once_then_raises_on_second_connection_failure():
    client, connects, closes = _mk_client_with_connect_sequence([_FailingReadFile(), _FailingReadFile()])

    with pytest.raises(ConnectionError, match="sidecar closed"):
        client._rpc("health", {}, timeout_s=1.0)

    assert len(connects) == 2
    assert len(closes) == 2


def test_rpc_does_not_retry_non_idempotent_drain_methods():
    client, connects, closes = _mk_client_with_connect_sequence([_FailingReadFile(), _SuccessFile({"ok": 1})])

    with pytest.raises(ConnectionError, match="sidecar closed"):
        client._rpc("drain_user_fills", {"max_items": 1}, timeout_s=1.0)

    assert len(connects) == 1
    assert len(closes) == 1


def test_wait_mids_parses_streaming_payload():
    payload = {
        "mids": {"btc": "100000.5", "ETH": 2500},
        "mids_age_s": "0.12",
        "mids_seq": 17,
        "changed": True,
        "timed_out": False,
    }
    client, _connects, _closes = _mk_client_with_connect_sequence([_SuccessFile(payload)])

    mids, age_s, seq, changed, timed_out = client.wait_mids(symbols=["BTC", "ETH"], after_seq=16, timeout_s=2.0)

    assert mids == {"BTC": 100000.5, "ETH": 2500.0}
    assert age_s == pytest.approx(0.12)
    assert seq == 17
    assert changed is True
    assert timed_out is False


def test_wait_mids_falls_back_to_get_mids_on_unknown_method():
    client = sidecar.SidecarWSClient(sock_path="/tmp/aiq-sidecar-test.sock")
    calls: list[str] = []

    def _fake_rpc(method: str, params, *, timeout_s: float):
        _ = params
        _ = timeout_s
        calls.append(method)
        if method == "wait_mids":
            raise RuntimeError("unknown method: wait_mids")
        if method == "get_mids":
            return {"mids": {"BTC": 99999.0}, "mids_age_s": 0.4}
        raise AssertionError(f"unexpected method: {method}")

    client._rpc = _fake_rpc  # type: ignore[method-assign]

    mids, age_s, seq, changed, timed_out = client.wait_mids(symbols=["BTC"], after_seq=10, timeout_s=1.0)

    assert calls == ["wait_mids", "get_mids"]
    assert mids == {"BTC": 99999.0}
    assert age_s == pytest.approx(0.4)
    assert seq is None
    assert changed is True
    assert timed_out is False
