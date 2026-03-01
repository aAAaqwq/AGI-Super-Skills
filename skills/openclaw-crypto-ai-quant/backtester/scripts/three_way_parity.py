#!/usr/bin/env python3
"""Three-way GPU↔CPU↔Live parity report (AQC-753).

Compares results across three execution paths:
1. GPU sweep top result (from JSONL)
2. CPU replay (from bt-cli JSON output)
3. Live kernel shadow (from kernel_shadow_report.json)

Usage:
    python three_way_parity.py \
        --gpu-results sweep_results.jsonl \
        --cpu-results cpu_replay.json \
        --shadow-report kernel_shadow_report.json \
        --output artifacts/parity/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Tolerance configuration (env overrides)
# ---------------------------------------------------------------------------

def _tol(env_key: str, default: float) -> float:
    return float(os.environ.get(env_key, default))


def get_tolerances() -> dict[str, float]:
    return {
        "total_pnl": _tol("AQC_3WAY_TOL_PNL", 0.02),
        "max_drawdown_pct": _tol("AQC_3WAY_TOL_DD", 0.03),
        "win_rate": _tol("AQC_3WAY_TOL_WR", 0.05),
        "trade_count": _tol("AQC_3WAY_TOL_TC", 0.05),
        "profit_factor": _tol("AQC_3WAY_TOL_PF", 0.50),
    }


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class MetricSet:
    """Normalised metrics from any execution path."""
    source: str
    total_pnl: float
    total_trades: int
    win_rate: float
    max_drawdown_pct: float
    profit_factor: float


@dataclass
class ParityCheck:
    metric: str
    source_a: str
    value_a: float
    source_b: str
    value_b: float
    delta: float
    tolerance: float
    passed: bool


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_gpu_results(path: Path) -> MetricSet:
    """Parse GPU sweep JSONL and return the top result by total_pnl."""
    best = None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if best is None or row.get("total_pnl", 0) > best.get("total_pnl", 0):
                best = row
    if best is None:
        raise ValueError(f"No results found in GPU JSONL: {path}")
    return MetricSet(
        source="GPU",
        total_pnl=best["total_pnl"],
        total_trades=int(best["total_trades"]),
        win_rate=best["win_rate"],
        max_drawdown_pct=best["max_drawdown_pct"],
        profit_factor=best["profit_factor"],
    )


def parse_cpu_results(path: Path) -> MetricSet:
    """Parse CPU replay JSON output (bt-cli --output-json format)."""
    with open(path) as f:
        data = json.load(f)
    return MetricSet(
        source="CPU",
        total_pnl=data["total_pnl"],
        total_trades=int(data["total_trades"]),
        win_rate=data["win_rate"],
        max_drawdown_pct=data["max_drawdown_pct"],
        profit_factor=data["profit_factor"],
    )


def parse_shadow_report(path: Path) -> MetricSet:
    """Parse kernel shadow report JSON (list of ShadowComparison dicts).

    The shadow report tracks live-vs-kernel deltas per metric. We extract
    the latest kernel_value for each metric we care about. If a metric is
    missing we fall back to old_value (the Python live path result).
    """
    with open(path) as f:
        data = json.load(f)

    # Index: latest comparison per metric name
    latest: dict[str, dict] = {}
    for entry in data:
        m = entry["metric"]
        if m not in latest or entry["timestamp"] > latest[m]["timestamp"]:
            latest[m] = entry

    def _get(metric: str, fallback: float = 0.0) -> float:
        if metric in latest:
            return latest[metric]["kernel_value"]
        return fallback

    # Shadow report may use either "pnl" or "total_pnl" as the metric key
    pnl = _get("total_pnl", _get("pnl", 0.0))

    return MetricSet(
        source="Live",
        total_pnl=pnl,
        total_trades=int(_get("total_trades", _get("trade_count", 0))),
        win_rate=_get("win_rate", 0.0),
        max_drawdown_pct=_get("max_drawdown_pct", _get("max_dd", 0.0)),
        profit_factor=_get("profit_factor", 0.0),
    )


# ---------------------------------------------------------------------------
# Comparison engine
# ---------------------------------------------------------------------------

def compare_pair(a: MetricSet, b: MetricSet, tolerances: dict[str, float]) -> list[ParityCheck]:
    """Compare two MetricSets across all tracked metrics."""
    checks: list[ParityCheck] = []
    metrics = [
        ("total_pnl", "total_pnl"),
        ("total_trades", "trade_count"),
        ("win_rate", "win_rate"),
        ("max_drawdown_pct", "max_drawdown_pct"),
        ("profit_factor", "profit_factor"),
    ]
    for attr, tol_key in metrics:
        va = getattr(a, attr)
        vb = getattr(b, attr)
        va_f = float(va)
        vb_f = float(vb)

        # For trade count, use relative error
        if attr == "total_trades" and vb_f != 0:
            delta = abs(va_f - vb_f) / vb_f
        elif attr == "total_trades":
            delta = abs(va_f - vb_f)
        else:
            delta = abs(va_f - vb_f)

        tol = tolerances[tol_key]
        checks.append(ParityCheck(
            metric=attr,
            source_a=a.source,
            value_a=va_f,
            source_b=b.source,
            value_b=vb_f,
            delta=delta,
            tolerance=tol,
            passed=delta <= tol,
        ))
    return checks


def run_three_way(
    gpu: MetricSet, cpu: MetricSet, live: MetricSet, tolerances: dict[str, float]
) -> list[ParityCheck]:
    """Run pairwise comparisons for all three paths."""
    checks: list[ParityCheck] = []
    checks.extend(compare_pair(gpu, cpu, tolerances))
    checks.extend(compare_pair(gpu, live, tolerances))
    checks.extend(compare_pair(cpu, live, tolerances))
    return checks


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def generate_markdown(checks: list[ParityCheck], output_dir: Path) -> Path:
    """Write a markdown parity report and return the path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"parity_report_{ts}.md"

    total = len(checks)
    passed = sum(1 for c in checks if c.passed)
    failed = total - passed
    overall = "PASS" if failed == 0 else "FAIL"

    lines = [
        f"# Three-Way Parity Report",
        f"",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()}",
        f"**Result**: {overall} ({passed}/{total} checks passed)",
        f"",
        f"## Pairwise Comparisons",
        f"",
        f"| Pair | Metric | Value A | Value B | Delta | Tolerance | Status |",
        f"|------|--------|--------:|--------:|------:|----------:|--------|",
    ]

    for c in checks:
        status = "PASS" if c.passed else "**FAIL**"
        pair = f"{c.source_a} vs {c.source_b}"
        lines.append(
            f"| {pair} | {c.metric} | {c.value_a:.6f} | {c.value_b:.6f} "
            f"| {c.delta:.6f} | {c.tolerance:.6f} | {status} |"
        )

    lines.append("")

    if failed > 0:
        lines.append("## Failures")
        lines.append("")
        for c in checks:
            if not c.passed:
                lines.append(
                    f"- **{c.source_a} vs {c.source_b} / {c.metric}**: "
                    f"delta={c.delta:.6f} > tolerance={c.tolerance:.6f}"
                )
        lines.append("")

    report_path.write_text("\n".join(lines))
    return report_path


