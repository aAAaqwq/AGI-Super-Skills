"""Pure, side-effect-free report construction and rendering for v4."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo

from scanner.contracts import (
    ContractViolation,
    DedupStatus,
    PostCountContract,
    format_utc,
    parse_utc,
)


_LOS_ANGELES = ZoneInfo("America/Los_Angeles")


class ReportValidationError(ValueError):
    """Raised when a report would overstate or omit required evidence."""


def build_local_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Build a JSON-serializable local report from collected run evidence."""

    try:
        scanned_at = parse_utc(payload.get("scanned_at"))
    except (ContractViolation, TypeError) as exc:
        raise ReportValidationError("a real scanned_at timestamp is required") from exc

    counts = _counts(payload.get("post_counts"))
    top = [
        _opportunity(item, watch=False)
        for item in _sequence(payload.get("top_opportunities"), "top_opportunities")[:3]
    ]
    observations = [
        _opportunity(item, watch=True)
        for item in _sequence(payload.get("observations"), "observations")[:5]
    ]
    snapshot_path = payload.get("snapshot_path")
    if not isinstance(snapshot_path, str) or not snapshot_path.strip():
        raise ReportValidationError("snapshot_path is required")

    report = dict(payload)
    generated_at = payload.get("report_generated_at")
    if generated_at is not None:
        try:
            report["report_generated_at"] = format_utc(parse_utc(generated_at))
        except ContractViolation as exc:
            raise ReportValidationError("report_generated_at must be timezone-aware") from exc
    leaderboard_coverage = _coverage(
        payload.get("leaderboard_coverage"), "leaderboard_coverage"
    )
    smart_money = payload.get("smart_money")
    normalized_smart_money = (
        _smart_money(smart_money, leaderboard_coverage)
        if smart_money is not None
        else None
    )
    report.update({
        "status": "OPPORTUNITIES" if top else "WAIT",
        "window_hours": 24,
        "post_counts": counts,
        "author_coverage": _author_coverage(payload.get("author_coverage")),
        "leaderboard_coverage": leaderboard_coverage,
        "smart_money": normalized_smart_money,
        "top_opportunities": top,
        "observations": observations,
        "snapshot_path": snapshot_path,
    })
    report["risk_banner"] = _risk_banner(report)
    report["scanned_at"] = {
        "utc": format_utc(scanned_at),
        "america_los_angeles": _format_local(scanned_at),
    }
    return report


