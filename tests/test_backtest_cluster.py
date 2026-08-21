"""Tests for backtest-only cluster suppression — quick task 260821-jw1.

Locked decisions (CONTEXT.md aliases D-01/D-02/D-03 == D1/D2/D3):
- D1 / D-01 — qualified-only: only `qualified=True` signals increment the
  per-ticker window and only they can be suppressed; near-misses pass through
  untouched.
- D2 / D-02 — a suppressed signal still records its date into the window.
- D3 / D-03 — CLI flag, default OFF; setting recorded in `run_meta.json`.
"""
from __future__ import annotations

import dataclasses
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from scanner.backtest import ClusterSuppressor, generate_signals
from scanner.core import QualityInfo


# ── ClusterSuppressor — unit tests ────────────────────────────────────────────

def test_disabled_when_limit_none():
    cs = ClusterSuppressor(limit=None, window=10)
    d = date(2026, 1, 1)
    for i in range(5):
        assert cs.admit("AAPL", d + timedelta(days=i), True) is True
    assert cs.suppressed == 0
    assert cs._dates_by_ticker == {}


def test_disabled_when_limit_zero_or_negative():
    for lim in (0, -1, -5):
        cs = ClusterSuppressor(limit=lim, window=10)
        d = date(2026, 1, 1)
        for i in range(5):
            assert cs.admit("AAPL", d + timedelta(days=i), True) is True
        assert cs.suppressed == 0
        assert cs._dates_by_ticker == {}


def test_exactly_at_limit():
    cs = ClusterSuppressor(limit=3, window=10)
    base = date(2026, 1, 1)
    results = [cs.admit("AAPL", base + timedelta(days=i), True) for i in range(4)]
    assert results == [True, True, True, False]
    assert cs.suppressed == 1


def test_under_limit_admits():
    cs = ClusterSuppressor(limit=3, window=10)
    base = date(2026, 1, 1)
    r1 = cs.admit("AAPL", base, True)
    r2 = cs.admit("AAPL", base + timedelta(days=1), True)
    assert r1 is True
    assert r2 is True
    assert cs.suppressed == 0


def test_calendar_boundary_in_window():
    """Exactly 10 calendar days IS inside the window; straddles a weekend."""
    cs = ClusterSuppressor(limit=1, window=10)
    p = date(2026, 1, 2)   # Friday
    d = p + timedelta(days=10)  # following Monday-week — straddles a weekend
    assert cs.admit("AAPL", p, True) is True
    assert cs.admit("AAPL", d, True) is False
    assert cs.suppressed == 1


def test_calendar_boundary_out_of_window():
    """Exactly 11 calendar days is NOT inside the window."""
    cs = ClusterSuppressor(limit=3, window=10)
    base = date(2026, 1, 15)
    for ago in (11, 5, 2):
        cs.admit("AAPL", base - timedelta(days=ago), True)
    # only -5 and -2 are in-window (count=2); -11 is out; limit=3 -> admit
    assert cs.admit("AAPL", base, True) is True
    assert cs.suppressed == 0


def test_same_day_prior_does_not_count():
    cs = ClusterSuppressor(limit=1, window=10)
    d = date(2026, 1, 1)
    assert cs.admit("AAPL", d, True) is True
    assert cs.admit("AAPL", d, True) is True  # delta == 0 -> not counted
    assert cs.suppressed == 0


def test_near_misses_ignored():
    cs_with_nm = ClusterSuppressor(limit=3, window=10)
    cs_without_nm = ClusterSuppressor(limit=3, window=10)
    base = date(2026, 1, 1)

    seq_with = [
        ("q", base, True),
        ("nm", base + timedelta(days=1), False),
        ("q", base + timedelta(days=2), True),
        ("nm", base + timedelta(days=3), False),
        ("q", base + timedelta(days=4), True),
        ("q", base + timedelta(days=5), True),  # 4th qualified -> suppressed
    ]
    seq_without = [t for t in seq_with if t[0] == "q"]

    results_with = [cs_with_nm.admit("AAPL", d, q) for _, d, q in seq_with]
    results_without = [cs_without_nm.admit("AAPL", d, q) for _, d, q in seq_without]

    q_results_with = [r for r, (kind, _, _) in zip(results_with, seq_with) if kind == "q"]
    assert q_results_with == results_without
    assert cs_with_nm.suppressed == cs_without_nm.suppressed

    nm_results = [r for r, (kind, _, _) in zip(results_with, seq_with) if kind == "nm"]
    assert all(r is True for r in nm_results)
    # near-miss dates never entered the registry
    assert len(cs_with_nm._dates_by_ticker["AAPL"]) == len(seq_without)


