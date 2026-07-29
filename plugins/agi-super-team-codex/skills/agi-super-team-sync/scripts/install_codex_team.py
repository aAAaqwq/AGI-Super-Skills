#!/usr/bin/env python3
"""Preview or install the AGI Super Team global CEO and outcome teams."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from sync_codex_agents import (
    atomic_write,
    default_codex_home,
    install_lock,
    read_regular_file,
    validate_codex_home,
    verify_directory_chain,
)


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
AGENT_PAYLOAD = PLUGIN_ROOT / "payload" / "agents"
GLOBAL_GUIDANCE = PLUGIN_ROOT / "payload" / "global" / "AGENTS.md"
TEAM_CONTRACTS = PLUGIN_ROOT / "skills" / "c-suite-team" / "references" / "team-contracts.json"
AGENT_HIERARCHY = PLUGIN_ROOT / "skills" / "c-suite-team" / "references" / "agent-hierarchy.json"
BEGIN_MARKER = "<!-- AGI-SUPER-TEAM:CEO:BEGIN -->"
END_MARKER = "<!-- AGI-SUPER-TEAM:CEO:END -->"


@dataclass(frozen=True)
class PlanItem:
    destination: Path
    baseline: bytes | None
    content: bytes
    label: str

    @property
    def status(self) -> str:
        if self.baseline is None:
            return "add"
        return "unchanged" if self.baseline == self.content else "update"


def load_contracts() -> dict:
    if TEAM_CONTRACTS.is_symlink() or not TEAM_CONTRACTS.is_file():
        raise ValueError(f"invalid team contracts: {TEAM_CONTRACTS}")
    contracts = json.loads(TEAM_CONTRACTS.read_text(encoding="utf-8"))
    teams = contracts.get("kits")
    agents = contracts.get("agents")
    if not isinstance(teams, list) or not isinstance(agents, list):
        raise ValueError("team contracts must contain agent and kit lists")
    return contracts


def load_hierarchy() -> dict:
    if AGENT_HIERARCHY.is_symlink() or not AGENT_HIERARCHY.is_file():
        raise ValueError(f"invalid Agent hierarchy: {AGENT_HIERARCHY}")
    hierarchy = json.loads(AGENT_HIERARCHY.read_text(encoding="utf-8"))
    if not isinstance(hierarchy.get("managers"), dict):
        raise ValueError("Agent hierarchy must contain managers")
    return hierarchy


def list_teams(contracts: dict) -> None:
    print("AGI Super Team outcome teams")
    for team in contracts["kits"]:
        members = ", ".join(team["agents"])
        print(f"  {team['id']:<20} {team['name']} — {members}")


def selected_agent_names(
    contracts: dict,
    team_ids: list[str],
    all_teams: bool,
    subagent_managers: list[str] | None = None,
    with_cco_specialists: bool = False,
) -> list[str]:
    teams = {team["id"]: team for team in contracts["kits"]}
    unknown = sorted(set(team_ids) - set(teams))
    if unknown:
        raise ValueError(f"unknown team: {', '.join(unknown)}")
    selected = list(teams) if all_teams else team_ids
    roles = {
        role
        for team_id in selected
        for role in teams[team_id]["agents"]
        if role != "ceo"
    }
    names = sorted(f"ast-{role}" for role in roles)
    requested_managers = set(subagent_managers or [])
    if with_cco_specialists:
        requested_managers.add("cco")
    if requested_managers:
        hierarchy = load_hierarchy()
        managers = hierarchy.get("managers", {})
        unknown_managers = sorted(requested_managers - set(managers))
        if unknown_managers:
            raise ValueError(f"unknown subagent group: {', '.join(unknown_managers)}")
        for manager in requested_managers:
            names.append(f"ast-{manager}")
            names.extend(f"ast-{role}" for role in managers[manager]["roleRefs"])
            names.extend(f"ast-{manager}-{role}" for role in managers[manager]["subagents"])
        names = sorted(set(names))
    missing = [name for name in names if not (AGENT_PAYLOAD / f"{name}.toml").is_file()]
    if missing:
        raise ValueError(f"team payload is incomplete: {', '.join(missing)}")
    return names


def render_global_guidance(existing: bytes | None) -> bytes:
    if GLOBAL_GUIDANCE.is_symlink() or not GLOBAL_GUIDANCE.is_file():
        raise ValueError(f"invalid global guidance payload: {GLOBAL_GUIDANCE}")
    managed = GLOBAL_GUIDANCE.read_text(encoding="utf-8").strip()
    if managed.count(BEGIN_MARKER) != 1 or managed.count(END_MARKER) != 1:
        raise ValueError("global guidance payload has invalid managed markers")
    if existing is None:
        return (managed + "\n").encode()
    try:
        current = existing.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("existing global AGENTS.md is not UTF-8") from error
    begin_count = current.count(BEGIN_MARKER)
    end_count = current.count(END_MARKER)
    if (begin_count, end_count) == (0, 0):
        prefix = current.rstrip()
        return ((prefix + "\n\n" if prefix else "") + managed + "\n").encode()
    if (begin_count, end_count) != (1, 1):
        raise ValueError("existing global AGENTS.md has malformed AGI Super Team markers")
    start = current.index(BEGIN_MARKER)
    finish = current.index(END_MARKER, start) + len(END_MARKER)
    if finish <= start:
        raise ValueError("existing global AGENTS.md has reversed AGI Super Team markers")
    return (current[:start] + managed + current[finish:]).encode()


def build_plan(
    codex_home: Path,
    contracts: dict,
    team_ids: list[str],
    all_teams: bool,
    global_ceo: bool,
    subagent_managers: list[str] | None = None,
    with_cco_specialists: bool = False,
) -> list[PlanItem]:
    plan: list[PlanItem] = []
    if global_ceo:
        destination = codex_home / "AGENTS.md"
        baseline = read_regular_file(destination, codex_home)
        plan.append(PlanItem(destination, baseline, render_global_guidance(baseline), "global-ceo"))
    for name in selected_agent_names(contracts, team_ids, all_teams, subagent_managers, with_cco_specialists):
        source = AGENT_PAYLOAD / f"{name}.toml"
        if source.is_symlink():
            raise ValueError(f"refusing symlinked agent payload: {source}")
        destination = codex_home / "agents" / source.name
        plan.append(PlanItem(destination, read_regular_file(destination, codex_home), source.read_bytes(), name))
    if not plan:
        raise ValueError("select --global-ceo, --team ID, or --all-teams")
    return plan


def apply_plan(codex_home: Path, plan: list[PlanItem]) -> Path | None:
    changed = [item for item in plan if item.status != "unchanged"]
    if not changed:
        return None
    backup_root = codex_home / "backups" / "agi-super-team"
    verify_directory_chain(codex_home, backup_root)
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    transaction = Path(tempfile.mkdtemp(prefix=f"{timestamp}-", dir=backup_root))
    written: list[PlanItem] = []
    try:
        for item in changed:
            if read_regular_file(item.destination, codex_home) != item.baseline:
                raise ValueError(f"destination changed after preview: {item.destination}")
            if item.baseline is not None:
                relative = item.destination.relative_to(codex_home)
                backup = transaction / relative
                backup.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                atomic_write(item.baseline, backup, codex_home)
            atomic_write(item.content, item.destination, codex_home)
            written.append(item)
    except (OSError, ValueError) as install_error:
        rollback_errors: list[str] = []
        for item in reversed(written):
            try:
                if read_regular_file(item.destination, codex_home) != item.content:
                    raise ValueError("destination changed during rollback")
                if item.baseline is None:
                    item.destination.unlink()
                else:
                    atomic_write(item.baseline, item.destination, codex_home)
            except (OSError, ValueError) as rollback_error:
                rollback_errors.append(f"{item.destination}: {rollback_error}")
        detail = f"; rollback failures: {', '.join(rollback_errors)}" if rollback_errors else "; changes rolled back"
        raise ValueError(f"installation failed: {install_error}{detail}") from install_error
    if not any(item.baseline is not None for item in changed):
        shutil.rmtree(transaction)
        return None
    return transaction


def run(args: argparse.Namespace) -> int:
    contracts = load_contracts()
    if args.list_teams:
        list_teams(contracts)
        return 0
    codex_home = validate_codex_home(args.codex_home)
    plan = build_plan(
        codex_home,
        contracts,
        args.team,
        args.all_teams,
        args.global_ceo,
        [
            *args.with_subagents,
            *(list(load_hierarchy()["managers"]) if args.all_subagents else []),
        ],
        args.with_cco_specialists,
    )
    counts = {status: sum(item.status == status for item in plan) for status in ("add", "update", "unchanged")}
    print(f"AGI Super Team Codex injection — {'INSTALL' if args.install else 'PREVIEW'}")
    print(f"target: {codex_home}")
    print(f"add={counts['add']} update={counts['update']} unchanged={counts['unchanged']}")
    for item in plan:
        if item.status != "unchanged":
            print(f"  {item.status:6} {item.label:<20} {item.destination}")
    override = codex_home / "AGENTS.override.md"
    if args.global_ceo and override.is_file() and override.stat().st_size:
        print("warning: non-empty AGENTS.override.md takes precedence over AGENTS.md")
    if not args.install:
        print("No files changed. Re-run with --install to apply this plan.")
        return 0
    (codex_home / "agents").mkdir(parents=True, exist_ok=True, mode=0o700)
    with install_lock(codex_home / "agents", codex_home):
        backup = apply_plan(codex_home, plan)
    if backup:
        print(f"backup: {backup}")
    print("Injection complete. Start a new Codex task to load global guidance and agents.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-teams", action="store_true", help="list packaged outcome teams")
    parser.add_argument("--global-ceo", action="store_true", help="inject or update the managed CEO block in AGENTS.md")
    parser.add_argument("--team", action="append", default=[], metavar="ID", help="install one team; repeat for multiple teams")
    parser.add_argument("--all-teams", action="store_true", help="install the union of all packaged C-suite teams")
    parser.add_argument("--with-cco-specialists", action="store_true", help="also install the 19 CCO-routed content and growth leaves")
    parser.add_argument("--with-subagents", action="append", default=[], metavar="ID", help="install one executive subagent group; repeatable")
    parser.add_argument("--all-subagents", action="store_true", help="install all 92 executive specialist leaves")
    parser.add_argument("--install", action="store_true", help="apply the previewed plan")
    parser.add_argument("--codex-home", type=Path, default=default_codex_home(), help="destination Codex home")
    return parser.parse_args()


def main() -> int:
    try:
        return run(parse_args())
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
