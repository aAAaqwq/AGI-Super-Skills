#!/usr/bin/env python3
"""Plan retention cleanup; deletion is opt-in and root-confirmed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scanner.contracts import ContractViolation, parse_utc  # noqa: E402
from scanner.retention import (  # noqa: E402
    ArtifactKind,
    RetentionArtifact,
    plan_retention,
)


def _contained_path(root: Path, relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute():
        raise ContractViolation("manifest paths must be non-empty and relative")
    candidate = (root / relative_path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ContractViolation("manifest path escapes cleanup root")
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--as-of", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-delete-root")
    args = parser.parse_args(argv)

    try:
        root = args.root.resolve()
        payload = json.loads(args.manifest.read_text(encoding="utf-8"))
        records = payload.get("artifacts")
        if not isinstance(records, list):
            raise ContractViolation("retention manifest must contain artifacts")
        artifacts = tuple(
            RetentionArtifact(
                path=_contained_path(root, item["path"]),
                kind=ArtifactKind(item["kind"]),
                created_at=parse_utc(item["created_at"]),
            )
            for item in records
        )
        plan = plan_retention(
            artifacts,
            as_of=parse_utc(args.as_of),
            aggregate_before=payload.get("aggregate_before", ""),
            aggregate_after=payload.get("aggregate_after", ""),
            dry_run=not args.apply,
        )
        if args.apply:
            if not args.confirm_delete_root:
                raise ContractViolation("--apply requires --confirm-delete-root")
            confirmed = Path(args.confirm_delete_root).resolve()
            if confirmed != root:
                raise ContractViolation("--apply requires an exact --confirm-delete-root")
            for artifact in plan.cleanup_candidates:
                if artifact.path.is_dir():
                    raise ContractViolation("retention cleanup never removes directories")
                if artifact.path.exists():
                    artifact.path.unlink()
        output = {
            "mode": "APPLY" if args.apply else "DRY_RUN",
            "retained_count": len(plan.retained),
            "cleanup_candidate_count": len(plan.cleanup_candidates),
            "cleanup_candidates": [str(item.path) for item in plan.cleanup_candidates],
            "aggregate_fingerprint": plan.aggregate_fingerprint,
        }
        print(json.dumps(output, sort_keys=True))
        return 0
    except (ContractViolation, KeyError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"cleanup refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