def test_suppressed_still_counts_toward_window():
    """Leaky-bucket regression: candidates 4, 5 and 6 must ALL stay suppressed."""
    cs = ClusterSuppressor(limit=3, window=10)
    base = date(2026, 1, 1)
    results = [cs.admit("AAPL", base + timedelta(days=i), True) for i in range(6)]
    assert results == [True, True, True, False, False, False]
    assert cs.suppressed == 3


def test_per_ticker_isolation():
    cs = ClusterSuppressor(limit=3, window=10)
    base = date(2026, 1, 1)
    for i in range(4):
        cs.admit("AAPL", base + timedelta(days=i), True)
    assert cs.suppressed == 1  # AAPL's 4th
    assert cs.admit("MSFT", base + timedelta(days=3), True) is True
    assert cs.suppressed == 1  # unchanged by MSFT


def test_suppressed_counter_equals_false_returns():
    cs = ClusterSuppressor(limit=2, window=10)
    base = date(2026, 1, 1)
    results = [cs.admit("AAPL", base + timedelta(days=i), True) for i in range(10)]
    assert cs.suppressed == sum(1 for r in results if r is False)


# ── generate_signals — end-to-end integration ─────────────────────────────────

def _bdate_index(n, end="2026-06-15"):
    return pd.bdate_range(end=pd.Timestamp(end), periods=n)


def _trend_bars(n=260, start_price=20.0, r=0.003, seed=1) -> pd.DataFrame:
    """Simple monotonic uptrend — same shape as test_backtest.py's helper,
    duplicated locally per the plan's read_first note (no cross-module import
    of private test helpers)."""
    rng = np.random.default_rng(seed)
    closes = start_price * (1 + r) ** np.arange(n)
    noise = rng.normal(0, 0.002, n)
    closes = closes * (1 + noise)
    idx = _bdate_index(n)
    opens = closes * (1 + rng.normal(0, 0.001, n))
    highs = np.maximum(opens, closes) * (1 + np.abs(rng.normal(0.002, 0.001, n)))
    lows = np.minimum(opens, closes) * (1 - np.abs(rng.normal(0.002, 0.001, n)))
    return pd.DataFrame(
        {"Open": opens, "High": highs, "Low": lows, "Close": closes,
         "Volume": np.full(n, 2_000_000.0)},
        index=idx,
    )


def _spy_bars(n=260) -> pd.DataFrame:
    closes = 400.0 * (1 + 0.0004) ** np.arange(n)
    idx = _bdate_index(n)
    return pd.DataFrame(
        {"Open": closes, "High": closes * 1.002, "Low": closes * 0.998,
         "Close": closes, "Volume": np.full(n, 5_000_000.0)},
        index=idx,
    )


def _quality() -> QualityInfo:
    return QualityInfo(
        profitable=True, market_cap=2.5e9, debt_equity=50.0,
        sector="Technology", float_shares=50e6,
    )


def _market(spy_bars: pd.DataFrame) -> dict[str, pd.DataFrame]:
    from scanner.core import INDUSTRY_ETF_MAP, SECTOR_ETF_MAP
    all_etfs = set(SECTOR_ETF_MAP.values()) | set(INDUSTRY_ETF_MAP.values())
    return {"SPY": spy_bars, **{etf: spy_bars for etf in all_etfs}}


def _fake_pullback_result(ticker, close, ctx, qualified):
    from scanner.strategies.pullback import PullbackResult
    return PullbackResult(
        ticker=ticker, close=close, sma50=close * 0.95, sma200=close * 0.9,
        ma200_distance_pct=5.0, swing_high=close * 1.05, pullback_depth_pct=3.0,
        pullback_days=5, support="sma50", support_level=close * 0.95,
        distance_to_support_pct=1.0, vol_contraction=0.8, rsi=50.0, adx=25.0,
        trigger_candle=True, pocket_pivot=False, nr7=False, rs_strength=1.1,
        rs_at_new_high=True, sector="Technology", sector_etf="XLK",
        sector_outperforming=True, weekly_above_30ma=True, weekly_30ma_rising=True,
        days_to_earnings=ctx.days_to_earnings, market_cap=2.5e9, profitable=True,
        debt_equity=50.0, qualified=qualified,
        failed_gates=[] if qualified else ["rsi_gate"],
        skipped_gates=[], gates_passed=8 if qualified else 7, gates_total=8,
        score=80.0 if qualified else 40.0, as_of=ctx.as_of,
    )


def _make_scripted_evaluate(qualified_dates: set, near_miss_dates: set):
    """Deterministic stand-in for pullback.evaluate — canned qualified /
    near-miss results on a fixed per-date schedule so the cluster-suppression
    integration test does not depend on the real strategy's numeric gates.
    """
    def _fake_evaluate(ticker, df, ctx, verbose=False, precomp=None):
        close = float(df["Close"].iloc[-1])
        d = ctx.as_of
        if d in qualified_dates:
            return _fake_pullback_result(ticker, close, ctx, True)
        if d in near_miss_dates:
            return _fake_pullback_result(ticker, close, ctx, False)
        return None
    return _fake_evaluate


