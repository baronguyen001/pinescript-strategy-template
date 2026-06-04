import numpy as np
import pandas as pd

from pinewf.engine import StrategyConfig
from pinewf.walk_forward import (
    consistency,
    rolling_windows,
    walk_forward_optimize,
    walk_forward_replay,
)


def wf_df() -> pd.DataFrame:
    idx = pd.date_range("2018-01-01", periods=6 * 365, freq="D")
    x = np.arange(len(idx))
    close = 100 + np.sin(x / 20) * 8 + x * 0.03
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": np.ones(len(idx)),
        },
        index=idx,
    )


def test_rolling_windows_boundaries() -> None:
    windows = rolling_windows(wf_df().index, train_years=2, test_years=1)
    assert windows
    assert windows[0].train_start == pd.Timestamp("2018-01-01")
    assert windows[0].test_start > windows[0].train_start


def test_walk_forward_replay_and_consistency() -> None:
    report = walk_forward_replay(
        wf_df(),
        StrategyConfig(fast=5, slow=20, trend=50, use_trend_filter=False),
        train_years=2,
        test_years=1,
    )
    assert not report.empty
    assert {"beats_bh", "lower_dd", "n_trades"}.issubset(report.columns)
    assert consistency(report)["verdict"] in {"ROBUST", "FRAGILE", "OVERFIT"}


def test_walk_forward_optimize_selects_train_best_and_scores_test() -> None:
    report = walk_forward_optimize(
        wf_df(),
        {"fast": [5, 8], "slow": [20, 30], "sl": [6, 8]},
        StrategyConfig(trend=50, use_trend_filter=False),
        train_years=2,
        test_years=1,
    )
    assert not report.empty
    assert "chosen_params" in report.columns
    assert "degradation_%" in report.columns
