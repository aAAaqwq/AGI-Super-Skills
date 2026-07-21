#!/usr/bin/env python3
"""Preview or install the AGI Super Team Codex agent payload safely."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import datetime as dt
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
import tomllib
from typing import Iterator


PLUGIN_ROOT = Path(__file__).resolve().parents[3]
PAYLOAD_DIR = PLUGIN_ROOT / "payload" / "agents"
LOCK_NAME = ".agi-super-team-sync.lock"


def default_codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".codex"


def validate_codex_home(path: Path) -> Path:
    expanded = path.expanduser()
    if expanded.is_symlink():
        raise ValueError(f"refusing symlinked Codex home: {expanded}")
    resolved = expanded.resolve()
    forbidden = {Path("/").resolve(), Path.home().resolve()}
    if resolved in forbidden:
        raise ValueError(f"refusing unsafe Codex home: {resolved}")
    return resolved


def verify_directory_chain(codex_home: Path, directory: Path) -> None:
    try:
        relative = directory.relative_to(codex_home)
    except ValueError as error:
        raise ValueError(f"directory escapes Codex home: {directory}") from error

    try:
        root_metadata = codex_home.lstat()
    except FileNotFoundError:
        root_metadata = None
    if root_metadata and (stat.S_ISLNK(root_metadata.st_mode) or not stat.S_ISDIR(root_metadata.st_mode)):
        raise ValueError(f"invalid Codex home directory: {codex_home}")

    current = codex_home
    for component in relative.parts:
        current = current / component
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            break
        if stat.S_ISLNK(metadata.st_mode):
            raise ValueError(f"refusing symlinked directory component: {current}")
        if not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"expected directory component: {current}")


def load_payload() -> list[Path]:
    if not PAYLOAD_DIR.is_dir() or PAYLOAD_DIR.is_symlink():
        raise ValueError(f"invalid payload directory: {PAYLOAD_DIR}")
    entries = sorted(PAYLOAD_DIR.iterdir())
    invalid = [path.name for path in entries if path.is_symlink() or not path.is_file() or path.suffix != ".toml"]
    if invalid:
        raise ValueError(f"invalid payload entries: {', '.join(invalid)}")
    if not entries:
        raise ValueError("agent payload is empty")
    for path in entries:
        try:
            agent = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise ValueError(f"invalid agent TOML {path.name}: {error}") from error
        if agent.get("name") != path.stem:
            raise ValueError(f"agent name does not match filename: {path.name}")
        if agent.get("sandbox_mode") not in {"read-only", "workspace-write"}:
            raise ValueError(f"unsupported sandbox mode in {path.name}")
    return entries


def read_regular_file(path: Path, codex_home: Path) -> bytes | None:
    verify_directory_chain(codex_home, path.parent)
    try:
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return None
    try:
        try:
            file_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise ValueError(f"refusing unsafe destination: {path}: {error}") from error
        with os.fdopen(file_fd, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise ValueError(f"refusing non-file destination: {path}")
            return handle.read()
    finally:
        os.close(directory_fd)


def atomic_write(content: bytes, destination: Path, codex_home: Path) -> None:
    verify_directory_chain(codex_home, destination.parent)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    verify_directory_chain(codex_home, destination.parent)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        verify_directory_chain(codex_home, destination.parent)
        directory_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            try:
                metadata = os.stat(destination.name, dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError:
                metadata = None
            if metadata and stat.S_ISLNK(metadata.st_mode):
                raise ValueError(f"refusing symlinked destination: {destination}")
            os.replace(temporary.name, destination.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def unlink_if_unchanged(destination: Path, expected: bytes, codex_home: Path) -> None:
    if read_regular_file(destination, codex_home) != expected:
        raise ValueError(f"refusing to remove concurrently changed file: {destination}")
    verify_directory_chain(codex_home, destination.parent)
    directory_fd = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.unlink(destination.name, dir_fd=directory_fd)
    finally:
        os.close(directory_fd)


@contextmanager
def install_lock(target_dir: Path, codex_home: Path) -> Iterator[None]:
    verify_directory_chain(codex_home, target_dir)
    directory_fd = os.open(target_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    lock_fd: int | None = None
    try:
        try:
            lock_fd = os.open(
                LOCK_NAME,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory_fd,
            )
        except FileExistsError as error:
            raise ValueError(f"another AGI Super Team sync is active: {target_dir / LOCK_NAME}") from error
        yield
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
            try:
                os.unlink(LOCK_NAME, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
        os.close(directory_fd)


def build_plan(payload: list[Path], target_dir: Path, codex_home: Path) -> list[tuple[Path, Path, str, bytes | None, bytes]]:
    plan = []
    for source in payload:
        source_content = source.read_bytes()
        destination = target_dir / source.name
        baseline = read_regular_file(destination, codex_home)
        if baseline is None:
            status = "add"
        elif baseline == source_content:
            status = "unchanged"
        else:
            status = "update"
        plan.append((source, destination, status, baseline, source_content))
    return plan


def apply_plan(
    codex_home: Path,
    plan: list[tuple[Path, Path, str, bytes | None, bytes]],
    update_count: int,
) -> Path | None:
    backup_base = codex_home / "backups" / "agi-super-team"
    verify_directory_chain(codex_home, backup_base)
    backup_base.mkdir(parents=True, exist_ok=True, mode=0o700)
    verify_directory_chain(codex_home, backup_base)
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    transaction = Path(tempfile.mkdtemp(prefix=f"{timestamp}-", dir=backup_base))
    backup_dir = transaction / "agents"
    stage_dir = transaction / "stage"
    backup_dir.mkdir(mode=0o700)
    stage_dir.mkdir(mode=0o700)

    actionable = [entry for entry in plan if entry[2] != "unchanged"]
    for source, destination, status, baseline, source_content in actionable:
        if read_regular_file(destination, codex_home) != baseline:
            raise ValueError(f"destination changed before backup: {destination}")
        atomic_write(source_content, stage_dir / source.name, codex_home)
        if status == "update" and baseline is not None:
            atomic_write(baseline, backup_dir / destination.name, codex_home)

    changed: list[tuple[Path, str, bytes | None, bytes]] = []
    try:
        for source, destination, status, baseline, source_content in actionable:
            if read_regular_file(destination, codex_home) != baseline:
                raise ValueError(f"destination changed after preview: {destination}")
            atomic_write(source_content, destination, codex_home)
            changed.append((destination, status, baseline, source_content))
    except (OSError, ValueError) as install_error:
        rollback_errors = []
        for destination, status, baseline, installed_content in reversed(changed):
            try:
                if read_regular_file(destination, codex_home) != installed_content:
                    raise ValueError(f"destination changed during rollback: {destination}")
                if status == "update" and baseline is not None:
                    atomic_write(baseline, destination, codex_home)
                else:
                    unlink_if_unchanged(destination, installed_content, codex_home)
            except (OSError, ValueError) as rollback_error:
                rollback_errors.append(f"{destination.name}: {rollback_error}")
        detail = f"; rollback failures: {', '.join(rollback_errors)}" if rollback_errors else "; changes rolled back"
        raise ValueError(f"agent sync failed: {install_error}{detail}") from install_error

    shutil.rmtree(stage_dir)
    if not update_count:
        backup_dir.rmdir()
        transaction.rmdir()
        return None
    return transaction


def sync(codex_home: Path, install: bool) -> int:
    target_dir = codex_home / "agents"
    verify_directory_chain(codex_home, target_dir)
    payload = load_payload()
    plan = build_plan(payload, target_dir, codex_home)
    counts = {status: sum(1 for _, _, current, _, _ in plan if current == status) for status in ("add", "update", "unchanged")}

    mode = "INSTALL" if install else "PREVIEW"
    print(f"AGI Super Team agent sync — {mode}")
    print(f"source: {PAYLOAD_DIR}")
    print(f"target: {target_dir}")
    print(f"add={counts['add']} update={counts['update']} unchanged={counts['unchanged']}")
    for _, destination, status, _, _ in plan:
        if status != "unchanged":
            print(f"  {status:6} {destination.name}")

    if not install:
        print("No files changed. Re-run with --install to apply this plan.")
        return 0

    target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    verify_directory_chain(codex_home, target_dir)
    with install_lock(target_dir, codex_home):
        backup = apply_plan(codex_home, plan, counts["update"])

    if backup:
        print(f"backup: {backup}")
    print("Sync complete. Start a new Codex task to discover the installed agents.")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true", help="apply the previewed changes")
    parser.add_argument("--codex-home", type=Path, default=default_codex_home(), help="destination Codex home")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return sync(validate_codex_home(args.codex_home), args.install)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
