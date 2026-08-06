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
_REPORT_SOURCES = (
    "FEED",
    "BINANCE_OFFICIAL_NEWS",
    "SMART_MONEY",
    "PROFILE",
    "MARKET_CATALOG",
)
_SOURCE_STATUSES = frozenset({"COMPLETE", "PARTIAL", "FAILED", "NOT_ATTEMPTED"})
_SOURCE_PROVENANCE = frozenset({"LIVE_CAPTURE", "FIXTURE_REPLAY", "UNKNOWN"})
_PROFILE_COUNT_FIELDS = (
    "complete_authors",
    "empty_authors",
    "partial_authors",
    "failed_authors",
    "not_attempted_authors",
)
_PROFILE_STATUS_COUNTS = {
    "COMPLETE": "complete_authors",
    "EMPTY": "empty_authors",
    "PARTIAL": "partial_authors",
    "FAILED": "failed_authors",
    "NOT_ATTEMPTED": "not_attempted_authors",
}
_TELEGRAM_FILTER_LABELS = {
    "RR below 2.0": "风险收益不足",
    "AMBIGUOUS_OR_MISSING_DIRECTION": "方向不明确",
    "AMBIGUOUS_OR_MISSING_SYMBOL": "缺少有效合约",
    "DIRECTIONAL_STRUCTURE_NOT_CONFIRMED": "多周期结构未确认",
    "STRUCTURAL_TARGETS_UNAVAILABLE": "缺少结构化目标位",
    "NO_ACTIVE_EXACT_USDT_PERPETUAL": "无对应 USDT 永续合约",
    "CURRENT_PRICE_TOO_EXTENDED": "当前价格偏离入场区",
    "EXECUTION_COSTS_NOT_CONFIGURED": "交易成本未配置",
}
_TELEGRAM_RISK_LABELS = {
    "排行榜阻塞": "排行榜数据不完整",
    "排行榜部分覆盖": "排行榜仅部分覆盖",
    "Square身份未解析": "交易员身份映射不完整",
    "SPOT PROXY": "部分行情使用现货代理",
    "集中风险": "候选信号存在集中风险",
}
_TELEGRAM_DIRECTIONS = {
    "LONG": "做多",
    "SHORT": "做空",
}


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
    if "profile_channel" in payload:
        report["profile_channel"] = _profile_channel(payload.get("profile_channel"))
    generated_at = payload.get("report_generated_at")
    capture_timing_value = payload.get("capture_timing")
    if generated_at is None and isinstance(capture_timing_value, Mapping):
        generated_at = _first_time(
            capture_timing_value,
            "report_generated_at_utc",
            "report",
        )
    if generated_at is not None:
        try:
            report["report_generated_at"] = format_utc(parse_utc(generated_at))
        except ContractViolation as exc:
            raise ReportValidationError("report_generated_at must be timezone-aware") from exc
    else:
        report["report_generated_at"] = None
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
    report["source_coverage"] = _source_coverage(
        report,
        normalized_smart_money,
    )
    if report["report_generated_at"] is not None:
        generated = parse_utc(report["report_generated_at"])
        captured_times = [scanned_at]
        captured_times.extend(
            parse_utc(source["source_capture_time_utc"])
            for source in report["source_coverage"].values()
            if source["source_capture_time_utc"] is not None
        )
        for opportunity in top:
            captured_times.extend(
                parse_utc(opportunity[field])
                for field in ("evidence_captured_at", "market_captured_at")
            )
        if max(captured_times) > generated:
            raise ReportValidationError(
                "report_generated_at cannot precede source capture time"
            )
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
    source_coverage = _mapping(report.get("source_coverage"), "source_coverage")
    for source_name in _REPORT_SOURCES:
        source = _mapping(
            source_coverage.get(source_name),
            f"source_coverage.{source_name}",
        )
        line = (
            f"- {source_name}：{source.get('status')}｜"
            f"{source.get('provenance')}｜source capture "
            f"{_display(source.get('source_capture_time_utc'))}"
        )
        if source.get("capture_started_at_utc"):
            line += f"｜start {source['capture_started_at_utc']}"
        if source.get("evidence_path"):
            line += f"｜evidence {source['evidence_path']}"
        if source.get("coverage_status"):
            line += (
                f"｜coverage {source['coverage_status']}｜"
                f"termination {_display(source.get('termination_reason'))}"
            )
        if source.get("reason"):
            line += f"｜{source['reason']}"
        lines.append(line)
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
        profile_coverage = profile_channel.get("coverage")
        profile_coverage_label = (
            profile_coverage.get("label")
            if isinstance(profile_coverage, Mapping)
            else "coverage unavailable"
        )
        profile_line = (
            f"- Profile主通道：{_display(profile_channel.get('status'))}｜"
            f"计划作者 {profile_channel.get('planned_authors', 0)}｜"
            f"完成 {profile_channel.get('complete_authors', 0)}｜"
            f"未尝试 {profile_channel.get('not_attempted_authors', 0)}｜"
            f"coverage {profile_coverage_label}"
        )
        profile_lines = [profile_line]
        cohort_specs = (
            ("smart_money_profiles", "Smart Money Profiles", True),
            ("seed_profiles", "Seed Profiles", False),
        )
        for field, label, show_mapping in cohort_specs:
            cohort = profile_channel.get(field)
            if not isinstance(cohort, Mapping):
                continue
            coverage = cohort.get("coverage")
            coverage_label = (
                coverage.get("label")
                if isinstance(coverage, Mapping)
                else "coverage unavailable"
            )
            cohort_line = (
                f"- {label}：状态 {_display(cohort.get('status'))}｜"
                f"coverage {coverage_label}｜"
                f"计划 {cohort.get('planned_authors', 0)}｜"
                f"完成 {cohort.get('complete_authors', 0)}｜"
                f"空 {cohort.get('empty_authors', 0)}｜"
                f"部分 {cohort.get('partial_authors', 0)}｜"
                f"失败 {cohort.get('failed_authors', 0)}｜"
                f"未尝试 {cohort.get('not_attempted_authors', 0)}｜"
                f"来源记录 {cohort.get('source_records', 0)}"
            )
            mapping = cohort.get("square_identity_mapping_coverage")
            if show_mapping and isinstance(mapping, Mapping):
                mapping_label = mapping.get("label")
                if not isinstance(mapping_label, str) or not mapping_label.strip():
                    covered = mapping.get("covered")
                    expected = mapping.get("expected")
                    if (
                        isinstance(covered, int)
                        and not isinstance(covered, bool)
                        and isinstance(expected, int)
                        and not isinstance(expected, bool)
                    ):
                        mapping_label = f"{covered}/{expected}"
                if isinstance(mapping_label, str) and mapping_label.strip():
                    cohort_line += f"｜mapping {mapping_label.strip()}"
            profile_lines.append(cohort_line)
        insertion = lines.index("## TOP 3") - 1
        lines[insertion:insertion] = profile_lines

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
                (
                    f"名义RR：{_display(opportunity.get('nominal_rr'))}｜"
                    f"成本模型：{_display(opportunity.get('cost_model_status'))}"
                ),
                f"失效：{_display(opportunity.get('invalidation'))}｜分数：{_display(opportunity.get('score'))}",
                f"证据：{_join(opportunity.get('evidence'))}",
                f"证据抓取：{_display(opportunity.get('evidence_captured_at'))}",
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
    opportunities = report.get("top_opportunities") or []
    lines = ["📡 币安合约雷达"]
    if opportunities:
        lines.extend(
            [
                f"🟢 结论：发现 {len(opportunities)} 个可执行信号",
                _telegram_counts(counts),
            ]
        )
        for index, item in enumerate(opportunities[:3], start=1):
            opportunity = _mapping(item, "top opportunity")
            direction = _TELEGRAM_DIRECTIONS.get(
                str(opportunity.get("direction")), "方向待确认"
            )
            lines.extend(
                [
                    (
                        f"🟢 {index}. {opportunity.get('symbol')} {direction}｜"
                        f"评分 {_display(opportunity.get('score'))}"
                    ),
                    (
                        f"   入场 {_display_entry(opportunity.get('entry'))}｜"
                        f"止损 {_display(opportunity.get('stop_loss'))}｜"
                        f"目标 {_display(opportunity.get('tp1'))} / "
                        f"{_display(opportunity.get('tp2'))}"
                    ),
                    (
                        f"   现价 {_display(opportunity.get('current_price'))}｜"
                        f"RR {_display(opportunity.get('nominal_rr'))}｜"
                        f"失效 {_display(opportunity.get('invalidation'))}"
                    ),
                    f"   来源 {opportunity.get('source_post_url')}",
                ]
            )
    else:
        lines.extend([
            "🟡 结论：本轮无可执行信号，继续等待",
            _telegram_counts(counts),
            f"🧹 主要过滤：{_telegram_filters(report.get('filtered'))}",
        ])
    risk_text = _telegram_risks(risks.get("labels"))
    if risk_text:
        lines.append(f"⚠️ 数据提示：{risk_text}")
    lines.append(
        f"🕒 数据时间：{_telegram_time(scanned.get('america_los_angeles'))}"
    )
    return "\n".join(lines)


