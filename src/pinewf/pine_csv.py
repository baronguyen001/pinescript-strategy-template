from __future__ import annotations

from pathlib import Path
from typing import cast

import pandas as pd

from pinewf.metrics import compute_metrics


def parse_tradingview_trades(path: str | Path) -> pd.DataFrame:
    """Parse TradingView Strategy Tester List of Trades CSV exports."""
    raw = pd.read_csv(path)
    if raw.empty:
        return pd.DataFrame(columns=_columns())
    price_col = _find_col(raw, ["price"])
    type_col = _find_col(raw, ["type"])
    date_col = _find_col(raw, ["date/time", "date", "time"])
    pnl_col = _find_col(raw, ["net p&l", "net pnl", "profit"], required=False)

    rows: list[dict[str, object]] = []
    pending: dict[str, object] | None = None
    for _, row in raw.iterrows():
        typ = str(row[type_col]).lower()
        price = _num(row[price_col])
        date = pd.to_datetime(row[date_col])
        if "entry" in typ:
            pending = {"entry_date": date, "entry_price": price}
        elif "exit" in typ and pending is not None:
            pnl = _num(row[pnl_col]) if pnl_col else None
            pnl_pct = _extract_pct(row, raw.columns)
            entry_price = cast(float, pending["entry_price"])
            if pnl_pct is None and entry_price:
                pnl_pct = (price / entry_price - 1) * 100
            rows.append(
                {
                    "entry_date": pending["entry_date"],
                    "exit_date": date,
                    "entry_price": entry_price,
                    "exit_price": price,
                    "pnl": pnl if pnl is not None else 0.0,
                    "pnl_pct": pnl_pct if pnl_pct is not None else 0.0,
                    "bars_held": float("nan"),
                }
            )
            pending = None
    return pd.DataFrame(rows, columns=_columns())


def metrics_from_pine_export(path: str | Path, initial: float = 10_000.0) -> dict:
    """Compute metrics from a TradingView trade export."""
    trades = parse_tradingview_trades(path)
    if trades.empty:
        equity = pd.Series(
            [initial], index=pd.DatetimeIndex([pd.Timestamp.utcnow().tz_localize(None)])
        )
        return compute_metrics(equity, trades, initial, 1, "tradingview_export")
    equity_values = [initial]
    dates = [pd.to_datetime(trades["entry_date"].iloc[0])]
    current = initial
    for _, trade in trades.iterrows():
        current += float(trade["pnl"])
        dates.append(pd.to_datetime(trade["exit_date"]))
        equity_values.append(current)
    equity = pd.Series(equity_values, index=pd.DatetimeIndex(dates), name="equity")
    return compute_metrics(equity, trades, initial, max(len(trades), 1), "tradingview_export")


def _find_col(df: pd.DataFrame, needles: list[str], required: bool = True) -> str | None:
    for col in df.columns:
        low = str(col).strip().lower()
        if any(needle in low for needle in needles):
            return str(col)
    if required:
        raise ValueError(f"could not find a column matching: {', '.join(needles)}")
    return None


def _num(value: object) -> float:
    text = str(value).replace("\u00a0", " ").strip()
    for token in ["USDT", "USD", "$", "%"]:
        text = text.replace(token, "")
    text = text.replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    return float(text)


def _extract_pct(row: pd.Series, columns: pd.Index) -> float | None:
    for col in columns:
        low = str(col).lower()
        if "net p&l %" in low or "net pnl %" in low or low.endswith("%"):
            return _num(row[col])
    return None


def _columns() -> list[str]:
    return ["entry_date", "exit_date", "entry_price", "exit_price", "pnl", "pnl_pct", "bars_held"]
