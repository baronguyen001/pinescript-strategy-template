"""Walk-forward companion for parameterized Pine Script strategies."""

from pinewf.engine import BacktestResult, StrategyConfig, run_backtest
from pinewf.metrics import buy_hold_metrics, compute_metrics
from pinewf.montecarlo import (
    MonteCarloConfig,
    equity_path_bands,
    load_trade_returns,
    monte_carlo_figure,
    percentile_bands,
    render_monte_carlo_png,
    run_monte_carlo,
    simulate_trade_returns,
)
from pinewf.risk import (
    max_consecutive_losses,
    max_drawdown_duration_bars,
    risk_metrics,
    sortino_ratio,
    ulcer_index,
)
from pinewf.sensitivity import (
    SensitivityConfig,
    duration_buckets,
    duration_sensitivity,
    sensitivity_from_csv,
)
from pinewf.walk_forward import (
    WFWindow,
    consistency,
    rolling_windows,
    walk_forward_optimize,
    walk_forward_replay,
)

__all__ = [
    "BacktestResult",
    "MonteCarloConfig",
    "SensitivityConfig",
    "StrategyConfig",
    "WFWindow",
    "buy_hold_metrics",
    "compute_metrics",
    "consistency",
    "duration_buckets",
    "duration_sensitivity",
    "equity_path_bands",
    "load_trade_returns",
    "max_consecutive_losses",
    "max_drawdown_duration_bars",
    "monte_carlo_figure",
    "percentile_bands",
    "render_monte_carlo_png",
    "risk_metrics",
    "rolling_windows",
    "run_backtest",
    "run_monte_carlo",
    "sensitivity_from_csv",
    "sortino_ratio",
    "ulcer_index",
    "simulate_trade_returns",
    "walk_forward_optimize",
    "walk_forward_replay",
]
