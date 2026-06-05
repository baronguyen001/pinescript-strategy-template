# Mean-reversion Template

`strategies/strategy_meanrev.pine` is a generic Pine v6 RSI/Bollinger template for long-only mean-reversion research.

It enters when price is below the lower Bollinger band and RSI is below the oversold threshold. It exits at the middle band, with optional percent/ATR risk exits and optional trailing/take-profit exits.

Use it as a second baseline next to the moving-average trend template:

1. Paste `strategies/strategy_meanrev.pine` into TradingView Pine Editor.
2. Export Strategy Tester trades as CSV.
3. Run `pinewf parse-pine <export.csv>` and `pinewf montecarlo <export.csv> --seed 7`.
4. Confirm behavior with walk-forward tests before trusting any parameter set.

The defaults are illustrative starting points. Bring your own market, timeframe, costs, and review process.

Pair a strategy that survives out-of-sample review with Trawlkit when you need a live scrape-to-AI-to-alert workflow.