def render_local_markdown(report: Mapping[str, Any]) -> str:
    """Render the complete local, human-readable v4 report."""

    risks = _mapping(report.get("risk_banner"), "risk_banner")
    scanned = _mapping(report.get("scanned_at"), "scanned_at")
    counts = _mapping(report.get("post_counts"), "post_counts")
    authors = _mapping(report.get("author_coverage"), "author_coverage")
    leaderboard = _mapping(
        report.get("leaderboard_coverage"), "leaderboard_coverage"
    )
    profile_channel = report.get("profile_channel")
    smart_money = report.get("smart_money")
    capture_timing = report.get("capture_timing")
    run_timing = report.get("run_timing")
    lines = [
        str(risks.get("line", "")),
        "# Binance Square 合约投机雷达 v4",
        "",
        f"抓取时间 UTC：{scanned.get('utc')}｜America/Los_Angeles：{scanned.get('america_los_angeles')}",
        f"报告生成时间 UTC：{_display(report.get('report_generated_at'))}",
        (
            f"帖子口径：发现{counts.get('discovered')} / 窗口内{counts.get('total')} / "
            f"accepted {counts.get('accepted')} / 窗口排除{counts.get('window_excluded')} / "
            f"DQ隔离{counts.get('dq_quarantine')} / "
            f"新增{_display_count(counts.get('new'))} / 重复{_display_count(counts.get('duplicate'))}"
        ),
        "",
        "## 数据覆盖",
    ]
    if isinstance(capture_timing, Mapping):
        lines.insert(
            3,
            (
                "广场抓取："
                f"{_display(capture_timing.get('square_started_at_utc'))} → "
                f"{_display(capture_timing.get('square_completed_at_utc'))}｜"
                f"行情最新：{_display(capture_timing.get('market_latest_at_utc'))}"
            ),
        )
    if isinstance(run_timing, Mapping) and run_timing.get("scheduled_for_utc"):
        lines.insert(
            3,
            (
                "运行时槽："
                f"{_display(run_timing.get('scheduled_for_utc'))}｜"
                f"decision {_display(run_timing.get('decision_at_utc'))}｜"
                f"延迟 {_display(run_timing.get('decision_lag_seconds'))}s / "
                f"上限 {_display(run_timing.get('maximum_production_lag_seconds'))}s"
            ),
        )
    elif isinstance(run_timing, Mapping):
        lines.insert(
            3,
            f"回放 decision：{_display(run_timing.get('decision_at_utc'))}",
        )
    for key, title in (("tier_a", "Tier A"), ("tier_b", "Tier B")):
        tier = _mapping(authors.get(key), f"author_coverage.{key}")
        identities = tier.get("identity_sources") or []
        lines.append(
            f"- {title}：{tier.get('label')}｜身份来源：{', '.join(identities) if identities else '无'}"
        )
    leaderboard_line = (
        f"- 排行榜：{leaderboard.get('label')}｜{leaderboard.get('status', 'UNKNOWN')}"
    )
    seed_count = leaderboard.get("verified_seed_profiles")
    if isinstance(seed_count, int):
        leaderboard_line += (
            f"｜Profile种子 {seed_count}｜已渲染榜单行 "
            f"{leaderboard.get('rendered_rank_rows', 0)}"
        )
        if leaderboard.get("complete_top30") is False:
            leaderboard_line += "｜非TOP30"
    if leaderboard.get("evidence_captured_at_utc"):
        leaderboard_line += (
            f"｜证据时间 {leaderboard['evidence_captured_at_utc']}"
        )
    if leaderboard.get("reason"):
        leaderboard_line += f"：{leaderboard['reason']}"
    lines.extend([leaderboard_line, "", "## TOP 3"])
    if isinstance(smart_money, Mapping):
        ranking = _mapping(
            smart_money.get("ranking_coverage"),
            "smart_money.ranking_coverage",
        )
        details = _mapping(
            smart_money.get("profile_detail_coverage"),
            "smart_money.profile_detail_coverage",
        )
        identities = _mapping(
            smart_money.get("square_identity_mapping_coverage"),
            "smart_money.square_identity_mapping_coverage",
        )
        observed_window = _mapping(
            smart_money.get("leaderboard_observed_window"),
            "smart_money.leaderboard_observed_window",
        )
        smart_lines = [
            (
                "- Smart Money排行："
                f"{ranking.get('label')}｜PNL/ROI TOP30 "
                f"{ranking.get('rendered_rank_rows')}行｜语义 "
                f"{smart_money.get('observation_semantics')}（非原子快照）"
            ),
            (
                "- 榜单数据更新时间："
                f"{smart_money.get('leaderboard_data_updated_at_utc')}｜"
                "OBSERVED_WINDOW："
                f"{observed_window.get('started_at_utc')} → "
                f"{observed_window.get('completed_at_utc')}｜"
                f"证据封装时间：{smart_money.get('captured_at_utc')}"
            ),
            (
                "- 交易员详情："
                f"{details.get('label')}｜失败 {details.get('failed', 0)}｜"
                "topTraderId→Square身份映射："
                f"{identities.get('label')}｜Tier A eligible="
                f"{smart_money.get('tier_a_eligible')}"
            ),
        ]
        insertion = lines.index("## TOP 3") - 1
        lines[insertion:insertion] = smart_lines
    if isinstance(profile_channel, Mapping):
        profile_line = (
            f"- Profile主通道：{_display(profile_channel.get('status'))}｜"
            f"计划作者 {profile_channel.get('planned_authors', 0)}｜"
            f"完成 {profile_channel.get('complete_authors', 0)}｜"
            f"未尝试 {profile_channel.get('not_attempted_authors', 0)}"
        )
        lines.insert(lines.index("## TOP 3") - 1, profile_line)

    opportunities = report.get("top_opportunities") or []
    if not opportunities:
        lines.append("无合格机会 / 等待")
    for index, item in enumerate(opportunities, start=1):
        opportunity = _mapping(item, "top opportunity")
        source_label = str(opportunity.get("market_source") or "UNKNOWN").replace(
            "_", " "
        )
        lines.extend(
            [
                "",
                f"## TOP {index}｜{opportunity.get('symbol')} {opportunity.get('direction')}｜{source_label}",
                f"Entry：{_display_entry(opportunity.get('entry'))}",
                (
                    f"SL：{_display(opportunity.get('stop_loss'))}｜"
                    f"TP1：{_display(opportunity.get('tp1'))}｜"
                    f"TP2：{_display(opportunity.get('tp2'))}｜"
                    f"现价：{_display(opportunity.get('current_price'))}"
                ),
                f"参数来源：{_display(opportunity.get('parameter_source'))}",
                f"失效：{_display(opportunity.get('invalidation'))}｜分数：{_display(opportunity.get('score'))}",
                f"证据：{_join(opportunity.get('evidence'))}",
                f"行情抓取：{_display(opportunity.get('market_captured_at'))}",
                f"缺失行情字段：{_join(opportunity.get('missing_market_fields'))}",
                f"来源：{_display(opportunity.get('source_post_url'))}",
            ]
        )

    lines.extend(["", "## 观察（最多5个）"])
    observations = report.get("observations") or []
    if not observations:
        lines.append("无")
    for item in observations:
        watch = _mapping(item, "observation")
        lines.append(
            f"- {watch.get('symbol')} {watch.get('direction')}｜分数 {_display(watch.get('score'))}｜等待：{_display(watch.get('waiting_condition'))}"
        )

    tracking = report.get("tracking")
    if isinstance(tracking, Mapping):
        lines.extend(
            [
                "",
                "## 前向追踪",
                (
                    f"- 状态：{_display(tracking.get('status'))}｜"
                    f"计划信号：{_display(tracking.get('signal_count'))}｜"
                    f"评估：{_display(tracking.get('evaluation_status'))}"
                ),
            ]
        )

    lines.extend(["", "## 过滤与限制"])
    lines.append(f"- 过滤原因：{_format_filters(report.get('filtered'))}")
    limitations = report.get("limitations") or []
    if limitations:
        for limitation in limitations:
            lines.append(f"- 限制：{limitation}")
    else:
        lines.append("- 限制：无额外声明")
    if report.get("concentration_risk"):
        lines.append(f"- 集中风险：{report['concentration_risk']}")
    lines.extend([
        "",
        f"完整快照：{report.get('snapshot_path')}",
        f"行情证据：{_display(report.get('market_snapshot_path'))}",
    ])
    return "\n".join(lines)


