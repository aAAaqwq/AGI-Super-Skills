#!/usr/bin/env python3
"""Build a single-combo sweep spec from a candidate row.

This preserves axis metadata (including gate clauses) from the source sweep spec
and rewrites each axis `values` list to a single value from the candidate row.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


def _load_candidate_row(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"empty candidate row file: {path}")
    if path.suffix.lower() == ".jsonl":
        line = next((ln for ln in text.splitlines() if ln.strip()), "")
        if not line:
            raise ValueError(f"no JSON row found in: {path}")
        row = json.loads(line)
    else:
        row = json.loads(text)
    if not isinstance(row, dict):
        raise ValueError(f"candidate row must be a JSON object: {path}")
    return row


def _normalise_overrides(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return {str(k): v for k, v in raw.items()}
    if isinstance(raw, list):
        out: dict[str, Any] = {}
        for item in raw:
            if not (isinstance(item, (list, tuple)) and len(item) == 2):
                raise ValueError("invalid overrides list item (expected [path, value])")
            out[str(item[0])] = item[1]
        return out
    raise ValueError("candidate row 'overrides' must be object or list-of-pairs")


def build_spec(
    *,
    source_spec_path: Path,
    candidate_row_path: Path,
    output_path: Path,
    allow_missing: bool,
    allow_extra: bool,
) -> None:
    src = yaml.safe_load(source_spec_path.read_text(encoding="utf-8"))
    if not isinstance(src, dict):
        raise ValueError(f"invalid sweep spec root (expected mapping): {source_spec_path}")

    axes = src.get("axes")
    if not isinstance(axes, list):
        raise ValueError(f"invalid sweep spec axes (expected list): {source_spec_path}")

    row = _load_candidate_row(candidate_row_path)
    overrides = _normalise_overrides(row.get("overrides"))

    out = dict(src)
    out_axes: list[dict[str, Any]] = []
    used: set[str] = set()

    for axis in axes:
        if not isinstance(axis, dict):
            raise ValueError("each axis must be a mapping")
        if "path" not in axis:
            raise ValueError("axis missing 'path'")
        path = str(axis["path"])
        axis_out = dict(axis)
        if path in overrides:
            axis_out["values"] = [overrides[path]]
            used.add(path)
        else:
            if allow_missing:
                old_values = axis_out.get("values")
                if isinstance(old_values, list) and old_values:
                    axis_out["values"] = [old_values[0]]
                else:
                    axis_out["values"] = [0.0]
            else:
                raise ValueError(f"candidate row missing value for axis path: {path}")
        out_axes.append(axis_out)

    extra_paths = sorted(set(overrides.keys()) - used)
    if extra_paths and not allow_extra:
        preview = ", ".join(extra_paths[:8])
        more = "" if len(extra_paths) <= 8 else f" (+{len(extra_paths)-8} more)"
        raise ValueError(f"candidate row has paths not in sweep spec: {preview}{more}")

    out["axes"] = out_axes
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(out, sort_keys=False), encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build a one-combo sweep spec from full sweep spec + candidate row."
    )
    p.add_argument("--sweep-spec", required=True, help="Source sweep YAML (for axis metadata/gates)")
    p.add_argument("--candidate-row", required=True, help="Candidate row JSON/JSONL file")
    p.add_argument("--output", required=True, help="Output YAML path")
    p.add_argument(
        "--allow-missing",
        action="store_true",
        help="Allow missing axis paths in candidate row; uses first source value as fallback",
    )
    p.add_argument(
        "--allow-extra",
        action="store_true",
        help="Allow candidate paths that do not exist in source sweep spec",
    )
    return p


def main() -> int:
    args = _build_parser().parse_args()
    build_spec(
        source_spec_path=Path(args.sweep_spec),
        candidate_row_path=Path(args.candidate_row),
        output_path=Path(args.output),
        allow_missing=bool(args.allow_missing),
        allow_extra=bool(args.allow_extra),
    )
    print(Path(args.output).resolve().as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

