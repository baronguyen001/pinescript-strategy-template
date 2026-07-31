"""Tests for pinewf.regime."""

import pandas as pd
import pytest

from pinewf.regime import (
    RegimeConfig,
    label_regimes,
    regime_breakdown,
    regime_buckets,
    regime_summary,
)

_REGIME_COLUMNS: list[str] = [
    "regime",
    "n_trades",
    "win_rate_pct",
    "avg_pnl_pct",
    "total_pnl",
    "profit_factor",
    "share_of_gross_profit_pct",
]


def _make_trade_dates() -> pd.DatetimeIndex:
    return pd.to_datetime(["2026-01-10", "2026-01-11", "2026-01-12", "2026-01-13"])


def test_label_regimes_golden_10_bars() -> None:
    dates = pd.date_range("2026-01-01", periods=10)
    df = pd.DataFrame(
        {"close": [100, 100, 102, 104, 106, 108, 108, 108, 106, 100]},
        index=dates,
    )
    cfg = RegimeConfig(window=2, slope_threshold_pct=1.0)
    expected = [
        "UNKNOWN",
        "UNKNOWN",
        "UNKNOWN",
        "UPTREND",
        "UPTREND",
        "UPTREND",
        "UPTREND",
        "RANGE",
        "RANGE",
        "DOWNTREND",
    ]
    result = label_regimes(df, cfg)
    assert result.tolist() == expected
    assert result.name == "regime"
    assert result.dtype == object


def test_label_regimes_uses_date_column() -> None:
    df = pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=10),
            "close": [100, 100, 102, 104, 106, 108, 108, 108, 106, 100],
        }
    )
    cfg = RegimeConfig(window=2, slope_threshold_pct=1.0)
    expected = [
        "UNKNOWN",
        "UNKNOWN",
        "UNKNOWN",
        "UPTREND",
        "UPTREND",
        "UPTREND",
        "UPTREND",
        "RANGE",
        "RANGE",
        "DOWNTREND",
    ]
    assert label_regimes(df, cfg).tolist() == expected


def test_label_regimes_missing_date_raises() -> None:
    df = pd.DataFrame({"close": [1, 2, 3]})
    with pytest.raises(ValueError, match="DatetimeIndex or a date column"):
        label_regimes(df)


def test_label_regimes_empty_df() -> None:
    result = label_regimes(pd.DataFrame())
    assert result.empty
    assert result.name == "regime"
    assert result.dtype == object


def test_regime_buckets_golden() -> None:
    dates = _make_trade_dates()
    trades = pd.DataFrame(
        {
            "entry_date": dates,
            "exit_date": dates,
            "entry_price": [100.0] * 4,
            "exit_price": [101.0, 99.5, 103.0, 99.8],
            "pnl": [100.0, -50.0, 300.0, -20.0],
            "pnl_pct": [1.0, -0.5, 3.0, -0.2],
            "reason": ["exit"] * 4,
            "bars_held": [1] * 4,
        }
    )
    regimes = pd.Series(
        ["UPTREND", "UPTREND", "RANGE", "RANGE"],
        index=dates,
        name="regime",
    )
    expected = pd.DataFrame(
        {
            "regime": ["UPTREND", "RANGE"],
            "n_trades": [2, 2],
            "win_rate_pct": [50.0, 50.0],
            "avg_pnl_pct": [0.25, 1.4],
            "total_pnl": [50.0, 280.0],
            "profit_factor": [2.0, 15.0],
            "share_of_gross_profit_pct": [25.0, 75.0],
        },
        columns=_REGIME_COLUMNS,
    )
    result = regime_buckets(trades, regimes)
    pd.testing.assert_frame_equal(result, expected)


def test_regime_buckets_empty_trades() -> None:
    result = regime_buckets(
        pd.DataFrame(),
        pd.Series(dtype=object, name="regime"),
    )
    assert list(result.columns) == _REGIME_COLUMNS
    assert result.empty


def test_regime_buckets_profit_factor_none_all_wins() -> None:
    dates = pd.to_datetime(["2026-01-10", "2026-01-11"])
    trades = pd.DataFrame(
        {
            "entry_date": dates,
            "exit_date": dates,
            "entry_price": [100.0, 100.0],
            "exit_price": [101.0, 102.0],
            "pnl": [100.0, 200.0],
            "pnl_pct": [1.0, 2.0],
            "reason": ["exit", "exit"],
            "bars_held": [1, 1],
        }
    )
    regimes = pd.Series(["UPTREND", "UPTREND"], index=dates, name="regime")
    result = regime_buckets(trades, regimes)
    assert result.iloc[0]["profit_factor"] is None
    assert result.iloc[0]["share_of_gross_profit_pct"] == 100.0


