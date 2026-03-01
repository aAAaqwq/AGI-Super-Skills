#!/usr/bin/env python3
"""Generate a 17-phase sweep set from full_144v coverage.

Design goals:
- Keep full axis coverage from `full_144v.yaml` (every axis appears once).
- Keep total grid size near a practical target (default ~100k combos per interval).
- Preserve broader resolution (3-point min/mid/max) on core axes from `full_34axis`
  plus selected high-impact risk/exit/regime dimensions.
"""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Axis:
    path: str
    values: list[float]

# Axes that are valid config keys but not meaningful to optimise in bt-core sweeps.
NO_OP_SWEEP_AXES = {
    "trade.use_bbo_for_fills",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    obj = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(obj, dict):
        raise ValueError(f"invalid YAML root: {path}")
    return obj


def _uniq(values: list[float]) -> list[float]:
    out: list[float] = []
    seen: set[float] = set()
    for raw in values:
        v = float(raw)
        if v in seen:
            continue
        out.append(v)
        seen.add(v)
    return out


def _sample_points(vals: list[float], n: int) -> list[float]:
    raw = _uniq(vals)
    if len(raw) == 0:
        return []
    n = int(max(1, n))
    if len(raw) <= n:
        return raw

    idxs: list[int] = []
    for i in range(n):
        pos = round(i * (len(raw) - 1) / (n - 1))
        idxs.append(int(pos))
    idxs = sorted(set(idxs))
    out = [raw[i] for i in idxs]
    if len(out) == n:
        return out

    # Fill missing slots deterministically from left to right.
    need = n - len(out)
    used = set(out)
    for v in raw:
        if v in used:
            continue
        out.append(v)
        used.add(v)
        need -= 1
        if need == 0:
            break
    out.sort()
    return out


def _combo_count(axes: list[Axis]) -> int:
    n = 1
    for axis in axes:
        n *= len(axis.values)
    return int(n)


def _phase_id(i: int) -> str:
    return f"p{i:02d}_144v"


def _dump_yaml(path: Path, obj: dict[str, Any]) -> None:
    text = yaml.safe_dump(obj, sort_keys=False)
    path.write_text(text, encoding="utf-8")


def _build_initial_keep_three(axes_34: list[dict[str, Any]]) -> set[str]:
    baseline_paths = {
        str(item.get("path", "")).strip()
        for item in axes_34
        if isinstance(item, dict) and str(item.get("path", "")).strip()
    }
    extra_keep_three = {
        "trade.smart_exit_adx_exhaustion_lt",
        "trade.smart_exit_adx_exhaustion_lt_low_conf",
        "trade.rsi_exit_profit_atr_switch",
        "trade.rsi_exit_ub_hi_profit",
        "trade.rsi_exit_lb_hi_profit",
        "thresholds.tp_and_momentum.tp_mult_strong",
        "thresholds.tp_and_momentum.tp_mult_weak",
        "market_regime.breadth_block_short_above",
        "market_regime.breadth_block_long_below",
        "market_regime.auto_reverse_breadth_low",
        "market_regime.auto_reverse_breadth_high",
        "indicators.ema_macro_window",
    }
    enum_three = {
        "trade.entry_min_confidence",
        "trade.add_min_confidence",
        "thresholds.entry.pullback_confidence",
        "thresholds.entry.macd_hist_entry_mode",
    }
    return baseline_paths | extra_keep_three | enum_three


def _collect_axis_source(axes_144: list[dict[str, Any]]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {}
    for item in axes_144:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path", "")).strip()
        raw_values = item.get("values", [])
        if not path or not isinstance(raw_values, list):
            continue
        if path in NO_OP_SWEEP_AXES:
            continue
        if path in out:
            raise ValueError(f"duplicate axis path in full_144v: {path}")
        vals = _uniq([float(v) for v in raw_values])
        if len(vals) == 0:
            raise ValueError(f"axis has empty values: {path}")
        out[path] = vals
    return out


def _build_points_map(
    axis_source: dict[str, list[float]],
    keep_three: set[str],
) -> dict[str, int]:
    points: dict[str, int] = {}
    for path, vals in axis_source.items():
        if len(vals) <= 2:
            points[path] = len(vals)
        elif path in keep_three:
            points[path] = 3
        else:
            points[path] = 2
    return points


def _reduced_axes(axis_source: dict[str, list[float]], points_map: dict[str, int]) -> list[Axis]:
    out: list[Axis] = []
    for path, full_values in sorted(axis_source.items()):
        n = int(points_map.get(path, 2))
        vals = _sample_points(full_values, n)
        out.append(Axis(path=path, values=vals))
    return out


def _partition_phases(reduced: list[Axis], phase_count: int, max_axes_per_phase: int) -> list[list[Axis]]:
    phases: list[list[Axis]] = [[] for _ in range(phase_count)]
    phase_weights = [0.0 for _ in range(phase_count)]

    items = sorted(reduced, key=lambda a: (-len(a.values), a.path))
    for axis in items:
        choices = [i for i, arr in enumerate(phases) if len(arr) < max_axes_per_phase]
        if not choices:
            choices = list(range(phase_count))
        idx = min(choices, key=lambda i: (phase_weights[i], len(phases[i])))
        phases[idx].append(axis)
        phase_weights[idx] += math.log(len(axis.values))
    return phases


def _phase_total_combo(phases: list[list[Axis]]) -> int:
    total = 0
    for arr in phases:
        total += _combo_count(arr)
    return int(total)


def _compute_total_combo(
    *,
    axis_source: dict[str, list[float]],
    points_map: dict[str, int],
    phase_count: int,
    max_axes_per_phase: int,
) -> int:
    reduced = _reduced_axes(axis_source, points_map)
    phases = _partition_phases(reduced, phase_count, max_axes_per_phase)
    return _phase_total_combo(phases)


def _auto_tune_points_map(
    *,
    axis_source: dict[str, list[float]],
    points_seed: dict[str, int],
    phase_count: int,
    max_axes_per_phase: int,
    target_combo: int,
) -> tuple[dict[str, int], int]:
    points_map = dict(points_seed)
    current = _compute_total_combo(
        axis_source=axis_source,
        points_map=points_map,
        phase_count=phase_count,
        max_axes_per_phase=max_axes_per_phase,
    )
    if current >= target_combo:
        return points_map, current

    while current < target_combo:
        upgrades: list[tuple[str, int]] = []
        for path, vals in axis_source.items():
            cur = int(points_map.get(path, 2))
            max_allowed = min(len(vals), 4)
            if cur < max_allowed:
                upgrades.append((path, cur + 1))

        if not upgrades:
            break

        best_above_path: str | None = None
        best_above_points: int | None = None
        best_above_combo: int | None = None
        best_below_path: str | None = None
        best_below_points: int | None = None
        best_below_combo = current

        for path, new_points in upgrades:
            trial_points = dict(points_map)
            trial_points[path] = int(new_points)
            trial_combo = _compute_total_combo(
                axis_source=axis_source,
                points_map=trial_points,
                phase_count=phase_count,
                max_axes_per_phase=max_axes_per_phase,
            )
            if trial_combo >= target_combo:
                if best_above_combo is None or trial_combo < best_above_combo:
                    best_above_combo = trial_combo
                    best_above_path = path
                    best_above_points = int(new_points)
            elif trial_combo > best_below_combo:
                best_below_combo = trial_combo
                best_below_path = path
                best_below_points = int(new_points)

        if best_above_path is not None and best_above_combo is not None and best_above_points is not None:
            points_map[best_above_path] = best_above_points
            current = best_above_combo
            break
        if best_below_path is None or best_below_points is None:
            break
        points_map[best_below_path] = best_below_points
        current = best_below_combo

    return points_map, current


def build(
    *,
    full_144v_path: Path,
    full_34_path: Path,
    out_dir: Path,
    source_spec_ref: str,
    reference_spec_ref: str,
    phase_count: int = 17,
    max_axes_per_phase: int = 9,
    target_combo: int = 100000,
) -> dict[str, Any]:
    src_144 = _load_yaml(full_144v_path)
    src_34 = _load_yaml(full_34_path)

    axes_144 = src_144.get("axes", [])
    axes_34 = src_34.get("axes", [])
    if not isinstance(axes_144, list) or not isinstance(axes_34, list):
        raise ValueError("sweep specs must define `axes` as a list")

    axis_source = _collect_axis_source(axes_144)
    if len(axis_source) == 0:
        raise ValueError("no axes found in full_144v")

    keep_three_seed = _build_initial_keep_three(axes_34)
    points_seed = _build_points_map(axis_source, keep_three_seed)
    base_total = _compute_total_combo(
        axis_source=axis_source,
        points_map=points_seed,
        phase_count=phase_count,
        max_axes_per_phase=max_axes_per_phase,
    )

    points_map = dict(points_seed)
    achieved_target_combo = base_total
    if int(target_combo) > 0:
        points_map, achieved_target_combo = _auto_tune_points_map(
            axis_source=axis_source,
            points_seed=points_seed,
            phase_count=phase_count,
            max_axes_per_phase=max_axes_per_phase,
            target_combo=int(target_combo),
        )

    reduced = _reduced_axes(axis_source, points_map)
    phases = _partition_phases(reduced, phase_count, max_axes_per_phase)
    total_combo = _phase_total_combo(phases)

    out_dir.mkdir(parents=True, exist_ok=True)

    manifest_phases: list[dict[str, Any]] = []
    all_paths_written: set[str] = set()
    for i, arr in enumerate(phases, start=1):
        arr_sorted = sorted(arr, key=lambda a: a.path)
        spec = {
            "initial_balance": float(src_144.get("initial_balance", 10000.0)),
            "lookback": int(src_144.get("lookback", 200)),
            "axes": [{"path": a.path, "values": [float(v) for v in a.values]} for a in arr_sorted],
        }
        phase_file = out_dir / f"{_phase_id(i)}.yaml"
        header = (
            f"# {_phase_id(i)}\n"
            "# Auto-generated from full_144v coverage.\n"
            "# Values are reduced for phase-grid practicality.\n"
        )
        phase_file.write_text(header + yaml.safe_dump(spec, sort_keys=False), encoding="utf-8")

        combo = _combo_count(arr_sorted)
        for axis in arr_sorted:
            all_paths_written.add(axis.path)
        manifest_phases.append(
            {
                "id": _phase_id(i),
                "file": str(phase_file.name),
                "axis_count": len(arr_sorted),
                "combo": combo,
                "two_value_axes": sum(1 for a in arr_sorted if len(a.values) == 2),
                "three_value_axes": sum(1 for a in arr_sorted if len(a.values) == 3),
                "four_value_axes": sum(1 for a in arr_sorted if len(a.values) == 4),
                "paths": [a.path for a in arr_sorted],
            }
        )

    all_paths_src = {a.path for a in reduced}
    if all_paths_written != all_paths_src:
        miss = sorted(all_paths_src - all_paths_written)
        extra = sorted(all_paths_written - all_paths_src)
        raise ValueError(f"path coverage mismatch: missing={len(miss)} extra={len(extra)}")

    manifest = {
        "source_spec": str(source_spec_ref),
        "reference_spec": str(reference_spec_ref),
        "phase_count": int(phase_count),
        "total_axes": len(reduced),
        "base_combo": int(base_total),
        "target_combo": int(target_combo),
        "achieved_combo": int(achieved_target_combo),
        "total_combo": int(total_combo),
        "four_value_axes_total": int(sum(1 for a in reduced if len(a.values) == 4)),
        "three_value_axes_total": int(sum(1 for a in reduced if len(a.values) == 3)),
        "two_value_axes_total": int(sum(1 for a in reduced if len(a.values) == 2)),
        "notes": [
            "All sweepable full_144v axes are included once across the 17 phases.",
            "Known no-op axes are excluded from sweep output (currently: trade.use_bbo_for_fills).",
            "Most axes use 2-point min/max values; selected axes use 3-point or 4-point samples.",
            "Auto-tuning promotes additional 3/4-point axes until the target combo is reached.",
        ],
        "phases": manifest_phases,
    }
    _dump_yaml(out_dir / "manifest.yaml", manifest)
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate 17-phase 144v sweep specs.")
    ap.add_argument(
        "--full-144v",
        default="backtester/sweeps/full_144v.yaml",
        help="Path to the full 144v sweep spec.",
    )
    ap.add_argument(
        "--full-34",
        default="backtester/sweeps/full_34axis.yaml",
        help="Path to the baseline 34-axis sweep spec.",
    )
    ap.add_argument(
        "--out-dir",
        default="backtester/sweeps/full_144v_17phase",
        help="Output directory for generated phase specs.",
    )
    ap.add_argument("--phase-count", type=int, default=17, help="Number of phases (default: 17).")
    ap.add_argument("--max-axes-per-phase", type=int, default=9, help="Max axes per phase.")
    ap.add_argument(
        "--target-combo",
        type=int,
        default=100000,
        help="Target total combos per interval (0 disables auto-tuning).",
    )
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[2]
    full_144v = (root / str(args.full_144v)).resolve()
    full_34 = (root / str(args.full_34)).resolve()
    out_dir = (root / str(args.out_dir)).resolve()

    manifest = build(
        full_144v_path=full_144v,
        full_34_path=full_34,
        out_dir=out_dir,
        source_spec_ref=str(args.full_144v),
        reference_spec_ref=str(args.full_34),
        phase_count=int(args.phase_count),
        max_axes_per_phase=int(args.max_axes_per_phase),
        target_combo=int(args.target_combo),
    )

    print(
        f"Generated {manifest['phase_count']} phases, "
        f"{manifest['total_axes']} axes, total_combo={manifest['total_combo']} "
        f"(target={manifest['target_combo']}, base={manifest['base_combo']})"
    )
    for ph in manifest["phases"]:
        print(
            f"{ph['id']}: axes={ph['axis_count']} combo={ph['combo']} "
            f"(2v={ph['two_value_axes']}, 3v={ph['three_value_axes']}, 4v={ph['four_value_axes']})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
