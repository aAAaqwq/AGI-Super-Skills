"""Frozen deterministic shadow derivation policy for v4 opportunities.

The policy is deliberately conservative.  It never invents a direction or a
symbol, never operates on partial/Spot market evidence, and returns an
auditable rejection instead of forcing a plan when structure or RR is weak.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Mapping

from .authors import AuthorProfile
from .contracts import ContractViolation, parse_utc
from .indicators import IndicatorEvidence, calculate_indicators
from .market import INTERVALS, UNKNOWN, Candle, MarketSnapshot, MarketSource
from .opportunities import (
    Direction,
    ParameterSource,
    SignalCandidate,
    calculate_risk_reward,
    extract_signal,
)
from .square import PostDetail, StructuredPost


class DerivationDisposition(str, Enum):
    AUTHOR = "AUTHOR"
    SYSTEM_REDERIVED = "SYSTEM_REDERIVED"
    REJECTED = "REJECTED"


class DerivationSetup(str, Enum):
    PULLBACK = "PULLBACK"
    BREAKOUT_RETEST = "BREAKOUT_RETEST"


@dataclass(frozen=True, slots=True)
class DerivationPolicy:
    """Versioned constants for deterministic shadow replays."""

    version: str = "DERIVATION_POLICY_V1"
    atr_stop_buffer: Decimal = Decimal("0.4")
    entry_half_width_atr: Decimal = Decimal("0.1")
    retest_tolerance_atr: Decimal = Decimal("0.2")
    max_chase_distance_atr: Decimal = Decimal("1.5")
    minimum_tp1_rr: Decimal = Decimal("1.5")
    minimum_main_target_rr: Decimal = Decimal("2")
    maximum_post_age: timedelta = timedelta(hours=24)
    maximum_market_age: timedelta = timedelta(minutes=15)
    minimum_candles: int = 21

    def __post_init__(self) -> None:
        decimal_fields = (
            self.atr_stop_buffer,
            self.entry_half_width_atr,
            self.retest_tolerance_atr,
            self.max_chase_distance_atr,
            self.minimum_tp1_rr,
            self.minimum_main_target_rr,
        )
        if any(
            not isinstance(value, Decimal) or not value.is_finite() or value <= 0
            for value in decimal_fields
        ):
            raise ContractViolation("derivation policy values must be positive Decimals")
        if self.minimum_candles < 21:
            raise ContractViolation("derivation policy requires at least 21 candles")
        if self.maximum_post_age <= timedelta(0) or self.maximum_market_age <= timedelta(0):
            raise ContractViolation("derivation policy ages must be positive")


DERIVATION_POLICY_V1 = DerivationPolicy()


@dataclass(frozen=True, slots=True)
class DerivationResult:
    policy_version: str
    disposition: DerivationDisposition
    original_candidate: SignalCandidate | None
    candidate: SignalCandidate | None
    setup: DerivationSetup | None
    evidence: tuple[str, ...]
    reasons: tuple[str, ...]

    @property
    def accepted(self) -> bool:
        return self.disposition is not DerivationDisposition.REJECTED


def _decision_time(
    market: MarketSnapshot, decision_at: datetime | str | None
) -> datetime:
    if decision_at is not None:
        return parse_utc(decision_at)
    return datetime.fromtimestamp(market.decision_time_ms / 1000, tz=timezone.utc)


def _reject(
    candidate: SignalCandidate | None,
    policy: DerivationPolicy,
    reasons: tuple[str, ...] | list[str],
    evidence: tuple[str, ...] | list[str] = (),
) -> DerivationResult:
    return DerivationResult(
        policy_version=policy.version,
        disposition=DerivationDisposition.REJECTED,
        original_candidate=candidate,
        candidate=None,
        setup=None,
        evidence=tuple(evidence),
        reasons=tuple(dict.fromkeys(reasons)),
    )


def _market_rejection_reasons(
    candidate: SignalCandidate,
    market: MarketSnapshot,
    decision_at: datetime,
    policy: DerivationPolicy,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if (
        market.symbol != candidate.symbol
        or market.contract.symbol != candidate.symbol
        or market.contract.status != "TRADING"
        or market.contract.contract_type != "PERPETUAL"
        or market.contract.quote_asset != "USDT"
        or market.contract.margin_asset != "USDT"
    ):
        reasons.append("NO_ACTIVE_EXACT_USDT_PERPETUAL")
    if market.source is not MarketSource.FUTURES:
        reasons.append("INCOMPLETE_MARKET_SPOT_PROXY")
    scalar_values = (
        market.mark_price,
        market.index_price,
        market.funding_rate,
        market.open_interest,
        market.base_volume_24h,
        market.quote_volume_24h,
    )
    if (
        market.missing_fields
        or market.complete_dataset_count != market.expected_dataset_count
        or any(
            value == UNKNOWN
            or not isinstance(value, Decimal)
            or not value.is_finite()
            for value in scalar_values
        )
    ):
        reasons.append("INCOMPLETE_MARKET_SNAPSHOT")
    if (
        not isinstance(market.last_price, Decimal)
        or not market.last_price.is_finite()
        or market.last_price <= 0
    ):
        reasons.append("INVALID_MARKET_PRICE")

    market_time = datetime.fromtimestamp(
        market.decision_time_ms / 1000, tz=timezone.utc
    )
    age = decision_at - market_time
    if age < timedelta(0):
        reasons.append("MARKET_SNAPSHOT_AFTER_DECISION")
    elif age > policy.maximum_market_age:
        reasons.append("STALE_MARKET_SNAPSHOT")

    for interval in INTERVALS:
        candles = market.candles.get(interval, ())
        if len(candles) < policy.minimum_candles:
            reasons.append(f"INCOMPLETE_{interval.upper()}_CANDLES")
            continue
        if any(candle.source is not MarketSource.FUTURES for candle in candles):
            reasons.append(f"NON_FUTURES_{interval.upper()}_CANDLES")
        if any(candle.close_time >= market.decision_time_ms for candle in candles):
            reasons.append(f"OPEN_{interval.upper()}_CANDLE_PRESENT")
        if any(
            left.open_time >= right.open_time
            for left, right in zip(candles, candles[1:])
        ):
            reasons.append(f"UNORDERED_{interval.upper()}_CANDLES")
        if any(
            candle.high < max(candle.open, candle.close)
            or candle.low > min(candle.open, candle.close)
            or candle.high < candle.low
            for candle in candles
        ):
            reasons.append(f"INVALID_{interval.upper()}_OHLC")
    return tuple(dict.fromkeys(reasons))


def _trend(candles: tuple[Candle, ...], indicator: IndicatorEvidence) -> str:
    first = sum((item.close for item in candles[:5]), Decimal(0)) / Decimal(5)
    last = sum((item.close for item in candles[-3:]), Decimal(0)) / Decimal(3)
    if last > first and candles[-1].close >= indicator.bollinger.middle:
        return "BULLISH"
    if last < first and candles[-1].close <= indicator.bollinger.middle:
        return "BEARISH"
    return "MIXED"


def _author_plan_status(
    candidate: SignalCandidate,
    current_price: Decimal,
    policy: DerivationPolicy,
) -> tuple[str, tuple[str, ...]]:
    if candidate.stop_loss is not None:
        if candidate.direction is Direction.LONG and current_price <= candidate.stop_loss:
            return "REJECT", ("AUTHOR_STOP_ALREADY_INVALIDATED",)
        if candidate.direction is Direction.SHORT and current_price >= candidate.stop_loss:
            return "REJECT", ("AUTHOR_STOP_ALREADY_INVALIDATED",)
    main_target = candidate.tp2 or candidate.tp1
    if main_target is not None:
        if candidate.direction is Direction.LONG and current_price >= main_target:
            return "REJECT", ("AUTHOR_MAIN_TARGET_ALREADY_REACHED",)
        if candidate.direction is Direction.SHORT and current_price <= main_target:
            return "REJECT", ("AUTHOR_MAIN_TARGET_ALREADY_REACHED",)

    complete = all(
        value is not None
        for value in (candidate.entry_price, candidate.stop_loss, candidate.tp1)
    )
    if not complete:
        return "REDERIVE", ("AUTHOR_PARAMETERS_INCOMPLETE",)
    try:
        rr = calculate_risk_reward(candidate)
    except ContractViolation:
        return "REJECT", ("AUTHOR_INVALID_PRICE_GEOMETRY",)
    if rr.tp1_rr < policy.minimum_tp1_rr:
        return "REJECT", ("AUTHOR_TP1_RR_BELOW_1_5",)
    if rr.main_target_rr < policy.minimum_main_target_rr:
        return "REJECT", ("AUTHOR_MAIN_TARGET_RR_BELOW_2",)

    assert candidate.entry_price is not None
    entry_low = candidate.entry_low or candidate.entry_price
    entry_high = candidate.entry_high or candidate.entry_price
    missed = (
        current_price > entry_high
        if candidate.direction is Direction.LONG
        else current_price < entry_low
    )
    if missed:
        return "REDERIVE", ("AUTHOR_ENTRY_MISSED",)
    return "AUTHOR", ("AUTHOR_PARAMETERS_VALID",)


def _breakout_retest_level(
    candles: tuple[Candle, ...],
    direction: Direction,
    atr: Decimal,
    policy: DerivationPolicy,
) -> Decimal | None:
    history = candles[-policy.minimum_candles : -2]
    breakout = candles[-2]
    retest = candles[-1]
    tolerance = atr * policy.retest_tolerance_atr
    if direction is Direction.LONG:
        level = max(item.high for item in history)
        if (
            breakout.close > level
            and retest.low <= level + tolerance
            and retest.close >= level
        ):
            return level
    else:
        level = min(item.low for item in history)
        if (
            breakout.close < level
            and retest.high >= level - tolerance
            and retest.close <= level
        ):
            return level
    return None


def _structural_targets(
    direction: Direction,
    entry_price: Decimal,
    one_hour: tuple[Candle, ...],
    four_hour: tuple[Candle, ...],
) -> tuple[Decimal, Decimal] | None:
    one_hour_level = (
        max(item.high for item in one_hour[-20:])
        if direction is Direction.LONG
        else min(item.low for item in one_hour[-20:])
    )
    four_hour_level = (
        max(item.high for item in four_hour[-20:])
        if direction is Direction.LONG
        else min(item.low for item in four_hour[-20:])
    )
    if direction is Direction.LONG:
        if not entry_price < one_hour_level < four_hour_level:
            return None
    elif not entry_price > one_hour_level > four_hour_level:
        return None
    return one_hour_level, four_hour_level


def apply_derivation_policy(
    candidate: SignalCandidate,
    market: MarketSnapshot,
    *,
    decision_at: datetime | str | None = None,
    policy: DerivationPolicy = DERIVATION_POLICY_V1,
) -> DerivationResult:
    """Resolve author parameters or create one conservative shadow re-entry."""

    if not isinstance(candidate, SignalCandidate):
        raise ContractViolation("derivation requires a SignalCandidate")
    if not isinstance(market, MarketSnapshot):
        raise ContractViolation("derivation requires a MarketSnapshot")
    if not isinstance(candidate.direction, Direction):
        return _reject(
            candidate,
            policy,
            ("AMBIGUOUS_OR_MISSING_DIRECTION",),
        )
    decision = _decision_time(market, decision_at)
    evidence: list[str] = [
        f"policy={policy.version}",
        f"symbol={candidate.symbol}",
        f"direction={candidate.direction.value}",
        f"market_source={market.source.value}",
        f"market_decision_time_ms={market.decision_time_ms}",
        f"market_captured_at={parse_utc(market.captured_at).isoformat()}",
    ]

    published_at = parse_utc(candidate.published_at)
    post_age = decision - published_at
    if post_age < timedelta(0):
        return _reject(candidate, policy, ("POST_AFTER_DECISION",), evidence)
    if post_age >= policy.maximum_post_age:
        return _reject(candidate, policy, ("POST_EXPIRED",), evidence)

    market_reasons = _market_rejection_reasons(candidate, market, decision, policy)
    if market_reasons:
        return _reject(candidate, policy, market_reasons, evidence)

    indicators: dict[str, IndicatorEvidence] = {}
    try:
        for interval in ("15m", "1h", "4h"):
            indicators[interval] = calculate_indicators(market.candles[interval])
    except (ContractViolation, KeyError) as exc:
        evidence.append(f"indicator_failure={type(exc).__name__}")
        return _reject(candidate, policy, ("INDICATOR_EVIDENCE_INVALID",), evidence)

    trends = {
        interval: _trend(market.candles[interval], indicators[interval])
        for interval in ("15m", "1h", "4h")
    }
    evidence.extend(
        f"{interval}_trend={trends[interval]}" for interval in ("15m", "1h", "4h")
    )
    desired = "BULLISH" if candidate.direction is Direction.LONG else "BEARISH"
    if trends["1h"] != desired or trends["4h"] != desired:
        return _reject(candidate, policy, ("DIRECTIONAL_STRUCTURE_NOT_CONFIRMED",), evidence)

    author_status, author_reasons = _author_plan_status(
        candidate, market.last_price, policy
    )
    if author_status == "REJECT":
        return _reject(candidate, policy, author_reasons, evidence)
    if author_status == "AUTHOR":
        rr = calculate_risk_reward(candidate)
        evidence.extend((f"tp1_rr={rr.tp1_rr}", f"main_target_rr={rr.main_target_rr}"))
        return DerivationResult(
            policy_version=policy.version,
            disposition=DerivationDisposition.AUTHOR,
            original_candidate=candidate,
            candidate=candidate,
            setup=None,
            evidence=tuple(evidence),
            reasons=author_reasons,
        )

    one_hour = market.candles["1h"]
    four_hour = market.candles["4h"]
    fifteen_minute = market.candles["15m"]
    atr_1h = indicators["1h"].atr
    atr_15m = indicators["15m"].atr
    breakout_level = _breakout_retest_level(
        one_hour, candidate.direction, atr_1h, policy
    )
    setup = (
        DerivationSetup.BREAKOUT_RETEST
        if breakout_level is not None
        else DerivationSetup.PULLBACK
    )
    if breakout_level is not None:
        anchor = breakout_level
    elif candidate.direction is Direction.LONG:
        anchor = min(item.low for item in fifteen_minute[-6:])
    else:
        anchor = max(item.high for item in fifteen_minute[-6:])

    half_width = atr_15m * policy.entry_half_width_atr
    entry_low = anchor - half_width
    entry_high = anchor + half_width
    entry_price = (entry_low + entry_high) / Decimal(2)
    stop_buffer = atr_1h * policy.atr_stop_buffer
    stop_loss = (
        anchor - stop_buffer
        if candidate.direction is Direction.LONG
        else anchor + stop_buffer
    )

    if candidate.direction is Direction.LONG:
        structurally_broken = market.last_price <= stop_loss
        chase_distance = market.last_price - entry_high
    else:
        structurally_broken = market.last_price >= stop_loss
        chase_distance = entry_low - market.last_price
    if structurally_broken:
        return _reject(candidate, policy, ("DERIVED_STRUCTURE_ALREADY_INVALID",), evidence)
    if chase_distance > atr_1h * policy.max_chase_distance_atr:
        evidence.append(f"chase_distance_atr={chase_distance / atr_1h}")
        return _reject(candidate, policy, ("CURRENT_PRICE_TOO_EXTENDED",), evidence)

    targets = _structural_targets(
        candidate.direction, entry_price, one_hour, four_hour
    )
    if targets is None:
        return _reject(candidate, policy, ("STRUCTURAL_TARGETS_UNAVAILABLE",), evidence)
    tp1, tp2 = targets
    resolved = replace(
        candidate,
        entry_low=entry_low,
        entry_high=entry_high,
        entry_price=entry_price,
        stop_loss=stop_loss,
        tp1=tp1,
        tp2=tp2,
        invalidation=(
            f"{policy.version}: {setup.value} structure invalid beyond {stop_loss}"
        ),
        parameter_source=ParameterSource.SYSTEM_REDERIVED,
    )
    try:
        rr = calculate_risk_reward(resolved)
    except ContractViolation:
        return _reject(candidate, policy, ("DERIVED_INVALID_PRICE_GEOMETRY",), evidence)
    rr_reasons: list[str] = []
    if rr.tp1_rr < policy.minimum_tp1_rr:
        rr_reasons.append("DERIVED_TP1_RR_BELOW_1_5")
    if rr.main_target_rr < policy.minimum_main_target_rr:
        rr_reasons.append("DERIVED_MAIN_TARGET_RR_BELOW_2")
    evidence.extend(
        (
            f"setup={setup.value}",
            f"entry_zone={entry_low}:{entry_high}",
            f"structural_stop={stop_loss};atr_buffer={policy.atr_stop_buffer}",
            f"tp1={tp1};tp1_rr={rr.tp1_rr}",
            f"tp2={tp2};main_target_rr={rr.main_target_rr}",
        )
    )
    if rr_reasons:
        return _reject(candidate, policy, rr_reasons, evidence)
    return DerivationResult(
        policy_version=policy.version,
        disposition=DerivationDisposition.SYSTEM_REDERIVED,
        original_candidate=candidate,
        candidate=resolved,
        setup=setup,
        evidence=tuple(evidence),
        reasons=author_reasons,
    )


def derive_post_signal(
    post: StructuredPost | PostDetail,
    author: AuthorProfile | None,
    market: MarketSnapshot,
    *,
    legacy_signal: Mapping[str, object] | None = None,
    decision_at: datetime | str | None = None,
    policy: DerivationPolicy = DERIVATION_POLICY_V1,
) -> DerivationResult:
    """Extract symbol/direction first; ambiguity becomes an auditable rejection."""

    try:
        candidate = extract_signal(post, author, legacy_signal=legacy_signal)
    except ContractViolation as exc:
        message = str(exc).casefold()
        reason = (
            "AMBIGUOUS_OR_MISSING_SYMBOL_DIRECTION"
            if "symbol" in message or "direction" in message
            else "EXTRACTED_AUTHOR_PARAMETERS_INVALID"
        )
        return _reject(
            None,
            policy,
            (reason,),
            (f"extraction_failure={type(exc).__name__}",),
        )
    return apply_derivation_policy(
        candidate, market, decision_at=decision_at, policy=policy
    )


__all__ = [
    "DERIVATION_POLICY_V1",
    "DerivationDisposition",
    "DerivationPolicy",
    "DerivationResult",
    "DerivationSetup",
    "apply_derivation_policy",
    "derive_post_signal",
]