def _telegram_counts(counts: Mapping[str, Any]) -> str:
    return (
        f"📊 扫描 {counts.get('discovered')}｜"
        f"有效 {counts.get('accepted')}｜"
        f"新增 {_display_count(counts.get('new'))}"
    )


def _telegram_time(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return "未知"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.astimezone(_LOS_ANGELES).strftime("%Y-%m-%d %H:%M %Z").strip()


def _telegram_filters(value: Any, *, limit: int = 3) -> str:
    if not isinstance(value, Mapping) or not value:
        return "无"
    grouped: dict[str, int] = {}
    for reason, count in value.items():
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            continue
        label = _TELEGRAM_FILTER_LABELS.get(str(reason), "其他规则")
        grouped[label] = grouped.get(label, 0) + count
    shown = sorted(grouped.items(), key=lambda item: (-item[1], item[0]))[:limit]
    parts = [f"{label} × {count}" for label, count in shown]
    return "｜".join(parts) if parts else "无"


def _telegram_risks(value: Any) -> str:
    if not isinstance(value, (list, tuple)):
        return ""
    labels = [
        _TELEGRAM_RISK_LABELS.get(str(label), str(label))
        for label in value
        if str(label).strip()
    ]
    return "；".join(labels)


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
    except (TypeError, ValueError):
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
    source_observations = source.get("source_observations", discovered)
    deduplicated_candidates = source.get(
        "deduplicated_candidates", discovered
    )
    same_run_duplicates = source.get("same_run_duplicates", 0)
    for field, count in (
        ("source_observations", source_observations),
        ("deduplicated_candidates", deduplicated_candidates),
        ("same_run_duplicates", same_run_duplicates),
    ):
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ReportValidationError(f"post_counts.{field} must be non-negative")
    if deduplicated_candidates != discovered:
        raise ReportValidationError(
            "post_counts.deduplicated_candidates must equal discovered"
        )
    if source_observations != deduplicated_candidates + same_run_duplicates:
        raise ReportValidationError(
            "post_counts source observations do not reconcile after deduplication"
        )
    return {
        **contract.as_dict(),
        "source_observations": source_observations,
        "deduplicated_candidates": deduplicated_candidates,
        "same_run_duplicates": same_run_duplicates,
    }


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

    captured_at = _read(value, "market_captured_at")
    if captured_at is not None:
        try:
            captured_at = format_utc(captured_at)
        except ContractViolation as exc:
            raise ReportValidationError("market_captured_at must be timezone-aware") from exc
    evidence_captured_at = _read(
        value,
        "evidence_captured_at",
        "source_detail_captured_at",
    )
    if evidence_captured_at is not None:
        try:
            evidence_captured_at = format_utc(evidence_captured_at)
        except ContractViolation as exc:
            raise ReportValidationError(
                "evidence_captured_at must be timezone-aware"
            ) from exc

    candidate = _read(value, "candidate")
    parameter_source = _read(value, "parameter_source")
    if parameter_source is None and candidate is not None:
        parameter_source = _read(candidate, "parameter_source")
    nominal_rr = _read(value, "nominal_rr")
    cost_model_status = _read(value, "cost_model_status")
    if not isinstance(value, Mapping) and candidate is not None:
        if nominal_rr is None:
            nominal_rr = _calculate_nominal_rr(value, direction)
        if cost_model_status is None:
            cost_model_status = "NOT_APPLIED"
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
        "nominal_rr": _json_value(nominal_rr),
        "cost_model_status": _json_value(cost_model_status),
        "evidence_captured_at": evidence_captured_at,
        "missing_market_fields": _json_value(
            _read(value, "missing_market_fields", "missing_fields", default=())
        ),
    }
    if watch:
        result["waiting_condition"] = _read(
            value, "waiting_condition", "wait_for", "wait_condition"
        )
    else:
        required_values = {
            "entry": result["entry"],
            "stop_loss": result["stop_loss"],
            "tp1": result["tp1"],
            "tp2": result["tp2"],
            "current_price": result["current_price"],
            "invalidation": result["invalidation"],
            "parameter_source": result["parameter_source"],
            "nominal_rr": result["nominal_rr"],
            "cost_model_status": result["cost_model_status"],
            "evidence_captured_at": result["evidence_captured_at"],
        }
        for field, field_value in required_values.items():
            if field_value is None or field_value == "" or field_value == []:
                raise ReportValidationError(
                    f"{field} is required for TOP opportunities"
                )
        _validate_top_price("entry", result["entry"])
        for field in ("stop_loss", "tp1", "tp2", "current_price"):
            _validate_top_price(field, result[field])
        _validate_positive_decimal("nominal_rr", result["nominal_rr"])
        if not isinstance(result["invalidation"], str) or not result[
            "invalidation"
        ].strip():
            raise ReportValidationError(
                "invalidation is required for TOP opportunities"
            )
        if not isinstance(result["parameter_source"], str) or not result[
            "parameter_source"
        ].strip():
            raise ReportValidationError(
                "parameter_source is required for TOP opportunities"
            )
        if not isinstance(result["cost_model_status"], str) or not result[
            "cost_model_status"
        ].strip():
            raise ReportValidationError(
                "cost_model_status is required for TOP opportunities"
            )
        if result["cost_model_status"].strip().upper() != "APPLIED":
            raise ReportValidationError(
                "cost_model_status must be APPLIED for TOP opportunities"
            )
        evidence = result["evidence"]
        if (
            not isinstance(evidence, list)
            or not evidence
            or not all(isinstance(item, str) and item.strip() for item in evidence)
        ):
            raise ReportValidationError(
                "evidence is required for TOP opportunities"
            )
        if not isinstance(result["source_post_url"], str) or not result[
            "source_post_url"
        ].strip():
            raise ReportValidationError("source_post_url is required for TOP opportunities")
        if result["market_captured_at"] is None:
            raise ReportValidationError(
                "market_captured_at is required for TOP opportunities"
            )
    return result


