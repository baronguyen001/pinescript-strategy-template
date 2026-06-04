"""Walk-forward companion for parameterized Pine Script strategies."""

from pinewf.engine import BacktestResult, StrategyConfig, run_backtest
from pinewf.metrics import buy_hold_metrics, compute_metrics
from pinewf.walk_forward import (
    WFWindow,
    consistency,
    rolling_windows,
    walk_forward_optimize,
    walk_forward_replay,
)

__all__ = [
    "BacktestResult",
    "StrategyConfig",
    "WFWindow",
    "buy_hold_metrics",
    "compute_metrics",
    "consistency",
    "rolling_windows",
    "run_backtest",
    "walk_forward_optimize",
    "walk_forward_replay",
]
