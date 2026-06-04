# Pine Setup

1. Open TradingView and create a new Pine Editor script.
2. Paste `strategies/strategy_template.pine` or `strategies/strategy_minimal.pine`.
3. Confirm the first line is `//@version=6`.
4. Click **Add to chart** and review the Strategy Tester.
5. In Strategy Tester, export the **List of Trades** CSV if you want to analyze TradingView's own trades with `pinewf parse-pine`.

TradingView is the only Pine compiler, so the repository cannot compile Pine in CI. Manual check for v0.1.0: paste both files into Pine Editor and confirm they compile without errors.

The Python engine uses signal-at-close to next-bar-open execution with slippage and commission per side, matching the intent of `process_orders_on_close=false`.
