"""E7 — Trade simulator (shared by backtest + journal resolve).

simulate_trades(): turns Signals into Trades by walking forward bars against
each signal's stop/target. See CLAUDE.md EPIC E7.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

import pandas as pd

from scanner.targets import apply_min_stop_floor


@dataclass
class Signal:
    """A trade-candidate signal from the backtest signal loop or a live scan."""
    date: date
    ticker: str
    strategy: str       # "pullback" | "breakout"
    score: float
    confidence: Optional[str]
    stop: float
    target: float
    atr: float
    qualified: bool
    failed_gates: list[str] = field(default_factory=list)
    close: float = 0.0  # signal-bar close price
    # Phase 2 — industry momentum (all Optional; None-defaulted so positional callers unaffected)
    industry_group: Optional[str] = None
    industry_momentum: Optional[float] = None
    industry_above_50ma: Optional[bool] = None
    industry_rank_pct: Optional[float] = None
    # Phase 4 — W/L analysis entry-time metrics (all Optional; None = not available)
    rsi_entry: Optional[float] = None
    rvol: Optional[float] = None
    pullback_depth_pct: Optional[float] = None  # None for breakout signals
    pct_to_52w_high: Optional[float] = None


@dataclass
class Trade:
    """Simulated trade outcome produced from a Signal."""
    ticker: str
    signal_date: date
    entry_date: Optional[date]
    entry_px: Optional[float]
    exit_date: Optional[date]
    exit_px: Optional[float]
    # target | stop | time_stop | gap_skip_up | gap_skip_down | incomplete
    exit_reason: str
    r_multiple: Optional[float]
    holding_days: Optional[int]
    score: float
    confidence: Optional[str]
    strategy: str
    qualified: bool
    failed_gates: list[str] = field(default_factory=list)
    flags: dict = field(default_factory=dict)
    target_r: Optional[float] = None    # (target − entry) / (entry − stop)
    target_atr: Optional[float] = None  # (target − entry) / signal ATR
    mae_r: Optional[float] = None       # max adverse excursion ÷ risk (≤ 0)
    mfe_r: Optional[float] = None       # max favorable excursion ÷ risk (≥ 0)
    post_stop_reached_target: Optional[bool] = None  # stop-outs only
    post_stop_mfe_r: Optional[float] = None          # stop-outs only


def simulate_trades(
    signals: list[Signal],
    bars_provider: Callable[[str], Optional[pd.DataFrame]],
    entry: str = "next_open",
    time_stop: int = 10,
) -> list[Trade]:
    """Simulate trade outcomes from a list of Signals.

    bars_provider(ticker) → full OHLCV DataFrame (all bars, unfiltered).

    Entry: open of the first bar strictly after signal.date.

    Entry-gap guards:
    - open >= target  → gap_skip_up  (skipped_gap=True in flags)
    - open <= stop    → gap_skip_down (skipped_gap=True in flags)
    - no next bar     → incomplete

    Exit priority each bar starting from the entry bar:
    1. Low ≤ stop AND High ≥ target → pessimistic stop-out (ambiguous_bar=True)
    2. Low ≤ stop  → stop at stop price (r = −1.0)
    3. High ≥ target → exit at target
    4. bar_idx == time_stop − 1 → exit at close (time_stop)

    Target is taken from the Signal as-is and never recomputed. The stop is
    the Signal's published stop widened at entry (quick-260819-ko0) so that
    entry_px − stop is never less than MIN_STOP_ATR_MULT × ATR — an adverse
    overnight gap can otherwise collapse the risk denominator even when the
    close-side floor (scanner/targets.py, quick-260819-g5h) already made the
    published stop executable at signal time. That widened value is what
    drives stop-hit detection, the stop-out exit price, and every R metric.
    The gap guards below still test against the Signal's published stop; the
    published `signals.stop` DB value is deliberately NOT rewritten.
    """
    trades: list[Trade] = []

    for sig in signals:
        base = dict(
            ticker=sig.ticker,
            signal_date=sig.date,
            score=sig.score,
            confidence=sig.confidence,
            strategy=sig.strategy,
            qualified=sig.qualified,
            failed_gates=list(sig.failed_gates),
        )

        bars = bars_provider(sig.ticker)
        if bars is None or bars.empty:
            trades.append(Trade(
                **base,
                entry_date=None, entry_px=None,
                exit_date=None, exit_px=None,
                exit_reason="incomplete",
                r_multiple=None, holding_days=None,
                flags={"incomplete": True},
            ))
            continue

        # Bars strictly after signal date
        sig_ts = pd.Timestamp(sig.date)
        future = bars[bars.index.normalize() > sig_ts.normalize()]

        if future.empty:
            trades.append(Trade(
                **base,
                entry_date=None, entry_px=None,
                exit_date=None, exit_px=None,
                exit_reason="incomplete",
                r_multiple=None, holding_days=None,
                flags={"incomplete": True},
            ))
            continue

        entry_bar = future.iloc[0]
        entry_px = float(entry_bar["Open"])
        entry_dt = entry_bar.name.date() if hasattr(entry_bar.name, "date") else entry_bar.name

        # Gap-skip guards
        if entry_px >= sig.target:
            trades.append(Trade(
                **base,
                entry_date=entry_dt, entry_px=entry_px,
                exit_date=entry_dt, exit_px=entry_px,
                exit_reason="gap_skip_up",
                r_multiple=None, holding_days=0,
                flags={"skipped_gap": True},
            ))
            continue

        if entry_px <= sig.stop:
            trades.append(Trade(
                **base,
                entry_date=entry_dt, entry_px=entry_px,
                exit_date=entry_dt, exit_px=entry_px,
                exit_reason="gap_skip_down",
                r_multiple=None, holding_days=0,
                flags={"skipped_gap": True},
            ))
            continue

        # quick-260819-ko0 (approved 2026-08-19): widen the stop at entry so
        # entry_px - stop never collapses below MIN_STOP_ATR_MULT x ATR on an
        # adverse overnight gap. Entry-side companion to the close-side floor
        # in scanner/targets.py (quick-260819-g5h). Must be computed AFTER
        # the gap_skip_down guard above (which stays on sig.stop) so a
        # widened stop can never rescue a gap-skipped trade.
        effective_stop = apply_min_stop_floor(sig.stop, entry_px, sig.atr)

        risk = entry_px - effective_stop  # always > 0 after gap guards
        target_dist = sig.target - entry_px
        target_r_val = target_dist / risk
        target_atr_val = (target_dist / sig.atr) if sig.atr and sig.atr > 0 else None

        # Walk forward bars; bar_idx 0 = entry bar (session 1 of holding)
        exit_date = None
        exit_px_val = None
        exit_reason = None
        flags: dict = {}

        # MAE/MFE: running worst/best price from entry (updated each bar)
        min_low = entry_px
        max_high = entry_px
        post_stop_reached_target_val: Optional[bool] = None
        post_stop_mfe_r_val: Optional[float] = None

        n_bars = len(future)
        for bar_idx in range(n_bars):
            bar = future.iloc[bar_idx]
            low = float(bar["Low"])
            high = float(bar["High"])
            close = float(bar["Close"])
            bar_dt = bar.name.date() if hasattr(bar.name, "date") else bar.name

            min_low = min(min_low, low)
            max_high = max(max_high, high)

            stop_hit = low <= effective_stop
            target_hit = high >= sig.target

            if stop_hit:
                exit_date = bar_dt
                exit_px_val = effective_stop
                exit_reason = "stop"
                if target_hit:
                    flags["ambiguous_bar"] = True
                # Shadow post-stop: bars remaining in the time-stop window
                remaining = future.iloc[bar_idx + 1:time_stop]
                if not remaining.empty:
                    max_post_high = float(remaining["High"].max())
                    post_stop_reached_target_val = max_post_high >= sig.target
                    post_stop_mfe_r_val = (max_post_high - entry_px) / risk
                else:
                    post_stop_reached_target_val = False
                    post_stop_mfe_r_val = 0.0
                break
            elif target_hit:
                exit_date = bar_dt
                exit_px_val = sig.target
                exit_reason = "target"
                break
            elif bar_idx == time_stop - 1:
                exit_date = bar_dt
                exit_px_val = close
                exit_reason = "time_stop"
                break

        if exit_reason is None:
            # Ran out of bars before reaching time_stop — exit at last available close
            last_bar = future.iloc[-1]
            exit_date = last_bar.name.date() if hasattr(last_bar.name, "date") else last_bar.name
            exit_px_val = float(last_bar["Close"])
            exit_reason = "time_stop"

        mae_r_val = (min_low - entry_px) / risk
        mfe_r_val = (max_high - entry_px) / risk
        r_multiple = (exit_px_val - entry_px) / risk
        holding_days = (pd.Timestamp(exit_date) - pd.Timestamp(entry_dt)).days

        trades.append(Trade(
            **base,
            entry_date=entry_dt, entry_px=entry_px,
            exit_date=exit_date, exit_px=exit_px_val,
            exit_reason=exit_reason,
            r_multiple=r_multiple,
            holding_days=holding_days,
            flags=flags,
            target_r=target_r_val,
            target_atr=target_atr_val,
            mae_r=mae_r_val,
            mfe_r=mfe_r_val,
            post_stop_reached_target=post_stop_reached_target_val,
            post_stop_mfe_r=post_stop_mfe_r_val,
        ))

    return trades
