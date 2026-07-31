"""Side-by-side comparison of two metric dictionaries."""

from __future__ import annotations

from collections.abc import Mapping
from numbers import Real
from typing import Any

import pandas as pd

HIGHER_IS_BETTER: frozenset[str] = frozenset(
    {
        "total_return_pct",
        "cagr_pct",
        "sharpe",
        "win_rate_pct",
        "avg_win_pct",
        "avg_loss_pct",
        "profit_factor",
        "final_equity",
        "max_dd_pct",
        "sortino",
        "calmar",
        "recovery_factor",
    }
)

LOWER_IS_BETTER: frozenset[str] = frozenset(
    {
        "ulcer_index",
        "max_dd_duration_bars",
        "avg_drawdown_pct",
        "max_consecutive_losses",
    }
)

COMPARE_COLUMNS: list[str] = [
    "metric",
    "baseline",
    "candidate",
    "delta",
    "delta_pct",
    "direction",
    "better",
]


def _is_number(value: Any) -> bool:
    """Return True if value is a real number, treating bool as non-numeric."""
    return isinstance(value, Real) and not isinstance(value, bool)


def _direction(metric: str) -> str:
    """Classify the improvement direction for a metric."""
    if metric in HIGHER_IS_BETTER:
        return "higher_is_better"
    if metric in LOWER_IS_BETTER:
        return "lower_is_better"
    return "neutral"


def _better(delta: float, direction: str) -> bool | None:
    """Return whether the candidate is better, or None if tied/neutral."""
    if direction == "neutral" or delta == 0.0:
        return None
    if direction == "higher_is_better":
        return delta > 0.0
    return delta < 0.0


def compare_metrics(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> pd.DataFrame:
    """Return a DataFrame comparing two metric dictionaries side by side."""
    rows: list[dict[str, Any]] = []
    for key, base_value in baseline.items():
        if key not in candidate:
            continue
        cand_value = candidate[key]
        if not _is_number(base_value) or not _is_number(cand_value):
            continue
        base = float(base_value)
        cand = float(cand_value)
        delta = round(cand - base, 4)
        if base == 0.0:
            delta_pct: float | None = None
        else:
            delta_pct = round((cand - base) / abs(base) * 100, 2)
        direction = _direction(key)
        rows.append(
            {
                "metric": key,
                "baseline": base,
                "candidate": cand,
                "delta": delta,
                "delta_pct": delta_pct,
                "direction": direction,
                "better": _better(delta, direction),
            }
        )
    return pd.DataFrame(rows, columns=COMPARE_COLUMNS, dtype=object)


def _count_identity(series: pd.Series, value: Any) -> int:
    """Count entries that are exactly value by identity."""
    return int(series.apply(lambda x: x is value).sum())


def compare_summary(table: pd.DataFrame) -> dict[str, object]:
    """Summarise a comparison table into counts and an overall verdict."""
    if table.empty:
        return {
            "n_metrics": 0,
            "n_better": 0,
            "n_worse": 0,
            "n_tied": 0,
            "verdict": "NO_METRICS",
        }
    n_metrics = len(table)
    n_better = _count_identity(table["better"], True)
    n_worse = _count_identity(table["better"], False)
    n_tied = _count_identity(table["better"], None)
    if n_better > n_worse:
        verdict = "BETTER"
    elif n_better < n_worse:
        verdict = "WORSE"
    elif n_better + n_worse > 0:
        verdict = "MIXED"
    else:
        verdict = "TIED"
    return {
        "n_metrics": n_metrics,
        "n_better": n_better,
        "n_worse": n_worse,
        "n_tied": n_tied,
        "verdict": verdict,
    }


def compare_report(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Return both the comparison table and its summary."""
    table = compare_metrics(baseline, candidate)
    return table, compare_summary(table)
