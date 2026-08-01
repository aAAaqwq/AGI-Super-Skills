"""Deterministic v4 opportunity scoring over point-in-time evidence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Iterable, Mapping

from .authors import AuthorProfile
from .contracts import ContractViolation, parse_utc
from .indicators import calculate_indicators
from .market import INTERVALS, UNKNOWN, MarketSnapshot, MarketSource
from .opportunities import (
    ConsensusIndex,
    Direction,
    RiskReward,
    SignalCandidate,
    calculate_risk_reward,
)


class RankBucket(str, Enum):
    TOP = "TOP"
    WATCH = "WATCH"
    FILTER = "FILTER"


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    author_credibility: int
    post_completeness: int
    freshness: int
    trend_alignment: int
    market_confirmation: int
    risk_reward: int
    news_or_consensus: int

    def as_dict(self) -> dict[str, int]:
        return {
            "author_credibility": self.author_credibility,
            "post_completeness": self.post_completeness,
            "freshness": self.freshness,
            "trend_alignment": self.trend_alignment,
            "market_confirmation": self.market_confirmation,
            "risk_reward": self.risk_reward,
            "news_or_consensus": self.news_or_consensus,
        }

    @property
    def total(self) -> int:
        return sum(self.as_dict().values())


@dataclass(frozen=True, slots=True)
class ScoredOpportunity:
    candidate: SignalCandidate
    score_breakdown: ScoreBreakdown
    total_score: int
    rank_bucket: RankBucket
    hard_gate_reasons: tuple[str, ...]
    evidence: tuple[str, ...]
    current_price: Decimal | None
    market_source: MarketSource | None
    market_captured_at: datetime | None
    missing_market_fields: tuple[str, ...]
    conflict_evidence: tuple[str, ...] = ()
    waiting_condition: str | None = None

    @property
    def signal_id(self) -> str:
        return self.candidate.signal_id

    @property
    def symbol(self) -> str:
        return self.candidate.symbol

    @property
    def direction(self) -> Direction:
        return self.candidate.direction

    @property
    def entry_low(self) -> Decimal | None:
        return self.candidate.entry_low

    @property
    def entry_high(self) -> Decimal | None:
        return self.candidate.entry_high

    @property
    def entry_price(self) -> Decimal | None:
        return self.candidate.entry_price

    @property
    def entry_zone(self) -> tuple[Decimal | None, Decimal | None]:
        return (self.candidate.entry_low, self.candidate.entry_high)

    @property
    def stop_loss(self) -> Decimal | None:
        return self.candidate.stop_loss

    @property
    def tp1(self) -> Decimal | None:
        return self.candidate.tp1

    @property
    def tp2(self) -> Decimal | None:
        return self.candidate.tp2

    @property
    def post_url(self) -> str:
        return self.candidate.post_url

    @property
    def invalidation(self) -> str | None:
        return self.candidate.invalidation

    @property
    def filter_reason(self) -> str | None:
        if self.hard_gate_reasons:
            return ",".join(self.hard_gate_reasons)
        return self.waiting_condition


@dataclass(frozen=True, slots=True)
class OpportunityBoard:
    top: tuple[ScoredOpportunity, ...]
    watch: tuple[ScoredOpportunity, ...]
    filtered: tuple[ScoredOpportunity, ...]
    concentration_risk: tuple[str, ...] = ()


def _author_score(author: AuthorProfile | None) -> int:
    if author is None:
        return 0
    status = author.tier_status.upper()
    if "PROBATION" in status or "EXTERNAL_VERIFIED" in status:
        return 20
    if status in {"A", "TIER_A", "A_VERIFIED", "VERIFIED_A"}:
        return 25
    if status == "B" or status.startswith("TIER_B"):
        return 15
    if status == "C" or status.startswith("TIER_C"):
        return 5
    return 0


def _completeness(candidate: SignalCandidate) -> int:
    return min(
        15,
        2
        + (2 if candidate.entry_price is not None else 0)
        + (2 if candidate.stop_loss is not None else 0)
        + (2 if candidate.tp1 is not None else 0)
        + (2 if candidate.tp2 is not None else 0)
        + (2 if candidate.invalidation else 0)
        + (3 if candidate.rationale else 0),
    )


def _freshness(candidate: SignalCandidate, decision_at: datetime) -> tuple[int, bool]:
    age = decision_at - parse_utc(candidate.published_at)
    hours = Decimal(str(age.total_seconds())) / Decimal(3600)
    if hours < 0 or hours >= 24:
        return 0, False
    if hours < 4:
        return 10, True
    if hours < 8:
        return 8, True
    if hours < 12:
        return 6, True
    return 4, True


def _trend_label(snapshot: MarketSnapshot, interval: str) -> str:
    candles = snapshot.candles.get(interval, ())
    if len(candles) < 2:
        return "UNKNOWN"
    if candles[-1].close > candles[0].close:
        return "BULLISH"
    if candles[-1].close < candles[0].close:
        return "BEARISH"
    return "FLAT"


def _market_scores(
    candidate: SignalCandidate, snapshot: MarketSnapshot | None
) -> tuple[int, int, tuple[str, ...]]:
    if snapshot is None:
        return 0, 0, ("market_evidence=UNAVAILABLE",)
    desired = "BULLISH" if candidate.direction is Direction.LONG else "BEARISH"
    labels = {interval: _trend_label(snapshot, interval) for interval in INTERVALS}
    evidence = [f"{interval}_trend={labels[interval]}" for interval in INTERVALS]
    trend_score = 5 * sum(label == desired for label in labels.values())

    bb_score = 0
    one_hour_volume: Decimal | str = UNKNOWN
    for interval in INTERVALS:
        candles = snapshot.candles.get(interval, ())
        try:
            indicator = calculate_indicators(candles)
        except ContractViolation:
            evidence.append(f"{interval}_indicators=UNKNOWN")
            continue
        percent_b = indicator.bollinger.percent_b
        evidence.append(f"{interval}_bb_percent_b={percent_b}")
        if isinstance(percent_b, Decimal):
            if candidate.direction is Direction.LONG and percent_b >= Decimal("0.5"):
                bb_score += 1
            if candidate.direction is Direction.SHORT and percent_b <= Decimal("0.5"):
                bb_score += 1
        if interval == "1h":
            one_hour_volume = indicator.volume.ratio
            evidence.append(
                f"1h_volume_ratio={one_hour_volume};source={indicator.volume.source.value}"
            )

    volume_score = 0
    if snapshot.source is MarketSource.FUTURES and isinstance(one_hour_volume, Decimal):
        if one_hour_volume >= Decimal("1.2"):
            volume_score = 4
        elif one_hour_volume >= Decimal("1"):
            volume_score = 2
    breakout_score = 2 if labels["1h"] == desired and labels["4h"] == desired else 0
    return trend_score, min(10, bb_score + volume_score + breakout_score), tuple(evidence)


def _rr_score_and_gates(candidate: SignalCandidate) -> tuple[int, RiskReward | None, list[str]]:
    missing: list[str] = []
    if candidate.entry_price is None:
        missing.append("MISSING_ENTRY")
    if candidate.stop_loss is None:
        missing.append("MISSING_STOP_LOSS")
    if candidate.tp1 is None:
        missing.append("MISSING_TP1")
    if missing:
        return 0, None, missing
    try:
        rr = calculate_risk_reward(candidate)
    except ContractViolation:
        return 0, None, ["INVALID_PRICE_GEOMETRY"]
    gates: list[str] = []
    score = 5
    if rr.tp1_rr >= Decimal("1.5"):
        score += 5
    else:
        gates.append("TP1_RR_BELOW_1_5")
    if rr.main_target_rr >= Decimal("2"):
        score += 5
    else:
        gates.append("MAIN_TARGET_RR_BELOW_2")
    return score, rr, gates


def _signal_invalidated(candidate: SignalCandidate, price: Decimal, rr: RiskReward | None) -> bool:
    if candidate.stop_loss is None or rr is None:
        return False
    if candidate.direction is Direction.LONG:
        return price <= candidate.stop_loss or price >= rr.main_target
    return price >= candidate.stop_loss or price <= rr.main_target


def _bucket(total: int, hard_gates: Iterable[str]) -> RankBucket:
    if tuple(hard_gates):
        return RankBucket.FILTER
    if total >= 75:
        return RankBucket.TOP
    if total >= 65:
        return RankBucket.WATCH
    return RankBucket.FILTER


def score_opportunity(
    candidate: SignalCandidate,
    author: AuthorProfile | None,
    market: MarketSnapshot | None,
    *,
    decision_at: datetime | str | None = None,
    consensus_author_ids: Iterable[str] = (),
    consensus_index: ConsensusIndex | None = None,
    content_hash: str | None = None,
) -> ScoredOpportunity:
    """Apply the frozen 25/15/10/20/10/15/5 model and hard gates."""

    if decision_at is None:
        if market is None:
            raise ContractViolation("decision_at is required without a market snapshot")
        decision = datetime.fromtimestamp(market.decision_time_ms / 1000, tz=timezone.utc)
    else:
        decision = parse_utc(decision_at)

    gates: list[str] = []
    if market is None or market.symbol != candidate.symbol or market.contract.symbol != candidate.symbol or market.contract.status != "TRADING":
        gates.append("NO_ACTIVE_FUTURES_CONTRACT")
    freshness, fresh = _freshness(candidate, decision)
    if not fresh:
        gates.append("SIGNAL_EXPIRED")
    rr_score, rr, rr_gates = _rr_score_and_gates(candidate)
    gates.extend(rr_gates)
    if market is not None and _signal_invalidated(candidate, market.last_price, rr):
        gates.append("SIGNAL_INVALIDATED")

    trend_score, confirmation_score, market_evidence = _market_scores(candidate, market)
    stable_candidate_author = (
        candidate.author_id.strip()
        if isinstance(candidate.author_id, str)
        and candidate.author_id.strip()
        and candidate.author_id.strip().upper() != "LIVE"
        else None
    )
    independent_authors = (
        {
            value
            for value in consensus_author_ids
            if value and value != stable_candidate_author
        }
        if stable_candidate_author is not None
        else set()
    )
    if consensus_index is not None and stable_candidate_author is not None:
        independent_authors.update(
            consensus_index.other_author_ids(
                symbol=candidate.symbol,
                direction=candidate.direction,
                author_id=stable_candidate_author,
                content_hash=content_hash,
            )
        )
    consensus_count = len(independent_authors)
    consensus_score = min(5, consensus_count * 3)
    if candidate.source_class == "BINANCE_OFFICIAL":
        consensus_score = min(5, consensus_score + 2)
    breakdown = ScoreBreakdown(
        author_credibility=_author_score(author),
        post_completeness=_completeness(candidate),
        freshness=freshness,
        trend_alignment=trend_score,
        market_confirmation=confirmation_score,
        risk_reward=rr_score,
        news_or_consensus=consensus_score,
    )
    unique_gates = tuple(dict.fromkeys(gates))
    rr_evidence = () if rr is None else (
        f"tp1_rr={rr.tp1_rr}",
        f"main_target_rr={rr.main_target_rr}",
    )
    evidence = market_evidence + rr_evidence + (
        f"author_parameter_evidence={candidate.parameter_evidence_source.value}",
        f"consensus_distinct_other_authors={consensus_count}",
    )
    return ScoredOpportunity(
        candidate=candidate,
        score_breakdown=breakdown,
        total_score=breakdown.total,
        rank_bucket=_bucket(breakdown.total, unique_gates),
        hard_gate_reasons=unique_gates,
        evidence=evidence,
        current_price=market.last_price if market is not None else None,
        market_source=market.source if market is not None else None,
        market_captured_at=market.captured_at if market is not None else None,
        missing_market_fields=market.missing_fields if market is not None else (),
    )


def _stable_key(value: ScoredOpportunity) -> tuple[int, str, str, str]:
    return (-value.total_score, value.symbol, value.direction.value, value.signal_id)


def build_opportunity_board(
    opportunities: Iterable[ScoredOpportunity],
    *,
    top_limit: int = 3,
    watch_limit: int = 5,
    concentration_risk: Iterable[str] = (),
) -> OpportunityBoard:
    """Resolve same-symbol conflicts, then apply stable TOP/WATCH limits.

    Correlation disclosures are carried separately and never affect ordering.
    """

    if top_limit < 0 or watch_limit < 0:
        raise ContractViolation("board limits cannot be negative")
    ordered = sorted(opportunities, key=_stable_key)
    filtered: list[ScoredOpportunity] = [
        replace(value, rank_bucket=RankBucket.FILTER)
        for value in ordered
        if value.hard_gate_reasons
    ]
    eligible = [value for value in ordered if not value.hard_gate_reasons]
    by_symbol: dict[str, list[ScoredOpportunity]] = {}
    for value in eligible:
        by_symbol.setdefault(value.symbol, []).append(value)

    provisional_top: list[ScoredOpportunity] = []
    provisional_watch: list[ScoredOpportunity] = []
    for symbol in sorted(by_symbol):
        values = by_symbol[symbol]
        best_by_direction: dict[Direction, ScoredOpportunity] = {}
        for value in values:
            if value.direction not in best_by_direction:
                best_by_direction[value.direction] = value
            else:
                filtered.append(
                    replace(
                        value,
                        rank_bucket=RankBucket.FILTER,
                        waiting_condition="LOWER_RANKED_SAME_DIRECTION",
                    )
                )
        directional = sorted(best_by_direction.values(), key=_stable_key)
        if len(directional) == 2:
            winner, loser = directional
            margin = winner.total_score - loser.total_score
            conflict = (
                f"opposing_direction_margin={margin}",
                f"opposing_direction={loser.direction.value};score={loser.total_score}",
            )
            winner = replace(winner, conflict_evidence=conflict)
            loser = replace(
                loser,
                rank_bucket=RankBucket.FILTER,
                conflict_evidence=(
                    f"opposing_direction_margin={margin}",
                    f"leading_direction={winner.direction.value};score={winner.total_score}",
                ),
                waiting_condition="OPPOSING_DIRECTION_CONFLICT",
            )
            filtered.append(loser)
            if winner.total_score >= 75 and margin >= 10:
                provisional_top.append(replace(winner, rank_bucket=RankBucket.TOP))
            elif winner.total_score >= 65:
                provisional_watch.append(
                    replace(
                        winner,
                        rank_bucket=RankBucket.WATCH,
                        waiting_condition="CONFLICT_MARGIN_BELOW_10_OR_NO_75_DIRECTION",
                    )
                )
            else:
                filtered.append(replace(winner, rank_bucket=RankBucket.FILTER))
            continue

        value = directional[0]
        natural = _bucket(value.total_score, ())
        if natural is RankBucket.TOP:
            provisional_top.append(replace(value, rank_bucket=natural))
        elif natural is RankBucket.WATCH:
            provisional_watch.append(replace(value, rank_bucket=natural))
        else:
            filtered.append(replace(value, rank_bucket=RankBucket.FILTER))

    provisional_top.sort(key=_stable_key)
    top = provisional_top[:top_limit]
    overflow_top = [
        replace(
            value,
            rank_bucket=RankBucket.WATCH,
            waiting_condition="TOP_LIMIT_REACHED",
        )
        for value in provisional_top[top_limit:]
    ]
    provisional_watch.extend(overflow_top)
    provisional_watch.sort(key=_stable_key)
    watch = provisional_watch[:watch_limit]
    filtered.extend(
        replace(
            value,
            rank_bucket=RankBucket.FILTER,
            waiting_condition="WATCH_LIMIT_REACHED",
        )
        for value in provisional_watch[watch_limit:]
    )
    filtered.sort(key=_stable_key)
    return OpportunityBoard(
        top=tuple(top),
        watch=tuple(watch),
        filtered=tuple(filtered),
        concentration_risk=tuple(concentration_risk),
    )


__all__ = [
    "OpportunityBoard",
    "RankBucket",
    "ScoreBreakdown",
    "ScoredOpportunity",
    "build_opportunity_board",
    "score_opportunity",
]
