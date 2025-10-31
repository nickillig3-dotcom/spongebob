# spongebob — Perps Hedge-Bot (Windows + Visual Studio)

**Ziel:** ein profitabilitätsorientierter, mehrzeitframe (1m, 3m, 15m, 30m, 1h) Perpetual-Futures-Bot mit
Backtesting, Paper-Trading-Vorbereitung und Monitoring.

> **Wichtig:** Die einzigen erlaubten Zeiteinheiten sind **1m, 3m, 15m, 30m, 1h** (kein 5m).

## Schnellstart (Windows + Visual Studio 2022)

1) **Installiere**:
   - [Python 3.11 (64-bit)](https://www.python.org/downloads/)
   - [Git](https://git-scm.com/download/win)
   - **Visual Studio 2022** mit *Python development* Workload (Visual Studio Installer → Workloads).
2) **Repo klonen** (oder diesen Ordner als Start nutzen):
   ```powershell
   git clone https://github.com/nickillig3-dotcom/spongebob.git
   cd spongebob
   ```
3) **Virtuelle Umgebung** erstellen:
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\activate
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
4) **Visual Studio öffnen** → *Open a local folder* → wähle dieses Repo.
   - Rechts: **Python Environments** → wähle `.venv`.
5) **Backtest Beispiel** (nachdem du Daten geladen hast):
   ```powershell
   python -m spongebob.scripts.backtest --symbols BTCUSDT ETHUSDT --start 2023-01-01 --end 2023-03-01
   ```
6) **Monitoring** starten:
   ```powershell
   streamlit run dashboard/app.py
   ```

## Daten laden (Binance USDT‑M Perps)
```powershell
python -m spongebob.scripts.download --exchange binance --symbols BTCUSDT ETHUSDT ^
  --since 2023-01-01 --until 2023-03-01 --intervals 1m 3m 15m 30m 1h
```
Die Rohdaten werden als CSV unter `data/raw/binance/<SYMBOL>/<INTERVAL>.csv` abgelegt und automatisch
appendend geladen (idempotent).

## Strategie (Baseline)
- **Entry** auf 1m durch EMA(9/21) Kreuz.
- **Trendfilter**: 3m EMA(21) > EMA(55) für Longs (umgekehrt für Shorts) **und**
  Kurs über/unter EMA(200) auf 15m, 30m, 1h für Richtungsfilter.
- **Risikomodell**: 0.5% Equity pro Trade, Stop = 2× ATR(14) auf 3m, TP = 1.5× Stop.
- **Gebühren & Slippage** konfigurierbar (Default: taker 4bp pro Seite, 1 tick Slippage).

## Reports
- CSV & JSON unter `reports/<timestamp>_<universe>/`.
- Streamlit-Dashboard zeigt Equity Curve, Kennzahlen und Trades.

## Konfiguration
Kopiere `.env.example` zu `.env` und fülle nur falls du **Paper/Live** testen willst
(Binance Futures Testnet). Für Backtests nicht nötig.

## Tests
```powershell
pytest -q
```

---

## Loops (Arbeitsmodus)

**Loop 1 (Bootstrap – HEUTE):**
1. Klone Repo, lege `.venv` an, `pip install -r requirements.txt`.
2. Lade Daten:
   ```powershell
   python -m spongebob.scripts.download --exchange binance --symbols BTCUSDT ETHUSDT --since 2023-01-01 --until 2023-03-01 --intervals 1m 3m 15m 30m 1h
   ```
3. Starte Backtest:
   ```powershell
   python -m spongebob.scripts.backtest --symbols BTCUSDT ETHUSDT --start 2023-01-01 --end 2023-03-01
   ```
4. Starte Dashboard:
   ```powershell
   streamlit run dashboard/app.py
   ```

**Artefakte nach Loop 1 bitte an mich zurück:**
- Commit‑Hash, der die oben genannten Schritte enthält.
- Datei `reports/latest/metrics.json` und `reports/latest/trades.csv`.
- Screenshot von der Equity Curve im Dashboard.

Als Nächstes (Loop 2) bauen wir Hyperparam‑Suche + Robustheitstests.