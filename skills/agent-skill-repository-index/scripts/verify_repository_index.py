#!/usr/bin/env python3
"""Verify repository-index links, local clone identities, and optional remotes."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path


ROW_PATTERN = re.compile(
    r"^\| \[([^]]+)\]\((https://github\.com/[^)]+)\) \| `([^`]+)` \|"
)


@dataclass(frozen=True)
class Repository:
    slug: str
    url: str
    local: str


def parse_index(reference: Path) -> list[Repository]:
    repositories: list[Repository] = []
    for line in reference.read_text(encoding="utf-8").splitlines():
        match = ROW_PATTERN.match(line)
        if match:
            repositories.append(Repository(*match.groups()))
    return repositories


def github_slug(value: str) -> str | None:
    match = re.search(r"github\.com[/:]([^/]+/[^/]+?)(?:\.git)?$", value)
    return match.group(1).lower() if match else None


def git_output(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()


def check_local(repository: Repository, root: Path) -> str | None:
    clone = root / repository.local
    if not (clone / ".git").exists():
        return f"missing clone: {clone}"
    try:
        remote = git_output("-C", str(clone), "remote", "get-url", "origin")
    except (subprocess.SubprocessError, OSError) as error:
        return f"cannot read origin: {error}"
    expected = repository.slug.lower()
    actual = github_slug(remote)
    if actual != expected:
        return f"origin mismatch: expected {expected}, got {remote}"
    return None


def check_remote(repository: Repository) -> str | None:
    try:
        subprocess.run(
            ["git", "ls-remote", "--exit-code", repository.url, "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except (subprocess.SubprocessError, OSError) as error:
        return f"remote unreachable: {error}"
    return None


def main() -> int:
    skill_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference",
        type=Path,
        default=skill_root / "references" / "repositories.md",
    )
    parser.add_argument("--repo-root", type=Path)
    parser.add_argument("--remote", action="store_true")
    parser.add_argument("--expected-count", type=int)
    args = parser.parse_args()

    repositories = parse_index(args.reference)
    errors: list[str] = []
    if args.expected_count is not None and len(repositories) != args.expected_count:
        errors.append(
            f"entry count mismatch: expected {args.expected_count}, got {len(repositories)}"
        )
    if len({item.slug.lower() for item in repositories}) != len(repositories):
        errors.append("duplicate repository slug")
    if len({item.local for item in repositories}) != len(repositories):
        errors.append("duplicate local directory")
    for repository in repositories:
        if github_slug(repository.url) != repository.slug.lower():
            errors.append(
                f"label/url mismatch: {repository.slug} points to {repository.url}"
            )

    if args.repo_root:
        for repository in repositories:
            if error := check_local(repository, args.repo_root):
                errors.append(f"{repository.slug}: {error}")

    if args.remote:
        with ThreadPoolExecutor(max_workers=6) as executor:
            results = executor.map(check_remote, repositories)
        for repository, error in zip(repositories, results, strict=True):
            if error:
                errors.append(f"{repository.slug}: {error}")

    for error in errors:
        print(f"FAIL {error}")
    if errors:
        return 1
    checks = [f"{len(repositories)} entries"]
    if args.repo_root:
        checks.append("local identities")
    if args.remote:
        checks.append("GitHub remotes")
    print("PASS " + ", ".join(checks))
    return 0


if __name__ == "__main__":
    sys.exit(main())
