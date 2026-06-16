"""Shared pytest fixtures: synthetic OHLCV factories (E0.2).

These are plain callable factory functions (not pytest fixture-injected
objects) per CLAUDE.md's calling convention: call them directly with
parens/args, e.g. ``make_pullback_setup()``, ``make_quality()``.

All series are generated from seeded ``numpy.random.default_rng`` calls so
every factory is fully deterministic between runs.
"""
import numpy as np
import pandas as pd

import pullback_filter as pf
import breakout_filter as bf


def bdate_index(n, end="2026-06-15"):
    """Business-day DatetimeIndex of length n ending on `end`."""
    return pd.bdate_range(end=pd.Timestamp(end), periods=n)


def ohlcv_from_close(closes, volumes, seed=0, noise=0.0015):
    """Build a full OHLCV frame around a given Close series.

    Open/High/Low are derived from Close with small seeded noise so the
    bars look like real candles without disturbing the Close-based gate
    logic the evaluators key off of.
    """
    rng = np.random.default_rng(seed)
    n = len(closes)
    closes = np.asarray(closes, dtype=float)
    opens = np.empty(n)
    opens[0] = closes[0] * (1 - noise)
    opens[1:] = closes[:-1] * (1 + rng.normal(0, noise * 0.3, n - 1))
    highs = np.maximum(opens, closes) * (1 + np.abs(rng.normal(noise, noise * 0.4, n)))
    lows = np.minimum(opens, closes) * (1 - np.abs(rng.normal(noise, noise * 0.4, n)))
    idx = bdate_index(n)
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=idx,
    )


def make_pullback_setup(r1=0.0035, n_base=270, pullback_days=10, depth=0.05, seed=1,
                        amp=0.008, period=5.0, phase=np.pi):
    """Synthetic pullback setup: a clean advance followed by a controlled
    pullback that lands within support tolerance and keeps RSI/ADX in
    qualifying range.

    The pullback leg is generated in log-return space with a small
    sinusoidal oscillation added on top of the average daily log-return,
    then mean-corrected back to the average. This creates day-to-day
    up/down variety (needed so RSI doesn't bottom out from Wilder-smoothing
    a perfectly monotonic decline) while still hitting the exact target
    cumulative `depth` and never pushing the price back above the original
    swing high.
    """
    n = n_base + pullback_days
    p0 = 20.0
    base = p0 * (1 + r1) ** np.arange(n_base)
    peak = base[-1]
    avg_log_ret = np.log(1 - depth) / pullback_days
    days = np.arange(1, pullback_days + 1)
    osc = amp * np.sin(2 * np.pi * days / period + phase)
    log_returns = avg_log_ret + osc
    log_returns = log_returns - log_returns.mean() + avg_log_ret
    decline = peak * np.exp(np.cumsum(log_returns))
    closes = np.concatenate([base, decline])
    vol_adv = 2_000_000 + np.linspace(0, 200_000, n_base)
    vol_pb = 1_100_000 - np.linspace(0, 100_000, pullback_days)
    volumes = np.concatenate([vol_adv, vol_pb])
    return ohlcv_from_close(closes, volumes, seed=seed)


def make_breakout_setup(r_base=0.0035, n_pre=230, n_consol=40, consol_drift=-0.0002,
                        consol_noise_amp=0.0015, breakout_jump=0.006, vol_base=1_500_000,
                        vol_breakout_mult=2.5, seed=3, pre_noise_sigma=0.004):
    """Synthetic breakout setup: long pre-trend, tightening consolidation,
    and a final breakout-day jump above the consolidation high.

    Small seeded Gaussian noise (mean-corrected) is added to the pre-trend
    Close values. Without it, a perfectly smooth monotonic pre-trend drives
    Wilder's EMA-based RSI average-loss toward zero, a "memory pathology"
    that keeps RSI pinned near 100 for many days into the consolidation
    regardless of the breakout-day jump size.
    """
    rng = np.random.default_rng(seed + 100)
    pre_trend = 20.0 * (1 + r_base) ** np.arange(n_pre)
    pre_noise = rng.normal(0, pre_noise_sigma, n_pre)
    pre_noise -= pre_noise.mean()
    pre = pre_trend * (1 + pre_noise)
    peak_pre = pre[-1]
    cdays = np.arange(1, n_consol + 1)
    consol_drift_path = peak_pre * (1 + consol_drift) ** cdays
    tightening = np.linspace(1.0, 0.1, n_consol)
    osc = consol_noise_amp * tightening * np.sin(cdays * 2 * np.pi / 6)
    consol_closes = consol_drift_path * (1 + osc)
    consol_closes[-1] = consol_closes[-2] * (1 + breakout_jump)
    closes = np.concatenate([pre, consol_closes])
    volumes = np.concatenate([
        np.full(n_pre, float(vol_base)),
        np.full(n_consol, vol_base * 0.6),
    ])
    volumes[-1] = vol_base * vol_breakout_mult
    return ohlcv_from_close(closes, volumes, seed=seed)


def make_downtrend(n=280, r=-0.003, seed=5):
    """Steady downtrend: should fail both pullback and breakout gates."""
    closes = 50.0 * (1 + r) ** np.arange(n)
    volumes = np.full(n, 1_500_000.0)
    return ohlcv_from_close(closes, volumes, seed=seed)


def make_choppy(n=280, amp=0.03, seed=6):
    """Directionless noisy random walk: should fail both pullback and
    breakout gates (no clean trend/consolidation structure)."""
    rng = np.random.default_rng(seed)
    log_rets = rng.normal(0, amp, n)
    closes = 50.0 * np.exp(np.cumsum(log_rets))
    volumes = np.full(n, 1_500_000.0)
    return ohlcv_from_close(closes, volumes, seed=seed)


def make_market_data(seed=2):
    """Sector/SPY benchmark frames for pullback's relative-strength gates.

    Only XLK (Technology) is distinct from SPY since the default
    `make_quality()` sector is Technology and that's the only sector ETF
    gate-relevant to the default fixtures; all other sector ETFs share the
    SPY-shaped frame.
    """
    idx_n = 280
    spy = 400 * (1 + 0.0008) ** np.arange(idx_n)
    xlk = 180 * (1 + 0.0010) ** np.arange(idx_n)
    spy_df = ohlcv_from_close(spy, np.full(idx_n, 5_000_000), seed=seed)
    xlk_df = ohlcv_from_close(xlk, np.full(idx_n, 3_000_000), seed=seed + 1)
    data = {"SPY": spy_df}
    for etf in pf.SECTOR_ETF_MAP.values():
        data[etf] = xlk_df if etf == "XLK" else spy_df
    return data


def make_quality(**overrides):
    """Quality/fundamentals dict that clears both strategies' default
    profitability, market-cap, debt/equity, and sector gates."""
    base = dict(profitable=True, market_cap=2.5e9, debt_equity=50.0, sector="Technology", float_shares=50e6)
    base.update(overrides)
    return base


def patch_pullback_external(monkeypatch):
    """Stub out pullback_filter's network-backed earnings/weekly-trend
    lookups so `_evaluate` can run fully offline against synthetic data."""
    monkeypatch.setattr(pf, "_earnings_proximity", lambda t: 30)
    monkeypatch.setattr(
        pf, "_weekly_trend",
        lambda t: {"weekly_above_30ma": True, "weekly_30ma_rising": True},
    )
