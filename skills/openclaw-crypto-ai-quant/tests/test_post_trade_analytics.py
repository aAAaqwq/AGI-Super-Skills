import json
from pathlib import Path

import pandas as pd

from tools.post_trade_analytics import run


def test_post_trade_analytics_writes_outputs(tmp_path: Path):
    trades_csv = tmp_path / "trades.csv"
    trades_csv.write_text(
        "\n".join(
            [
                "trade_id,position_id,entry_ts_ms,exit_ts_ms,symbol,side,entry_price,exit_price,exit_size,pnl_usd,fee_usd,mae_pct,mfe_pct,reason_code,reason",
                "1:1,1,1000,2000,BTC,LONG,100,110,1,10,1,-0.05,0.10,tp_hit,take profit",
                "2:1,2,1000,3000,ETH,SHORT,200,210,1,-5,0.5,-0.04,0.03,sl_hit,stop loss",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    events_jsonl = tmp_path / "events.jsonl"
    events_jsonl.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema": "aiq_event_v1",
                        "ts_ms": 123,
                        "ts": "2026-01-01T00:00:00Z",
                        "pid": 1,
                        "mode": "paper",
                        "run_id": "",
                        "config_id": "",
                        "kind": "audit",
                        "symbol": "BTC",
                        "data": {"event": "ENTRY_OPEN", "level": "info", "data": {}},
                    }
                ),
                json.dumps(
                    {
                        "schema": "aiq_event_v1",
                        "ts_ms": 124,
                        "ts": "2026-01-01T00:00:01Z",
                        "pid": 1,
                        "mode": "paper",
                        "run_id": "",
                        "config_id": "",
                        "kind": "audit",
                        "symbol": "ETH",
                        "data": {"event": "ENTRY_SKIP_SSF", "level": "info", "data": {}},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    paths = run(trades_csv=trades_csv, events_jsonl=events_jsonl, out_dir=out_dir)

    assert paths.trade_summary_json.exists()
    assert paths.pnl_by_symbol_csv.exists()
    assert paths.reason_code_stats_csv.exists()
    assert paths.mae_mfe_summary_json.exists()
    assert paths.entry_event_counts_csv.exists()
    assert paths.entry_event_counts_by_symbol_csv.exists()

    payload = json.loads(paths.trade_summary_json.read_text(encoding="utf-8"))
    assert payload["summary"]["trades"] == 2
    assert payload["summary"]["total_net_pnl_usd"] == 3.5

    by_symbol = pd.read_csv(paths.pnl_by_symbol_csv)
    assert set(by_symbol["symbol"]) == {"BTC", "ETH"}

