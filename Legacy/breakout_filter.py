"""
breakout_filter.py
Companion to swing_scanner.py — volume-confirmed breakout detector for US
small/mid-caps. Designed to surface the *individual names* that ZPRR.DE only
gives you indirect exposure to.

Run standalone:
    python breakout_filter.py

Or import:
    from breakout_filter import scan_breakouts
    df = scan_breakouts(my_tickers)

Universe: bring your own. For Russell 2000, easiest path is to download the
IWM holdings CSV from iShares and parse the ticker column. Cache it locally;
no need to re-fetch daily.
"""

from __future__ import annotations

import time
import warnings
from dataclasses import asdict, dataclass
from typing import Iterable, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, SMAIndicator
from ta.volatility import BollingerBands

warnings.filterwarnings("ignore", category=FutureWarning)


# ---------- thresholds (regime-dependent; tune as you go) ----------
NEAR_HIGH_PCT     = 0.97       # close >= 97% of 52w high
CONSOL_LOOKBACK   = 20         # break of 20-day consolidation high
VOL_RATIO_MIN     = 1.5        # day's volume vs SMA50 volume
RSI_RANGE         = (55, 75)
ADX_MIN           = 20
BB_WIDTH_PCTILE   = 0.40       # current BB width must be in lowest 40% of last 60d
MARKET_CAP_RANGE  = (3e8, 5e9) # $300M – $5B
DOLLAR_VOL_MIN    = 5e6        # $5M avg daily turnover
DEBT_EQUITY_MAX   = 150.0      # yfinance reports D/E * 100


@dataclass
class BreakoutResult:
    ticker: str
    close: float
    pct_to_52w_high: float   # how close to the 52w high, %
    vol_ratio: float         # today vs 50d avg
    rsi: float
    adx: float
    bb_width: float
    market_cap: float
    profitable: bool
    debt_equity: Optional[float]
    score: float


# ---------- data fetch ----------

def _history(ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
    try:
        df = yf.Ticker(ticker).history(period=period, auto_adjust=True)
        return df if df is not None and len(df) >= 220 else None
    except Exception:
        return None


def _quality(ticker: str) -> dict:
    """Pull fundamentals for the zombie filter. yfinance .info is flaky;
    treat all values as best-effort."""
    out = {"profitable": False, "market_cap": None, "debt_equity": None}
    try:
        info = yf.Ticker(ticker).info or {}
        op_inc  = info.get("operatingIncome") or 0
        fwd_eps = info.get("forwardEps") or 0
        out["profitable"]   = (op_inc > 0) or (fwd_eps > 0)
        out["market_cap"]   = info.get("marketCap")
        out["debt_equity"]  = info.get("debtToEquity")
    except Exception:
        pass
    return out


# ---------- per-ticker evaluation ----------

def _evaluate(ticker: str, df: pd.DataFrame, q: dict) -> Optional[BreakoutResult]:
    close = float(df["Close"].iloc[-1])

    # --- proximity to 52w high ---
    high_52w = df["High"].rolling(252, min_periods=200).max().iloc[-1]
    pct_to_high = close / high_52w
    if pct_to_high < NEAR_HIGH_PCT:
        return None

    # --- consolidation breakout ---
    consol_high = df["High"].iloc[-CONSOL_LOOKBACK - 1 : -1].max()
    if close < consol_high:
        return None

    # --- volume confirmation ---
    vol_sma50 = df["Volume"].rolling(50).mean().iloc[-1]
    vol_ratio = float(df["Volume"].iloc[-1] / vol_sma50) if vol_sma50 else 0.0
    if vol_ratio < VOL_RATIO_MIN:
        return None

    # --- trend filter ---
    sma50  = SMAIndicator(df["Close"], 50).sma_indicator().iloc[-1]
    sma200 = SMAIndicator(df["Close"], 200).sma_indicator().iloc[-1]
    if not (close > sma50 > sma200):
        return None

    # --- momentum ---
    rsi = float(RSIIndicator(df["Close"], 14).rsi().iloc[-1])
    if not (RSI_RANGE[0] <= rsi <= RSI_RANGE[1]):
        return None

    adx = float(ADXIndicator(df["High"], df["Low"], df["Close"], 14).adx().iloc[-1])
    if adx < ADX_MIN:
        return None

    # --- BB squeeze (came out of compression) ---
    bb = BollingerBands(df["Close"], 20, 2)
    bb_width = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()
    if bb_width.iloc[-1] > bb_width.iloc[-60:].quantile(BB_WIDTH_PCTILE):
        return None

    # --- liquidity ---
    avg_dollar_vol = (df["Close"] * df["Volume"]).rolling(50).mean().iloc[-1]
    if avg_dollar_vol < DOLLAR_VOL_MIN:
        return None

    # --- quality ---
    mc = q.get("market_cap")
    if mc is None or not (MARKET_CAP_RANGE[0] <= mc <= MARKET_CAP_RANGE[1]):
        return None
    if not q.get("profitable"):
        return None
    de = q.get("debt_equity")
    if de is not None and de > DEBT_EQUITY_MAX:
        return None

    # --- composite score ---
    score = (
        (vol_ratio - 1.0) * 30           # volume conviction
        + (pct_to_high - NEAR_HIGH_PCT) * 400  # freshness vs high
        + (adx - 20) * 1.0               # trend strength
        + (10 if q.get("profitable") else 0)
    )

    return BreakoutResult(
        ticker          = ticker,
        close           = round(close, 2),
        pct_to_52w_high = round(pct_to_high * 100, 2),
        vol_ratio       = round(vol_ratio, 2),
        rsi             = round(rsi, 1),
        adx             = round(adx, 1),
        bb_width        = round(float(bb_width.iloc[-1]), 4),
        market_cap      = mc,
        profitable      = bool(q.get("profitable")),
        debt_equity     = de,
        score           = round(score, 1),
    )


# ---------- scanner entry point ----------

def scan_breakouts(tickers: Iterable[str], sleep_sec: float = 0.2) -> pd.DataFrame:
    """Run the filter against an iterable of tickers. Returns a DataFrame
    sorted by composite score (highest first). Empty if nothing passes."""
    rows = []
    for tkr in tickers:
        df = _history(tkr)
        if df is None:
            continue
        q = _quality(tkr)
        result = _evaluate(tkr, df, q)
        if result is not None:
            rows.append(asdict(result))
        time.sleep(sleep_sec)  # be polite to yfinance
    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .sort_values("score", ascending=False)
        .reset_index(drop=True)
    )


# ---------- demo ----------

# Replace with your own universe. For Russell 2000, parse IWM holdings CSV.
SAMPLE_UNIVERSE = [
    "RKLB", "CELH", "ELF",  "CVNA", "DUOL",
    "HIMS", "FTAI", "SOUN", "IOT",  "BWXT",
    "CAVA", "MARA", "RIOT", "PLAY", "GTLB",
    "URG",
]

if __name__ == "__main__":
    print(f"Scanning {len(SAMPLE_UNIVERSE)} tickers...")
    df = scan_breakouts(SAMPLE_UNIVERSE)
    if df.empty:
        print("No breakout candidates today.")
    else:
        print(df.to_string(index=False))