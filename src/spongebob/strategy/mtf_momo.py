from dataclasses import dataclass
from typing import Dict, Tuple
import pandas as pd
import numpy as np

from ..utils.indicators import ema, atr, resample_ohlcv

@dataclass
class Params:
    ema_fast_1m: int = 9
    ema_slow_1m: int = 21
    ema_fast_3m: int = 21
    ema_slow_3m: int = 55
    ema_trend_long: int = 200  # used on 15m/30m/1h
    atr_period_3m: int = 14
    atr_mult_stop: float = 2.0
    tp_rr: float = 1.5

class MTFMomentum:
    """
    Returns a DataFrame on the 1m grid with columns:
    - signal: 1 for long entry, -1 for short entry, 0 otherwise
    - stop: stop price for new entry
    - take: take-profit price for new entry
    """
    def __init__(self, params: Params = Params()):
        self.p = params

    def _prep_multitimeframe(self, df_1m: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        # Build higher timeframe frames
        df_3m  = resample_ohlcv(df_1m, '3min')
        df_15m = resample_ohlcv(df_1m, '15min')
        df_30m = resample_ohlcv(df_1m, '30min')
        df_1h  = resample_ohlcv(df_1m, '1h')
        return {"1m": df_1m, "3m": df_3m, "15m": df_15m, "30m": df_30m, "1h": df_1h}

    def generate(self, df_1m: pd.DataFrame) -> pd.DataFrame:
        frames = self._prep_multitimeframe(df_1m.copy())

        # Indicators
        f1 = frames["1m"]
        f1["ema_fast"] = ema(f1["close"], self.p.ema_fast_1m)
        f1["ema_slow"] = ema(f1["close"], self.p.ema_slow_1m)

        f3 = frames["3m"]
        f3["ema_fast"] = ema(f3["close"], self.p.ema_fast_3m)
        f3["ema_slow"] = ema(f3["close"], self.p.ema_slow_3m)
        f3["atr"] = atr(f3, self.p.atr_period_3m)

        for key in ["15m","30m","1h"]:
            f = frames[key]
            f["ema_trend"] = ema(f["close"], self.p.ema_trend_long)

        # Align higher TFs down to 1m grid via forward-fill
        aligned = f1[["open","high","low","close","volume"]].copy()
        aligned["ema_fast_1m"] = f1["ema_fast"]
        aligned["ema_slow_1m"] = f1["ema_slow"]

        for key, col in [("3m","ema_fast"),("3m","ema_slow"),("3m","atr")]:
            aligned[f"{key}_{col}"] = frames["3m"][col].reindex(aligned.index, method='ffill')

        for key in ["15m","30m","1h"]:
            aligned[f"{key}_ema_trend"] = frames[key]["ema_trend"].reindex(aligned.index, method='ffill')

        # Entry conditions
        long_trend  = (aligned["3m_ema_fast"] > aligned["3m_ema_slow"]) & \
                      (aligned["close"] > aligned["15m_ema_trend"]) & \
                      (aligned["close"] > aligned["30m_ema_trend"]) & \
                      (aligned["close"] > aligned["1h_ema_trend"])
        short_trend = (aligned["3m_ema_fast"] < aligned["3m_ema_slow"]) & \
                      (aligned["close"] < aligned["15m_ema_trend"]) & \
                      (aligned["close"] < aligned["30m_ema_trend"]) & \
                      (aligned["close"] < aligned["1h_ema_trend"])

        cross_up   = (aligned["ema_fast_1m"] > aligned["ema_slow_1m"]) & (aligned["ema_fast_1m"].shift(1) <= aligned["ema_slow_1m"].shift(1))
        cross_down = (aligned["ema_fast_1m"] < aligned["ema_slow_1m"]) & (aligned["ema_fast_1m"].shift(1) >= aligned["ema_slow_1m"].shift(1))

        signal = pd.Series(0, index=aligned.index)
        signal = signal.mask(long_trend & cross_up, 1)
        signal = signal.mask(short_trend & cross_down, -1)

        # Stops & takes based on 3m ATR
        atr3 = aligned["3m_atr"].ffill()
        stop_dist = self.p.atr_mult_stop * atr3
        take_dist = self.p.tp_rr * stop_dist

        stop_price = pd.Series(np.nan, index=aligned.index)
        take_price = pd.Series(np.nan, index=aligned.index)

        # When a long entry triggers, stop below; short entry stop above
        close = aligned["close"]
        stop_price = np.where(signal == 1, close - stop_dist, 
                       np.where(signal == -1, close + stop_dist, np.nan))
        take_price = np.where(signal == 1, close + take_dist, 
                       np.where(signal == -1, close - take_dist, np.nan))

        out = aligned.copy()
        out["signal"] = signal
        out["stop"] = stop_price
        out["take"] = take_price
        return out