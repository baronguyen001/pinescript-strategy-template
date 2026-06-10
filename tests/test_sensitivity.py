from pathlib import Path

import pandas as pd

from pinewf.cli import main
from pinewf.sensitivity import (
    SensitivityConfig,
    duration_buckets,
    duration_sensitivity,
    holding_durations,
    load_trades,
    sensitivity_from_csv,
)

EXPORT = Path("examples/sample_tradingview_export.csv")


def _engine_trades() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "entry_date": pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01", "2024-04-01"]),
            "exit_date": pd.to_datetime(["2024-01-02", "2024-02-03", "2024-03-15", "2024-04-30"]),
            "pnl": [50.0, -30.0, 400.0, -20.0],
            "pnl_pct": [0.5, -0.3, 4.0, -0.2],
            "bars_held": [1, 2, 14, 29],
        }
    )


def test_holding_durations_prefers_bars_held() -> None:
    durations = holding_durations(_engine_trades())
    assert durations.tolist() == [1.0, 2.0, 14.0, 29.0]


def test_holding_durations_falls_back_to_dates() -> None:
    trades = _engine_trades().drop(columns=["bars_held"])
    durations = holding_durations(trades)
    assert durations.tolist() == [1.0, 2.0, 14.0, 29.0]


def test_duration_buckets_partitions_trades() -> None:
    table = duration_buckets(_engine_trades())
    # durations 1, 2, 14, 29 -> buckets <=1, <=3, <=20, >20
    assert set(table["bucket"]) == {"<=1", "<=3", "<=20", ">20"}
    assert int(table["n_trades"].sum()) == 4
    shares = table.set_index("bucket")["share_of_gross_profit_pct"]
    assert abs(float(shares.sum()) - 100.0) < 1e-6


def test_duration_sensitivity_flags_concentration() -> None:
    # One huge winner in a single bucket dominates gross profit.
    trades = pd.DataFrame(
        {
            "pnl": [1000.0, 10.0, -5.0],
            "pnl_pct": [10.0, 0.1, -0.05],
            "bars_held": [4, 1, 25],
        }
    )
    summary = duration_sensitivity(trades, SensitivityConfig(concentration_threshold=0.6))
    assert summary["concentrated"] is True
    assert summary["verdict"] == "CONCENTRATED"
    assert summary["dominant_bucket"] == "<=5"


def test_empty_trades_are_safe() -> None:
    table = duration_buckets(pd.DataFrame())
    assert table.empty
    summary = duration_sensitivity(pd.DataFrame())
    assert summary["verdict"] == "NO_TRADES"


def test_load_trades_reads_tradingview_export() -> None:
    trades = load_trades(EXPORT)
    assert len(trades) == 3
    assert {"entry_date", "exit_date", "pnl"}.issubset(trades.columns)


def test_sensitivity_from_csv_and_cli(capsys) -> None:
    table, summary = sensitivity_from_csv(EXPORT)
    assert not table.empty
    assert summary["verdict"] in {"SPREAD", "CONCENTRATED"}
    assert main(["sensitivity", str(EXPORT)]) == 0
    out = capsys.readouterr().out
    assert "verdict" in out
    assert "bucket" in out


def test_sensitivity_cli_custom_buckets(capsys) -> None:
    assert main(["sensitivity", str(EXPORT), "--buckets", "2,8", "--concentration", "0.9"]) == 0
    out = capsys.readouterr().out
    assert "<=2" in out or "<=8" in out or ">8" in out
