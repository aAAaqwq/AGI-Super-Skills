from collections import OrderedDict

import exchange.ws as ws_mod


def _build_ws(tmp_path, monkeypatch):
    db_path = tmp_path / "ws_test.db"
    monkeypatch.setattr(ws_mod, "DB_PATH", str(db_path))
    return ws_mod.HyperliquidWS()


def test_get_candles_df_drops_non_numeric_rows_and_keeps_valid_rows(tmp_path, monkeypatch):
    ws = _build_ws(tmp_path, monkeypatch)
    key = ("BTC", "1m")
    with ws._lock:  # noqa: SLF001
        ws._candles[key] = OrderedDict(
            {
                1: {"Open": "100.0", "High": "101.0", "Low": "99.0", "Close": "100.5", "Volume": "10"},
                2: {"Open": "100.5", "High": "102.0", "Low": "100.0", "Close": "bad", "Volume": "12"},
                3: {"Open": "101.0", "High": "103.0", "Low": "100.8", "Close": "102.0", "Volume": "15"},
            }
        )

    df = ws.get_candles_df("BTC", "1m", min_rows=2)

    assert df is not None
    assert len(df) == 2
    assert df["Close"].isna().sum() == 0
    assert list(df["Close"]) == [100.5, 102.0]


def test_get_candles_df_returns_none_if_dropna_breaks_min_rows(tmp_path, monkeypatch):
    ws = _build_ws(tmp_path, monkeypatch)
    key = ("ETH", "1m")
    with ws._lock:  # noqa: SLF001
        ws._candles[key] = OrderedDict(
            {
                1: {"Open": "200.0", "High": "201.0", "Low": "199.0", "Close": "bad", "Volume": "20"},
                2: {"Open": "201.0", "High": "202.0", "Low": "200.5", "Close": "201.5", "Volume": "25"},
            }
        )

    df = ws.get_candles_df("ETH", "1m", min_rows=2)

    assert df is None
