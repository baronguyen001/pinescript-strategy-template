import pandas as pd

from pinewf.indicators import add_signals, atr, moving_average


def test_moving_average_sma_and_ema() -> None:
    series = pd.Series([1.0, 2.0, 3.0, 4.0])
    assert moving_average(series, 2, "sma").iloc[-1] == 3.5
    assert round(moving_average(series, 2, "ema").iloc[-1], 3) == 3.519


def test_atr_and_cross_signals() -> None:
    df = pd.DataFrame(
        {
            "open": [5, 4, 3, 6, 7],
            "high": [6, 5, 4, 7, 8],
            "low": [4, 3, 2, 5, 6],
            "close": [5, 4, 3, 6, 7],
            "volume": [1, 1, 1, 1, 1],
        }
    )
    assert atr(df, 2).iloc[-1] == 3.0
    out = add_signals(df, fast=2, slow=3, trend=3, kind="sma", use_trend_filter=False)
    assert bool(out["cross_up"].iloc[3])
    assert not bool(out["cross_dn"].iloc[3])
