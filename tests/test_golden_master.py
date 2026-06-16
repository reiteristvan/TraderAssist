"""E0.3 golden-master snapshots: current evaluators vs frozen expected
values for the E0.2 fixtures, plus one near-miss variant per strategy.

These snapshots are the refactor contract: later epics (E2/E3) must keep
them green, modulo explicitly-allowed diffs each task lists.
"""
import json
from pathlib import Path

from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator

import pullback_filter as pf
import breakout_filter as bf

from tests.conftest import (
    make_pullback_setup,
    make_breakout_setup,
    make_quality,
    make_market_data,
    patch_pullback_external,
)

GOLDEN_DIR = Path(__file__).parent / "golden"

PULLBACK_FIELDS = [
    "qualified", "failed_gates", "gates_passed", "gates_total", "score",
    "pullback_depth_pct", "rsi", "adx", "vol_contraction", "rs_strength",
    "ma200_distance_pct",
]

BREAKOUT_FIELDS = [
    "ticker", "close", "pct_to_52w_high", "vol_ratio", "rsi", "adx",
    "bb_width", "market_cap", "profitable", "debt_equity", "score",
]


def _load(name):
    with open(GOLDEN_DIR / name) as f:
        return json.load(f)


def _assert_field_matches(actual, expected, field):
    if isinstance(expected, float):
        assert abs(actual - expected) <= 0.1, f"{field}: {actual} vs expected {expected}"
    else:
        assert actual == expected, f"{field}: {actual!r} vs expected {expected!r}"


def test_pullback_qualifying_golden_master(monkeypatch):
    patch_pullback_external(monkeypatch)
    res = pf._evaluate("SYN", make_pullback_setup(), make_quality(), make_market_data(), verbose=False)
    expected = _load("pullback_qualifying.json")
    for field in PULLBACK_FIELDS:
        _assert_field_matches(getattr(res, field), expected[field], field)


def test_pullback_near_miss_golden_master(monkeypatch):
    patch_pullback_external(monkeypatch)
    res = pf._evaluate("SYN", make_pullback_setup(depth=0.035), make_quality(), make_market_data(), verbose=False)
    expected = _load("pullback_near_miss.json")
    for field in PULLBACK_FIELDS:
        _assert_field_matches(getattr(res, field), expected[field], field)


def test_breakout_qualifying_golden_master():
    res = bf._evaluate("SYN", make_breakout_setup(), make_quality())
    expected = _load("breakout_qualifying.json")
    assert res is not None
    for field in BREAKOUT_FIELDS:
        _assert_field_matches(getattr(res, field), expected[field], field)


def test_breakout_near_miss_golden_master():
    df = make_breakout_setup(breakout_jump=0.012, consol_drift=-0.0002)
    expected = _load("breakout_near_miss.json")

    close = float(df["Close"].iloc[-1])
    high_52w = df["High"].rolling(252, min_periods=200).max().iloc[-1]
    consol_high = df["High"].iloc[-bf.CONSOL_LOOKBACK - 1 : -1].max()
    vol_sma50 = df["Volume"].rolling(50).mean().iloc[-1]
    vol_ratio = float(df["Volume"].iloc[-1] / vol_sma50)
    sma50 = SMAIndicator(df["Close"], 50).sma_indicator().iloc[-1]
    sma200 = SMAIndicator(df["Close"], 200).sma_indicator().iloc[-1]
    rsi = float(RSIIndicator(df["Close"], 14).rsi().iloc[-1])

    prior_gates = {
        "pct_to_high_ok": bool(close / high_52w >= bf.NEAR_HIGH_PCT),
        "close_above_consol_high": bool(close >= consol_high),
        "vol_ratio_ok": bool(vol_ratio >= bf.VOL_RATIO_MIN),
        "trend_ok": bool(close > sma50 > sma200),
    }
    assert prior_gates == expected["prior_gates"]
    assert abs(rsi - expected["rsi"]) <= 0.1
    assert not (bf.RSI_RANGE[0] <= rsi <= bf.RSI_RANGE[1])

    res = bf._evaluate("SYN", df, make_quality())
    assert res is expected["result"] is None
