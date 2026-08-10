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


class ExecutionReadinessStatus(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNAVAILABLE = "UNAVAILABLE"
    COST_ADJUSTED_RR_BELOW_MINIMUM = "COST_ADJUSTED_RR_BELOW_MINIMUM"
    READY = "READY"


class CostModelStatus(str, Enum):
    NOT_CONFIGURED = "NOT_CONFIGURED"
    UNAVAILABLE = "UNAVAILABLE"
    APPLIED = "APPLIED"


@dataclass(frozen=True, slots=True)
class ExecutionCostConfig:
    """Injected execution assumptions; defaults never invent live costs."""

    fee_rate: Decimal | None = None
    slippage_rate: Decimal | None = None
    funding_rate: Decimal | None = None
    depth_available: bool | None = None

    def __post_init__(self) -> None:
        for value in (self.fee_rate, self.slippage_rate, self.funding_rate):
            if value is not None and (
                not isinstance(value, Decimal)
                or not value.is_finite()
                or value < 0
                or value > 1
            ):
                raise ContractViolation(
                    "execution cost rates must be finite Decimals between zero and one"
                )
        if self.depth_available is not None and not isinstance(
            self.depth_available, bool
        ):
            raise ContractViolation("depth_available must be bool or None")


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
    content_hash: str | None = None
    execution_readiness_status: ExecutionReadinessStatus = (
        ExecutionReadinessStatus.NOT_CONFIGURED
    )
    cost_adjusted_main_rr: Decimal | None = None
    execution_ready: bool = False
    cost_model_status: CostModelStatus = CostModelStatus.NOT_CONFIGURED
    evidence_captured_at: datetime | None = None
    source_detail_captured_at: datetime | None = None

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
) -> tuple[int, int, tuple[str, ...], str | None]:
    if snapshot is None:
        return 0, 0, ("market_evidence=UNAVAILABLE",), None
    desired = "BULLISH" if candidate.direction is Direction.LONG else "BEARISH"
    labels = {interval: _trend_label(snapshot, interval) for interval in INTERVALS}
    evidence = [f"{interval}_trend={labels[interval]}" for interval in INTERVALS]
    trend_score = 5 * sum(label == desired for label in labels.values())

    bb_score = 0
    one_hour_volume: Decimal | str = UNKNOWN
    one_hour_bandwidth: Decimal | str = UNKNOWN
    one_hour_breakout = False
    for interval in INTERVALS:
        candles = snapshot.candles.get(interval, ())
        try:
            indicator = calculate_indicators(candles)
        except ContractViolation:
            evidence.append(f"{interval}_indicators=UNKNOWN")
            continue
        percent_b = indicator.bollinger.percent_b
        evidence.append(f"{interval}_bb_percent_b={percent_b}")
        evidence.append(f"{interval}_bb_bandwidth={indicator.bollinger.bandwidth}")
        if isinstance(percent_b, Decimal):
            if candidate.direction is Direction.LONG and percent_b >= Decimal("0.5"):
                bb_score += 1
            if candidate.direction is Direction.SHORT and percent_b <= Decimal("0.5"):
                bb_score += 1
        if interval == "1h":
            one_hour_volume = indicator.volume.ratio
            one_hour_bandwidth = indicator.bollinger.bandwidth
            one_hour_breakout = (
                indicator.close >= indicator.bollinger.upper
                if candidate.direction is Direction.LONG
                else indicator.close <= indicator.bollinger.lower
            )
            evidence.append(
                f"1h_volume_ratio={one_hour_volume};source={indicator.volume.source.value}"
            )

    volume_score = 0
    if snapshot.source is MarketSource.FUTURES and isinstance(one_hour_volume, Decimal):
        if one_hour_volume >= Decimal("1.2"):
            volume_score = 4
        elif one_hour_volume >= Decimal("1"):
            volume_score = 2
    squeeze = (
        isinstance(one_hour_bandwidth, Decimal)
        and one_hour_bandwidth <= Decimal("0.01")
    )
    confirmed_squeeze_breakout = (
        squeeze
        and one_hour_breakout
        and isinstance(one_hour_volume, Decimal)
        and one_hour_volume >= Decimal("1.2")
    )
    waiting_condition = None
    if squeeze and not confirmed_squeeze_breakout:
        evidence.append("1h_bb_state=SQUEEZE_NO_BREAKOUT")
        waiting_condition = "BB_SQUEEZE_AWAITING_BREAKOUT"
    elif confirmed_squeeze_breakout:
        evidence.append("1h_bb_state=SQUEEZE_BREAKOUT_CONFIRMED")
    else:
        evidence.append("1h_bb_state=NORMAL")
    breakout_score = (
        2
        if labels["1h"] == desired
        and labels["4h"] == desired
        and (not squeeze or confirmed_squeeze_breakout)
        else 0
    )
    return (
        trend_score,
        min(10, bb_score + volume_score + breakout_score),
        tuple(evidence),
        waiting_condition,
    )


