from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path


@dataclass
class _FakeTrader:
    values: list[float]

    def __post_init__(self) -> None:
        self._idx = 0

    def get_live_balance(self) -> float:
        v = float(self.values[self._idx])
        self._idx += 1
        return v


def _bootstrap_risk_manager(
    *,
    tmp_path: Path,
    monkeypatch,
    max_drawdown_pct: float = 5.0,
    drawdown_reduce_policy: str | None = None,
    max_daily_loss_usd: float | None = None,
):
    cfg = tmp_path / "strategy_overrides.yaml"
    body = f"global:\n  risk:\n    max_drawdown_pct: {float(max_drawdown_pct)}\n"
    if drawdown_reduce_policy is not None:
        body += f"    drawdown_reduce_policy: {drawdown_reduce_policy}\n"
    if max_daily_loss_usd is not None:
        body += f"    max_daily_loss_usd: {float(max_daily_loss_usd)}\n"
    cfg.write_text(body, encoding="utf-8")

    monkeypatch.setenv("AI_QUANT_STRATEGY_YAML", str(cfg))
    monkeypatch.delenv("AI_QUANT_KILL_SWITCH", raising=False)
    monkeypatch.delenv("AI_QUANT_KILL_SWITCH_MODE", raising=False)
    monkeypatch.delenv("AI_QUANT_KILL_SWITCH_FILE", raising=False)
    monkeypatch.delenv("AI_QUANT_RISK_MAX_DRAWDOWN_PCT", raising=False)
    monkeypatch.delenv("AI_QUANT_RISK_DRAWDOWN_REDUCE_POLICY", raising=False)

    from engine.strategy_manager import StrategyManager

    StrategyManager.bootstrap(
        defaults={"trade": {}, "indicators": {}, "filters": {}, "thresholds": {}},
        yaml_path=str(cfg),
        changelog_path=None,
    )

    from engine.risk import RiskManager

    return RiskManager()


def test_drawdown_kill_switch_requires_explicit_resume(tmp_path, monkeypatch):
    risk = _bootstrap_risk_manager(tmp_path=tmp_path, monkeypatch=monkeypatch, max_drawdown_pct=5.0)
    trader = _FakeTrader([100.0, 94.0, 100.0, 100.0])

    risk.refresh(trader=trader)
    assert risk.kill_mode == "off"

    risk.refresh(trader=trader)
    assert risk.kill_mode == "close_only"

    risk.refresh(trader=trader)
    assert risk.kill_mode == "close_only"

    monkeypatch.setenv("AI_QUANT_KILL_SWITCH", "clear")
    risk.refresh(trader=trader)
    assert risk.kill_mode == "off"


def test_drawdown_reduce_policy_is_loaded_from_yaml(tmp_path, monkeypatch):
    risk = _bootstrap_risk_manager(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        max_drawdown_pct=5.0,
        drawdown_reduce_policy="close_all",
    )
    risk.refresh(trader=None)
    assert risk.drawdown_reduce_policy == "close_all"


def test_drawdown_does_not_trigger_just_below_threshold(tmp_path, monkeypatch):
    risk = _bootstrap_risk_manager(tmp_path=tmp_path, monkeypatch=monkeypatch, max_drawdown_pct=5.0)
    trader = _FakeTrader([100.0, 95.1])

    risk.refresh(trader=trader)
    risk.refresh(trader=trader)

    assert risk.kill_mode == "off"


def test_drawdown_triggers_at_exact_threshold_boundary(tmp_path, monkeypatch):
    risk = _bootstrap_risk_manager(tmp_path=tmp_path, monkeypatch=monkeypatch, max_drawdown_pct=5.0)
    trader = _FakeTrader([100.0, 95.0])

    risk.refresh(trader=trader)
    risk.refresh(trader=trader)

    assert risk.kill_mode == "close_only"
    assert risk.kill_reason == "drawdown"


def test_allow_order_blocks_open_but_allows_reduce_risk_when_killed(tmp_path, monkeypatch):
    risk = _bootstrap_risk_manager(tmp_path=tmp_path, monkeypatch=monkeypatch, max_drawdown_pct=5.0)
    trader = _FakeTrader([100.0, 94.0])

    risk.refresh(trader=trader)
    risk.refresh(trader=trader)
    assert risk.kill_mode == "close_only"

    open_decision = risk.allow_order(
        symbol="BTC",
        action="OPEN",
        side="BUY",
        notional_usd=100.0,
        leverage=3.0,
    )
    close_decision = risk.allow_order(
        symbol="BTC",
        action="CLOSE",
        side="SELL",
        notional_usd=100.0,
        leverage=3.0,
        reduce_risk=True,
    )

    assert open_decision.allowed is False
    assert open_decision.reason.startswith("close_only")
    assert close_decision.allowed is True
    assert close_decision.reason == "ok"


