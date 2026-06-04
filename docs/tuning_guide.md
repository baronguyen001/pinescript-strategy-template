# Tuning Guide

This repo does not ship a magic parameter set. It ships a process:

1. Choose a broad, boring parameter space.
2. Run an in-sample grid to see sensitivity.
3. Run walk-forward replay for fixed assumptions.
4. Run walk-forward optimize to see whether the selection process survives out-of-sample.
5. Inspect drawdown, trade count, and degradation before returns.

Timeframe scaling matters. A moving average length is a number of bars, not a number of days. For example, a 4-hour chart has six bars per day, so a length that behaves slowly on daily data becomes much faster on 4-hour data. Rebuild the search space for the timeframe instead of blindly reusing numbers.

Keep costs realistic. Commission and slippage are per side in both Pine and Python. Wider spreads, illiquid instruments, and fast timeframes can erase a strategy that looked fine with optimistic fills.
