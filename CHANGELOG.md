# Changelog

## v0.4.0 - 2026-06-21

- Added `strategies/strategy_breakout.pine`, a generic long-only Donchian-channel
  breakout template (prior-bar channel to avoid same-bar peeking, channel exit +
  percent stop) with the same input-block and alert-hook structure as the others.
  Generic defaults, explicitly not a recommendation.
- Added extended risk analytics (`pinewf.risk`): Sortino, Calmar, Ulcer index,
  recovery factor, max drawdown duration (bars), average drawdown, and longest
  losing streak. Surface them with `pinewf backtest --risk` and they now appear
  as a "Risk metrics" section in the `pinewf report` HTML. Descriptive statistics
  only — no tuned parameters.

## v0.3.0 - 2026-06-10

- Added `strategies/strategy_short.pine`, a generic short-only Pine v6 breakdown template with the same input-block, risk-exit, alert-hook, and info-table structure as the other templates.
- Added `pinewf sensitivity`, which buckets realized trades by holding duration, reports per-bucket metrics, and flags edge concentrated in a single duration band. Available as a `--sensitivity-trades` section in the HTML report.
- Extended `pinewf montecarlo` with `--png` to export an equity percentile-band chart (matplotlib `[viz]` extra). The HTML report embeds the chart when Monte Carlo bands are present.

## v0.2.0 - 2026-06-05

- Added `pinewf montecarlo` for trade-order shuffle and bootstrap robustness bands over user-supplied trade exports.
- Added `strategies/strategy_meanrev.pine`, a second generic Pine v6 RSI/Bollinger mean-reversion template.
- Expanded HTML reports with per-window parameters, train-vs-out-of-sample degradation charts, and optional Monte Carlo percentile bands.

## v0.1.0 - 2026-06-04

- Added configurable and minimal Pine Script v6 strategy templates.
- Added the `pinewf` Python package and CLI for backtesting, grids, walk-forward replay, walk-forward optimization, TradingView CSV parsing, and HTML reports.
- Added offline examples, tests, and CI.

Roadmap ideas: short-side support, combinatorial purged validation via `walk-forward-validator`, Monte Carlo trade shuffling, a second built-in public data source, and more Pine exit modules.
