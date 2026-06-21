"""Extended, generic risk analytics for an equity curve and trade table.

These are standard textbook risk measures (Sortino, Calmar, Ulcer index,
drawdown duration, recovery factor, loss streaks) computed from a backtest's
equity curve. They are descriptive statistics, not tuned parameters or a
recommended strategy — the project's educational, generic-defaults ethos is
unchanged.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sortino_ratio(returns: pd.Series, periods_per_year: int = 365, target: float = 0.0) -> float:
    """Annualised Sortino ratio: excess return over downside deviation."""
    r = returns.astype(float).dropna()
    if r.empty:
        return 0.0
    downside = r[r < target]
    downside_dev = float(np.sqrt((downside**2).mean())) if len(downside) else 0.0
    if downside_dev <= 0:
        return 0.0
    return float((r.mean() - target) / downside_dev * np.sqrt(periods_per_year))


def ulcer_index(equity: pd.Series) -> float:
    """Ulcer index: RMS of the percentage drawdown series (depth + duration)."""
    series = equity.astype(float).dropna()
    if series.empty:
        return 0.0
    drawdown_pct = (series / series.cummax() - 1.0) * 100.0
    return float(np.sqrt((drawdown_pct**2).mean()))


def max_drawdown_duration_bars(equity: pd.Series) -> int:
    """Longest stretch (in bars) the equity stayed below a previous peak."""
    series = equity.astype(float).dropna()
    if series.empty:
        return 0
    underwater = series < series.cummax()
    longest = current = 0
    for is_under in underwater:
        current = current + 1 if is_under else 0
        longest = max(longest, current)
    return int(longest)


def max_consecutive_losses(trades: pd.DataFrame) -> int:
    """Longest run of consecutive losing trades (``pnl <= 0``)."""
    if trades.empty or "pnl" not in trades:
        return 0
    longest = current = 0
    for pnl in trades["pnl"].astype(float):
        current = current + 1 if pnl <= 0 else 0
        longest = max(longest, current)
    return int(longest)


def _annualised_return(equity: pd.Series, periods_per_year: int) -> float:
    series = equity.astype(float).dropna()
    if len(series) < 2 or series.iloc[0] <= 0:
        return 0.0
    growth = series.iloc[-1] / series.iloc[0]
    if isinstance(series.index, pd.DatetimeIndex):
        days = max((series.index[-1] - series.index[0]).total_seconds() / 86_400, 1e-9)
        years = max(days / 365.25, 1e-9)
    else:
        years = max(len(series) / periods_per_year, 1e-9)
    return float(growth ** (1 / years) - 1.0)


def risk_metrics(
    equity: pd.Series,
    trades: pd.DataFrame,
    periods_per_year: int = 365,
) -> dict:
    """Aggregate extended risk metrics from an equity curve and trade table."""
    series = equity.astype(float).dropna()
    if series.empty:
        raise ValueError("equity must not be empty")
    returns = series.pct_change().fillna(0.0)
    drawdown = series / series.cummax() - 1.0
    max_dd = float(drawdown.min())
    total_return = float(series.iloc[-1] / series.iloc[0] - 1.0) if series.iloc[0] else 0.0
    annual = _annualised_return(series, periods_per_year)
    abs_dd = abs(max_dd)

    return {
        "sortino": round(sortino_ratio(returns, periods_per_year), 3),
        "calmar": round(annual / abs_dd, 3) if abs_dd > 0 else 0.0,
        "ulcer_index": round(ulcer_index(series), 3),
        "recovery_factor": round(total_return / abs_dd, 3) if abs_dd > 0 else 0.0,
        "max_dd_duration_bars": max_drawdown_duration_bars(series),
        "avg_drawdown_pct": round(float(drawdown[drawdown < 0].mean()) * 100, 2)
        if (drawdown < 0).any()
        else 0.0,
        "max_consecutive_losses": max_consecutive_losses(trades),
    }
