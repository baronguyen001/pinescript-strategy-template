from pathlib import Path

import pandas as pd

from pinewf.cli import main
from pinewf.data import load_ohlcv
from pinewf.engine import StrategyConfig, run_backtest
from pinewf.metrics import compute_metrics
from pinewf.report import equity_curve_figure, render_html_report

SAMPLE = Path("examples/sample_btc_4h.csv")


def test_load_ohlcv() -> None:
    df = load_ohlcv(SAMPLE)
    assert {"open", "high", "low", "close", "volume"}.issubset(df.columns)
    assert isinstance(df.index, pd.DatetimeIndex)


def test_render_html_report(tmp_path: Path) -> None:
    df = load_ohlcv(SAMPLE).head(260)
    cfg = StrategyConfig(trend=50, use_trend_filter=False)
    result = run_backtest(df, cfg)
    metrics = compute_metrics(result.equity, result.trades, cfg.initial, len(df), "strategy")
    fig = equity_curve_figure(result.equity)
    assert fig is not None
    out = render_html_report(result, metrics, out_path=tmp_path / "report.html")
    html = out.read_text(encoding="utf-8")
    assert "data:image/png;base64" in html
    assert "Metrics" in html


def test_cli_backtest_and_parse_pine(capsys) -> None:
    assert main(["backtest", str(SAMPLE), "--trend", "50", "--no-trend-filter"]) == 0
    first = capsys.readouterr()
    assert "strategy" in first.out
    assert main(["parse-pine", "examples/sample_tradingview_export.csv"]) == 0
    second = capsys.readouterr()
    assert "parsed 3 trades" in second.out


def test_cli_grid_walkforward_and_report(tmp_path: Path, capsys) -> None:
    assert (
        main(
            [
                "grid",
                str(SAMPLE),
                "--fast",
                "9,20",
                "--slow",
                "50,100",
                "--sl",
                "6,8",
                "--limit",
                "2",
            ]
        )
        == 0
    )
    assert "overfit" in capsys.readouterr().out
    assert main(["walkforward", str(SAMPLE), "--train", "2", "--test", "1"]) == 0
    assert "consistency" in capsys.readouterr().out
    html = tmp_path / "out.html"
    assert main(["report", str(SAMPLE), "--html", str(html), "--walkforward"]) == 0
    assert html.exists()
