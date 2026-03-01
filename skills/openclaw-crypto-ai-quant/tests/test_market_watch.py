from __future__ import annotations

import pytest

from exchange.market_watch import _pct_return


def test_pct_return_basic_case():
    assert _pct_return(110.0, 100.0) == pytest.approx(10.0)


def test_pct_return_non_positive_start_returns_zero():
    assert _pct_return(110.0, 0.0) == 0.0
    assert _pct_return(110.0, -1.0) == 0.0


def test_pct_return_non_finite_or_invalid_returns_zero():
    assert _pct_return(float("nan"), 100.0) == 0.0
    assert _pct_return(110.0, float("inf")) == 0.0
    assert _pct_return("oops", 100.0) == 0.0
    assert _pct_return(110.0, "oops") == 0.0
    assert _pct_return(110.0, 1e-308) == 0.0
