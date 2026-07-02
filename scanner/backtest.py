"""E6 — Backtest engine.

generate_signals() over a historical universe/date range. See CLAUDE.md EPIC E6.
"""
from __future__ import annotations

import dataclasses
import logging
import warnings
from datetime import date
from typing import Callable, Iterable, Optional

import pandas as pd

from scanner.core import (
    EvalContext,
    QualityInfo,
    RS_LOOKBACK,
    WEEKLY_MA_PERIOD,
    _sma_slope,
    _macd_bullish,
    _industry_strength,
    _attach_industry_rank_pct,
)
from scanner.data_store import resample_weekly
from scanner.simulate import Signal

_log = logging.getLogger("scanner.backtest")

_MIN_DAILY_ROWS = 220

# BB width percentile — must match breakout strategy constant
_BB_WIDTH_PCTILE = 0.40


# ── Pre-computed indicator cache (one instance per ticker, reused across all dates) ──

@dataclasses.dataclass
class PrecomputedBars:
    """Rolling indicator Series pre-computed over the full ticker history.

    Use .asof(ts) for O(log n) point-in-time lookups in the backtest inner loop.
    """
    sma20:            pd.Series  # SMA(20) of Close
    sma50:            pd.Series  # SMA(50) of Close
    sma50_prev:       pd.Series  # SMA(50).shift(20) — for "SMA50 rising" gate
    sma200:           pd.Series  # SMA(200) of Close
    high_52w:         pd.Series  # High.rolling(252, min_periods=200).max()
    vol_sma50:        pd.Series  # Volume.rolling(50).mean()
    dollar_vol_sma50: pd.Series  # (Close × Volume).rolling(50).mean()
    rsi14:            pd.Series  # RSI(14)
    adx14:            pd.Series  # ADX(14)
    bb_width:         pd.Series  # Bollinger Band width series
    bb_threshold:     pd.Series  # bb_width.rolling(60).quantile(BB_WIDTH_PCTILE)
    rs_strength:      pd.Series  # Rolling RS ratio vs SPY (60-day)
    rs_at_new_high:   pd.Series  # bool series — RS line at 60d high
    sma_slope:        pd.Series  # SMA(50) slope % over 5 bars (for confidence)
    macd_bullish:     pd.Series  # bool series — MACD hist > 0 (for confidence)


def _precompute_bars(
    full_daily: pd.DataFrame,
    spy_full: Optional[pd.DataFrame],
) -> PrecomputedBars:
    """Compute all rolling indicator Series once over the full ticker history."""
    from ta.momentum import RSIIndicator
    from ta.trend import ADXIndicator, MACD, SMAIndicator
    from ta.volatility import BollingerBands

    warnings.filterwarnings("ignore", category=FutureWarning)
    warnings.filterwarnings("ignore", category=UserWarning)

    close  = full_daily["Close"]
    high   = full_daily["High"]
    low    = full_daily["Low"]
    volume = full_daily["Volume"]

    sma20  = SMAIndicator(close, 20).sma_indicator()
    sma50  = SMAIndicator(close, 50).sma_indicator()
    sma200 = SMAIndicator(close, 200).sma_indicator()

    high_52w         = high.rolling(252, min_periods=200).max()
    vol_sma50        = volume.rolling(50).mean()
    dollar_vol_sma50 = (close * volume).rolling(50).mean()

    rsi14 = RSIIndicator(close, 14).rsi()
    adx14 = ADXIndicator(high, low, close, 14).adx()

    bb = BollingerBands(close, 20, 2)
    bb_width = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()
    bb_threshold = bb_width.rolling(60).quantile(_BB_WIDTH_PCTILE)

    # RS vs SPY — align on shared index, then reindex back to ticker's index
    if spy_full is not None and len(spy_full) >= RS_LOOKBACK:
        aligned = pd.DataFrame(
            {"stock": close, "spy": spy_full["Close"]}
        ).dropna()
        rs_line       = aligned["stock"] / aligned["spy"]
        rs_strength_a = rs_line / rs_line.shift(RS_LOOKBACK)
        rs_at_high_a  = rs_line >= rs_line.rolling(RS_LOOKBACK).max() * 0.99
        rs_strength   = rs_strength_a.reindex(close.index)
        rs_at_new_high = rs_at_high_a.reindex(close.index).fillna(False)
    else:
        rs_strength    = pd.Series(1.0,  index=close.index, dtype=float)
        rs_at_new_high = pd.Series(False, index=close.index, dtype=bool)

    # SMA slope (% change over 5 bars) — mirrors _sma_slope() in core.py
    sma_slope = ((sma50 - sma50.shift(5)) / sma50.shift(5) * 100).fillna(0.0)

    # MACD bullish — histogram > 0
    macd_obj      = MACD(close, window_slow=26, window_fast=12, window_sign=9)
    macd_bullish  = (macd_obj.macd_diff() > 0).fillna(False)

    return PrecomputedBars(
        sma20            = sma20,
        sma50            = sma50,
        sma50_prev       = sma50.shift(20),
        sma200           = sma200,
        high_52w         = high_52w,
        vol_sma50        = vol_sma50,
        dollar_vol_sma50 = dollar_vol_sma50,
        rsi14            = rsi14,
        adx14            = adx14,
        bb_width         = bb_width,
        bb_threshold     = bb_threshold,
        rs_strength      = rs_strength,
        rs_at_new_high   = rs_at_new_high,
        sma_slope        = sma_slope,
        macd_bullish     = macd_bullish,
    )


