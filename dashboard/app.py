import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Spongebob Backtest Dashboard", layout="wide")

st.title("Spongebob — Backtest Dashboard")

report_dir = st.text_input("Reports Ordner", value="reports/latest")

# ✅ NEU: Portfolio-Dateien
port_path = os.path.join(report_dir, "portfolio_equity.csv")
port_metrics_path = os.path.join(report_dir, "portfolio_metrics.json")

eq_path = os.path.join(report_dir, "equity.csv")
tr_path = os.path.join(report_dir, "trades.csv")
mt_path = os.path.join(report_dir, "metrics.json")

# ✅ Tabs für Portfolio / Symbol-Equity
st.subheader("Equity Curve")
tab1, tab2 = st.tabs(["Portfolio", "Per Symbol"])

with tab1:
    if os.path.exists(port_path):
        peq = pd.read_csv(port_path, parse_dates=["time"])
        st.line_chart(peq.set_index("time")["equity"])
        if os.path.exists(port_metrics_path):
            pm = pd.read_json(port_metrics_path, typ="series")
            st.caption(f"Portfolio: Sharpe {pm['sharpe']:.3f} | MDD {pm['max_drawdown']:.2%} | Final {pm['final_equity']:.2f}")
    else:
        st.info("portfolio_equity.csv fehlt – erst `python -m spongebob.scripts.portfolio` ausführen.")

with tab2:
    if os.path.exists(eq_path):
        eq = pd.read_csv(eq_path, parse_dates=["time"]).sort_values("time")
        st.line_chart(eq.set_index("time")["equity"])
    else:
        st.info("equity.csv nicht gefunden – Backtest zuerst laufen lassen.")

# Zwei Spalten für Metriken & Trades
col1, col2 = st.columns(2)

with col1:
    if os.path.exists(mt_path):
        metrics = pd.read_json(mt_path)
        st.subheader("Metriken (pro Symbol)")
        st.dataframe(metrics)
    else:
        st.info("metrics.json nicht gefunden.")

# ✅ Robuster Trades-Block
with col2:
    if os.path.exists(tr_path) and os.path.getsize(tr_path) > 0:
        try:
            trades = pd.read_csv(tr_path)
            for col in ("open_time", "close_time"):
                if col in trades.columns:
                    trades[col] = pd.to_datetime(trades[col], utc=True, errors="coerce")
            st.subheader("Trades")
            st.dataframe(trades.tail(300) if len(trades) > 0 else trades)
        except Exception as e:
            st.warning(f"Kann trades.csv nicht lesen: {e}")
    else:
        st.info("trades.csv fehlt oder ist leer – Backtest hat keine Trades erzeugt.")
