from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from pinewf.pine_csv import parse_tradingview_trades

DEFAULT_BUCKETS: tuple[float, ...] = (1.0, 3.0, 5.0, 10.0, 20.0)
"""Right edges (inclusive) of holding-duration buckets, in bars or days."""


@dataclass(frozen=True)
class SensitivityConfig:
    """Settings for holding-period sensitivity analysis."""

    buckets: tuple[float, ...] = DEFAULT_BUCKETS
    concentration_threshold: float = 0.6
    """Flag if a single bucket holds at least this fraction of gross profit."""


def load_trades(path: str | Path) -> pd.DataFrame:
    """Load trades from a generic engine CSV or a TradingView export."""
    csv_path = Path(path)
    raw = pd.read_csv(csv_path)
    lower = {str(col).strip().lower() for col in raw.columns}
    if {"pnl", "entry_date", "exit_date"}.issubset(lower) or "bars_held" in lower:
        raw.columns = [str(col).strip().lower() for col in raw.columns]
        return raw
    return parse_tradingview_trades(csv_path)


def holding_durations(trades: pd.DataFrame) -> pd.Series:
    """Return a holding-duration series, preferring bars_held over calendar days."""
    if trades.empty:
        return pd.Series(dtype=float)
    if "bars_held" in trades:
        bars = pd.to_numeric(trades["bars_held"], errors="coerce")
        if bars.notna().any():
            return bars.astype(float)
    if {"entry_date", "exit_date"}.issubset(trades.columns):
        entry = pd.to_datetime(trades["entry_date"], errors="coerce")
        exit_ = pd.to_datetime(trades["exit_date"], errors="coerce")
        days = (exit_ - entry).dt.total_seconds() / 86_400.0
        return days.astype(float)
    raise ValueError("trades need a bars_held column or entry_date/exit_date columns")


def _bucket_labels(buckets: tuple[float, ...]) -> list[str]:
    labels: list[str] = []
    prev = 0.0
    for edge in buckets:
        labels.append(f"<={edge:g}")
        prev = edge
    labels.append(f">{prev:g}")
    return labels


def _assign_bucket(duration: float, buckets: tuple[float, ...]) -> str:
    labels = _bucket_labels(buckets)
    for index, edge in enumerate(buckets):
        if duration <= edge:
            return labels[index]
    return labels[-1]


def duration_buckets(trades: pd.DataFrame, config: SensitivityConfig | None = None) -> pd.DataFrame:
    """Bucket realized trades by holding duration and compute per-bucket metrics."""
    cfg = config or SensitivityConfig()
    labels = _bucket_labels(cfg.buckets)
    columns = [
        "bucket",
        "n_trades",
        "win_rate_pct",
        "avg_pnl_pct",
        "total_pnl",
        "profit_factor",
        "share_of_gross_profit_pct",
    ]
    if trades.empty:
        return pd.DataFrame(columns=columns)

    work = trades.copy()
    work["duration"] = holding_durations(work)
    work = work[work["duration"].notna()]
    if work.empty:
        return pd.DataFrame(columns=columns)

    pnl_pct = (
        pd.to_numeric(work["pnl_pct"], errors="coerce")
        if "pnl_pct" in work
        else pd.Series(np.nan, index=work.index)
    )
    pnl = pd.to_numeric(work["pnl"], errors="coerce") if "pnl" in work else pnl_pct.fillna(0.0)
    work = work.assign(_pnl=pnl.fillna(0.0), _pnl_pct=pnl_pct)
    work["bucket"] = work["duration"].map(lambda d: _assign_bucket(float(d), cfg.buckets))

    gross_profit = float(work.loc[work["_pnl"] > 0, "_pnl"].sum())
    rows: list[dict[str, object]] = []
    for label in labels:
        group = work[work["bucket"] == label]
        if group.empty:
            continue
        wins = group[group["_pnl"] > 0]
        losses = group[group["_pnl"] <= 0]
        gross_wins = float(wins["_pnl"].sum())
        gross_losses = abs(float(losses["_pnl"].sum()))
        profit_factor = round(gross_wins / gross_losses, 3) if gross_losses else None
        share = gross_wins / gross_profit * 100 if gross_profit > 0 else 0.0
        rows.append(
            {
                "bucket": label,
                "n_trades": int(len(group)),
                "win_rate_pct": round(len(wins) / len(group) * 100, 2),
                "avg_pnl_pct": round(float(group["_pnl_pct"].mean()), 4)
                if group["_pnl_pct"].notna().any()
                else None,
                "total_pnl": round(float(group["_pnl"].sum()), 4),
                "profit_factor": profit_factor,
                "share_of_gross_profit_pct": round(float(share), 2),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def duration_sensitivity(
    trades: pd.DataFrame, config: SensitivityConfig | None = None
) -> dict[str, object]:
    """Summarize duration buckets and flag edge concentrated in one holding band."""
    cfg = config or SensitivityConfig()
    table = duration_buckets(trades, cfg)
    if table.empty:
        return {
            "n_buckets": 0,
            "dominant_bucket": None,
            "dominant_share_pct": 0.0,
            "concentrated": False,
            "verdict": "NO_TRADES",
        }
    shares = table.set_index("bucket")["share_of_gross_profit_pct"].astype(float)
    if shares.max() <= 0:
        dominant = None
        dominant_share = 0.0
    else:
        dominant = str(shares.idxmax())
        dominant_share = float(shares.max())
    concentrated = (
        dominant is not None
        and len(table) > 1
        and dominant_share >= cfg.concentration_threshold * 100
    )
    verdict = "CONCENTRATED" if concentrated else "SPREAD"
    return {
        "n_buckets": int(len(table)),
        "dominant_bucket": dominant,
        "dominant_share_pct": round(dominant_share, 2),
        "concentrated": bool(concentrated),
        "verdict": verdict,
    }


def sensitivity_from_csv(
    path: str | Path, config: SensitivityConfig | None = None
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Load a trade CSV and return per-bucket metrics plus a concentration summary."""
    trades = load_trades(path)
    cfg = config or SensitivityConfig()
    return duration_buckets(trades, cfg), duration_sensitivity(trades, cfg)
