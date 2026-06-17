#!/usr/bin/env python3
"""
DEPRECATED — swing_scanner.py has been retired. Use scan.py instead:

  python scan.py scan --strategy pullback --file universes/sample.txt
  python scan.py scan --strategy breakout --file universes/sample.txt
  python scan.py scan --ticker AAPL

This file is preserved for reference only. All active code lives in scanner/.

Swing Trading Scanner (legacy)
================================
Scans a universe of US stocks for two setups:
  A) Pullback to Support — stock in uptrend, pulled back to 20 EMA / support, oversold RSI
  B) Breakout with Volume — stock breaking out of consolidation range with high relative volume

Usage:
  python swing_scanner.py                  # Scan all tiers, score 70+ only (auto-detects market hours)
  python swing_scanner.py --tier 0         # Blue chips & large-caps only
  python swing_scanner.py --tier 1         # Mid-caps only ($5-50)
  python swing_scanner.py --tier 2         # Small/penny caps (<$5)
  python swing_scanner.py --tier 3         # ETFs only
  python swing_scanner.py --ticker AAPL    # Analyze a single stock
  python swing_scanner.py --ticker NUVB --date 2026-04-28   # What would the scanner have shown on that date?
  python swing_scanner.py --custom tickers.txt  # Custom list (one ticker per line)
  python swing_scanner.py --closed         # Force using last closed candle
  python swing_scanner.py --live           # Force using current (possibly incomplete) candle
  python swing_scanner.py --all            # Include weaker setups (score 40+)
  python swing_scanner.py --min-score 55   # Custom score threshold
  python swing_scanner.py --high-only      # Only show HIGH confidence results
  python swing_scanner.py --backtest       # Backtest pullback setups on 10 tickers per tier
  python swing_scanner.py --backtest 20    # Backtest with 20 tickers per tier

Requirements:
  pip install yfinance pandas ta
"""

import argparse
import sys
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import yfinance as yf
import ta

# ── Global flags ────────────────────────────────────────────────────────────
DROP_INCOMPLETE = False
EVAL_DATE = None  # If set, evaluate as of this historical date (datetime.date)


def is_us_market_open() -> bool:
    """Check if the US stock market is likely open right now (rough heuristic)."""
    from zoneinfo import ZoneInfo
    now_et = datetime.now(ZoneInfo("America/New_York"))
    # Weekday check (Mon=0, Fri=4)
    if now_et.weekday() > 4:
        return False
    market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now_et <= market_close


# ── Stock Universe ──────────────────────────────────────────────────────────

# Tier 0: Blue Chips & Large-Caps (>$50, high liquidity, lower volatility)
# These rarely trigger swing setups but when they do, the signals are very reliable.
TIER0_BLUECHIPS = [
    # Magnificent 7 / Mega-cap Tech
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
    # Semiconductor Leaders
    "AVGO", "AMD", "INTC", "QCOM", "TXN", "MU", "ASML", "LRCX", "AMAT",
    # Software / Cloud
    "CRM", "ORCL", "ADBE", "NOW", "SNOW", "PANW", "CRWD", "ZS", "FTNT",
    "WDAY", "TEAM", "MDB", "NET", "DDOG",
    # Fintech / Payments
    "V", "MA", "PYPL", "SQ", "GS", "JPM", "MS", "BAC", "C", "WFC",
    # Consumer / Retail
    "WMT", "COST", "TGT", "HD", "LOW", "NKE", "SBUX", "MCD",
    "DIS", "NFLX", "BKNG",
    # Healthcare / Pharma
    "JNJ", "UNH", "PFE", "ABBV", "LLY", "BMY", "MRK", "AMGN", "GILD",
    "TMO", "ISRG", "DXCM", "VEEV",
    # Industrial / Aerospace / Defense
    "BA", "LMT", "RTX", "NOC", "GD", "GE", "CAT", "DE", "HON", "UPS",
    # Energy Majors
    "XOM", "CVX", "COP", "EOG", "SLB", "OXY",
    # Other Large-Cap
    "BRK-B", "T", "VZ", "IBM", "CSCO",
]

# Tier 1: Liquid mid-caps and popular swing trading names ($5-$50 range typically)
TIER1_MIDCAPS = [
    # Tech / Growth
    "SOFI", "PLTR", "HOOD", "RKLB", "IONQ", "JOBY", "DNA", "OPEN",
    "WISH", "BARK", "SKLZ", "GSAT", "BB", "NOK", "CLSK", "MARA",
    "RIOT", "HUT", "BITF", "CORZ", "AFRM", "UPST", "LC",
    "BIGC", "PATH", "AI", "S", "ASAN", "GRAB",
    "U", "RBLX", "SNAP", "PINS", "SPOT", "TTD", "ROKU",
    # AI / Quantum / Momentum
    "SOUN", "IREN", "RGTI", "QUBT", "ARQQ", "BBAI", "BFLY",
    "PDYN", "INFQ", "QBTS", "SMCI",
    # Biotech / Pharma
    "SNDL", "TLRY", "CGC", "ACB", "CRON",
    "VKTX", "MRNA", "CRSP", "BEAM", "NTLA",
    "LAZR", "INVZ", "NUVB", "CGTX", "EDIT",
    "DNLI", "FATE", "RXRX", "VERV", "ALNY",
    # Energy / EV / Clean
    "RIVN", "LCID", "NIO", "XPEV", "LI", "FCEL", "PLUG", "BE",
    "CHPT", "BLNK", "EVGO", "QS", "ENVX", "FLNC", "RUN",
    "ENPH", "SEDG", "NOVA", "ARRY",
    # Consumer / Retail / Travel
    "BBWI", "DKS", "VSCO", "ETSY", "W", "CHWY",
    "ABNB", "UBER", "LYFT", "DASH", "BROS", "CAVA",
    # Industrial / Materials / Mining
    "CLF", "X", "AA", "MP", "LAC", "ALB", "SQM",
    "VALE", "RIG", "HAL", "GOLD", "NEM",
    "FCX", "CENX", "BTU", "ARCH",
    # Fintech / Financial
    "NU", "COIN", "MSTR", "HIMS",
    # Space / Defense
    "LUNR", "ASTS", "RDW", "MNTS", "SPIR",
]

# Tier 2: Penny / small caps (<$5)
TIER2_PENNIES = [
    # EV / Clean energy
    "NKLA", "GOEV", "WKHS", "MULN", "EVTL", "FFIE",
    "GEVO", "NXXT", "VTNR", "TELL",
    # Biotech / Health
    "CLOV", "SEEL", "APRE", "BIOR", "BNGO",
    "EDSA", "AQST", "HOLO", "PRAX", "TGTX",
    # Tech / AI small-cap
    "GXAI", "ANY", "VCIG", "PRSO", "BBGI",
    "XPON", "DVLT", "AMCI", "BTBT", "WIMI",
    "MITI", "CXAI", "RCAT", "ACHR",
    # Mining / Resources
    "UUUU", "URG", "DNN", "NXE", "WULF",
    # Cannabis
    "HEXO", "VFF", "OGI", "GRWG",
    # Other speculative
    "TBLT", "IMPP", "COSM", "ATER", "IRNT",
]

# Tier 3: EU-Accessible UCITS ETFs & ETCs
# ─────────────────────────────────────────────────────────────────────────────
# EU PRIIPs regulation blocks retail investors from buying US-domiciled ETFs.
# All tickers below are UCITS-compliant or ETC-structured, tradeable via IBKR
# from Hungary. Suffix convention: .L = London, .DE = Xetra, .PA = Euronext Paris
# .AS = Euronext Amsterdam, .MI = Milan. Pick the exchange with best liquidity
# for your usual trading hours.
# ─────────────────────────────────────────────────────────────────────────────

