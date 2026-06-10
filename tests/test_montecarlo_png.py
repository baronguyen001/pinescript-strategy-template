from pathlib import Path

import numpy as np

from pinewf.cli import main
from pinewf.montecarlo import (
    MonteCarloConfig,
    equity_path_bands,
    monte_carlo_figure,
    render_monte_carlo_png,
)

EXPORT = Path("examples/sample_tradingview_export.csv")


def test_equity_path_bands_shape_and_order() -> None:
    returns = np.array([0.08, -0.05, 0.10])
    bands = equity_path_bands(returns, MonteCarloConfig(initial=1_000, iters=50, seed=7))
    assert list(bands.columns) == ["trade", "p05", "p50", "p95"]
    assert len(bands) == returns.size + 1
    assert bands["p05"].iloc[0] == bands["p95"].iloc[0] == 1_000.0
    assert (bands["p05"] <= bands["p95"]).all()


def test_monte_carlo_figure_is_buildable() -> None:
    bands = equity_path_bands(
        np.array([0.05, -0.02, 0.03]), MonteCarloConfig(initial=1_000, iters=20, seed=1)
    )
    fig = monte_carlo_figure(bands)
    assert fig is not None


def test_render_png_writes_file(tmp_path: Path) -> None:
    out = render_monte_carlo_png(
        EXPORT, MonteCarloConfig(initial=10_000, iters=30, seed=3), tmp_path / "mc.png"
    )
    assert out.exists()
    assert out.read_bytes()[:4] == b"\x89PNG"


def test_montecarlo_cli_png(tmp_path: Path, capsys) -> None:
    png = tmp_path / "cli_mc.png"
    assert main(["montecarlo", str(EXPORT), "--iters", "20", "--seed", "5", "--png", str(png)]) == 0
    out = capsys.readouterr().out
    assert "wrote" in out
    assert png.exists()


def test_report_embeds_mc_chart_and_sensitivity(tmp_path: Path, capsys) -> None:
    html = tmp_path / "rep.html"
    assert (
        main(
            [
                "report",
                "examples/sample_btc_4h.csv",
                "--html",
                str(html),
                "--walkforward",
                "--montecarlo-trades",
                str(EXPORT),
                "--montecarlo-iters",
                "20",
                "--seed",
                "9",
                "--sensitivity-trades",
                str(EXPORT),
            ]
        )
        == 0
    )
    text = html.read_text(encoding="utf-8")
    assert "Monte Carlo Robustness" in text
    assert "Monte Carlo equity bands" in text
    assert "Holding-period Sensitivity" in text
