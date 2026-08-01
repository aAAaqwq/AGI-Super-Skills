"""SQLite-backed run ledger for production slots and offline replays."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from .contracts import (
    AcceptedPostObservation,
    ContractViolation,
    RunNamespace,
    SCHEMA_VERSION,
    format_utc,
    parse_utc,
    serialize_decimal,
)


@dataclass(frozen=True, slots=True)
class LogicalRun:
    logical_run_id: str
    run_namespace: RunNamespace
    pipeline_version: str
    production_job_id: str | None
    scheduled_for_utc: str | None
    replay_namespace: str | None
    source_logical_run_id: str | None
    schema_version: str
    source_system: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class RunAttempt:
    attempt_id: str
    logical_run_id: str
    attempt_no: int
    status: str
    started_at_utc: str
    finished_at_utc: str | None
    failed_stage: str | None
    recovered_silently: bool
    alert_sent_at_utc: str | None
    schema_version: str
    source_system: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class ProductionRunCutoff:
    logical_run_id: str
    decision_at_utc: str
    schema_version: str
    source_system: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class BronzeManifest:
    manifest_id: str
    logical_run_id: str
    attempt_id: str
    artifact_path: str
    sha256_hex: str
    payload_schema_version: str
    event_start_utc: str | None
    event_end_utc: str | None
    record_count: int
    schema_version: str
    source_system: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class DeliveryOutboxItem:
    outbox_id: str
    logical_run_id: str
    report_sha256: str
    payload_path: str
    status: str
    schema_version: str
    source_system: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class StoredPostObservation:
    post_observation_id: str
    logical_run_id: str
    attempt_id: str
    post_id: str
    canonical_post_url: str
    author_id: str
    published_at_utc: str
    observed_at_utc: str
    content_hash: str
    source_channel: str
    source_record_ordinal: int
    observation_status: str
    schema_version: str
    source_system: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class StoredSignalFamily:
    signal_family_id: str
    post_id: str
    symbol: str
    direction: str
    first_logical_run_id: str
    first_attempt_id: str
    family_status: str
    schema_version: str
    source_system: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class StoredSignalRevision:
    signal_revision_id: str
    signal_family_id: str
    logical_run_id: str
    attempt_id: str
    revision_no: int
    decision_at_utc: str
    parameter_source: str
    entry_low_decimal: str
    entry_high_decimal: str
    stop_loss_decimal: str
    tp1_decimal: str
    tp2_decimal: str | None
    original_signal_status: str
    invalidation_reason: str | None
    dq_score: int
    quality_flags: tuple[str, ...]
    schema_version: str
    source_system: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class StoredTrackingEvaluation:
    tracking_evaluation_id: str
    signal_revision_id: str
    logical_run_id: str
    attempt_id: str
    evaluated_at_utc: str
    evaluation_status: str
    nominal_r_decimal: str | None
    mfe_r_decimal: str | None
    mae_r_decimal: str | None
    net_r_decimal: str | None
    cost_model_version: str | None
    dq_score: int
    quality_flags: tuple[str, ...]
    schema_version: str
    source_system: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class SmartMoneyLeaderboardRowInput:
    rank_no: int
    top_trader_id: str
    pnl: Decimal | None = None
    roi: Decimal | None = None
    assets: Any = None
    subscribers: int | None = None
    position_status: str | None = None
    signal_lead_on: bool | None = None
    raw: Any = None


@dataclass(frozen=True, slots=True)
class SmartMoneyLeaderboardCapture:
    smart_money_capture_id: str
    logical_run_id: str
    attempt_id: str
    ranking_type: str
    time_range: str
    capture_status: str
    captured_at_utc: str
    snapshot_semantics: str
    observed_start_utc: str
    observed_end_utc: str
    last_update_time_ms: int | None
    evidence_path: str
    evidence_file_sha256: str
    payload_sha256: str | None
    expected_rows: int
    rendered_rows: int
    failure_reason: str | None
    schema_version: str
    source_system: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class SmartMoneyLeaderboardRow:
    smart_money_row_id: str
    smart_money_capture_id: str
    top_trader_id: str
    rank_no: int
    pnl_decimal: str | None
    roi_decimal: str | None
    assets: Any
    subscribers: int | None
    position_status: str | None
    signal_lead_on: bool | None
    raw: Any
    schema_version: str
    source_system: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class SmartMoneyProfileObservation:
    smart_money_profile_observation_id: str
    logical_run_id: str
    attempt_id: str
    top_trader_id: str
    observation_status: str
    captured_at_utc: str
    days_active: int | None
    mdd_decimal: str | None
    win_rate_decimal: str | None
    um_margin_balance_decimal: str | None
    cm_margin_balance_decimal: str | None
    net_transfer_decimal: str | None
    sharing_position: Any
    sharing_history: Any
    latest_record: Any
    is_ai: bool | None
    is_pm_user: bool | None
    copy_trade_portfolio_ids: Any
    evidence_path: str
    evidence_file_sha256: str
    payload_sha256: str | None
    failure_reason: str | None
    raw_profile: Any
    schema_version: str
    source_system: str
    created_at_utc: str
    updated_at_utc: str


@dataclass(frozen=True, slots=True)
class SmartMoneySquareIdentityMapping:
    top_trader_id: str
    author_id: str
    verification_method: str
    verified_at_utc: str
    evidence_path: str
    evidence_sha256: str
    schema_version: str
    source_system: str
    created_at_utc: str
    updated_at_utc: str


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"{prefix}_{digest[:32]}"


def _required(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{field_name} must be a non-empty string")
    return value.strip()


def _enum_value(value: Any, field_name: str) -> str:
    raw = value.value if isinstance(value, Enum) else value
    return _required(raw, field_name).upper()


def _quality_flags_json(values: Iterable[str]) -> str:
    flags = list(values)
    if not all(isinstance(value, str) and value.strip() for value in flags):
        raise ContractViolation("quality_flags must contain non-empty strings")
    return json.dumps(
        sorted({value.strip() for value in flags}),
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _decimal_text(value: Decimal | None, field_name: str) -> str | None:
    if value is None:
        return None
    try:
        return serialize_decimal(value)
    except ContractViolation as exc:
        raise ContractViolation(f"{field_name} must be a finite Decimal") from exc


def _sha256_text(value: str, field_name: str) -> str:
    digest = _required(value, field_name).lower()
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise ContractViolation(
            f"{field_name} must contain exactly 64 hexadecimal characters"
        )
    return digest


def _read_verified_file(
    path: str,
    expected_sha256: str,
    *,
    digest_field: str = "evidence_file_sha256",
) -> tuple[str, bytes]:
    digest = _sha256_text(expected_sha256, digest_field)
    evidence_file = Path(path)
    try:
        if not evidence_file.is_file():
            raise ContractViolation(
                "evidence_path must reference an existing readable file"
            )
        content = evidence_file.read_bytes()
    except OSError as exc:
        raise ContractViolation("evidence_path must be a readable file") from exc
    actual = sha256(content).hexdigest()
    if actual != digest:
        raise ContractViolation(
            f"{digest_field} does not match the evidence file"
        )
    return digest, content


def _verified_file_sha256(path: str, expected_sha256: str) -> str:
    """Validate that a digest is scoped to, and matches, a local evidence file."""

    digest, _ = _read_verified_file(path, expected_sha256)
    return digest


def _canonical_json(value: Any, field_name: str) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ContractViolation(f"{field_name} must be JSON serializable") from exc


def _optional_bool(value: bool | None, field_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise ContractViolation(f"{field_name} must be a boolean or None")
    return int(value)


_TRACKING_STATUS_MAP = {
    "PENDING": "PENDING",
    "UNTRIGGERED": "UNTRIGGERED",
    "TRACKING": "TRIGGERED",
    "TRIGGERED": "TRIGGERED",
    "STOPPED": "STOPPED",
    "TP1_REACHED": "TP1_HIT",
    "TP1_HIT": "TP1_HIT",
    "TP2_REACHED": "TP2_HIT",
    "TP2_HIT": "TP2_HIT",
    "TIMEOUT": "EXPIRED",
    "EXPIRED": "EXPIRED",
}

_TERMINAL_TRACKING_STATUSES = frozenset(
    {"UNTRIGGERED", "STOPPED", "TP2_HIT", "EXPIRED"}
)

_SMART_MONEY_IDENTITY_MAPPING_SCHEMA = (
    "binance-smart-money-square-identity-mapping/v1"
)


def _verified_identity_mapping_digest(
    path: str,
    expected_sha256: str,
    *,
    top_trader_id: str,
    square_uid: str,
) -> str:
    digest, content = _read_verified_file(
        path, expected_sha256, digest_field="evidence_sha256"
    )
    try:
        evidence = json.loads(content)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ContractViolation(
            "identity mapping evidence must be readable JSON"
        ) from exc
    if (
        not isinstance(evidence, dict)
        or evidence.get("schema") != _SMART_MONEY_IDENTITY_MAPPING_SCHEMA
    ):
        raise ContractViolation(
            "identity mapping evidence schema must be "
            f"{_SMART_MONEY_IDENTITY_MAPPING_SCHEMA}"
        )

    if "mappings" in evidence:
        mappings = evidence["mappings"]
        if not isinstance(mappings, list) or not mappings:
            raise ContractViolation(
                "identity mapping evidence mappings must be a non-empty array"
            )
    else:
        mappings = [evidence]

    pairs: list[tuple[str, str]] = []
    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise ContractViolation(
                "identity mapping evidence entries must be objects"
            )
        trader = mapping.get("topTraderId")
        author = mapping.get("squareUid")
        if (
            not isinstance(trader, str)
            or not trader.strip()
            or not isinstance(author, str)
            or not author.strip()
        ):
            raise ContractViolation(
                "identity mapping evidence requires topTraderId and squareUid"
            )
        pairs.append((trader.strip(), author.strip()))

    if (
        len({trader for trader, _ in pairs}) != len(pairs)
        or len({author for _, author in pairs}) != len(pairs)
    ):
        raise ContractViolation(
            "identity mapping evidence must contain unique ID mappings"
        )
    if pairs.count((top_trader_id, square_uid)) != 1:
        raise ContractViolation(
            "identity mapping evidence does not bind the requested "
            "topTraderId and squareUid"
        )
    return digest


class SQLiteRunLedger:
    """Small transactional API over the v4 SQLite audit ledger."""

    _SMART_MONEY_REQUIRED_COLUMNS = {
        "smart_money_leaderboard_capture": frozenset(
            {
                "snapshot_semantics",
                "observed_start_utc",
                "observed_end_utc",
                "evidence_file_sha256",
                "payload_sha256",
            }
        ),
        "smart_money_profile_observation": frozenset(
            {"evidence_file_sha256", "payload_sha256"}
        ),
    }

    def __init__(self, database: str | Path, migration: str | Path) -> None:
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        try:
            # Migration 004 was hardened while it was still unreleased.  SQLite's
            # CREATE TABLE IF NOT EXISTS cannot upgrade an earlier draft table, so
            # reject that state explicitly instead of failing later with a vague
            # missing-column error or silently weakening the evidence contract.
            self._verify_smart_money_schema(allow_absent=True)
            migration_path = Path(migration)
            migration_paths = (
                sorted(migration_path.glob("*.sql"))
                if migration_path.is_dir()
                else [migration_path]
            )
            if not migration_paths:
                raise ContractViolation("migration path contains no SQL migrations")
            for path in migration_paths:
                self._connection.executescript(path.read_text(encoding="utf-8"))
            self._verify_smart_money_schema(allow_absent=False)
        except Exception:
            self._connection.close()
            raise

    def _verify_smart_money_schema(self, *, allow_absent: bool) -> None:
        for table_name, required_columns in self._SMART_MONEY_REQUIRED_COLUMNS.items():
            exists = self._connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table_name,),
            ).fetchone()
            if exists is None:
                if allow_absent:
                    continue
                raise ContractViolation(
                    f"Smart Money schema is incomplete: missing {table_name}"
                )
            actual_columns = {
                str(row["name"])
                for row in self._connection.execute(
                    f'PRAGMA table_info("{table_name}")'
                ).fetchall()
            }
            missing_columns = sorted(required_columns - actual_columns)
            if missing_columns:
                missing = ", ".join(missing_columns)
                raise ContractViolation(
                    "legacy Smart Money schema is incompatible; preserve the "
                    f"database and migrate it explicitly ({table_name} missing: {missing})"
                )

    def close(self) -> None:
        self._connection.close()

    def create_or_open_production_run(
        self,
        *,
        production_job_id: str,
        scheduled_for_utc: datetime | str,
        pipeline_version: str,
        now: datetime | str | None = None,
    ) -> LogicalRun:
        job_id = _required(production_job_id, "production_job_id")
        scheduled = format_utc(scheduled_for_utc)
        version = _required(pipeline_version, "pipeline_version")
        observed_at = format_utc(now or datetime.now(timezone.utc))
        logical_run_id = _stable_id("prod", job_id, scheduled)
        with self._connection:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO logical_run (
                    logical_run_id, run_namespace, production_job_id,
                    scheduled_for_utc, pipeline_version, schema_version,
                    source_system, created_at_utc, updated_at_utc
                ) VALUES (?, 'PRODUCTION', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    logical_run_id,
                    job_id,
                    scheduled,
                    version,
                    SCHEMA_VERSION,
                    "binance_square_scanner",
                    observed_at,
                    observed_at,
                ),
            )
        row = self._connection.execute(
            """
            SELECT * FROM logical_run
            WHERE run_namespace = 'PRODUCTION'
              AND production_job_id = ? AND scheduled_for_utc = ?
            """,
            (job_id, scheduled),
        ).fetchone()
        if row is None:
            raise RuntimeError("production run insert was not observable")
        return self._logical_run(row)

    def create_or_open_replay_run(
        self,
        *,
        replay_namespace: str,
        source_logical_run_id: str,
        pipeline_version: str,
        now: datetime | str | None = None,
    ) -> LogicalRun:
        namespace = _required(replay_namespace, "replay_namespace")
        source_run_id = _required(source_logical_run_id, "source_logical_run_id")
        version = _required(pipeline_version, "pipeline_version")
        observed_at = format_utc(now or datetime.now(timezone.utc))
        logical_run_id = _stable_id("replay", namespace, source_run_id, version)
        with self._connection:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO logical_run (
                    logical_run_id, run_namespace, pipeline_version,
                    replay_namespace, source_logical_run_id, schema_version,
                    source_system, created_at_utc, updated_at_utc
                ) VALUES (?, 'REPLAY', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    logical_run_id,
                    version,
                    namespace,
                    source_run_id,
                    SCHEMA_VERSION,
                    "binance_square_replay",
                    observed_at,
                    observed_at,
                ),
            )
        row = self._connection.execute(
            """
            SELECT * FROM logical_run
            WHERE run_namespace = 'REPLAY'
              AND replay_namespace = ?
              AND source_logical_run_id = ?
              AND pipeline_version = ?
            """,
            (namespace, source_run_id, version),
        ).fetchone()
        if row is None:
            raise RuntimeError("replay run insert was not observable")
        return self._logical_run(row)

    def freeze_production_decision(
        self,
        logical_run_id: str,
        *,
        decision_at: datetime | str,
        now: datetime | str | None = None,
    ) -> ProductionRunCutoff:
        """Insert once or require an exact retry match for a production cutoff."""

        run_id = _required(logical_run_id, "logical_run_id")
        decision = format_utc(decision_at)
        observed_at = format_utc(now or datetime.now(timezone.utc))
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            run = self._connection.execute(
                "SELECT run_namespace FROM logical_run WHERE logical_run_id = ?",
                (run_id,),
            ).fetchone()
            if run is None or run["run_namespace"] != "PRODUCTION":
                raise ContractViolation(
                    "decision cutoff requires an existing production run"
                )
            self._connection.execute(
                """
                INSERT OR IGNORE INTO production_run_cutoff (
                    logical_run_id, decision_at_utc, schema_version,
                    source_system, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    decision,
                    SCHEMA_VERSION,
                    "binance_square_scanner",
                    observed_at,
                    observed_at,
                ),
            )
            row = self._connection.execute(
                "SELECT * FROM production_run_cutoff WHERE logical_run_id = ?",
                (run_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("production cutoff insert was not observable")
            if row["decision_at_utc"] != decision:
                raise ContractViolation(
                    "scheduled retry decision_at does not match the frozen cutoff"
                )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        return self._production_run_cutoff(row)

    def get_production_decision(
        self,
        logical_run_id: str,
    ) -> ProductionRunCutoff:
        row = self._connection.execute(
            "SELECT * FROM production_run_cutoff WHERE logical_run_id = ?",
            (_required(logical_run_id, "logical_run_id"),),
        ).fetchone()
        if row is None:
            raise ContractViolation("production decision cutoff does not exist")
        return self._production_run_cutoff(row)

    def record_attempt(
        self,
        logical_run_id: str,
        *,
        attempt_no: int,
        started_at: datetime | str,
    ) -> RunAttempt:
        run_id = _required(logical_run_id, "logical_run_id")
        if attempt_no not in (1, 2):
            raise ContractViolation("attempt_no must be 1 or 2")
        started = format_utc(started_at)
        attempt_id = _stable_id("attempt", run_id, str(attempt_no))
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO run_attempt (
                        attempt_id, logical_run_id, attempt_no, status,
                        started_at_utc, schema_version, source_system,
                        created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, 'RUNNING', ?, ?, ?, ?, ?)
                    """,
                    (
                        attempt_id,
                        run_id,
                        attempt_no,
                        started,
                        SCHEMA_VERSION,
                        "binance_square_scanner",
                        started,
                        started,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ContractViolation("attempt must reference an existing logical run") from exc
        row = self._connection.execute(
            "SELECT * FROM run_attempt WHERE logical_run_id = ? AND attempt_no = ?",
            (run_id, attempt_no),
        ).fetchone()
        if row is None:
            raise RuntimeError("run attempt insert was not observable")
        return self._run_attempt(row)

    def start_next_attempt(
        self,
        logical_run_id: str,
        *,
        started_at: datetime | str,
    ) -> RunAttempt:
        """Atomically allocate the only safe next attempt for a logical run.

        A successful or currently-running slot cannot be started again.  A
        failed attempt may advance once, from attempt 1 to attempt 2.
        """

        run_id = _required(logical_run_id, "logical_run_id")
        started = format_utc(started_at)
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            run = self._connection.execute(
                "SELECT logical_run_id FROM logical_run WHERE logical_run_id = ?",
                (run_id,),
            ).fetchone()
            if run is None:
                raise ContractViolation("attempt must reference an existing logical run")
            rows = self._connection.execute(
                """
                SELECT * FROM run_attempt
                WHERE logical_run_id = ? ORDER BY attempt_no
                """,
                (run_id,),
            ).fetchall()
            if any(row["status"] == "RUNNING" for row in rows):
                raise ContractViolation("logical run already has a RUNNING attempt")
            if any(row["status"] == "SUCCEEDED" for row in rows):
                raise ContractViolation("logical run already has a SUCCEEDED attempt")
            attempt_no = 1 if not rows else max(row["attempt_no"] for row in rows) + 1
            if attempt_no not in (1, 2):
                raise ContractViolation("logical run has exhausted its two attempts")
            if rows:
                prior_finished = rows[-1]["finished_at_utc"]
                if prior_finished is None or parse_utc(started) < parse_utc(prior_finished):
                    raise ContractViolation(
                        "retry started_at cannot precede the prior failed attempt"
                    )
            attempt_id = _stable_id("attempt", run_id, str(attempt_no))
            self._connection.execute(
                """
                INSERT INTO run_attempt (
                    attempt_id, logical_run_id, attempt_no, status,
                    started_at_utc, schema_version, source_system,
                    created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, 'RUNNING', ?, ?, ?, ?, ?)
                """,
                (
                    attempt_id,
                    run_id,
                    attempt_no,
                    started,
                    SCHEMA_VERSION,
                    "binance_square_scanner",
                    started,
                    started,
                ),
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        row = self._connection.execute(
            "SELECT * FROM run_attempt WHERE attempt_id = ?", (attempt_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError("next attempt insert was not observable")
        return self._run_attempt(row)

    # The name is kept as a readable alias for callers that think in terms of
    # reservation rather than execution.
    reserve_next_attempt = start_next_attempt

    def list_attempts(self, logical_run_id: str) -> list[RunAttempt]:
        rows = self._connection.execute(
            """
            SELECT * FROM run_attempt
            WHERE logical_run_id = ? ORDER BY attempt_no
            """,
            (logical_run_id,),
        ).fetchall()
        return [self._run_attempt(row) for row in rows]

    def get_attempt(self, attempt_id: str) -> RunAttempt:
        row = self._connection.execute(
            "SELECT * FROM run_attempt WHERE attempt_id = ?",
            (_required(attempt_id, "attempt_id"),),
        ).fetchone()
        if row is None:
            raise ContractViolation("attempt does not exist")
        return self._run_attempt(row)

    def finish_attempt(
        self,
        attempt_id: str,
        *,
        status: str,
        finished_at: datetime | str,
        failed_stage: str | None = None,
    ) -> RunAttempt:
        """Move one RUNNING attempt to exactly one terminal audit state."""

        actual_attempt_id = _required(attempt_id, "attempt_id")
        terminal = _required(status, "status").upper()
        if terminal not in {"SUCCEEDED", "FAILED"}:
            raise ContractViolation("attempt terminal status must be SUCCEEDED or FAILED")
        stage = None
        if terminal == "FAILED":
            stage = _required(failed_stage or "", "failed_stage")
        elif failed_stage is not None:
            raise ContractViolation("successful attempts cannot have failed_stage")
        finished = format_utc(finished_at)
        row = self._connection.execute(
            "SELECT * FROM run_attempt WHERE attempt_id = ?", (actual_attempt_id,)
        ).fetchone()
        if row is None:
            raise ContractViolation("attempt does not exist")
        if row["status"] != "RUNNING":
            raise ContractViolation("attempt is already terminal")
        if parse_utc(finished) < parse_utc(row["started_at_utc"]):
            raise ContractViolation("finished_at cannot precede started_at")
        with self._connection:
            self._connection.execute(
                """
                UPDATE run_attempt
                SET status = ?, finished_at_utc = ?, failed_stage = ?,
                    updated_at_utc = ?
                WHERE attempt_id = ? AND status = 'RUNNING'
                """,
                (terminal, finished, stage, finished, actual_attempt_id),
            )
            self._connection.execute(
                """
                UPDATE logical_run SET updated_at_utc = ?
                WHERE logical_run_id = ?
                """,
                (finished, row["logical_run_id"]),
            )
        updated = self._connection.execute(
            "SELECT * FROM run_attempt WHERE attempt_id = ?", (actual_attempt_id,)
        ).fetchone()
        if updated is None or updated["status"] != terminal:
            raise RuntimeError("attempt terminal update was not observable")
        return self._run_attempt(updated)

    def record_manifest(
        self,
        *,
        logical_run_id: str,
        attempt_id: str,
        artifact_path: str,
        sha256_hex: str,
        source_system: str,
        payload_schema_version: str,
        event_start: datetime | str | None,
        event_end: datetime | str | None,
        record_count: int,
        now: datetime | str | None = None,
    ) -> BronzeManifest:
        run_id = _required(logical_run_id, "logical_run_id")
        actual_attempt_id = _required(attempt_id, "attempt_id")
        path = _required(artifact_path, "artifact_path")
        digest = _required(sha256_hex, "sha256_hex").lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ContractViolation("sha256_hex must contain exactly 64 hexadecimal characters")
        source = _required(source_system, "source_system")
        payload_version = _required(payload_schema_version, "payload_schema_version")
        if not isinstance(record_count, int) or isinstance(record_count, bool) or record_count < 0:
            raise ContractViolation("record_count must be a non-negative integer")
        if (event_start is None) != (event_end is None):
            raise ContractViolation("event_start and event_end must both be present or absent")
        start = format_utc(event_start) if event_start is not None else None
        end = format_utc(event_end) if event_end is not None else None
        if start is not None and end is not None and parse_utc(start) > parse_utc(end):
            raise ContractViolation("event_start must not be after event_end")
        observed_at = format_utc(now or datetime.now(timezone.utc))
        manifest_id = _stable_id("manifest", run_id, actual_attempt_id, path, digest)
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO bronze_manifest (
                        manifest_id, logical_run_id, attempt_id, artifact_path,
                        sha256_hex, payload_schema_version, event_start_utc,
                        event_end_utc, record_count, schema_version,
                        source_system, created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        manifest_id,
                        run_id,
                        actual_attempt_id,
                        path,
                        digest,
                        payload_version,
                        start,
                        end,
                        record_count,
                        SCHEMA_VERSION,
                        source,
                        observed_at,
                        observed_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ContractViolation("manifest must reference its run attempt") from exc
        row = self._connection.execute(
            "SELECT * FROM bronze_manifest WHERE manifest_id = ?", (manifest_id,)
        ).fetchone()
        if row is None:
            raise RuntimeError("bronze manifest insert was not observable")
        return self._bronze_manifest(row)

    def list_manifests(self, logical_run_id: str) -> list[BronzeManifest]:
        rows = self._connection.execute(
            """
            SELECT * FROM bronze_manifest
            WHERE logical_run_id = ? ORDER BY created_at_utc, manifest_id
            """,
            (logical_run_id,),
        ).fetchall()
        return [self._bronze_manifest(row) for row in rows]

    def record_accepted_post_observations(
        self,
        *,
        logical_run_id: str,
        attempt_id: str,
        observations: Iterable[AcceptedPostObservation],
        now: datetime | str | None = None,
    ) -> list[StoredPostObservation]:
        """Persist accepted observations without prematurely committing dedup.

        Rows may be written while an attempt is RUNNING, but baseline queries
        expose them only after that exact attempt reaches SUCCEEDED.
        """

        run_id = _required(logical_run_id, "logical_run_id")
        actual_attempt_id = _required(attempt_id, "attempt_id")
        values = list(observations)
        observed_now = format_utc(now or datetime.now(timezone.utc))
        attempt = self._connection.execute(
            """
            SELECT status FROM run_attempt
            WHERE logical_run_id = ? AND attempt_id = ?
            """,
            (run_id, actual_attempt_id),
        ).fetchone()
        if attempt is None:
            raise ContractViolation("observations must reference their run attempt")
        if attempt["status"] != "RUNNING":
            raise ContractViolation("observations can only be added to a RUNNING attempt")
        stored_ids: list[str] = []
        with self._connection:
            for observation in values:
                if not isinstance(observation, AcceptedPostObservation):
                    raise ContractViolation(
                        "observations must use AcceptedPostObservation contracts"
                    )
                author_id = observation.author_id.strip()
                self._connection.execute(
                    """
                    INSERT INTO author_entity (
                        author_id, identity_source, schema_version, source_system,
                        created_at_utc, updated_at_utc
                    ) VALUES (?, 'POST_DETAIL', ?, ?, ?, ?)
                    ON CONFLICT(author_id) DO UPDATE SET
                        updated_at_utc = excluded.updated_at_utc
                    """,
                    (
                        author_id,
                        SCHEMA_VERSION,
                        "binance_square_scanner",
                        observed_now,
                        observed_now,
                    ),
                )
                observation_id = _stable_id(
                    "postobs",
                    actual_attempt_id,
                    observation.source_channel.strip(),
                    str(observation.source_record_ordinal),
                    observation.post_id,
                )
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO post_observation (
                        post_observation_id, logical_run_id, attempt_id, post_id,
                        canonical_post_url, author_id, published_at_utc,
                        observed_at_utc, content_hash, source_channel,
                        source_record_ordinal, observation_status,
                        schema_version, source_system, created_at_utc,
                        updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACCEPTED',
                              ?, ?, ?, ?)
                    """,
                    (
                        observation_id,
                        run_id,
                        actual_attempt_id,
                        observation.post_id,
                        observation.canonical_post_url,
                        author_id,
                        format_utc(observation.published_at),
                        format_utc(observation.observed_at),
                        observation.content_hash,
                        observation.source_channel.strip(),
                        observation.source_record_ordinal,
                        SCHEMA_VERSION,
                        "binance_square_scanner",
                        observed_now,
                        observed_now,
                    ),
                )
                stored_ids.append(observation_id)
        if not stored_ids:
            return []
        placeholders = ",".join("?" for _ in stored_ids)
        rows = self._connection.execute(
            f"""
            SELECT * FROM post_observation
            WHERE post_observation_id IN ({placeholders})
            ORDER BY source_record_ordinal, post_observation_id
            """,
            stored_ids,
        ).fetchall()
        if len(rows) != len(set(stored_ids)):
            raise RuntimeError("accepted observation insert was not observable")
        return [self._stored_post_observation(row) for row in rows]

    def list_post_observations(
        self, logical_run_id: str | None = None
    ) -> list[StoredPostObservation]:
        if logical_run_id is None:
            rows = self._connection.execute(
                """
                SELECT * FROM post_observation
                ORDER BY created_at_utc, post_observation_id
                """
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT * FROM post_observation
                WHERE logical_run_id = ?
                ORDER BY created_at_utc, post_observation_id
                """,
                (_required(logical_run_id, "logical_run_id"),),
            ).fetchall()
        return [self._stored_post_observation(row) for row in rows]

    def prior_succeeded_production_post_ids(
        self,
        *,
        production_job_id: str,
        scheduled_for_utc: datetime | str,
    ) -> frozenset[str]:
        """Return only accepted IDs committed by strictly earlier slots."""

        job_id = _required(production_job_id, "production_job_id")
        scheduled = format_utc(scheduled_for_utc)
        rows = self._connection.execute(
            """
            SELECT DISTINCT observation.post_id
            FROM post_observation AS observation
            JOIN run_attempt AS attempt
              ON attempt.logical_run_id = observation.logical_run_id
             AND attempt.attempt_id = observation.attempt_id
            JOIN logical_run AS logical
              ON logical.logical_run_id = observation.logical_run_id
            WHERE observation.observation_status = 'ACCEPTED'
              AND attempt.status = 'SUCCEEDED'
              AND logical.run_namespace = 'PRODUCTION'
              AND logical.production_job_id = ?
              AND julianday(logical.scheduled_for_utc) < julianday(?)
            """,
            (job_id, scheduled),
        ).fetchall()
        return frozenset(str(row["post_id"]) for row in rows)

    def record_signal_family(
        self,
        *,
        logical_run_id: str,
        attempt_id: str,
        post_id: str,
        symbol: str,
        direction: Any,
        signal_family_id: str | None = None,
        family_status: str = "OPEN",
        source_system: str = "binance_square_scanner",
        now: datetime | str | None = None,
    ) -> StoredSignalFamily:
        """Create or update a signal family without changing its first sighting."""

        observed_at = format_utc(now or datetime.now(timezone.utc))
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._legal_attempt(logical_run_id, attempt_id)
            row = self._record_signal_family_in_transaction(
                logical_run_id=logical_run_id,
                attempt_id=attempt_id,
                post_id=post_id,
                symbol=symbol,
                direction=direction,
                signal_family_id=signal_family_id,
                family_status=family_status,
                source_system=source_system,
                observed_at=observed_at,
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        return self._stored_signal_family(row)

    upsert_signal_family = record_signal_family

    def record_signal_revision(
        self,
        *,
        logical_run_id: str,
        attempt_id: str,
        post_id: str,
        symbol: str,
        direction: Any,
        decision_at: datetime | str,
        parameter_source: Any,
        entry_low: Decimal,
        entry_high: Decimal,
        stop_loss: Decimal,
        tp1: Decimal,
        tp2: Decimal | None,
        original_signal_status: str,
        invalidation_reason: str | None = None,
        dq_score: int = 100,
        quality_flags: Iterable[str] = (),
        signal_family_id: str | None = None,
        family_status: str = "OPEN",
        source_system: str = "binance_square_scanner",
        now: datetime | str | None = None,
    ) -> StoredSignalRevision:
        """Atomically upsert a family and append one idempotent revision."""

        run_id = _required(logical_run_id, "logical_run_id")
        actual_attempt_id = _required(attempt_id, "attempt_id")
        observed_at = format_utc(now or datetime.now(timezone.utc))
        decision = format_utc(decision_at)
        if parse_utc(decision) > parse_utc(observed_at):
            raise ContractViolation("signal revision decision_at cannot be in the future")
        parameter = _enum_value(parameter_source, "parameter_source")
        if parameter not in {"AUTHOR", "SYSTEM_REDERIVED"}:
            raise ContractViolation("parameter_source is invalid")
        entry_low_text = _decimal_text(entry_low, "entry_low")
        entry_high_text = _decimal_text(entry_high, "entry_high")
        stop_loss_text = _decimal_text(stop_loss, "stop_loss")
        tp1_text = _decimal_text(tp1, "tp1")
        tp2_text = _decimal_text(tp2, "tp2")
        assert entry_low_text is not None
        assert entry_high_text is not None
        assert stop_loss_text is not None
        assert tp1_text is not None
        if entry_low > entry_high:
            raise ContractViolation("entry_low cannot exceed entry_high")
        signal_status = _required(original_signal_status, "original_signal_status")
        reason = (
            _required(invalidation_reason, "invalidation_reason")
            if invalidation_reason is not None
            else None
        )
        quality_json = _quality_flags_json(quality_flags)
        self._validate_dq_score(dq_score)
        source = _required(source_system, "source_system")

        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._legal_attempt(run_id, actual_attempt_id)
            family_row = self._record_signal_family_in_transaction(
                logical_run_id=run_id,
                attempt_id=actual_attempt_id,
                post_id=post_id,
                symbol=symbol,
                direction=direction,
                signal_family_id=signal_family_id,
                family_status=family_status,
                source_system=source,
                observed_at=observed_at,
            )
            actual_family_id = str(family_row["signal_family_id"])
            existing = self._connection.execute(
                """
                SELECT * FROM signal_revision
                WHERE signal_family_id = ? AND logical_run_id = ? AND attempt_id = ?
                """,
                (actual_family_id, run_id, actual_attempt_id),
            ).fetchone()
            expected = {
                "decision_at_utc": decision,
                "parameter_source": parameter,
                "entry_low_decimal": entry_low_text,
                "entry_high_decimal": entry_high_text,
                "stop_loss_decimal": stop_loss_text,
                "tp1_decimal": tp1_text,
                "tp2_decimal": tp2_text,
                "original_signal_status": signal_status,
                "invalidation_reason": reason,
                "dq_score": dq_score,
                "quality_flags_json": quality_json,
                "source_system": source,
            }
            if existing is not None:
                if any(existing[field] != value for field, value in expected.items()):
                    raise ContractViolation(
                        "signal revision idempotency key already has different evidence"
                    )
                revision_row = existing
            else:
                latest = self._connection.execute(
                    """
                    SELECT COALESCE(MAX(revision_no), 0) AS revision_no
                    FROM signal_revision WHERE signal_family_id = ?
                    """,
                    (actual_family_id,),
                ).fetchone()
                revision_no = int(latest["revision_no"]) + 1
                revision_id = _stable_id(
                    "signalrev", actual_family_id, run_id, actual_attempt_id
                )
                self._connection.execute(
                    """
                    INSERT INTO signal_revision (
                        signal_revision_id, signal_family_id, logical_run_id,
                        attempt_id, revision_no, decision_at_utc,
                        parameter_source, entry_low_decimal, entry_high_decimal,
                        stop_loss_decimal, tp1_decimal, tp2_decimal,
                        original_signal_status, invalidation_reason, dq_score,
                        quality_flags_json, schema_version, source_system,
                        created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                              ?, ?, ?, ?)
                    """,
                    (
                        revision_id,
                        actual_family_id,
                        run_id,
                        actual_attempt_id,
                        revision_no,
                        decision,
                        parameter,
                        entry_low_text,
                        entry_high_text,
                        stop_loss_text,
                        tp1_text,
                        tp2_text,
                        signal_status,
                        reason,
                        dq_score,
                        quality_json,
                        SCHEMA_VERSION,
                        source,
                        observed_at,
                        observed_at,
                    ),
                )
                revision_row = self._connection.execute(
                    "SELECT * FROM signal_revision WHERE signal_revision_id = ?",
                    (revision_id,),
                ).fetchone()
                if revision_row is None:
                    raise RuntimeError("signal revision insert was not observable")
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        return self._stored_signal_revision(revision_row)

    def record_tracking_evaluation(
        self,
        *,
        signal_revision_id: str,
        logical_run_id: str,
        attempt_id: str,
        evaluated_at: datetime | str,
        evaluation_status: Any,
        nominal_r: Decimal | None = None,
        mfe_r: Decimal | None = None,
        mae_r: Decimal | None = None,
        net_r: Decimal | None = None,
        cost_model_version: str | None = None,
        dq_score: int = 100,
        quality_flags: Iterable[str] = (),
        source_system: str = "binance_square_scanner",
        now: datetime | str | None = None,
    ) -> StoredTrackingEvaluation:
        """Persist one idempotent point-in-time tracking evaluation."""

        revision_id = _required(signal_revision_id, "signal_revision_id")
        run_id = _required(logical_run_id, "logical_run_id")
        actual_attempt_id = _required(attempt_id, "attempt_id")
        evaluated = format_utc(evaluated_at)
        observed_at = format_utc(now or datetime.now(timezone.utc))
        if parse_utc(evaluated) > parse_utc(observed_at):
            raise ContractViolation("tracking evaluation cannot be in the future")
        raw_status = _enum_value(evaluation_status, "evaluation_status")
        try:
            status = _TRACKING_STATUS_MAP[raw_status]
        except KeyError as exc:
            raise ContractViolation("evaluation_status is invalid") from exc
        nominal_text = _decimal_text(nominal_r, "nominal_r")
        mfe_text = _decimal_text(mfe_r, "mfe_r")
        mae_text = _decimal_text(mae_r, "mae_r")
        net_text = _decimal_text(net_r, "net_r")
        if mfe_r is not None and mfe_r < 0:
            raise ContractViolation("mfe_r must be non-negative")
        if mae_r is not None and mae_r < 0:
            raise ContractViolation("mae_r must be non-negative")
        cost_model = (
            _required(cost_model_version, "cost_model_version")
            if cost_model_version is not None
            else None
        )
        if net_text is not None and cost_model is None:
            raise ContractViolation("NET_R requires a cost model version")
        self._validate_dq_score(dq_score)
        quality_json = _quality_flags_json(quality_flags)
        source = _required(source_system, "source_system")

        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._legal_attempt(run_id, actual_attempt_id)
            revision = self._connection.execute(
                """
                SELECT revision.*, attempt.status AS revision_attempt_status
                FROM signal_revision AS revision
                JOIN run_attempt AS attempt
                  ON attempt.logical_run_id = revision.logical_run_id
                 AND attempt.attempt_id = revision.attempt_id
                WHERE revision.signal_revision_id = ?
                """,
                (revision_id,),
            ).fetchone()
            if revision is None:
                raise ContractViolation("tracking evaluation requires an existing revision")
            if revision["revision_attempt_status"] not in {"RUNNING", "SUCCEEDED"}:
                raise ContractViolation(
                    "tracking evaluation cannot reference a failed revision"
                )
            if parse_utc(evaluated) < parse_utc(revision["decision_at_utc"]):
                raise ContractViolation(
                    "tracking evaluation cannot precede its signal revision"
                )
            evaluation_id = _stable_id("trackeval", revision_id, evaluated)
            existing = self._connection.execute(
                """
                SELECT * FROM tracking_evaluation
                WHERE signal_revision_id = ? AND evaluated_at_utc = ?
                """,
                (revision_id, evaluated),
            ).fetchone()
            expected = {
                "logical_run_id": run_id,
                "attempt_id": actual_attempt_id,
                "evaluation_status": status,
                "nominal_r_decimal": nominal_text,
                "mfe_r_decimal": mfe_text,
                "mae_r_decimal": mae_text,
                "net_r_decimal": net_text,
                "cost_model_version": cost_model,
                "dq_score": dq_score,
                "quality_flags_json": quality_json,
                "source_system": source,
            }
            if existing is not None:
                if any(existing[field] != value for field, value in expected.items()):
                    raise ContractViolation(
                        "tracking evaluation idempotency key already has different evidence"
                    )
                evaluation_row = existing
            else:
                self._connection.execute(
                    """
                    INSERT INTO tracking_evaluation (
                        tracking_evaluation_id, signal_revision_id,
                        logical_run_id, attempt_id, evaluated_at_utc,
                        evaluation_status, nominal_r_decimal, mfe_r_decimal,
                        mae_r_decimal, net_r_decimal, cost_model_version,
                        dq_score, quality_flags_json, schema_version,
                        source_system, created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evaluation_id,
                        revision_id,
                        run_id,
                        actual_attempt_id,
                        evaluated,
                        status,
                        nominal_text,
                        mfe_text,
                        mae_text,
                        net_text,
                        cost_model,
                        dq_score,
                        quality_json,
                        SCHEMA_VERSION,
                        source,
                        observed_at,
                        observed_at,
                    ),
                )
                evaluation_row = self._connection.execute(
                    """
                    SELECT * FROM tracking_evaluation
                    WHERE tracking_evaluation_id = ?
                    """,
                    (evaluation_id,),
                ).fetchone()
                if evaluation_row is None:
                    raise RuntimeError("tracking evaluation insert was not observable")
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        return self._stored_tracking_evaluation(evaluation_row)

    def list_current_signal_revisions(
        self, *, as_of: datetime | str
    ) -> list[StoredSignalRevision]:
        """Return the latest legal revision per family at or before ``as_of``."""

        cutoff = format_utc(as_of)
        rows = self._connection.execute(
            """
            SELECT revision.*
            FROM signal_revision AS revision
            JOIN run_attempt AS attempt
              ON attempt.logical_run_id = revision.logical_run_id
             AND attempt.attempt_id = revision.attempt_id
            WHERE attempt.status IN ('RUNNING', 'SUCCEEDED')
              AND julianday(revision.decision_at_utc) <= julianday(?)
            ORDER BY revision.signal_family_id,
                     julianday(revision.decision_at_utc),
                     revision.revision_no, revision.signal_revision_id
            """,
            (cutoff,),
        ).fetchall()
        current: dict[str, sqlite3.Row] = {}
        for row in rows:
            current[str(row["signal_family_id"])] = row
        return [
            self._stored_signal_revision(row)
            for _, row in sorted(current.items())
        ]

    current_signal_revisions = list_current_signal_revisions

    def list_tracking_evaluations(
        self,
        *,
        as_of: datetime | str,
        signal_revision_id: str | None = None,
    ) -> list[StoredTrackingEvaluation]:
        """Read legal evaluations without exposing future evaluation evidence."""

        cutoff = format_utc(as_of)
        parameters: list[str] = [cutoff, cutoff]
        revision_filter = ""
        if signal_revision_id is not None:
            revision_filter = " AND evaluation.signal_revision_id = ?"
            parameters.append(_required(signal_revision_id, "signal_revision_id"))
        rows = self._connection.execute(
            f"""
            SELECT evaluation.*
            FROM tracking_evaluation AS evaluation
            JOIN run_attempt AS evaluation_attempt
              ON evaluation_attempt.logical_run_id = evaluation.logical_run_id
             AND evaluation_attempt.attempt_id = evaluation.attempt_id
            JOIN signal_revision AS revision
              ON revision.signal_revision_id = evaluation.signal_revision_id
            JOIN run_attempt AS revision_attempt
              ON revision_attempt.logical_run_id = revision.logical_run_id
             AND revision_attempt.attempt_id = revision.attempt_id
            WHERE evaluation_attempt.status IN ('RUNNING', 'SUCCEEDED')
              AND revision_attempt.status IN ('RUNNING', 'SUCCEEDED')
              AND julianday(evaluation.evaluated_at_utc) <= julianday(?)
              AND julianday(revision.decision_at_utc) <= julianday(?)
              {revision_filter}
            ORDER BY julianday(evaluation.evaluated_at_utc),
                     evaluation.tracking_evaluation_id
            """,
            parameters,
        ).fetchall()
        return [self._stored_tracking_evaluation(row) for row in rows]

    evaluations_as_of = list_tracking_evaluations

    def list_latest_tracking_evaluations(
        self, *, as_of: datetime | str
    ) -> list[StoredTrackingEvaluation]:
        latest: dict[str, StoredTrackingEvaluation] = {}
        for evaluation in self.list_tracking_evaluations(as_of=as_of):
            latest[evaluation.signal_revision_id] = evaluation
        return [latest[key] for key in sorted(latest)]

    def list_pending_signal_revisions(
        self, *, as_of: datetime | str
    ) -> list[StoredSignalRevision]:
        """Return open current revisions whose latest state still needs tracking."""

        current = self.list_current_signal_revisions(as_of=as_of)
        latest_evaluations = {
            value.signal_revision_id: value
            for value in self.list_latest_tracking_evaluations(as_of=as_of)
        }
        if not current:
            return []
        family_ids = [revision.signal_family_id for revision in current]
        placeholders = ",".join("?" for _ in family_ids)
        statuses = {
            str(row["signal_family_id"]): str(row["family_status"])
            for row in self._connection.execute(
                f"""
                SELECT signal_family_id, family_status FROM signal_family
                WHERE signal_family_id IN ({placeholders})
                """,
                family_ids,
            ).fetchall()
        }
        return [
            revision
            for revision in current
            if statuses.get(revision.signal_family_id) == "OPEN"
            and (
                revision.signal_revision_id not in latest_evaluations
                or latest_evaluations[revision.signal_revision_id].evaluation_status
                not in _TERMINAL_TRACKING_STATUSES
            )
        ]

    pending_signal_revisions = list_pending_signal_revisions

    def record_smart_money_leaderboard_capture(
        self,
        *,
        logical_run_id: str,
        attempt_id: str,
        ranking_type: str,
        captured_at: datetime | str,
        snapshot_semantics: str,
        observed_start: datetime | str,
        observed_end: datetime | str,
        last_update_time_ms: int | None,
        capture_status: str,
        evidence_path: str,
        evidence_file_sha256: str,
        rows: Iterable[SmartMoneyLeaderboardRowInput],
        payload_sha256: str | None = None,
        expected_rows: int = 30,
        failure_reason: str | None = None,
        source_system: str = "binance_smart_money",
        now: datetime | str | None = None,
    ) -> tuple[SmartMoneyLeaderboardCapture, tuple[SmartMoneyLeaderboardRow, ...]]:
        """Atomically persist one PNL/ROI 30D capture and all of its rows.

        The idempotency key is ``attempt_id + ranking_type + 30D``.  A retry
        with different evidence is rejected instead of silently overwriting a
        source snapshot.
        """

        run_id = _required(logical_run_id, "logical_run_id")
        actual_attempt_id = _required(attempt_id, "attempt_id")
        ranking = _enum_value(ranking_type, "ranking_type")
        if ranking not in {"PNL", "ROI"}:
            raise ContractViolation("ranking_type must be PNL or ROI")
        status = _enum_value(capture_status, "capture_status")
        if status not in {"COMPLETE", "FAILED"}:
            raise ContractViolation("capture_status must be COMPLETE or FAILED")
        if expected_rows != 30 or isinstance(expected_rows, bool):
            raise ContractViolation("Smart Money expected_rows must equal 30")
        captured = format_utc(captured_at)
        semantics = _enum_value(snapshot_semantics, "snapshot_semantics")
        if semantics != "OBSERVED_WINDOW":
            raise ContractViolation(
                "snapshot_semantics must be OBSERVED_WINDOW"
            )
        observed_start_utc = format_utc(observed_start)
        observed_end_utc = format_utc(observed_end)
        if not (
            parse_utc(observed_start_utc)
            <= parse_utc(observed_end_utc)
            <= parse_utc(captured)
        ):
            raise ContractViolation(
                "observed window must satisfy observed_start <= observed_end <= captured_at"
            )
        observed_at = format_utc(now or datetime.now(timezone.utc))
        if parse_utc(captured) > parse_utc(observed_at):
            raise ContractViolation("captured_at cannot be in the future")
        if last_update_time_ms is not None and (
            not isinstance(last_update_time_ms, int)
            or isinstance(last_update_time_ms, bool)
            or last_update_time_ms < 0
        ):
            raise ContractViolation("last_update_time_ms must be non-negative or None")
        path = _required(evidence_path, "evidence_path")
        file_digest = _verified_file_sha256(path, evidence_file_sha256)
        payload_digest = (
            _sha256_text(payload_sha256, "payload_sha256")
            if payload_sha256 is not None
            else None
        )
        source = _required(source_system, "source_system")
        reason = (
            _required(failure_reason, "failure_reason")
            if failure_reason is not None
            else None
        )
        values = list(rows)
        if not all(isinstance(value, SmartMoneyLeaderboardRowInput) for value in values):
            raise ContractViolation(
                "rows must use SmartMoneyLeaderboardRowInput contracts"
            )
        if status == "COMPLETE":
            if reason is not None:
                raise ContractViolation("COMPLETE capture cannot have failure_reason")
            if last_update_time_ms is None:
                raise ContractViolation(
                    "COMPLETE capture requires last_update_time_ms"
                )
            if len(values) != 30:
                raise ContractViolation("COMPLETE Smart Money capture requires 30 rows")
        else:
            if reason is None:
                raise ContractViolation("FAILED capture requires failure_reason")
            if values:
                raise ContractViolation("FAILED Smart Money capture cannot contain rows")

        normalized_rows: list[dict[str, Any]] = []
        ranks: list[int] = []
        trader_ids: list[str] = []
        for value in values:
            if (
                not isinstance(value.rank_no, int)
                or isinstance(value.rank_no, bool)
                or value.rank_no < 1
                or value.rank_no > 30
            ):
                raise ContractViolation("rank_no must be an integer from 1 to 30")
            top_trader_id = _required(value.top_trader_id, "top_trader_id")
            if value.subscribers is not None and (
                not isinstance(value.subscribers, int)
                or isinstance(value.subscribers, bool)
                or value.subscribers < 0
            ):
                raise ContractViolation("subscribers must be non-negative or None")
            position_status = (
                _required(value.position_status, "position_status")
                if value.position_status is not None
                else None
            )
            if value.raw is None:
                raise ContractViolation("COMPLETE rows require raw source JSON")
            if (
                not isinstance(value.raw, dict)
                or value.raw.get("topTraderId") != top_trader_id
            ):
                raise ContractViolation(
                    "raw.topTraderId must equal top_trader_id"
                )
            pnl_decimal = _decimal_text(value.pnl, "pnl")
            roi_decimal = _decimal_text(value.roi, "roi")
            if ranking == "PNL" and pnl_decimal is None:
                raise ContractViolation("PNL rows require pnl")
            if ranking == "ROI" and roi_decimal is None:
                raise ContractViolation("ROI rows require roi")
            normalized_rows.append(
                {
                    "rank_no": value.rank_no,
                    "top_trader_id": top_trader_id,
                    "pnl_decimal": pnl_decimal,
                    "roi_decimal": roi_decimal,
                    "assets_json": _canonical_json(value.assets, "assets"),
                    "subscribers": value.subscribers,
                    "position_status": position_status,
                    "signal_lead_on": _optional_bool(
                        value.signal_lead_on, "signal_lead_on"
                    ),
                    "raw_row_json": _canonical_json(value.raw, "raw"),
                }
            )
            ranks.append(value.rank_no)
            trader_ids.append(top_trader_id)
        if len(ranks) != len(set(ranks)):
            raise ContractViolation("Smart Money capture contains duplicate rank")
        if len(trader_ids) != len(set(trader_ids)):
            raise ContractViolation("Smart Money capture contains duplicate topTraderId")
        if status == "COMPLETE" and sorted(ranks) != list(range(1, 31)):
            raise ContractViolation("COMPLETE capture ranks must be exactly 1 through 30")

        capture_id = _stable_id(
            "smartmoneycapture", actual_attempt_id, ranking, "30D"
        )
        capture_expected = {
            "logical_run_id": run_id,
            "attempt_id": actual_attempt_id,
            "ranking_type": ranking,
            "time_range": "30D",
            "capture_status": status,
            "captured_at_utc": captured,
            "snapshot_semantics": semantics,
            "observed_start_utc": observed_start_utc,
            "observed_end_utc": observed_end_utc,
            "last_update_time_ms": last_update_time_ms,
            "evidence_path": path,
            "evidence_file_sha256": file_digest,
            "payload_sha256": payload_digest,
            "expected_rows": 30,
            "rendered_rows": len(normalized_rows),
            "failure_reason": reason,
            "source_system": source,
        }
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._legal_attempt(run_id, actual_attempt_id)
            existing = self._connection.execute(
                "SELECT * FROM smart_money_leaderboard_capture "
                "WHERE smart_money_capture_id = ?",
                (capture_id,),
            ).fetchone()
            if existing is not None:
                if any(existing[field] != value for field, value in capture_expected.items()):
                    raise ContractViolation(
                        "Smart Money capture idempotency key has different evidence"
                    )
                persisted = self._connection.execute(
                    "SELECT * FROM smart_money_leaderboard_row "
                    "WHERE smart_money_capture_id = ? ORDER BY rank_no",
                    (capture_id,),
                ).fetchall()
                if len(persisted) != len(normalized_rows) or any(
                    any(actual[field] != expected[field] for field in expected)
                    for actual, expected in zip(persisted, normalized_rows)
                ):
                    raise ContractViolation(
                        "Smart Money capture idempotency key has different rows"
                    )
                capture_row = existing
                row_records = persisted
            else:
                for expected in normalized_rows:
                    self._connection.execute(
                        """
                        INSERT OR IGNORE INTO smart_money_trader_entity (
                            top_trader_id, identity_source, schema_version,
                            source_system, created_at_utc, updated_at_utc
                        ) VALUES (?, 'BINANCE_SMART_MONEY_TOP_TRADER_ID', ?, ?, ?, ?)
                        """,
                        (
                            expected["top_trader_id"],
                            SCHEMA_VERSION,
                            source,
                            observed_at,
                            observed_at,
                        ),
                    )
                self._connection.execute(
                    """
                    INSERT INTO smart_money_leaderboard_capture (
                        smart_money_capture_id, logical_run_id, attempt_id,
                        ranking_type, time_range, capture_status, captured_at_utc,
                        snapshot_semantics, observed_start_utc, observed_end_utc,
                        last_update_time_ms, evidence_path, evidence_file_sha256,
                        payload_sha256,
                        expected_rows, rendered_rows, failure_reason,
                        schema_version, source_system, created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, '30D', ?, ?, ?, ?, ?, ?, ?, ?, ?, 30, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        capture_id,
                        run_id,
                        actual_attempt_id,
                        ranking,
                        status,
                        captured,
                        semantics,
                        observed_start_utc,
                        observed_end_utc,
                        last_update_time_ms,
                        path,
                        file_digest,
                        payload_digest,
                        len(normalized_rows),
                        reason,
                        SCHEMA_VERSION,
                        source,
                        observed_at,
                        observed_at,
                    ),
                )
                for expected in normalized_rows:
                    row_id = _stable_id(
                        "smartmoneyrow",
                        capture_id,
                        str(expected["rank_no"]),
                        expected["top_trader_id"],
                    )
                    self._connection.execute(
                        """
                        INSERT INTO smart_money_leaderboard_row (
                            smart_money_row_id, smart_money_capture_id,
                            top_trader_id, rank_no, pnl_decimal, roi_decimal,
                            assets_json, subscribers, position_status,
                            signal_lead_on, raw_row_json, schema_version,
                            source_system, created_at_utc, updated_at_utc
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            row_id,
                            capture_id,
                            expected["top_trader_id"],
                            expected["rank_no"],
                            expected["pnl_decimal"],
                            expected["roi_decimal"],
                            expected["assets_json"],
                            expected["subscribers"],
                            expected["position_status"],
                            expected["signal_lead_on"],
                            expected["raw_row_json"],
                            SCHEMA_VERSION,
                            source,
                            observed_at,
                            observed_at,
                        ),
                    )
                capture_row = self._connection.execute(
                    "SELECT * FROM smart_money_leaderboard_capture "
                    "WHERE smart_money_capture_id = ?",
                    (capture_id,),
                ).fetchone()
                row_records = self._connection.execute(
                    "SELECT * FROM smart_money_leaderboard_row "
                    "WHERE smart_money_capture_id = ? ORDER BY rank_no",
                    (capture_id,),
                ).fetchall()
            self._connection.commit()
        except sqlite3.IntegrityError as exc:
            self._connection.rollback()
            raise ContractViolation("Smart Money capture violated storage contract") from exc
        except Exception:
            self._connection.rollback()
            raise
        if capture_row is None:
            raise RuntimeError("Smart Money capture insert was not observable")
        return (
            self._smart_money_capture(capture_row),
            tuple(self._smart_money_row(row) for row in row_records),
        )

    def list_smart_money_leaderboard_captures(
        self,
        *,
        logical_run_id: str | None = None,
        attempt_id: str | None = None,
        ranking_type: str | None = None,
    ) -> list[SmartMoneyLeaderboardCapture]:
        predicates: list[str] = []
        parameters: list[str] = []
        if logical_run_id is not None:
            predicates.append("logical_run_id = ?")
            parameters.append(_required(logical_run_id, "logical_run_id"))
        if attempt_id is not None:
            predicates.append("attempt_id = ?")
            parameters.append(_required(attempt_id, "attempt_id"))
        if ranking_type is not None:
            ranking = _enum_value(ranking_type, "ranking_type")
            if ranking not in {"PNL", "ROI"}:
                raise ContractViolation("ranking_type must be PNL or ROI")
            predicates.append("ranking_type = ?")
            parameters.append(ranking)
        where = f"WHERE {' AND '.join(predicates)}" if predicates else ""
        rows = self._connection.execute(
            f"SELECT * FROM smart_money_leaderboard_capture {where} "
            "ORDER BY captured_at_utc, ranking_type, smart_money_capture_id",
            parameters,
        ).fetchall()
        return [self._smart_money_capture(row) for row in rows]

    def list_smart_money_leaderboard_rows(
        self, smart_money_capture_id: str
    ) -> list[SmartMoneyLeaderboardRow]:
        rows = self._connection.execute(
            "SELECT * FROM smart_money_leaderboard_row "
            "WHERE smart_money_capture_id = ? ORDER BY rank_no",
            (_required(smart_money_capture_id, "smart_money_capture_id"),),
        ).fetchall()
        return [self._smart_money_row(row) for row in rows]

    def record_smart_money_profile_observation(
        self,
        *,
        logical_run_id: str,
        attempt_id: str,
        top_trader_id: str,
        observation_status: str,
        captured_at: datetime | str,
        evidence_path: str,
        evidence_file_sha256: str,
        days_active: int | None = None,
        mdd: Decimal | None = None,
        win_rate: Decimal | None = None,
        um_margin_balance: Decimal | None = None,
        cm_margin_balance: Decimal | None = None,
        net_transfer: Decimal | None = None,
        sharing_position: Any = None,
        sharing_history: Any = None,
        latest_record: Any = None,
        is_ai: bool | None = None,
        is_pm_user: bool | None = None,
        copy_trade_portfolio_ids: Any = None,
        payload_sha256: str | None = None,
        raw_profile: Any = None,
        failure_reason: str | None = None,
        source_system: str = "binance_smart_money_profile",
        now: datetime | str | None = None,
    ) -> SmartMoneyProfileObservation:
        """Persist one point-in-time Smart Money profile result or failure."""

        run_id = _required(logical_run_id, "logical_run_id")
        actual_attempt_id = _required(attempt_id, "attempt_id")
        trader_id = _required(top_trader_id, "top_trader_id")
        status = _enum_value(observation_status, "observation_status")
        if status not in {"COMPLETE", "FAILED"}:
            raise ContractViolation("observation_status must be COMPLETE or FAILED")
        captured = format_utc(captured_at)
        observed_at = format_utc(now or datetime.now(timezone.utc))
        if parse_utc(captured) > parse_utc(observed_at):
            raise ContractViolation("captured_at cannot be in the future")
        if days_active is not None and (
            not isinstance(days_active, int)
            or isinstance(days_active, bool)
            or days_active < 0
        ):
            raise ContractViolation("days_active must be non-negative or None")
        reason = (
            _required(failure_reason, "failure_reason")
            if failure_reason is not None
            else None
        )
        if status == "COMPLETE" and (reason is not None or raw_profile is None):
            raise ContractViolation(
                "COMPLETE profile requires raw_profile and no failure_reason"
            )
        if status == "COMPLETE" and (
            not isinstance(raw_profile, dict)
            or raw_profile.get("topTraderId") != trader_id
        ):
            raise ContractViolation(
                "raw_profile.topTraderId must equal top_trader_id"
            )
        if status == "FAILED" and reason is None:
            raise ContractViolation("FAILED profile requires failure_reason")
        path = _required(evidence_path, "evidence_path")
        file_digest = _verified_file_sha256(path, evidence_file_sha256)
        payload_digest = (
            _sha256_text(payload_sha256, "payload_sha256")
            if payload_sha256 is not None
            else None
        )
        source = _required(source_system, "source_system")

        nullable_json = lambda value, field: (  # noqa: E731 - compact normalization
            _canonical_json(value, field) if value is not None else None
        )
        expected = {
            "logical_run_id": run_id,
            "attempt_id": actual_attempt_id,
            "top_trader_id": trader_id,
            "observation_status": status,
            "captured_at_utc": captured,
            "days_active": days_active,
            "mdd_decimal": _decimal_text(mdd, "mdd"),
            "win_rate_decimal": _decimal_text(win_rate, "win_rate"),
            "um_margin_balance_decimal": _decimal_text(
                um_margin_balance, "um_margin_balance"
            ),
            "cm_margin_balance_decimal": _decimal_text(
                cm_margin_balance, "cm_margin_balance"
            ),
            "net_transfer_decimal": _decimal_text(net_transfer, "net_transfer"),
            "sharing_position_json": nullable_json(
                sharing_position, "sharing_position"
            ),
            "sharing_history_json": nullable_json(sharing_history, "sharing_history"),
            "latest_record_json": nullable_json(latest_record, "latest_record"),
            "is_ai": _optional_bool(is_ai, "is_ai"),
            "is_pm_user": _optional_bool(is_pm_user, "is_pm_user"),
            "copy_trade_portfolio_ids_json": nullable_json(
                copy_trade_portfolio_ids, "copy_trade_portfolio_ids"
            ),
            "evidence_path": path,
            "evidence_file_sha256": file_digest,
            "payload_sha256": payload_digest,
            "failure_reason": reason,
            "raw_profile_json": nullable_json(raw_profile, "raw_profile"),
            "source_system": source,
        }
        observation_id = _stable_id(
            "smartmoneyprofile", actual_attempt_id, trader_id
        )
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            self._legal_attempt(run_id, actual_attempt_id)
            existing = self._connection.execute(
                "SELECT * FROM smart_money_profile_observation "
                "WHERE smart_money_profile_observation_id = ?",
                (observation_id,),
            ).fetchone()
            if existing is not None:
                if any(existing[field] != value for field, value in expected.items()):
                    raise ContractViolation(
                        "Smart Money profile idempotency key has different evidence"
                    )
                profile_row = existing
            else:
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO smart_money_trader_entity (
                        top_trader_id, identity_source, schema_version,
                        source_system, created_at_utc, updated_at_utc
                    ) VALUES (?, 'BINANCE_SMART_MONEY_TOP_TRADER_ID', ?, ?, ?, ?)
                    """,
                    (trader_id, SCHEMA_VERSION, source, observed_at, observed_at),
                )
                self._connection.execute(
                    """
                    INSERT INTO smart_money_profile_observation (
                        smart_money_profile_observation_id, logical_run_id,
                        attempt_id, top_trader_id, observation_status,
                        captured_at_utc, days_active, mdd_decimal,
                        win_rate_decimal, um_margin_balance_decimal,
                        cm_margin_balance_decimal, net_transfer_decimal,
                        sharing_position_json, sharing_history_json,
                        latest_record_json, is_ai, is_pm_user,
                        copy_trade_portfolio_ids_json, evidence_path,
                        evidence_file_sha256, payload_sha256, failure_reason,
                        raw_profile_json,
                        schema_version, source_system, created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        observation_id,
                        run_id,
                        actual_attempt_id,
                        trader_id,
                        status,
                        captured,
                        days_active,
                        expected["mdd_decimal"],
                        expected["win_rate_decimal"],
                        expected["um_margin_balance_decimal"],
                        expected["cm_margin_balance_decimal"],
                        expected["net_transfer_decimal"],
                        expected["sharing_position_json"],
                        expected["sharing_history_json"],
                        expected["latest_record_json"],
                        expected["is_ai"],
                        expected["is_pm_user"],
                        expected["copy_trade_portfolio_ids_json"],
                        path,
                        file_digest,
                        payload_digest,
                        reason,
                        expected["raw_profile_json"],
                        SCHEMA_VERSION,
                        source,
                        observed_at,
                        observed_at,
                    ),
                )
                profile_row = self._connection.execute(
                    "SELECT * FROM smart_money_profile_observation "
                    "WHERE smart_money_profile_observation_id = ?",
                    (observation_id,),
                ).fetchone()
            self._connection.commit()
        except sqlite3.IntegrityError as exc:
            self._connection.rollback()
            raise ContractViolation("Smart Money profile violated storage contract") from exc
        except Exception:
            self._connection.rollback()
            raise
        if profile_row is None:
            raise RuntimeError("Smart Money profile insert was not observable")
        return self._smart_money_profile(profile_row)

    def list_smart_money_profile_observations(
        self,
        *,
        logical_run_id: str | None = None,
        attempt_id: str | None = None,
        top_trader_id: str | None = None,
    ) -> list[SmartMoneyProfileObservation]:
        predicates: list[str] = []
        parameters: list[str] = []
        for column, value in (
            ("logical_run_id", logical_run_id),
            ("attempt_id", attempt_id),
            ("top_trader_id", top_trader_id),
        ):
            if value is not None:
                predicates.append(f"{column} = ?")
                parameters.append(_required(value, column))
        where = f"WHERE {' AND '.join(predicates)}" if predicates else ""
        rows = self._connection.execute(
            f"SELECT * FROM smart_money_profile_observation {where} "
            "ORDER BY captured_at_utc, top_trader_id",
            parameters,
        ).fetchall()
        return [self._smart_money_profile(row) for row in rows]

    def record_smart_money_square_identity_mapping(
        self,
        *,
        top_trader_id: str,
        author_id: str,
        verified_at: datetime | str,
        evidence_path: str,
        evidence_sha256: str,
        verification_method: str = "EXPLICIT_SOURCE_EVIDENCE",
        source_system: str = "binance_identity_evidence",
        now: datetime | str | None = None,
    ) -> SmartMoneySquareIdentityMapping:
        """Record only explicit ID evidence; display-name mapping is unsupported."""

        trader_id = _required(top_trader_id, "top_trader_id")
        square_author_id = _required(author_id, "author_id")
        method = _enum_value(verification_method, "verification_method")
        if method != "EXPLICIT_SOURCE_EVIDENCE":
            raise ContractViolation(
                "Smart Money/Square mapping requires explicit source evidence"
            )
        verified = format_utc(verified_at)
        observed_at = format_utc(now or datetime.now(timezone.utc))
        if parse_utc(verified) > parse_utc(observed_at):
            raise ContractViolation("verified_at cannot be in the future")
        path = _required(evidence_path, "evidence_path")
        digest = _verified_identity_mapping_digest(
            path,
            evidence_sha256,
            top_trader_id=trader_id,
            square_uid=square_author_id,
        )
        source = _required(source_system, "source_system")
        expected = {
            "top_trader_id": trader_id,
            "author_id": square_author_id,
            "verification_method": method,
            "verified_at_utc": verified,
            "evidence_path": path,
            "evidence_sha256": digest,
            "source_system": source,
        }
        try:
            self._connection.execute("BEGIN IMMEDIATE")
            trader = self._connection.execute(
                "SELECT 1 FROM smart_money_trader_entity WHERE top_trader_id = ?",
                (trader_id,),
            ).fetchone()
            author = self._connection.execute(
                "SELECT 1 FROM author_entity WHERE author_id = ?",
                (square_author_id,),
            ).fetchone()
            if trader is None or author is None:
                raise ContractViolation(
                    "identity mapping requires existing source-specific entities"
                )
            existing = self._connection.execute(
                "SELECT * FROM smart_money_square_identity_mapping "
                "WHERE top_trader_id = ? OR author_id = ?",
                (trader_id, square_author_id),
            ).fetchone()
            if existing is not None:
                if any(existing[field] != value for field, value in expected.items()):
                    raise ContractViolation("Smart Money/Square identity mapping conflict")
                mapping_row = existing
            else:
                self._connection.execute(
                    """
                    INSERT INTO smart_money_square_identity_mapping (
                        top_trader_id, author_id, verification_method,
                        verified_at_utc, evidence_path, evidence_sha256,
                        schema_version, source_system, created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trader_id,
                        square_author_id,
                        method,
                        verified,
                        path,
                        digest,
                        SCHEMA_VERSION,
                        source,
                        observed_at,
                        observed_at,
                    ),
                )
                mapping_row = self._connection.execute(
                    "SELECT * FROM smart_money_square_identity_mapping "
                    "WHERE top_trader_id = ?",
                    (trader_id,),
                ).fetchone()
            self._connection.commit()
        except sqlite3.IntegrityError as exc:
            self._connection.rollback()
            raise ContractViolation("Smart Money/Square identity mapping conflict") from exc
        except Exception:
            self._connection.rollback()
            raise
        if mapping_row is None:
            raise RuntimeError("identity mapping insert was not observable")
        return self._smart_money_identity_mapping(mapping_row)

    def list_smart_money_square_identity_mappings(
        self,
    ) -> list[SmartMoneySquareIdentityMapping]:
        rows = self._connection.execute(
            "SELECT * FROM smart_money_square_identity_mapping "
            "ORDER BY top_trader_id"
        ).fetchall()
        return [self._smart_money_identity_mapping(row) for row in rows]

    def _legal_attempt(self, logical_run_id: str, attempt_id: str) -> sqlite3.Row:
        run_id = _required(logical_run_id, "logical_run_id")
        actual_attempt_id = _required(attempt_id, "attempt_id")
        row = self._connection.execute(
            """
            SELECT attempt.*, logical.run_namespace, logical.scheduled_for_utc
            FROM run_attempt AS attempt
            JOIN logical_run AS logical
              ON logical.logical_run_id = attempt.logical_run_id
            WHERE attempt.logical_run_id = ? AND attempt.attempt_id = ?
            """,
            (run_id, actual_attempt_id),
        ).fetchone()
        if row is None:
            raise ContractViolation("state write must reference its exact run attempt")
        if row["status"] not in {"RUNNING", "SUCCEEDED"}:
            raise ContractViolation("state write cannot reference a FAILED attempt")
        return row

    def _record_signal_family_in_transaction(
        self,
        *,
        logical_run_id: str,
        attempt_id: str,
        post_id: str,
        symbol: str,
        direction: Any,
        signal_family_id: str | None,
        family_status: str,
        source_system: str,
        observed_at: str,
    ) -> sqlite3.Row:
        actual_post_id = _required(post_id, "post_id")
        if not actual_post_id.isdecimal():
            raise ContractViolation("post_id must be a stable numeric ID")
        actual_symbol = _required(symbol, "symbol").upper()
        actual_direction = _enum_value(direction, "direction")
        if actual_direction not in {"LONG", "SHORT"}:
            raise ContractViolation("direction must be LONG or SHORT")
        status = _enum_value(family_status, "family_status")
        if status not in {"OPEN", "INVALIDATED", "CLOSED"}:
            raise ContractViolation("family_status is invalid")
        source = _required(source_system, "source_system")
        canonical_family_id = f"{actual_post_id}:{actual_symbol}:{actual_direction}"
        requested_family_id = (
            _required(signal_family_id, "signal_family_id")
            if signal_family_id is not None
            else canonical_family_id
        )
        if requested_family_id != canonical_family_id:
            raise ContractViolation(
                "signal_family_id must equal post_id:symbol:direction"
            )
        existing = self._connection.execute(
            """
            SELECT * FROM signal_family
            WHERE post_id = ? AND symbol = ? AND direction = ?
            """,
            (actual_post_id, actual_symbol, actual_direction),
        ).fetchone()
        if existing is None:
            self._connection.execute(
                """
                INSERT INTO signal_family (
                    signal_family_id, post_id, symbol, direction,
                    first_logical_run_id, first_attempt_id, family_status,
                    schema_version, source_system, created_at_utc, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    requested_family_id,
                    actual_post_id,
                    actual_symbol,
                    actual_direction,
                    _required(logical_run_id, "logical_run_id"),
                    _required(attempt_id, "attempt_id"),
                    status,
                    SCHEMA_VERSION,
                    source,
                    observed_at,
                    observed_at,
                ),
            )
        else:
            if existing["signal_family_id"] != requested_family_id:
                raise ContractViolation("signal family stable identity collision")
            previous_status = str(existing["family_status"])
            if previous_status in {"INVALIDATED", "CLOSED"} and status != previous_status:
                raise ContractViolation("terminal signal family cannot change status")
            if status != previous_status:
                self._connection.execute(
                    """
                    UPDATE signal_family SET family_status = ?, updated_at_utc = ?
                    WHERE signal_family_id = ?
                    """,
                    (status, observed_at, requested_family_id),
                )
        row = self._connection.execute(
            "SELECT * FROM signal_family WHERE signal_family_id = ?",
            (requested_family_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError("signal family upsert was not observable")
        return row

    @staticmethod
    def _validate_dq_score(value: int) -> None:
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or value < 0
            or value > 100
        ):
            raise ContractViolation("dq_score must be an integer from 0 to 100")

    def enqueue_delivery(
        self,
        *,
        logical_run_id: str,
        report_sha256: str,
        payload_path: str,
        now: datetime | str | None = None,
    ) -> DeliveryOutboxItem:
        run_id = _required(logical_run_id, "logical_run_id")
        row = self._connection.execute(
            "SELECT run_namespace FROM logical_run WHERE logical_run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            raise ContractViolation("delivery must reference an existing logical run")
        if RunNamespace(row["run_namespace"]) is not RunNamespace.PRODUCTION:
            raise ContractViolation("replay runs cannot write the production outbox")
        digest = _required(report_sha256, "report_sha256").lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ContractViolation(
                "report_sha256 must contain exactly 64 hexadecimal characters"
            )
        path = _required(payload_path, "payload_path")
        observed_at = format_utc(now or datetime.now(timezone.utc))
        outbox_id = _stable_id("outbox", run_id)
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT OR IGNORE INTO delivery_outbox (
                        outbox_id, logical_run_id, report_sha256, payload_path,
                        status, schema_version, source_system,
                        created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, 'PENDING', ?, ?, ?, ?)
                    """,
                    (
                        outbox_id,
                        run_id,
                        digest,
                        path,
                        SCHEMA_VERSION,
                        "binance_square_scanner",
                        observed_at,
                        observed_at,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise ContractViolation("delivery outbox rejected the logical run") from exc
        queued = self._connection.execute(
            "SELECT * FROM delivery_outbox WHERE logical_run_id = ?", (run_id,)
        ).fetchone()
        if queued is None:
            raise RuntimeError("delivery outbox insert was not observable")
        return self._delivery_outbox_item(queued)

    def list_delivery_outbox(self) -> list[DeliveryOutboxItem]:
        rows = self._connection.execute(
            "SELECT * FROM delivery_outbox ORDER BY created_at_utc, outbox_id"
        ).fetchall()
        return [self._delivery_outbox_item(row) for row in rows]

    def integrity_check(self) -> str:
        """Return SQLite's integrity verdict for acceptance receipts."""

        rows = self._connection.execute("PRAGMA integrity_check").fetchall()
        return "\n".join(str(row[0]) for row in rows)

    def foreign_key_check(self) -> list[tuple[object, ...]]:
        """Return every foreign-key violation; an empty list is clean."""

        rows = self._connection.execute("PRAGMA foreign_key_check").fetchall()
        return [tuple(row) for row in rows]

    def list_logical_runs(self) -> list[LogicalRun]:
        rows = self._connection.execute(
            "SELECT * FROM logical_run ORDER BY created_at_utc, logical_run_id"
        ).fetchall()
        return [self._logical_run(row) for row in rows]

    @staticmethod
    def _logical_run(row: sqlite3.Row) -> LogicalRun:
        return LogicalRun(
            logical_run_id=row["logical_run_id"],
            run_namespace=RunNamespace(row["run_namespace"]),
            pipeline_version=row["pipeline_version"],
            production_job_id=row["production_job_id"],
            scheduled_for_utc=row["scheduled_for_utc"],
            replay_namespace=row["replay_namespace"],
            source_logical_run_id=row["source_logical_run_id"],
            schema_version=row["schema_version"],
            source_system=row["source_system"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )

    @staticmethod
    def _production_run_cutoff(row: sqlite3.Row) -> ProductionRunCutoff:
        return ProductionRunCutoff(
            logical_run_id=row["logical_run_id"],
            decision_at_utc=row["decision_at_utc"],
            schema_version=row["schema_version"],
            source_system=row["source_system"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )

    @staticmethod
    def _run_attempt(row: sqlite3.Row) -> RunAttempt:
        return RunAttempt(
            attempt_id=row["attempt_id"],
            logical_run_id=row["logical_run_id"],
            attempt_no=row["attempt_no"],
            status=row["status"],
            started_at_utc=row["started_at_utc"],
            finished_at_utc=row["finished_at_utc"],
            failed_stage=row["failed_stage"],
            recovered_silently=bool(row["recovered_silently"]),
            alert_sent_at_utc=row["alert_sent_at_utc"],
            schema_version=row["schema_version"],
            source_system=row["source_system"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )

    @staticmethod
    def _bronze_manifest(row: sqlite3.Row) -> BronzeManifest:
        return BronzeManifest(
            manifest_id=row["manifest_id"],
            logical_run_id=row["logical_run_id"],
            attempt_id=row["attempt_id"],
            artifact_path=row["artifact_path"],
            sha256_hex=row["sha256_hex"],
            payload_schema_version=row["payload_schema_version"],
            event_start_utc=row["event_start_utc"],
            event_end_utc=row["event_end_utc"],
            record_count=row["record_count"],
            schema_version=row["schema_version"],
            source_system=row["source_system"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )

    @staticmethod
    def _delivery_outbox_item(row: sqlite3.Row) -> DeliveryOutboxItem:
        return DeliveryOutboxItem(
            outbox_id=row["outbox_id"],
            logical_run_id=row["logical_run_id"],
            report_sha256=row["report_sha256"],
            payload_path=row["payload_path"],
            status=row["status"],
            schema_version=row["schema_version"],
            source_system=row["source_system"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )

    @staticmethod
    def _stored_post_observation(row: sqlite3.Row) -> StoredPostObservation:
        return StoredPostObservation(
            post_observation_id=row["post_observation_id"],
            logical_run_id=row["logical_run_id"],
            attempt_id=row["attempt_id"],
            post_id=row["post_id"],
            canonical_post_url=row["canonical_post_url"],
            author_id=row["author_id"],
            published_at_utc=row["published_at_utc"],
            observed_at_utc=row["observed_at_utc"],
            content_hash=row["content_hash"],
            source_channel=row["source_channel"],
            source_record_ordinal=row["source_record_ordinal"],
            observation_status=row["observation_status"],
            schema_version=row["schema_version"],
            source_system=row["source_system"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )

    @staticmethod
    def _smart_money_capture(row: sqlite3.Row) -> SmartMoneyLeaderboardCapture:
        return SmartMoneyLeaderboardCapture(
            smart_money_capture_id=row["smart_money_capture_id"],
            logical_run_id=row["logical_run_id"],
            attempt_id=row["attempt_id"],
            ranking_type=row["ranking_type"],
            time_range=row["time_range"],
            capture_status=row["capture_status"],
            captured_at_utc=row["captured_at_utc"],
            snapshot_semantics=row["snapshot_semantics"],
            observed_start_utc=row["observed_start_utc"],
            observed_end_utc=row["observed_end_utc"],
            last_update_time_ms=row["last_update_time_ms"],
            evidence_path=row["evidence_path"],
            evidence_file_sha256=row["evidence_file_sha256"],
            payload_sha256=row["payload_sha256"],
            expected_rows=row["expected_rows"],
            rendered_rows=row["rendered_rows"],
            failure_reason=row["failure_reason"],
            schema_version=row["schema_version"],
            source_system=row["source_system"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )

    @staticmethod
    def _smart_money_row(row: sqlite3.Row) -> SmartMoneyLeaderboardRow:
        return SmartMoneyLeaderboardRow(
            smart_money_row_id=row["smart_money_row_id"],
            smart_money_capture_id=row["smart_money_capture_id"],
            top_trader_id=row["top_trader_id"],
            rank_no=row["rank_no"],
            pnl_decimal=row["pnl_decimal"],
            roi_decimal=row["roi_decimal"],
            assets=json.loads(row["assets_json"]),
            subscribers=row["subscribers"],
            position_status=row["position_status"],
            signal_lead_on=(
                bool(row["signal_lead_on"])
                if row["signal_lead_on"] is not None
                else None
            ),
            raw=json.loads(row["raw_row_json"]),
            schema_version=row["schema_version"],
            source_system=row["source_system"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )

    @staticmethod
    def _smart_money_profile(row: sqlite3.Row) -> SmartMoneyProfileObservation:
        load_optional = lambda value: json.loads(value) if value is not None else None
        return SmartMoneyProfileObservation(
            smart_money_profile_observation_id=row[
                "smart_money_profile_observation_id"
            ],
            logical_run_id=row["logical_run_id"],
            attempt_id=row["attempt_id"],
            top_trader_id=row["top_trader_id"],
            observation_status=row["observation_status"],
            captured_at_utc=row["captured_at_utc"],
            days_active=row["days_active"],
            mdd_decimal=row["mdd_decimal"],
            win_rate_decimal=row["win_rate_decimal"],
            um_margin_balance_decimal=row["um_margin_balance_decimal"],
            cm_margin_balance_decimal=row["cm_margin_balance_decimal"],
            net_transfer_decimal=row["net_transfer_decimal"],
            sharing_position=load_optional(row["sharing_position_json"]),
            sharing_history=load_optional(row["sharing_history_json"]),
            latest_record=load_optional(row["latest_record_json"]),
            is_ai=bool(row["is_ai"]) if row["is_ai"] is not None else None,
            is_pm_user=(
                bool(row["is_pm_user"])
                if row["is_pm_user"] is not None
                else None
            ),
            copy_trade_portfolio_ids=load_optional(
                row["copy_trade_portfolio_ids_json"]
            ),
            evidence_path=row["evidence_path"],
            evidence_file_sha256=row["evidence_file_sha256"],
            payload_sha256=row["payload_sha256"],
            failure_reason=row["failure_reason"],
            raw_profile=load_optional(row["raw_profile_json"]),
            schema_version=row["schema_version"],
            source_system=row["source_system"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )

    @staticmethod
    def _smart_money_identity_mapping(
        row: sqlite3.Row,
    ) -> SmartMoneySquareIdentityMapping:
        return SmartMoneySquareIdentityMapping(
            top_trader_id=row["top_trader_id"],
            author_id=row["author_id"],
            verification_method=row["verification_method"],
            verified_at_utc=row["verified_at_utc"],
            evidence_path=row["evidence_path"],
            evidence_sha256=row["evidence_sha256"],
            schema_version=row["schema_version"],
            source_system=row["source_system"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )

    @staticmethod
    def _stored_signal_family(row: sqlite3.Row) -> StoredSignalFamily:
        return StoredSignalFamily(
            signal_family_id=row["signal_family_id"],
            post_id=row["post_id"],
            symbol=row["symbol"],
            direction=row["direction"],
            first_logical_run_id=row["first_logical_run_id"],
            first_attempt_id=row["first_attempt_id"],
            family_status=row["family_status"],
            schema_version=row["schema_version"],
            source_system=row["source_system"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )

    @staticmethod
    def _stored_signal_revision(row: sqlite3.Row) -> StoredSignalRevision:
        quality_flags = json.loads(row["quality_flags_json"])
        if not isinstance(quality_flags, list) or not all(
            isinstance(value, str) for value in quality_flags
        ):
            raise RuntimeError("stored signal revision quality flags are invalid")
        return StoredSignalRevision(
            signal_revision_id=row["signal_revision_id"],
            signal_family_id=row["signal_family_id"],
            logical_run_id=row["logical_run_id"],
            attempt_id=row["attempt_id"],
            revision_no=row["revision_no"],
            decision_at_utc=row["decision_at_utc"],
            parameter_source=row["parameter_source"],
            entry_low_decimal=row["entry_low_decimal"],
            entry_high_decimal=row["entry_high_decimal"],
            stop_loss_decimal=row["stop_loss_decimal"],
            tp1_decimal=row["tp1_decimal"],
            tp2_decimal=row["tp2_decimal"],
            original_signal_status=row["original_signal_status"],
            invalidation_reason=row["invalidation_reason"],
            dq_score=row["dq_score"],
            quality_flags=tuple(quality_flags),
            schema_version=row["schema_version"],
            source_system=row["source_system"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )

    @staticmethod
    def _stored_tracking_evaluation(row: sqlite3.Row) -> StoredTrackingEvaluation:
        quality_flags = json.loads(row["quality_flags_json"])
        if not isinstance(quality_flags, list) or not all(
            isinstance(value, str) for value in quality_flags
        ):
            raise RuntimeError("stored tracking evaluation quality flags are invalid")
        return StoredTrackingEvaluation(
            tracking_evaluation_id=row["tracking_evaluation_id"],
            signal_revision_id=row["signal_revision_id"],
            logical_run_id=row["logical_run_id"],
            attempt_id=row["attempt_id"],
            evaluated_at_utc=row["evaluated_at_utc"],
            evaluation_status=row["evaluation_status"],
            nominal_r_decimal=row["nominal_r_decimal"],
            mfe_r_decimal=row["mfe_r_decimal"],
            mae_r_decimal=row["mae_r_decimal"],
            net_r_decimal=row["net_r_decimal"],
            cost_model_version=row["cost_model_version"],
            dq_score=row["dq_score"],
            quality_flags=tuple(quality_flags),
            schema_version=row["schema_version"],
            source_system=row["source_system"],
            created_at_utc=row["created_at_utc"],
            updated_at_utc=row["updated_at_utc"],
        )
