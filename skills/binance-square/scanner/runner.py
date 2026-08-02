"""Deterministic, shadow-only scheduling and retry orchestration contracts.

This module deliberately owns no clock, scheduler, network client, browser,
database, or message transport.  Time and attempt execution are injected by
callers.  Delivery and alert intents remain in memory as ``HELD/NO_SEND``
DTOs; the current SQLite outbox cannot persist a ``HELD`` state safely.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from hashlib import sha256
from typing import Any, Callable, Mapping

from .contracts import ContractViolation, format_utc, parse_utc


UTC_SLOT_HOURS = (0, 4, 8, 12, 16, 20)
RETRY_DELAY = timedelta(minutes=10)
OUTBOX_HOLD_REASON = (
    "delivery_outbox schema has no HELD status; external write is disabled"
)


class CycleMode(str, Enum):
    """A shadow production slot or an isolated offline replay."""

    PRODUCTION_SHADOW = "PRODUCTION_SHADOW"
    REPLAY = "REPLAY"


class CycleStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    FAILED_TERMINAL = "FAILED_TERMINAL"


class AttemptStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class FailureStage(str, Enum):
    """Explicit operational stages suitable for a terminal alert."""

    CHROME = "CHROME"
    FETCH = "FETCH"
    MARKET_API = "MARKET_API"
    ANALYSIS = "ANALYSIS"
    REPORT = "REPORT"
    MESSAGE_DELIVERY = "MESSAGE_DELIVERY"
    ORCHESTRATION = "ORCHESTRATION"


class IntentStatus(str, Enum):
    HELD = "HELD"


class SendPolicy(str, Enum):
    NO_SEND = "NO_SEND"


class StageFailure(RuntimeError):
    """An injected attempt failed at a known operational stage."""

    def __init__(self, stage: FailureStage, message: str) -> None:
        if not isinstance(stage, FailureStage):
            raise ContractViolation("stage must use FailureStage")
        super().__init__(message)
        self.stage = stage


@dataclass(frozen=True, slots=True)
class FailureDetail:
    stage: FailureStage
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class AttemptContext:
    """Input passed to the injected attempt callable."""

    mode: CycleMode
    slot_utc: str
    decision_at_utc: str
    attempt_no: int
    planned_for_utc: str
    no_send: bool = True


@dataclass(frozen=True, slots=True)
class AttemptReceipt:
    attempt_no: int
    planned_for_utc: str
    observed_at_utc: str
    status: AttemptStatus
    failure: FailureDetail | None = None


@dataclass(frozen=True, slots=True)
class RetryPlan:
    attempt_no: int
    scheduled_for_utc: str
    delay_seconds: int
    scheduler_write_enabled: bool = False


@dataclass(frozen=True, slots=True)
class DeliveryDraft:
    """Local report material from which a held delivery intent can be built."""

    logical_run_id: str
    report_sha256: str
    payload_path: str
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class DeliveryIntent:
    intent_id: str
    intent_type: str
    logical_run_id: str
    report_sha256: str
    payload_path: str
    payload: Mapping[str, Any]
    status: IntentStatus = IntentStatus.HELD
    send_policy: SendPolicy = SendPolicy.NO_SEND
    external_write_enabled: bool = False
    hold_reason: str = OUTBOX_HOLD_REASON

    @property
    def outbox_payload(self) -> dict[str, Any]:
        """Return the desired payload without writing the incompatible schema."""

        return {
            "outbox_id": self.intent_id,
            "logical_run_id": self.logical_run_id,
            "report_sha256": self.report_sha256,
            "payload_path": self.payload_path,
            "payload": dict(self.payload),
            "status": self.status.value,
            "send_policy": self.send_policy.value,
            "external_write_enabled": self.external_write_enabled,
            "hold_reason": self.hold_reason,
        }


@dataclass(frozen=True, slots=True)
class AlertIntent:
    intent_id: str
    intent_type: str
    slot_utc: str
    attempt_no: int
    failure: FailureDetail
    status: IntentStatus = IntentStatus.HELD
    send_policy: SendPolicy = SendPolicy.NO_SEND
    external_write_enabled: bool = False


@dataclass(frozen=True, slots=True)
class ShadowCycleResult:
    mode: CycleMode
    slot_utc: str
    decision_at_utc: str
    status: CycleStatus
    attempts: tuple[AttemptReceipt, ...]
    retry_plan: RetryPlan | None
    recovered_silently: bool
    delivery_intent: DeliveryIntent | None
    alert_intent: AlertIntent | None
    external_actions_enabled: bool = False
    persistence_writes_enabled: bool = False


AttemptExecutor = Callable[[AttemptContext], Any]
DeliveryFactory = Callable[[Any], DeliveryDraft]
FailureClassifier = Callable[[Exception], FailureStage]
Clock = Callable[[], datetime]


def utc_slots_for_day(value: date | datetime | str) -> tuple[datetime, ...]:
    """Return the six fixed UTC slots for a calendar day."""

    if isinstance(value, datetime):
        day = parse_utc(value).date()
    elif isinstance(value, date):
        day = value
    elif isinstance(value, str):
        candidate = value.strip()
        try:
            day = date.fromisoformat(candidate)
        except ValueError:
            day = parse_utc(candidate).date()
    else:
        raise ContractViolation("day must be a date, aware datetime, or ISO string")
    return tuple(
        datetime.combine(day, time(hour=hour), tzinfo=timezone.utc)
        for hour in UTC_SLOT_HOURS
    )


def slot_at_or_before(value: datetime | str) -> datetime:
    """Floor an aware timestamp to its deterministic four-hour UTC slot."""

    observed = parse_utc(value)
    return observed.replace(
        hour=(observed.hour // 4) * 4,
        minute=0,
        second=0,
        microsecond=0,
    )


def next_utc_slot(value: datetime | str) -> datetime:
    """Return the first fixed UTC slot strictly after ``value``."""

    observed = parse_utc(value)
    current = slot_at_or_before(observed)
    return current + timedelta(hours=4)


def classify_failure(error: Exception) -> FailureStage:
    """Classify a failure without guessing at browser or API root causes."""

    if isinstance(error, StageFailure):
        return error.stage
    explicit = getattr(error, "failure_stage", None)
    try:
        return FailureStage(explicit)
    except (TypeError, ValueError):
        return FailureStage.ORCHESTRATION


def build_held_delivery_intent(
    draft: DeliveryDraft,
    *,
    mode: CycleMode,
) -> DeliveryIntent | None:
    """Build an in-memory held intent; replays never get delivery intents."""

    actual_mode = _mode(mode)
    if actual_mode is CycleMode.REPLAY:
        return None
    logical_run_id = _required(draft.logical_run_id, "logical_run_id")
    digest = _sha256_hex(draft.report_sha256, "report_sha256")
    payload_path = _required(draft.payload_path, "payload_path")
    if not isinstance(draft.payload, Mapping):
        raise ContractViolation("payload must be a mapping")
    intent_id = _stable_id("held_delivery", logical_run_id, digest)
    return DeliveryIntent(
        intent_id=intent_id,
        intent_type="REPORT_DELIVERY",
        logical_run_id=logical_run_id,
        report_sha256=digest,
        payload_path=payload_path,
        payload=dict(draft.payload),
    )


def build_held_alert_intent(
    *,
    slot_utc: datetime | str,
    attempt_no: int,
    failure: FailureDetail,
) -> AlertIntent:
    """Build a terminal, held alert intent without contacting a transport."""

    slot = _slot(slot_utc)
    if attempt_no != 2:
        raise ContractViolation("terminal alert intent requires attempt_no 2")
    intent_id = _stable_id(
        "held_alert", format_utc(slot), failure.stage.value, failure.error_type
    )
    return AlertIntent(
        intent_id=intent_id,
        intent_type="RUN_FAILURE_ALERT",
        slot_utc=format_utc(slot),
        attempt_no=attempt_no,
        failure=failure,
    )


def run_shadow_cycle(
    *,
    mode: CycleMode,
    scheduled_for_utc: datetime | str,
    execute_attempt: AttemptExecutor,
    clock: Clock,
    delivery_factory: DeliveryFactory | None = None,
    failure_classifier: FailureClassifier = classify_failure,
) -> ShadowCycleResult:
    """Execute attempt one and, on failure, plan exactly one retry.

    The function never sleeps and never invokes the retry itself.  A scheduler
    may later pass the returned result to :func:`run_scheduled_retry`.
    """

    actual_mode = _mode(mode)
    slot = _slot(scheduled_for_utc)
    observed = parse_utc(clock())
    if observed < slot:
        raise ContractViolation("attempt cannot run before its scheduled UTC slot")
    if (
        actual_mode is CycleMode.PRODUCTION_SHADOW
        and observed - slot > timedelta(minutes=10)
    ):
        raise ContractViolation(
            "production first attempt must start within +10 minutes of its UTC slot"
        )
    context = AttemptContext(
        mode=actual_mode,
        slot_utc=format_utc(slot),
        decision_at_utc=format_utc(observed),
        attempt_no=1,
        planned_for_utc=format_utc(slot),
    )
    try:
        result = execute_attempt(context)
        delivery = None
        if actual_mode is CycleMode.PRODUCTION_SHADOW and delivery_factory is not None:
            delivery = build_held_delivery_intent(
                delivery_factory(result), mode=actual_mode
            )
    except Exception as error:
        failure = _failure_detail(error, failure_classifier)
        retry_at = observed + RETRY_DELAY
        return ShadowCycleResult(
            mode=actual_mode,
            slot_utc=format_utc(slot),
            decision_at_utc=format_utc(observed),
            status=CycleStatus.RETRY_SCHEDULED,
            attempts=(
                AttemptReceipt(
                    attempt_no=1,
                    planned_for_utc=format_utc(slot),
                    observed_at_utc=format_utc(observed),
                    status=AttemptStatus.FAILED,
                    failure=failure,
                ),
            ),
            retry_plan=RetryPlan(
                attempt_no=2,
                scheduled_for_utc=format_utc(retry_at),
                delay_seconds=int(RETRY_DELAY.total_seconds()),
            ),
            recovered_silently=False,
            delivery_intent=None,
            alert_intent=None,
        )
    return ShadowCycleResult(
        mode=actual_mode,
        slot_utc=format_utc(slot),
        decision_at_utc=format_utc(observed),
        status=CycleStatus.SUCCEEDED,
        attempts=(
            AttemptReceipt(
                attempt_no=1,
                planned_for_utc=format_utc(slot),
                observed_at_utc=format_utc(observed),
                status=AttemptStatus.SUCCEEDED,
            ),
        ),
        retry_plan=None,
        recovered_silently=False,
        delivery_intent=delivery,
        alert_intent=None,
    )


def run_scheduled_retry(
    prior: ShadowCycleResult,
    *,
    execute_attempt: AttemptExecutor,
    clock: Clock,
    delivery_factory: DeliveryFactory | None = None,
    failure_classifier: FailureClassifier = classify_failure,
) -> ShadowCycleResult:
    """Execute the one planned retry, never a third attempt.

    A successful retry is recorded as ``recovered_silently``. Production
    shadow still builds the ordinary held report-delivery intent when a
    factory is supplied; "silent" means there is no separate recovery alert.
    A failed retry terminates the cycle and creates one structured, held alert
    intent.
    """

    if prior.status is not CycleStatus.RETRY_SCHEDULED:
        raise ContractViolation("retry requires a RETRY_SCHEDULED cycle")
    if prior.retry_plan is None or prior.retry_plan.attempt_no != 2:
        raise ContractViolation("cycle does not contain the one valid retry plan")
    if len(prior.attempts) != 1 or prior.attempts[0].status is not AttemptStatus.FAILED:
        raise ContractViolation("retry requires exactly one failed first attempt")
    decision = parse_utc(prior.decision_at_utc)
    if decision != parse_utc(prior.attempts[0].observed_at_utc):
        raise ContractViolation("retry must reuse the first attempt decision_at")
    if prior.mode is CycleMode.PRODUCTION_SHADOW:
        slot = parse_utc(prior.slot_utc)
        if decision < slot or decision - slot > timedelta(minutes=10):
            raise ContractViolation(
                "production retry decision_at must stay within the original slot window"
            )
    observed = parse_utc(clock())
    planned = parse_utc(prior.retry_plan.scheduled_for_utc)
    if observed < planned:
        raise ContractViolation("retry is not due; runner never sleeps")
    context = AttemptContext(
        mode=prior.mode,
        slot_utc=prior.slot_utc,
        decision_at_utc=prior.decision_at_utc,
        attempt_no=2,
        planned_for_utc=format_utc(planned),
    )
    try:
        result = execute_attempt(context)
        delivery = None
        if prior.mode is CycleMode.PRODUCTION_SHADOW and delivery_factory is not None:
            delivery = build_held_delivery_intent(
                delivery_factory(result), mode=prior.mode
            )
    except Exception as error:
        failure = _failure_detail(error, failure_classifier)
        attempts = prior.attempts + (
            AttemptReceipt(
                attempt_no=2,
                planned_for_utc=format_utc(planned),
                observed_at_utc=format_utc(observed),
                status=AttemptStatus.FAILED,
                failure=failure,
            ),
        )
        return ShadowCycleResult(
            mode=prior.mode,
            slot_utc=prior.slot_utc,
            decision_at_utc=prior.decision_at_utc,
            status=CycleStatus.FAILED_TERMINAL,
            attempts=attempts,
            retry_plan=None,
            recovered_silently=False,
            delivery_intent=None,
            alert_intent=build_held_alert_intent(
                slot_utc=prior.slot_utc,
                attempt_no=2,
                failure=failure,
            ),
        )
    return ShadowCycleResult(
        mode=prior.mode,
        slot_utc=prior.slot_utc,
        decision_at_utc=prior.decision_at_utc,
        status=CycleStatus.SUCCEEDED,
        attempts=prior.attempts + (
            AttemptReceipt(
                attempt_no=2,
                planned_for_utc=format_utc(planned),
                observed_at_utc=format_utc(observed),
                status=AttemptStatus.SUCCEEDED,
            ),
        ),
        retry_plan=None,
        recovered_silently=True,
        delivery_intent=delivery,
        alert_intent=None,
    )


def cycle_result_to_dict(result: ShadowCycleResult) -> dict[str, Any]:
    """Serialize a cycle result for an audit receipt or later retry."""

    return _json_value(asdict(result))


def retry_cycle_from_dict(payload: Mapping[str, Any]) -> ShadowCycleResult:
    """Restore and validate the minimal first-failure state used by the CLI."""

    if not isinstance(payload, Mapping):
        raise ContractViolation("retry state must be a mapping")
    if payload.get("status") != CycleStatus.RETRY_SCHEDULED.value:
        raise ContractViolation("retry state must have RETRY_SCHEDULED status")
    attempts = payload.get("attempts")
    retry = payload.get("retry_plan")
    if not isinstance(attempts, list) or len(attempts) != 1:
        raise ContractViolation("retry state must contain one first attempt")
    if not isinstance(attempts[0], Mapping) or not isinstance(retry, Mapping):
        raise ContractViolation("retry state is missing attempt or retry data")
    failure_payload = attempts[0].get("failure")
    if not isinstance(failure_payload, Mapping):
        raise ContractViolation("failed first attempt must contain failure detail")
    failure = FailureDetail(
        stage=FailureStage(failure_payload["stage"]),
        error_type=_required(failure_payload["error_type"], "error_type"),
        message=_required(failure_payload["message"], "message"),
    )
    receipt = AttemptReceipt(
        attempt_no=1,
        planned_for_utc=format_utc(attempts[0]["planned_for_utc"]),
        observed_at_utc=format_utc(attempts[0]["observed_at_utc"]),
        status=AttemptStatus.FAILED,
        failure=failure,
    )
    retry_plan = RetryPlan(
        attempt_no=int(retry["attempt_no"]),
        scheduled_for_utc=format_utc(retry["scheduled_for_utc"]),
        delay_seconds=int(retry["delay_seconds"]),
        scheduler_write_enabled=False,
    )
    result = ShadowCycleResult(
        mode=CycleMode(payload["mode"]),
        slot_utc=format_utc(payload["slot_utc"]),
        decision_at_utc=format_utc(
            payload.get("decision_at_utc", attempts[0]["observed_at_utc"])
        ),
        status=CycleStatus.RETRY_SCHEDULED,
        attempts=(receipt,),
        retry_plan=retry_plan,
        recovered_silently=False,
        delivery_intent=None,
        alert_intent=None,
    )
    if retry_plan.attempt_no != 2 or retry_plan.delay_seconds != 600:
        raise ContractViolation("retry state must contain the single +10 minute retry")
    if parse_utc(result.decision_at_utc) != parse_utc(receipt.observed_at_utc):
        raise ContractViolation("retry state must preserve first-attempt decision_at")
    if result.mode is CycleMode.PRODUCTION_SHADOW:
        slot = parse_utc(result.slot_utc)
        decision = parse_utc(result.decision_at_utc)
        if decision < slot or decision - slot > timedelta(minutes=10):
            raise ContractViolation(
                "retry state decision_at is outside the original slot window"
            )
    return result


def _failure_detail(
    error: Exception,
    classifier: FailureClassifier,
) -> FailureDetail:
    stage = classifier(error)
    if not isinstance(stage, FailureStage):
        try:
            stage = FailureStage(stage)
        except (TypeError, ValueError) as exc:
            raise ContractViolation("failure classifier returned an invalid stage") from exc
    message = " ".join(str(error).split())[:500] or type(error).__name__
    return FailureDetail(
        stage=stage,
        error_type=type(error).__name__,
        message=message,
    )


def _slot(value: datetime | str) -> datetime:
    parsed = parse_utc(value)
    if (
        parsed.hour not in UTC_SLOT_HOURS
        or parsed.minute
        or parsed.second
        or parsed.microsecond
    ):
        raise ContractViolation(
            "scheduled_for_utc must be one of 00/04/08/12/16/20 UTC"
        )
    return parsed


def _mode(value: CycleMode) -> CycleMode:
    try:
        return CycleMode(value)
    except (TypeError, ValueError) as exc:
        raise ContractViolation("mode must use CycleMode") from exc


def _required(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{field_name} must be a non-empty string")
    return value.strip()


def _sha256_hex(value: Any, field_name: str) -> str:
    digest = _required(value, field_name).lower()
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        raise ContractViolation(f"{field_name} must be 64 lowercase hexadecimal characters")
    return digest


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:32]}"


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


__all__ = [
    "AlertIntent",
    "AttemptContext",
    "AttemptReceipt",
    "AttemptStatus",
    "CycleMode",
    "CycleStatus",
    "DeliveryDraft",
    "DeliveryIntent",
    "FailureDetail",
    "FailureStage",
    "IntentStatus",
    "OUTBOX_HOLD_REASON",
    "RETRY_DELAY",
    "RetryPlan",
    "SendPolicy",
    "ShadowCycleResult",
    "StageFailure",
    "UTC_SLOT_HOURS",
    "build_held_alert_intent",
    "build_held_delivery_intent",
    "classify_failure",
    "cycle_result_to_dict",
    "next_utc_slot",
    "retry_cycle_from_dict",
    "run_scheduled_retry",
    "run_shadow_cycle",
    "slot_at_or_before",
    "utc_slots_for_day",
]
