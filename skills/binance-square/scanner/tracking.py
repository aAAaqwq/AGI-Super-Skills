"""Deterministic, dependency-free forward tracking for published signals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Iterable

from .contracts import ContractViolation, parse_utc

if TYPE_CHECKING:
    from .scoring import ScoredOpportunity


class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"


class Outcome(str, Enum):
    PENDING = "PENDING"
    UNTRIGGERED = "UNTRIGGERED"
    TRACKING = "TRACKING"
    STOPPED = "STOPPED"
    TP1_REACHED = "TP1_REACHED"
    TP2_REACHED = "TP2_REACHED"
    TIMEOUT = "TIMEOUT"


@dataclass(frozen=True, slots=True)
class TrackingSignal:
    signal_id: str
    signal_family_id: str
    author_id: str
    direction: Direction
    entry_low: Decimal
    entry_high: Decimal
    entry_price: Decimal
    stop_loss: Decimal
    tp1: Decimal
    tp2: Decimal
    published_at: datetime
    holding_period_hours: int = 72


@dataclass(frozen=True, slots=True)
class Candle:
    observed_at: datetime
    high: Decimal
    low: Decimal
    close: Decimal


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Complete execution assumptions required before reporting ``NET_R``."""

    entry_fee_rate: Decimal
    exit_fee_rate: Decimal
    entry_slippage_rate: Decimal
    exit_slippage_rate: Decimal
    tp1_exit_fraction: Decimal

    def __post_init__(self) -> None:
        rates = (
            self.entry_fee_rate,
            self.exit_fee_rate,
            self.entry_slippage_rate,
            self.exit_slippage_rate,
        )
        if any(
            not isinstance(value, Decimal) or not value.is_finite() or value < 0
            for value in rates
        ):
            raise ContractViolation(
                "fees and slippage must be non-negative finite Decimals"
            )
        if (
            not isinstance(self.tp1_exit_fraction, Decimal)
            or not self.tp1_exit_fraction.is_finite()
            or not Decimal(0) <= self.tp1_exit_fraction <= Decimal(1)
        ):
            raise ContractViolation(
                "TP1 exit fraction must be a Decimal from zero to one"
            )


@dataclass(frozen=True, slots=True)
class TrackingResult:
    signal_id: str
    signal_family_id: str
    author_id: str
    published_at: datetime
    outcome: Outcome
    triggered_at: datetime | None
    finalized_at: datetime | None
    r_value: Decimal | None
    r_label: str | None
    mfe_r: Decimal | None
    mae_r: Decimal | None
    tp1_reached: bool


@dataclass(frozen=True, slots=True)
class AuthorObservation:
    signal_family_id: str
    author_id: str
    finalized_at: datetime
    triggered: bool
    performance_score: Decimal | None

    def __post_init__(self) -> None:
        if self.performance_score is not None and (
            not isinstance(self.performance_score, Decimal)
            or not self.performance_score.is_finite()
            or not Decimal(0) <= self.performance_score <= Decimal(25)
        ):
            raise ContractViolation("author performance score must be from zero to 25")


@dataclass(frozen=True, slots=True)
class AuthorAggregate:
    author_id: str
    as_of: datetime
    observation_count: int
    triggered_count: int
    execution_rate: Decimal | None
    score_60d: Decimal | None
    score_lifetime: Decimal | None
    score_final: Decimal | None
    score_for_ranking: Decimal | None
    eligible_for_tier_change: bool


