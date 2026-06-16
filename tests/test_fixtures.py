"""E0.2 acceptance criteria: synthetic fixture factories behave as specified."""
import pullback_filter as pf
import breakout_filter as bf

from tests.conftest import (
    make_pullback_setup,
    make_breakout_setup,
    make_downtrend,
    make_choppy,
    make_quality,
    make_market_data,
    patch_pullback_external,
)


def test_pullback_setup_qualifies(monkeypatch):
    patch_pullback_external(monkeypatch)
    res = pf._evaluate("SYN", make_pullback_setup(), make_quality(), make_market_data(), verbose=True)
    assert res.qualified is True


def test_breakout_setup_qualifies():
    res = bf._evaluate("SYN", make_breakout_setup(), make_quality())
    assert res is not None


def test_downtrend_fails_both(monkeypatch):
    patch_pullback_external(monkeypatch)
    df = make_downtrend()
    pres = pf._evaluate("SYN", df, make_quality(), make_market_data(), verbose=False)
    bres = bf._evaluate("SYN", df, make_quality())
    assert pres.qualified is False
    assert bres is None


def test_choppy_fails_both(monkeypatch):
    patch_pullback_external(monkeypatch)
    df = make_choppy()
    pres = pf._evaluate("SYN", df, make_quality(), make_market_data(), verbose=False)
    bres = bf._evaluate("SYN", df, make_quality())
    assert pres.qualified is False
    assert bres is None


def test_factories_deterministic():
    assert make_pullback_setup().equals(make_pullback_setup())
    assert make_breakout_setup().equals(make_breakout_setup())
    assert make_downtrend().equals(make_downtrend())
    assert make_choppy().equals(make_choppy())
    md1, md2 = make_market_data(), make_market_data()
    assert set(md1.keys()) == set(md2.keys())
    assert all(md1[k].equals(md2[k]) for k in md1)
