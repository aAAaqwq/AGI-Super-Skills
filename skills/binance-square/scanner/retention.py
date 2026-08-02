"""Auditable retention planning with reconciliation as a hard delete gate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Iterable

from .contracts import ContractViolation, parse_utc


class ArtifactKind(str, Enum):
    RAW_POST = "RAW_POST"
    CANDLE = "CANDLE"
    REPORT = "REPORT"
    ERROR = "ERROR"
    AUTHOR_DAILY_AGGREGATE = "AUTHOR_DAILY_AGGREGATE"
    TIER_HISTORY = "TIER_HISTORY"


LONG_TERM_KINDS = frozenset(
    {ArtifactKind.AUTHOR_DAILY_AGGREGATE, ArtifactKind.TIER_HISTORY}
)


@dataclass(frozen=True, slots=True)
class RetentionArtifact:
    path: Path
    kind: ArtifactKind
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RetentionPlan:
    as_of: datetime
    retention_days: int
    dry_run: bool
    retained: tuple[RetentionArtifact, ...]
    cleanup_candidates: tuple[RetentionArtifact, ...]
    aggregate_fingerprint: str


def plan_retention(
    artifacts: Iterable[RetentionArtifact],
    *,
    as_of: datetime,
    aggregate_before: str,
    aggregate_after: str,
    retention_days: int = 60,
    dry_run: bool = True,
) -> RetentionPlan:
    """Keep day 60, select day 61+, and refuse an unreconciled plan."""

    if not aggregate_before or aggregate_before != aggregate_after:
        raise ContractViolation("long-term aggregate reconciliation failed")
    if retention_days < 1:
        raise ContractViolation("retention days must be positive")
    decision_at = parse_utc(as_of)
    cutoff = decision_at - timedelta(days=retention_days)
    retained: list[RetentionArtifact] = []
    cleanup: list[RetentionArtifact] = []
    for artifact in artifacts:
        if artifact.kind in LONG_TERM_KINDS or parse_utc(artifact.created_at) >= cutoff:
            retained.append(artifact)
        else:
            cleanup.append(artifact)
    return RetentionPlan(
        as_of=decision_at,
        retention_days=retention_days,
        dry_run=dry_run,
        retained=tuple(retained),
        cleanup_candidates=tuple(cleanup),
        aggregate_fingerprint=aggregate_before,
    )
