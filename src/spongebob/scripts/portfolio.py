import os, json, pandas as pd, numpy as np

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--report_dir", default="reports/latest")
    ap.add_argument("--equity0", type=float, default=10000.0)
    args = ap.parse_args()

    eq_path = os.path.join(args.report_dir, "equity.csv")
    if not os.path.exists(eq_path):
        print("equity.csv missing"); return

    df = pd.read_csv(eq_path, parse_dates=["time"])
    if "symbol" not in df.columns:
        print("symbol column missing in equity.csv"); return

    # pro Symbol auf NAV normalisieren
    navs = []
    for sym, g in df.groupby("symbol"):
        g = g.sort_values("time").copy()
        base = g["equity"].iloc[0]
        g["nav"] = g["equity"] / base
        navs.append(g[["time","nav"]].rename(columns={"nav": sym}))
    merged = navs[0]
    for g in navs[1:]:
        merged = pd.merge_asof(merged.sort_values("time"), g.sort_values("time"), on="time", direction="nearest")
    merged = merged.set_index("time").ffill()

    # Equal-Weight-Portfolio
    peq = (merged["portfolio_nav"] * args.equity0).rename("equity").to_frame()
    peq.index.name = "time"      # <--- NEU: Index benennen
    peq.to_csv(os.path.join(args.report_dir, "portfolio_equity.csv"))

    # Kennzahlen (täglich)
    daily = peq["equity"].resample("1D").last().ffill()
    ret_daily = daily.pct_change().dropna()
    sharpe = (ret_daily.mean() / ret_daily.std() * np.sqrt(365.0)) if ret_daily.std() > 0 else 0.0
    max_dd = (peq["equity"]/peq["equity"].cummax() - 1.0).min()
    total_return = peq["equity"].iloc[-1] / peq["equity"].iloc[0] - 1.0
    n_days = max(1.0, len(daily))
    cagr = (1+total_return) ** (365.0/n_days) - 1.0

    metrics = {
        "final_equity": float(peq["equity"].iloc[-1]),
        "total_return": float(total_return),
        "cagr": float(cagr),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_dd),
        "n_symbols": int(df["symbol"].nunique()),
        "weighting": "equal"
    }
    with open(os.path.join(args.report_dir, "portfolio_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print("Saved portfolio_* to", args.report_dir)

if __name__ == "__main__":
    main()