def _validate_positive_decimal(field: str, value: Any) -> Decimal:
    try:
        number = Decimal(str(value))
    except Exception as exc:
        raise ReportValidationError(f"{field} must be numeric") from exc
    if not number.is_finite() or number <= 0:
        raise ReportValidationError(f"{field} must be positive and finite")
    return number


def _validate_top_price(field: str, value: Any) -> None:
    values = value if isinstance(value, list) else [value]
    if not values or len(values) > 2:
        raise ReportValidationError(f"{field} must contain one or two prices")
    for item in values:
        _validate_positive_decimal(field, item)


def _calculate_nominal_rr(value: Any, direction: str) -> str | None:
    entry = _json_value(_read(value, "entry", "entry_zone"))
    stop = _json_value(_read(value, "stop_loss", "sl"))
    target = _json_value(_read(value, "tp2"))
    try:
        entry_values = entry if isinstance(entry, list) else [entry]
        if not entry_values or any(item is None for item in entry_values):
            return None
        midpoint = sum(Decimal(str(item)) for item in entry_values) / len(entry_values)
        stop_value = Decimal(str(stop))
        target_value = Decimal(str(target))
        if direction.strip().upper() == "LONG":
            risk = midpoint - stop_value
            reward = target_value - midpoint
        else:
            risk = stop_value - midpoint
            reward = midpoint - target_value
        if risk <= 0 or reward <= 0:
            return None
        return format(reward / risk, "f")
    except Exception:
        return None


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


