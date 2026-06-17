"""Unit tests for E2.2 semantic changes (a-d) in pullback.evaluate,
   E3.3 earnings gate in breakout.evaluate, and E3.2 run_scan.
"""
import numpy as np
import pandas as pd
import pytest
from datetime import date

from scanner.core import QualityInfo, EvalContext
from scanner.strategies.pullback import evaluate as pb_eval
from scanner.strategies.breakout import evaluate as br_eval
from scanner.core import run_scan

# ── helpers ──────────────────────────────────────────────────────────────────

def _make_pb_df():
    from tests.conftest import make_pullback_setup
    return make_pullback_setup()


def _make_br_df():
    from tests.conftest import make_breakout_setup
    return make_breakout_setup()


def _make_market_data():
    from tests.conftest import make_market_data
    return make_market_data()


def _quality(**overrides) -> QualityInfo:
    defaults = dict(profitable=True, market_cap=2.5e9, debt_equity=50.0,
                    sector="Technology", float_shares=50e6)
    defaults.update(overrides)
    return QualityInfo(**defaults)


def _make_weekly(df):
    weekly = df.resample("W-FRI").agg(
        Open=("Open", "first"), High=("High", "max"),
        Low=("Low", "min"), Close=("Close", "last"),
        Volume=("Volume", "sum"),
    ).dropna(subset=["Close"])
    if len(weekly) > 0 and weekly.index[-1] > df.index[-1]:
        weekly = weekly.iloc[:-1]
    return weekly


_AUTO = object()  # sentinel for "compute weekly from df"


def _pb_ctx(df, quality=None, weekly=_AUTO, days_to_earnings=30, market_data=None):
    if quality is None:
        quality = _quality()
    if market_data is None:
        market_data = _make_market_data()
    if weekly is _AUTO:
        weekly = _make_weekly(df)
    return EvalContext(
        as_of=df.index[-1].date(),
        market_data=market_data,
        weekly=weekly,
        quality=quality,
        days_to_earnings=days_to_earnings,
    )


def _br_ctx(df, quality=None, days_to_earnings=30):
    if quality is None:
        quality = _quality()
    return EvalContext(
        as_of=df.index[-1].date(),
        market_data={},
        weekly=None,
        quality=quality,
        days_to_earnings=days_to_earnings,
    )


# ── E2.2a: earnings skip (pullback) ──────────────────────────────────────────

def test_pullback_earnings_unknown_skips():
    df = _make_pb_df()
    ctx = _pb_ctx(df, days_to_earnings=None)
    res = pb_eval("SYN", df, ctx)
    assert "Earnings clear" in res.skipped_gates
    assert "Earnings clear" not in res.failed_gates


def test_pullback_earnings_known_within_buffer_fails():
    df = _make_pb_df()
    ctx = _pb_ctx(df, days_to_earnings=3)
    res = pb_eval("SYN", df, ctx)
    assert "Earnings clear" in res.failed_gates
    assert "Earnings clear" not in res.skipped_gates


def test_pullback_earnings_known_beyond_buffer_passes():
    df = _make_pb_df()
    ctx = _pb_ctx(df, days_to_earnings=10)
    res = pb_eval("SYN", df, ctx)
    assert "Earnings clear" not in res.failed_gates
    assert "Earnings clear" not in res.skipped_gates


# ── E2.2b: sector skip (pullback) ────────────────────────────────────────────

def test_pullback_sector_unknown_skips():
    df = _make_pb_df()
    quality = _quality(sector=None)
    ctx = _pb_ctx(df, quality=quality)
    res = pb_eval("SYN", df, ctx)
    sector_skipped = any("Sector" in s for s in res.skipped_gates)
    assert sector_skipped, f"Expected Sector gate skipped; got: {res.skipped_gates}"


def test_pullback_sector_missing_etf_skips():
    df = _make_pb_df()
    quality = _quality(sector="Technology")
    spy_only = {"SPY": _make_market_data()["SPY"]}
    ctx = _pb_ctx(df, quality=quality, market_data=spy_only)
    res = pb_eval("SYN", df, ctx)
    sector_skipped = any("Sector" in s for s in res.skipped_gates)
    assert sector_skipped, f"Expected Sector gate skipped (no ETF); got: {res.skipped_gates}"


