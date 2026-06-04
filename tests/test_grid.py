import numpy as np
import pandas as pd

from pinewf.engine import StrategyConfig
from pinewf.grid import param_grid


def sample_df() -> pd.DataFrame:
    idx = pd.date_range("2020-01-01", periods=260, freq="D")
    close = 100 + np.sin(np.arange(260) / 8) * 6 + np.arange(260) * 0.08
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 2,
            "low": close - 2,
            "close": close,
            "volume": np.ones(260),
        },
        index=idx,
    )


def test_param_grid_returns_ranked_rows() -> None:
    report = param_grid(
        sample_df(),
        {"fast": [5, 10], "slow": [20, 30], "sl": [6, 8]},
        StrategyConfig(trend=50, use_trend_filter=False),
    )
    assert len(report) == 8
    assert "overfit_warning" in report.columns
