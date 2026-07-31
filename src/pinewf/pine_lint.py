"""Static lint checks for Pine Script v6 strategy sources."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PineFinding:
    rule: str
    severity: str
    line: int
    message: str


RULES: dict[str, tuple[str, str]] = {
    "PL001": ("error", "request.security() uses barmerge.lookahead_on"),
    "PL002": ("error", "calc_on_every_tick=true repaints on intrabar updates"),
    "PL003": ("warning", "strategy() declares no commission_type/commission_value"),
    "PL004": ("warning", "strategy() declares no slippage"),
    "PL005": ("warning", "strategy.entry without any strategy.exit or strategy.close"),
    "PL006": ("info", "no alert() or alertcondition() hook found"),
    "PL007": ("warning", "numeric indicator length; expose it with input.*"),
}

SEVERITY_ORDER: tuple[str, ...] = ("error", "warning", "info")

_TA_LENGTH_FUNCS = r"(?:sma|ema|wma|rma|rsi|atr|stdev|highest|lowest)"
TA_LENGTH_LITERAL_RE = re.compile(r"\bta\." + _TA_LENGTH_FUNCS + r"\s*\([^()]*,\s*\d+\s*[),]")
CALC_ON_EVERY_TICK_RE = re.compile(r"calc_on_every_tick\s*=\s*true")
LOOKAHEAD_ON_RE = re.compile(r"lookahead_on")
STRATEGY_DECL_RE = re.compile(r"strategy\s*\(")
STRATEGY_ENTRY_RE = re.compile(r"strategy\.entry\s*\(")
STRATEGY_EXIT_RE = re.compile(r"strategy\.exit\s*\(")
STRATEGY_CLOSE_RE = re.compile(r"strategy\.close\s*\(")
ALERT_RE = re.compile(r"alert\s*\(")
ALERTCONDITION_RE = re.compile(r"alertcondition\s*\(")
COMMISSION_TYPE_RE = re.compile(r"commission_type")
COMMISSION_VALUE_RE = re.compile(r"commission_value")
SLIPPAGE_RE = re.compile(r"slippage")


def _strip_inline_comments(source: str) -> list[str]:
    """Remove inline comments while preserving the total line count."""
    stripped: list[str] = []
    for raw_line in source.splitlines():
        idx = raw_line.find("//")
        if idx >= 0:
            raw_line = raw_line[:idx]
        stripped.append(raw_line)
    return stripped


def _finding(rule: str, line: int) -> PineFinding:
    """Build a PineFinding from a rule code and line number."""
    severity, message = RULES[rule]
    return PineFinding(rule=rule, severity=severity, line=line, message=message)


def lint_source(source: str) -> list[PineFinding]:
    """Lint a Pine Script strategy source string."""
    code_lines = _strip_inline_comments(source)
    cleaned_text = "\n".join(code_lines)

    findings: list[PineFinding] = []

    decl_line: int | None = None
    for idx, line in enumerate(code_lines):
        if STRATEGY_DECL_RE.search(line):
            decl_line = idx + 1
            break

    for idx, line in enumerate(code_lines):
        line_no = idx + 1
        if LOOKAHEAD_ON_RE.search(line):
            findings.append(_finding("PL001", line_no))
        if CALC_ON_EVERY_TICK_RE.search(line):
            findings.append(_finding("PL002", line_no))
        if TA_LENGTH_LITERAL_RE.search(line):
            findings.append(_finding("PL007", line_no))

    if decl_line is not None:
        has_comm_type = COMMISSION_TYPE_RE.search(cleaned_text)
        has_comm_value = COMMISSION_VALUE_RE.search(cleaned_text)
        if not (has_comm_type and has_comm_value):
            findings.append(_finding("PL003", decl_line))
        if not SLIPPAGE_RE.search(cleaned_text):
            findings.append(_finding("PL004", decl_line))
        has_entry = STRATEGY_ENTRY_RE.search(cleaned_text)
        has_exit = STRATEGY_EXIT_RE.search(cleaned_text)
        has_close = STRATEGY_CLOSE_RE.search(cleaned_text)
        if has_entry and not has_exit and not has_close:
            findings.append(_finding("PL005", decl_line))
        has_alert = ALERT_RE.search(cleaned_text)
        has_alertcondition = ALERTCONDITION_RE.search(cleaned_text)
        if not (has_alert or has_alertcondition):
            findings.append(_finding("PL006", decl_line))

    findings.sort(key=lambda finding: (finding.line, finding.rule))
    return findings


def lint_file(path: str | Path) -> list[PineFinding]:
    """Lint a UTF-8 encoded Pine Script file."""
    text = Path(path).read_text(encoding="utf-8")
    return lint_source(text)


def format_findings(findings: Sequence[PineFinding], path: str = "<source>") -> str:
    """Return a human-readable text report for the given findings."""
    if not findings:
        return f"{path}: clean (0 findings)"

    counts = count_by_severity(findings)
    lines: list[str] = []
    for finding in findings:
        lines.append(f"{path}:{finding.line}: {finding.severity} {finding.rule} {finding.message}")
    summary = (
        f"{len(findings)} findings: {counts['error']} error, "
        f"{counts['warning']} warning, {counts['info']} info"
    )
    return "\n".join(lines + [summary])


def findings_to_json(findings: Sequence[PineFinding], path: str = "<source>") -> str:
    """Return the findings as an indented JSON string."""
    counts = count_by_severity(findings)
    payload: dict[str, object] = {
        "path": path,
        "n_findings": len(findings),
        "counts": counts,
        "findings": [
            {
                "rule": finding.rule,
                "severity": finding.severity,
                "line": finding.line,
                "message": finding.message,
            }
            for finding in findings
        ],
    }
    return json.dumps(payload, indent=2)


def worst_severity(findings: Sequence[PineFinding]) -> str | None:
    """Return the highest severity present, or None if there are no findings."""
    if not findings:
        return None
    order = {severity: idx for idx, severity in enumerate(SEVERITY_ORDER)}
    return min(findings, key=lambda finding: order[finding.severity]).severity


def count_by_severity(findings: Sequence[PineFinding]) -> dict[str, int]:
    """Return counts for every severity level, including zero counts."""
    counts = {level: 0 for level in SEVERITY_ORDER}
    for finding in findings:
        counts[finding.severity] += 1
    return counts
