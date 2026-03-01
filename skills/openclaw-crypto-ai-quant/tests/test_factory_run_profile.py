from __future__ import annotations

from factory_run import PROFILE_DEFAULTS, _parse_cli_args, _resolve_profile_requires_live_initial_balance


def test_profile_smoke_sets_trials_and_candidate_counts() -> None:
    args = _parse_cli_args(["--run-id", "x", "--profile", "smoke"])
    assert args.tpe_trials == 2000
    assert args.shortlist_per_mode == 3
    assert args.shortlist_max_rank == 20
    assert args.num_candidates == 2


def test_profile_daily_sets_updated_values() -> None:
    args = _parse_cli_args(["--run-id", "x", "--profile", "daily"])
    assert args.tpe_trials == 2000000
    assert args.shortlist_per_mode == 20
    assert args.shortlist_max_rank == 200
    assert args.num_candidates == 5


def test_profile_deep_backward_compat() -> None:
    args = _parse_cli_args(["--run-id", "x", "--profile", "deep"])
    assert args.tpe_trials == 10000000
    assert args.shortlist_per_mode == 40
    assert args.shortlist_max_rank == 500
    assert args.num_candidates == 10


def test_profile_weekly_values() -> None:
    args = _parse_cli_args(["--run-id", "x", "--profile", "weekly"])
    assert args.tpe_trials == 10000000
    assert args.shortlist_per_mode == 40
    assert args.shortlist_max_rank == 500
    assert args.num_candidates == 10


def test_profile_weekly_matches_deep() -> None:
    """weekly and deep must be identical (weekly is the canonical name)."""
    assert PROFILE_DEFAULTS["weekly"] == PROFILE_DEFAULTS["deep"]


def test_profile_does_not_override_explicit_values() -> None:
    args = _parse_cli_args(
        [
            "--run-id",
            "x",
            "--profile",
            "deep",
            "--tpe-trials",
            "123",
            "--shortlist-per-mode",
            "7",
            "--shortlist-max-rank",
            "77",
            "--num-candidates",
            "9",
        ]
    )
    assert args.tpe_trials == 123
    assert args.shortlist_per_mode == 7
    assert args.shortlist_max_rank == 77
    assert args.num_candidates == 9


def test_all_profiles_present_in_defaults() -> None:
    assert set(PROFILE_DEFAULTS.keys()) == {"smoke", "daily", "deep", "weekly"}


# ── Sweep-spec profile binding (C2) ──────────────────────────────────


def test_smoke_profile_sweep_spec() -> None:
    args = _parse_cli_args(["--run-id", "x", "--profile", "smoke"])
    assert args.sweep_spec == "backtester/sweeps/full_144v.yaml"


def test_live_initial_balance_profiles() -> None:
    assert _resolve_profile_requires_live_initial_balance(profile="daily")
    assert _resolve_profile_requires_live_initial_balance(profile="deep")
    assert _resolve_profile_requires_live_initial_balance(profile="weekly")
    assert not _resolve_profile_requires_live_initial_balance(profile="smoke")


def test_daily_profile_sweep_spec() -> None:
    args = _parse_cli_args(["--run-id", "x", "--profile", "daily"])
    assert args.sweep_spec == "backtester/sweeps/full_144v.yaml"


def test_weekly_profile_sweep_spec() -> None:
    args = _parse_cli_args(["--run-id", "x", "--profile", "weekly"])
    assert args.sweep_spec == "backtester/sweeps/full_144v.yaml"


def test_deep_profile_sweep_spec() -> None:
    args = _parse_cli_args(["--run-id", "x", "--profile", "deep"])
    assert args.sweep_spec == "backtester/sweeps/full_144v.yaml"


def test_explicit_sweep_spec_overrides_profile() -> None:
    args = _parse_cli_args(
        ["--run-id", "x", "--profile", "daily", "--sweep-spec", "custom/my_spec.yaml"]
    )
    assert args.sweep_spec == "custom/my_spec.yaml"
