from dataclasses import dataclass
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional

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
        ticks = self.settings.slippage_ticks
        tick_size = self.settings.tick_size
        if side == "buy":
            return price + ticks * tick_size
        else:
            return price - ticks * tick_size

    def run_symbol(self, symbol: str, df_1m: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
        """
        df_1m: index tz-aware UTC, columns open, high, low, close, volume
        """
        strat = MTFMomentum(self.params)
        sig = strat.generate(df_1m)

        equity = self.equity0
        position = 0               # +1 long, -1 short, 0 flat
        entry_price: Optional[float] = None
        qty = 0.0
        trades: List[Trade] = []
        equity_curve = []

        fees = self.settings.fees
        risk = self.settings.risk
        max_lev = risk.max_leverage
        cooldown_bars = int(getattr(self.settings, "cooldown_bars", 0))
        trade_hours = set(getattr(self.settings, "trade_hours", []))
        cooldown_until: Optional[pd.Timestamp] = None

        # Pre-extract arrays (viel schneller als iterrows)
        index = df_1m.index
        opens = df_1m["open"].to_numpy(dtype=float)
        highs = df_1m["high"].to_numpy(dtype=float)
        lows  = df_1m["low"].to_numpy(dtype=float)
        closes= df_1m["close"].to_numpy(dtype=float)

        signals = sig["signal"].to_numpy(dtype=float)
        stops   = sig["stop"].to_numpy(dtype=float)
        takes   = sig["take"].to_numpy(dtype=float)

        for i in range(len(index)):
            ts = index[i]
            price_open = opens[i]
            price_close = closes[i]
            high = highs[i]
            low  = lows[i]
            signal_now = int(signals[i]) if np.isfinite(signals[i]) else 0
            stop_now = float(stops[i]) if np.isfinite(stops[i]) else np.nan
            take_now = float(takes[i]) if np.isfinite(takes[i]) else np.nan

            # mark-to-market
            if position != 0 and entry_price is not None:
                pnl_unreal = (price_close - entry_price) * qty
                equity_curve.append({"time": ts, "equity": equity + pnl_unreal})
            else:
                equity_curve.append({"time": ts, "equity": equity})

            # manage exit
            if position != 0:
                if position > 0:
                    if low <= curr_stop:
                        exit_px = curr_stop
                    elif high >= curr_take:
                        exit_px = curr_take
                    else:
                        exit_px = None
                else:  # short
                    if high >= curr_stop:
                        exit_px = curr_stop
                    elif low <= curr_take:
                        exit_px = curr_take
                    else:
                        exit_px = None

                if exit_px is not None:
                    side = "sell" if position > 0 else "buy"
                    filled = self._apply_slippage(exit_px, side)
                    trade_fee = abs(filled * qty) * fees.taker
                    pnl = (filled - entry_price) * qty - trade_fee
                    equity += pnl
                    trades.append(Trade(entry_time, ts, "long" if position>0 else "short",
                                        entry_price, filled, qty, pnl, trade_fee, symbol, curr_stop, curr_take))
                    position = 0
                    entry_price = None
                    qty = 0.0
                    curr_stop = curr_take = None
                    if cooldown_bars > 0:
                        cooldown_until = ts + pd.Timedelta(minutes=cooldown_bars)  # 1m grid
                    else:
                        cooldown_until = None
                    continue  # next bar after exit

            # gating for entries
            if position == 0:
                if cooldown_until is not None and ts < cooldown_until:
                    continue
                if trade_hours and (ts.hour not in trade_hours):
                    continue

            # new entry
            if position == 0 and signal_now != 0 and np.isfinite(stop_now) and np.isfinite(take_now):
                # position sizing
                atr_stop_dist = abs(price_close - stop_now)
                if atr_stop_dist <= 0:
                    continue
                risk_usdt = risk.risk_per_trade * equity
                qty_est = risk_usdt / atr_stop_dist
                notional = qty_est * price_close
                if notional > equity * max_lev:
                    qty_est = (equity * max_lev) / price_close

                side = "buy" if signal_now > 0 else "sell"
                filled = self._apply_slippage(price_close, side)
                trade_fee = abs(filled * qty_est) * fees.taker
                position = 1 if signal_now > 0 else -1
                entry_price = filled
                qty = qty_est if position > 0 else -qty_est
                curr_stop = float(stop_now)
                curr_take = float(take_now)
                entry_time = ts
                equity -= trade_fee

        eq = pd.DataFrame(equity_curve).set_index("time")

        tdf = pd.DataFrame([t.__dict__ for t in trades])

        metrics = self._metrics(eq, tdf)

        return eq, tdf, metrics

    def _metrics(self, eq: pd.DataFrame, trades: pd.DataFrame) -> Dict:
        if eq.empty:
            return {"final_equity": self.equity0, "total_return": 0.0, "cagr": 0.0, "sharpe": 0.0, "max_drawdown": 0.0, "n_trades": 0}
        ret_min = eq["equity"].pct_change().fillna(0.0)

        # Daily returns -> realistischere Sharpe
        eq_daily = eq["equity"].resample("1D").last().ffill()
        ret_daily = eq_daily.pct_change().dropna()
        sharpe = 0.0
        if len(ret_daily) > 2 and ret_daily.std() > 0:
            sharpe = (ret_daily.mean() / ret_daily.std()) * np.sqrt(365.0)

        max_dd = (eq["equity"]/eq["equity"].cummax() - 1.0).min()
        total_return = eq["equity"].iloc[-1] / eq["equity"].iloc[0] - 1.0
        n_days = max(1.0, len(eq_daily))
        cagr = (1+total_return) ** (365.0/n_days) - 1.0

        return {
            "final_equity": float(eq["equity"].iloc[-1]),
            "total_return": float(total_return),
            "cagr": float(cagr),
            "sharpe": float(sharpe),
            "max_drawdown": float(max_dd),
            "n_trades": int(len(trades)) if trades is not None else 0
        }
