from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pinewf.pine_csv import parse_tradingview_trades


@dataclass(frozen=True)
class MonteCarloConfig:
    """Simulation settings for realized trade-return robustness checks."""

    initial: float = 10_000.0
    iters: int = 1_000
    seed: int | None = None


def load_trade_returns(path: str | Path) -> np.ndarray:
    """Load realized trade returns from a generic or TradingView trade CSV."""
    csv_path = Path(path)
    raw = pd.read_csv(csv_path)
    if raw.empty:
        return np.array([], dtype=float)

    normalized = {str(col).strip().lower(): str(col) for col in raw.columns}
    for candidate in ("pnl_pct", "pnl %", "return_pct", "return %", "net p&l %", "net pnl %"):
        if candidate in normalized:
            series = raw[normalized[candidate]].dropna().map(_as_float)
            return series.to_numpy(dtype=float) / 100.0

    trades = parse_tradingview_trades(csv_path)
    if "pnl_pct" not in trades:
        raise ValueError("could not find a trade-return percentage column")
    return trades["pnl_pct"].dropna().to_numpy(dtype=float) / 100.0


def simulate_trade_returns(returns: np.ndarray, config: MonteCarloConfig) -> pd.DataFrame:
    """Run trade-order shuffle and bootstrap simulations over realized returns."""
    if config.iters < 1:
        raise ValueError("iters must be at least 1")
    if config.initial <= 0:
        raise ValueError("initial must be positive")

    clean = np.asarray(returns, dtype=float)
    clean = clean[np.isfinite(clean)]
    rng = np.random.default_rng(config.seed)
    rows: list[dict[str, float | int | str]] = []

    for method in ("shuffle", "bootstrap"):
        for iteration in range(config.iters):
            path = _sample_path(clean, method, rng)
            stats = _path_stats(path, config.initial)
            rows.append({"method": method, "iteration": iteration, **stats})
    return pd.DataFrame(rows)


def percentile_bands(simulations: pd.DataFrame) -> pd.DataFrame:
    """Summarize final equity, max drawdown, and Sharpe into 5/50/95 bands."""
    if simulations.empty:
        return pd.DataFrame(columns=["method", "metric", "p05", "p50", "p95"])

    rows: list[dict[str, float | str]] = []
    for method, group in simulations.groupby("method", sort=False):
        for metric in ("final_equity", "max_dd_pct", "sharpe"):
            values = group[metric].astype(float).to_numpy()
            p05, p50, p95 = np.percentile(values, [5, 50, 95])
            rows.append(
                {
                    "method": str(method),
                    "metric": metric,
                    "p05": round(float(p05), 4),
                    "p50": round(float(p50), 4),
                    "p95": round(float(p95), 4),
                }
            )
    return pd.DataFrame(rows)


def run_monte_carlo(
    path: str | Path, config: MonteCarloConfig
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load a trade CSV and return raw simulations plus percentile bands."""
    simulations = simulate_trade_returns(load_trade_returns(path), config)
    return simulations, percentile_bands(simulations)


def equity_path_bands(
    returns: np.ndarray, config: MonteCarloConfig, method: str = "bootstrap"
) -> pd.DataFrame:
    """Build per-step 5/50/95 equity-curve percentile bands across simulated paths."""
    if config.iters < 1:
        raise ValueError("iters must be at least 1")
    if config.initial <= 0:
        raise ValueError("initial must be positive")
    clean = np.asarray(returns, dtype=float)
    clean = clean[np.isfinite(clean)]
    n = clean.size
    rng = np.random.default_rng(config.seed)
    paths = np.empty((config.iters, n + 1), dtype=float)
    for i in range(config.iters):
        sampled = _sample_path(clean, method, rng)
        paths[i] = _equity_path(sampled, config.initial)
    p05, p50, p95 = np.percentile(paths, [5, 50, 95], axis=0)
    return pd.DataFrame(
        {
            "trade": np.arange(n + 1),
            "p05": np.round(p05, 4),
            "p50": np.round(p50, 4),
            "p95": np.round(p95, 4),
        }
    )


def monte_carlo_figure(bands: pd.DataFrame, method: str = "bootstrap") -> Any:
    """Return a matplotlib Figure of the equity percentile band (requires [viz])."""
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    x = bands["trade"].to_numpy()
    ax.fill_between(x, bands["p05"], bands["p95"], color="#4c78a8", alpha=0.25, label="5-95% band")
    ax.plot(x, bands["p50"], color="#4c78a8", linewidth=2, label="Median")
    ax.set_title(f"Monte Carlo Equity Bands ({method})")
    ax.set_xlabel("Trade")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    return fig


def render_monte_carlo_png(
    path: str | Path,
    config: MonteCarloConfig,
    out_path: str | Path,
    method: str = "bootstrap",
) -> Path:
    """Render the Monte Carlo equity-band chart from a trade CSV to a PNG file."""
    bands = equity_path_bands(load_trade_returns(path), config, method)
    fig = monte_carlo_figure(bands, method)
    out = Path(out_path)
    fig.savefig(out, format="png", dpi=140)
    _close(fig)
    return out


def _pyplot() -> Any:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "Monte Carlo PNG export requires: pip install pinescript-walkforward[viz]"
        ) from exc
    return plt


def _close(fig: Any) -> None:
    plt = _pyplot()
    plt.close(fig)


def _sample_path(returns: np.ndarray, method: str, rng: np.random.Generator) -> np.ndarray:
    if returns.size == 0:
        return returns.copy()
    if method == "shuffle":
        return rng.permutation(returns)
    if method == "bootstrap":
        return rng.choice(returns, size=returns.size, replace=True)
    raise ValueError(f"unknown method: {method}")


def _path_stats(returns: np.ndarray, initial: float) -> dict[str, float | int]:
    equity = _equity_path(returns, initial)
    drawdown = equity / np.maximum.accumulate(equity) - 1
    sharpe = _trade_sharpe(returns)
    return {
        "n_trades": int(returns.size),
        "final_equity": round(float(equity[-1]), 4),
        "total_return_pct": round(float(equity[-1] / initial - 1) * 100, 4),
        "max_dd_pct": round(float(drawdown.min()) * 100, 4),
        "sharpe": round(sharpe, 4),
    }


def _equity_path(returns: np.ndarray, initial: float) -> np.ndarray:
    if returns.size == 0:
        return np.array([initial], dtype=float)
    return np.concatenate(([initial], initial * np.cumprod(1 + returns)))


def _trade_sharpe(returns: np.ndarray) -> float:
    if returns.size < 2:
        return 0.0
    std = float(returns.std(ddof=1))
    if std < 1e-12:
        return 0.0
    return float(returns.mean() / std * np.sqrt(returns.size))


def _as_float(value: object) -> float:
    text = str(value).replace("\u00a0", " ").strip()
    for token in ("USDT", "USD", "$", "%"):
        text = text.replace(token, "")
    text = text.replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    return float(text)
