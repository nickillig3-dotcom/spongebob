import numpy as np
import pandas as pd

def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df['close'].shift(1)
    tr1 = df['high'] - df['low']
    tr2 = (df['high'] - prev_close).abs()
    tr3 = (df['low'] - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr

def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    tr = true_range(df)
    return tr.ewm(span=period, adjust=False).mean()

def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    # Pandas: 'T'/'H' deprecated → auf 'min'/'h' mappen
    freq = rule.replace('T', 'min').replace('H', 'h')
    o = df['open'].resample(freq).first()
    h = df['high'].resample(freq).max()
    l = df['low'].resample(freq).min()
    c = df['close'].resample(freq).last()
    v = df['volume'].resample(freq).sum()
    out = pd.concat([o, h, l, c, v], axis=1)
    out.columns = ['open','high','low','close','volume']
    return out.dropna()
