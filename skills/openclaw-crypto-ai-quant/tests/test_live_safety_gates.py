"""H8: Comprehensive tests for live safety gate functions.

Covers all combinations of:
- AI_QUANT_HARD_KILL_SWITCH  (hard kill: blocks ALL orders including exits)
- AI_QUANT_LIVE_ENABLE       (enable flag)
- AI_QUANT_LIVE_CONFIRM      (confirmation string)
- AI_QUANT_KILL_SWITCH       (soft kill: blocks entries, allows exits)
- AI_QUANT_MODE              (live / dry_live / paper)

Functions under test:
- _env_bool()              (internal helper)
- live_mode()
- live_orders_enabled()
- live_entries_enabled()
- live_trading_enabled()   (backwards-compat alias)
"""

import pytest

from exchange.executor import (
    _env_bool,
    live_entries_enabled,
    live_mode,
    live_orders_enabled,
    live_trading_enabled,
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Ensure a clean environment for each test."""
    for var in (
        "AI_QUANT_LIVE_ENABLE",
        "AI_QUANT_LIVE_CONFIRM",
        "AI_QUANT_HARD_KILL_SWITCH",
        "AI_QUANT_KILL_SWITCH",
        "AI_QUANT_MODE",
    ):
        monkeypatch.delenv(var, raising=False)


# ---------------------------------------------------------------------------
# _env_bool() helper
# ---------------------------------------------------------------------------
class TestEnvBool:
    """Test the _env_bool() helper that underlies the kill-switch flags."""

    def test_missing_env_returns_default_true(self, monkeypatch):
        monkeypatch.delenv("TEST_BOOL_VAR", raising=False)
        assert _env_bool("TEST_BOOL_VAR", True) is True

    def test_missing_env_returns_default_false(self, monkeypatch):
        monkeypatch.delenv("TEST_BOOL_VAR", raising=False)
        assert _env_bool("TEST_BOOL_VAR", False) is False

    @pytest.mark.parametrize("val", ["1", "true", "True", "TRUE", "yes", "Yes", "YES", "y", "Y", "on", "ON"])
    def test_truthy_values(self, monkeypatch, val):
        monkeypatch.setenv("TEST_BOOL_VAR", val)
        assert _env_bool("TEST_BOOL_VAR", False) is True

    @pytest.mark.parametrize("val", ["0", "false", "False", "FALSE", "no", "No", "off", "OFF", ""])
    def test_falsy_values(self, monkeypatch, val):
        monkeypatch.setenv("TEST_BOOL_VAR", val)
        assert _env_bool("TEST_BOOL_VAR", True) is False

    def test_whitespace_is_stripped(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL_VAR", "  true  ")
        assert _env_bool("TEST_BOOL_VAR", False) is True

    def test_garbage_string_is_falsy(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL_VAR", "maybe")
        assert _env_bool("TEST_BOOL_VAR", True) is False


# ---------------------------------------------------------------------------
# live_mode()
# ---------------------------------------------------------------------------
class TestLiveMode:
    """Test live_mode() which reads AI_QUANT_MODE."""

    def test_defaults_to_paper(self):
        assert live_mode() == "paper"

    def test_live_mode(self, monkeypatch):
        monkeypatch.setenv("AI_QUANT_MODE", "live")
        assert live_mode() == "live"

    def test_dry_live_mode(self, monkeypatch):
        monkeypatch.setenv("AI_QUANT_MODE", "dry_live")
        assert live_mode() == "dry_live"

    def test_paper_mode_explicit(self, monkeypatch):
        monkeypatch.setenv("AI_QUANT_MODE", "paper")
        assert live_mode() == "paper"

    def test_mode_is_lowercased(self, monkeypatch):
        monkeypatch.setenv("AI_QUANT_MODE", "LIVE")
        assert live_mode() == "live"

    def test_mode_is_stripped(self, monkeypatch):
        monkeypatch.setenv("AI_QUANT_MODE", "  live  ")
        assert live_mode() == "live"

    def test_empty_string_defaults_to_paper(self, monkeypatch):
        monkeypatch.setenv("AI_QUANT_MODE", "")
        assert live_mode() == "paper"


# ---------------------------------------------------------------------------
# live_orders_enabled()
# ---------------------------------------------------------------------------
class TestLiveOrdersEnabled:
    """Test live_orders_enabled() safety gate.

    Requires:
    - AI_QUANT_HARD_KILL_SWITCH is NOT set (or falsy)
    - AI_QUANT_LIVE_ENABLE is truthy
    - AI_QUANT_LIVE_CONFIRM == "I_UNDERSTAND_THIS_CAN_LOSE_MONEY"
    """

    def test_all_unset_returns_false(self):
        """Default environment (nothing set) -> orders disabled."""
        assert live_orders_enabled() is False

    def test_enable_without_confirm(self, monkeypatch):
        """ENABLE=1 without CONFIRM -> no orders."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        assert live_orders_enabled() is False

    def test_confirm_without_enable(self, monkeypatch):
        """CONFIRM set but ENABLE not set -> no orders."""
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        assert live_orders_enabled() is False

    def test_enable_with_wrong_confirm(self, monkeypatch):
        """ENABLE=1 with wrong CONFIRM -> no orders."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "WRONG_STRING")
        assert live_orders_enabled() is False

    def test_enable_with_empty_confirm(self, monkeypatch):
        """ENABLE=1 with empty CONFIRM -> no orders."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "")
        assert live_orders_enabled() is False

    def test_enable_with_whitespace_only_confirm(self, monkeypatch):
        """ENABLE=1 with whitespace-only CONFIRM -> no orders."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "   ")
        assert live_orders_enabled() is False

    def test_confirm_is_case_sensitive(self, monkeypatch):
        """Confirm string must be exact case -> lowercase rejected."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "i_understand_this_can_lose_money")
        assert live_orders_enabled() is False

    def test_confirm_with_trailing_whitespace_passes(self, monkeypatch):
        """Confirm string is .strip()'d, so trailing/leading space is OK."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "  I_UNDERSTAND_THIS_CAN_LOSE_MONEY  ")
        assert live_orders_enabled() is True

    def test_hard_kill_switch_overrides_everything(self, monkeypatch):
        """HARD_KILL_SWITCH=1 overrides even correct enable+confirm."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        monkeypatch.setenv("AI_QUANT_HARD_KILL_SWITCH", "1")
        assert live_orders_enabled() is False

    @pytest.mark.parametrize("val", ["true", "yes", "on", "1"])
    def test_hard_kill_switch_truthy_variants(self, monkeypatch, val):
        """All truthy values for HARD_KILL_SWITCH block orders."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        monkeypatch.setenv("AI_QUANT_HARD_KILL_SWITCH", val)
        assert live_orders_enabled() is False

    def test_hard_kill_switch_falsy_allows(self, monkeypatch):
        """HARD_KILL_SWITCH=0 does NOT block orders."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        monkeypatch.setenv("AI_QUANT_HARD_KILL_SWITCH", "0")
        assert live_orders_enabled() is True

    def test_correct_enable_and_confirm(self, monkeypatch):
        """Both set correctly -> orders enabled."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        assert live_orders_enabled() is True

    @pytest.mark.parametrize("val", ["true", "yes", "y", "on", "1", "True", "YES"])
    def test_enable_truthy_variants(self, monkeypatch, val):
        """All truthy values for ENABLE work."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", val)
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        assert live_orders_enabled() is True

    def test_enable_false_blocks(self, monkeypatch):
        """ENABLE=false (falsy) blocks even with correct confirm."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "false")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        assert live_orders_enabled() is False

    def test_soft_kill_switch_does_not_affect_orders(self, monkeypatch):
        """AI_QUANT_KILL_SWITCH (soft) does NOT block orders (only entries)."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        monkeypatch.setenv("AI_QUANT_KILL_SWITCH", "1")
        assert live_orders_enabled() is True