def _profile_channel(value: Any) -> dict[str, Any]:
    source = _mapping(value, "profile_channel")
    normalized = dict(source)
    denominators_value = source.get("cohort_denominators")
    if denominators_value is None:
        raise ReportValidationError(
            "profile_channel.cohort_denominators is required"
        )

    denominators = _mapping(
        denominators_value,
        "profile_channel.cohort_denominators",
    )
    required_cohorts = {"smart_money_profiles", "seed_profiles"}
    if set(denominators) != required_cohorts:
        raise ReportValidationError(
            "profile_channel.cohort_denominators must declare both profile cohorts"
        )
    aggregate_counts = {field: 0 for field in _PROFILE_COUNT_FIELDS}
    aggregate_denominator = 0
    for cohort_name, denominator in denominators.items():
        path = f"profile_channel.{cohort_name}"
        if not isinstance(denominator, int) or isinstance(denominator, bool) or denominator < 0:
            raise ReportValidationError(f"{path} denominator must be non-negative")
        cohort = _mapping(source.get(cohort_name), path)
        normalized_cohort = dict(cohort)
        planned = cohort.get("planned_authors")
        if planned != denominator:
            raise ReportValidationError(f"{path}.planned_authors must equal denominator")
        counts: dict[str, int] = {}
        for field in _PROFILE_COUNT_FIELDS:
            count = cohort.get(field)
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise ReportValidationError(f"{path}.{field} must be non-negative")
            counts[field] = count
        if sum(counts.values()) != denominator:
            raise ReportValidationError(
                f"{path} terminal status counts must sum to denominator"
            )
        aggregate_denominator += denominator
        for field, count in counts.items():
            aggregate_counts[field] += count
        outcomes_value = cohort.get("outcomes")
        if outcomes_value is None and counts["not_attempted_authors"] != denominator:
            raise ReportValidationError(
                f"{path}.outcomes is required for attempted authors"
            )
        if outcomes_value is not None:
            outcomes = _sequence(outcomes_value, f"{path}.outcomes")
            if len(outcomes) != denominator:
                raise ReportValidationError(
                    f"{path}.outcomes must contain {denominator} rows"
                )
            outcome_counts = {status: 0 for status in _PROFILE_STATUS_COUNTS}
            for index, outcome_value in enumerate(outcomes):
                outcome = _mapping(outcome_value, f"{path}.outcomes[{index}]")
                status = str(outcome.get("status") or "").upper()
                if status not in outcome_counts:
                    raise ReportValidationError(
                        f"{path}.outcomes[{index}].status is invalid"
                    )
                outcome_counts[status] += 1
            if any(
                outcome_counts[status] != counts[field]
                for status, field in _PROFILE_STATUS_COUNTS.items()
            ):
                raise ReportValidationError(
                    f"{path} outcomes do not match summary counts"
                )
            identities: list[str] = []
            for index, outcome_value in enumerate(outcomes):
                outcome = _mapping(outcome_value, f"{path}.outcomes[{index}]")
                identity = next(
                    (
                        outcome.get(field)
                        for field in (
                            "top_trader_id",
                            "author_id",
                            "planned_author_id",
                        )
                        if isinstance(outcome.get(field), str)
                        and str(outcome.get(field)).strip()
                    ),
                    None,
                )
                if identity is None:
                    raise ReportValidationError(
                        f"{path}.outcomes[{index}] has no stable author identity"
                    )
                identities.append(str(identity).strip())
            if len(set(identities)) != len(identities):
                raise ReportValidationError(
                    f"{path} outcome identities must be unique"
                )
        completed = counts["complete_authors"] + counts["empty_authors"]
        status = str(cohort.get("status") or "NOT_ATTEMPTED").upper()
        if denominator == 0:
            allowed_statuses = {"EMPTY", "NOT_ATTEMPTED"}
        elif counts["not_attempted_authors"] == denominator:
            allowed_statuses = {"NOT_ATTEMPTED"}
        elif counts["failed_authors"] == denominator:
            allowed_statuses = {"FAILED"}
        elif completed == denominator:
            allowed_statuses = {"COMPLETE", "EMPTY"}
        else:
            allowed_statuses = {"PARTIAL"}
        if status not in allowed_statuses:
            raise ReportValidationError(
                f"{path}.status is inconsistent with terminal status counts"
            )
        normalized_cohort["status"] = status
        normalized_cohort["coverage"] = _coverage(
            {"covered": completed, "expected": denominator},
            f"{path}.coverage",
        )
        normalized[cohort_name] = normalized_cohort
    supplied_aggregate = {
        "planned_authors": source.get("planned_authors"),
        **{field: source.get(field) for field in _PROFILE_COUNT_FIELDS},
    }
    expected_aggregate = {
        "planned_authors": aggregate_denominator,
        **aggregate_counts,
    }
    if any(
        supplied_aggregate[field] is not None
        and supplied_aggregate[field] != expected
        for field, expected in expected_aggregate.items()
    ):
        raise ReportValidationError(
            "profile_channel aggregate counts do not match cohort totals"
        )
    normalized.update(expected_aggregate)
    aggregate_completed = (
        aggregate_counts["complete_authors"]
        + aggregate_counts["empty_authors"]
    )
    supplied_status = str(source.get("status") or "NOT_ATTEMPTED").upper()
    canonical_supplied_status = (
        "COMPLETE" if supplied_status == "EMPTY" else supplied_status
    )
    if aggregate_denominator == 0:
        derived_status = (
            "COMPLETE"
            if canonical_supplied_status == "COMPLETE"
            else "NOT_ATTEMPTED"
        )
    elif aggregate_counts["not_attempted_authors"] == aggregate_denominator:
        derived_status = "NOT_ATTEMPTED"
    elif aggregate_counts["failed_authors"] == aggregate_denominator:
        derived_status = "FAILED"
    elif aggregate_completed == aggregate_denominator:
        derived_status = "COMPLETE"
    else:
        derived_status = "PARTIAL"
    if canonical_supplied_status != derived_status:
        raise ReportValidationError(
            "profile_channel.status is inconsistent with aggregate terminal status counts"
        )
    normalized["status"] = derived_status
    normalized["coverage"] = _coverage(
        {
            "covered": aggregate_completed,
            "expected": aggregate_denominator,
        },
        "profile_channel.coverage",
    )
    return normalized


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


