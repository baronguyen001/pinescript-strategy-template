from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pandas as pd

from pinewf.compare import compare_metrics, compare_summary
from pinewf.data import fetch_binance_klines, load_ohlcv
from pinewf.engine import StrategyConfig, run_backtest
from pinewf.grid import param_grid
from pinewf.metrics import buy_hold_metrics, compute_metrics
from pinewf.montecarlo import (
    MonteCarloConfig,
    equity_path_bands,
    load_trade_returns,
    monte_carlo_figure,
    render_monte_carlo_png,
    run_monte_carlo,
)
from pinewf.pine_csv import metrics_from_pine_export, parse_tradingview_trades
from pinewf.pine_lint import findings_to_json, format_findings, lint_file, worst_severity
from pinewf.regime import RegimeConfig, regime_breakdown
from pinewf.report import render_html_report
from pinewf.risk import risk_metrics
from pinewf.sensitivity import (
    SensitivityConfig,
    duration_buckets,
    duration_sensitivity,
    load_trades,
    sensitivity_from_csv,
)
from pinewf.walk_forward import consistency, walk_forward_optimize, walk_forward_replay


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except Exception as exc:
        parser.exit(1, f"pinewf: error: {exc}\n")
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    df = fetch_binance_klines(args.symbol, args.interval, args.start, args.cache_dir)
    out = Path(args.out) if args.out else Path(f"{args.symbol.upper()}_{args.interval}.csv")
    df.to_csv(out)
    print(f"wrote {out} ({len(df)} bars)")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    df = load_ohlcv(args.csv)
    cfg = _cfg(args)
    result = run_backtest(df, cfg)
    rows = [
        compute_metrics(result.equity, result.trades, cfg.initial, len(df), "strategy"),
        buy_hold_metrics(df, cfg.initial, cfg.commission, cfg.slippage),
    ]
    _print_table(pd.DataFrame(rows))
    if getattr(args, "risk", False):
        print("\nExtended risk metrics (strategy):")
        _print_table(pd.DataFrame([risk_metrics(result.equity, result.trades)]))
    return 0


def cmd_grid(args: argparse.Namespace) -> int:
    df = load_ohlcv(args.csv)
    report = param_grid(df, _grid_from_args(args), _cfg(args), args.rank_by)
    _print_table(report.head(args.limit))
    print(f"\nwarning: {report['overfit_warning'].iloc[0]}")
    return 0


def cmd_walkforward(args: argparse.Namespace) -> int:
    df = load_ohlcv(args.csv)
    cfg = _cfg(args)
    if args.optimize:
        report = walk_forward_optimize(
            df, _grid_from_args(args), cfg, args.train, args.test, args.rank_by
        )
    else:
        report = walk_forward_replay(df, cfg, args.train, args.test)
    _print_table(report)
    print(f"\nconsistency: {consistency(report)}")
    if args.html:
        result = run_backtest(df, cfg)
        metrics = compute_metrics(result.equity, result.trades, cfg.initial, len(df), "strategy")
        path = render_html_report(
            result, metrics, report, out_path=args.html, **_report_extras(args)
        )
        print(f"wrote {path}")
    return 0


def cmd_parse_pine(args: argparse.Namespace) -> int:
    trades = parse_tradingview_trades(args.csv)
    metrics = metrics_from_pine_export(args.csv, args.initial)
    print(f"parsed {len(trades)} trades")
    _print_table(pd.DataFrame([metrics]))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    df = load_ohlcv(args.csv)
    cfg = _cfg(args)
    result = run_backtest(df, cfg)
    metrics = compute_metrics(result.equity, result.trades, cfg.initial, len(df), "strategy")
    wf = walk_forward_replay(df, cfg, args.train, args.test) if args.walkforward else None
    risk = risk_metrics(result.equity, result.trades)
    extras = _report_extras(args)
    if getattr(args, "regime", False):
        regime_table, regime_stats = regime_breakdown(df, result.trades, _regime_cfg(args))
        extras["regime_table"] = regime_table
        extras["regime_summary"] = regime_stats
    path = render_html_report(result, metrics, wf, out_path=args.html, risk=risk, **extras)
    print(f"wrote {path}")
    return 0