def _rr_score_and_gates(candidate: SignalCandidate) -> tuple[int, RiskReward | None, list[str]]:
    missing: list[str] = []
    if candidate.entry_price is None:
        missing.append("MISSING_ENTRY")
    if candidate.stop_loss is None:
        missing.append("MISSING_STOP_LOSS")
    if candidate.tp1 is None:
        missing.append("MISSING_TP1")
    if missing:
        partial_score = max(0, 5 - len(missing) * 1)
        return partial_score, None, []
    try:
        rr = calculate_risk_reward(candidate)
    except ContractViolation:
        return 0, None, ["INVALID_PRICE_GEOMETRY"]
    gates: list[str] = []
    score = 5
    if rr.tp1_rr >= Decimal("1.2"):
        score += 5
    if rr.main_target_rr >= Decimal("1.5"):
        score += 5
    else:
        gates.append("MAIN_TARGET_RR_BELOW_1_5")
    return score, rr, gates


def _signal_invalidated(candidate: SignalCandidate, price: Decimal, rr: RiskReward | None) -> bool:
    if candidate.stop_loss is None or rr is None:
        return False
    if candidate.direction is Direction.LONG:
        return price <= candidate.stop_loss or price >= rr.main_target
    return price >= candidate.stop_loss or price <= rr.main_target


def _execution_readiness(
    candidate: SignalCandidate,
    rr: RiskReward | None,
    costs: ExecutionCostConfig | None,
) -> tuple[ExecutionReadinessStatus, Decimal | None, str | None, tuple[str, ...]]:
    if costs is None or any(
        value is None
        for value in (costs.fee_rate, costs.slippage_rate, costs.funding_rate)
    ) or costs.depth_available is None:
        return (
            ExecutionReadinessStatus.NOT_CONFIGURED,
            None,
            "EXECUTION_COSTS_NOT_CONFIGURED",
            ("execution_cost_status=NOT_CONFIGURED",),
        )
    if not costs.depth_available:
        return (
            ExecutionReadinessStatus.UNAVAILABLE,
            None,
            "EXECUTION_DEPTH_UNAVAILABLE",
            ("execution_cost_status=UNAVAILABLE;depth=UNAVAILABLE",),
        )
    if rr is None or candidate.entry_price is None:
        return (
            ExecutionReadinessStatus.UNAVAILABLE,
            None,
            "NOMINAL_RR_UNAVAILABLE",
            ("execution_cost_status=UNAVAILABLE;nominal_rr=UNAVAILABLE",),
        )
    assert costs.fee_rate is not None
    assert costs.slippage_rate is not None
    assert costs.funding_rate is not None
    total_cost_rate = (
        Decimal(2) * (costs.fee_rate + costs.slippage_rate)
        + abs(costs.funding_rate)
    )
    adjusted_rr = rr.main_target_rr - (
        candidate.entry_price * total_cost_rate / rr.risk
    )
    evidence = (
        "execution_cost_status=CONFIGURED",
        f"round_trip_fee_rate={costs.fee_rate * Decimal(2)}",
        f"round_trip_slippage_rate={costs.slippage_rate * Decimal(2)}",
        f"funding_cost_rate={abs(costs.funding_rate)}",
        "depth=AVAILABLE",
        f"cost_adjusted_main_rr={adjusted_rr}",
    )
    if adjusted_rr < Decimal("2"):
        return (
            ExecutionReadinessStatus.COST_ADJUSTED_RR_BELOW_MINIMUM,
            adjusted_rr,
            "COST_ADJUSTED_RR_BELOW_2",
            evidence,
        )
    return ExecutionReadinessStatus.READY, adjusted_rr, None, evidence


