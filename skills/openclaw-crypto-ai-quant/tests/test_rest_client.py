from __future__ import annotations

import urllib.request

from engine.rest_client import HyperliquidRestClient


def test_all_mids_defaults_to_single_attempt(monkeypatch) -> None:
    attempts = 0
    sleep_calls = 0

    def _fake_urlopen(_req, timeout):
        nonlocal attempts
        attempts += 1
        raise RuntimeError("boom")

    def _fake_sleep(_seconds: float):
        nonlocal sleep_calls
        sleep_calls += 1

    monkeypatch.delenv("AI_QUANT_REST_ALL_MIDS_RETRIES", raising=False)
    monkeypatch.delenv("AI_QUANT_REST_ALL_MIDS_TIMEOUT_S", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr("engine.rest_client.time.sleep", _fake_sleep)

    client = HyperliquidRestClient(timeout_s=30.0)
    res = client.all_mids()

    assert res.ok is False
    assert attempts == 1
    assert sleep_calls == 0


def test_all_mids_honours_env_retry_and_timeout(monkeypatch) -> None:
    timeouts: list[float] = []
    sleep_calls = 0

    def _fake_urlopen(_req, timeout):
        timeouts.append(float(timeout))
        raise RuntimeError("boom")

    def _fake_sleep(_seconds: float):
        nonlocal sleep_calls
        sleep_calls += 1

    monkeypatch.setenv("AI_QUANT_REST_ALL_MIDS_RETRIES", "2")
    monkeypatch.setenv("AI_QUANT_REST_ALL_MIDS_TIMEOUT_S", "1.5")
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr("engine.rest_client.time.sleep", _fake_sleep)

    client = HyperliquidRestClient(timeout_s=30.0)
    res = client.all_mids()

    assert res.ok is False
    assert len(timeouts) == 2
    assert timeouts == [1.5, 1.5]
    assert sleep_calls == 1


def test_all_mids_falls_back_to_client_timeout_when_env_unset(monkeypatch) -> None:
    timeouts: list[float] = []

    def _fake_urlopen(_req, timeout):
        timeouts.append(float(timeout))
        raise RuntimeError("boom")

    monkeypatch.delenv("AI_QUANT_REST_ALL_MIDS_TIMEOUT_S", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr("engine.rest_client.time.sleep", lambda _seconds: None)

    client = HyperliquidRestClient(timeout_s=2.5)
    res = client.all_mids()

    assert res.ok is False
    assert timeouts == [2.5]