def cmd_montecarlo(args: argparse.Namespace) -> int:
    config = MonteCarloConfig(initial=args.initial, iters=args.iters, seed=args.seed)
    _, bands = run_monte_carlo(args.trades_or_csv, config)
    _print_table(bands)
    if args.png:
        out = render_monte_carlo_png(args.trades_or_csv, config, args.png, args.png_method)
        print(f"wrote {out}")
    return 0


def cmd_sensitivity(args: argparse.Namespace) -> int:
    table, summary = sensitivity_from_csv(args.trades_or_csv, _sensitivity_cfg(args))
    _print_table(table)
    print(
        f"\nverdict: {summary['verdict']} (dominant {summary['dominant_bucket']} "
        f"= {summary['dominant_share_pct']}% of gross profit)"
    )
    return 0


def cmd_pine_lint(args: argparse.Namespace) -> int:
    findings = lint_file(args.pine)
    label = str(args.pine)
    if args.format == "json":
        print(findings_to_json(findings, label))
    else:
        print(format_findings(findings, label))
    worst = worst_severity(findings)
    if worst is None:
        return 0
    gate = ["error", "warning", "info"]
    return 1 if gate.index(worst) <= gate.index(args.fail_on) else 0


def cmd_regime(args: argparse.Namespace) -> int:
    df = load_ohlcv(args.csv)
    cfg = _cfg(args)
    result = run_backtest(df, cfg)
    table, summary = regime_breakdown(df, result.trades, _regime_cfg(args))
    _print_table(table)
    print(
        f"\nverdict: {summary['verdict']} (dominant {summary['dominant_regime']} "
        f"= {summary['dominant_share_pct']}% of gross profit)"
    )
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    df = load_ohlcv(args.csv)
    base_cfg = _cfg(args)
    cand_cfg = _candidate_cfg(args, base_cfg)
    rows = []
    for label, cfg in (("baseline", base_cfg), ("candidate", cand_cfg)):
        result = run_backtest(df, cfg)
        rows.append(compute_metrics(result.equity, result.trades, cfg.initial, len(df), label))
    table = compare_metrics(rows[0], rows[1])
    summary = compare_summary(table)
    _print_table(table)
    print(
        f"\nverdict: {summary['verdict']} ({summary['n_better']} better, "
        f"{summary['n_worse']} worse, {summary['n_tied']} tied)"
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pinewf")
    sub = parser.add_subparsers(required=True)

    fetch = sub.add_parser("fetch", help="fetch public Binance klines")
    fetch.add_argument("symbol")
    fetch.add_argument("--interval", default="1d")
    fetch.add_argument("--start")
    fetch.add_argument("--out")
    fetch.add_argument("--cache-dir")
    fetch.set_defaults(func=cmd_fetch)

    backtest = sub.add_parser("backtest", help="run one backtest")
    backtest.add_argument("csv")
    _strategy_args(backtest)
    backtest.add_argument("--risk", action="store_true", help="also print extended risk metrics")
    backtest.set_defaults(func=cmd_backtest)

    grid = sub.add_parser("grid", help="run an in-sample parameter grid")
    grid.add_argument("csv")
    _strategy_args(grid)
    _grid_args(grid)
    grid.add_argument("--limit", type=int, default=10)
    grid.set_defaults(func=cmd_grid)

    wf = sub.add_parser("walkforward", help="run replay or optimized walk-forward")
    wf.add_argument("csv")
    _strategy_args(wf)
    _grid_args(wf)
    wf.add_argument("--train", type=float, default=2.0)
    wf.add_argument("--test", type=float, default=1.0)
    wf.add_argument("--optimize", action="store_true")
    wf.add_argument("--html", help="write an HTML walk-forward report")
    _monte_carlo_args(wf)
    wf.set_defaults(func=cmd_walkforward)

    parse = sub.add_parser("parse-pine", help="parse a TradingView List of Trades export")
    parse.add_argument("csv")
    parse.add_argument("--initial", type=float, default=10_000.0)
    parse.set_defaults(func=cmd_parse_pine)

    report = sub.add_parser("report", help="render a self-contained HTML report")
    report.add_argument("csv")
    _strategy_args(report)
    report.add_argument("--html", default="report.html")
    report.add_argument("--walkforward", action="store_true")
    report.add_argument("--train", type=float, default=2.0)
    report.add_argument("--test", type=float, default=1.0)
    report.add_argument("--regime", action="store_true", help="add a market-regime section")
    _regime_args(report)
    _monte_carlo_args(report)
    report.set_defaults(func=cmd_report)

    mc = sub.add_parser("montecarlo", help="simulate robustness from realized trade returns")
    mc.add_argument("trades_or_csv")
    mc.add_argument("--iters", type=int, default=1_000)
    mc.add_argument("--seed", type=int)
    mc.add_argument("--initial", type=float, default=10_000.0)
    mc.add_argument("--png", help="write an equity-band PNG chart (needs the viz extra)")
    mc.add_argument("--png-method", choices=["shuffle", "bootstrap"], default="bootstrap")
    mc.set_defaults(func=cmd_montecarlo)

    sens = sub.add_parser("sensitivity", help="bucket realized trades by holding duration")
    sens.add_argument("trades_or_csv")
    sens.add_argument(
        "--buckets",
        help="comma-separated holding-duration bucket edges (bars or days)",
    )
    sens.add_argument(
        "--concentration",
        type=float,
        default=0.6,
        help="flag when one bucket holds this fraction of gross profit",
    )
    sens.set_defaults(func=cmd_sensitivity)

    lint = sub.add_parser("pine-lint", help="static checks on a Pine Script strategy file")
    lint.add_argument("pine")
    lint.add_argument("--format", choices=["text", "json"], default="text")
    lint.add_argument(
        "--fail-on",
        choices=["error", "warning", "info"],
        default="error",
        help="exit 1 when a finding of at least this severity is present",
    )
    lint.set_defaults(func=cmd_pine_lint)

    regime = sub.add_parser("regime", help="break realized trades down by market regime")
    regime.add_argument("csv")
    _strategy_args(regime)
    _regime_args(regime)
    regime.set_defaults(func=cmd_regime)

    compare = sub.add_parser("compare", help="compare two parameter sets on the same data")
    compare.add_argument("csv")
    _strategy_args(compare)
    compare.add_argument("--vs-fast", type=int)
    compare.add_argument("--vs-slow", type=int)
    compare.add_argument("--vs-sl-pct", type=float)
    compare.add_argument("--vs-trend", type=int)
    compare.set_defaults(func=cmd_compare)
    return parser


def _regime_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--regime-window", type=int, default=50)
    parser.add_argument("--regime-slope", type=float, default=2.0)
    parser.add_argument("--regime-concentration", type=float, default=0.6)


def _regime_cfg(args: argparse.Namespace) -> RegimeConfig:
    return RegimeConfig(
        window=getattr(args, "regime_window", 50),
        slope_threshold_pct=getattr(args, "regime_slope", 2.0),
        concentration_threshold=getattr(args, "regime_concentration", 0.6),
    )


def _candidate_cfg(args: argparse.Namespace, base: StrategyConfig) -> StrategyConfig:
    return replace(
        base,
        fast=args.vs_fast if args.vs_fast is not None else base.fast,
        slow=args.vs_slow if args.vs_slow is not None else base.slow,
        trend=args.vs_trend if args.vs_trend is not None else base.trend,
        stop_loss_pct=args.vs_sl_pct if args.vs_sl_pct is not None else base.stop_loss_pct,
    )


def _strategy_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ma", choices=["ema", "sma"], default="ema")
    parser.add_argument("--fast", default="20")
    parser.add_argument("--slow", default="50")
    parser.add_argument("--trend", type=int, default=200)
    parser.add_argument("--no-trend-filter", action="store_true")
    parser.add_argument("--stop", choices=["percent", "atr", "none"], default="percent")
    parser.add_argument("--sl-pct", type=float, default=8.0)
    parser.add_argument("--stop-atr", type=float, default=2.0)
    parser.add_argument("--tp-pct", type=float)
    parser.add_argument("--trailing-pct", type=float)
    parser.add_argument("--chandelier-atr", type=float)
    parser.add_argument("--initial", type=float, default=10_000.0)
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage", type=float, default=0.0005)


def _grid_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--grid-fast", "--fast-list", dest="grid_fast")
    parser.add_argument("--grid-slow", "--slow-list", dest="grid_slow")
    parser.add_argument("--grid-sl", "--sl", dest="grid_sl")
    parser.add_argument("--rank-by", default="sharpe")


def _monte_carlo_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--montecarlo-trades", help="trade CSV to include MC bands in HTML")
    parser.add_argument("--montecarlo-iters", type=int, default=1_000)
    parser.add_argument("--seed", type=int)
    parser.add_argument(
        "--sensitivity-trades", help="trade CSV to include a holding-period section in HTML"
    )


def _cfg(args: argparse.Namespace) -> StrategyConfig:
    return StrategyConfig(
        fast=_first_int(args.fast),
        slow=_first_int(args.slow),
        trend=args.trend,
        ma_kind=args.ma,
        use_trend_filter=not args.no_trend_filter,
        stop_kind=args.stop,
        stop_loss_pct=args.sl_pct,
        stop_atr_mult=args.stop_atr,
        take_profit_pct=args.tp_pct,
        trailing_pct=args.trailing_pct,
        chandelier_atr_mult=args.chandelier_atr,
        initial=args.initial,
        commission=args.commission,
        slippage=args.slippage,
    )


def _grid_from_args(args: argparse.Namespace) -> dict[str, list[Any]]:
    fast_src = args.grid_fast or (args.fast if "," in str(args.fast) else "9,20,34")
    slow_src = args.grid_slow or (args.slow if "," in str(args.slow) else "50,100")
    sl_src = args.grid_sl or "6,8,10"
    base: dict[str, list[Any]] = {
        "fast": _ints(fast_src),
        "slow": _ints(slow_src),
        "sl": _floats(sl_src),
    }
    return base


def _report_extras(args: argparse.Namespace) -> dict[str, Any]:
    extras: dict[str, Any] = {}
    mc_path = getattr(args, "montecarlo_trades", None)
    if mc_path:
        config = MonteCarloConfig(initial=args.initial, iters=args.montecarlo_iters, seed=args.seed)
        _, bands = run_monte_carlo(mc_path, config)
        extras["monte_carlo_bands"] = bands
        try:
            mc_bands = equity_path_bands(load_trade_returns(mc_path), config)
            extras["monte_carlo_figure"] = monte_carlo_figure(mc_bands)
        except RuntimeError:
            extras["monte_carlo_figure"] = None
    sens_path = getattr(args, "sensitivity_trades", None)
    if sens_path:
        trades = load_trades(sens_path)
        cfg = SensitivityConfig()
        extras["sensitivity_table"] = duration_buckets(trades, cfg)
        extras["sensitivity_summary"] = duration_sensitivity(trades, cfg)
    return extras


def _sensitivity_cfg(args: argparse.Namespace) -> SensitivityConfig:
    if args.buckets:
        edges = tuple(_floats(args.buckets))
    else:
        return SensitivityConfig(concentration_threshold=args.concentration)
    return SensitivityConfig(buckets=edges, concentration_threshold=args.concentration)


def _first_int(value: str) -> int:
    return int(str(value).split(",")[0].strip())


def _ints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def _floats(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def _print_table(df: pd.DataFrame) -> None:
    if df.empty:
        print("(no rows)")
    else:
        print(df.to_string(index=False))


if __name__ == "__main__":
    raise SystemExit(main())