def _bucket(total: int, hard_gates: Iterable[str]) -> RankBucket:
    if tuple(hard_gates):
        return RankBucket.FILTER
    if total >= 55:
        return RankBucket.TOP
    if total >= 40:
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
    execution_costs: ExecutionCostConfig | None = None,
    evidence_captured_at: datetime | str | None = None,
    source_detail_captured_at: datetime | str | None = None,
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

    trend_score, confirmation_score, market_evidence, market_waiting = _market_scores(
        candidate, market
    )
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
    readiness_status, adjusted_rr, cost_waiting, cost_evidence = (
        _execution_readiness(candidate, rr, execution_costs)
    )
    if readiness_status is ExecutionReadinessStatus.NOT_CONFIGURED:
        cost_model_status = CostModelStatus.NOT_CONFIGURED
    elif readiness_status is ExecutionReadinessStatus.UNAVAILABLE:
        cost_model_status = CostModelStatus.UNAVAILABLE
    else:
        cost_model_status = CostModelStatus.APPLIED
    source_detail_time = (
        parse_utc(source_detail_captured_at)
        if source_detail_captured_at is not None
        else None
    )
    evidence_time = (
        parse_utc(evidence_captured_at)
        if evidence_captured_at is not None
        else source_detail_time
    )
    rr_evidence = () if rr is None else (
        f"tp1_rr={rr.tp1_rr}",
        f"main_target_rr={rr.main_target_rr}",
    )
    evidence = market_evidence + rr_evidence + cost_evidence + (
        f"author_parameter_evidence={candidate.parameter_evidence_source.value}",
        f"consensus_distinct_other_authors={consensus_count}",
    )
    rank_bucket = _bucket(breakdown.total, unique_gates)
    capture_waiting = (
        "EVIDENCE_CAPTURE_TIMESTAMPS_NOT_CONFIGURED"
        if evidence_time is None or source_detail_time is None
        else None
    )
    waiting_condition = market_waiting or cost_waiting or capture_waiting
    if rank_bucket is RankBucket.TOP and waiting_condition is not None:
        rank_bucket = RankBucket.WATCH
    return ScoredOpportunity(
        candidate=candidate,
        score_breakdown=breakdown,
        total_score=breakdown.total,
        rank_bucket=rank_bucket,
        hard_gate_reasons=unique_gates,
        evidence=evidence,
        current_price=market.last_price if market is not None else None,
        market_source=market.source if market is not None else None,
        market_captured_at=market.captured_at if market is not None else None,
        missing_market_fields=market.missing_fields if market is not None else (),
        waiting_condition=waiting_condition,
        content_hash=(content_hash.strip() if isinstance(content_hash, str) and content_hash.strip() else None),
        execution_readiness_status=readiness_status,
        cost_adjusted_main_rr=adjusted_rr,
        execution_ready=(
            rank_bucket is RankBucket.TOP
            and readiness_status is ExecutionReadinessStatus.READY
        ),
        cost_model_status=cost_model_status,
        evidence_captured_at=evidence_time,
        source_detail_captured_at=source_detail_time,
    )


def _stable_key(value: ScoredOpportunity) -> tuple[int, str, str, str]:
    return (-value.total_score, value.symbol, value.direction.value, value.signal_id)


def _independent_direction_contributors(
    values: Iterable[ScoredOpportunity],
) -> tuple[tuple[ScoredOpportunity, ...], tuple[ScoredOpportunity, ...]]:
    """Select at most one post per stable author and content cluster."""

    contributors: list[ScoredOpportunity] = []
    duplicates: list[ScoredOpportunity] = []
    seen_authors: set[str] = set()
    seen_clusters: set[str] = set()
    for value in sorted(values, key=_stable_key):
        raw_author = value.candidate.author_id
        author_id = (
            raw_author.strip()
            if isinstance(raw_author, str)
            and raw_author.strip()
            and raw_author.strip().upper() != "LIVE"
            else "UNKNOWN_AUTHOR"
        )
        content_cluster = value.content_hash or "UNKNOWN_CONTENT_CLUSTER"
        if author_id in seen_authors or content_cluster in seen_clusters:
            duplicates.append(value)
            continue
        contributors.append(value)
        seen_authors.add(author_id)
        seen_clusters.add(content_cluster)
    return tuple(contributors), tuple(duplicates)


