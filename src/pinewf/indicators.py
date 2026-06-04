from __future__ import annotations

import pandas as pd


def moving_average(series: pd.Series, length: int, kind: str = "ema") -> pd.Series:
    """Return a simple or exponential moving average."""
    if length < 1:
        raise ValueError("length must be positive")
    kind_norm = kind.lower()
    if kind_norm == "sma":
        return series.rolling(length).mean()
    if kind_norm == "ema":
        return series.ewm(span=length, adjust=False).mean()
    raise ValueError("kind must be 'sma' or 'ema'")


def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average true range using the same rolling TR definition as the Pine template."""
    _require_columns(df, {"high", "low", "close"})
    prev_close = df["close"].shift()
    true_range = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(length).mean()


def add_signals(
    df: pd.DataFrame,
    fast: int,
    slow: int,
    trend: int,
    kind: str = "ema",
    use_trend_filter: bool = True,
) -> pd.DataFrame:
    """Add moving averages, ATR, cross signals, and trend filter columns."""
    _require_columns(df, {"open", "high", "low", "close", "volume"})
    if slow <= fast:
        raise ValueError("slow must be greater than fast")
    out = df.copy()
    out["fast"] = moving_average(out["close"], fast, kind)
    out["slow"] = moving_average(out["close"], slow, kind)
    out["trend_ma"] = moving_average(out["close"], trend, kind)
    out["atr14"] = atr(out, 14)
    out["cross_up"] = (out["fast"] > out["slow"]) & (out["fast"].shift(1) <= out["slow"].shift(1))
    out["cross_dn"] = (out["fast"] < out["slow"]) & (out["fast"].shift(1) >= out["slow"].shift(1))
    out["trend_ok"] = True if not use_trend_filter else out["close"] > out["trend_ma"]
    return out


def _require_columns(df: pd.DataFrame, columns: set[str]) -> None:
    missing = columns.difference(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")