# ── Internal context builder (no disk I/O inside the loop) ────────────────────

def _days_to_earn_from_list(dates: list[date], as_of: date) -> Optional[int]:
    """Days to next earnings from pre-loaded date list (no disk read)."""
    if not dates:
        return None
    latest = max(dates)
    as_of_ts = pd.Timestamp(as_of)
    if (as_of_ts - pd.Timestamp(latest)).days > 90:
        return None
    future = [d for d in dates if d > as_of]
    if not future:
        return None
    return int((pd.Timestamp(min(future)) - as_of_ts).days)


def _make_context_from_frames(
    ticker: str,
    as_of: date,
    daily_sliced: pd.DataFrame,
    market_sliced: dict[str, pd.DataFrame],
    quality: QualityInfo,
    earnings_dates: list[date],
    weekly_sliced: Optional[pd.DataFrame] = None,
    earnings_gate: bool = True,
) -> Optional[EvalContext]:
    """Build EvalContext from pre-sliced frames. Zero disk/network/resample I/O.

    All DataFrames must already be sliced to as_of by the caller — this
    function does no filtering, which is intentional: slicing happens once
    in the outer loop rather than once per ticker×day.
    """
    if len(daily_sliced) < _MIN_DAILY_ROWS:
        return None

    weekly = weekly_sliced if weekly_sliced is not None else resample_weekly(daily_sliced)
    days = _days_to_earn_from_list(earnings_dates, as_of) if earnings_gate else None

    return EvalContext(
        as_of=as_of,
        market_data=market_sliced,
        weekly=weekly,
        quality=quality,
        days_to_earnings=days,
    )


# ── Signal generation loop ─────────────────────────────────────────────────────