def _top_readiness_waiting(value: ScoredOpportunity) -> str | None:
    if value.cost_model_status != CostModelStatus.APPLIED:
        return "EXECUTION_READINESS_NOT_APPLIED"
    if (
        value.evidence_captured_at is None
        or value.source_detail_captured_at is None
    ):
        return "EVIDENCE_CAPTURE_TIMESTAMPS_NOT_CONFIGURED"
    if not value.execution_ready:
        return "EXECUTION_READINESS_NOT_APPLIED"
    return None


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
        by_direction: dict[Direction, list[ScoredOpportunity]] = {}
        for value in values:
            by_direction.setdefault(value.direction, []).append(value)
        aggregates: list[
            tuple[ScoredOpportunity, tuple[ScoredOpportunity, ...], int]
        ] = []
        for direction in sorted(by_direction, key=lambda item: item.value):
            direction_values = by_direction[direction]
            contributors, duplicates = _independent_direction_contributors(
                direction_values
            )
            representative = contributors[0]
            aggregates.append(
                (
                    representative,
                    contributors,
                    sum(value.total_score for value in contributors),
                )
            )
            contributor_ids = {value.signal_id for value in contributors}
            for value in direction_values:
                if value.signal_id == representative.signal_id:
                    continue
                reason = (
                    "AGGREGATED_SAME_DIRECTION_SUPPORT"
                    if value.signal_id in contributor_ids
                    else "DUPLICATE_AUTHOR_OR_CONTENT_CLUSTER"
                )
                filtered.append(
                    replace(
                        value,
                        rank_bucket=RankBucket.FILTER,
                        waiting_condition=reason,
                    )
                )
        aggregates.sort(key=lambda item: (-item[2], _stable_key(item[0])))
        if len(aggregates) == 2:
            (winner, winner_support, winner_strength), (
                loser,
                loser_support,
                loser_strength,
            ) = aggregates
            margin = winner_strength - loser_strength
            conflict = (
                f"opposing_direction_margin={margin}",
                f"leading_independent_support={len(winner_support)}",
                f"opposing_independent_support={len(loser_support)}",
                f"leading_aggregate_strength={winner_strength}",
                f"opposing_direction={loser.direction.value};aggregate_strength={loser_strength}",
            )
            winner = replace(winner, conflict_evidence=conflict)
            loser = replace(
                loser,
                rank_bucket=RankBucket.FILTER,
                conflict_evidence=(
                    f"opposing_direction_margin={margin}",
                    f"leading_direction={winner.direction.value};aggregate_strength={winner_strength}",
                ),
                waiting_condition="OPPOSING_DIRECTION_CONFLICT",
            )
            filtered.append(loser)
            readiness_waiting = _top_readiness_waiting(winner)
            if (
                winner.total_score >= 55
                and margin >= 10
                and winner.waiting_condition is None
                and readiness_waiting is None
            ):
                provisional_top.append(replace(winner, rank_bucket=RankBucket.TOP))
            elif winner.total_score >= 40:
                provisional_watch.append(
                    replace(
                        winner,
                        rank_bucket=RankBucket.WATCH,
                        waiting_condition=(
                            winner.waiting_condition
                            or readiness_waiting
                            or "CONFLICT_MARGIN_BELOW_10_OR_NO_55_DIRECTION"
                        ),
                    )
                )
            else:
                filtered.append(replace(winner, rank_bucket=RankBucket.FILTER))
            continue

        value = aggregates[0][0]
        natural = _bucket(value.total_score, ())
        if natural is RankBucket.TOP:
            readiness_waiting = _top_readiness_waiting(value)
            waiting_condition = value.waiting_condition or readiness_waiting
            if waiting_condition is not None:
                natural = RankBucket.WATCH
                value = replace(value, waiting_condition=waiting_condition)
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
    "CostModelStatus",
    "ExecutionCostConfig",
    "ExecutionReadinessStatus",
    "OpportunityBoard",
    "RankBucket",
    "ScoreBreakdown",
    "ScoredOpportunity",
    "build_opportunity_board",
    "score_opportunity",
]