def render_telegram(report: Mapping[str, Any]) -> str:
    """Render the compact Telegram body without sending it."""

    risks = _mapping(report.get("risk_banner"), "risk_banner")
    scanned = _mapping(report.get("scanned_at"), "scanned_at")
    counts = _mapping(report.get("post_counts"), "post_counts")
    authors = _mapping(report.get("author_coverage"), "author_coverage")
    tier_a = _mapping(authors.get("tier_a"), "author_coverage.tier_a")
    tier_b = _mapping(authors.get("tier_b"), "author_coverage.tier_b")
    leaderboard = _mapping(
        report.get("leaderboard_coverage"), "leaderboard_coverage"
    )
    lines = [
        str(risks.get("line", "")),
        "Binance Square 合约雷达 v4",
        f"抓取 UTC {scanned.get('utc')}｜LA {scanned.get('america_los_angeles')}",
        (
            f"发现{counts.get('discovered')}｜窗口内{counts.get('total')}｜"
            f"有效{counts.get('accepted')}｜窗口排除{counts.get('window_excluded')}｜"
            f"DQ隔离{counts.get('dq_quarantine')}｜"
            f"新增{_display_count(counts.get('new'))}｜重复{_display_count(counts.get('duplicate'))}"
        ),
        f"作者 A {tier_a.get('label')}｜B {tier_b.get('label')}",
        (
            f"排行榜 {leaderboard.get('label')} {leaderboard.get('status', 'UNKNOWN')}"
            + (
                f"｜种子{leaderboard.get('verified_seed_profiles')}｜榜单行"
                f"{leaderboard.get('rendered_rank_rows', 0)}｜非TOP30"
                if isinstance(leaderboard.get("verified_seed_profiles"), int)
                else ""
            )
        ),
    ]
    smart_money = report.get("smart_money")
    if isinstance(smart_money, Mapping):
        ranking = _mapping(
            smart_money.get("ranking_coverage"),
            "smart_money.ranking_coverage",
        )
        details = _mapping(
            smart_money.get("profile_detail_coverage"),
            "smart_money.profile_detail_coverage",
        )
        identities = _mapping(
            smart_money.get("square_identity_mapping_coverage"),
            "smart_money.square_identity_mapping_coverage",
        )
        lines.append(
            "Smart Money "
            f"{ranking.get('label')} / {ranking.get('rendered_rank_rows')}行｜"
            f"详情{details.get('label')}｜身份{identities.get('label')}｜"
            f"Tier A {smart_money.get('tier_a_eligible')}"
        )

    opportunities = report.get("top_opportunities") or []
    if not opportunities:
        lines.append("结论：无合格机会 / 等待")
    else:
        lines.append("TOP：")
        for index, item in enumerate(opportunities, start=1):
            opportunity = _mapping(item, "top opportunity")
            source = str(opportunity.get("market_source") or "UNKNOWN").replace(
                "_", " "
            )
            lines.extend(
                [
                    f"{index}. {opportunity.get('symbol')} {opportunity.get('direction')} [{source}]",
                    (
                        f"Entry {_display_entry(opportunity.get('entry'))}｜"
                        f"SL {_display(opportunity.get('stop_loss'))}｜"
                        f"TP1 {_display(opportunity.get('tp1'))}｜"
                        f"TP2 {_display(opportunity.get('tp2'))}"
                    ),
                    (
                        f"现价 {_display(opportunity.get('current_price'))}｜"
                        f"分数 {_display(opportunity.get('score'))}｜"
                        f"参数 {_display(opportunity.get('parameter_source'))}｜"
                        f"失效 {_display(opportunity.get('invalidation'))}"
                    ),
                    (
                        f"行情 {opportunity.get('market_captured_at')}｜"
                        f"来源 {opportunity.get('source_post_url')}"
                    ),
                ]
            )

    observations = report.get("observations") or []
    if observations:
        lines.append("观察：")
        for item in observations:
            watch = _mapping(item, "observation")
            lines.append(
                f"- {watch.get('symbol')} {watch.get('direction')}：{_display(watch.get('waiting_condition'))}"
            )
    lines.extend(
        [
            f"过滤：{_format_filters(report.get('filtered'))}",
            f"快照：{report.get('snapshot_path')}",
        ]
    )
    return "\n".join(lines)


