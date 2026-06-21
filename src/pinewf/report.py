from __future__ import annotations

import base64
from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pinewf.engine import BacktestResult
from pinewf.walk_forward import consistency


def equity_curve_figure(equity: pd.Series, benchmark: pd.Series | None = None):
    """Return a matplotlib Figure for the equity curve."""
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(9, 4.5))
    equity.plot(ax=ax, label="Strategy", linewidth=2)
    if benchmark is not None:
        benchmark.plot(ax=ax, label="Benchmark", linewidth=1.5)
    ax.set_title("Equity Curve")
    ax.set_ylabel("Equity")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    return fig


def render_html_report(
    result: BacktestResult,
    metrics: dict,
    wf_report: pd.DataFrame | None = None,
    monte_carlo_bands: pd.DataFrame | None = None,
    out_path: str | Path = "report.html",
    monte_carlo_figure: Any | None = None,
    sensitivity_table: pd.DataFrame | None = None,
    sensitivity_summary: dict | None = None,
    risk: dict | None = None,
) -> Path:
    """Write a self-contained HTML report with embedded equity image and tables."""
    fig = equity_curve_figure(result.equity)
    image = _fig_to_base64(fig)
    metrics_table = _dict_table(metrics)
    risk_html = ""
    if risk is not None:
        risk_html = "<h2>Risk metrics</h2>" + _dict_table(risk)
    wf_html = ""
    if wf_report is not None:
        summary = consistency(wf_report)
        wf_html = (
            "<h2>Walk-forward</h2>"
            f"<p><strong>Verdict:</strong> {escape(str(summary['verdict']))}</p>"
            f"{_dict_table(summary)}"
            f"{_walk_forward_details(wf_report)}"
            f"{wf_report.to_html(index=False, escape=True)}"
        )
    sensitivity_html = ""
    if sensitivity_table is not None:
        verdict = ""
        if sensitivity_summary is not None:
            verdict = (
                f"<p><strong>Verdict:</strong> "
                f"{escape(str(sensitivity_summary.get('verdict', '')))}</p>"
                f"{_dict_table(sensitivity_summary)}"
            )
        sensitivity_html = (
            "<h2>Holding-period Sensitivity</h2>"
            "<p>Metrics bucketed by trade holding duration. A single band that holds most "
            "of the gross profit can mean the edge is overfit to one duration.</p>"
            f"{verdict}"
            f"{sensitivity_table.to_html(index=False, escape=True)}"
        )
    mc_html = ""
    if monte_carlo_bands is not None:
        chart = ""
        if monte_carlo_figure is not None:
            chart = (
                '<img alt="Monte Carlo equity bands" '
                f'src="data:image/png;base64,{_fig_to_base64(monte_carlo_figure)}">'
            )
        mc_html = (
            "<h2>Monte Carlo Robustness</h2>"
            "<p>Percentile bands from trade-order shuffle and bootstrap simulations.</p>"
            f"{chart}"
            f"{monte_carlo_bands.to_html(index=False, escape=True)}"
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pine Walk-forward Report</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 32px; color: #17202a; }}
    table {{ border-collapse: collapse; margin: 16px 0; width: 100%; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px 10px; text-align: right; }}
    th {{ background: #f6f8fa; }}
    td:first-child, th:first-child {{ text-align: left; }}
    img {{ max-width: 100%; height: auto; }}
  </style>
</head>
<body>
  <h1>Pine Walk-forward Report</h1>
  <p>Illustrative research output from user-supplied data. Not financial advice.</p>
  <img alt="Equity curve" src="data:image/png;base64,{image}">
  <h2>Metrics</h2>
  {metrics_table}
  {risk_html}
  {wf_html}
  {sensitivity_html}
  {mc_html}
</body>
</html>
"""
    path = Path(out_path)
    path.write_text(html, encoding="utf-8")
    return path


def _pyplot():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("HTML reports require: pip install pinescript-walkforward[viz]") from exc
    return plt


def _fig_to_base64(fig: Any) -> str:
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=140)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _dict_table(values: dict) -> str:
    rows = "\n".join(
        f"<tr><th>{escape(str(key))}</th><td>{escape(str(value))}</td></tr>"
        for key, value in values.items()
    )
    return f"<table>{rows}</table>"


def _walk_forward_details(wf_report: pd.DataFrame) -> str:
    pieces: list[str] = []
    param_cols = [
        col
        for col in (
            "test_start",
            "test_end",
            "chosen_params",
            "train_score",
            "test_score",
            "degradation_%",
        )
        if col in wf_report.columns
    ]
    if "chosen_params" in wf_report.columns and param_cols:
        pieces.append("<h3>Per-window Parameters</h3>")
        pieces.append(wf_report[param_cols].to_html(index=False, escape=True))

    if {"train_score", "test_score"}.issubset(wf_report.columns):
        chart = _degradation_chart(wf_report)
        pieces.append("<h3>Walk-forward Degradation</h3>")
        pieces.append(
            f'<img alt="Walk-forward degradation chart" src="data:image/png;base64,{chart}">'
        )
    return "\n".join(pieces)


def _degradation_chart(wf_report: pd.DataFrame) -> str:
    plt = _pyplot()
    labels = list(range(1, len(wf_report) + 1))
    train = wf_report["train_score"].astype(float).replace([np.inf, -np.inf], np.nan)
    test = wf_report["test_score"].astype(float).replace([np.inf, -np.inf], np.nan)
    fig, ax = plt.subplots(figsize=(8, 3.5))
    ax.plot(labels, train, marker="o", label="Train")
    ax.plot(labels, test, marker="o", label="Out-of-sample")
    ax.set_xlabel("Window")
    ax.set_ylabel("Score")
    ax.set_title("Walk-forward Degradation")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    return _fig_to_base64(fig)
