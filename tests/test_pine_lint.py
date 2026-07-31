"""Tests for pinewf.pine_lint."""

from __future__ import annotations

from pathlib import Path

from pinewf.pine_lint import (
    PineFinding,
    count_by_severity,
    findings_to_json,
    format_findings,
    lint_file,
    lint_source,
    worst_severity,
)

DIRTY = (
    "//@version=6\n"
    'strategy("Dirty", overlay=true, calc_on_every_tick=true)\n'
    'src = request.security(syminfo.tickerid, "D", close, lookahead=barmerge.lookahead_on)\n'
    "fast = ta.ema(close, 20)\n"
    "if ta.crossover(close, fast)\n"
    '    strategy.entry("Long", strategy.long)\n'
)

CLEAN = (
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

DIRTY_EXPECTED = [
    PineFinding(
        rule="PL002",
        severity="error",
        line=2,
        message="calc_on_every_tick=true repaints on intrabar updates",
    ),
    PineFinding(
        rule="PL003",
        severity="warning",
        line=2,
        message="strategy() declares no commission_type/commission_value",
    ),
    PineFinding(
        rule="PL004",
        severity="warning",
        line=2,
        message="strategy() declares no slippage",
    ),
    PineFinding(
        rule="PL005",
        severity="warning",
        line=2,
        message="strategy.entry without any strategy.exit or strategy.close",
    ),
    PineFinding(
        rule="PL006",
        severity="info",
        line=2,
        message="no alert() or alertcondition() hook found",
    ),
    PineFinding(
        rule="PL001",
        severity="error",
        line=3,
        message="request.security() uses barmerge.lookahead_on",
    ),
    PineFinding(
        rule="PL007",
        severity="warning",
        line=4,
        message="numeric indicator length; expose it with input.*",
    ),
]

DIRTY_FMT = (
    "dirty.pine:2: error PL002 calc_on_every_tick=true repaints on intrabar updates\n"
    "dirty.pine:2: warning PL003 strategy() declares no commission_type/commission_value\n"
    "dirty.pine:2: warning PL004 strategy() declares no slippage\n"
    "dirty.pine:2: warning PL005 strategy.entry without any strategy.exit or strategy.close\n"
    "dirty.pine:2: info PL006 no alert() or alertcondition() hook found\n"
    "dirty.pine:3: error PL001 request.security() uses barmerge.lookahead_on\n"
    "dirty.pine:4: warning PL007 numeric indicator length; expose it with input.*\n"
    "7 findings: 2 error, 4 warning, 1 info"
)

CLEAN_JSON = (
    "{\n"
    '  "path": "clean.pine",\n'
    '  "n_findings": 0,\n'
    '  "counts": {\n'
    '    "error": 0,\n'
    '    "warning": 0,\n'
    '    "info": 0\n'
    "  },\n"
    '  "findings": []\n'
    "}"
)

DIRTY_JSON = (
    "{\n"
    '  "path": "dirty.pine",\n'
    '  "n_findings": 7,\n'
    '  "counts": {\n'
    '    "error": 2,\n'
    '    "warning": 4,\n'
    '    "info": 1\n'
    "  },\n"
    '  "findings": [\n'
    "    {\n"
    '      "rule": "PL002",\n'
    '      "severity": "error",\n'
    '      "line": 2,\n'
    '      "message": "calc_on_every_tick=true repaints on intrabar updates"\n'
    "    },\n"
    "    {\n"
    '      "rule": "PL003",\n'
    '      "severity": "warning",\n'
    '      "line": 2,\n'
    '      "message": "strategy() declares no commission_type/commission_value"\n'
    "    },\n"
    "    {\n"
    '      "rule": "PL004",\n'
    '      "severity": "warning",\n'
    '      "line": 2,\n'
    '      "message": "strategy() declares no slippage"\n'
    "    },\n"
    "    {\n"
    '      "rule": "PL005",\n'
    '      "severity": "warning",\n'
    '      "line": 2,\n'
    '      "message": "strategy.entry without any strategy.exit or strategy.close"\n'
    "    },\n"
    "    {\n"
    '      "rule": "PL006",\n'
    '      "severity": "info",\n'
    '      "line": 2,\n'
    '      "message": "no alert() or alertcondition() hook found"\n'
    "    },\n"
    "    {\n"
    '      "rule": "PL001",\n'
    '      "severity": "error",\n'
    '      "line": 3,\n'
    '      "message": "request.security() uses barmerge.lookahead_on"\n'
    "    },\n"
    "    {\n"
    '      "rule": "PL007",\n'
    '      "severity": "warning",\n'
    '      "line": 4,\n'
    '      "message": "numeric indicator length; expose it with input.*"\n'
    "    }\n"
    "  ]\n"
    "}"
)

PL001_SRC = (
    "//@version=6\n"
    'strategy("X", commission_type=strategy.commission.percent,\n'
    "     commission_value=0.1, slippage=1)\n"
    'src = request.security(syminfo.tickerid, "D", close, lookahead=barmerge.lookahead_on)\n'
    "if true\n"
    '    strategy.entry("L", strategy.long)\n'
    '    strategy.exit("L")\n'
    '    strategy.close("L")\n'
    'alertcondition(true, "a", "b")\n'
)
PL001_EXPECTED = [
    PineFinding(
        rule="PL001",
        severity="error",
        line=4,
        message="request.security() uses barmerge.lookahead_on",
    ),
]

PL002_SRC = (
    "//@version=6\n"
    'strategy("X", commission_type=strategy.commission.percent,\n'
    "     commission_value=0.1, slippage=1, calc_on_every_tick=true)\n"
    "if true\n"
    '    strategy.entry("L", strategy.long)\n'
    '    strategy.exit("L")\n'
    '    strategy.close("L")\n'
    'alertcondition(true, "a", "b")\n'
)
PL002_EXPECTED = [
    PineFinding(
        rule="PL002",
        severity="error",
        line=3,
        message="calc_on_every_tick=true repaints on intrabar updates",
    ),
]

PL003_SRC = (
    "//@version=6\n"
    'strategy("X", overlay=true, slippage=2)\n'
    "fast = close\n"
    'alertcondition(true, "a", "b")\n'
)
PL003_EXPECTED = [
    PineFinding(
        rule="PL003",
        severity="warning",
        line=2,
        message="strategy() declares no commission_type/commission_value",
    ),
]

PL004_SRC = (
    "//@version=6\n"
    'strategy("X", overlay=true, commission_type=strategy.commission.percent,\n'
    "     commission_value=0.1)\n"
    "fast = close\n"
    'alertcondition(true, "a", "b")\n'
)
PL004_EXPECTED = [
    PineFinding(
        rule="PL004",
        severity="warning",
        line=2,
        message="strategy() declares no slippage",
    ),
]

PL005_SRC = (
    "//@version=6\n"
    'strategy("X", overlay=true, commission_type=strategy.commission.percent,\n'
    "     commission_value=0.1, slippage=2)\n"
    "if ta.crossover(close, close)\n"
    '    strategy.entry("L", strategy.long)\n'
    'alertcondition(true, "a", "b")\n'
)
PL005_EXPECTED = [
    PineFinding(
        rule="PL005",
        severity="warning",
        line=2,
        message="strategy.entry without any strategy.exit or strategy.close",
    ),
]

PL006_SRC = (
    "//@version=6\n"
    'strategy("X", overlay=true, commission_type=strategy.commission.percent,\n'
    "     commission_value=0.1, slippage=2)\n"
    "if true\n"
    '    strategy.entry("L", strategy.long)\n'
    '    strategy.exit("L")\n'
    '    strategy.close("L")\n'
)
PL006_EXPECTED = [
    PineFinding(
        rule="PL006",
        severity="info",
        line=2,
        message="no alert() or alertcondition() hook found",
    ),
]

PL007_SRC = (
    "//@version=6\n"
    'strategy("X", commission_type=strategy.commission.percent,\n'
    "     commission_value=0.1, slippage=1)\n"
    'length = input.int(20, "Length")\n'
    "fast = ta.ema(close, 20)\n"
    "if true\n"
    '    strategy.entry("L", strategy.long)\n'
    '    strategy.exit("L")\n'
    '    strategy.close("L")\n'
    'alertcondition(true, "a", "b")\n'
)
PL007_EXPECTED = [
    PineFinding(
        rule="PL007",
        severity="warning",
        line=5,
        message="numeric indicator length; expose it with input.*",
    ),
]


def test_lint_source_dirty() -> None:
    assert lint_source(DIRTY) == DIRTY_EXPECTED


def test_lint_source_clean() -> None:
    assert lint_source(CLEAN) == []


def test_format_findings_dirty() -> None:
    assert format_findings(DIRTY_EXPECTED, "dirty.pine") == DIRTY_FMT


def test_format_findings_empty() -> None:
    assert format_findings([], "clean.pine") == "clean.pine: clean (0 findings)"


def test_findings_to_json_clean() -> None:
    assert findings_to_json([], "clean.pine") == CLEAN_JSON


def test_findings_to_json_dirty() -> None:
    assert findings_to_json(DIRTY_EXPECTED, "dirty.pine") == DIRTY_JSON


def test_lint_file(tmp_path: Path) -> None:
    p = tmp_path / "dirty.pine"
    p.write_text(DIRTY, encoding="utf-8")
    assert lint_file(p) == DIRTY_EXPECTED


def test_worst_severity() -> None:
    assert worst_severity(DIRTY_EXPECTED) == "error"
    assert worst_severity([]) is None


def test_count_by_severity() -> None:
    assert count_by_severity(DIRTY_EXPECTED) == {"error": 2, "warning": 4, "info": 1}
    assert count_by_severity([]) == {"error": 0, "warning": 0, "info": 0}


def test_pl001_lookahead() -> None:
    assert lint_source(PL001_SRC) == PL001_EXPECTED


def test_pl002_calc_on_every_tick() -> None:
    assert lint_source(PL002_SRC) == PL002_EXPECTED


def test_pl003_missing_commission() -> None:
    assert lint_source(PL003_SRC) == PL003_EXPECTED


def test_pl004_missing_slippage() -> None:
    assert lint_source(PL004_SRC) == PL004_EXPECTED


def test_pl005_missing_exit_or_close() -> None:
    assert lint_source(PL005_SRC) == PL005_EXPECTED


def test_pl006_no_alert() -> None:
    assert lint_source(PL006_SRC) == PL006_EXPECTED


def test_pl007_numeric_length() -> None:
    assert lint_source(PL007_SRC) == PL007_EXPECTED
