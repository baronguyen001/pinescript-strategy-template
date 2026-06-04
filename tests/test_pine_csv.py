from pathlib import Path

from pinewf.pine_csv import metrics_from_pine_export, parse_tradingview_trades


def test_parse_tradingview_two_row_layout() -> None:
    trades = parse_tradingview_trades(Path("examples/sample_tradingview_export.csv"))
    assert len(trades) == 3
    assert trades.iloc[0]["entry_price"] == 100.0
    assert trades.iloc[0]["exit_price"] == 108.0
    assert trades.iloc[1]["pnl_pct"] == -5.0


def test_metrics_from_pine_export() -> None:
    metrics = metrics_from_pine_export(
        Path("examples/sample_tradingview_export.csv"), initial=10_000
    )
    assert metrics["name"] == "tradingview_export"
    assert metrics["n_trades"] == 3
