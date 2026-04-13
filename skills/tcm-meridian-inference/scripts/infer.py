#!/usr/bin/env python3
"""TCM Meridian Inference MVP CLI

Goal for c1/c2: project structure readiness + Excel-derived rule JSON.
This CLI stays stdlib-only and is intentionally lightweight.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

MERIDIANS = ["liver", "spleen", "kidney", "stomach", "gallbladder", "bladder"]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _get_by_path(obj: dict, dotted: str) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(dotted)
        cur = cur[part]
    return cur


def load_rules(rules_dir: Path) -> Tuple[dict, dict, dict]:
    thresholds = _load_json(rules_dir / "thresholds.json")
    meridian_rules = _load_json(rules_dir / "meridian_rules.json")
    combo_rules = _load_json(rules_dir / "combination_rules.json")
    return thresholds, meridian_rules, combo_rules


def normalize_measurements(payload: dict) -> Dict[str, dict]:
    ms = payload.get("measurements")
    if not isinstance(ms, dict):
        raise ValueError("payload.measurements must be an object")
    out: Dict[str, dict] = {}
    for m in MERIDIANS:
        v = ms.get(m)
        if not isinstance(v, dict):
            raise ValueError(f"measurements.{m} must be an object")
        if "left" in v and "right" in v:
            left = float(v["left"])
            right = float(v["right"])
            trend = float(v.get("trendDelta", right - left))
        elif "t1" in v and "t2" in v:
            left = float(v["t1"])
            right = float(v["t2"])
            trend = right - left
        else:
            raise ValueError(f"measurements.{m} must contain left/right or t1/t2")
        out[m] = {"left": left, "right": right, "trendDelta": trend}
    return out


def eval_conditions(fields: dict, thresholds: dict, conditions: list[dict]) -> bool:
    for c in conditions:
        field = c["field"]
        op = c["op"]
        rhs = _get_by_path({"thresholds": thresholds}, c["valueFrom"]) if "valueFrom" in c else c["value"]
        lhs = fields.get(field)
        if lhs is None:
            return False
        if op == "<":
            ok = lhs < rhs
        elif op == "<=":
            ok = lhs <= rhs
        elif op == ">":
            ok = lhs > rhs
        elif op == ">=":
            ok = lhs >= rhs
        elif op == "==":
            ok = lhs == rhs
        else:
            raise ValueError(f"Unsupported op: {op}")
        if not ok:
            return False
    return True


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def combo_matches(combo_rule: dict, meridian_statuses: Dict[str, List[str]]) -> bool:
    def _match_clause(clause: dict) -> bool:
        for item in clause.get("allStatuses", []) or []:
            if item["status"] not in meridian_statuses.get(item["meridian"], []):
                return False
        msc = clause.get("minStatusCount")
        if msc:
            hit = sum(1 for sts in meridian_statuses.values() if msc["status"] in sts)
            if hit < int(msc["count"]):
                return False
        return True

    when = combo_rule.get("when") or {}
    if not _match_clause(when):
        return False
    any_of = when.get("anyOf")
    if any_of:
        return any(_match_clause(clause) for clause in any_of)
    return True


def infer(payload: dict, thresholds: dict, meridian_rules: dict, combo_rules: dict) -> dict:
    subject = payload.get("subject") or {}
    context = payload.get("context") or {}
    measurements = normalize_measurements(payload)

    scoring = thresholds["scoring"]
    base = float(scoring["base"])
    floor = float(scoring["floor"])
    ceiling = float(scoring["ceiling"])
    penalties = scoring["penalty"]

    per_meridian: Dict[str, dict] = {}
    risk_tags: List[str] = []
    advice: List[str] = []
    summaries: List[str] = []
    meridian_statuses: Dict[str, List[str]] = {}

    for m, v in measurements.items():
        left = v["left"]
        right = v["right"]
        avg = (left + right) / 2.0
        diff_abs = abs(left - right)
        trend = v["trendDelta"]
        trend_abs = abs(trend)
        fields = {
            "left": left,
            "right": right,
            "avg": avg,
            "diffAbs": diff_abs,
            "trendDelta": trend,
            "trendAbs": trend_abs,
        }

        score = base
        matched: List[dict] = []
        tags_here: List[str] = []
        statuses_here: List[str] = []
        symptoms_here: List[str] = []

        for rule in meridian_rules.get("rules", []):
            if rule.get("meridian") != m:
                continue
            if eval_conditions(fields, thresholds, rule.get("conditions", [])):
                matched.append({
                    "id": rule.get("id"),
                    "status": rule.get("status"),
                    "tag": rule.get("tag"),
                    "summary": rule.get("summary"),
                })
                if rule.get("tag"):
                    tags_here.append(rule["tag"])
                if rule.get("status"):
                    statuses_here.append(rule["status"])
                pk = rule.get("penaltyKey")
                if pk in penalties:
                    score -= float(penalties[pk])
                if rule.get("summary"):
                    summaries.append(rule["summary"])
                symptoms_here.extend(rule.get("symptoms", []) or [])
                advice.extend(rule.get("advice", []) or [])

        score = clamp(score, floor, ceiling)
        statuses_here = list(dict.fromkeys(statuses_here))
        tags_here = list(dict.fromkeys(tags_here))
        symptoms_here = list(dict.fromkeys(symptoms_here))
        meridian_statuses[m] = statuses_here

        # primary status preference for c3:
        # directional low should win over generic left/right difference.
        # This keeps left_low/right_low fixtures stable while retaining cross in statuses/tags.
        if "left_low" in statuses_here and "right_low" not in statuses_here:
            primary_status = "left_low"
        elif "right_low" in statuses_here and "left_low" not in statuses_here:
            primary_status = "right_low"
        elif "cross" in statuses_here:
            primary_status = "cross"
        elif "left_low" in statuses_here:
            primary_status = "left_low"
        elif "right_low" in statuses_here:
            primary_status = "right_low"
        else:
            primary_status = "stable"

        per_meridian[m] = {
            "left": left,
            "right": right,
            "trendDelta": trend,
            "avg": avg,
            "diffAbs": diff_abs,
            "score": round(score, 1),
            "status": primary_status,
            "statuses": statuses_here,
            "tags": tags_here,
            "symptoms": symptoms_here,
            "matchedRules": matched,
        }
        risk_tags.extend(tags_here)

    combinations: List[dict] = []
    combo_penalty = float(penalties.get("combo", 0))
    for rule in combo_rules.get("rules", []):
        if combo_matches(rule, meridian_statuses):
            combinations.append({
                "id": rule.get("id"),
                "name": rule.get("name"),
                "tags": rule.get("tags", []),
                "summary": rule.get("summary"),
            })
            summaries.append(rule.get("summary", ""))
            advice.extend(rule.get("advice", []) or [])
            risk_tags.extend(rule.get("tags", []) or [])
            for m in per_meridian:
                if per_meridian[m]["status"] != "stable":
                    per_meridian[m]["score"] = round(clamp(per_meridian[m]["score"] - combo_penalty, floor, ceiling), 1)

    risk_tags = list(dict.fromkeys(risk_tags))
    advice = list(dict.fromkeys(a for a in advice if a))
    summaries = [s for s in summaries if s]

    scores_map = {m: per_meridian[m]["score"] for m in MERIDIANS}
    health_score = round(sum(scores_map.values()) / len(MERIDIANS), 1)
    meridians = {m: {
        "status": per_meridian[m]["status"],
        "score": per_meridian[m]["score"],
        "symptoms": per_meridian[m]["symptoms"],
        "tags": per_meridian[m]["tags"],
    } for m in MERIDIANS}
    six_dimension_scores = [{"meridian": m, "score": scores_map[m], "tags": per_meridian[m]["tags"]} for m in MERIDIANS]

    # Determine scenario label for storefront headline (c6 acceptance)
    left_cnt = sum(1 for m in MERIDIANS if per_meridian[m]["status"] == "left_low")
    right_cnt = sum(1 for m in MERIDIANS if per_meridian[m]["status"] == "right_low")
    combo_names = [c.get("name", "") for c in combinations if c.get("name")]

    if not risk_tags:
        scenario = "stable"
    elif left_cnt >= 4 and right_cnt == 0:
        scenario = "left"
    elif right_cnt >= 4 and left_cnt == 0:
        scenario = "right"
    elif len(combinations) >= 2:
        scenario = "multi"
    else:
        scenario = "cross"

    if scenario == "stable":
        report_summary = "整体相对平稳，本次结果更适合做状态追踪，不等同于医疗诊断。"
        focus = "整体相对平稳"
        talk_track = [
            "本次六经整体比较平稳，更像状态跟踪结果。",
            "这不等同于医疗诊断，主要用于看趋势和左右差异。",
            "建议保持作息，按周期复测即可。",
        ]
    else:
        report_summary = "；".join(summaries[:8])
        if scenario == "left":
            focus = "左侧偏低"
        elif scenario == "right":
            focus = "右侧偏低"
        elif scenario == "multi":
            focus = "多经络失衡"
        else:
            focus = "左右交叉/不对称"

        # Append up to 2 key combination names for clarity
        if combo_names:
            focus = focus + "：重点关注 " + "、".join(combo_names[:2])

        talk_track = [
            "这次主要看到的是经络侧的偏低/交叉信号，不等同于医疗诊断。",
            "更适合把它理解为体感、作息和左右差异的提示。",
            "建议结合近期状态，按 20-30 分钟间隔复测 2-3 次看趋势。",
        ]

    storefront = {
        "focusHeadline": focus,
        "clientExplanation": report_summary if "不等同" in report_summary else report_summary + "；结果不等同于医疗诊断。",
        "talkTrack": talk_track,
        "retestPrompt": "建议间隔 20-30 分钟复测一次，连续 2-3 次趋势更可靠。",
    }

    return {
        "engine": {"mode": "rule-based-mvp", "version": "0.2.0"},
        "subject": subject,
        "context": context,
        "input": {"mode": "foot_six", "meridians": MERIDIANS},
        "healthScore": health_score,
        "scores": scores_map,
        "meridians": meridians,
        "sixDimensionScores": six_dimension_scores,
        "riskTags": risk_tags,
        "combinations": combinations,
        "summary": report_summary,
        "reportSummary": report_summary,
        "advice": advice,
        "storefront": storefront,
        "trace": {"perMeridian": per_meridian, "thresholds": thresholds, "comboRulesMatched": combinations},
    }


def build_argparser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="infer.py", description="TCM meridian inference MVP (rule-based) CLI")
    ap.add_argument("input", nargs="?", help="Input JSON file (see fixtures/*.json)")
    ap.add_argument("--rules-dir", default="rules", help="Rules directory (default: ./rules)")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    ap.add_argument("--out", help="Write output JSON to file")
    return ap


def main() -> int:
    ap = build_argparser()
    args = ap.parse_args()
    if not args.input:
        ap.print_help()
        return 0
    project_root = Path(__file__).resolve().parents[1]
    in_path = (project_root / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input)
    rules_dir = (project_root / args.rules_dir).resolve()
    if not in_path.exists():
        raise SystemExit(f"Input not found: {in_path}")
    if not rules_dir.exists():
        raise SystemExit(f"Rules dir not found: {rules_dir}")
    payload = _load_json(in_path)
    thresholds, meridian_rules, combo_rules = load_rules(rules_dir)
    result = infer(payload, thresholds, meridian_rules, combo_rules)
    text = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.out:
        out_path = (project_root / args.out).resolve() if not Path(args.out).is_absolute() else Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
    else:
        try:
            print(text)
        except BrokenPipeError:
            # Allow piping to tools that may close early (e.g., head/grep)
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
