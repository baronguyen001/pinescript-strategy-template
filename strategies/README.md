# Strategy Templates

Start with `strategy_minimal.pine` if you are new to Pine. Use `strategy_template.pine` when you want configurable trend filters, ATR stops, trailing stops, take profit exits, an info table, and alert conditions. Use `strategy_meanrev.pine` when you want a second generic RSI/Bollinger mean-reversion baseline.

| Input | Meaning | How to Tune |
| --- | --- | --- |
| MA type | SMA or EMA smoothing | Compare on your own market; faster smoothing can react earlier and whipsaw more. |
| Fast length | Short moving average | Keep it below the slow length and test broad ranges. |
| Slow length | Long moving average | Use it as the main regime/cross signal partner. |
| Trend length | Higher-level filter | Longer values reduce trades and can miss reversals. |
| Stop type | Percent, ATR, or none | Percent is simple; ATR adapts to volatility. |
| Stop loss % | Fixed risk distance | Treat it as a risk assumption, not an edge. |
| ATR settings | Volatility stop controls | Tune per timeframe and instrument. |
| Take profit | Optional fixed profit exit | Useful for bounded moves, but can cut trends short. |
| Trailing stop | Optional peak-based stop | Helps protect open profit after a move. |
| Chandelier stop | Optional ATR trail from peak | Volatility-aware trend exit. |

## Mean-reversion Template

`strategy_meanrev.pine` enters below the lower Bollinger band when RSI is below the oversold threshold, then exits at the middle band. It shares the same generic risk input style and alert hooks as the trend template.

See `docs/mean_reversion_template.md` for the setup flow.

TradingView's Strategy Tester is useful, but a single in-sample number is easy to curve-fit. Use the Python companion to walk-forward your own thresholds and compare out-of-sample windows.

Pair a strategy that survives that process with Trawlkit when you need a live scrape-to-AI-to-alert workflow.
