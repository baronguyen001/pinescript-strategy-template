# Walk-forward Guide

In-sample backtests answer: "What worked on the same history I used to choose parameters?" Walk-forward tests answer a harder question: "What happened after the choice was made?"

`pinewf walkforward` supports two modes:

| Mode | What It Does | Use When |
| --- | --- | --- |
| Replay | Keeps your fixed parameters and scores each test window | You already have a candidate config and want OOS behavior. |
| Optimize | Grid-searches each train span, chooses one config, then scores only the following test span | You want to estimate how parameter selection generalizes. |

The `degradation_%` field compares the train score with the test score. High degradation is a warning that the grid found a curve-fit pocket. The built-in verdict is a simple heuristic: robust means at least 60% of windows beat buy-and-hold and optimized degradation is below 30%. Treat those thresholds as illustrative; template, bring your own thresholds.

Sharpe annualization defaults to 365 periods per year for always-open daily markets. Override mentally or in code for your data, such as 252 for daily equities or `6 * 365` for 4-hour crypto bars.

For advanced purged or embargoed cross-validation, pair this repository with `walk-forward-validator`.
