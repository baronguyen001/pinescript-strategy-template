from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd

from pinewf.engine import StrategyConfig, run_backtest
from pinewf.grid import param_grid
from pinewf.metrics import buy_hold_metrics, compute_metrics


@dataclass
class WFWindow:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def rolling_windows(
    index: pd.DatetimeIndex,
    train_years: float = 2.0,
    test_years: float = 1.0,
    step_years: float | None = None,
) -> list[WFWindow]:
    """Build rolling train/test windows; optionally delegates if a sibling splitter exists."""
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError("index must be a DatetimeIndex")
    try:
        import walkforward

        splitter = getattr(walkforward, "rolling_windows", None)
        if splitter is not None:
            return list(
                splitter(
                    index, train_years=train_years, test_years=test_years, step_years=step_years
                )
            )
    except Exception:
        pass

    idx = index.sort_values()
    if idx.empty:
        return []
    step = step_years if step_years is not None else test_years
    start = idx[0]
    last = idx[-1]
    windows: list[WFWindow] = []
    while True:
        train_start = start
        train_end = train_start + pd.DateOffset(days=round(train_years * 365.25))
        test_start = train_end
        test_end = test_start + pd.DateOffset(days=round(test_years * 365.25))
        if test_end > last:
            break
        windows.append(WFWindow(train_start, train_end, test_start, test_end))
        start = start + pd.DateOffset(days=round(step * 365.25))
    return windows


def walk_forward_replay(
    df: pd.DataFrame, cfg: StrategyConfig, train_years: float = 2.0, test_years: float = 1.0
) -> pd.DataFrame:
    """Evaluate fixed user parameters on each out-of-sample window."""
    data = _ensure_dt_index(df)
    rows: list[dict[str, Any]] = []
    for window in rolling_windows(data.index, train_years, test_years):
        sub = data.loc[window.train_start : window.test_end]
        test = data.loc[window.test_start : window.test_end]
        if len(test) < 2:
            continue
        result = run_backtest(sub, cfg)
        eq_test = result.equity.loc[window.test_start : window.test_end]
        if len(eq_test) < 2:
            continue
        eq_norm = eq_test / eq_test.iloc[0] * cfg.initial
        trades = _slice_trades(result.trades, window.test_start, window.test_end)
        strat = compute_metrics(eq_norm, trades, cfg.initial, len(test), "strategy")
        bh = buy_hold_metrics(test, cfg.initial, cfg.commission, cfg.slippage)
        rows.append(_wf_row(window, strat, bh, trades))
    return pd.DataFrame(rows)


def walk_forward_optimize(
    df: pd.DataFrame,
    grid: dict[str, list],
    base: StrategyConfig,
    train_years: float = 2.0,
    test_years: float = 1.0,
    select_by: str = "sharpe",
) -> pd.DataFrame:
    """Grid-search on each train span, then score the chosen config out-of-sample."""
    data = _ensure_dt_index(df)
    rows: list[dict[str, Any]] = []
    for window in rolling_windows(data.index, train_years, test_years):
        train = data.loc[window.train_start : window.train_end]
        test = data.loc[window.test_start : window.test_end]
        if len(train) < 3 or len(test) < 2:
            continue
        ranked = param_grid(train, grid, base, select_by)
        best = ranked.iloc[0].to_dict()
        params = {key: best[key] for key in grid if key in best}
        cfg = replace(base, **_normalize_grid_params(params))
        result = run_backtest(data.loc[window.train_start : window.test_end], cfg)
        eq_test = result.equity.loc[window.test_start : window.test_end]
        if len(eq_test) < 2:
            continue
        eq_norm = eq_test / eq_test.iloc[0] * cfg.initial
        trades = _slice_trades(result.trades, window.test_start, window.test_end)
        strat = compute_metrics(eq_norm, trades, cfg.initial, len(test), "strategy")
        bh = buy_hold_metrics(test, cfg.initial, cfg.commission, cfg.slippage)
        train_score = float(best.get(select_by, np.nan))
        test_score = float(strat.get(select_by, np.nan))
        degradation = (
            (train_score - test_score) / abs(train_score) * 100
            if np.isfinite(train_score) and train_score != 0 and np.isfinite(test_score)
            else np.nan
        )
        row = _wf_row(window, strat, bh, trades)
        row.update(
            {
                "chosen_params": _format_params(params),
                "train_score": round(train_score, 3),
                "test_score": round(test_score, 3),
                "degradation_%": round(float(degradation), 2)
                if np.isfinite(degradation)
                else np.nan,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def consistency(report: pd.DataFrame) -> dict:
    """Summarize OOS consistency using simple documented heuristics."""
    if report.empty:
        return {
            "frac_beats_bh": 0.0,
            "frac_lower_dd": 0.0,
            "mean_oos_return_%": 0.0,
            "mean_oos_sharpe": None,
            "mean_degradation_%": None,
            "verdict": "NO_WINDOWS",
        }
    frac_beats = float(report["beats_bh"].mean())
    frac_lower_dd = float(report["lower_dd"].mean())
    mean_return = float(report["strat_return_%"].mean())
    mean_sharpe = float(report["strat_sharpe"].mean()) if "strat_sharpe" in report else None
    mean_degradation = (
        float(report["degradation_%"].dropna().mean()) if "degradation_%" in report else None
    )
    if frac_beats >= 0.6 and (mean_degradation is None or mean_degradation < 30):
        verdict = "ROBUST"
    elif mean_degradation is not None and mean_degradation >= 50:
        verdict = "OVERFIT"
    else:
        verdict = "FRAGILE"
    return {
        "frac_beats_bh": round(frac_beats, 3),
        "frac_lower_dd": round(frac_lower_dd, 3),
        "mean_oos_return_%": round(mean_return, 2),
        "mean_oos_sharpe": round(mean_sharpe, 3) if mean_sharpe is not None else None,
        "mean_degradation_%": round(mean_degradation, 2) if mean_degradation is not None else None,
        "verdict": verdict,
    }


def _wf_row(window: WFWindow, strat: dict, bh: dict, trades: pd.DataFrame) -> dict[str, Any]:
    return {
        "test_start": window.test_start.date().isoformat(),
        "test_end": window.test_end.date().isoformat(),
        "strat_return_%": strat["total_return_pct"],
        "bh_return_%": bh["total_return_pct"],
        "strat_dd_%": strat["max_dd_pct"],
        "bh_dd_%": bh["max_dd_pct"],
        "strat_sharpe": strat["sharpe"],
        "beats_bh": strat["total_return_pct"] > bh["total_return_pct"],
        "lower_dd": strat["max_dd_pct"] > bh["max_dd_pct"],
        "n_trades": int(len(trades)),
    }


def _ensure_dt_index(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    if not isinstance(data.index, pd.DatetimeIndex):
        data["date"] = pd.to_datetime(data["date"])
        data = data.set_index("date")
    return data.sort_index()


def _slice_trades(trades: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if trades.empty:
        return trades
    exit_dates = pd.to_datetime(trades["exit_date"])
    return trades[(exit_dates >= start) & (exit_dates <= end)].copy()


def _normalize_grid_params(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(params)
    if "sl" in out:
        out["stop_loss_pct"] = out.pop("sl")
    if "ma" in out:
        out["ma_kind"] = out.pop("ma")
    return out


def _format_params(params: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(params.items()))