# ---------------------------------------------------------------------------
# live_entries_enabled()
# ---------------------------------------------------------------------------
class TestLiveEntriesEnabled:
    """Test live_entries_enabled() which also checks AI_QUANT_KILL_SWITCH.

    Entries require live_orders_enabled() AND AI_QUANT_KILL_SWITCH is NOT set.
    """

    def test_all_unset_returns_false(self):
        """Default environment -> entries disabled (orders disabled)."""
        assert live_entries_enabled() is False

    def test_kill_switch_blocks_entries(self, monkeypatch):
        """KILL_SWITCH=1 blocks entries even when orders are enabled."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        monkeypatch.setenv("AI_QUANT_KILL_SWITCH", "1")
        assert live_entries_enabled() is False

    @pytest.mark.parametrize("val", ["true", "yes", "on", "1"])
    def test_kill_switch_truthy_variants(self, monkeypatch, val):
        """All truthy values for KILL_SWITCH block entries."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        monkeypatch.setenv("AI_QUANT_KILL_SWITCH", val)
        assert live_entries_enabled() is False

    def test_kill_switch_falsy_allows(self, monkeypatch):
        """KILL_SWITCH=0 does NOT block entries."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        monkeypatch.setenv("AI_QUANT_KILL_SWITCH", "0")
        assert live_entries_enabled() is True

    def test_hard_kill_switch_blocks_entries(self, monkeypatch):
        """HARD_KILL_SWITCH=1 blocks entries (orders disabled entirely)."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        monkeypatch.setenv("AI_QUANT_HARD_KILL_SWITCH", "1")
        assert live_entries_enabled() is False

    def test_both_kill_switches_block_entries(self, monkeypatch):
        """Both KILL_SWITCH and HARD_KILL_SWITCH active -> entries blocked."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        monkeypatch.setenv("AI_QUANT_KILL_SWITCH", "1")
        monkeypatch.setenv("AI_QUANT_HARD_KILL_SWITCH", "1")
        assert live_entries_enabled() is False

    def test_entries_enabled_when_all_gates_pass(self, monkeypatch):
        """All gates pass -> entries enabled."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        assert live_entries_enabled() is True

    def test_close_only_semantics(self, monkeypatch):
        """KILL_SWITCH on: orders still enabled (exits OK), but entries blocked."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        monkeypatch.setenv("AI_QUANT_KILL_SWITCH", "1")
        # Orders (exits) still work
        assert live_orders_enabled() is True
        # Entries blocked
        assert live_entries_enabled() is False

    def test_hard_kill_blocks_both(self, monkeypatch):
        """HARD_KILL_SWITCH blocks both orders AND entries."""
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        monkeypatch.setenv("AI_QUANT_HARD_KILL_SWITCH", "1")
        assert live_orders_enabled() is False
        assert live_entries_enabled() is False


# ---------------------------------------------------------------------------
# live_trading_enabled() (backwards-compat alias)
# ---------------------------------------------------------------------------
class TestLiveTradingEnabled:
    """Test live_trading_enabled() is an exact alias for live_entries_enabled()."""

    def test_alias_returns_false_by_default(self):
        assert live_trading_enabled() is False

    def test_alias_matches_entries_enabled(self, monkeypatch):
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        assert live_trading_enabled() is True
        assert live_trading_enabled() == live_entries_enabled()

    def test_alias_with_kill_switch(self, monkeypatch):
        monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        monkeypatch.setenv("AI_QUANT_KILL_SWITCH", "1")
        assert live_trading_enabled() is False
        assert live_trading_enabled() == live_entries_enabled()


# ---------------------------------------------------------------------------
# Exhaustive truth table for live_orders_enabled()
# ---------------------------------------------------------------------------
class TestLiveOrdersEnabledTruthTable:
    """Exhaustive 2^3 truth table for the three conditions."""

    @pytest.mark.parametrize(
        "hard_kill, enable, confirm, expected",
        [
            # hard_kill=off, enable=off, confirm=off -> False (no enable)
            (False, False, False, False),
            # hard_kill=off, enable=off, confirm=on -> False (no enable)
            (False, False, True, False),
            # hard_kill=off, enable=on, confirm=off -> False (no confirm)
            (False, True, False, False),
            # hard_kill=off, enable=on, confirm=on -> True (all gates pass)
            (False, True, True, True),
            # hard_kill=on, enable=off, confirm=off -> False (hard kill)
            (True, False, False, False),
            # hard_kill=on, enable=off, confirm=on -> False (hard kill)
            (True, False, True, False),
            # hard_kill=on, enable=on, confirm=off -> False (hard kill)
            (True, True, False, False),
            # hard_kill=on, enable=on, confirm=on -> False (hard kill overrides)
            (True, True, True, False),
        ],
    )
    def test_truth_table(self, monkeypatch, hard_kill, enable, confirm, expected):
        if hard_kill:
            monkeypatch.setenv("AI_QUANT_HARD_KILL_SWITCH", "1")
        if enable:
            monkeypatch.setenv("AI_QUANT_LIVE_ENABLE", "1")
        if confirm:
            monkeypatch.setenv("AI_QUANT_LIVE_CONFIRM", "I_UNDERSTAND_THIS_CAN_LOSE_MONEY")
        assert live_orders_enabled() is expected
