import pandas as pd

from pinewf.metrics import buy_hold_metrics, compute_metrics


def test_compute_metrics_known_equity() -> None:
    equity = pd.Series(
        [100.0, 120.0, 90.0, 130.0],
        index=pd.date_range("2020-01-01", periods=4, freq="D"),
        name="equity",
    )
    trades = pd.DataFrame({"pnl": [20.0, -10.0], "pnl_pct": [20.0, -10.0], "bars_held": [1, 1]})
    metrics = compute_metrics(equity, trades, 100.0, 4, periods_per_year=365)
    assert metrics["total_return_pct"] == 30.0
    assert metrics["max_dd_pct"] == -25.0
    assert metrics["n_trades"] == 2
    assert metrics["win_rate_pct"] == 50.0
    assert metrics["profit_factor"] == 2.0


def test_buy_hold_metrics() -> None:
    df = pd.DataFrame(
        {
            "close": [100.0, 110.0],
            "open": [100.0, 100.0],
            "high": [100.0, 110.0],
            "low": [99.0, 109.0],
            "volume": [1, 1],
        },
        index=pd.date_range("2020-01-01", periods=2, freq="D"),
    )
    metrics = buy_hold_metrics(df, initial=100.0, commission=0, slippage=0)
    assert metrics["total_return_pct"] == 10.0
