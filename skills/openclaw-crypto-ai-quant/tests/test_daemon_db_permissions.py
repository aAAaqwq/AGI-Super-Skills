from __future__ import annotations

import os
import stat
from pathlib import Path

import engine.daemon as daemon


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_harden_db_permissions_sets_mode_600(tmp_path: Path) -> None:
    root_db = tmp_path / "root.db"
    root_wal = tmp_path / "root.db-wal"
    root_shm = tmp_path / "root.db-shm"
    root_journal = tmp_path / "root.db-journal"
    nested_db = tmp_path / "nested" / "extra.db"
    nested_wal = tmp_path / "nested" / "extra.db-wal"
    nested_shm = tmp_path / "nested" / "extra.db-shm"
    nested_journal = tmp_path / "nested" / "extra.db-journal"
    nested_db.parent.mkdir(parents=True, exist_ok=True)
    root_db.write_text("", encoding="utf-8")
    root_wal.write_text("", encoding="utf-8")
    root_shm.write_text("", encoding="utf-8")
    root_journal.write_text("", encoding="utf-8")
    nested_db.write_text("", encoding="utf-8")
    nested_wal.write_text("", encoding="utf-8")
    nested_shm.write_text("", encoding="utf-8")
    nested_journal.write_text("", encoding="utf-8")

    os.chmod(root_db, 0o644)
    os.chmod(root_wal, 0o644)
    os.chmod(root_shm, 0o644)
    os.chmod(root_journal, 0o644)
    os.chmod(nested_db, 0o644)
    os.chmod(nested_wal, 0o644)
    os.chmod(nested_shm, 0o644)
    os.chmod(nested_journal, 0o644)

    daemon._harden_db_permissions(str(nested_db), project_root=tmp_path)

    assert _mode(root_db) == 0o600
    assert _mode(root_wal) == 0o600
    assert _mode(root_shm) == 0o600
    assert _mode(root_journal) == 0o600
    assert _mode(nested_db) == 0o600
    assert _mode(nested_wal) == 0o600
    assert _mode(nested_shm) == 0o600
    assert _mode(nested_journal) == 0o600


def test_harden_db_permissions_ignores_missing_paths(tmp_path: Path) -> None:
    daemon._harden_db_permissions(str(tmp_path / "missing.db"), project_root=tmp_path)


def test_harden_db_permissions_ignores_chmod_oserror(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "blocked.db"
    db_path.write_text("", encoding="utf-8")

    def _raise_oserror(_path: str, _mode: int) -> None:
        raise PermissionError("blocked")

    monkeypatch.setattr(daemon.os, "chmod", _raise_oserror)

    daemon._harden_db_permissions(str(db_path), project_root=tmp_path)
