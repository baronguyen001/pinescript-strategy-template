"""CLI wiring tests for the v0.5 pine-lint, regime, and compare commands."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from pinewf.cli import main

DIRTY_PINE = (
    "//@version=6\n"
    'strategy("Dirty", overlay=true)\n'
    'src = request.security(syminfo.tickerid, "D", close, lookahead=barmerge.lookahead_on)\n'
    "fast = ta.ema(close, 20)\n"
    "if ta.crossover(close, fast)\n"
    '    strategy.entry("Long", strategy.long)\n'
)

CLEAN_PINE = (
    "//@version=6\n"
    'strategy("Clean", overlay=true,\n'
    "     commission_type=strategy.commission.percent,\n"
    "     commission_value=0.1, slippage=2)\n"
    'length = input.int(20, "Length")\n'
    "fast = ta.sma(close, length)\n"
    "if ta.crossover(close, fast)\n"
    '    strategy.entry("Long", strategy.long)\n'
    '    strategy.close("Long")\n'
    'alertcondition(ta.crossover(close, fast), "Long", "entry")\n'
)


def _write_pine(tmp_path: Path, name: str, body: str) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _sample_ohlcv(tmp_path: Path, bars: int = 260) -> Path:
    dates = pd.date_range("2024-01-01", periods=bars, freq="D")
    close = [100.0 + (index % 40) * 1.5 for index in range(bars)]
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": [value * 1.02 for value in close],
            "low": [value * 0.98 for value in close],
            "close": close,
            "volume": [1_000.0] * bars,
        }
    )
    path = tmp_path / "ohlcv.csv"
    frame.to_csv(path, index=False)
    return path


def test_pine_lint_clean_exits_zero(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write_pine(tmp_path, "clean.pine", CLEAN_PINE)
    assert main(["pine-lint", str(path)]) == 0
    assert "clean (0 findings)" in capsys.readouterr().out


def test_pine_lint_dirty_exits_one(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write_pine(tmp_path, "dirty.pine", DIRTY_PINE)
    assert main(["pine-lint", str(path)]) == 1
    out = capsys.readouterr().out
    assert "error PL001 request.security() uses barmerge.lookahead_on" in out
    assert "findings:" in out


def test_pine_lint_json_format(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write_pine(tmp_path, "dirty.pine", DIRTY_PINE)
    main(["pine-lint", str(path), "--format", "json"])
    out = capsys.readouterr().out
    assert '"rule": "PL001"' in out
    assert '"n_findings": 6' in out


def test_pine_lint_fail_on_info_gates_warnings(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write_pine(tmp_path, "warn.pine", CLEAN_PINE.replace("slippage=2", "pyramiding=0"))
    assert main(["pine-lint", str(path)]) == 0
    assert main(["pine-lint", str(path), "--fail-on", "warning"]) == 1
    assert "PL004" in capsys.readouterr().out


def test_regime_command_prints_verdict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    csv = _sample_ohlcv(tmp_path)
    assert main(["regime", str(csv), "--regime-window", "10", "--regime-slope", "1.0"]) == 0
    assert "verdict:" in capsys.readouterr().out


def test_compare_command_prints_verdict(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    csv = _sample_ohlcv(tmp_path)
    exit_code = main(
        ["compare", str(csv), "--fast", "10", "--slow", "30", "--vs-fast", "5", "--vs-slow", "20"]
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "verdict:" in out
    assert "better" in out


def test_report_regime_section(tmp_path: Path) -> None:
    csv = _sample_ohlcv(tmp_path)
    html = tmp_path / "report.html"
    exit_code = main(
        [
            "report",
            str(csv),
            "--html",
            str(html),
            "--regime",
            "--regime-window",
            "10",
            "--regime-slope",
            "1.0",
        ]
    )
    assert exit_code == 0
    body = html.read_text(encoding="utf-8")
    assert "<h2>Market Regime</h2>" in body


def test_report_without_regime_has_no_section(tmp_path: Path) -> None:
    csv = _sample_ohlcv(tmp_path)
    html = tmp_path / "plain.html"
    assert main(["report", str(csv), "--html", str(html)]) == 0
    assert "<h2>Market Regime</h2>" not in html.read_text(encoding="utf-8")
