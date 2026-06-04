from pinewf.data import load_ohlcv
from pinewf.engine import StrategyConfig, run_backtest
from pinewf.metrics import compute_metrics

df = load_ohlcv("examples/sample_btc_4h.csv")
cfg = StrategyConfig()
result = run_backtest(df, cfg)
metrics = compute_metrics(result.equity, result.trades, cfg.initial, len(df), "strategy")

for key, value in metrics.items():
    print(f"{key}: {value}")
