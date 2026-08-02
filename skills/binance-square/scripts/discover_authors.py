#!/usr/bin/env python3
"""Parse local Binance Square author/leaderboard evidence; never fetch network data."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from scanner.authors import (
    assess_leaderboard_coverage,
    load_seed_profile_evidence,
    parse_30d_leaderboards,
)
from scanner.contracts import SCHEMA_VERSION, ContractViolation
from scanner.discovery import (
    ProfileFetchOutcome,
    parse_profile_content_response,
    plan_profile_fetches,
    reconcile_profile_fetch_plan,
)


def _load_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractViolation(f"cannot read offline discovery input: {path}") from exc
    if not isinstance(payload, dict):
        raise ContractViolation(f"offline discovery input must be an object: {path}")
    return payload


def _profile_outcomes(
    fixture: dict[str, Any] | None,
    planned_ids: set[str],
) -> tuple[ProfileFetchOutcome, ...]:
    if fixture is None or "profile_contents" not in fixture:
        return ()
    raw_contents = fixture.get("profile_contents")
    if not isinstance(raw_contents, list):
        raise ContractViolation("fixture profile_contents must be a list")
    outcomes: list[ProfileFetchOutcome] = []
    for index, item in enumerate(raw_contents):
        if not isinstance(item, dict):
            raise ContractViolation(f"profile_contents[{index}] must be an object")
        author_id = item.get("author_id")
        if not isinstance(author_id, str) or author_id not in planned_ids:
            raise ContractViolation(
                f"profile_contents[{index}] author_id is not in the Profile plan"
            )
        payload = item.get("payload", item.get("response"))
        if not isinstance(payload, dict):
            outcomes.append(
                ProfileFetchOutcome(author_id, "FAILED", 0, "missing fixture payload")
            )
            continue
        try:
            posts = parse_profile_content_response(payload, author_id=author_id)
        except ContractViolation as exc:
            outcomes.append(ProfileFetchOutcome(author_id, "FAILED", 0, str(exc)))
            continue
        status = "COMPLETE" if posts else "EMPTY"
        outcomes.append(ProfileFetchOutcome(author_id, status, len(posts)))
    return tuple(outcomes)


def discover_from_inputs(
    *,
    evidence_path: Path | None,
    fixture_path: Path | None,
) -> dict[str, Any]:
    """Return a deterministic discovery document from local evidence only."""

    evidence = (
        load_seed_profile_evidence(evidence_path)
        if evidence_path is not None
        else None
    )
    fixture = _load_object(fixture_path) if fixture_path is not None else None
    plan = plan_profile_fetches(evidence.profiles if evidence is not None else None)
    outcomes = _profile_outcomes(
        fixture, {target.author_id for target in plan.targets}
    )
    profile_coverage = reconcile_profile_fetch_plan(plan, outcomes)
    leaderboards = parse_30d_leaderboards(fixture) if fixture is not None else ()
    leaderboard_coverage = assess_leaderboard_coverage(
        leaderboards,
        seed_count=len(evidence.profiles) if evidence is not None else 0,
    )
    profile_plan = asdict(plan)
    profile_plan["target_count"] = len(plan.targets)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_system": "binance_square_author_discovery_offline_v1",
        "network_access": False,
        "credential_access": False,
        "inputs": {
            "evidence": str(evidence_path) if evidence_path is not None else None,
            "fixture": str(fixture_path) if fixture_path is not None else None,
        },
        "profile_plan": profile_plan,
        "profile_coverage": asdict(profile_coverage),
        "leaderboards": [asdict(result) for result in leaderboards],
        "leaderboard_coverage": asdict(leaderboard_coverage),
    }


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, help="profile-seed evidence JSON")
    parser.add_argument("--fixture", type=Path, help="offline discovery fixture JSON")
    parser.add_argument("--output", type=Path, help="optional new JSON output file")
    args = parser.parse_args(argv)
    if args.evidence is None and args.fixture is None:
        parser.error("choose --evidence, --fixture, or both")
    return args


def main(argv: list[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        payload = discover_from_inputs(
            evidence_path=args.evidence,
            fixture_path=args.fixture,
        )
    except ContractViolation as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    document = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(document)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(document)
        except FileExistsError:
            print(
                json.dumps(
                    {"error": f"output already exists: {args.output}"},
                    ensure_ascii=False,
                ),
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
