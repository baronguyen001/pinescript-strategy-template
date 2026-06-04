from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


def load_ohlcv(path: str | Path) -> pd.DataFrame:
    """Load a CSV with date, open, high, low, close, volume into a DatetimeIndex."""
    df = pd.read_csv(path)
    df.columns = [str(col).strip().lower() for col in df.columns]
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"missing required columns: {', '.join(sorted(missing))}")
    df["date"] = pd.to_datetime(df["date"], utc=True).dt.tz_convert(None)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="raise")
    return df[["date", "open", "high", "low", "close", "volume"]].set_index("date").sort_index()


def fetch_binance_klines(
    symbol: str,
    interval: str = "1d",
    start: str | None = None,
    cache_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Fetch public Binance klines without an API key; bring your own CSV for other markets."""
    start_ms = int(pd.Timestamp(start or "2020-01-01", tz="UTC").timestamp() * 1000)
    rows: list[list] = []
    current = start_ms
    while True:
        query = urlencode(
            {
                "symbol": symbol.upper(),
                "interval": interval,
                "startTime": current,
                "limit": 1000,
            }
        )
        with urlopen(f"https://api.binance.com/api/v3/klines?{query}", timeout=30) as response:
            chunk = pd.read_json(response.read()).values.tolist()
        if not chunk:
            break
        rows.extend(chunk)
        if len(chunk) < 1000:
            break
        current = int(chunk[-1][0]) + 1
        time.sleep(0.15)
    df = pd.DataFrame(
        rows,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )
    df["date"] = pd.to_datetime(df["open_time"], unit="ms", utc=True).dt.tz_convert(None)
    out = df[["date", "open", "high", "low", "close", "volume"]].copy()
    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = out[col].astype(float)
    out = out.set_index("date")
    if cache_dir is not None:
        path = Path(cache_dir)
        path.mkdir(parents=True, exist_ok=True)
        out.to_csv(path / f"{symbol.upper()}_{interval}.csv")
    return out
