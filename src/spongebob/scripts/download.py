import argparse
import pandas as pd
from ..data.binance import download

def main():
    parser = argparse.ArgumentParser(description="Download Binance USDT-M futures klines.")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--symbols", nargs="+", required=True, help="e.g. BTCUSDT ETHUSDT")
    parser.add_argument("--since", required=True, help="UTC start date, e.g. 2023-01-01")
    parser.add_argument("--until", required=True, help="UTC end date, e.g. 2023-03-01")
    parser.add_argument("--intervals", nargs="+", default=["1m","3m","15m","30m","1h"])
    args = parser.parse_args()

    if set(args.intervals) - {"1m","3m","15m","30m","1h"}:
        raise SystemExit("Only intervals 1m 3m 15m 30m 1h are allowed.")

    download(args.symbols, args.intervals, args.since, args.until)

if __name__ == "__main__":
    main()