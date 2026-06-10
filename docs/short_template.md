# Short Template

`strategies/strategy_short.pine` is a generic Pine v6 template for long-side-free, short-only breakdown research.

It enters short when price closes below a Donchian-style lower channel (`ta.lowest` over a lookback) while an optional regime moving average confirms a down regime. It covers at the channel midline, with optional percent/ATR risk exits and an optional trailing or take-profit exit, all mirrored to the short side.

Use it as a third baseline next to the moving-average trend and RSI/Bollinger mean-reversion templates:

1. Paste `strategies/strategy_short.pine` into TradingView Pine Editor.
2. Confirm the first line is `//@version=6` and add it to a chart.
3. Export Strategy Tester trades as CSV.
4. Run `pinewf parse-pine <export.csv>`, `pinewf sensitivity <export.csv>`, and `pinewf montecarlo <export.csv> --seed 7`.
5. Confirm behavior with walk-forward tests before trusting any parameter set.

Inputs follow the same Signal / Risk / Optional-exits grouping as the other templates:

| Input | Meaning | How to Tune |
| --- | --- | --- |
| Breakdown length | Lower-channel lookback for the entry trigger | Longer values trade less and react slower. |
| Regime MA type / length | Down-regime confirmation filter | Disable it to test raw breakdowns. |
| Stop type | Percent, ATR, or none (placed above entry for shorts) | Percent is simple; ATR adapts to volatility. |
| Take profit / Trailing | Optional short-side profit and trail exits | Both are mirrored below the entry for shorts. |

The defaults are illustrative starting points. Bring your own market, timeframe, costs, and review process. Shorting carries unbounded loss risk and borrow/funding costs that a backtest may not capture.

Pair a strategy that survives out-of-sample review with Trawlkit when you need a live scrape-to-AI-to-alert workflow.
