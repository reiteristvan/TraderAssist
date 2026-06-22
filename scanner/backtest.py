"""E6 — Backtest engine.

generate_signals() over a historical universe/date range. See CLAUDE.md EPIC E6.
"""
from __future__ import annotations

import dataclasses
import logging
from datetime import date
from typing import Callable, Iterable, Optional

import pandas as pd

from scanner.core import (
    EvalContext,
    QualityInfo,
    WEEKLY_MA_PERIOD,
    _sma_slope,
    _macd_bullish,
)
from scanner.data_store import resample_weekly
from scanner.simulate import Signal

_log = logging.getLogger("scanner.backtest")

_MIN_DAILY_ROWS = 220


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
    full_daily: pd.DataFrame,
    full_market: dict[str, pd.DataFrame],
    quality: QualityInfo,
    earnings_dates: list[date],
    earnings_gate: bool = True,
) -> Optional[EvalContext]:
    """Build EvalContext from pre-loaded frames. Zero disk/network I/O."""
    as_of_ts = pd.Timestamp(as_of)

    daily = full_daily[full_daily.index <= as_of_ts]
    if len(daily) < _MIN_DAILY_ROWS:
        return None

    market = {sym: df[df.index <= as_of_ts] for sym, df in full_market.items()}
    weekly = resample_weekly(daily)
    days = _days_to_earn_from_list(earnings_dates, as_of) if earnings_gate else None

    return EvalContext(
        as_of=as_of,
        market_data=market,
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
    from scanner.regime import compute_confidence, market_regime, ath_zone
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

        # Slice market once per day
        sliced_market = {
            sym: df[df.index <= as_of_ts] for sym, df in full_market.items()
        }
        regime_str: Optional[str] = None

        for ticker, full_daily in bars_by_ticker.items():
            ctx = _make_context_from_frames(
                ticker=ticker,
                as_of=d,
                full_daily=full_daily,
                full_market=sliced_market,
                quality=quality_by_ticker.get(ticker, QualityInfo(False, None, None, None, None)),
                earnings_dates=earnings_by_ticker.get(ticker, []),
                earnings_gate=earnings_gate,
            )
            if ctx is None:
                continue

            daily_sliced = full_daily[full_daily.index <= as_of_ts]

            result = fn(ticker, daily_sliced, ctx)
            if result is None:
                continue

            # Near-miss filter: skip if too many gates failed
            n_failed = len(result.failed_gates)
            if not result.qualified and n_failed > capture_near_misses:
                continue

            # Attach risk (stop, target, atr, rr)
            try:
                result = _targets.attach_risk(result, daily_sliced)
            except Exception:
                pass

            if result.suggested_stop is None or result.suggested_target is None:
                continue

            # Compute confidence
            try:
                if regime_str is None:
                    regime_str = market_regime(sliced_market)
                _, _, zone_label = ath_zone(ticker, result.close, end=d)
                obstacles, _ = count_resistance_obstacles(
                    daily_sliced, result.close,
                    result.suggested_target,
                )
                from scanner.strategies.pullback import PullbackResult
                weekly_aligned = False
                if isinstance(result, PullbackResult):
                    weekly_aligned = result.weekly_above_30ma
                elif ctx.weekly is not None and len(ctx.weekly) >= 35:
                    wma = ctx.weekly["Close"].rolling(WEEKLY_MA_PERIOD).mean()
                    weekly_aligned = bool(ctx.weekly["Close"].iloc[-1] > wma.iloc[-1])
                conf = compute_confidence(
                    score=result.score,
                    adx=result.adx,
                    weekly_aligned=weekly_aligned,
                    market_regime_str=regime_str or "UNKNOWN",
                    obstacles=obstacles,
                    rr=result.risk_reward,
                    sma_slope=_sma_slope(daily_sliced),
                    macd_bullish=_macd_bullish(daily_sliced),
                    ath_zone_label=zone_label,
                )
                result = dataclasses.replace(result, confidence=conf)
            except Exception:
                pass

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
            ))

    print()  # newline after progress counter
    return signals
