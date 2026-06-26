"""E0.2 acceptance criteria: synthetic fixture factories behave as specified."""
from datetime import date

import pytest

from scanner.core import QualityInfo, EvalContext
import scanner.strategies.pullback as pb
import scanner.strategies.breakout as br

from tests.conftest import (
    make_pullback_setup,
    make_breakout_setup,
    make_downtrend,
    make_choppy,
    make_quality,
    make_market_data,
    patch_pullback_external,
)


def _make_ctx(df, market, quality, as_of_date="2026-06-15"):
    from scanner.data_store import resample_weekly
    as_of = date.fromisoformat(as_of_date)
    return EvalContext(
        as_of=as_of,
        market_data=market,
        weekly=resample_weekly(df),
        quality=QualityInfo(**quality),
        days_to_earnings=30,
    )


def test_pullback_setup_qualifies(monkeypatch):
    patch_pullback_external(monkeypatch)
    df = make_pullback_setup()
    market = make_market_data()
    quality = make_quality()
    ctx = _make_ctx(df, market, quality)
    res = pb.evaluate("SYN", df, ctx, verbose=True)
    assert res.qualified is True


def test_breakout_setup_qualifies():
    df = make_breakout_setup()
    market = make_market_data()
    quality = make_quality()
    ctx = _make_ctx(df, market, quality)
    res = br.evaluate("SYN", df, ctx)
    assert res is not None


def test_downtrend_fails_both(monkeypatch):
    patch_pullback_external(monkeypatch)
    df = make_downtrend()
    market = make_market_data()
    quality = make_quality()
    ctx = _make_ctx(df, market, quality)
    pres = pb.evaluate("SYN", df, ctx, verbose=False)
    bres = br.evaluate("SYN", df, ctx)
    assert pres.qualified is False
    assert bres is not None and bres.qualified is False


def test_choppy_fails_both(monkeypatch):
    patch_pullback_external(monkeypatch)
    df = make_choppy()
    market = make_market_data()
    quality = make_quality()
    ctx = _make_ctx(df, market, quality)
    pres = pb.evaluate("SYN", df, ctx, verbose=False)
    bres = br.evaluate("SYN", df, ctx)
    assert pres.qualified is False
    assert bres is not None and bres.qualified is False


def test_factories_deterministic():
    assert make_pullback_setup().equals(make_pullback_setup())
    assert make_breakout_setup().equals(make_breakout_setup())
    assert make_downtrend().equals(make_downtrend())
    assert make_choppy().equals(make_choppy())
    md1, md2 = make_market_data(), make_market_data()
    assert set(md1.keys()) == set(md2.keys())
    assert all(md1[k].equals(md2[k]) for k in md1)
