from dataclasses import dataclass
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

from ..config import SETTINGS
from ..strategy.mtf_momo import MTFMomentum, Params

@dataclass
class Trade:
    open_time: pd.Timestamp
    close_time: pd.Timestamp
    side: str
    entry: float
    exit: float
    qty: float
    pnl: float
    fee: float
    symbol: str
    stop: float
    take: float

class SimpleFuturesBacktester:
    def __init__(self, equity: float = 10_000.0, settings=SETTINGS, params: Params = Params()):
        self.equity0 = equity
        self.settings = settings
        self.params = params

    def _apply_slippage(self, price: float, side: str) -> float:
        # simple tick slippage model
        ticks = self.settings.slippage_ticks
        tick_size = self.settings.tick_size
        if side == "buy":
            return price + ticks * tick_size
        else:
            return price - ticks * tick_size

    def run_symbol(self, symbol: str, df_1m: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
        """
        df_1m must have index tz-aware UTC and columns open,high,low,close,volume
        """
        strat = MTFMomentum(self.params)
        sig = strat.generate(df_1m)

        equity = self.equity0
        position = 0  # +1 long, -1 short, 0 flat
        entry_price = None
        qty = 0.0
        trades: List[Trade] = []
        equity_curve = []

        fees = self.settings.fees
        risk = self.settings.risk
        max_lev = risk.max_leverage

        for ts, row in df_1m.iterrows():
            price_open = float(row["open"])
            price_close = float(row["close"])
            high = float(row["high"])
            low = float(row["low"])

            # mark-to-market
            if position != 0 and entry_price is not None:
                # unrealized pnl at close
                pnl_unreal = (price_close - entry_price) * qty
                equity_curve.append({"time": ts, "equity": equity + pnl_unreal})
            else:
                equity_curve.append({"time": ts, "equity": equity})

            # manage existing position exits using stop/take
            if position != 0:
                if position > 0:
                    stop = curr_stop
                    take = curr_take
                    # conservative bar processing: if both touched, assume stop hit first
                    if low <= stop:
                        exit_px = stop
                    elif high >= take:
                        exit_px = take
                    else:
                        exit_px = None
                else:
                    stop = curr_stop
                    take = curr_take
                    if high >= stop:
                        exit_px = stop
                    elif low <= take:
                        exit_px = take
                    else:
                        exit_px = None

                if exit_px is not None:
                    # close position
                    side = "sell" if position > 0 else "buy"
                    filled = self._apply_slippage(exit_px, side)
                    trade_fee = abs(filled * qty) * fees.taker  # taker fee on exit
                    pnl = (filled - entry_price) * qty - trade_fee
                    equity += pnl
                    trades.append(Trade(entry_time, ts, "long" if position>0 else "short",
                                        entry_price, filled, qty, pnl, trade_fee, symbol, curr_stop, curr_take))
                    position = 0
                    entry_price = None
                    qty = 0.0
                    curr_stop = curr_take = None
                    continue  # after exit, wait for next bar for new entries

            # check for new entry
            if position == 0 and sig.loc[ts, "signal"] != 0:
                direction = int(sig.loc[ts, "signal"])
                # size using risk budget
                atr_stop_dist = abs(float(price_close - sig.loc[ts, "stop"]))
                if atr_stop_dist <= 0:
                    continue
                risk_usdt = risk.risk_per_trade * equity
                qty_est = risk_usdt / atr_stop_dist
                # leverage cap
                notional = qty_est * price_close
                if notional > equity * max_lev:
                    qty_est = (equity * max_lev) / price_close
                # entry fill
                side = "buy" if direction > 0 else "sell"
                filled = self._apply_slippage(price_close, side)
                trade_fee = abs(filled * qty_est) * fees.taker  # taker fee on entry
                # book
                position = direction
                entry_price = filled
                qty = qty_est if direction > 0 else -qty_est  # signed qty for PnL calc
                curr_stop = float(sig.loc[ts, "stop"])
                curr_take = float(sig.loc[ts, "take"])
                entry_time = ts
                equity -= trade_fee  # pay entry fee

        # finalize equity curve df
        eq = pd.DataFrame(equity_curve).set_index("time")
        # trades df
        tdf = pd.DataFrame([t.__dict__ for t in trades])
        metrics = self._metrics(eq, tdf)

        return eq, tdf, metrics

    def _metrics(self, eq: pd.DataFrame, trades: pd.DataFrame) -> Dict:
        if eq.empty:
            return {"final_equity": self.equity0, "cagr": 0, "sharpe": 0, "max_drawdown": 0, "n_trades": 0}
        ret = eq["equity"].pct_change().fillna(0.0)
        # simple sharpe with daily (1m bars -> assume 1440 per day)
        daily = (1 + ret).rolling(1440).apply(lambda x: np.prod(x)-1, raw=False)
        sharpe = (ret.mean() / (ret.std() + 1e-12)) * np.sqrt(1440*365)
        max_dd = (eq["equity"]/eq["equity"].cummax() - 1.0).min()
        total_return = eq["equity"].iloc[-1] / eq["equity"].iloc[0] - 1.0
        # naive CAGR approximation using bar count
        n_days = max(1.0, len(eq)/1440.0)
        cagr = (1+total_return) ** (365.0/n_days) - 1.0
        return {
            "final_equity": float(eq["equity"].iloc[-1]),
            "total_return": float(total_return),
            "cagr": float(cagr),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_dd),
            "n_trades": int(len(trades)) if trades is not None else 0
        }