def test_regime_buckets_share_zero_no_winners() -> None:
    dates = pd.to_datetime(["2026-01-10", "2026-01-11"])
    trades = pd.DataFrame(
        {
            "entry_date": dates,
            "exit_date": dates,
            "entry_price": [100.0, 100.0],
            "exit_price": [99.0, 98.0],
            "pnl": [-100.0, -200.0],
            "pnl_pct": [-1.0, -2.0],
            "reason": ["exit", "exit"],
            "bars_held": [1, 1],
        }
    )
    regimes = pd.Series(["DOWNTREND", "DOWNTREND"], index=dates, name="regime")
    row = regime_buckets(trades, regimes).iloc[0]
    assert row["profit_factor"] == 0.0
    assert row["share_of_gross_profit_pct"] == 0.0


def test_regime_summary_concentrated_golden() -> None:
    dates = _make_trade_dates()
    trades = pd.DataFrame(
        {
            "entry_date": dates,
            "exit_date": dates,
            "entry_price": [100.0] * 4,
            "exit_price": [101.0, 99.5, 103.0, 99.8],
            "pnl": [100.0, -50.0, 300.0, -20.0],
            "pnl_pct": [1.0, -0.5, 3.0, -0.2],
            "reason": ["exit"] * 4,
            "bars_held": [1] * 4,
        }
    )
    regimes = pd.Series(
        ["UPTREND", "UPTREND", "RANGE", "RANGE"],
        index=dates,
        name="regime",
    )
    expected = {
        "n_regimes": 2,
        "dominant_regime": "RANGE",
        "dominant_share_pct": 75.0,
        "concentrated": True,
        "verdict": "CONCENTRATED",
    }
    assert regime_summary(trades, regimes) == expected


def test_regime_summary_spread_even_shares() -> None:
    dates = pd.to_datetime(["2026-01-10", "2026-01-11"])
    trades = pd.DataFrame(
        {
            "entry_date": dates,
            "exit_date": dates,
            "entry_price": [100.0, 100.0],
            "exit_price": [101.0, 101.0],
            "pnl": [100.0, 100.0],
            "pnl_pct": [1.0, 1.0],
            "reason": ["exit", "exit"],
            "bars_held": [1, 1],
        }
    )
    regimes = pd.Series(["UPTREND", "DOWNTREND"], index=dates, name="regime")
    expected = {
        "n_regimes": 2,
        "dominant_regime": "UPTREND",
        "dominant_share_pct": 50.0,
        "concentrated": False,
        "verdict": "SPREAD",
    }
    assert regime_summary(trades, regimes) == expected


def test_regime_summary_empty_trades() -> None:
    expected = {
        "n_regimes": 0,
        "dominant_regime": None,
        "dominant_share_pct": 0.0,
        "concentrated": False,
        "verdict": "NO_TRADES",
    }
    result = regime_summary(
        pd.DataFrame(),
        pd.Series(dtype=object, name="regime"),
    )
    assert result == expected


def test_regime_breakdown_returns_tuple() -> None:
    dates = pd.date_range("2026-01-01", periods=5)
    df = pd.DataFrame(
        {"close": [100, 102, 104, 103, 101]},
        index=dates,
    )
    trades = pd.DataFrame(
        {
            "entry_date": [dates[2], dates[4]],
            "exit_date": [dates[3], dates[4]],
            "entry_price": [100.0, 100.0],
            "exit_price": [103.0, 101.0],
            "pnl": [100.0, -50.0],
            "pnl_pct": [1.0, -0.5],
            "reason": ["exit", "exit"],
            "bars_held": [1, 1],
        }
    )
    result = regime_breakdown(df, trades)
    assert isinstance(result, tuple)
    assert len(result) == 2
    assert isinstance(result[0], pd.DataFrame)
    assert isinstance(result[1], dict)


def test_regime_buckets_python_types() -> None:
    dates = _make_trade_dates()
    trades = pd.DataFrame(
        {
            "entry_date": dates,
            "exit_date": dates,
            "entry_price": [100.0] * 4,
            "exit_price": [101.0, 99.5, 103.0, 99.8],
            "pnl": [100.0, -50.0, 300.0, -20.0],
            "pnl_pct": [1.0, -0.5, 3.0, -0.2],
            "reason": ["exit"] * 4,
            "bars_held": [1] * 4,
        }
    )
    regimes = pd.Series(
        ["UPTREND", "UPTREND", "RANGE", "RANGE"],
        index=dates,
        name="regime",
    )
    result = regime_buckets(trades, regimes)
    assert result["n_trades"].dtype == "int64"
    assert result["total_pnl"].dtype == "float64"
    assert result["avg_pnl_pct"].dtype == "float64"
    assert result["win_rate_pct"].dtype == "float64"
