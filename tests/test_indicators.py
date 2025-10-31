import pandas as pd
import numpy as np
from spongebob.utils.indicators import ema, atr

def test_ema_basic():
    s = pd.Series([1,2,3,4,5], dtype=float)
    e = ema(s, span=2)
    assert len(e) == 5
    assert np.isfinite(e).all()

def test_atr_shapes():
    df = pd.DataFrame({
        "open":[1,1,1,1,1],
        "high":[2,2,2,2,2],
        "low":[0,0,0,0,0],
        "close":[1,1,1,1,1],
        "volume":[1,1,1,1,1],
    }, dtype=float)
    a = atr(df, 3)
    assert len(a) == len(df)