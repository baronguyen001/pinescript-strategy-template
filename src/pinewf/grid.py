from __future__ import annotations

from dataclasses import replace
from itertools import product
from typing import Any

import pandas as pd

from pinewf.engine import StrategyConfig, run_backtest
from pinewf.metrics import compute_metrics


def param_grid(
    df: pd.DataFrame, grid: dict[str, list], base: StrategyConfig, rank_by: str = "sharpe"
) -> pd.DataFrame:
    """Run a full in-sample grid and rank every parameter combination."""
    rows: list[dict[str, Any]] = []
    keys = list(grid.keys())
    for values in product(*(grid[key] for key in keys)):
        params = dict(zip(keys, values, strict=True))
        if "slow" in params and "fast" in params and params["slow"] <= params["fast"]:
            continue
        cfg = replace(base, **_normalize_params(params))
        result = run_backtest(df, cfg)
        metrics = compute_metrics(result.equity, result.trades, cfg.initial, len(df), "grid")
        rows.append({**params, **metrics})
    if not rows:
        raise ValueError("grid produced no valid combinations")
    report = pd.DataFrame(rows).sort_values(rank_by, ascending=False).reset_index(drop=True)
    report["overfit_warning"] = _overfit_warning(report, rank_by)
    return report


def _normalize_params(params: dict[str, Any]) -> dict[str, Any]:
    out = dict(params)
    if "sl" in out:
        out["stop_loss_pct"] = out.pop("sl")
    if "ma" in out:
        out["ma_kind"] = out.pop("ma")
    return out


def _overfit_warning(report: pd.DataFrame, rank_by: str) -> str:
    if len(report) < 4:
        return "small grid; confirm with walk-forward"
    top = float(report[rank_by].iloc[0])
    near_top = report.head(min(5, len(report)))[rank_by].astype(float)
    median_near = float(near_top.iloc[1:].median())
    if top > 0 and median_near < top * 0.6:
        return "top result is isolated; confirm out-of-sample"
    return "use walk-forward before trusting in-sample ranks"