def tracking_signal_from_scored(
    opportunity: "ScoredOpportunity",
) -> TrackingSignal:
    """Convert one publishable scored opportunity into a tracking contract.

    This is intentionally a pure adapter.  It neither persists nor schedules
    tracking, and it refuses filtered/hard-gated or identity-incomplete input.
    """

    from .opportunities import calculate_risk_reward
    from .scoring import RankBucket, ScoredOpportunity

    if not isinstance(opportunity, ScoredOpportunity):
        raise ContractViolation("tracking conversion requires a ScoredOpportunity")
    if opportunity.hard_gate_reasons or opportunity.rank_bucket not in {
        RankBucket.TOP,
        RankBucket.WATCH,
    }:
        raise ContractViolation("only publishable TOP/WATCH opportunities can be tracked")
    if (
        opportunity.rank_bucket is RankBucket.TOP
        and opportunity.total_score < 75
    ) or (
        opportunity.rank_bucket is RankBucket.WATCH
        and opportunity.total_score < 65
    ):
        raise ContractViolation("tracking rank bucket and score are inconsistent")
    candidate = opportunity.candidate
    author_id = candidate.author_id.strip() if isinstance(candidate.author_id, str) else ""
    if not author_id or author_id.upper() == "LIVE":
        raise ContractViolation("tracking requires a stable author ID")
    if any(
        value is None
        for value in (
            candidate.entry_price,
            candidate.stop_loss,
            candidate.tp1,
        )
    ):
        raise ContractViolation("tracking requires Entry, SL, and TP1")
    calculate_risk_reward(candidate)
    assert candidate.entry_price is not None
    assert candidate.stop_loss is not None
    assert candidate.tp1 is not None
    entry_low = candidate.entry_low or candidate.entry_price
    entry_high = candidate.entry_high or candidate.entry_price
    if entry_low > entry_high:
        raise ContractViolation("tracking entry zone must be ordered")
    if candidate.holding_period_hours <= 0:
        raise ContractViolation("tracking holding period must be positive")
    return TrackingSignal(
        signal_id=candidate.signal_id,
        signal_family_id=candidate.signal_family_id,
        author_id=author_id,
        direction=Direction(candidate.direction.value),
        entry_low=entry_low,
        entry_high=entry_high,
        entry_price=candidate.entry_price,
        stop_loss=candidate.stop_loss,
        tp1=candidate.tp1,
        tp2=candidate.tp2 or candidate.tp1,
        published_at=parse_utc(candidate.published_at),
        holding_period_hours=candidate.holding_period_hours,
    )


def tracking_signals_from_scored(
    opportunities: Iterable["ScoredOpportunity"],
) -> tuple[TrackingSignal, ...]:
    """Convert eligible scored values and deduplicate signal families."""

    from .scoring import RankBucket, ScoredOpportunity

    converted: list[TrackingSignal] = []
    for opportunity in opportunities:
        if not isinstance(opportunity, ScoredOpportunity):
            raise ContractViolation("tracking inputs must be ScoredOpportunity values")
        if opportunity.rank_bucket not in {RankBucket.TOP, RankBucket.WATCH}:
            continue
        converted.append(tracking_signal_from_scored(opportunity))
    return deduplicate_signal_families(converted)


def _entry_touched(signal: TrackingSignal, candle: Candle) -> bool:
    return candle.low <= signal.entry_high and candle.high >= signal.entry_low


def _stop_touched(signal: TrackingSignal, candle: Candle) -> bool:
    if signal.direction is Direction.LONG:
        return candle.low <= signal.stop_loss
    return candle.high >= signal.stop_loss


def _target_touched(signal: TrackingSignal, candle: Candle, target: Decimal) -> bool:
    if signal.direction is Direction.LONG:
        return candle.high >= target
    return candle.low <= target


def _nominal_r(signal: TrackingSignal, exit_price: Decimal) -> Decimal:
    risk = abs(signal.entry_price - signal.stop_loss)
    movement = exit_price - signal.entry_price
    if signal.direction is Direction.SHORT:
        movement = -movement
    return movement / risk


def _excursions(signal: TrackingSignal, candle: Candle) -> tuple[Decimal, Decimal]:
    risk = abs(signal.entry_price - signal.stop_loss)
    if signal.direction is Direction.LONG:
        favorable = candle.high - signal.entry_price
        adverse = signal.entry_price - candle.low
    else:
        favorable = signal.entry_price - candle.low
        adverse = candle.high - signal.entry_price
    return max(Decimal(0), favorable / risk), max(Decimal(0), adverse / risk)