TIER3_ETFS = [
    # ── Leveraged Bull (UCITS, hold days not weeks) ──
    # WisdomTree & Xtrackers leveraged products on LSE/Xetra
    "QQQ3.L",     # WisdomTree NASDAQ 100 3x Daily Leveraged
    "3USL.L",     # WisdomTree S&P 500 3x Daily Leveraged
    "3GOL.L",     # WisdomTree Gold 3x Daily Leveraged
    "3OIL.L",     # WisdomTree WTI Crude Oil 3x Daily Leveraged
    "3NGS.L",     # WisdomTree Natural Gas 3x Daily Leveraged
    "3SIL.L",     # WisdomTree Silver 3x Daily Leveraged
    "DBPG.DE",    # Xtrackers S&P 500 2x Leveraged Daily Swap UCITS
    "LVE.PA",     # Amundi EURO STOXX 50 Daily 2x Leveraged UCITS

    # ── Leveraged Bear / Short ──
    "QQQS.L",     # WisdomTree NASDAQ 100 3x Daily Short
    "3USS.L",     # WisdomTree S&P 500 3x Daily Short
    "3GOS.L",     # WisdomTree Gold 3x Daily Short
    "3OIS.L",     # WisdomTree WTI Crude Oil 3x Daily Short

    # ── Broad Market (non-leveraged) ──
    "SXR8.DE",    # iShares Core S&P 500 UCITS (your core holding)
    "EQQQ.DE",    # Invesco NASDAQ 100 UCITS
    "EUNL.DE",    # iShares Core MSCI World UCITS
    "VWCE.DE",    # Vanguard FTSE All-World UCITS
    "EXSA.DE",    # iShares STOXX Europe 600 UCITS
    "ZPRR.DE",    # SPDR Russell 2000 US Small Cap UCITS

    # ── US Sector (UCITS on LSE, also available on Xetra under different tickers) ──
    "IUIT.L",     # iShares S&P 500 IT Sector UCITS
    "IUES.L",     # iShares S&P 500 Energy Sector UCITS
    "IUFS.L",     # iShares S&P 500 Financials Sector UCITS
    "IUHC.L",     # iShares S&P 500 Health Care Sector UCITS
    "IUCD.L",     # iShares S&P 500 Consumer Discretionary UCITS
    "IUCS.L",     # iShares S&P 500 Consumer Staples UCITS
    "IUMS.L",     # iShares S&P 500 Materials Sector UCITS
    "IUIS.L",     # iShares S&P 500 Industrials Sector UCITS
    "IUUS.L",     # iShares S&P 500 Utilities Sector UCITS

    # ── European Sector ──
    "EXV1.DE",    # iShares STOXX Europe 600 Banks UCITS
    "EXV6.DE",    # iShares STOXX Europe 600 Basic Resources UCITS
    "EXH1.DE",    # iShares STOXX Europe 600 Technology UCITS
    "EXV5.DE",    # iShares STOXX Europe 600 Food & Beverage UCITS
    "EXH7.DE",    # iShares STOXX Europe 600 Health Care UCITS
    "EXV4.DE",    # iShares STOXX Europe 600 Industrial Goods UCITS

    # ── Thematic / Sector (UCITS) ──
    "IQQH.DE",    # iShares Global Clean Energy UCITS
    "L0CK.DE",    # iShares Digital Security UCITS
    "XMLD.DE",    # iShares Digitalisation UCITS
    "2B76.DE",    # iShares Automation & Robotics UCITS
    "ECAR.DE",    # iShares Electric Vehicles and Driving Technology UCITS
    "SEMI.L",     # VanEck Semiconductor UCITS
    "DGTL.L",     # iShares Digitalisation UCITS (LSE)

    # ── Commodities (ETCs — no KID issue for most) ──
    "IGLN.L",     # iShares Physical Gold ETC
    "ISLN.L",     # iShares Physical Silver ETC
    "PHAU.L",     # WisdomTree Physical Gold
    "PHAG.L",     # WisdomTree Physical Silver
    "PHPT.L",     # WisdomTree Physical Platinum
    "PHPD.L",     # WisdomTree Physical Palladium
    "CRUD.L",     # WisdomTree WTI Crude Oil ETC
    "NGAS.L",     # WisdomTree Natural Gas ETC
    "AIGA.L",     # WisdomTree All Commodities ETC

    # ── Bonds / Rates (UCITS) ──
    "IDTL.L",     # iShares $ Treasury Bond 20+yr UCITS
    "DTLA.L",     # iShares $ Treasury Bond 20+yr UCITS (dist)
    "IBTS.L",     # iShares $ Treasury Bond 1-3yr UCITS
    "LQDE.L",     # iShares $ Corporate Bond UCITS
    "IHYG.L",     # iShares € High Yield Corp Bond UCITS
    "IEAG.L",     # iShares Core € Govt Bond UCITS

    # ── Emerging Markets / Regional ──
    "IS3N.DE",    # iShares Core MSCI EM IMI UCITS
    "FXC.L",      # iShares China Large Cap UCITS
    "CNYA.L",     # iShares MSCI China A UCITS
    "IBZL.L",     # iShares MSCI Brazil UCITS
    "IJPA.L",     # iShares Core MSCI Japan IMI UCITS
    "NDIA.L",     # iShares MSCI India UCITS
    "IEMS.L",     # iShares Core MSCI EM IMI UCITS (LSE)

    # ── Mining / Resources (UCITS) ──
    "IS0E.DE",    # iShares Gold Producers UCITS
    "APTS.L",     # Sprott Uranium Miners UCITS (if available)
    "GDX.L",      # VanEck Gold Miners UCITS
    "GDXJ.L",     # VanEck Junior Gold Miners UCITS

    # ── Volatility / Hedging ──
    # Note: VIX-based products are very limited in EU. These are the few available:
    "VOOL.L",     # Lyxor S&P 500 VIX Futures Enhanced Roll UCITS
]


# ── Analysis Engine ─────────────────────────────────────────────────────────

@dataclass
class TargetMethod:
    name: str
    price: float
    label: str   # short explanation


@dataclass
class TargetAnalysis:
    methods: list          # list of TargetMethod
    confluence_zone: tuple  # (low, high) where multiple methods agree
    suggested_target: float # conservative: lowest realistic target
    risk_reward: float
    first_obstacle: float = 0.0  # nearest resistance level


@dataclass
class ScanResult:
    ticker: str
    setup: str            # "PULLBACK" or "BREAKOUT"
    score: int            # 0-100 composite score
    price: float
    change_1d: float      # % change today
    rsi: float
    rel_volume: float     # today's volume / 20-day avg
    above_50sma: bool
    near_20ema: bool      # within 3% of 20 EMA
    avg_volume: float
    market_cap: Optional[float] = None
    atr_pct: float = 0.0  # ATR as % of price (volatility)
    suggested_stop: float = 0.0
    targets: Optional[TargetAnalysis] = None
    # Quality fields
    adx: float = 0.0             # Trend strength (>25 = trending)
    sma_slope: float = 0.0       # 50 SMA slope (positive = rising trend)
    macd_bullish: bool = False    # MACD above signal line
    weekly_aligned: bool = False  # Weekly trend agrees with daily
    market_regime: str = ""       # "BULLISH", "BEARISH", or "NEUTRAL"
    obstacles: int = 0            # Number of resistance levels before target
    confidence: str = ""          # "HIGH", "MEDIUM", "LOW"
    # All-Time High fields
    ath: float = 0.0              # All-time high price
    ath_dist_pct: float = 0.0     # Distance from ATH as % (negative = below)
    ath_zone: str = ""            # "NEW_ATH", "NEAR_ATH", "MODERATE", "FAR", "DEEP"
    notes: list = field(default_factory=list)


def fetch_data(ticker: str, period: str = "3mo") -> Optional[pd.DataFrame]:
    """Fetch OHLCV data for a ticker. If EVAL_DATE is set, fetches historical data
    ending on that date (inclusive)."""
    try:
        t = yf.Ticker(ticker)

        if EVAL_DATE is not None:
            # Need ~100 trading days before EVAL_DATE for indicators (50 SMA + buffer)
            start_date = EVAL_DATE - timedelta(days=200)  # ~200 calendar days ≈ 140 trading days
            end_date = EVAL_DATE + timedelta(days=1)       # yfinance end is exclusive
            df = t.history(start=start_date, end=end_date, auto_adjust=True)
        else:
            df = t.history(period=period, auto_adjust=True)

        if df is None or len(df) < 50:
            return None

        if EVAL_DATE is not None:
            # Truncate to ensure we don't have data after EVAL_DATE
            df = df[df.index.date <= EVAL_DATE]
            if len(df) < 50:
                return None
        elif DROP_INCOMPLETE and len(df) > 50:
            df = df.iloc[:-1]  # Drop today's incomplete candle

        return df
    except Exception:
        return None


# Cache for ATH data (avoid re-fetching for each ticker)
_ath_cache = {}


def fetch_ath(ticker: str) -> tuple:
    """
    Fetch All-Time High data for a ticker using max available history.
    If EVAL_DATE is set, only considers data up to that date.
    Returns (ath_price, distance_pct, zone_label) or (0, 0, "UNKNOWN").

    Zones:
      NEW_ATH  — within 1% of ATH or making new ATH (clear skies, no resistance)
      NEAR_ATH — within 10% of ATH (minimal overhead supply)
      MODERATE — 10-30% below ATH (some overhead resistance)
      FAR      — 30-60% below ATH (heavy overhead supply)
      DEEP     — 60%+ below ATH (distressed, massive resistance above)
    """
    if ticker in _ath_cache:
        return _ath_cache[ticker]

    try:
        t = yf.Ticker(ticker)

        if EVAL_DATE is not None:
            end_date = EVAL_DATE + timedelta(days=1)
            df_long = t.history(start=EVAL_DATE - timedelta(days=365*5), end=end_date, auto_adjust=True)
            if df_long is not None and len(df_long) > 0:
                df_long = df_long[df_long.index.date <= EVAL_DATE]
        else:
            df_long = t.history(period="5y", auto_adjust=True)

        if df_long is None or len(df_long) < 20:
            if EVAL_DATE is not None:
                end_date = EVAL_DATE + timedelta(days=1)
                df_long = t.history(start=EVAL_DATE - timedelta(days=365*2), end=end_date, auto_adjust=True)
                if df_long is not None and len(df_long) > 0:
                    df_long = df_long[df_long.index.date <= EVAL_DATE]
            else:
                df_long = t.history(period="2y", auto_adjust=True)

        if df_long is None or len(df_long) < 20:
            result = (0, 0, "UNKNOWN")
            _ath_cache[ticker] = result
            return result

        ath = df_long["High"].max()
        current = df_long["Close"].iloc[-1]
        dist_pct = ((current - ath) / ath) * 100  # Negative = below ATH

        if dist_pct >= -1:
            zone = "NEW_ATH"
        elif dist_pct >= -10:
            zone = "NEAR_ATH"
        elif dist_pct >= -30:
            zone = "MODERATE"
        elif dist_pct >= -60:
            zone = "FAR"
        else:
            zone = "DEEP"

        result = (round(ath, 2), round(dist_pct, 1), zone)
        _ath_cache[ticker] = result
        return result
    except Exception:
        result = (0, 0, "UNKNOWN")
        _ath_cache[ticker] = result
        return result