def _format_local(value: datetime) -> str:
    local = value.astimezone(_LOS_ANGELES)
    timespec = "microseconds" if local.microsecond else "seconds"
    return local.isoformat(timespec=timespec)


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ReportValidationError(f"{name} must be a mapping")
    return value


def _sequence(value: Any, name: str) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        raise ReportValidationError(f"{name} must be a sequence")
    return list(value)


def _counts(value: Any) -> dict[str, Any]:
    source = _mapping(value, "post_counts")
    values: dict[str, int] = {}
    for field in ("total", "accepted", "quarantine"):
        count = source.get(field)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ReportValidationError(f"post_counts.{field} must be non-negative")
        values[field] = count
    discovered = source.get(
        "discovered", values["accepted"] + values["quarantine"]
    )
    if not isinstance(discovered, int) or isinstance(discovered, bool) or discovered < 0:
        raise ReportValidationError("post_counts.discovered must be non-negative")
    dq_quarantine = source.get("dq_quarantine", values["quarantine"])
    window_excluded = source.get("window_excluded", 0)
    for field, count in (
        ("dq_quarantine", dq_quarantine),
        ("window_excluded", window_excluded),
    ):
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ReportValidationError(f"post_counts.{field} must be non-negative")
    unique_accepted = source.get("unique_accepted", values["accepted"])
    if (
        not isinstance(unique_accepted, int)
        or isinstance(unique_accepted, bool)
        or unique_accepted < 0
    ):
        raise ReportValidationError(
            "post_counts.unique_accepted must be non-negative"
        )
    raw_dedup_status = source.get("dedup_status", DedupStatus.COMPUTED.value)
    try:
        dedup_status = DedupStatus(raw_dedup_status)
    except (TypeError, ValueError) as exc:
        raise ReportValidationError("post_counts.dedup_status is invalid")
    try:
        contract = PostCountContract(
            discovered=discovered,
            total=values["total"],
            accepted=values["accepted"],
            quarantine=values["quarantine"],
            dq_quarantine=dq_quarantine,
            window_excluded=window_excluded,
            unique_accepted=unique_accepted,
            new=source.get("new"),
            duplicate=source.get("duplicate"),
            dedup_status=dedup_status,
        )
    except ContractViolation as exc:
        raise ReportValidationError(f"post_counts {exc}") from exc
    return contract.as_dict()