# ── E2.2c: weekly skip (pullback) ────────────────────────────────────────────

def test_pullback_weekly_none_skips():
    df = _make_pb_df()
    ctx = _pb_ctx(df, weekly=None)
    res = pb_eval("SYN", df, ctx)
    assert "Weekly above 30-MA" in res.skipped_gates


def test_pullback_weekly_short_skips():
    df = _make_pb_df()
    short_weekly = _make_weekly(df).iloc[:10]
    ctx = _pb_ctx(df, weekly=short_weekly)
    res = pb_eval("SYN", df, ctx)
    assert "Weekly above 30-MA" in res.skipped_gates


# ── E2.2d: market cap / D/E skip (pullback) ──────────────────────────────────

def test_pullback_mc_unknown_skips():
    df = _make_pb_df()
    quality = _quality(market_cap=None)
    ctx = _pb_ctx(df, quality=quality)
    res = pb_eval("SYN", df, ctx)
    mc_skipped = any("Market cap" in s for s in res.skipped_gates)
    assert mc_skipped, f"Expected market cap gate skipped; got: {res.skipped_gates}"


def test_pullback_de_unknown_skips():
    df = _make_pb_df()
    quality = _quality(debt_equity=None)
    ctx = _pb_ctx(df, quality=quality)
    res = pb_eval("SYN", df, ctx)
    de_skipped = any("Debt" in s for s in res.skipped_gates)
    assert de_skipped, f"Expected D/E gate skipped; got: {res.skipped_gates}"


def test_pullback_profitable_false_hard_gate():
    df = _make_pb_df()
    quality = _quality(profitable=False)
    ctx = _pb_ctx(df, quality=quality)
    res = pb_eval("SYN", df, ctx)
    assert "Profitable" in res.failed_gates
    assert "Profitable" not in res.skipped_gates


# ── E3.3: breakout earnings gate ─────────────────────────────────────────────

def test_breakout_earnings_within_buffer_fails():
    df = _make_br_df()
    ctx = _br_ctx(df, days_to_earnings=3)
    res = br_eval("SYN", df, ctx)
    assert "Earnings clear" in res.failed_gates
    assert "Earnings clear" not in res.skipped_gates


def test_breakout_earnings_beyond_buffer_passes():
    df = _make_br_df()
    ctx = _br_ctx(df, days_to_earnings=10)
    res = br_eval("SYN", df, ctx)
    assert "Earnings clear" not in res.failed_gates
    assert "Earnings clear" not in res.skipped_gates


def test_breakout_earnings_unknown_skips():
    df = _make_br_df()
    ctx = _br_ctx(df, days_to_earnings=None)
    res = br_eval("SYN", df, ctx)
    assert "Earnings clear" in res.skipped_gates
    assert "Earnings clear" not in res.failed_gates
    # gates_total invariant: total == passed + failed
    assert res.gates_total == res.gates_passed + len(res.failed_gates)


def test_earnings_buffer_days_single_definition():
    from scanner.core import EARNINGS_BUFFER_DAYS
    from scanner.strategies import breakout, pullback
    assert breakout.EARNINGS_BUFFER_DAYS is EARNINGS_BUFFER_DAYS
    assert pullback.EARNINGS_BUFFER_DAYS is EARNINGS_BUFFER_DAYS


# ── E3.2: run_scan ───────────────────────────────────────────────────────────

def test_run_scan_sorted_and_complete(monkeypatch):
    import scanner.core as core
    from scanner.strategies.breakout import evaluate as br_fn

    df = _make_br_df()
    tickers = ["A", "B"]
    quality = _quality()
    as_of = df.index[-1].date()
    ctx = EvalContext(as_of=as_of, market_data={}, weekly=None,
                      quality=quality, days_to_earnings=30)

    monkeypatch.setattr(core, "make_contexts", lambda t, as_of=None: {tk: ctx for tk in t})

    result = run_scan(
        tickers, br_fn, as_of=as_of,
        history_provider=lambda t, end=None: df,
    )
    assert not result.empty
    assert "score" in result.columns
    assert "qualified" in result.columns
    assert len(result) == 2
    # qualified rows should come first (descending sort)
    if result["qualified"].nunique() > 1:
        assert result["qualified"].iloc[0] >= result["qualified"].iloc[1]