def test_generate_signals_cluster_suppression_end_to_end(monkeypatch):
    n = 260
    daily = _trend_bars(n=n)
    spy = _spy_bars(n=n)
    market = _market(spy)
    quality = _quality()

    # Last 8 trading days of the fixture: 6 consecutive qualified days for T1,
    # followed by 1 near-miss day. All 6 qualified dates fall inside a single
    # rolling 10-calendar-day window (they span < 10 calendar days).
    trading_idx = daily.index[-8:]
    qualified_dates = {ts.date() for ts in trading_idx[:6]}
    near_miss_dates = {trading_idx[6].date()}
    start = trading_idx[0].date()
    end = trading_idx[-1].date()

    span = (max(qualified_dates) - min(qualified_dates)).days
    assert span < 10, "fixture dates must fall inside a single 10-day window"

    fake_evaluate = _make_scripted_evaluate(qualified_dates, near_miss_dates)
    monkeypatch.setattr("scanner.strategies.pullback.evaluate", fake_evaluate)

    def _bars_loader(t):
        return {"T1": daily, "SPY": spy}.get(t)

    common_kwargs = dict(
        universe=["T1"],
        start=start,
        end=end,
        strategy="pullback",
        _bars_loader=_bars_loader,
        _market_loader=lambda: market,
        _quality_loader=lambda t: quality,
        _earnings_loader=lambda t: [],
    )

    baseline = generate_signals(**common_kwargs)
    baseline_qualified = [s for s in baseline if s.qualified]
    baseline_near_miss = [s for s in baseline if not s.qualified]
    assert len(baseline_qualified) > 0, "fixture produced no qualified signals"

    cluster_stats: dict = {}
    suppressed_run = generate_signals(
        **common_kwargs, cluster_limit=3, cluster_window=10, cluster_stats=cluster_stats,
    )
    suppressed_qualified = [s for s in suppressed_run if s.qualified]
    suppressed_near_miss = [s for s in suppressed_run if not s.qualified]

    assert len(suppressed_qualified) < len(baseline_qualified)
    baseline_dates = {s.date for s in baseline_qualified}
    suppressed_dates = {s.date for s in suppressed_qualified}
    assert suppressed_dates < baseline_dates  # strict subset

    assert [dataclasses.asdict(s) for s in suppressed_near_miss] == \
           [dataclasses.asdict(s) for s in baseline_near_miss]

    assert cluster_stats["cluster_suppressed"] == \
           len(baseline_qualified) - len(suppressed_qualified)
    assert cluster_stats["cluster_limit"] == 3
    assert cluster_stats["cluster_window"] == 10


# ── CLI flags — scan.py build_parser() ────────────────────────────────────────

def test_backtest_parser_cluster_flags_default_off():
    from scan import build_parser
    parser = build_parser()
    args = parser.parse_args([
        "backtest", "--tickers", "AAPL", "--start", "2026-01-01", "--end", "2026-01-31",
    ])
    assert args.cluster_limit is None
    assert args.cluster_window == 10


def test_backtest_parser_cluster_flags_explicit():
    from scan import build_parser
    parser = build_parser()
    args = parser.parse_args([
        "backtest", "--tickers", "AAPL", "--start", "2026-01-01", "--end", "2026-01-31",
        "--cluster-limit", "3", "--cluster-window", "14",
    ])
    assert args.cluster_limit == 3
    assert args.cluster_window == 14


def test_scan_parser_rejects_cluster_flags():
    from scan import build_parser
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["scan", "--tickers", "AAPL", "--cluster-limit", "3"])


# ── render_report — conditional cluster line ──────────────────────────────────

def test_render_report_no_cluster_line_when_absent():
    from scanner.report import render_report
    md, _ = render_report([], [], [], run_meta={"strategy": "pullback"})
    assert "Cluster suppression" not in md


def test_render_report_no_cluster_line_when_disabled():
    from scanner.report import render_report
    md, _ = render_report([], [], [], run_meta={
        "strategy": "pullback", "cluster_limit": None, "cluster_window": 10,
        "cluster_suppressed": 0,
    })
    assert "Cluster suppression" not in md


def test_render_report_has_cluster_line_when_enabled():
    from scanner.report import render_report
    md, _ = render_report([], [], [], run_meta={
        "strategy": "pullback", "cluster_limit": 3, "cluster_window": 10,
        "cluster_suppressed": 5,
    })
    assert "Cluster suppression: limit=3, window=10d, suppressed=5" in md