def _reported_r(
    signal: TrackingSignal,
    exit_price: Decimal,
    *,
    tp1_reached: bool,
    execution_config: ExecutionConfig | None,
) -> tuple[Decimal, str]:
    if execution_config is None:
        return _nominal_r(signal, exit_price), "NOMINAL_R"

    config = execution_config
    if signal.direction is Direction.LONG:
        entry_fill = signal.entry_price * (Decimal(1) + config.entry_slippage_rate)
        entry_cash = entry_fill * (Decimal(1) + config.entry_fee_rate)

        def exit_cash(price: Decimal) -> Decimal:
            fill = price * (Decimal(1) - config.exit_slippage_rate)
            return fill * (Decimal(1) - config.exit_fee_rate)

        pnl = -entry_cash
        sign = Decimal(1)
    else:
        entry_fill = signal.entry_price * (Decimal(1) - config.entry_slippage_rate)
        entry_cash = entry_fill * (Decimal(1) - config.entry_fee_rate)

        def exit_cash(price: Decimal) -> Decimal:
            fill = price * (Decimal(1) + config.exit_slippage_rate)
            return fill * (Decimal(1) + config.exit_fee_rate)

        pnl = entry_cash
        sign = Decimal(-1)

    first_fraction = config.tp1_exit_fraction if tp1_reached else Decimal(0)
    final_fraction = Decimal(1) - first_fraction
    exits = first_fraction * exit_cash(signal.tp1) + final_fraction * exit_cash(exit_price)
    pnl += sign * exits
    return pnl / abs(signal.entry_price - signal.stop_loss), "NET_R"


def track_signal(
    signal: TrackingSignal,
    candles: Iterable[Candle],
    *,
    execution_config: ExecutionConfig | None = None,
) -> TrackingResult:
    """Evaluate one signal using conservative intrabar ordering."""

    ordered = sorted(candles, key=lambda item: parse_utc(item.observed_at))
    trigger_deadline = parse_utc(signal.published_at) + timedelta(hours=24)
    triggered_at: datetime | None = None
    risk = abs(signal.entry_price - signal.stop_loss)
    if not risk:
        raise ContractViolation("entry price and stop loss must differ")
    tp1_reached = False
    mfe_r = Decimal(0)
    mae_r = Decimal(0)

    for candle in ordered:
        observed_at = parse_utc(candle.observed_at)
        if triggered_at is None:
            if (
                observed_at < parse_utc(signal.published_at)
                or observed_at > trigger_deadline
                or not _entry_touched(signal, candle)
            ):
                continue
            triggered_at = observed_at
        candle_mfe, candle_mae = _excursions(signal, candle)
        mfe_r = max(mfe_r, candle_mfe)
        mae_r = max(mae_r, candle_mae)
        if _stop_touched(signal, candle):
            r_value, r_label = _reported_r(
                signal,
                signal.stop_loss,
                tp1_reached=tp1_reached,
                execution_config=execution_config,
            )
            return TrackingResult(
                signal_id=signal.signal_id,
                signal_family_id=signal.signal_family_id,
                author_id=signal.author_id,
                published_at=parse_utc(signal.published_at),
                outcome=Outcome.STOPPED,
                triggered_at=triggered_at,
                finalized_at=observed_at,
                r_value=r_value,
                r_label=r_label,
                mfe_r=mfe_r,
                mae_r=mae_r,
                tp1_reached=tp1_reached,
            )
        if _target_touched(signal, candle, signal.tp1):
            tp1_reached = True
        if tp1_reached and _target_touched(signal, candle, signal.tp2):
            r_value, r_label = _reported_r(
                signal,
                signal.tp2,
                tp1_reached=True,
                execution_config=execution_config,
            )
            return TrackingResult(
                signal_id=signal.signal_id,
                signal_family_id=signal.signal_family_id,
                author_id=signal.author_id,
                published_at=parse_utc(signal.published_at),
                outcome=Outcome.TP2_REACHED,
                triggered_at=triggered_at,
                finalized_at=observed_at,
                r_value=r_value,
                r_label=r_label,
                mfe_r=mfe_r,
                mae_r=mae_r,
                tp1_reached=True,
            )
        tracking_deadline = triggered_at + timedelta(hours=signal.holding_period_hours)
        if observed_at >= tracking_deadline:
            r_value, r_label = _reported_r(
                signal,
                candle.close,
                tp1_reached=tp1_reached,
                execution_config=execution_config,
            )
            return TrackingResult(
                signal_id=signal.signal_id,
                signal_family_id=signal.signal_family_id,
                author_id=signal.author_id,
                published_at=parse_utc(signal.published_at),
                outcome=Outcome.TIMEOUT,
                triggered_at=triggered_at,
                finalized_at=observed_at,
                r_value=r_value,
                r_label=r_label,
                mfe_r=mfe_r,
                mae_r=mae_r,
                tp1_reached=tp1_reached,
            )

    untriggered = (
        triggered_at is None
        and bool(ordered)
        and parse_utc(ordered[-1].observed_at) >= trigger_deadline
    )
    return TrackingResult(
        signal_id=signal.signal_id,
        signal_family_id=signal.signal_family_id,
        author_id=signal.author_id,
        published_at=parse_utc(signal.published_at),
        outcome=(
            Outcome.TRACKING
            if triggered_at is not None
            else Outcome.UNTRIGGERED
            if untriggered
            else Outcome.PENDING
        ),
        triggered_at=triggered_at,
        finalized_at=trigger_deadline if untriggered else None,
        r_value=None,
        r_label=None,
        mfe_r=mfe_r if triggered_at is not None else None,
        mae_r=mae_r if triggered_at is not None else None,
        tp1_reached=tp1_reached,
    )


