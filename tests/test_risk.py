"""Tests for the extended risk analytics (v0.4)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pinewf.risk import (
    max_consecutive_losses,
    max_drawdown_duration_bars,
    risk_metrics,
    sortino_ratio,
    ulcer_index,
)


def _rising_then_dip() -> pd.Series:
    # 100 -> 110 -> 121 (peak) -> 100 (underwater 2 bars) -> 130
    return pd.Series([100.0, 110.0, 121.0, 110.0, 100.0, 130.0])


def test_sortino_zero_when_no_downside() -> None:
    rising = pd.Series([100, 101, 102, 103]).pct_change().fillna(0)
    assert sortino_ratio(rising) == 0.0  # no downside deviation


def test_sortino_positive_with_mixed_returns() -> None:
    returns = pd.Series([0.02, -0.01, 0.03, -0.005, 0.01])
    assert sortino_ratio(returns) > 0


def test_ulcer_index_zero_for_monotonic_rise() -> None:
    assert ulcer_index(pd.Series([100, 110, 120])) == 0.0


def test_ulcer_index_positive_with_drawdown() -> None:
    assert ulcer_index(_rising_then_dip()) > 0


def test_max_drawdown_duration_bars() -> None:
    # underwater at bars index 3 and 4 (110 and 100 < peak 121)
    assert max_drawdown_duration_bars(_rising_then_dip()) == 2


def test_max_consecutive_losses() -> None:
    trades = pd.DataFrame({"pnl": [10, -5, -3, -1, 4, -2]})
    assert max_consecutive_losses(trades) == 3


def test_max_consecutive_losses_empty() -> None:
    assert max_consecutive_losses(pd.DataFrame()) == 0


def test_risk_metrics_keys_and_types() -> None:
    equity = _rising_then_dip()
    trades = pd.DataFrame({"pnl": [10, -5, -3]})
    m = risk_metrics(equity, trades)
    for key in (
        "sortino",
        "calmar",
        "ulcer_index",
        "recovery_factor",
        "max_dd_duration_bars",
        "avg_drawdown_pct",
        "max_consecutive_losses",
    ):
        assert key in m
    assert m["max_dd_duration_bars"] == 2
    assert m["max_consecutive_losses"] == 2
    assert isinstance(m["sortino"], float)


def test_risk_metrics_datetime_index_calmar() -> None:
    idx = pd.date_range("2020-01-01", periods=6, freq="D")
    equity = pd.Series(_rising_then_dip().to_numpy(), index=idx)
    m = risk_metrics(equity, pd.DataFrame({"pnl": [1.0]}))
    assert np.isfinite(m["calmar"])


def test_risk_metrics_empty_raises() -> None:
    with pytest.raises(ValueError):
        risk_metrics(pd.Series([], dtype=float), pd.DataFrame())
