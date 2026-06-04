from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from pinewf.indicators import add_signals, atr


@dataclass
class StrategyConfig:
    fast: int = 20
    slow: int = 50
    trend: int = 200
    ma_kind: str = "ema"
    use_trend_filter: bool = True
    stop_kind: str = "percent"
    stop_loss_pct: float = 8.0
    stop_atr_mult: float = 2.0
    atr_length: int = 14
    take_profit_pct: float | None = None
    trailing_pct: float | None = None
    chandelier_atr_mult: float | None = None
    initial: float = 10_000.0
    commission: float = 0.001
    slippage: float = 0.0005


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    equity: pd.Series


def run_backtest(df: pd.DataFrame, cfg: StrategyConfig) -> BacktestResult:
    """Run a long-only MA-cross strategy with Pine-like next-open fills."""
    if len(df) < 3:
        raise ValueError("at least three OHLCV bars are required")
    prepared = _prepare_bars(df, cfg)
    bars = prepared.reset_index()
    date_col = bars.columns[0]

    cash = float(cfg.initial)
    qty = 0.0
    in_pos = False
    entry_price = 0.0
    entry_equity = 0.0
    sl_price = 0.0
    peak_high = 0.0
    entry_date: pd.Timestamp | None = None
    entry_idx = -1
    pending_entry = False
    pending_exit = False
    trades: list[dict[str, object]] = []
    eq_records: list[tuple[pd.Timestamp, float]] = []

    for i, row in bars.iterrows():
        date = pd.Timestamp(row[date_col])

        if pending_exit and in_pos:
            cash, qty, in_pos = _close_position(
                trades,
                qty,
                row["open"],
                row["open"],
                cfg,
                entry_date,
                date,
                entry_price,
                entry_equity,
                i - entry_idx,
                "CROSS_DN",
            )
            pending_exit = False

        if pending_entry and not in_pos:
            effective_entry = row["open"] * (1 + cfg.slippage)
            cash_after_commission = cash * (1 - cfg.commission)
            qty = cash_after_commission / effective_entry
            entry_price = float(row["open"])
            entry_date = date
            entry_idx = i
            entry_equity = cash
            peak_high = float(row["high"])
            cash = 0.0
            sl_price = _initial_stop(row, bars, i, entry_price, cfg)
            in_pos = True
            pending_entry = False

        if in_pos:
            peak_high = max(peak_high, float(row["high"]))
            cur_sl = sl_price
            if cfg.trailing_pct is not None:
                cur_sl = max(cur_sl, peak_high * (1 - cfg.trailing_pct / 100))
            if cfg.chandelier_atr_mult is not None and not pd.isna(row["atr_custom"]):
                cur_sl = max(cur_sl, peak_high - cfg.chandelier_atr_mult * row["atr_custom"])

            tp_price = (
                entry_price * (1 + cfg.take_profit_pct / 100)
                if cfg.take_profit_pct is not None
                else None
            )
            exit_price, reason = _intrabar_exit(row, cur_sl, tp_price)
            if exit_price is not None:
                cash, qty, in_pos = _close_position(
                    trades,
                    qty,
                    exit_price,
                    exit_price,
                    cfg,
                    entry_date,
                    date,
                    entry_price,
                    entry_equity,
                    i - entry_idx,
                    reason or "EXIT",
                )
                pending_exit = False

        eq_records.append((date, cash + qty * float(row["close"])))

        if in_pos and bool(row["cross_dn"]):
            pending_exit = True
        elif (not in_pos) and bool(row["cross_up"]) and bool(row["trend_ok"]):
            pending_entry = True

    if in_pos:
        last = bars.iloc[-1]
        date = pd.Timestamp(last[date_col])
        cash, qty, in_pos = _close_position(
            trades,
            qty,
            float(last["close"]),
            float(last["close"]),
            cfg,
            entry_date,
            date,
            entry_price,
            entry_equity,
            len(bars) - 1 - entry_idx,
            "EOD",
        )
        eq_records[-1] = (date, cash)

    equity = pd.Series(
        [record[1] for record in eq_records],
        index=pd.DatetimeIndex([record[0] for record in eq_records], name="date"),
        name="equity",
    )
    return BacktestResult(trades=pd.DataFrame(trades, columns=_trade_columns()), equity=equity)


def _prepare_bars(df: pd.DataFrame, cfg: StrategyConfig) -> pd.DataFrame:
    data = df.copy()
    if not isinstance(data.index, pd.DatetimeIndex):
        if "date" not in data.columns:
            raise ValueError("df must have a DatetimeIndex or a date column")
        data["date"] = pd.to_datetime(data["date"])
        data = data.set_index("date")
    data = data.sort_index()
    out = add_signals(data, cfg.fast, cfg.slow, cfg.trend, cfg.ma_kind, cfg.use_trend_filter)
    out["atr_custom"] = atr(out, cfg.atr_length)
    return out


def _initial_stop(
    row: pd.Series, bars: pd.DataFrame, i: int, entry_price: float, cfg: StrategyConfig
) -> float:
    stop_kind = cfg.stop_kind.lower()
    if stop_kind == "percent":
        return entry_price * (1 - cfg.stop_loss_pct / 100)
    if stop_kind == "atr":
        atr_prev = bars.iloc[i - 1]["atr_custom"] if i > 0 else np.nan
        if pd.isna(atr_prev):
            return 0.0
        return entry_price - cfg.stop_atr_mult * float(atr_prev)
    if stop_kind == "none":
        return 0.0
    raise ValueError("stop_kind must be 'percent', 'atr', or 'none'")


def _intrabar_exit(
    row: pd.Series, cur_sl: float, tp_price: float | None
) -> tuple[float | None, str | None]:
    if cur_sl > 0 and row["open"] <= cur_sl:
        return float(row["open"]), "SL_GAP"
    if cur_sl > 0 and row["low"] <= cur_sl:
        return float(cur_sl), "SL/TRAIL"
    if tp_price is not None:
        if row["open"] >= tp_price:
            return float(row["open"]), "TP_GAP"
        if row["high"] >= tp_price:
            return float(tp_price), "TP"
    return None, None


def _close_position(
    trades: list[dict[str, object]],
    qty: float,
    effective_source_price: float,
    reported_exit_price: float,
    cfg: StrategyConfig,
    entry_date: pd.Timestamp | None,
    exit_date: pd.Timestamp,
    entry_price: float,
    entry_equity: float,
    bars_held: int,
    reason: str,
) -> tuple[float, float, bool]:
    if entry_date is None:
        raise RuntimeError("cannot close position without an entry")
    exit_effective = effective_source_price * (1 - cfg.slippage)
    proceeds = qty * exit_effective * (1 - cfg.commission)
    pnl = proceeds - entry_equity
    trades.append(
        {
            "entry_date": entry_date,
            "exit_date": exit_date,
            "entry_price": entry_price,
            "exit_price": reported_exit_price,
            "pnl": pnl,
            "pnl_pct": pnl / entry_equity * 100 if entry_equity else 0.0,
            "reason": reason,
            "bars_held": bars_held,
        }
    )
    return proceeds, 0.0, False


def _trade_columns() -> list[str]:
    return [
        "entry_date",
        "exit_date",
        "entry_price",
        "exit_price",
        "pnl",
        "pnl_pct",
        "reason",
        "bars_held",
    ]
