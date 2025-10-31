import argparse
import os
import pandas as pd
from datetime import datetime, timezone
from ..backtest.engine import SimpleFuturesBacktester

def load_1m_csv(symbol: str, base_dir: str = "data/raw/binance") -> pd.DataFrame:
    path = os.path.join(base_dir, symbol, "1m.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"1m data missing for {symbol}: {path}. Run download first.")
    df = pd.read_csv(path)
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    df = df.set_index("open_time").sort_index()
    return df

def slice_df(df: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    s = pd.Timestamp(start, tz="UTC")
    e = pd.Timestamp(end, tz="UTC")
    return df.loc[(df.index >= s) & (df.index <= e)].copy()

def main():
    parser = argparse.ArgumentParser(description="Run backtest for baseline strategy.")
    parser.add_argument("--symbols", nargs="+", required=True, help="e.g. BTCUSDT ETHUSDT")
    parser.add_argument("--start", required=True, help="UTC start date, e.g. 2023-01-01")
    parser.add_argument("--end", required=True, help="UTC end date, e.g. 2023-03-01")
    parser.add_argument("--equity", type=float, default=10000.0)
    args = parser.parse_args()

    bt = SimpleFuturesBacktester(equity=args.equity)
    curves = []
    all_trades = []
    metrics_list = []

    for sym in args.symbols:
        df = load_1m_csv(sym)
        df = slice_df(df, args.start, args.end)
        if df.empty:
            print(f"No data for {sym} in selected window.")
            continue
        eq, tdf, metrics = bt.run_symbol(sym, df)
        eq["symbol"] = sym
        tdf["symbol"] = sym
        curves.append(eq)
        all_trades.append(tdf)
        m = metrics.copy()
        m["symbol"] = sym
        metrics_list.append(m)

    if not curves:
        print("No results.")
        return

    out_dir = os.path.join("reports", "latest")
    os.makedirs(out_dir, exist_ok=True)

    eq_all = pd.concat(curves)
    trades_all = pd.concat(all_trades) if all_trades else pd.DataFrame()
    metrics_df = pd.DataFrame(metrics_list)

    eq_all.to_csv(os.path.join(out_dir, "equity.csv"))
    trades_all.to_csv(os.path.join(out_dir, "trades.csv"), index=False)
    metrics_df.to_json(os.path.join(out_dir, "metrics.json"), orient="records", indent=2)

    print("Saved reports to:", out_dir)

if __name__ == "__main__":
    main()