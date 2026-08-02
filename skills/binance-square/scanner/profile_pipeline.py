"""Fail-closed Smart Money identity mapping to public Square Profile outcomes."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Iterable

from .authors import (
    SmartMoneySquareIdentityEvidence,
    SmartMoneySquareIdentityMapping,
)
from .contracts import ContractViolation, format_utc
from .discovery import ChannelObservation, parse_profile_content_response


PROFILE_PROVENANCE = frozenset({"LIVE_CAPTURE", "FIXTURE_REPLAY"})


@dataclass(frozen=True, slots=True)
class ProfilePipelineOutcome:
    top_trader_id: str
    square_uid: str | None
    status: str
    post_count: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ProfilePipelineResult:
    status: str
    reason: str
    provenance: str
    source_capture_time_utc: str | None
    mapping_covered: int
    mapping_expected: int
    tier_a_eligible: int
    mapping_evidence_path: str | None
    mapping_evidence_sha256: str | None
    identity_mappings: tuple[SmartMoneySquareIdentityMapping, ...]
    outcomes: tuple[ProfilePipelineOutcome, ...]
    observations: tuple[ChannelObservation, ...]

    def identity_mapping_records(self) -> tuple[dict[str, str], ...]:
        """Return the exact keyword contract expected by ledger persistence."""

        if self.mapping_evidence_path is None or self.mapping_evidence_sha256 is None:
            return ()
        return tuple(
            {
                "top_trader_id": mapping.top_trader_id,
                "author_id": mapping.square_uid,
                "verified_at": mapping.verified_at,
                "evidence_path": self.mapping_evidence_path,
                "evidence_sha256": self.mapping_evidence_sha256,
            }
            for mapping in self.identity_mappings
        )

    def as_report_contract(self) -> dict[str, Any]:
        counts = {
            status: sum(outcome.status == status for outcome in self.outcomes)
            for status in ("COMPLETE", "EMPTY", "PARTIAL", "FAILED", "NOT_ATTEMPTED")
        }
        return {
            "status": self.status,
            "reason": self.reason,
            "provenance": self.provenance,
            "source_capture_time_utc": self.source_capture_time_utc,
            "evidence_path": self.mapping_evidence_path,
            "square_identity_mapping_coverage": {
                "covered": self.mapping_covered,
                "expected": self.mapping_expected,
                "label": f"{self.mapping_covered}/{self.mapping_expected}",
                "status": (
                    "COMPLETE"
                    if self.mapping_expected and self.mapping_covered == self.mapping_expected
                    else "PARTIAL"
                    if self.mapping_covered
                    else "NOT_ATTEMPTED"
                ),
                "verification_method": "EXPLICIT_SOURCE_EVIDENCE_ONLY",
                "evidence_path": self.mapping_evidence_path,
                "evidence_sha256": self.mapping_evidence_sha256,
            },
            "planned_authors": self.mapping_expected,
            "complete_authors": counts["COMPLETE"],
            "empty_authors": counts["EMPTY"],
            "partial_authors": counts["PARTIAL"],
            "failed_authors": counts["FAILED"],
            "not_attempted_authors": counts["NOT_ATTEMPTED"],
            "source_records": sum(item.post_count for item in self.outcomes),
            "tier_a_eligible": self.tier_a_eligible,
            "outcomes": [asdict(item) for item in self.outcomes],
            "observations": [asdict(item) for item in self.observations],
        }


def _top_trader_ids(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise ContractViolation(f"top_trader_ids[{index}] must be non-empty")
        source_id = value.strip()
        if source_id in seen:
            raise ContractViolation(f"duplicate topTraderId: {source_id}")
        seen.add(source_id)
        result.append(source_id)
    return tuple(result)


def run_profile_pipeline(
    top_trader_ids: Iterable[str],
    *,
    mapping_evidence: SmartMoneySquareIdentityEvidence | None,
    fetch_profile_contents: Callable[[str], dict[str, Any]] | None,
    source_capture_time_utc: str | None,
    provenance: str,
) -> ProfilePipelineResult:
    """Return a reconciled result slot for every Smart Money identity.

    The fetch callback receives only an explicitly mapped ``squareUid``.  When
    mapping evidence is absent, the callback is never invoked.
    """

    source_ids = _top_trader_ids(top_trader_ids)
    normalized_provenance = str(provenance).upper()
    if normalized_provenance not in PROFILE_PROVENANCE:
        raise ContractViolation(
            "Profile provenance must be LIVE_CAPTURE or FIXTURE_REPLAY"
        )
    if mapping_evidence is None:
        return ProfilePipelineResult(
            status="NOT_ATTEMPTED",
            reason="no_explicit_topTraderId_to_squareUid_mapping",
            provenance=normalized_provenance,
            source_capture_time_utc=None,
            mapping_covered=0,
            mapping_expected=len(source_ids),
            tier_a_eligible=0,
            mapping_evidence_path=None,
            mapping_evidence_sha256=None,
            identity_mappings=(),
            outcomes=tuple(
                ProfilePipelineOutcome(source_id, None, "NOT_ATTEMPTED", 0)
                for source_id in source_ids
            ),
            observations=(),
        )

    mapping_by_trader = {
        mapping.top_trader_id: mapping.square_uid
        for mapping in mapping_evidence.mappings
        if mapping.top_trader_id in source_ids
    }
    accepted_mappings = tuple(
        mapping
        for mapping in mapping_evidence.mappings
        if mapping.top_trader_id in source_ids
    )
    mapping_covered = len(mapping_by_trader)
    if fetch_profile_contents is not None and mapping_covered:
        if source_capture_time_utc is None:
            raise ContractViolation(
                "Profile collection requires an explicit source_capture_time_utc"
            )
        try:
            captured_at = format_utc(source_capture_time_utc)
        except ContractViolation as exc:
            raise ContractViolation(
                "Profile source_capture_time_utc must be timezone-aware"
            ) from exc
    else:
        captured_at = None

    outcomes: list[ProfilePipelineOutcome] = []
    observations: list[ChannelObservation] = []
    for top_trader_id in source_ids:
        square_uid = mapping_by_trader.get(top_trader_id)
        if square_uid is None:
            outcomes.append(
                ProfilePipelineOutcome(
                    top_trader_id,
                    None,
                    "NOT_ATTEMPTED",
                    0,
                    "no_explicit_identity_mapping",
                )
            )
            continue
        if fetch_profile_contents is None:
            outcomes.append(
                ProfilePipelineOutcome(
                    top_trader_id,
                    square_uid,
                    "NOT_ATTEMPTED",
                    0,
                    "profile_fetcher_not_supplied",
                )
            )
            continue
        try:
            payload = fetch_profile_contents(square_uid)
            if not isinstance(payload, dict):
                raise ContractViolation("Profile response root must be an object")
            profile_observations = parse_profile_content_response(
                payload,
                author_id=square_uid,
            )
        except Exception as exc:
            outcomes.append(
                ProfilePipelineOutcome(
                    top_trader_id,
                    square_uid,
                    "FAILED",
                    0,
                    f"{type(exc).__name__}: {exc}"[:300],
                )
            )
            continue
        observations.extend(profile_observations)
        outcomes.append(
            ProfilePipelineOutcome(
                top_trader_id,
                square_uid,
                "COMPLETE" if profile_observations else "EMPTY",
                len(profile_observations),
            )
        )

    successful = {"COMPLETE", "EMPTY"}
    if not mapping_covered or fetch_profile_contents is None:
        status = "NOT_ATTEMPTED"
        reason = (
            "no_expected_topTraderId_has_explicit_mapping"
            if not mapping_covered
            else "profile_fetcher_not_supplied"
        )
    elif mapping_covered == len(source_ids) and all(
        outcome.status in successful for outcome in outcomes
    ):
        status = "COMPLETE"
        reason = "all_explicitly_mapped_profiles_reconciled"
    elif mapping_covered == len(source_ids) and all(
        outcome.status == "FAILED" for outcome in outcomes
    ):
        status = "FAILED"
        reason = "all_explicitly_mapped_profile_fetches_failed"
    else:
        status = "PARTIAL"
        reason = "identity_mapping_or_profile_outcomes_are_partial"
    return ProfilePipelineResult(
        status=status,
        reason=reason,
        provenance=normalized_provenance,
        source_capture_time_utc=captured_at,
        mapping_covered=mapping_covered,
        mapping_expected=len(source_ids),
        tier_a_eligible=0,
        mapping_evidence_path=mapping_evidence.evidence_path,
        mapping_evidence_sha256=mapping_evidence.evidence_sha256,
        identity_mappings=accepted_mappings,
        outcomes=tuple(outcomes),
        observations=tuple(observations),
    )


__all__ = [
    "PROFILE_PROVENANCE",
    "ProfilePipelineOutcome",
    "ProfilePipelineResult",
    "run_profile_pipeline",
]
