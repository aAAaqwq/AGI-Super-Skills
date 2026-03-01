"""Tests for promoted config loading and fallback logic.

Covers:
- _find_latest_promoted_config: scanning artifacts tree for promoted YAMLs
- load_promoted_config: deep-merge promoted on top of base
- maybe_apply_promoted_config: env-var integration and AI_QUANT_STRATEGY_YAML wiring
- Fallback behavior when no promoted config exists
- Role validation
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from engine.promoted_config import (
    VALID_ROLES,
    _find_latest_promoted_config,
    _write_text_atomic,
    load_promoted_config,
    maybe_apply_promoted_config,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_artifacts_tree(
    tmp_path: Path,
    *,
    runs: list[tuple[str, str, list[str]]] | None = None,
) -> Path:
    """Build a mock artifacts tree.

    Parameters
    ----------
    runs:
        List of (date, run_id, roles) tuples.
        e.g. [("2026-02-13", "nightly_20260213T010000Z", ["primary", "fallback"])]
    """
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    for date_str, run_id, roles in (runs or []):
        run_dir = artifacts / date_str / f"run_{run_id}"
        promoted = run_dir / "promoted_configs"
        promoted.mkdir(parents=True)
        for role in roles:
            cfg = {
                "global": {
                    "trade": {"allocation_pct": 0.05, "sl_atr_mult": 2.5},
                    "engine": {"interval": "30m"},
                },
                "_promoted_meta": {"role": role, "run_id": run_id},
            }
            (promoted / f"{role}.yaml").write_text(
                yaml.dump(cfg, default_flow_style=False), encoding="utf-8"
            )
    return artifacts


def _make_base_config(tmp_path: Path) -> Path:
    """Write a minimal base strategy_overrides.yaml."""
    base = tmp_path / "config" / "strategy_overrides.yaml"
    base.parent.mkdir(parents=True, exist_ok=True)
    cfg = {
        "global": {
            "trade": {"allocation_pct": 0.03, "leverage": 3.0, "sl_atr_mult": 2.0},
            "indicators": {"adx_window": 14},
            "engine": {"interval": "1h", "loop_target_s": 60},
        },
        "modes": {
            "primary": {"global": {"engine": {"interval": "30m"}}},
        },
        "symbols": {},
    }
    base.write_text(yaml.dump(cfg, default_flow_style=False), encoding="utf-8")
    return base


# ---------------------------------------------------------------------------
# _find_latest_promoted_config
# ---------------------------------------------------------------------------


class TestFindLatestPromotedConfig:
    def test_finds_most_recent_run(self, tmp_path: Path) -> None:
        """Should return the promoted config from the most recent run directory."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-12", "nightly_20260212T010000Z", ["primary"]),
            ("2026-02-13", "nightly_20260213T010000Z", ["primary"]),
            ("2026-02-14", "nightly_20260214T010000Z", ["primary"]),
        ])

        result = _find_latest_promoted_config(artifacts, "primary")

        assert result is not None
        assert "2026-02-14" in str(result)
        assert result.name == "primary.yaml"
        assert result.is_file()

    def test_finds_correct_role(self, tmp_path: Path) -> None:
        """Should return the config for the requested role only."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-14", "nightly_20260214T010000Z", ["primary", "fallback", "conservative"]),
        ])

        for role in VALID_ROLES:
            result = _find_latest_promoted_config(artifacts, role)
            assert result is not None
            assert result.name == f"{role}.yaml"

    def test_returns_none_for_missing_role(self, tmp_path: Path) -> None:
        """Should return None if the role YAML doesn't exist."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-14", "nightly_20260214T010000Z", ["primary"]),
        ])

        result = _find_latest_promoted_config(artifacts, "conservative")
        assert result is None

    def test_returns_none_for_invalid_role(self, tmp_path: Path) -> None:
        """Should return None for roles not in VALID_ROLES."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-14", "nightly_20260214T010000Z", ["primary"]),
        ])

        assert _find_latest_promoted_config(artifacts, "invalid") is None
        assert _find_latest_promoted_config(artifacts, "") is None

    def test_returns_none_for_empty_artifacts(self, tmp_path: Path) -> None:
        """Should return None when artifacts dir is empty."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()

        assert _find_latest_promoted_config(artifacts, "primary") is None

    def test_returns_none_for_nonexistent_dir(self, tmp_path: Path) -> None:
        """Should return None when artifacts dir doesn't exist."""
        assert _find_latest_promoted_config(tmp_path / "nope", "primary") is None

    def test_skips_runs_without_promoted_configs(self, tmp_path: Path) -> None:
        """Should skip run directories that lack promoted_configs/ dir."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-12", "nightly_20260212T010000Z", ["primary"]),
        ])
        # Create a more recent run WITHOUT promoted_configs
        newer_run = artifacts / "2026-02-14" / "run_nightly_20260214T010000Z"
        newer_run.mkdir(parents=True)
        # (no promoted_configs subdir)

        result = _find_latest_promoted_config(artifacts, "primary")
        assert result is not None
        assert "2026-02-12" in str(result)

    def test_handles_multiple_runs_same_day(self, tmp_path: Path) -> None:
        """Should pick the latest run within the same date directory."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-14", "nightly_20260214T010000Z", ["primary"]),
            ("2026-02-14", "nightly_20260214T230000Z", ["primary"]),
        ])

        result = _find_latest_promoted_config(artifacts, "primary")
        assert result is not None
        assert "20260214T230000Z" in str(result)

    def test_date_scan_limit_preserves_backwards_compatible_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If bounded scan misses, fallback full scan should still find older configs."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-13", "nightly_20260213T010000Z", ["primary"]),
        ])
        # Newest date has no promoted_configs payload.
        (artifacts / "2026-02-14" / "run_nightly_20260214T010000Z").mkdir(parents=True)

        monkeypatch.setenv("AI_QUANT_PROMOTED_SCAN_DATE_DIRS", "1")
        result = _find_latest_promoted_config(artifacts, "primary")
        assert result is not None
        assert "2026-02-13" in str(result)

    def test_run_scan_limit_preserves_backwards_compatible_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If bounded per-date run scan misses, fallback full scan should still find config."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-14", "nightly_20260214T010000Z", ["primary"]),
        ])
        # Create a lexicographically newer run without promoted configs.
        (artifacts / "2026-02-14" / "run_nightly_20260214T230000Z").mkdir(parents=True)

        monkeypatch.setenv("AI_QUANT_PROMOTED_SCAN_RUN_DIRS_PER_DATE", "1")
        result = _find_latest_promoted_config(artifacts, "primary")
        assert result is not None
        assert "20260214T010000Z" in str(result)

    def test_ignores_non_date_directories(self, tmp_path: Path) -> None:
        """Should ignore directories that don't match YYYY-MM-DD pattern."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-14", "nightly_20260214T010000Z", ["primary"]),
        ])
        # Create non-date dirs
        (artifacts / "_effective_configs").mkdir(exist_ok=True)
        (artifacts / "registry").mkdir(exist_ok=True)
        (artifacts / "events").mkdir(exist_ok=True)

        result = _find_latest_promoted_config(artifacts, "primary")
        assert result is not None
        assert "2026-02-14" in str(result)


# ---------------------------------------------------------------------------
# load_promoted_config
# ---------------------------------------------------------------------------


class TestLoadPromotedConfig:
    def test_merges_promoted_on_top_of_base(self, tmp_path: Path) -> None:
        """Promoted config values should override base, base fills gaps."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-14", "nightly_20260214T010000Z", ["primary"]),
        ])
        base = _make_base_config(tmp_path)

        merged, path = load_promoted_config(
            "primary",
            artifacts_dir=artifacts,
            base_yaml_path=base,
        )

        assert merged is not None
        assert path is not None

        trade = merged["global"]["trade"]
        # Promoted overrides:
        assert trade["allocation_pct"] == 0.05
        assert trade["sl_atr_mult"] == 2.5
        # Base value preserved where promoted doesn't specify:
        assert trade["leverage"] == 3.0

    def test_preserves_base_sections_not_in_promoted(self, tmp_path: Path) -> None:
        """Sections only in base should survive the merge."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-14", "nightly_20260214T010000Z", ["primary"]),
        ])
        base = _make_base_config(tmp_path)

        merged, _ = load_promoted_config(
            "primary",
            artifacts_dir=artifacts,
            base_yaml_path=base,
        )

        assert merged is not None
        # indicators section is only in base
        assert merged["global"]["indicators"]["adx_window"] == 14
        # modes section is only in base
        assert "modes" in merged

    def test_returns_none_for_missing_promoted(self, tmp_path: Path) -> None:
        """Should return (None, None) when no promoted config exists."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        base = _make_base_config(tmp_path)

        merged, path = load_promoted_config(
            "primary",
            artifacts_dir=artifacts,
            base_yaml_path=base,
        )

        assert merged is None
        assert path is None

    def test_returns_none_for_invalid_role(self, tmp_path: Path) -> None:
        """Should return (None, None) for invalid role names."""
        merged, path = load_promoted_config(
            "bogus",
            artifacts_dir=tmp_path,
            base_yaml_path=tmp_path / "nope.yaml",
        )
        assert merged is None
        assert path is None

    def test_handles_empty_promoted_file(self, tmp_path: Path) -> None:
        """Should fall back when promoted YAML is empty."""
        artifacts = tmp_path / "artifacts"
        date_dir = artifacts / "2026-02-14" / "run_nightly_20260214T010000Z" / "promoted_configs"
        date_dir.mkdir(parents=True)
        (date_dir / "primary.yaml").write_text("", encoding="utf-8")
        base = _make_base_config(tmp_path)

        merged, path = load_promoted_config(
            "primary",
            artifacts_dir=artifacts,
            base_yaml_path=base,
        )

        assert merged is None
        assert path is None

    def test_all_three_roles(self, tmp_path: Path) -> None:
        """All three roles should be loadable independently."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-14", "nightly_20260214T010000Z", ["primary", "fallback", "conservative"]),
        ])
        base = _make_base_config(tmp_path)

        for role in ("primary", "fallback", "conservative"):
            merged, path = load_promoted_config(
                role,
                artifacts_dir=artifacts,
                base_yaml_path=base,
            )
            assert merged is not None, f"Failed for role={role}"
            assert path is not None
            # Each promoted YAML includes _promoted_meta.role
            assert merged.get("_promoted_meta", {}).get("role") == role


# ---------------------------------------------------------------------------
# maybe_apply_promoted_config
# ---------------------------------------------------------------------------


class TestMaybeApplyPromotedConfig:
    def test_no_op_when_env_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return None and not touch AI_QUANT_STRATEGY_YAML."""
        monkeypatch.delenv("AI_QUANT_PROMOTED_ROLE", raising=False)
        monkeypatch.delenv("AI_QUANT_STRATEGY_YAML", raising=False)

        result = maybe_apply_promoted_config()

        assert result is None

    def test_applies_promoted_role(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should set AI_QUANT_STRATEGY_YAML to merged config when role is valid."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-14", "nightly_20260214T010000Z", ["primary"]),
        ])
        base = _make_base_config(tmp_path)

        monkeypatch.setenv("AI_QUANT_PROMOTED_ROLE", "primary")
        monkeypatch.setenv("AI_QUANT_ARTIFACTS_DIR", str(artifacts))
        monkeypatch.setenv("AI_QUANT_STRATEGY_YAML", str(base))

        result = maybe_apply_promoted_config()

        assert result == "primary"
        # AI_QUANT_STRATEGY_YAML should now point at the merged file
        yaml_path = os.environ.get("AI_QUANT_STRATEGY_YAML", "")
        assert "_promoted_primary" in yaml_path
        assert Path(yaml_path).is_file()

        # Verify merged content
        with open(yaml_path, "r") as f:
            content = yaml.safe_load(f)
        assert content["global"]["trade"]["allocation_pct"] == 0.05
        assert content["global"]["trade"]["leverage"] == 3.0

    def test_fallback_when_no_promoted_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return None when promoted config doesn't exist."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        base = _make_base_config(tmp_path)

        monkeypatch.setenv("AI_QUANT_PROMOTED_ROLE", "primary")
        monkeypatch.setenv("AI_QUANT_ARTIFACTS_DIR", str(artifacts))
        monkeypatch.setenv("AI_QUANT_STRATEGY_YAML", str(base))

        # Record original value to confirm it's NOT changed
        orig_yaml = str(base)

        result = maybe_apply_promoted_config()

        assert result is None
        # AI_QUANT_STRATEGY_YAML should remain unchanged (still points to base)
        assert os.environ.get("AI_QUANT_STRATEGY_YAML") == orig_yaml

    def test_role_case_insensitive(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Role should be normalised to lowercase."""
        artifacts = _make_artifacts_tree(tmp_path, runs=[
            ("2026-02-14", "nightly_20260214T010000Z", ["fallback"]),
        ])
        base = _make_base_config(tmp_path)

        monkeypatch.setenv("AI_QUANT_PROMOTED_ROLE", "FALLBACK")
        monkeypatch.setenv("AI_QUANT_ARTIFACTS_DIR", str(artifacts))
        monkeypatch.setenv("AI_QUANT_STRATEGY_YAML", str(base))

        result = maybe_apply_promoted_config()
        assert result == "fallback"


# ---------------------------------------------------------------------------
# Role-to-daemon mapping documentation
# ---------------------------------------------------------------------------


class TestRoleDaemonMapping:
    """Verify the documented role-to-daemon mapping constants."""

    def test_valid_roles_complete(self) -> None:
        assert VALID_ROLES == {"primary", "fallback", "conservative"}

    def test_paper_daemon_role_mapping(self) -> None:
        """Document the expected env var values for each paper daemon."""
        mapping = {
            "paper1": "primary",
            "paper2": "fallback",
            "paper3": "conservative",
        }
        for daemon, role in mapping.items():
            assert role in VALID_ROLES, f"{daemon} → {role} not in VALID_ROLES"


class TestAtomicWrite:
    def test_write_text_atomic_replaces_target(self, tmp_path: Path) -> None:
        target = tmp_path / "out.yaml"
        _write_text_atomic(target, "first: 1\n")
        _write_text_atomic(target, "second: 2\n")

        assert target.read_text(encoding="utf-8") == "second: 2\n"
        leftovers = list(tmp_path.glob(".out.yaml.*.tmp"))
        assert leftovers == []

    def test_write_text_atomic_cleans_temp_on_replace_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        target = tmp_path / "out.yaml"

        def _boom_replace(_src, _dst):  # noqa: ANN001
            raise OSError("replace failed")

        monkeypatch.setattr("engine.promoted_config.os.replace", _boom_replace)

        with pytest.raises(OSError, match="replace failed"):
            _write_text_atomic(target, "broken: true\n")

        leftovers = list(tmp_path.glob(".out.yaml.*.tmp"))
        assert leftovers == []
