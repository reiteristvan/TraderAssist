"""E0.3 golden-master snapshots — Sprint 2 update.

Now uses scanner.strategies.{pullback,breakout}.evaluate() with EvalContext.
Snapshots are the refactor contract: each field diff is documented in the JSON.
"""
import json
from pathlib import Path

import pandas as pd

from scanner.core import QualityInfo, EvalContext
import scanner.strategies.pullback as pb
import scanner.strategies.breakout as br

from tests.conftest import (
    make_pullback_setup,
    make_breakout_setup,
    make_quality,
    make_market_data,
)

GOLDEN_DIR = Path(__file__).parent / "golden"

PULLBACK_FIELDS = [
    "qualified", "failed_gates", "skipped_gates", "gates_passed", "gates_total", "score",
    "pullback_depth_pct", "rsi", "adx", "vol_contraction", "rs_strength",
    "ma200_distance_pct",
]

BREAKOUT_FIELDS = [
    "ticker", "close", "pct_to_52w_high", "vol_ratio", "rsi", "adx",
    "bb_width", "market_cap", "profitable", "debt_equity", "score",
    "qualified", "failed_gates", "skipped_gates", "gates_passed", "gates_total",
]


def _load(name):
    with open(GOLDEN_DIR / name) as f:
        return json.load(f)


def _assert_field_matches(actual, expected, field):
    if isinstance(expected, float):
        assert abs(actual - expected) <= 0.1, f"{field}: {actual} vs expected {expected}"
    elif isinstance(expected, list):
        assert actual == expected, f"{field}: {actual!r} vs expected {expected!r}"
    else:
        assert actual == expected, f"{field}: {actual!r} vs expected {expected!r}"


def _make_weekly(df):
    weekly = df.resample("W-FRI").agg(
        Open=("Open", "first"), High=("High", "max"),
        Low=("Low", "min"), Close=("Close", "last"), Volume=("Volume", "sum"),
    ).dropna(subset=["Close"])
    if len(weekly) > 0 and weekly.index[-1] > df.index[-1]:
        weekly = weekly.iloc[:-1]
    return weekly


def _pb_ctx(df, q_dict, market_data, days_to_earnings=30):
    quality = QualityInfo(
        profitable=q_dict["profitable"], market_cap=q_dict["market_cap"],
        debt_equity=q_dict["debt_equity"], sector=q_dict.get("sector"),
        float_shares=q_dict.get("float_shares"),
    )
    return EvalContext(
        as_of=df.index[-1].date(), market_data=market_data,
        weekly=_make_weekly(df), quality=quality, days_to_earnings=days_to_earnings,
    )


def _br_ctx(df, q_dict, days_to_earnings=30):
    quality = QualityInfo(
        profitable=q_dict["profitable"], market_cap=q_dict["market_cap"],
        debt_equity=q_dict["debt_equity"], sector=q_dict.get("sector"),
        float_shares=q_dict.get("float_shares"),
    )
    return EvalContext(
        as_of=df.index[-1].date(), market_data={},
        weekly=None, quality=quality, days_to_earnings=days_to_earnings,
    )


def test_pullback_qualifying_golden_master():
    df = make_pullback_setup()
    ctx = _pb_ctx(df, make_quality(), make_market_data())
    res = pb.evaluate("SYN", df, ctx)
    expected = _load("pullback_qualifying.json")
    for field in PULLBACK_FIELDS:
        _assert_field_matches(getattr(res, field), expected[field], field)


def test_pullback_near_miss_golden_master():
    df = make_pullback_setup(depth=0.035)
    ctx = _pb_ctx(df, make_quality(), make_market_data())
    res = pb.evaluate("SYN", df, ctx)
    expected = _load("pullback_near_miss.json")
    for field in PULLBACK_FIELDS:
        _assert_field_matches(getattr(res, field), expected[field], field)


def test_breakout_qualifying_golden_master():
    df = make_breakout_setup()
    ctx = _br_ctx(df, make_quality())
    res = br.evaluate("SYN", df, ctx)
    expected = _load("breakout_qualifying.json")
    assert res is not None
    for field in BREAKOUT_FIELDS:
        _assert_field_matches(getattr(res, field), expected[field], field)


def test_breakout_near_miss_golden_master():
    df = make_breakout_setup(breakout_jump=0.012, consol_drift=-0.0002)
    ctx = _br_ctx(df, make_quality())
    expected = _load("breakout_near_miss.json")
    res = br.evaluate("SYN", df, ctx)
    assert res is not None
    assert res.qualified is False
    assert res.failed_gates == expected["failed_gates"]
    assert res.gates_total == expected["gates_total"]
