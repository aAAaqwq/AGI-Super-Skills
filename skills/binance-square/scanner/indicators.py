"""Dependency-free Decimal indicators over already-closed candles."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Iterable, Sequence

from scanner.contracts import ContractViolation
from scanner.market import UNKNOWN, Candle, MarketSource


@dataclass(frozen=True, slots=True)
class BollingerBands:
    lower: Decimal
    middle: Decimal
    upper: Decimal
    percent_b: Decimal | str
    bandwidth: Decimal | str
    period: int
    standard_deviations: Decimal


@dataclass(frozen=True, slots=True)
class VolumeEvidence:
    current: Decimal | str
    prior_average: Decimal | str
    ratio: Decimal | str
    unit: str
    source: MarketSource


@dataclass(frozen=True, slots=True)
class IndicatorEvidence:
    as_of_close_time: int
    close: Decimal
    bollinger: BollingerBands
    atr: Decimal
    volume: VolumeEvidence


def _finite_decimals(values: Iterable[Decimal], field_name: str) -> tuple[Decimal, ...]:
    parsed = tuple(values)
    if not parsed or any(not isinstance(value, Decimal) or not value.is_finite() for value in parsed):
        raise ContractViolation(f"{field_name} must contain finite Decimal values")
    return parsed


def bollinger_bands(
    closes: Sequence[Decimal],
    *,
    period: int = 20,
    standard_deviations: Decimal = Decimal("2"),
) -> BollingerBands:
    """Return BB using population standard deviation and the latest close."""

    if not isinstance(period, int) or isinstance(period, bool) or period < 2:
        raise ContractViolation("Bollinger period must be at least 2")
    values = _finite_decimals(closes, "closes")
    if len(values) < period:
        raise ContractViolation(f"BB({period}) requires at least {period} closes")
    if not isinstance(standard_deviations, Decimal) or standard_deviations <= 0:
        raise ContractViolation("Bollinger deviation multiplier must be positive Decimal")

    window = values[-period:]
    with localcontext() as context:
        context.prec = 28
        middle = sum(window, Decimal(0)) / Decimal(period)
        variance = sum(
            ((value - middle) * (value - middle) for value in window), Decimal(0)
        ) / Decimal(period)
        offset = standard_deviations * variance.sqrt()
        lower = middle - offset
        upper = middle + offset
        width = upper - lower
        percent_b: Decimal | str = (
            UNKNOWN if width == 0 else (window[-1] - lower) / width
        )
        bandwidth: Decimal | str = UNKNOWN if middle == 0 else width / middle
    return BollingerBands(
        lower=lower,
        middle=middle,
        upper=upper,
        percent_b=percent_b,
        bandwidth=bandwidth,
        period=period,
        standard_deviations=standard_deviations,
    )


def average_true_range(
    candles: Sequence[Candle], *, period: int = 14
) -> Decimal:
    """Return Wilder ATR, requiring one close before the first true range."""

    if not isinstance(period, int) or isinstance(period, bool) or period < 1:
        raise ContractViolation("ATR period must be a positive integer")
    if len(candles) < period + 1:
        raise ContractViolation(
            f"ATR({period}) requires at least {period + 1} closed candles"
        )
    for item in candles:
        _finite_decimals((item.high, item.low, item.close), "candle prices")
        if item.high < item.low:
            raise ContractViolation("candle high cannot be below low")

    true_ranges: list[Decimal] = []
    for previous, current in zip(candles, candles[1:]):
        true_ranges.append(
            max(
                current.high - current.low,
                abs(current.high - previous.close),
                abs(current.low - previous.close),
            )
        )
    with localcontext() as context:
        context.prec = 28
        atr = sum(true_ranges[:period], Decimal(0)) / Decimal(period)
        for true_range in true_ranges[period:]:
            atr = ((atr * Decimal(period - 1)) + true_range) / Decimal(period)
    return atr


def volume_evidence(
    candles: Sequence[Candle], *, lookback: int = 20
) -> VolumeEvidence:
    """Return auditable Futures base-volume evidence; Spot volume stays unknown."""

    if not isinstance(lookback, int) or isinstance(lookback, bool) or lookback < 1:
        raise ContractViolation("volume lookback must be a positive integer")
    if not candles:
        raise ContractViolation("volume evidence requires closed candles")
    source = candles[-1].source
    if any(candle.source is not source for candle in candles):
        raise ContractViolation("volume evidence cannot mix market sources")
    if source is MarketSource.SPOT_PROXY:
        return VolumeEvidence(
            current=UNKNOWN,
            prior_average=UNKNOWN,
            ratio=UNKNOWN,
            unit=UNKNOWN,
            source=source,
        )
    if len(candles) < lookback + 1:
        raise ContractViolation(
            f"volume ratio requires {lookback + 1} closed Futures candles"
        )
    values = tuple(candle.volume for candle in candles[-(lookback + 1) :])
    if any(not isinstance(value, Decimal) or not value.is_finite() for value in values):
        raise ContractViolation("Futures volume must contain finite Decimal values")
    current = values[-1]
    with localcontext() as context:
        context.prec = 28
        prior_average = sum(values[:-1], Decimal(0)) / Decimal(lookback)
        ratio: Decimal | str = (
            UNKNOWN if prior_average == 0 else current / prior_average
        )
    return VolumeEvidence(
        current=current,
        prior_average=prior_average,
        ratio=ratio,
        unit="BASE_ASSET",
        source=source,
    )


def calculate_indicators(candles: Sequence[Candle]) -> IndicatorEvidence:
    """Calculate the v4 BB(20,2), ATR(14), and source-safe volume evidence."""

    if len(candles) < 21:
        raise ContractViolation("v4 indicators require 21 closed candles")
    if any(left.open_time >= right.open_time for left, right in zip(candles, candles[1:])):
        raise ContractViolation("closed candles must be strictly time ordered")
    return IndicatorEvidence(
        as_of_close_time=candles[-1].close_time,
        close=candles[-1].close,
        bollinger=bollinger_bands([candle.close for candle in candles]),
        atr=average_true_range(candles),
        volume=volume_evidence(candles),
    )
