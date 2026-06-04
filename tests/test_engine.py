import pandas as pd

from pinewf.engine import StrategyConfig, run_backtest


def base_df(
    low_at_entry: float = 99,
    high_at_entry: float = 101,
    open_at_entry: float = 100,
    next_open: float = 102,
    next_low: float = 101,
) -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=6, freq="D")
    return pd.DataFrame(
        {
            "open": [5, 4, 3, 6, open_at_entry, next_open],
            "high": [6, 5, 4, 7, high_at_entry, max(next_open, 103)],
            "low": [4, 3, 2, 5, low_at_entry, next_low],
            "close": [5, 4, 3, 6, 99, 102],
            "volume": [1, 1, 1, 1, 1, 1],
        },
        index=idx,
    )


def cfg(**kwargs) -> StrategyConfig:
    values = {
        "fast": 2,
        "slow": 3,
        "trend": 3,
        "ma_kind": "sma",
        "use_trend_filter": False,
        "stop_kind": "none",
        "commission": 0,
        "slippage": 0,
    }
    values.update(kwargs)
    return StrategyConfig(**values)


def test_signal_at_close_executes_next_open() -> None:
    result = run_backtest(base_df(), cfg())
    trade = result.trades.iloc[0]
    assert trade["entry_date"] == pd.Timestamp("2020-01-05")
    assert trade["entry_price"] == 100
    assert trade["reason"] == "EOD"


def test_percent_stop_intrabar() -> None:
    result = run_backtest(base_df(low_at_entry=90), cfg(stop_kind="percent", stop_loss_pct=8))
    trade = result.trades.iloc[0]
    assert trade["exit_price"] == 92
    assert trade["reason"] == "SL/TRAIL"


def test_stop_gap_exit() -> None:
    result = run_backtest(
        base_df(low_at_entry=99, open_at_entry=100, next_open=88, next_low=87),
        cfg(stop_kind="percent", stop_loss_pct=8),
    )
    trade = result.trades.iloc[0]
    assert trade["exit_price"] == 88
    assert trade["reason"] == "SL_GAP"


def test_take_profit_gap_exit() -> None:
    result = run_backtest(base_df(high_at_entry=101, next_open=112), cfg(take_profit_pct=10))
    trade = result.trades.iloc[0]
    assert trade["reason"] == "TP_GAP"


def test_trailing_stop_exit() -> None:
    result = run_backtest(base_df(low_at_entry=94, high_at_entry=110), cfg(trailing_pct=10))
    trade = result.trades.iloc[0]
    assert trade["exit_price"] == 99
    assert trade["reason"] == "SL/TRAIL"


def test_chandelier_exit() -> None:
    df = base_df(low_at_entry=95, high_at_entry=110)
    result = run_backtest(df, cfg(chandelier_atr_mult=0.2, atr_length=2))
    assert result.trades.iloc[0]["reason"] == "SL/TRAIL"


def test_commission_and_slippage_affect_fill() -> None:
    result = run_backtest(base_df(), cfg(commission=0.001, slippage=0.001))
    assert result.trades.iloc[0]["pnl"] < 200
