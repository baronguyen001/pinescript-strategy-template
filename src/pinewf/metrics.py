from __future__ import annotations

import numpy as np
import pandas as pd


def compute_metrics(
    equity: pd.Series,
    trades: pd.DataFrame,
    initial: float,
    n_price_bars: int,
    name: str = "strategy",
    periods_per_year: int = 365,
) -> dict:
    """Compute common strategy metrics from an equity curve and trade table."""
    if equity.empty:
        raise ValueError("equity must not be empty")
    series = equity.astype(float).dropna()
    total = series.iloc[-1] / initial - 1
    years = _years(series.index, n_price_bars, periods_per_year)
    cagr = (series.iloc[-1] / initial) ** (1 / years) - 1 if years > 0 else 0.0
    drawdown = series / series.cummax() - 1
    returns = series.pct_change().fillna(0)
    std = returns.std()
    sharpe = returns.mean() / std * np.sqrt(periods_per_year) if std > 0 else 0.0

    n_trades = len(trades)
    if n_trades:
        wins = trades[trades["pnl"] > 0]
        losses = trades[trades["pnl"] <= 0]
        gross_wins = float(wins["pnl"].sum())
        gross_losses = abs(float(losses["pnl"].sum()))
        profit_factor = gross_wins / gross_losses if gross_losses else None
        bars_held = float(trades.get("bars_held", pd.Series(dtype=float)).fillna(0).sum())
        win_rate = len(wins) / n_trades * 100
        avg_win = float(wins["pnl_pct"].mean()) if len(wins) else 0.0
        avg_loss = float(losses["pnl_pct"].mean()) if len(losses) else 0.0
        time_in_market = bars_held / max(n_price_bars, 1) * 100
    else:
        profit_factor = None
        win_rate = avg_win = avg_loss = time_in_market = 0.0

    return {
        "name": name,
        "total_return_pct": round(total * 100, 2),
        "cagr_pct": round(cagr * 100, 2),
        "max_dd_pct": round(float(drawdown.min()) * 100, 2),
        "sharpe": round(float(sharpe), 3),
        "n_trades": int(n_trades),
        "win_rate_pct": round(win_rate, 2),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "profit_factor": round(profit_factor, 3) if profit_factor is not None else None,
        "time_in_market_pct": round(time_in_market, 2),
        "final_equity": round(float(series.iloc[-1]), 2),
    }


def buy_hold_metrics(
    df: pd.DataFrame,
    initial: float = 10_000.0,
    commission: float = 0.001,
    slippage: float = 0.0005,
    periods_per_year: int = 365,
) -> dict:
    """Buy at the first close, hold, then apply an exit cost at the end."""
    if df.empty:
        raise ValueError("df must not be empty")
    data = df.copy()
    if not isinstance(data.index, pd.DatetimeIndex):
        data = data.set_index(pd.to_datetime(data["date"]))
    qty = (initial * (1 - commission)) / (float(data["close"].iloc[0]) * (1 + slippage))
    equity = data["close"].astype(float) * qty * (1 - commission)
    equity.name = "equity"
    return compute_metrics(equity, pd.DataFrame(), initial, len(data), "buy_hold", periods_per_year)


def _years(index: pd.Index, n_price_bars: int, periods_per_year: int) -> float:
    if isinstance(index, pd.DatetimeIndex) and len(index) >= 2:
        days = max((index[-1] - index[0]).total_seconds() / 86_400, 1e-9)
        return max(days / 365.25, 1e-9)
    return max(n_price_bars / periods_per_year, 1e-9)
