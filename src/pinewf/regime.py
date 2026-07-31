"""Market-regime breakdown for realized trades."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

REGIME_ORDER: tuple[str, ...] = ("UPTREND", "RANGE", "DOWNTREND", "UNKNOWN")

_REGIME_COLUMNS: list[str] = [
    "regime",
    "n_trades",
    "win_rate_pct",
    "avg_pnl_pct",
    "total_pnl",
    "profit_factor",
    "share_of_gross_profit_pct",
]


@dataclass(frozen=True)
class RegimeConfig:
    """Settings for market-regime labelling and concentration analysis."""

    window: int = 50
    slope_threshold_pct: float = 2.0
    concentration_threshold: float = 0.6


def _prepare_price_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return *df* sorted by a DatetimeIndex, raising if no date is available."""
    if len(df) == 0:
        return df.copy()

    df_sorted = df.copy()
    if not isinstance(df_sorted.index, pd.DatetimeIndex):
        if "date" not in df_sorted.columns:
            raise ValueError("df must have a DatetimeIndex or a date column")
        df_sorted["date"] = pd.to_datetime(df_sorted["date"])
        df_sorted = df_sorted.set_index("date")

    return df_sorted.sort_index()


def _bucket_row(
    regime: str,
    mask: pd.Series,
    pnl: pd.Series,
    pnl_pct: pd.Series,
    gross_profit: float,
) -> dict[str, object] | None:
    """Return a bucket row for *regime* or None when no trades match."""
    if not mask.any():
        return None

    pnl_m = pnl.loc[mask]
    pnl_pct_m = pnl_pct.loc[mask]

    n_trades = int(mask.sum())
    wins = int((pnl_m > 0).sum())
    win_rate_pct = round(wins / n_trades * 100, 2)

    valid_pct = pnl_pct_m.dropna()
    avg_pnl_pct: float | None = None if valid_pct.empty else round(float(valid_pct.mean()), 4)

    total_pnl = round(float(pnl_m.sum()), 4)

    gross_wins = float(pnl_m[pnl_m > 0].sum())
    gross_losses = abs(float(pnl_m[pnl_m <= 0].sum()))
    profit_factor: float | None = None if gross_losses == 0 else round(gross_wins / gross_losses, 3)

    share = 0.0 if gross_profit <= 0 else round(gross_wins / gross_profit * 100, 2)

    return {
        "regime": regime,
        "n_trades": n_trades,
        "win_rate_pct": win_rate_pct,
        "avg_pnl_pct": avg_pnl_pct,
        "total_pnl": total_pnl,
        "profit_factor": profit_factor,
        "share_of_gross_profit_pct": share,
    }


def label_regimes(
    df: pd.DataFrame,
    config: RegimeConfig | None = None,
) -> pd.Series:
    """Label each bar of *df* with a market regime."""
    cfg = config if config is not None else RegimeConfig()

    if len(df) == 0:
        return pd.Series(dtype=object, name="regime")

    df_sorted = _prepare_price_df(df)
    if "close" not in df_sorted.columns:
        raise ValueError("df must contain a 'close' column")

    close = df_sorted["close"].astype(float)
    sma = close.rolling(cfg.window).mean()
    ref = sma.shift(cfg.window)
    slope_pct = (sma - ref) / ref * 100

    slope_arr = slope_pct.to_numpy(dtype=float)
    conditions = [
        np.isnan(slope_arr),
        slope_arr >= cfg.slope_threshold_pct,
        slope_arr <= -cfg.slope_threshold_pct,
    ]
    choices = ["UNKNOWN", "UPTREND", "DOWNTREND"]
    labels = np.select(conditions, choices, default="RANGE")

    return pd.Series(labels, index=df_sorted.index, dtype=object, name="regime")


def regime_buckets(
    trades: pd.DataFrame,
    regimes: pd.Series,
    config: RegimeConfig | None = None,
) -> pd.DataFrame:
    """Break down realized trades by the regime active at entry."""
    if len(trades) == 0:
        return pd.DataFrame(columns=_REGIME_COLUMNS)

    trade_dates = pd.DatetimeIndex(trades["entry_date"])
    assigned = pd.Series(
        regimes.reindex(trade_dates).fillna("UNKNOWN").to_numpy(),
        index=trades.index,
        dtype=object,
        name="regime",
    )

    pnl = pd.to_numeric(trades["pnl"], errors="coerce").fillna(0.0)
    pnl_pct = pd.to_numeric(trades["pnl_pct"], errors="coerce")

    gross_profit = float(pnl[pnl > 0].sum())

    rows: list[dict[str, object]] = []
    for regime in REGIME_ORDER:
        mask = assigned == regime
        row = _bucket_row(regime, mask, pnl, pnl_pct, gross_profit)
        if row is not None:
            rows.append(row)

    return pd.DataFrame(rows, columns=_REGIME_COLUMNS)


def regime_summary(
    trades: pd.DataFrame,
    regimes: pd.Series,
    config: RegimeConfig | None = None,
) -> dict[str, object]:
    """Summarize whether profits are concentrated in one regime."""
    cfg = config if config is not None else RegimeConfig()
    table = regime_buckets(trades, regimes, cfg)

    if table.empty:
        return {
            "n_regimes": 0,
            "dominant_regime": None,
            "dominant_share_pct": 0.0,
            "concentrated": False,
            "verdict": "NO_TRADES",
        }

    n_regimes = int(len(table))
    max_share = float(table["share_of_gross_profit_pct"].max())

    if max_share <= 0:
        return {
            "n_regimes": n_regimes,
            "dominant_regime": None,
            "dominant_share_pct": 0.0,
            "concentrated": False,
            "verdict": "SPREAD",
        }

    dominant_idx = table["share_of_gross_profit_pct"].idxmax()
    dominant_regime = str(table.at[dominant_idx, "regime"])
    dominant_share_pct = round(max_share, 2)

    concentrated = len(table) > 1 and dominant_share_pct >= cfg.concentration_threshold * 100
    verdict = "CONCENTRATED" if concentrated else "SPREAD"

    return {
        "n_regimes": n_regimes,
        "dominant_regime": dominant_regime,
        "dominant_share_pct": dominant_share_pct,
        "concentrated": concentrated,
        "verdict": verdict,
    }


def regime_breakdown(
    df: pd.DataFrame,
    trades: pd.DataFrame,
    config: RegimeConfig | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Label regimes and return both the bucket table and the summary."""
    cfg = config if config is not None else RegimeConfig()
    regimes = label_regimes(df, cfg)

    return (
        regime_buckets(trades, regimes, cfg),
        regime_summary(trades, regimes, cfg),
    )