def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators to dataframe."""
    df = df.copy()
    df["SMA_50"] = ta.trend.sma_indicator(df["Close"], window=50)
    df["EMA_20"] = ta.trend.ema_indicator(df["Close"], window=20)
    df["EMA_9"] = ta.trend.ema_indicator(df["Close"], window=9)
    df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
    df["ATR"] = ta.volatility.average_true_range(df["High"], df["Low"], df["Close"], window=14)
    df["Vol_SMA20"] = df["Volume"].rolling(20).mean()
    df["Rel_Volume"] = df["Volume"] / df["Vol_SMA20"]

    # ADX — trend strength (>25 = trending, <20 = choppy)
    adx_indicator = ta.trend.ADXIndicator(df["High"], df["Low"], df["Close"], window=14)
    df["ADX"] = adx_indicator.adx()
    df["DI_Plus"] = adx_indicator.adx_pos()
    df["DI_Minus"] = adx_indicator.adx_neg()

    # MACD — momentum confirmation
    macd = ta.trend.MACD(df["Close"], window_slow=26, window_fast=12, window_sign=9)
    df["MACD"] = macd.macd()
    df["MACD_Signal"] = macd.macd_signal()
    df["MACD_Hist"] = macd.macd_diff()

    # Bollinger Bands for consolidation detection
    bb = ta.volatility.BollingerBands(df["Close"], window=20, window_dev=2)
    df["BB_Width"] = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()
    df["BB_Upper"] = bb.bollinger_hband()

    # Recent high/low for range detection
    df["High_20"] = df["High"].rolling(20).max()
    df["Low_20"] = df["Low"].rolling(20).min()
    df["Range_Pct"] = (df["High_20"] - df["Low_20"]) / df["Low_20"] * 100

    # SMA slope — is the 50 SMA actually rising?
    df["SMA_50_Slope"] = (df["SMA_50"] - df["SMA_50"].shift(5)) / df["SMA_50"].shift(5) * 100

    return df


def find_swing_points(df: pd.DataFrame, window: int = 5) -> tuple:
    """Find the most recent swing low and swing high for Fibonacci calculation."""
    highs = df["High"].values
    lows = df["Low"].values
    n = len(df)

    swing_high = None
    swing_high_idx = None
    swing_low = None
    swing_low_idx = None

    # Walk backwards to find most recent swing high
    for i in range(n - 1 - window, window, -1):
        if all(highs[i] >= highs[i - j] for j in range(1, window + 1)) and \
           all(highs[i] >= highs[i + j] for j in range(1, min(window + 1, n - i))):
            swing_high = highs[i]
            swing_high_idx = i
            break

    # Walk backwards to find most recent swing low BEFORE the swing high
    start = (swing_high_idx - 1) if swing_high_idx else n - 1 - window
    for i in range(start, window, -1):
        if all(lows[i] <= lows[i - j] for j in range(1, window + 1)) and \
           all(lows[i] <= lows[i + j] for j in range(1, min(window + 1, n - i))):
            swing_low = lows[i]
            swing_low_idx = i
            break

    return swing_low, swing_high, swing_low_idx, swing_high_idx


def compute_targets(df: pd.DataFrame, price: float, stop: float,
                    setup: str, atr: float) -> TargetAnalysis:
    """
    Compute profit targets using 5 methods:
      1. ATR-Based           — mechanical, based on volatility
      2. Previous High/Low   — historical support/resistance
      3. Measured Move       — range projection from consolidation
      4. Fibonacci Extension — swing-based mathematical levels
      5. EMA Distance        — mean reversion based on typical stretch
    """
    methods = []

    # ── Method 1: ATR-Based ──────────────────────────────────────────────
    if setup == "PULLBACK":
        atr_target = round(price + 2 * atr, 2)
        methods.append(TargetMethod("ATR (2×)", atr_target, "Entry + 2× avg daily range"))
    else:
        atr_target = round(price + 3 * atr, 2)
        methods.append(TargetMethod("ATR (3×)", atr_target, "Entry + 3× avg daily range"))

    # ── Method 2: Previous Highs (Resistance Levels) ─────────────────────
    # Find the nearest significant resistance above current price
    recent_highs = df["High"].iloc[-60:]  # Look back ~3 months
    resistance_levels = []
    # Find local maxima
    for i in range(2, len(recent_highs) - 2):
        h = recent_highs.iloc[i]
        if h > recent_highs.iloc[i-1] and h > recent_highs.iloc[i-2] and \
           h > recent_highs.iloc[i+1] and h > recent_highs.iloc[i+2] and h > price:
            resistance_levels.append(h)

    # Also add the absolute high of the period
    period_high = df["High"].iloc[-60:].max()
    if period_high > price:
        resistance_levels.append(period_high)

    if resistance_levels:
        # Pick the nearest resistance above price
        nearest_resistance = min(resistance_levels)
        prev_high_target = round(nearest_resistance, 2)
        methods.append(TargetMethod("Prev High", prev_high_target,
                                    f"Nearest resistance from recent highs"))
    else:
        # No resistance found above — use 52-week high if available
        all_time_high = df["High"].max()
        if all_time_high > price:
            prev_high_target = round(all_time_high, 2)
            methods.append(TargetMethod("Prev High", prev_high_target,
                                        "Period high (no nearer resistance)"))

    # ── Method 3: Measured Move ──────────────────────────────────────────
    high_20 = df["High"].iloc[-21:-1].max()
    low_20 = df["Low"].iloc[-21:-1].min()
    range_height = high_20 - low_20

    if setup == "BREAKOUT":
        measured_target = round(high_20 + range_height, 2)
        methods.append(TargetMethod("Measured Move", measured_target,
                                    f"Breakout + range height (${range_height:.2f})"))
    else:
        # For pullbacks, project from support level
        measured_target = round(price + range_height * 0.75, 2)
        methods.append(TargetMethod("Measured Move", measured_target,
                                    f"Entry + 75% of range (${range_height:.2f})"))

    # ── Method 4: Fibonacci Extensions ───────────────────────────────────
    swing_low, swing_high, _, _ = find_swing_points(df)

    if swing_low is not None and swing_high is not None and swing_low < swing_high:
        swing_range = swing_high - swing_low
        fib_1272 = round(swing_low + swing_range * 1.272, 2)
        fib_1618 = round(swing_low + swing_range * 1.618, 2)

        # Pick the Fibonacci level closest above current price
        fib_levels = [(1.272, fib_1272), (1.618, fib_1618)]
        valid_fibs = [(label, val) for label, val in fib_levels if val > price]

        if valid_fibs:
            fib_label, fib_target = valid_fibs[0]  # nearest above price
            methods.append(TargetMethod(f"Fib {fib_label:.3f}", fib_target,
                                        f"Swing ${swing_low:.2f}→${swing_high:.2f}, ext {fib_label}×"))
            # Add second fib as bonus info if available
            if len(valid_fibs) > 1:
                fib_label2, fib_target2 = valid_fibs[1]
                methods.append(TargetMethod(f"Fib {fib_label2:.3f}", fib_target2,
                                            f"Extended fib target (aggressive)"))

    # ── Method 5: EMA Distance (Mean Reversion) ─────────────────────────
    # How far above the 20 EMA does this stock typically get before pulling back?
    ema20_series = df["EMA_20"].iloc[-60:]
    close_series = df["Close"].iloc[-60:]

    if len(ema20_series) > 0 and not ema20_series.isna().all():
        pct_above_ema = ((close_series - ema20_series) / ema20_series * 100)
        # Only look at positive excursions (above EMA)
        positive_excursions = pct_above_ema[pct_above_ema > 0]

        if len(positive_excursions) > 5:
            # Use 75th percentile of historical stretch above EMA
            typical_stretch = positive_excursions.quantile(0.75)
            current_ema20 = df["EMA_20"].iloc[-1]

            if not pd.isna(current_ema20) and typical_stretch > 0:
                ema_target = round(current_ema20 * (1 + typical_stretch / 100), 2)
                if ema_target > price:
                    methods.append(TargetMethod("EMA Stretch", ema_target,
                                                f"75th pctl stretch above 20 EMA ({typical_stretch:.1f}%)"))

    # ── Confluence Analysis ──────────────────────────────────────────────
    # Find where multiple methods cluster together
    target_prices = sorted([m.price for m in methods if m.price > price])

    if len(target_prices) >= 2:
        # Find the tightest cluster of targets
        best_cluster = []
        best_spread = float("inf")

        for i in range(len(target_prices)):
            cluster = [target_prices[i]]
            for j in range(i + 1, len(target_prices)):
                # Within 3% of each other = same zone
                if (target_prices[j] - target_prices[i]) / target_prices[i] < 0.03:
                    cluster.append(target_prices[j])
            if len(cluster) >= 2:
                spread = cluster[-1] - cluster[0]
                if spread < best_spread:
                    best_spread = spread
                    best_cluster = cluster

        if best_cluster:
            zone_low = min(best_cluster)
            zone_high = max(best_cluster)
            suggested = round((zone_low + zone_high) / 2, 2)
        else:
            # No tight cluster — use the most conservative (lowest) target
            zone_low = target_prices[0]
            zone_high = target_prices[0]
            suggested = target_prices[0]
    elif len(target_prices) == 1:
        zone_low = target_prices[0]
        zone_high = target_prices[0]
        suggested = target_prices[0]
    else:
        # Fallback to ATR-based
        zone_low = atr_target
        zone_high = atr_target
        suggested = atr_target

    risk = price - stop
    rr = (suggested - price) / risk if risk > 0 else 0

    # Find first obstacle (nearest resistance)
    first_obstacle = target_prices[0] if target_prices else suggested

    return TargetAnalysis(
        methods=methods,
        confluence_zone=(round(zone_low, 2), round(zone_high, 2)),
        suggested_target=suggested,
        risk_reward=round(rr, 2),
        first_obstacle=round(first_obstacle, 2),
    )


# ── Market Context & Quality Filters ───────────────────────────────────────

# Cache for market regime (avoid re-fetching SPY for every ticker)
_market_regime_cache = {"regime": None, "spy_data": None}


def check_market_regime() -> tuple:
    """
    Check overall market health using SPY (S&P 500 ETF).
    If EVAL_DATE is set, evaluates as of that historical date.
    Returns (regime_str, spy_df) where regime is BULLISH/BEARISH/NEUTRAL.
    """
    if _market_regime_cache["regime"] is not None:
        return _market_regime_cache["regime"], _market_regime_cache["spy_data"]

    try:
        spy = yf.Ticker("SPY")

        if EVAL_DATE is not None:
            start_date = EVAL_DATE - timedelta(days=200)
            end_date = EVAL_DATE + timedelta(days=1)
            spy_df = spy.history(start=start_date, end=end_date, auto_adjust=True)
            if spy_df is not None and len(spy_df) > 0:
                spy_df = spy_df[spy_df.index.date <= EVAL_DATE]
        else:
            spy_df = spy.history(period="3mo", auto_adjust=True)

        if spy_df is None or len(spy_df) < 50:
            _market_regime_cache["regime"] = "UNKNOWN"
            return "UNKNOWN", None

        if EVAL_DATE is None and DROP_INCOMPLETE and len(spy_df) > 50:
            spy_df = spy_df.iloc[:-1]

        sma50 = spy_df["Close"].rolling(50).mean().iloc[-1]
        ema20 = spy_df["Close"].ewm(span=20).mean().iloc[-1]
        price = spy_df["Close"].iloc[-1]
        # SPY ADX
        adx_ind = ta.trend.ADXIndicator(spy_df["High"], spy_df["Low"], spy_df["Close"], window=14)
        spy_adx = adx_ind.adx().iloc[-1]

        if price > sma50 and price > ema20:
            regime = "BULLISH"
        elif price < sma50 and price < ema20:
            regime = "BEARISH"
        else:
            regime = "NEUTRAL"

        _market_regime_cache["regime"] = regime
        _market_regime_cache["spy_data"] = spy_df
        return regime, spy_df
    except Exception:
        _market_regime_cache["regime"] = "UNKNOWN"
        return "UNKNOWN", None


def check_weekly_trend(ticker: str) -> bool:
    """
    Check if the weekly trend aligns with the daily setup (bullish).
    Returns True if the weekly close is above the weekly 10-period SMA.
    If EVAL_DATE is set, truncates weekly data to that date.
    """
    try:
        t = yf.Ticker(ticker)

        if EVAL_DATE is not None:
            end_date = EVAL_DATE + timedelta(days=1)
            start_date = EVAL_DATE - timedelta(days=200)
            wk = t.history(start=start_date, end=end_date, interval="1wk", auto_adjust=True)
            if wk is not None and len(wk) > 0:
                wk = wk[wk.index.date <= EVAL_DATE]
        else:
            wk = t.history(period="6mo", interval="1wk", auto_adjust=True)

        if wk is None or len(wk) < 10:
            return True  # Can't determine, give benefit of doubt

        sma10w = wk["Close"].rolling(10).mean().iloc[-1]
        price = wk["Close"].iloc[-1]

        if pd.isna(sma10w):
            return True

        return price > sma10w
    except Exception:
        return True  # Can't determine, give benefit of doubt


def count_resistance_obstacles(df: pd.DataFrame, price: float, target: float) -> tuple:
    """
    Count significant resistance levels between current price and target.
    Returns (count, list_of_levels).
    """
    recent_highs = df["High"].iloc[-60:]
    levels = []

    # Find local maxima (resistance points)
    for i in range(2, len(recent_highs) - 2):
        h = recent_highs.iloc[i]
        if (h > recent_highs.iloc[i-1] and h > recent_highs.iloc[i-2] and
            h > recent_highs.iloc[i+1] and h > recent_highs.iloc[i+2]):
            # Only count levels between price and target
            if price < h < target:
                # Deduplicate: don't count levels within 1% of each other
                if not any(abs(h - existing) / existing < 0.01 for existing in levels):
                    levels.append(round(h, 2))

    # Add round number levels (psychological resistance)
    if price > 5:
        step = 5 if price > 20 else 1
        round_level = (int(price / step) + 1) * step
        while round_level < target:
            if not any(abs(round_level - existing) / existing < 0.02 for existing in levels):
                levels.append(round_level)
            round_level += step

    levels.sort()
    return len(levels), levels


def compute_confidence(score: int, adx: float, weekly_aligned: bool,
                       market_regime: str, obstacles: int, rr: float,
                       sma_slope: float, macd_bullish: bool,
                       ath_zone: str = "") -> str:
    """
    Compute overall confidence rating based on multiple quality signals.
    """
    points = 0

    # Score contribution (0-3)
    if score >= 80:
        points += 3
    elif score >= 70:
        points += 2
    elif score >= 60:
        points += 1

    # Trend strength (0-3)
    if adx >= 30:
        points += 3
    elif adx >= 25:
        points += 2
    elif adx >= 20:
        points += 1

    # Weekly alignment (0-2)
    if weekly_aligned:
        points += 2

    # Market regime (0-2)
    if market_regime == "BULLISH":
        points += 2
    elif market_regime == "NEUTRAL":
        points += 1
    # BEARISH = 0

    # Obstacles (-1 to 0)
    if obstacles >= 3:
        points -= 1

    # R/R ratio (0-2)
    if rr >= 3.0:
        points += 2
    elif rr >= 2.0:
        points += 1

    # SMA slope (0-1)
    if sma_slope > 0.5:
        points += 1

    # MACD (0-1)
    if macd_bullish:
        points += 1

    # ATH zone (−2 to +3)
    if ath_zone == "NEW_ATH":
        points += 3    # No overhead resistance, strongest momentum
    elif ath_zone == "NEAR_ATH":
        points += 2    # Minimal resistance above
    elif ath_zone == "MODERATE":
        points += 0    # Neutral — some resistance
    elif ath_zone == "FAR":
        points -= 1    # Heavy overhead supply
    elif ath_zone == "DEEP":
        points -= 2    # Distressed — massive resistance, likely broken stock

    # Total: max ~18
    if points >= 12:
        return "HIGH"
    elif points >= 7:
        return "MEDIUM"
    else:
        return "LOW"


def backtest_setups(ticker_list: list, lookback_days: int = 60) -> dict:
    """
    Simple backtest: go back in time, find where setups triggered,
    and check if they would have hit target or stop first.
    """
    results = {"total": 0, "wins": 0, "losses": 0, "avg_gain": 0, "avg_loss": 0,
               "win_rate": 0, "avg_days_held": 0, "details": []}
    gains = []
    losses = []
    days_held_list = []

    for ticker in ticker_list:
        try:
            t = yf.Ticker(ticker)
            df = t.history(period="1y", auto_adjust=True)
            if df is None or len(df) < 100:
                continue

            df = compute_indicators(df)

            # Simulate entering at various points in the past
            for entry_idx in range(60, len(df) - lookback_days):
                sim_df = df.iloc[:entry_idx + 1]
                latest = sim_df.iloc[-1]

                # Quick pullback check
                price = latest["Close"]
                sma50 = latest["SMA_50"]
                ema20 = latest["EMA_20"]
                rsi = latest["RSI"]
                adx = latest["ADX"]
                atr = latest["ATR"]

                if pd.isna(sma50) or pd.isna(ema20) or pd.isna(rsi) or pd.isna(adx):
                    continue

                # Only check pullback setups (more common)
                if not (price > sma50 and abs(price - ema20) / ema20 < 0.03
                        and 30 <= rsi <= 45 and adx >= 20):
                    continue

                stop = round(ema20 - atr, 2)
                target = round(price + 2 * atr, 2)

                # Simulate forward
                future = df.iloc[entry_idx + 1: entry_idx + 1 + 15]  # max 15 days
                hit_target = False
                hit_stop = False
                days_held = 0

                for j, (_, row) in enumerate(future.iterrows()):
                    days_held = j + 1
                    if row["Low"] <= stop:
                        hit_stop = True
                        break
                    if row["High"] >= target:
                        hit_target = True
                        break

                results["total"] += 1

                if hit_target:
                    results["wins"] += 1
                    gain_pct = (target - price) / price * 100
                    gains.append(gain_pct)
                    days_held_list.append(days_held)
                    results["details"].append({
                        "ticker": ticker, "outcome": "WIN",
                        "gain": round(gain_pct, 2), "days": days_held
                    })
                elif hit_stop:
                    results["losses"] += 1
                    loss_pct = (stop - price) / price * 100
                    losses.append(loss_pct)
                    days_held_list.append(days_held)
                    results["details"].append({
                        "ticker": ticker, "outcome": "LOSS",
                        "gain": round(loss_pct, 2), "days": days_held
                    })
                else:
                    # Didn't hit either in 15 days — check final price
                    if len(future) > 0:
                        final = future.iloc[-1]["Close"]
                        pnl = (final - price) / price * 100
                        if pnl > 0:
                            results["wins"] += 1
                            gains.append(pnl)
                        else:
                            results["losses"] += 1
                            losses.append(pnl)
                        days_held_list.append(15)

        except Exception:
            continue

    if results["total"] > 0:
        results["win_rate"] = round(results["wins"] / results["total"] * 100, 1)
        results["avg_gain"] = round(sum(gains) / len(gains), 2) if gains else 0
        results["avg_loss"] = round(sum(losses) / len(losses), 2) if losses else 0
        results["avg_days_held"] = round(sum(days_held_list) / len(days_held_list), 1) if days_held_list else 0

    return results


def evaluate_pullback(df: pd.DataFrame, ticker: str) -> Optional[ScanResult]:
    """
    Setup A: Pullback to Support (STRICT version)
    Hard gates: above 50 SMA, SMA rising, ADX >= 20, near 20 EMA, RSI 30-50
    Soft scoring: volume decline, reversal candle, MACD, DI+/DI-
    """
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    price = latest["Close"]
    sma50 = latest["SMA_50"]
    ema20 = latest["EMA_20"]
    rsi = latest["RSI"]
    atr = latest["ATR"]
    rel_vol = latest["Rel_Volume"]
    avg_vol = latest["Vol_SMA20"]
    adx = latest["ADX"]
    sma_slope = latest["SMA_50_Slope"]
    macd_hist = latest["MACD_Hist"]
    di_plus = latest["DI_Plus"]
    di_minus = latest["DI_Minus"]

    if pd.isna(sma50) or pd.isna(ema20) or pd.isna(rsi) or pd.isna(adx):
        return None

    above_50 = price > sma50
    dist_to_ema20 = abs(price - ema20) / ema20 * 100
    near_ema20 = dist_to_ema20 < 3.0

    score = 0
    notes = []

    # ── HARD GATES (fail = reject) ──────────────────────────────────────

    # Must be in uptrend
    if not above_50:
        return None

    # 50 SMA must be RISING (not flat or declining)
    if pd.notna(sma_slope) and sma_slope < 0:
        return None  # Trend is weakening

    # ADX must show a real trend exists (not choppy sideways)
    if pd.notna(adx) and adx < 20:
        return None  # No trend, setup will likely fail

    # Must be near support
    if dist_to_ema20 > 5.0:
        return None

    # RSI must show pullback
    if rsi > 55 or rsi < 25:
        return None

    # ── SCORING ─────────────────────────────────────────────────────────

    # Trend quality (0-25)
    score += 15
    notes.append("Above rising 50 SMA ✓")
    if pd.notna(sma_slope) and sma_slope > 1.0:
        score += 10
        notes.append(f"Strong trend slope ({sma_slope:.1f}%) ✓")
    elif pd.notna(sma_slope) and sma_slope > 0:
        score += 5
        notes.append(f"Moderate trend slope ({sma_slope:.1f}%)")

    # ADX trend strength (0-15)
    if pd.notna(adx):
        if adx >= 30:
            score += 15
            notes.append(f"ADX {adx:.0f} — strong trend ✓")
        elif adx >= 25:
            score += 10
            notes.append(f"ADX {adx:.0f} — trending ✓")
        else:
            score += 5
            notes.append(f"ADX {adx:.0f} — weak trend ⚠️")

    # Support proximity (0-15)
    if near_ema20:
        score += 15
        notes.append(f"At 20 EMA support ({dist_to_ema20:.1f}% away) ✓")
    else:
        score += 5
        notes.append(f"Approaching 20 EMA ({dist_to_ema20:.1f}% away)")

    # RSI zone (0-15)
    if 30 <= rsi <= 40:
        score += 15
        notes.append(f"RSI {rsi:.0f} — ideal oversold ✓")
    elif 40 < rsi <= 50:
        score += 10
        notes.append(f"RSI {rsi:.0f} — mild pullback")
    else:
        score += 3
        notes.append(f"RSI {rsi:.0f} — edge of range ⚠️")

    # Volume declining (0-10)
    vol_3d_avg = df["Volume"].iloc[-3:].mean()
    vol_10d_avg = df["Volume"].iloc[-10:].mean()
    if vol_3d_avg < vol_10d_avg * 0.8:
        score += 10
        notes.append("Volume clearly declining ✓")
    elif vol_3d_avg < vol_10d_avg:
        score += 5
        notes.append("Volume slightly declining")

    # Reversal candle (0-10)
    body = latest["Close"] - latest["Open"]
    if body > 0 and latest["Close"] > prev["Close"]:
        score += 10
        notes.append("Green reversal candle ✓")

    # MACD momentum (0-5)
    macd_bullish = False
    if pd.notna(macd_hist):
        if macd_hist > 0:
            score += 5
            notes.append("MACD histogram positive ✓")
            macd_bullish = True
        else:
            prev_macd = prev["MACD_Hist"] if "MACD_Hist" in prev.index and pd.notna(prev["MACD_Hist"]) else None
            if prev_macd is not None and macd_hist > prev_macd:
                score += 3
                notes.append("MACD histogram improving")
                macd_bullish = True

    # DI+ > DI- (0-5)
    if pd.notna(di_plus) and pd.notna(di_minus) and di_plus > di_minus:
        score += 5
        notes.append("DI+ > DI- (buyers stronger) ✓")

    # Calculate stop and targets
    atr_pct = (atr / price) * 100 if price > 0 else 0
    stop = round(ema20 - atr, 2)

    targets = compute_targets(df, price, stop, "PULLBACK", atr)

    # Count resistance obstacles
    if targets:
        obstacles, obstacle_levels = count_resistance_obstacles(
            df, price, targets.suggested_target)
        if obstacles >= 3:
            notes.append(f"⚠️ {obstacles} resistance levels before target")
    else:
        obstacles = 0

    change_1d = ((latest["Close"] - prev["Close"]) / prev["Close"]) * 100

    return ScanResult(
        ticker=ticker, setup="PULLBACK", score=min(score, 100),
        price=round(price, 2), change_1d=round(change_1d, 2),
        rsi=round(rsi, 1), rel_volume=round(rel_vol, 2),
        above_50sma=above_50, near_20ema=near_ema20,
        avg_volume=round(avg_vol), market_cap=None,
        atr_pct=round(atr_pct, 2),
        suggested_stop=stop, targets=targets,
        adx=round(adx, 1) if pd.notna(adx) else 0,
        sma_slope=round(sma_slope, 2) if pd.notna(sma_slope) else 0,
        macd_bullish=macd_bullish,
        obstacles=obstacles,
        notes=notes,
    )


def evaluate_breakout(df: pd.DataFrame, ticker: str) -> Optional[ScanResult]:
    """
    Setup B: Breakout with Volume (STRICT version)
    Hard gates: above 50 SMA, breaking 20-day high, volume >= 1.5x, ADX >= 20
    Soft scoring: close position, BB squeeze, MACD, DI+/DI-
    """
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    price = latest["Close"]
    high_20_prev = df["High"].iloc[-21:-1].max()
    rsi = latest["RSI"]
    rel_vol = latest["Rel_Volume"]
    atr = latest["ATR"]
    avg_vol = latest["Vol_SMA20"]
    sma50 = latest["SMA_50"]
    adx = latest["ADX"]
    sma_slope = latest["SMA_50_Slope"]
    macd_hist = latest["MACD_Hist"]
    di_plus = latest["DI_Plus"]
    di_minus = latest["DI_Minus"]

    if pd.isna(sma50) or pd.isna(rsi) or pd.isna(high_20_prev) or pd.isna(adx):
        return None

    above_50 = price > sma50
    breakout = latest["High"] > high_20_prev

    # ── HARD GATES ──────────────────────────────────────────────────────

    if not breakout:
        return None

    # Must be above 50 SMA (trend alignment is now required)
    if not above_50:
        return None

    # Volume must be at least 1.5x (raised from 1.0x — weak volume breakouts fail)
    if rel_vol < 1.5:
        return None

    # ADX must show directional movement
    if pd.notna(adx) and adx < 20:
        return None

    # RSI can't be deeply overbought (>80 means exhaustion)
    if rsi > 80:
        return None

    # ── SCORING ─────────────────────────────────────────────────────────

    score = 0
    notes = []

    # Breakout confirmed (15)
    score += 15
    notes.append(f"Breaking 20-day high ({high_20_prev:.2f}) ✓")

    # Volume strength (0-20)
    if rel_vol >= 2.5:
        score += 20
        notes.append(f"Relative volume {rel_vol:.1f}x — very strong ✓")
    elif rel_vol >= 2.0:
        score += 17
        notes.append(f"Relative volume {rel_vol:.1f}x — strong ✓")
    else:
        score += 12
        notes.append(f"Relative volume {rel_vol:.1f}x — adequate ✓")

    # ADX trend strength (0-15)
    if pd.notna(adx):
        if adx >= 30:
            score += 15
            notes.append(f"ADX {adx:.0f} — strong trend ✓")
        elif adx >= 25:
            score += 10
            notes.append(f"ADX {adx:.0f} — trending ✓")
        else:
            score += 5
            notes.append(f"ADX {adx:.0f} — marginal trend")

    # Close position in day's range (0-15)
    day_range = latest["High"] - latest["Low"]
    if day_range > 0:
        close_position = (latest["Close"] - latest["Low"]) / day_range
        if close_position > 0.80:
            score += 15
            notes.append("Closed in top 20% of range ✓")
        elif close_position > 0.65:
            score += 10
            notes.append("Closed in upper third of range ✓")
        elif close_position > 0.5:
            score += 5
            notes.append("Closed in upper half")

    # Bollinger squeeze before breakout (0-10)
    bb_width_5d = df["BB_Width"].iloc[-6:-1].mean()
    bb_width_20d = df["BB_Width"].iloc[-21:-1].mean()
    if bb_width_5d < bb_width_20d:
        score += 10
        notes.append("Bollinger squeeze before breakout ✓")

    # SMA slope (0-5)
    if pd.notna(sma_slope) and sma_slope > 0.5:
        score += 5
        notes.append(f"50 SMA rising ({sma_slope:.1f}%) ✓")

    # MACD bullish (0-5)
    macd_bullish = False
    if pd.notna(macd_hist) and macd_hist > 0:
        score += 5
        notes.append("MACD histogram positive ✓")
        macd_bullish = True

    # DI+ > DI- (0-5)
    if pd.notna(di_plus) and pd.notna(di_minus) and di_plus > di_minus:
        score += 5
        notes.append("DI+ > DI- (buyers dominant) ✓")

    # RSI room to run (0-5)
    if rsi < 65:
        score += 5
        notes.append(f"RSI {rsi:.0f} — room to run ✓")
    elif rsi < 75:
        score += 2
        notes.append(f"RSI {rsi:.0f} — getting extended ⚠️")
    else:
        notes.append(f"RSI {rsi:.0f} — overbought ⚠️")

    # Calculate stop and targets
    atr_pct = (atr / price) * 100 if price > 0 else 0
    stop = round(high_20_prev - 0.5 * atr, 2)

    targets = compute_targets(df, price, stop, "BREAKOUT", atr)

    # Count resistance obstacles
    if targets:
        obstacles, obstacle_levels = count_resistance_obstacles(
            df, price, targets.suggested_target)
        if obstacles >= 3:
            notes.append(f"⚠️ {obstacles} resistance levels before target")
    else:
        obstacles = 0

    change_1d = ((latest["Close"] - prev["Close"]) / prev["Close"]) * 100

    return ScanResult(
        ticker=ticker, setup="BREAKOUT", score=min(score, 100),
        price=round(price, 2), change_1d=round(change_1d, 2),
        rsi=round(rsi, 1), rel_volume=round(rel_vol, 2),
        above_50sma=above_50, near_20ema=abs(price - latest["EMA_20"]) / latest["EMA_20"] < 0.03,
        avg_volume=round(avg_vol), market_cap=None,
        atr_pct=round(atr_pct, 2),
        suggested_stop=stop, targets=targets,
        adx=round(adx, 1) if pd.notna(adx) else 0,
        sma_slope=round(sma_slope, 2) if pd.notna(sma_slope) else 0,
        macd_bullish=macd_bullish,
        obstacles=obstacles,
        notes=notes,
    )


def scan_ticker(ticker: str) -> list[ScanResult]:
    """Run both setups on a single ticker with full context analysis."""
    df = fetch_data(ticker)
    if df is None:
        return []

    df = compute_indicators(df)
    results = []

    # Check market regime (cached, only fetched once)
    market_regime, _ = check_market_regime()

    # Fetch ATH data (cached per ticker)
    ath_price, ath_dist_pct, ath_zone = fetch_ath(ticker)

    for evaluate_fn in [evaluate_pullback, evaluate_breakout]:
        result = evaluate_fn(df, ticker)
        if result and result.score >= 40:
            # Filter out minimal/negative gain
            if not (result.targets and result.targets.suggested_target > result.price * 1.02):
                continue

            # Require R/R >= 1.5
            if result.targets and result.targets.risk_reward < 1.5:
                continue

            # Apply ATH data
            result.ath = ath_price
            result.ath_dist_pct = ath_dist_pct
            result.ath_zone = ath_zone

            # ATH score adjustments
            if ath_zone == "NEW_ATH":
                result.score = min(result.score + 10, 100)
                result.notes.append(f"🚀 At/near All-Time High ${ath_price:.2f} — no overhead resistance!")
            elif ath_zone == "NEAR_ATH":
                result.score = min(result.score + 5, 100)
                result.notes.append(f"ATH ${ath_price:.2f} ({ath_dist_pct:+.1f}%) — minimal resistance above ✓")
            elif ath_zone == "MODERATE":
                result.notes.append(f"ATH ${ath_price:.2f} ({ath_dist_pct:+.1f}%) — some overhead supply")
            elif ath_zone == "FAR":
                result.score = max(result.score - 5, 0)
                result.notes.append(f"⚠️ ATH ${ath_price:.2f} ({ath_dist_pct:+.1f}%) — heavy overhead supply")
            elif ath_zone == "DEEP":
                result.score = max(result.score - 10, 0)
                result.notes.append(f"⚠️ ATH ${ath_price:.2f} ({ath_dist_pct:+.1f}%) — distressed, massive resistance")

            # Add market regime
            result.market_regime = market_regime

            # Check weekly trend (extra fetch, but important)
            result.weekly_aligned = check_weekly_trend(ticker)

            # Compute confidence (now includes ATH zone)
            rr = result.targets.risk_reward if result.targets else 0
            result.confidence = compute_confidence(
                result.score, result.adx, result.weekly_aligned,
                market_regime, result.obstacles, rr,
                result.sma_slope, result.macd_bullish, ath_zone
            )

            # In BEARISH market, demote confidence
            if market_regime == "BEARISH":
                if result.confidence == "HIGH":
                    result.confidence = "MEDIUM"
                elif result.confidence == "MEDIUM":
                    result.confidence = "LOW"
                result.notes.append("⚠️ Market regime: BEARISH — increased risk")

            if not result.weekly_aligned:
                result.notes.append("⚠️ Weekly trend not aligned — higher risk")

            results.append(result)

    return results


# ── Output ──────────────────────────────────────────────────────────────────

def print_results(results: list[ScanResult], tier_label: str = ""):
    """Print formatted scan results."""
    if not results:
        print(f"\n  No setups found{' for ' + tier_label if tier_label else ''}.\n")
        return

    results.sort(key=lambda r: r.score, reverse=True)

    print(f"\n{'─' * 90}")
    if tier_label:
        print(f"  {tier_label}")
        print(f"{'─' * 90}")

    for r in results:
        t = r.targets
        # Confidence-based icon
        conf_icon = "🟢" if r.confidence == "HIGH" else "🟡" if r.confidence == "MEDIUM" else "🔴"
        print(f"\n  {conf_icon} {r.ticker:<6} | {r.setup:<10} | Score: {r.score}/100 | ${r.price:.2f} ({r.change_1d:+.1f}%) | Confidence: {r.confidence}")
        print(f"    ADX: {r.adx:.0f} | RSI: {r.rsi:.0f} | RelVol: {r.rel_volume:.1f}x | ATR%: {r.atr_pct:.1f}% | SMA Slope: {r.sma_slope:+.1f}%")
        mkt = r.market_regime or "?"
        wk = "✓" if r.weekly_aligned else "✗"
        macd = "✓" if r.macd_bullish else "✗"
        obs = f"{r.obstacles} levels" if r.obstacles > 0 else "clear"
        print(f"    Market: {mkt} | Weekly: {wk} | MACD: {macd} | Obstacles: {obs}")

        # ATH line
        if r.ath > 0:
            ath_icon = "🚀" if r.ath_zone == "NEW_ATH" else "✓" if r.ath_zone == "NEAR_ATH" else "—" if r.ath_zone == "MODERATE" else "⚠️"
            print(f"    ATH: ${r.ath:.2f} ({r.ath_dist_pct:+.1f}%) | Zone: {ath_icon} {r.ath_zone}")
        print(f"    Stop: ${r.suggested_stop:.2f}")

        # Target methods detail
        if t:
            print(f"    ┌─ PROFIT TARGETS ({'confluence' if t.confluence_zone[0] != t.confluence_zone[1] else 'best estimate'}) ─────")
            for m in t.methods:
                pct_gain = ((m.price - r.price) / r.price) * 100
                risk = r.price - r.suggested_stop
                rr = (m.price - r.price) / risk if risk > 0 else 0
                print(f"    │  {m.name:<16} ${m.price:<8.2f} (+{pct_gain:.1f}%)  R/R 1:{rr:.1f}  — {m.label}")

            if t.confluence_zone[0] != t.confluence_zone[1]:
                zone_methods = sum(1 for m in t.methods
                                   if t.confluence_zone[0] <= m.price <= t.confluence_zone[1] * 1.03)
                print(f"    │")
                print(f"    │  🎯 Confluence zone: ${t.confluence_zone[0]:.2f} – ${t.confluence_zone[1]:.2f} ({zone_methods} methods agree)")
            print(f"    │  ➜ Suggested target: ${t.suggested_target:.2f} (+{((t.suggested_target - r.price) / r.price) * 100:.1f}%)  R/R 1:{t.risk_reward:.1f}")
            print(f"    └{'─' * 60}")

        # Position sizing at $650 max
        if r.price > 0 and t:
            shares = int(650 / r.price)
            risk_per_share = r.price - r.suggested_stop
            total_risk = round(risk_per_share * shares, 2)
            potential_gain = round((t.suggested_target - r.price) * shares, 2)
            print(f"    → At $650 max: ~{shares} shares, risking ~${total_risk:.0f}, potential gain ~${potential_gain:.0f}")

        for note in r.notes:
            print(f"      • {note}")

    print(f"\n{'─' * 90}\n")


def print_single_analysis(ticker: str):
    """Detailed analysis of a single ticker."""
    print(f"\n{'═' * 70}")
    if EVAL_DATE is not None:
        print(f"  Detailed Analysis: {ticker} (as of {EVAL_DATE.strftime('%Y-%m-%d')})")
    else:
        print(f"  Detailed Analysis: {ticker}")
    print(f"{'═' * 70}")

    df = fetch_data(ticker)
    if df is None:
        if EVAL_DATE is not None:
            print(f"  Could not fetch data for {ticker} on {EVAL_DATE.strftime('%Y-%m-%d')}")
            print(f"  (the stock may not have existed yet, or the date may be a weekend/holiday)")
        else:
            print(f"  Could not fetch data for {ticker}")
        return

    df = compute_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]

    price = latest["Close"]
    change = ((price - prev["Close"]) / prev["Close"]) * 100
    data_date = latest.name.strftime('%Y-%m-%d') if hasattr(latest.name, 'strftime') else str(latest.name)

    print(f"\n  Data Date: {data_date}")
    print(f"  Price: ${price:.2f} ({change:+.2f}%)")
    print(f"  50 SMA: ${latest['SMA_50']:.2f}  {'(above ✓)' if price > latest['SMA_50'] else '(below ✗)'}")
    sma_slope = latest['SMA_50_Slope']
    slope_str = f"{sma_slope:+.1f}%" if pd.notna(sma_slope) else "N/A"
    print(f"  50 SMA Slope: {slope_str}  {'(rising ✓)' if pd.notna(sma_slope) and sma_slope > 0 else '(falling ✗)' if pd.notna(sma_slope) else ''}")
    print(f"  20 EMA: ${latest['EMA_20']:.2f}  (dist: {abs(price - latest['EMA_20']) / latest['EMA_20'] * 100:.1f}%)")
    print(f"  9 EMA:  ${latest['EMA_9']:.2f}")
    print(f"  RSI:    {latest['RSI']:.1f}")
    adx_val = latest['ADX']
    adx_str = f"{adx_val:.1f}" if pd.notna(adx_val) else "N/A"
    trend_label = "strong trend" if pd.notna(adx_val) and adx_val >= 25 else "trending" if pd.notna(adx_val) and adx_val >= 20 else "choppy/no trend"
    print(f"  ADX:    {adx_str} ({trend_label})")
    di_p = latest['DI_Plus']
    di_m = latest['DI_Minus']
    if pd.notna(di_p) and pd.notna(di_m):
        print(f"  DI+/DI-: {di_p:.1f} / {di_m:.1f}  {'(buyers ✓)' if di_p > di_m else '(sellers ✗)'}")
    macd_h = latest['MACD_Hist']
    if pd.notna(macd_h):
        print(f"  MACD Hist: {macd_h:.4f}  {'(bullish ✓)' if macd_h > 0 else '(bearish ✗)'}")
    print(f"  ATR:    ${latest['ATR']:.2f} ({latest['ATR'] / price * 100:.1f}% of price)")
    print(f"  RelVol: {latest['Rel_Volume']:.2f}x")
    print(f"  20d Range: ${latest['Low_20']:.2f} – ${latest['High_20']:.2f} ({latest['Range_Pct']:.1f}%)")
    print(f"  BB Width: {latest['BB_Width']:.3f}")

    # Market regime
    regime, _ = check_market_regime()
    regime_icon = "🟢" if regime == "BULLISH" else "🔴" if regime == "BEARISH" else "🟡"
    print(f"\n  Market Regime: {regime_icon} {regime}")

    # Weekly trend
    weekly = check_weekly_trend(ticker)
    print(f"  Weekly Trend:  {'✓ Aligned' if weekly else '✗ Not aligned'}")

    # All-Time High
    ath_price, ath_dist_pct, ath_zone = fetch_ath(ticker)
    if ath_price > 0:
        zone_icons = {"NEW_ATH": "🚀", "NEAR_ATH": "✓", "MODERATE": "—", "FAR": "⚠️", "DEEP": "🔴"}
        icon = zone_icons.get(ath_zone, "?")
        print(f"  ATH:           ${ath_price:.2f} ({ath_dist_pct:+.1f}%) | Zone: {icon} {ath_zone}")
        if ath_zone == "NEW_ATH":
            print(f"                 → No overhead resistance — strongest possible position")
        elif ath_zone == "NEAR_ATH":
            print(f"                 → Minimal overhead supply — favorable for upward moves")
        elif ath_zone == "MODERATE":
            print(f"                 → Some trapped buyers above — expect resistance")
        elif ath_zone == "FAR":
            print(f"                 → Heavy overhead supply — many sellers waiting to exit")
        elif ath_zone == "DEEP":
            print(f"                 → Massive resistance above — stock may be structurally broken")

    # 5-day price action
    print(f"\n  Last 5 Days:")
    for i in range(-5, 0):
        row = df.iloc[i]
        day_change = ((row["Close"] - df.iloc[i - 1]["Close"]) / df.iloc[i - 1]["Close"]) * 100
        bar = "▲" if row["Close"] > row["Open"] else "▼"
        vol_ratio = row["Volume"] / row["Vol_SMA20"] if row["Vol_SMA20"] > 0 else 0
        print(f"    {row.name.strftime('%m/%d')} {bar} ${row['Close']:.2f} ({day_change:+.1f}%)  Vol: {vol_ratio:.1f}x")

    # Run setups
    results = []
    pullback = evaluate_pullback(df, ticker)
    if pullback:
        results.append(pullback)
    breakout = evaluate_breakout(df, ticker)
    if breakout:
        results.append(breakout)

    if results:
        print_results(results, f"Setups Found for {ticker}")
    else:
        print(f"\n  No qualifying setups found for {ticker}.")
        print(f"  Reasons:")
        if price < latest["SMA_50"]:
            print(f"    • Below 50 SMA — not in uptrend")
        if pd.notna(sma_slope) and sma_slope < 0:
            print(f"    • 50 SMA declining ({sma_slope:+.1f}%) — trend weakening")
        if pd.notna(adx_val) and adx_val < 20:
            print(f"    • ADX {adx_val:.0f} — no real trend (choppy market)")
        dist = abs(price - latest["EMA_20"]) / latest["EMA_20"] * 100
        if dist > 5:
            print(f"    • {dist:.1f}% from 20 EMA — not at pullback support")
        if latest["RSI"] > 55:
            print(f"    • RSI {latest['RSI']:.0f} — not oversold enough for pullback")
        if latest["RSI"] < 25:
            print(f"    • RSI {latest['RSI']:.0f} — momentum too weak")
        if pd.notna(di_p) and pd.notna(di_m) and di_m > di_p:
            print(f"    • DI- > DI+ — sellers dominating")

    # Always show target analysis in --ticker mode
    atr = latest["ATR"]
    ema20 = latest["EMA_20"]
    stop = 0.0
    targets = None
    if not pd.isna(atr) and not pd.isna(ema20) and price > 0:
        # Use a reasonable stop for target calculation
        stop = round(ema20 - atr, 2) if price > ema20 else round(price - atr, 2)
        setup_type = "BREAKOUT" if latest["High"] > df["High"].iloc[-21:-1].max() else "PULLBACK"
        targets = compute_targets(df, price, stop, setup_type, atr)

        print(f"\n  {'═' * 60}")
        print(f"  TARGET ANALYSIS (all 5 methods)")
        print(f"  {'─' * 60}")
        for m in targets.methods:
            pct = ((m.price - price) / price) * 100
            risk = price - stop
            rr = (m.price - price) / risk if risk > 0 else 0
            marker = "◆" if targets.confluence_zone[0] <= m.price <= targets.confluence_zone[1] * 1.03 else "◇"
            print(f"    {marker} {m.name:<16} ${m.price:<8.2f} ({pct:+.1f}%)  R/R 1:{rr:.1f}")
            print(f"      {m.label}")

        if targets.confluence_zone[0] != targets.confluence_zone[1]:
            print(f"\n    🎯 Confluence zone: ${targets.confluence_zone[0]:.2f} – ${targets.confluence_zone[1]:.2f}")
        print(f"    ➜ Suggested target: ${targets.suggested_target:.2f} ({((targets.suggested_target - price) / price) * 100:+.1f}%)  R/R 1:{targets.risk_reward:.1f}")
        print(f"      (using stop ${stop:.2f}, ◆ = in confluence zone)")
        print(f"  {'═' * 60}")

    # ── "What happened next" section for historical mode ────────────────
    if EVAL_DATE is not None:
        print(f"\n  {'═' * 60}")
        print(f"  WHAT HAPPENED NEXT (hindsight)")
        print(f"  {'─' * 60}")
        try:
            t = yf.Ticker(ticker)
            future_start = EVAL_DATE + timedelta(days=1)
            future_end = EVAL_DATE + timedelta(days=30)  # Look 20 trading days ahead
            future_df = t.history(start=future_start, end=future_end, auto_adjust=True)

            if future_df is not None and len(future_df) > 0:
                entry_price = price
                max_price = future_df["High"].max()
                min_price = future_df["Low"].min()
                max_gain = ((max_price - entry_price) / entry_price) * 100
                max_loss = ((min_price - entry_price) / entry_price) * 100

                # Find which day hit max and min
                max_day = future_df["High"].idxmax()
                min_day = future_df["Low"].idxmin()
                max_days_out = (max_day.date() - EVAL_DATE).days
                min_days_out = (min_day.date() - EVAL_DATE).days

                # Price after 1, 3, 5, 10 trading days
                periods = [1, 3, 5, 10]
                print(f"\n  Entry price on {EVAL_DATE}: ${entry_price:.2f}")
                print()
                for p in periods:
                    if len(future_df) >= p:
                        future_price = future_df["Close"].iloc[p - 1]
                        future_change = ((future_price - entry_price) / entry_price) * 100
                        bar = "📈" if future_change > 0 else "📉"
                        future_date = future_df.index[p - 1].strftime('%m/%d')
                        print(f"    {bar} Day {p:>2} ({future_date}): ${future_price:.2f} ({future_change:+.1f}%)")

                print(f"\n    Peak:   ${max_price:.2f} ({max_gain:+.1f}%) — day {max_days_out} after entry")
                print(f"    Trough: ${min_price:.2f} ({max_loss:+.1f}%) — day {min_days_out} after entry")

                # Check if stop or target would have been hit
                stop_hit = pd.DataFrame()
                target_hit = pd.DataFrame()

                if stop > 0:
                    stop_hit = future_df[future_df["Low"] <= stop]
                    if len(stop_hit) > 0:
                        stop_date = stop_hit.index[0]
                        stop_days = (stop_date.date() - EVAL_DATE).days
                        print(f"\n    🔴 Stop-loss (${stop:.2f}) would have been hit on day {stop_days}")

                if targets is not None:
                    target_hit = future_df[future_df["High"] >= targets.suggested_target]
                    if len(target_hit) > 0:
                        target_date = target_hit.index[0]
                        target_days = (target_date.date() - EVAL_DATE).days
                        print(f"    🟢 Target (${targets.suggested_target:.2f}) would have been hit on day {target_days}")

                # Determine outcome
                if len(stop_hit) > 0 and len(target_hit) > 0:
                    if stop_hit.index[0] < target_hit.index[0]:
                        print(f"\n    ➜ OUTCOME: LOSS — stop hit before target")
                    else:
                        print(f"\n    ➜ OUTCOME: WIN — target hit before stop")
                elif len(stop_hit) > 0:
                    print(f"\n    ➜ OUTCOME: LOSS — stop hit, target never reached")
                elif len(target_hit) > 0:
                    print(f"\n    ➜ OUTCOME: WIN — target reached")
                else:
                    final_price = future_df["Close"].iloc[-1]
                    final_pnl = ((final_price - entry_price) / entry_price) * 100
                    print(f"\n    ➜ OUTCOME: OPEN — neither stop nor target hit in 20 days")
                    print(f"       Position after 20 days: ${final_price:.2f} ({final_pnl:+.1f}%)")

            else:
                print(f"\n  No future data available after {EVAL_DATE}")
                print(f"  (date may be too recent or a non-trading day)")

        except Exception as e:
            print(f"\n  Could not fetch future data: {e}")

        print(f"  {'═' * 60}")

    print()


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    global DROP_INCOMPLETE, EVAL_DATE

    parser = argparse.ArgumentParser(description="Swing Trading Scanner")
    parser.add_argument("--tier", type=int, choices=[0, 1, 2, 3],
                        help="Scan specific tier (0=blue chips, 1=mid-caps, 2=penny, 3=ETFs)")
    parser.add_argument("--ticker", type=str, help="Analyze a single ticker in detail")
    parser.add_argument("--date", type=str, default=None,
                        help="Evaluate as of a historical date (YYYY-MM-DD). Use with --ticker to see what the scanner would have shown on that day.")
    parser.add_argument("--custom", type=str, help="Path to file with custom ticker list")
    parser.add_argument("--min-score", type=int, default=70, help="Minimum score to show (default: 70)")
    parser.add_argument("--all", action="store_true", default=False,
                        help="Show all results including lower scores (sets min-score to 40)")
    parser.add_argument("--closed", action="store_true", default=None,
                        help="Force using last fully closed candle (ignore today's incomplete bar)")
    parser.add_argument("--live", action="store_true", default=False,
                        help="Force using today's bar even if market is open")
    parser.add_argument("--backtest", type=int, nargs="?", const=10, default=None,
                        help="Run backtest on N tickers from each tier (default: 10)")
    parser.add_argument("--high-only", action="store_true", default=False,
                        help="Only show HIGH confidence results")
    args = parser.parse_args()

    # --all overrides min-score to 40
    if args.all:
        args.min_score = 40

    # Handle --date: parse and set EVAL_DATE
    if args.date:
        try:
            EVAL_DATE = datetime.strptime(args.date, "%Y-%m-%d").date()
            # Clear caches since we're in historical mode
            _market_regime_cache["regime"] = None
            _market_regime_cache["spy_data"] = None
            _ath_cache.clear()
        except ValueError:
            print(f"\n  ❌ Invalid date format: '{args.date}'. Use YYYY-MM-DD (e.g., 2026-04-28)")
            sys.exit(1)

    # Auto-detect: if market is open and user didn't force --live, drop incomplete bar
    if EVAL_DATE is not None:
        DROP_INCOMPLETE = False  # Historical mode — data is already complete
    elif args.live:
        DROP_INCOMPLETE = False
    elif args.closed:
        DROP_INCOMPLETE = True
    else:
        market_open = is_us_market_open()
        DROP_INCOMPLETE = market_open
        if market_open:
            print("\n  ⏰ US market is currently open — using last closed candle (use --live to override)")
        else:
            print("\n  ✓ US market is closed — using today's completed candle")

    if EVAL_DATE is not None:
        mode = f"historical ({EVAL_DATE.strftime('%Y-%m-%d')})"
    elif DROP_INCOMPLETE:
        mode = "closed candle"
    else:
        mode = "latest candle"

    print("\n" + "═" * 70)
    print("  SWING TRADING SCANNER v2 (strict mode)")
    if EVAL_DATE is not None:
        print(f"  📅 HISTORICAL MODE: evaluating as of {EVAL_DATE.strftime('%A, %B %d, %Y')}")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')} | Min Score: {args.min_score} | Mode: {mode}")
    print("═" * 70)

    # Check and display market regime
    print("\n  Checking market regime (SPY)...", end="", flush=True)
    regime, _ = check_market_regime()
    regime_icon = "🟢" if regime == "BULLISH" else "🔴" if regime == "BEARISH" else "🟡"
    print(f"\r  Market Regime: {regime_icon} {regime}{'  ' * 20}")
    if regime == "BEARISH":
        print("  ⚠️  S&P 500 is below key moving averages — most buy setups will fail.")
        print("  ⚠️  Consider sitting in cash or reducing position sizes.")
    elif regime == "NEUTRAL":
        print("  ⚡ Mixed signals — be selective, only take HIGH confidence setups.")

    # Backtest mode
    if args.backtest is not None:
        n = args.backtest
        print(f"\n  Running backtest on {n} tickers per tier...")
        print(f"  (This may take a few minutes)\n")
        test_tickers = TIER0_BLUECHIPS[:n] + TIER1_MIDCAPS[:n] + TIER2_PENNIES[:min(n, 5)]
        total = len(test_tickers)
        for i, t in enumerate(test_tickers, 1):
            print(f"\r  Backtesting... ({i}/{total})", end="", flush=True)
        results = backtest_setups(test_tickers)
        print(f"\r  Backtest complete.{' ' * 30}")
        print(f"\n  {'═' * 50}")
        print(f"  BACKTEST RESULTS")
        print(f"  {'─' * 50}")
        print(f"  Total setups found:  {results['total']}")
        print(f"  Wins:                {results['wins']} ({results['win_rate']}%)")
        print(f"  Losses:              {results['losses']}")
        print(f"  Avg gain (winners):  {results['avg_gain']:+.2f}%")
        print(f"  Avg loss (losers):   {results['avg_loss']:+.2f}%")
        print(f"  Avg days held:       {results['avg_days_held']:.1f}")
        if results['avg_gain'] and results['avg_loss']:
            expectancy = (results['win_rate']/100 * results['avg_gain'] +
                         (1 - results['win_rate']/100) * results['avg_loss'])
            print(f"  Expectancy per trade: {expectancy:+.2f}%")
        print(f"  {'═' * 50}\n")
        return

    # Single ticker analysis
    if args.ticker:
        print_single_analysis(args.ticker.upper())
        return

    # Custom ticker list
    if args.custom:
        with open(args.custom) as f:
            tickers = [line.strip().upper() for line in f if line.strip()]
        all_results = []
        total = len(tickers)
        for i, t in enumerate(tickers, 1):
            print(f"\r  Scanning {t}... ({i}/{total})", end="", flush=True)
            all_results.extend(scan_ticker(t))
        print(f"\r  Scanned {total} tickers.{' ' * 30}")
        qualified = [r for r in all_results if r.score >= args.min_score]
        if args.high_only:
            qualified = [r for r in qualified if r.confidence == "HIGH"]
        print_results(qualified, "Custom Watchlist")
        return

    # Tier scanning
    tiers = {
        0: ("Tier 0 — Blue Chips & Large-Caps", TIER0_BLUECHIPS),
        1: ("Tier 1 — Mid-Caps ($5–$50)", TIER1_MIDCAPS),
        2: ("Tier 2 — Penny / Small-Caps (<$5)", TIER2_PENNIES),
        3: ("Tier 3 — UCITS ETFs & ETCs", TIER3_ETFS),
    }

    if args.tier is not None:
        scan_tiers = {args.tier: tiers[args.tier]}
    else:
        scan_tiers = tiers

    total_found = 0
    for tier_num, (label, ticker_list) in scan_tiers.items():
        all_results = []
        total = len(ticker_list)
        for i, t in enumerate(ticker_list, 1):
            print(f"\r  Scanning {label}: {t}... ({i}/{total})", end="", flush=True)
            all_results.extend(scan_ticker(t))
        print(f"\r  {label}: scanned {total} tickers.{' ' * 30}")

        qualified = [r for r in all_results if r.score >= args.min_score]
        if args.high_only:
            qualified = [r for r in qualified if r.confidence == "HIGH"]
        total_found += len(qualified)
        print_results(qualified, label)

    # Summary
    print(f"  SUMMARY: {total_found} qualifying setups found")
    print()
    print("  TIPS:")
    print("  • 🟢 HIGH confidence = strongest setups (ADX, weekly, market all aligned)")
    print("  • 🟡 MEDIUM confidence = decent but watch for headwinds")
    print("  • 🔴 LOW confidence = risky, multiple factors misaligned")
    print("  • Use --high-only to see only HIGH confidence results")
    print("  • Use --backtest to see historical win rates")
    print("  • Results with <2% gain or R/R < 1.5 are automatically filtered out")
    print("  • Wait 30 min after open before entering (avoid opening range trap)")
    print()


if __name__ == "__main__":
    main()