def _source_coverage(
    payload: Mapping[str, Any],
    smart_money: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return one explicit timing/provenance slot for every report source.

    Missing source timestamps are never filled from ``scanned_at`` or report
    generation time.  That distinction matters most for replay artifacts.
    """

    derived = _derived_source_coverage(payload, smart_money)
    supplied = payload.get("source_coverage")
    if supplied is None:
        raw_supplied: Mapping[str, Any] = {}
    else:
        raw_supplied = _mapping(supplied, "source_coverage")
    aliases = {
        "FEED": "FEED",
        "BINANCE_OFFICIAL_NEWS": "BINANCE_OFFICIAL_NEWS",
        "OFFICIAL_NEWS": "BINANCE_OFFICIAL_NEWS",
        "SMART_MONEY": "SMART_MONEY",
        "PROFILE": "PROFILE",
        "MARKET_CATALOG": "MARKET_CATALOG",
    }
    explicit: dict[str, Any] = {}
    for raw_name, value in raw_supplied.items():
        name = str(raw_name).strip().upper().replace(" ", "_").replace("-", "_")
        canonical = aliases.get(name)
        if canonical is None:
            raise ReportValidationError(f"unknown report source: {raw_name}")
        if canonical in explicit:
            raise ReportValidationError(f"duplicate report source: {canonical}")
        explicit[canonical] = value
    if "PROFILE" in explicit:
        explicit_profile = _mapping(
            explicit["PROFILE"],
            "source_coverage.PROFILE",
        )
        explicit_profile_status = str(
            explicit_profile.get("status") or ""
        ).upper()
        if (
            explicit_profile_status == "EMPTY"
            and derived["PROFILE"]["status"] == "COMPLETE"
        ):
            explicit_profile = dict(explicit_profile)
            explicit_profile["status"] = "COMPLETE"
            explicit["PROFILE"] = explicit_profile
            explicit_profile_status = "COMPLETE"
        if explicit_profile_status != derived["PROFILE"]["status"]:
            raise ReportValidationError(
                "source_coverage.PROFILE.status must match normalized profile status"
            )
    normalized = {
        name: _normalize_source_coverage(
            explicit.get(name, derived[name]),
            f"source_coverage.{name}",
        )
        for name in _REPORT_SOURCES
    }
    if (
        "PROFILE" in explicit
        and normalized["PROFILE"]["status"] != derived["PROFILE"]["status"]
    ):
        raise ReportValidationError(
            "source_coverage.PROFILE.status must match normalized profile status"
        )
    return normalized


def _first_time(source: Mapping[str, Any], *names: str) -> Any:
    return next((source.get(name) for name in names if source.get(name) is not None), None)


def _derived_source_coverage(
    payload: Mapping[str, Any],
    smart_money: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    timing_value = payload.get("capture_timing")
    timing = timing_value if isinstance(timing_value, Mapping) else {}
    feed_start = _first_time(
        timing,
        "detail_fetch_started_at_utc",
        "detail_fetch_started_at",
        "detail_fetch_started",
        "square_started_at_utc",
    )
    feed_end = _first_time(
        timing,
        "detail_fetch_completed_at_utc",
        "detail_fetch_completed_at",
        "detail_fetch_completed",
        "square_completed_at_utc",
    )
    discovery_snapshot = _first_time(
        timing,
        "discovery_snapshot_at_utc",
        "discovery_snapshot_at",
    )
    if feed_end is not None:
        feed_status, feed_capture, feed_reason = "COMPLETE", feed_end, "detail_fetch_completed"
    elif feed_start is not None or discovery_snapshot is not None:
        feed_status = "PARTIAL"
        feed_capture = discovery_snapshot or feed_start
        feed_reason = "discovery_or_fetch_started_without_completion"
    else:
        feed_status, feed_capture, feed_reason = "NOT_ATTEMPTED", None, "capture_time_missing"

    if smart_money is None:
        smart_status, smart_capture, smart_provenance, smart_reason = (
            "NOT_ATTEMPTED",
            None,
            "UNKNOWN",
            "no_smart_money_evidence",
        )
    else:
        declared = str(smart_money.get("status") or "PARTIAL").upper()
        smart_status = "COMPLETE" if declared == "COMPLETE" else "PARTIAL"
        smart_capture = smart_money.get("captured_at_utc")
        smart_provenance = str(smart_money.get("provenance") or "UNKNOWN").upper()
        smart_reason = "smart_money_evidence_present"

    profile_value = payload.get("profile_channel")
    profile = profile_value if isinstance(profile_value, Mapping) else {}
    raw_profile_status = str(profile.get("status") or "NOT_ATTEMPTED").upper()
    profile_status = (
        raw_profile_status
        if raw_profile_status in _SOURCE_STATUSES
        else "PARTIAL"
        if raw_profile_status == "EMPTY"
        else "NOT_ATTEMPTED"
    )
    profile_capture = _first_time(
        profile,
        "source_capture_time_utc",
        "captured_at_utc",
        "observed_at_utc",
    )

    catalog_capture = _first_time(
        timing,
        "market_catalog_at_utc",
        "market_catalog_at",
        "market_catalog_captured_at_utc",
        "market_catalog",
    )
    market_latest = _first_time(timing, "market_latest_at_utc")
    if catalog_capture is not None:
        market_status, market_capture, market_reason = (
            "COMPLETE",
            catalog_capture,
            "market_catalog_capture_present",
        )
    elif market_latest is not None:
        market_status, market_capture, market_reason = (
            "PARTIAL",
            market_latest,
            "market_snapshot_time_does_not_prove_catalog_capture",
        )
    else:
        market_status, market_capture, market_reason = (
            "NOT_ATTEMPTED",
            None,
            "market_catalog_capture_missing",
        )
    return {
        "FEED": {
            "status": feed_status,
            "provenance": str(payload.get("feed_provenance") or "UNKNOWN").upper(),
            "source_capture_time_utc": feed_capture,
            "capture_started_at_utc": feed_start,
            "capture_completed_at_utc": feed_end,
            "reason": feed_reason,
        },
        "BINANCE_OFFICIAL_NEWS": {
            "status": "NOT_ATTEMPTED",
            "provenance": "UNKNOWN",
            "source_capture_time_utc": None,
            "reason": "no_official_news_evidence",
        },
        "SMART_MONEY": {
            "status": smart_status,
            "provenance": smart_provenance,
            "source_capture_time_utc": smart_capture,
            "reason": smart_reason,
            "evidence_path": smart_money.get("evidence_path") if smart_money else None,
        },
        "PROFILE": {
            "status": profile_status,
            "provenance": str(profile.get("provenance") or "UNKNOWN").upper(),
            "source_capture_time_utc": profile_capture,
            "reason": str(profile.get("reason") or "profile_channel_summary"),
            "evidence_path": profile.get("evidence_path"),
        },
        "MARKET_CATALOG": {
            "status": market_status,
            "provenance": str(payload.get("market_provenance") or "UNKNOWN").upper(),
            "source_capture_time_utc": market_capture,
            "reason": market_reason,
        },
    }


def _normalize_source_coverage(value: Any, name: str) -> dict[str, Any]:
    source = _mapping(value, name)
    status = str(source.get("status") or "").upper()
    if status not in _SOURCE_STATUSES:
        raise ReportValidationError(f"{name}.status is invalid")
    provenance = str(source.get("provenance") or "UNKNOWN").upper()
    if provenance not in _SOURCE_PROVENANCE:
        raise ReportValidationError(f"{name}.provenance is invalid")

    started = _first_time(source, "capture_started_at_utc", "started_at_utc")
    completed = _first_time(source, "capture_completed_at_utc", "completed_at_utc")
    captured = _first_time(
        source,
        "source_capture_time_utc",
        "source_capture_at_utc",
        "captured_at_utc",
    )
    normalized_times: dict[str, str | None] = {}
    for field, raw in (
        ("capture_started_at_utc", started),
        ("capture_completed_at_utc", completed),
        ("source_capture_time_utc", captured or completed),
    ):
        if raw is None:
            normalized_times[field] = None
            continue
        try:
            normalized_times[field] = format_utc(parse_utc(raw))
        except (ContractViolation, TypeError) as exc:
            raise ReportValidationError(f"{name}.{field} must be timezone-aware") from exc
    if (
        normalized_times["capture_started_at_utc"] is not None
        and normalized_times["capture_completed_at_utc"] is not None
        and parse_utc(normalized_times["capture_completed_at_utc"])
        < parse_utc(normalized_times["capture_started_at_utc"])
    ):
        raise ReportValidationError(f"{name} capture completion precedes start")
    reason = source.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise ReportValidationError(f"{name}.reason must be a string")
    if status == "COMPLETE" and normalized_times["source_capture_time_utc"] is None:
        status = "PARTIAL"
        reason = (
            f"{reason};source_capture_time_missing"
            if reason
            else "source_capture_time_missing"
        )
    if status == "COMPLETE" and provenance == "UNKNOWN":
        status = "PARTIAL"
        reason = (
            f"{reason};source_provenance_missing"
            if reason
            else "source_provenance_missing"
        )
    evidence_path = source.get("evidence_path")
    if evidence_path is not None and (
        not isinstance(evidence_path, str) or not evidence_path.strip()
    ):
        raise ReportValidationError(f"{name}.evidence_path must be a non-empty string")
    coverage_version = source.get("coverage_contract_version")
    coverage_status = source.get("coverage_status")
    termination_reason = source.get("termination_reason")
    coverage_fields_present = any(
        value is not None
        for value in (coverage_version, coverage_status, termination_reason)
    )
    if coverage_fields_present and name != "source_coverage.FEED":
        raise ReportValidationError(f"{name} cannot declare Feed coverage fields")
    if coverage_fields_present:
        coverage_status = str(coverage_status or "").upper()
        termination_reason = str(termination_reason or "").upper()
        if coverage_version not in {None, "square-feed-coverage/v1"}:
            raise ReportValidationError(f"{name}.coverage_contract_version is invalid")
        if coverage_status not in {
            "BOUNDED_COMPLETE",
            "PARTIAL",
            "CAPPED",
            "BLOCKED",
            "LEGACY_UNVERIFIED",
        }:
            raise ReportValidationError(f"{name}.coverage_status is invalid")
        if termination_reason not in {
            "EXHAUSTED",
            "STAGNANT",
            "HARD_LIMIT",
            "SCROLL_LIMIT",
            "ERROR",
            "LEGACY_UNVERIFIED",
        }:
            raise ReportValidationError(f"{name}.termination_reason is invalid")
        expected_source_status = (
            "COMPLETE"
            if coverage_status == "BOUNDED_COMPLETE"
            else "FAILED"
            if coverage_status == "BLOCKED"
            else "PARTIAL"
        )
        if status != expected_source_status:
            raise ReportValidationError(
                f"{name}.status conflicts with bounded coverage status"
            )
    return {
        "status": status,
        "provenance": provenance,
        **normalized_times,
        "reason": reason,
        "evidence_path": evidence_path,
        "coverage_contract_version": coverage_version,
        "coverage_status": coverage_status,
        "termination_reason": termination_reason,
    }


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
