from pathlib import Path

import numpy as np

from pinewf.cli import main
from pinewf.montecarlo import (
    MonteCarloConfig,
    load_trade_returns,
    percentile_bands,
    run_monte_carlo,
    simulate_trade_returns,
)


def test_load_trade_returns_from_tradingview_export() -> None:
    returns = load_trade_returns(Path("examples/sample_tradingview_export.csv"))
    assert np.allclose(returns, [0.08, -0.05, 0.10])


def test_monte_carlo_reproducible() -> None:
    returns = np.array([0.08, -0.05, 0.10, 0.02])
    config = MonteCarloConfig(initial=1_000, iters=8, seed=42)
    first = simulate_trade_returns(returns, config)
    second = simulate_trade_returns(returns, config)
    assert first.equals(second)
    bands = percentile_bands(first)
    assert set(bands["method"]) == {"shuffle", "bootstrap"}
    assert {"final_equity", "max_dd_pct", "sharpe"}.issubset(set(bands["metric"]))


def test_monte_carlo_single_trade_is_sane() -> None:
    sims = simulate_trade_returns(np.array([0.10]), MonteCarloConfig(initial=100, iters=3, seed=1))
    assert set(sims["final_equity"]) == {110.0}
    assert set(sims["sharpe"]) == {0.0}
    assert sims["n_trades"].tolist() == [1, 1, 1, 1, 1, 1]


def test_run_monte_carlo_and_cli(capsys) -> None:
    _, bands = run_monte_carlo(
        Path("examples/sample_tradingview_export.csv"),
        MonteCarloConfig(initial=10_000, iters=5, seed=7),
    )
    assert not bands.empty
    assert (
        main(
            ["montecarlo", "examples/sample_tradingview_export.csv", "--iters", "5", "--seed", "7"]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "bootstrap" in out
