import os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Spongebob Backtest Dashboard", layout="wide")

st.title("Spongebob — Backtest Dashboard")

report_dir = st.text_input("Reports Ordner", value="reports/latest")

eq_path = os.path.join(report_dir, "equity.csv")
tr_path = os.path.join(report_dir, "trades.csv")
mt_path = os.path.join(report_dir, "metrics.json")

if os.path.exists(eq_path):
    eq = pd.read_csv(eq_path, parse_dates=["time"])
    eq = eq.sort_values("time")
    st.subheader("Equity Curve")
    st.line_chart(eq.set_index("time")["equity"])
else:
    st.info("equity.csv nicht gefunden – Backtest zuerst laufen lassen.")

col1, col2 = st.columns(2)

with col1:
    if os.path.exists(mt_path):
        metrics = pd.read_json(mt_path)
        st.subheader("Metriken (pro Symbol)")
        st.dataframe(metrics)
    else:
        st.info("metrics.json nicht gefunden.")

with col2:
    if os.path.exists(tr_path):
        trades = pd.read_csv(tr_path, parse_dates=["open_time","close_time"])
        st.subheader("Trades")
        st.dataframe(trades.tail(250))
    else:
        st.info("trades.csv nicht gefunden.")