def test_clear_kill_resets_peak_and_prevents_immediate_retrigger(tmp_path, monkeypatch):
    risk = _bootstrap_risk_manager(tmp_path=tmp_path, monkeypatch=monkeypatch, max_drawdown_pct=5.0)
    trader = _FakeTrader([100.0, 94.0, 100.0, 96.0, 90.0])

    risk.refresh(trader=trader)
    risk.refresh(trader=trader)
    assert risk.kill_mode == "close_only"

    monkeypatch.setenv("AI_QUANT_KILL_SWITCH", "clear")
    risk.refresh(trader=trader)
    assert risk.kill_mode == "off"
    monkeypatch.delenv("AI_QUANT_KILL_SWITCH", raising=False)

    risk.refresh(trader=trader)
    assert risk.kill_mode == "off"

    risk.refresh(trader=trader)
    assert risk.kill_mode == "close_only"


def test_drawdown_peak_resets_at_utc_day_rollover(tmp_path, monkeypatch):
    risk = _bootstrap_risk_manager(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        max_drawdown_pct=5.0,
        max_daily_loss_usd=1000.0,
    )
    trader = _FakeTrader([100.0, 96.0, 96.0, 94.0])
    day1 = datetime.datetime(2026, 2, 10, 23, 59, tzinfo=datetime.timezone.utc)
    day2 = datetime.datetime(2026, 2, 11, 0, 1, tzinfo=datetime.timezone.utc)
    day_seq = iter(("2026-02-10", "2026-02-10", "2026-02-11", "2026-02-11"))
    risk._current_utc_day = lambda: next(day_seq)  # type: ignore[method-assign]

    # Establish day-1 high-water mark.
    risk.refresh(trader=trader)
    risk.refresh(trader=trader)
    assert risk.kill_mode == "off"

    # Daily-loss boundary reset should also reset drawdown peak.
    risk.note_fill(ts_ms=int(day1.timestamp() * 1000.0), symbol="BTC", action="CLOSE", pnl_usd=0.0, fee_usd=0.0)
    risk.note_fill(ts_ms=int(day2.timestamp() * 1000.0), symbol="BTC", action="CLOSE", pnl_usd=0.0, fee_usd=0.0)

    # With stale peak (100), 94 would breach 5% DD; with day-2 fresh peak (96), it stays below threshold.
    risk.refresh(trader=trader)
    risk.refresh(trader=trader)
    assert risk.kill_mode == "off"


def test_drawdown_peak_resets_without_daily_loss_fills(tmp_path, monkeypatch):
    risk = _bootstrap_risk_manager(tmp_path=tmp_path, monkeypatch=monkeypatch, max_drawdown_pct=5.0)

    today = datetime.datetime.now(tz=datetime.timezone.utc).date()
    yesterday = today - datetime.timedelta(days=1)
    risk._equity_peak = 100.0
    risk._drawdown_peak_utc_day = yesterday.isoformat()

    # No note_fill calls: rollover reset should still happen in refresh() path.
    trader = _FakeTrader([94.0, 93.0])
    risk.refresh(trader=trader)
    risk.refresh(trader=trader)
    assert risk.kill_mode == "off"


def test_refresh_drawdown_uses_account_value_fallback(tmp_path, monkeypatch):
    risk = _bootstrap_risk_manager(tmp_path=tmp_path, monkeypatch=monkeypatch, max_drawdown_pct=5.0)

    class _AccountValueTrader:
        def __init__(self, value: float) -> None:
            self._account_value_usd = float(value)

    trader = _AccountValueTrader(100.0)
    risk.refresh(trader=trader)
    assert risk.kill_mode == "off"

    trader._account_value_usd = 94.0
    risk.refresh(trader=trader)
    assert risk.kill_mode == "close_only"
    assert risk.kill_reason == "drawdown"


def test_refresh_drawdown_ignores_non_positive_equity(tmp_path, monkeypatch):
    risk = _bootstrap_risk_manager(tmp_path=tmp_path, monkeypatch=monkeypatch, max_drawdown_pct=6.0)
    trader = _FakeTrader([100.0, 0.0, -10.0, 95.0])

    risk.refresh(trader=trader)
    risk.refresh(trader=trader)
    risk.refresh(trader=trader)
    risk.refresh(trader=trader)

    assert risk.kill_mode == "off"


def test_drawdown_then_manual_halt_all_interaction(tmp_path, monkeypatch):
    risk = _bootstrap_risk_manager(tmp_path=tmp_path, monkeypatch=monkeypatch, max_drawdown_pct=5.0)
    trader = _FakeTrader([100.0, 94.0, 110.0])

    risk.refresh(trader=trader)
    risk.refresh(trader=trader)
    assert risk.kill_mode == "close_only"
    assert risk.kill_reason == "drawdown"

    monkeypatch.setenv("AI_QUANT_KILL_SWITCH", "halt")
    risk.refresh(trader=trader)
    assert risk.kill_mode == "halt_all"
    assert risk.kill_reason == "env"


def test_drawdown_sets_kill_reason_and_kill_since(tmp_path, monkeypatch):
    risk = _bootstrap_risk_manager(tmp_path=tmp_path, monkeypatch=monkeypatch, max_drawdown_pct=5.0)
    trader = _FakeTrader([100.0, 94.0])

    risk.refresh(trader=trader)
    risk.refresh(trader=trader)

    assert risk.kill_mode == "close_only"
    assert risk.kill_reason == "drawdown"
    assert isinstance(risk.kill_since_s, float)
