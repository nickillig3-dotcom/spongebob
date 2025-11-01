import argparse, os, json, random, pandas as pd, numpy as np
from datetime import datetime
from ..backtest.engine import SimpleFuturesBacktester
from ..strategy.mtf_momo import Params
from ..config import SETTINGS

def load_1m(symbol, base_dir="data/raw/binance"):
    path = os.path.join(base_dir, symbol, "1m.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing {path}. Run download first.")
    df = pd.read_csv(path)
    df["open_time"] = pd.to_datetime(df["open_time"], utc=True)
    return df.set_index("open_time").sort_index()

def slice_df(df, start, end):
    s, e = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    return df.loc[(df.index >= s) & (df.index <= e)].copy()

def sample_params(rng: random.Random) -> Params:
    c = rng.choice
    return Params(
        ema_fast_1m=c([7,9,12]),
        ema_slow_1m=c([20,21,26,30]),
        ema_fast_3m=c([13,21,34]),
        ema_slow_3m=c([34,55,89]),
        ema_trend_long=c([150,200,233]),
        atr_period_3m=c([10,14,20]),
        atr_mult_stop=c([1.5,2.0,2.5,3.0]),
        tp_rr=c([1.0,1.2,1.5,2.0]),
        min_atr_pct=c([0.0008,0.0012,0.0018,0.0025]),
        min_ema_gap_pct=c([0.0002,0.0004,0.0008]),
    )

def parse_hours(s: str):
    if not s:
        return []
    s = s.strip()
    if "-" in s:
        a, b = [int(x) for x in s.split("-", 1)]
        if b < a:
            return list(range(a,24)) + list(range(0,b+1))
        return list(range(a,b+1))
    return [int(x) for x in s.split(",") if x != ""]

def score(metrics_is, metrics_oos):
    if not metrics_is or not metrics_oos:
        return -1e9
    sr_is  = np.mean([m["sharpe"] for m in metrics_is])
    sr_oos = np.mean([m["sharpe"] for m in metrics_oos])
    mdd_is = np.mean([m["max_drawdown"] for m in metrics_is])
    mdd_oos= np.mean([m["max_drawdown"] for m in metrics_oos])
    n_tr   = np.sum([m["n_trades"] for m in metrics_is])  # nur IS zählte vorher
    pen = 0.0
    # Drawdown-Strafen
    pen += max(0.0, abs(mdd_is)  - 0.25) * 2.0
    pen += max(0.0, abs(mdd_oos) - 0.30) * 3.0
    # Mindest-Tradezahl (weniger hart)
    if n_tr < 80:
        pen += (80 - n_tr) / 120.0
    return float(sr_is + 0.7*sr_oos - pen)

def main():
    ap = argparse.ArgumentParser(description="Random-search optimizer (IS/OOS).")
    ap.add_argument("--symbols", nargs="+", required=True)
    ap.add_argument("--start", required=True, help="IS start (UTC)")
    ap.add_argument("--split",  required=True, help="OOS start (UTC)")
    ap.add_argument("--end",    required=True, help="OOS end (UTC)")
    ap.add_argument("--n-trials", type=int, default=150)
    ap.add_argument("--equity", type=float, default=10000.0)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--cooldown", type=int, default=0, help="Cooldown in 1m bars after exit")
    ap.add_argument("--hours", type=str, default="", help="Trading hours, e.g., '7-22' or '0,1,2,3,...'")
    args = ap.parse_args()

    # Settings-Gates setzen
    SETTINGS.cooldown_bars = int(args.cooldown)
    SETTINGS.trade_hours   = parse_hours(args.hours)

    rng = random.Random(args.seed)
    data = {sym: load_1m(sym) for sym in args.symbols}

    is_slices  = {sym: slice_df(df, args.start, args.split) for sym, df in data.items()}
    oos_slices = {sym: slice_df(df, args.split, args.end)   for sym, df in data.items()}

    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M")
    outdir = os.path.join("reports", "opt", stamp)
    os.makedirs(outdir, exist_ok=True)
    rows, best = [], {"score": -1e9}

    for t in range(1, args.n_trials+1):
        p = sample_params(rng)
        bt = SimpleFuturesBacktester(equity=args.equity, params=p)

        metrics_is, metrics_oos = [], []
        for sym in args.symbols:
            if is_slices[sym].empty or oos_slices[sym].empty:
                continue
            _, _, m_is  = bt.run_symbol(sym, is_slices[sym])
            _, _, m_oos = bt.run_symbol(sym, oos_slices[sym])
            m_is["symbol"], m_oos["symbol"] = sym, sym
            metrics_is.append(m_is); metrics_oos.append(m_oos)

        s = score(metrics_is, metrics_oos)
        row = {"trial": t, "score": s, "params": p.__dict__,
               "is_metrics": metrics_is, "oos_metrics": metrics_oos}
        rows.append(row)
        if s > best["score"]:
            best = row

        if t % 10 == 0:
            print(f"Trial {t}/{args.n_trials}  best_score={best['score']:.3f}")

    pd.DataFrame([{"trial": r["trial"], "score": r["score"], **r["params"]} for r in rows]) \
      .to_csv(os.path.join(outdir, "results.csv"), index=False)
    with open(os.path.join(outdir, "best_params.json"), "w", encoding="utf-8") as f:
        json.dump(best["params"], f, indent=2)

    print("Saved:", outdir)
    print("Best score:", best["score"])
    print("Best params file:", os.path.join(outdir, "best_params.json"))

if __name__ == "__main__":
    main()