def _display_count(value: Any) -> str:
    return "未计算" if value is None else str(value)


def _read(value: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(value, Mapping) and name in value:
            return value[name]
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return format_utc(value)
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_json_value(item) for item in value]
    return value


def _opportunity(value: Any, *, watch: bool) -> dict[str, Any]:
    symbol = _read(value, "symbol")
    direction = _read(value, "direction", "side")
    if not isinstance(symbol, str) or not symbol.strip():
        raise ReportValidationError("opportunity symbol is required")
    if not isinstance(direction, str) or not direction.strip():
        raise ReportValidationError("opportunity direction is required")

    captured_at = _read(value, "market_captured_at", "captured_at")
    if captured_at is not None:
        try:
            captured_at = format_utc(captured_at)
        except ContractViolation as exc:
            raise ReportValidationError("market_captured_at must be timezone-aware") from exc

    candidate = _read(value, "candidate")
    parameter_source = _read(value, "parameter_source")
    if parameter_source is None and candidate is not None:
        parameter_source = _read(candidate, "parameter_source")
    result = {
        "symbol": symbol.strip().upper(),
        "direction": direction.strip().upper(),
        "entry": _json_value(_read(value, "entry", "entry_zone")),
        "stop_loss": _json_value(_read(value, "stop_loss", "sl")),
        "tp1": _json_value(_read(value, "tp1")),
        "tp2": _json_value(_read(value, "tp2")),
        "current_price": _json_value(_read(value, "current_price", "last_price")),
        "invalidation": _read(value, "invalidation", "invalidation_condition"),
        "score": _json_value(_read(value, "score", "total_score")),
        "evidence": _json_value(_read(value, "evidence", default=())),
        "source_post_url": _read(value, "source_post_url", "post_url"),
        "market_captured_at": captured_at,
        "market_source": _json_value(_read(value, "market_source", "source")),
        "parameter_source": _json_value(parameter_source),
        "missing_market_fields": _json_value(
            _read(value, "missing_market_fields", "missing_fields", default=())
        ),
    }
    if watch:
        result["waiting_condition"] = _read(
            value, "waiting_condition", "wait_for", "wait_condition"
        )
    else:
        if not isinstance(result["source_post_url"], str) or not result[
            "source_post_url"
        ].strip():
            raise ReportValidationError("source_post_url is required for TOP opportunities")
        if result["market_captured_at"] is None:
            raise ReportValidationError(
                "market_captured_at is required for TOP opportunities"
            )
    return result


