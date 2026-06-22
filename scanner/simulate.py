"""E7 — Trade simulator (shared by backtest + journal resolve).

simulate_trades(): turns Signals into Trades by walking forward bars against
each signal's stop/target. See CLAUDE.md EPIC E7.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

import pandas as pd


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

    Stops and targets come from the Signal; never recomputed here.
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

        risk = entry_px - sig.stop  # always > 0 after gap guards

        # Walk forward bars; bar_idx 0 = entry bar (session 1 of holding)
        exit_date = None
        exit_px_val = None
        exit_reason = None
        flags: dict = {}

        n_bars = len(future)
        for bar_idx in range(n_bars):
            bar = future.iloc[bar_idx]
            low = float(bar["Low"])
            high = float(bar["High"])
            close = float(bar["Close"])
            bar_dt = bar.name.date() if hasattr(bar.name, "date") else bar.name

            stop_hit = low <= sig.stop
            target_hit = high >= sig.target

            if stop_hit and target_hit:
                exit_date = bar_dt
                exit_px_val = sig.stop
                exit_reason = "stop"
                flags["ambiguous_bar"] = True
                break
            elif stop_hit:
                exit_date = bar_dt
                exit_px_val = sig.stop
                exit_reason = "stop"
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
        ))

    return trades
