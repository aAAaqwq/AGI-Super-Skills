import pytest

from tools.monte_carlo_bootstrap import compute_path_stats, load_trade_deltas_csv, summarise_dist


def test_load_trade_deltas_csv_sorts_and_nets_fees(tmp_path):
    p = tmp_path / "trades.csv"
    p.write_text(
        "trade_id,position_id,entry_ts_ms,exit_ts_ms,symbol,side,entry_price,exit_price,exit_size,pnl_usd,fee_usd,mae_pct,mfe_pct,reason_code,reason\n"
        "t1,1,0,2000,BTC,LONG,0,0,0,10.0,1.0,0,0,x,y\n"
        "t2,2,0,1000,BTC,LONG,0,0,0,-5.0,0.5,0,0,x,y\n",
        encoding="utf-8",
    )

    rows = load_trade_deltas_csv(p)
    assert rows[0][0] == 1000
    assert rows[0][1] == pytest.approx(-5.5)
    assert rows[1][0] == 2000
    assert rows[1][1] == pytest.approx(9.0)


def test_compute_path_stats_return_and_drawdown():
    st = compute_path_stats([-5.5, 9.0], initial_balance=100.0)
    assert st["final_balance"] == pytest.approx(103.5)
    assert st["total_return_pct"] == pytest.approx(0.035)
    assert st["max_drawdown_pct"] == pytest.approx(0.055)


def test_summarise_dist_quantiles():
    s = summarise_dist([0.0, 1.0, 2.0, 3.0])
    assert s.n == 4
    assert s.p50 == pytest.approx(1.5)