def emit_ci_annotations(checks: list[ParityCheck]) -> None:
    """Output GitHub Actions annotations for failed checks."""
    for c in checks:
        if not c.passed:
            print(
                f"::error title=Parity failure: {c.source_a} vs {c.source_b} / {c.metric}"
                f"::{c.metric} delta={c.delta:.6f} exceeds tolerance={c.tolerance:.6f}"
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Three-way GPU↔CPU↔Live parity report",
    )
    p.add_argument("--gpu-results", type=Path, required=True,
                   help="Path to GPU sweep JSONL results")
    p.add_argument("--cpu-results", type=Path, required=True,
                   help="Path to CPU replay JSON output")
    p.add_argument("--shadow-report", type=Path, required=True,
                   help="Path to kernel shadow report JSON")
    p.add_argument("--output", type=Path, default=Path("artifacts/parity"),
                   help="Output directory for report (default: artifacts/parity/)")
    p.add_argument("--ci", action="store_true",
                   help="Emit GitHub Actions annotations on failure")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    tolerances = get_tolerances()

    # Parse all three sources
    gpu = parse_gpu_results(args.gpu_results)
    cpu = parse_cpu_results(args.cpu_results)
    live = parse_shadow_report(args.shadow_report)

    # Run comparisons
    checks = run_three_way(gpu, cpu, live, tolerances)

    # Generate report
    report_path = generate_markdown(checks, args.output)

    failures = [c for c in checks if not c.passed]

    # Console summary
    print(f"Three-way parity report: {report_path}")
    print(f"  Total checks: {len(checks)}")
    print(f"  Passed:       {len(checks) - len(failures)}")
    print(f"  Failed:       {len(failures)}")

    if failures:
        print("\nFailed checks:")
        for c in failures:
            print(
                f"  {c.source_a} vs {c.source_b} / {c.metric}: "
                f"delta={c.delta:.6f} > tol={c.tolerance:.6f}"
            )

    if args.ci:
        emit_ci_annotations(checks)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
