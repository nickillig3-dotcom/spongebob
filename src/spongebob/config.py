from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Fees(BaseModel):
    taker: float = 0.0004  # 4 bps pro Seite
    maker: float = 0.0002

class Risk(BaseModel):
    risk_per_trade: float = 0.005  # 0.5% Equity
    atr_mult_stop: float = 2.0
    tp_rr: float = 1.5
    max_leverage: float = 5.0

class Settings(BaseModel):
    fees: Fees = Fees()
    risk: Risk = Risk()
    slippage_ticks: int = 1
    tick_size: float = 0.1  # konservativ
    lot_size: float = 0.001

SETTINGS = Settings()