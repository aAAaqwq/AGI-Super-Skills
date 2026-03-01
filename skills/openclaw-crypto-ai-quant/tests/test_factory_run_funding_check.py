from __future__ import annotations

import factory_run


def _payload(*, symbols: list[str], status: str = "FAIL", severity: str = "FAIL", issue_type: str = "stale") -> dict:
    return {
        "status": status,
        "issues": [
            {"symbol": symbol, "severity": severity, "type": issue_type, "message": f"issue:{symbol}"}
            for symbol in symbols
        ],
    }


def test_parse_cli_args_reads_funding_env_threshold(monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_FUNDING_MAX_AGE_FAIL_HOURS", "21.5")
    args = factory_run._parse_cli_args(["--run-id", "x"])
    assert args.max_age_fail_hours == 21.5


def test_parse_cli_args_reads_funding_stale_allowance_env(monkeypatch) -> None:
    monkeypatch.setenv("AI_QUANT_FUNDING_MAX_STALE_SYMBOLS", "2")
    args = factory_run._parse_cli_args(["--run-id", "x"])
    assert args.funding_max_stale_symbols == 2


def test_funding_stale_symbol_allowance_handles_single_stale_symbol() -> None:
    can_degrade, meta = factory_run._funding_check_degraded_allowance(
        _payload(symbols=["BTC"], status="FAIL"),
        max_stale_symbols=1,
    )
    assert can_degrade
    assert meta is not None
    assert meta["symbols"] == ["BTC"]
    assert meta["count"] == 1


def test_funding_stale_symbol_allowance_rejects_non_stale_fail() -> None:
    payload = _payload(symbols=["BTC"], status="FAIL")
    payload["issues"][0]["type"] = "no_data_in_window"
    can_degrade, meta = factory_run._funding_check_degraded_allowance(payload, max_stale_symbols=1)
    assert not can_degrade
    assert meta is None


def test_funding_stale_symbol_allowance_rejects_excessive_stale_symbols() -> None:
    can_degrade, meta = factory_run._funding_check_degraded_allowance(
        _payload(symbols=["BTC", "ETH"], status="FAIL"),
        max_stale_symbols=1,
    )
    assert not can_degrade
    assert meta is None