def generate_signals(
    universe: list[str],
    start: date,
    end: date,
    strategy: str,
    capture_near_misses: int = 1,
    earnings_gate: bool = True,
    _bars_loader: Optional[Callable[[str], Optional[pd.DataFrame]]] = None,
    _market_loader: Optional[Callable[[], dict[str, pd.DataFrame]]] = None,
    _quality_loader: Optional[Callable[[str], QualityInfo]] = None,
    _earnings_loader: Optional[Callable[[str], list[date]]] = None,
) -> list[Signal]:
    """Generate trade-candidate Signals over a historical date range.

    Parameters
    ----------
    universe:
        List of ticker symbols to scan.
    start, end:
        Inclusive date range for signal generation.
    strategy:
        "pullback" or "breakout".
    capture_near_misses:
        Include results that fail at most this many gates (qualified=False).
        Set to 0 for qualified-only, 1 for one-gate near-misses (default).
    earnings_gate:
        When False, days_to_earnings=None is passed to every context
        (equivalent to --earnings-gate off in the backtest CLI).
    _bars_loader, _market_loader, _quality_loader, _earnings_loader:
        Test seams. Default to the real data-store functions.
        The loaders are called ONCE before the loop — never inside it.
    """
    import scanner.strategies.pullback as pb
    import scanner.strategies.breakout as br
    import scanner.targets as _targets
    from scanner.regime import compute_confidence, market_regime, _ath_zone_label
    from scanner.targets import count_resistance_obstacles

    # ── resolve loaders ────────────────────────────────────────────────────────
    if _bars_loader is None:
        from scanner.data_store import get_history
        _bars_loader = lambda t: get_history(t)  # noqa: E731

    if _market_loader is None:
        from scanner.data_store import get_market_data
        _market_loader = get_market_data  # noqa: E731

    if _quality_loader is None:
        from scanner.core import _make_quality_info
        _quality_loader = _make_quality_info  # noqa: E731

    if _earnings_loader is None:
        from scanner.earnings_store import get_earnings_dates
        _earnings_loader = get_earnings_dates  # noqa: E731

    # ── strategy function ──────────────────────────────────────────────────────
    if strategy == "pullback":
        fn = pb.evaluate
    elif strategy == "breakout":
        fn = br.evaluate
    else:
        raise ValueError(f"Unknown strategy: {strategy!r}")

    # ── pre-load everything OUTSIDE the loop (no per-date disk reads inside) ──
    print(f"Loading {len(universe)} tickers...")
    bars_by_ticker: dict[str, pd.DataFrame] = {}
    for ticker in universe:
        df = _bars_loader(ticker)
        if df is not None:
            bars_by_ticker[ticker] = df

    if not bars_by_ticker:
        _log.warning("generate_signals: no bars loaded for any ticker")
        return []

    full_market = _market_loader()

    quality_by_ticker: dict[str, QualityInfo] = {}
    for ticker in bars_by_ticker:
        q = _quality_loader(ticker)
        if not isinstance(q, QualityInfo):
            q = QualityInfo(
                profitable=bool(q.get("profitable", False)) if isinstance(q, dict) else False,
                market_cap=q.get("market_cap") if isinstance(q, dict) else None,
                debt_equity=q.get("debt_equity") if isinstance(q, dict) else None,
                sector=q.get("sector") if isinstance(q, dict) else None,
                float_shares=q.get("float_shares") if isinstance(q, dict) else None,
            )
        quality_by_ticker[ticker] = q

    earnings_by_ticker: dict[str, list[date]] = {}
    for ticker in bars_by_ticker:
        earnings_by_ticker[ticker] = _earnings_loader(ticker)

    # ── pre-compute per-ticker derived series ──────────────────────────────────
    # Phase 1: weekly bars (eliminates resample_weekly() inside the loop)
    # Phase 2: ATH expanding max (eliminates parquet reads inside the loop)
    # Phase 3: rolling indicators (SMA/RSI/ADX/BB/RS — eliminates O(n) recomputation
    #          every iteration; replaced by O(log n) .asof() binary search)
    spy_full = full_market.get("SPY")
    print(f"Pre-computing weekly bars, ATH series, and rolling indicators "
          f"for {len(bars_by_ticker)} ticker(s)...")

    weekly_by_ticker:  dict[str, pd.DataFrame]    = {}
    ath_series_by_ticker: dict[str, pd.Series]    = {}
    precomp_by_ticker: dict[str, PrecomputedBars] = {}

    for ticker, full_daily in bars_by_ticker.items():
        w = resample_weekly(full_daily)
        if w is not None:
            weekly_by_ticker[ticker] = w
        ath_series_by_ticker[ticker] = full_daily["High"].expanding().max()
        precomp_by_ticker[ticker] = _precompute_bars(full_daily, spy_full)

    # ── derive trading days from SPY (or first available ticker) ──────────────
    spy_bars = bars_by_ticker.get("SPY") or next(iter(bars_by_ticker.values()))
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    trading_days = [
        ts.date() for ts in spy_bars.index
        if start_ts <= ts <= end_ts
    ]

    if not trading_days:
        return []

    n_days = len(trading_days)
    signals: list[Signal] = []

    for day_num, d in enumerate(trading_days):
        print(f"[{day_num + 1}/{n_days}] {d}", end="\r")
        as_of_ts = pd.Timestamp(d)

        # Slice market once per day — all ETF reads below use sliced_market only (IND-06)
        sliced_market = {
            sym: df[df.index <= as_of_ts] for sym, df in full_market.items()
        }
        regime_str: Optional[str] = None

        # Per-day ETF momentum dict for rank percentile (IND-04).
        # Computed BEFORE the ticker sub-loop so rank covers all tickers on this day.
        day_etf_scores: dict = {}
        day_ind_cache: dict = {}  # ticker -> _industry_strength result for reuse
        for _ticker in bars_by_ticker:
            _q = quality_by_ticker.get(_ticker)
            if _q is None:
                continue
            _ind_key = getattr(_q, "industry_key", None)
            _ind_sec = getattr(_q, "sector", None)
            _st = _industry_strength(_ind_key, _ind_sec, sliced_market)
            day_ind_cache[_ticker] = _st
            _etf = _st.get("industry_etf")
            _mom = _st.get("industry_mom_20d")
            if _etf is not None and _mom is not None and _etf not in day_etf_scores:
                day_etf_scores[_etf] = _mom
        day_rank = pd.Series(day_etf_scores).rank(pct=True) if len(day_etf_scores) >= 2 else pd.Series(dtype=float)

        for ticker, full_daily in bars_by_ticker.items():
            # Slice daily once per ticker×day; reuse for both ctx and fn()
            daily_sliced = full_daily[full_daily.index <= as_of_ts]

            # Slice pre-computed weekly (O(n_weekly) filter vs full daily resample)
            full_weekly = weekly_by_ticker.get(ticker)
            weekly_sliced: Optional[pd.DataFrame] = None
            if full_weekly is not None:
                w = full_weekly[full_weekly.index <= as_of_ts]
                weekly_sliced = w if not w.empty else None

            ctx = _make_context_from_frames(
                ticker=ticker,
                as_of=d,
                daily_sliced=daily_sliced,
                market_sliced=sliced_market,
                quality=quality_by_ticker.get(ticker, QualityInfo(False, None, None, None, None)),
                earnings_dates=earnings_by_ticker.get(ticker, []),
                weekly_sliced=weekly_sliced,
                earnings_gate=earnings_gate,
            )
            if ctx is None:
                continue

            precomp_t = precomp_by_ticker.get(ticker)
            result = fn(ticker, daily_sliced, ctx, precomp=precomp_t)
            if result is None:
                continue

            # Near-miss filter: skip if too many gates failed
            n_failed = len(result.failed_gates)
            if not result.qualified and n_failed > capture_near_misses:
                continue

            # Attach risk (stop, target, atr, rr)
            try:
                result = _targets.attach_risk(result, daily_sliced)
            except (ValueError, AttributeError, KeyError, IndexError):
                pass

            if result.suggested_stop is None or result.suggested_target is None:
                continue

            # Compute confidence — ATH from pre-computed series (no parquet read)
            try:
                if regime_str is None:
                    regime_str = market_regime(sliced_market)
                ath_s = ath_series_by_ticker.get(ticker)
                raw_ath = ath_s.asof(as_of_ts) if ath_s is not None else None
                ath_val = float(raw_ath) if raw_ath is not None and not pd.isna(raw_ath) else None
                _, _, zone_label = _ath_zone_label(result.close, ath_val)
                obstacles, _ = count_resistance_obstacles(
                    daily_sliced, result.close,
                    result.suggested_target,
                )
                from scanner.strategies.pullback import PullbackResult
                from scanner.strategies.breakout import BreakoutResult
                weekly_aligned = False
                if isinstance(result, PullbackResult):
                    weekly_aligned = result.weekly_above_30ma
                elif ctx.weekly is not None and len(ctx.weekly) >= 35:
                    wma = ctx.weekly["Close"].rolling(WEEKLY_MA_PERIOD).mean()
                    weekly_aligned = bool(ctx.weekly["Close"].iloc[-1] > wma.iloc[-1])

                # Use pre-computed slope/MACD when available (avoids recomputing on sliced df)
                if precomp_t is not None:
                    slope_val   = float(precomp_t.sma_slope.asof(as_of_ts))
                    _macd_raw   = precomp_t.macd_bullish.asof(as_of_ts)
                    macd_val    = bool(_macd_raw) if not pd.isna(_macd_raw) else False
                else:
                    slope_val   = _sma_slope(daily_sliced)
                    macd_val    = _macd_bullish(daily_sliced)

                conf = compute_confidence(
                    score=result.score,
                    adx=result.adx,
                    weekly_aligned=weekly_aligned,
                    market_regime_str=regime_str or "UNKNOWN",
                    obstacles=obstacles,
                    rr=result.risk_reward,
                    sma_slope=slope_val,
                    macd_bullish=macd_val,
                    ath_zone_label=zone_label,
                )
                result = dataclasses.replace(result, confidence=conf)
            except (ValueError, AttributeError, KeyError, IndexError):
                pass

            # Industry momentum — reuse per-day cached strength (sliced_market only)
            _strength = day_ind_cache.get(ticker) or {"industry_etf": None, "industry_mom_20d": None, "industry_above_50ma": None}
            _etf = _strength.get("industry_etf")
            _rank_pct: Optional[float] = None
            if _etf is not None and _etf in day_rank.index:
                _rv = day_rank[_etf]
                _rank_pct = float(_rv) if not pd.isna(_rv) else None
            _q_sig = quality_by_ticker.get(ticker)
            # Phase 4 — W/L entry-time metric extraction (strategy-polymorphic via getattr)
            _is_breakout_result = isinstance(result, BreakoutResult)
            _rsi = getattr(result, 'rsi', None)
            _rvol = getattr(result, 'vol_ratio', None)   # BreakoutResult only
            if _rvol is None and precomp_t is not None:
                # Pullback: compute RVOL from precomp vol_sma50 series
                _vol_sma50 = float(precomp_t.vol_sma50.asof(as_of_ts))
                _cur_vol = float(daily_sliced['Volume'].iloc[-1])
                if _vol_sma50 > 0 and not pd.isna(_vol_sma50) and not pd.isna(_cur_vol):
                    _rvol = _cur_vol / _vol_sma50
            _pullback_depth = getattr(result, 'pullback_depth_pct', None)   # PullbackResult only
            # pct_to_52w_high: standardize to "% distance below 52w high" (positive = farther below)
            _pct_high: Optional[float] = None
            if _is_breakout_result:
                # Breakout: convert native ratio format (close/high*100) to distance format
                _raw = getattr(result, 'pct_to_52w_high', None)
                if _raw is not None:
                    _pct_high = 100.0 - _raw
            elif precomp_t is not None:
                # Pullback: pct below 52w high = (high_52w - close) / high_52w * 100
                _h52 = precomp_t.high_52w.asof(as_of_ts)
                if not pd.isna(_h52) and float(_h52) > 0:
                    _pct_high = (float(_h52) - result.close) / float(_h52) * 100
            signals.append(Signal(
                date=d,
                ticker=ticker,
                strategy=strategy,
                score=result.score,
                confidence=result.confidence,
                stop=result.suggested_stop,
                target=result.suggested_target,
                atr=result.atr or 0.0,
                qualified=result.qualified,
                failed_gates=list(result.failed_gates),
                close=result.close,
                industry_group=getattr(_q_sig, "industry", None),
                industry_momentum=_strength.get("industry_mom_20d"),
                industry_above_50ma=_strength.get("industry_above_50ma"),
                industry_rank_pct=_rank_pct,
                rsi_entry=_rsi,
                rvol=_rvol,
                pullback_depth_pct=_pullback_depth,
                pct_to_52w_high=_pct_high,
            ))

    print()  # newline after progress counter
    return signals