def _coverage(value: Any, name: str) -> dict[str, Any]:
    source = _mapping(value, name)
    covered = source.get("covered")
    expected = source.get("expected")
    if (
        not isinstance(covered, int)
        or isinstance(covered, bool)
        or covered < 0
        or not isinstance(expected, int)
        or isinstance(expected, bool)
        or expected < 0
        or covered > expected
    ):
        raise ReportValidationError(f"{name} has invalid covered/expected counts")
    if expected:
        label = f"{covered}/{expected} ({covered / expected:.1%})"
    else:
        label = "0/0 (coverage unavailable)"
    result = dict(source)
    if name == "leaderboard_coverage":
        status = str(source.get("status", "")).upper()
        complete_top30 = source.get("complete_top30")
        if status == "PARTIAL_SEED_DISCOVERY":
            if (
                covered != 0
                or complete_top30 is not False
                or source.get("rendered_rank_rows") != 0
                or source.get("seed_scope") != "PROFILE_BACKED"
            ):
                raise ReportValidationError(
                    "partial seed discovery must declare zero full coverage, "
                    "zero rendered rows, non-TOP30, and PROFILE_BACKED scope"
                )
        if complete_top30 is False and covered != 0:
            raise ReportValidationError(
                "incomplete TOP30 evidence cannot claim leaderboard coverage"
            )
        if status == "COMPLETE" and (
            complete_top30 is not True or covered != expected
        ):
            raise ReportValidationError(
                "complete leaderboard status requires complete expected coverage"
            )
        for field in ("verified_seed_profiles", "rendered_rank_rows"):
            count = source.get(field)
            if count is not None and (
                not isinstance(count, int)
                or isinstance(count, bool)
                or count < 0
            ):
                raise ReportValidationError(
                    f"leaderboard_coverage.{field} must be non-negative"
                )
    result.update({"covered": covered, "expected": expected, "label": label})
    return result


def _smart_money(
    value: Any,
    leaderboard_coverage: Mapping[str, Any],
) -> dict[str, Any]:
    source = _mapping(value, "smart_money")
    if source.get("observation_semantics") != "OBSERVED_WINDOW":
        raise ReportValidationError(
            "smart_money.observation_semantics must be OBSERVED_WINDOW"
        )
    normalized = dict(source)
    for field in ("captured_at_utc", "leaderboard_data_updated_at_utc"):
        try:
            normalized[field] = format_utc(parse_utc(source.get(field)))
        except (ContractViolation, TypeError) as exc:
            raise ReportValidationError(
                f"smart_money.{field} must be timezone-aware"
            ) from exc
    window = _mapping(
        source.get("leaderboard_observed_window"),
        "smart_money.leaderboard_observed_window",
    )
    try:
        window_start = parse_utc(window.get("started_at_utc"))
        window_end = parse_utc(window.get("completed_at_utc"))
    except (ContractViolation, TypeError) as exc:
        raise ReportValidationError(
            "Smart Money observed window timestamps must be timezone-aware"
        ) from exc
    duration = window.get("duration_seconds")
    if (
        window_end < window_start
        or not isinstance(duration, (int, float))
        or isinstance(duration, bool)
        or duration < 0
        or abs(duration - (window_end - window_start).total_seconds()) > 0.001
    ):
        raise ReportValidationError("Smart Money observed window is invalid")
    normalized["leaderboard_observed_window"] = {
        "started_at_utc": format_utc(window_start),
        "completed_at_utc": format_utc(window_end),
        "duration_seconds": duration,
    }
    ranking = _coverage(
        source.get("ranking_coverage"), "smart_money.ranking_coverage"
    )
    if ranking["expected"] != 2:
        raise ReportValidationError("Smart Money ranking expected coverage must be 2")
    ranking_types = ranking.get("ranking_types")
    if (
        not isinstance(ranking_types, (list, tuple))
        or len(ranking_types) != ranking["covered"]
        or len(set(ranking_types)) != len(ranking_types)
        or any(value not in {"PNL", "ROI"} for value in ranking_types)
    ):
        raise ReportValidationError("Smart Money ranking types are invalid")
    rows = ranking.get("rendered_rank_rows")
    if rows != ranking["covered"] * 30:
        raise ReportValidationError(
            "Smart Money rendered rank rows must equal covered rankings times 30"
        )
    if (
        leaderboard_coverage.get("covered") != ranking["covered"]
        or leaderboard_coverage.get("expected") != ranking["expected"]
        or leaderboard_coverage.get("rendered_rank_rows") != rows
    ):
        raise ReportValidationError(
            "Smart Money ranking coverage must match leaderboard coverage"
        )

    details = _coverage(
        source.get("profile_detail_coverage"),
        "smart_money.profile_detail_coverage",
    )
    failed = details.get("failed")
    if (
        not isinstance(failed, int)
        or isinstance(failed, bool)
        or failed < 0
        or details["covered"] + failed > details["expected"]
    ):
        raise ReportValidationError("Smart Money profile failure count is invalid")
    identities = _coverage(
        source.get("square_identity_mapping_coverage"),
        "smart_money.square_identity_mapping_coverage",
    )
    unique_count = source.get("unique_top_trader_count")
    if (
        not isinstance(unique_count, int)
        or isinstance(unique_count, bool)
        or unique_count < 0
        or unique_count != details["expected"]
        or unique_count != identities["expected"]
    ):
        raise ReportValidationError(
            "Smart Money unique trader/detail/identity counts must reconcile"
        )
    tier_a = source.get("tier_a_eligible")
    if (
        not isinstance(tier_a, int)
        or isinstance(tier_a, bool)
        or tier_a < 0
        or tier_a > identities["covered"]
    ):
        raise ReportValidationError("Smart Money Tier A eligible count is invalid")
    if identities.get("verification_method") != "EXPLICIT_SOURCE_EVIDENCE_ONLY":
        raise ReportValidationError(
            "Smart Money identity mapping must require explicit source evidence"
        )
    evidence_path = source.get("evidence_path")
    if not isinstance(evidence_path, str) or not evidence_path.strip():
        raise ReportValidationError("Smart Money evidence_path is required")
    normalized["ranking_coverage"] = ranking
    normalized["profile_detail_coverage"] = details
    normalized["square_identity_mapping_coverage"] = identities
    return normalized