def deduplicate_signal_families(
    signals: Iterable[TrackingSignal],
) -> tuple[TrackingSignal, ...]:
    """Return one deterministic, earliest publication per signal family."""

    chosen: dict[str, TrackingSignal] = {}
    for signal in signals:
        current = chosen.get(signal.signal_family_id)
        key = (parse_utc(signal.published_at), signal.signal_id)
        if current is None or key < (parse_utc(current.published_at), current.signal_id):
            chosen[signal.signal_family_id] = signal
    return tuple(
        sorted(
            chosen.values(),
            key=lambda item: (parse_utc(item.published_at), item.signal_family_id),
        )
    )


def _average(values: list[Decimal]) -> Decimal | None:
    return sum(values, Decimal(0)) / len(values) if values else None


def aggregate_author_performance(
    author_id: str,
    observations: Iterable[AuthorObservation],
    *,
    as_of: datetime,
    exclude_signal_family_ids: Iterable[str] = (),
) -> AuthorAggregate:
    """Build a point-in-time 60-day/lifetime author view without family duplicates."""

    cutoff = parse_utc(as_of) - timedelta(days=60)
    excluded_families = frozenset(exclude_signal_family_ids)
    by_family: dict[str, AuthorObservation] = {}
    for observation in observations:
        finalized_at = parse_utc(observation.finalized_at)
        if (
            observation.author_id != author_id
            or observation.signal_family_id in excluded_families
            or finalized_at > parse_utc(as_of)
        ):
            continue
        current = by_family.get(observation.signal_family_id)
        if current is None or finalized_at > parse_utc(current.finalized_at):
            by_family[observation.signal_family_id] = observation

    unique = tuple(by_family.values())
    triggered = tuple(item for item in unique if item.triggered)
    lifetime_scores = [
        item.performance_score
        for item in triggered
        if item.performance_score is not None
    ]
    recent_scores = [
        item.performance_score
        for item in triggered
        if item.performance_score is not None and parse_utc(item.finalized_at) >= cutoff
    ]
    score_60d = _average(recent_scores)
    score_lifetime = _average(lifetime_scores)
    score_final = (
        score_60d * Decimal("0.7") + score_lifetime * Decimal("0.3")
        if score_60d is not None and score_lifetime is not None
        else score_60d or score_lifetime
    )
    eligible = len(triggered) >= 20
    score_for_ranking = (
        min(score_final, Decimal(20))
        if score_final is not None and not eligible
        else score_final
    )
    return AuthorAggregate(
        author_id=author_id,
        as_of=parse_utc(as_of),
        observation_count=len(unique),
        triggered_count=len(triggered),
        execution_rate=(Decimal(len(triggered)) / len(unique) if unique else None),
        score_60d=score_60d,
        score_lifetime=score_lifetime,
        score_final=score_final,
        score_for_ranking=score_for_ranking,
        eligible_for_tier_change=eligible,
    )
