import pytest

from tools.cross_universe_validate import compute_cross_universe_summary, load_symbol_set


def test_load_symbol_set_text_and_json(tmp_path):
    txt = tmp_path / "syms.txt"
    txt.write_text("# comment\nBTC\nETH\nBTC\n", encoding="utf-8")
    assert load_symbol_set(txt) == ["BTC", "ETH"]

    js = tmp_path / "syms.json"
    js.write_text('["SOL","BTC","SOL"]\n', encoding="utf-8")
    assert load_symbol_set(js) == ["BTC", "SOL"]


def test_compute_cross_universe_summary_shares():
    replay = {
        "per_symbol": {
            "A": {"trades": 10, "net_pnl_usd": 100.0, "fees_usd": 5.0},
            "B": {"trades": 5, "net_pnl_usd": 50.0, "fees_usd": 2.0},
            "C": {"trades": 1, "net_pnl_usd": -25.0, "fees_usd": 1.0},
        }
    }

    out = compute_cross_universe_summary(replay, sets=[("liquid", ["A", "B"]), ("tail", ["C", "D"])])
    assert out["version"] == "cross_universe_v1"

    total = out["total"]
    assert total["trades"] == pytest.approx(16.0)
    assert total["net_pnl_usd"] == pytest.approx(125.0)

    sets = {s["name"]: s for s in out["sets"]}
    liquid = sets["liquid"]
    assert liquid["subset"]["net_pnl_usd"] == pytest.approx(150.0)
    assert liquid["shares"]["net_pnl_usd"] == pytest.approx(150.0 / 125.0)