def _author_coverage(value: Any) -> dict[str, dict[str, Any]]:
    source = _mapping(value, "author_coverage")
    result: dict[str, dict[str, Any]] = {}
    for tier in ("tier_a", "tier_b"):
        coverage = _coverage(source.get(tier), f"author_coverage.{tier}")
        identities = coverage.get("identity_sources")
        if not isinstance(identities, (list, tuple)) or not all(
            isinstance(item, str) for item in identities
        ):
            raise ReportValidationError(
                f"author_coverage.{tier}.identity_sources must be strings"
            )
        coverage["identity_sources"] = list(identities)
        result[tier] = coverage
    return result


def _risk_banner(report: Mapping[str, Any]) -> dict[str, Any]:
    labels: list[str] = []
    if any(
        item.get("market_source") == "SPOT_PROXY"
        for item in report.get("top_opportunities", [])
    ):
        labels.append("SPOT PROXY")
    if report.get("concentration_risk"):
        labels.append("集中风险")
    leaderboard = report.get("leaderboard_coverage", {})
    leaderboard_status = str(leaderboard.get("status", "")).upper()
    if leaderboard_status == "BLOCKED":
        labels.append("排行榜阻塞")
    elif leaderboard_status not in {"COMPLETE", "PASS", "OK"}:
        labels.append("排行榜部分覆盖")
    smart_money = report.get("smart_money")
    if isinstance(smart_money, Mapping):
        details = smart_money.get("profile_detail_coverage", {})
        identities = smart_money.get("square_identity_mapping_coverage", {})
        if isinstance(details, Mapping) and details.get("covered") != details.get(
            "expected"
        ):
            labels.append("交易员详情部分覆盖")
        if isinstance(identities, Mapping) and identities.get(
            "covered"
        ) != identities.get("expected"):
            labels.append("Square身份未解析")
    line = "⚠️ " + " · ".join(labels) if labels else "✅ 无已知降级风险"
    return {"labels": labels, "line": line}


def _display(value: Any) -> str:
    return "UNKNOWN" if value is None or value == "" else str(value)


def _display_entry(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "–".join(_display(item) for item in value)
    return _display(value)


def _join(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(_display(item) for item in value) if value else "无"
    return _display(value)


def _format_filters(value: Any) -> str:
    if isinstance(value, Mapping):
        return ", ".join(f"{reason} × {count}" for reason, count in value.items()) or "无"
    return _join(value)
