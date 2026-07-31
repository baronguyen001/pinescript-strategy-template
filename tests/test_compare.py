"""Tests for the compare module."""

from __future__ import annotations

import pandas as pd

from pinewf.compare import COMPARE_COLUMNS, compare_metrics, compare_report, compare_summary

BASE = {
    "name": "baseline",
    "total_return_pct": 12.5,
    "sharpe": 0.8,
    "n_trades": 10,
    "max_dd_pct": -20.0,
    "profit_factor": 1.5,
}

CAND = {
    "name": "candidate",
    "total_return_pct": 18.0,
    "sharpe": 0.6,
    "n_trades": 12,
    "max_dd_pct": -15.0,
    "profit_factor": 1.5,
}


def test_compare_metrics_golden_sample() -> None:
    expected_rows = [
        {
            "metric": "total_return_pct",
            "baseline": 12.5,
            "candidate": 18.0,
            "delta": 5.5,
            "delta_pct": 44.0,
            "direction": "higher_is_better",
            "better": True,
        },
        {
            "metric": "sharpe",
            "baseline": 0.8,
            "candidate": 0.6,
            "delta": -0.2,
            "delta_pct": -25.0,
            "direction": "higher_is_better",
            "better": False,
        },
        {
            "metric": "n_trades",
            "baseline": 10.0,
            "candidate": 12.0,
            "delta": 2.0,
            "delta_pct": 20.0,
            "direction": "neutral",
            "better": None,
        },
        {
            "metric": "max_dd_pct",
            "baseline": -20.0,
            "candidate": -15.0,
            "delta": 5.0,
            "delta_pct": 25.0,
            "direction": "higher_is_better",
            "better": True,
        },
        {
            "metric": "profit_factor",
            "baseline": 1.5,
            "candidate": 1.5,
            "delta": 0.0,
            "delta_pct": 0.0,
            "direction": "higher_is_better",
            "better": None,
        },
    ]
    expected = pd.DataFrame(expected_rows, columns=COMPARE_COLUMNS, dtype=object)
    result = compare_metrics(BASE, CAND)
    pd.testing.assert_frame_equal(result, expected)


def test_compare_metrics_zero_baseline() -> None:
    table = compare_metrics({"sharpe": 0.0}, {"sharpe": 0.5})
    assert len(table) == 1
    row = table.iloc[0]
    assert row["metric"] == "sharpe"
    assert row["baseline"] == 0.0
    assert row["candidate"] == 0.5
    assert row["delta"] == 0.5
    assert row["delta_pct"] is None
    assert row["direction"] == "higher_is_better"
    assert row["better"] is True


def test_compare_metrics_lower_is_better_improvement() -> None:
    table = compare_metrics({"ulcer_index": 10.0}, {"ulcer_index": 6.0})
    assert len(table) == 1
    row = table.iloc[0]
    assert row["metric"] == "ulcer_index"
    assert row["baseline"] == 10.0
    assert row["candidate"] == 6.0
    assert row["delta"] == -4.0
    assert row["delta_pct"] == -40.0
    assert row["direction"] == "lower_is_better"
    assert row["better"] is True


def test_compare_metrics_skips_non_numeric_strings() -> None:
    table = compare_metrics({"name": "a"}, {"name": "b"})
    assert table.empty
    assert list(table.columns) == COMPARE_COLUMNS


def test_compare_metrics_skips_bool_values() -> None:
    table = compare_metrics({"win_rate_pct": True}, {"win_rate_pct": False})
    assert table.empty
    assert list(table.columns) == COMPARE_COLUMNS


def test_compare_metrics_converts_int_input_to_float() -> None:
    table = compare_metrics({"n_trades": 10}, {"n_trades": 12})
    assert len(table) == 1
    row = table.iloc[0]
    assert isinstance(row["baseline"], float)
    assert isinstance(row["candidate"], float)
    assert isinstance(row["delta"], float)
    assert row["baseline"] == 10.0
    assert row["candidate"] == 12.0
    assert row["delta"] == 2.0
    assert row["delta_pct"] == 20.0
    assert row["direction"] == "neutral"
    assert row["better"] is None


def test_compare_summary_golden_sample() -> None:
    table = compare_metrics(BASE, CAND)
    summary = compare_summary(table)
    expected = {
        "n_metrics": 5,
        "n_better": 2,
        "n_worse": 1,
        "n_tied": 2,
        "verdict": "BETTER",
    }
    assert summary == expected


def test_compare_summary_no_metrics() -> None:
    table = compare_metrics({"name": "a"}, {"name": "b"})
    summary = compare_summary(table)
    expected = {
        "n_metrics": 0,
        "n_better": 0,
        "n_worse": 0,
        "n_tied": 0,
        "verdict": "NO_METRICS",
    }
    assert summary == expected


def test_compare_summary_mixed_verdict() -> None:
    table = compare_metrics(
        {"total_return_pct": 10.0, "sharpe": 1.0},
        {"total_return_pct": 8.0, "sharpe": 1.2},
    )
    summary = compare_summary(table)
    expected = {
        "n_metrics": 2,
        "n_better": 1,
        "n_worse": 1,
        "n_tied": 0,
        "verdict": "MIXED",
    }
    assert summary == expected


def test_compare_summary_worse_verdict() -> None:
    table = compare_metrics({"total_return_pct": 10.0}, {"total_return_pct": 8.0})
    summary = compare_summary(table)
    expected = {
        "n_metrics": 1,
        "n_better": 0,
        "n_worse": 1,
        "n_tied": 0,
        "verdict": "WORSE",
    }
    assert summary == expected


def test_compare_summary_tied_verdict() -> None:
    table = compare_metrics({"n_trades": 10}, {"n_trades": 10})
    summary = compare_summary(table)
    expected = {
        "n_metrics": 1,
        "n_better": 0,
        "n_worse": 0,
        "n_tied": 1,
        "verdict": "TIED",
    }
    assert summary == expected


def test_compare_report_returns_table_and_summary() -> None:
    table, summary = compare_report(BASE, CAND)
    assert isinstance(table, pd.DataFrame)
    assert len(table) == 5
    expected_summary = {
        "n_metrics": 5,
        "n_better": 2,
        "n_worse": 1,
        "n_tied": 2,
        "verdict": "BETTER",
    }
    assert summary == expected_summary
