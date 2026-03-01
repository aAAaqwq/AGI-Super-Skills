from __future__ import annotations

from factory_run import resolve_run_dir


def test_resolve_run_dir_uses_utc_date_subdir(tmp_path) -> None:
    # 0 ms since epoch -> 1970-01-01 UTC
    p = resolve_run_dir(artifacts_root=tmp_path, run_id="abc123", generated_at_ms=0)
    assert p == (tmp_path / "1970-01-01" / "run_abc123").resolve()

