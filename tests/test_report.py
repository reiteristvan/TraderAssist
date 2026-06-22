"""Tests for scanner.report — E8.1/E8.2/E8.3.

Acceptance criteria from CLAUDE.md:
E8.1: hand-built 6-trade fixture (3×+2R, 3×−1R) → 50% win rate, +0.5R expectancy.
      Zero trades → graceful report, exit 0.
E8.2: monotonic fixture verdict correct; n=19 bucket excluded from verdict.
E8.3: fixture where NR7-only failures match qualified expectancy → delta≈0;
      n<30 → 'insufficient n'; headline metrics unchanged by near-miss inclusion.
"""
from __future__ import annotations

from datetime import date

import pytest

from scanner.simulate import Signal, Trade
from scanner.report import (
    compute_metrics,
    bucket_by_score,
    bucket_by_confidence,
    gate_attribution,
    render_report,
    _monotonic_verdict,
    MIN_ATTRIBUTION_N,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _trade(
    r: float,
    exit_reason: str = "target",
    score: float = 60.0,
    confidence: str = "MEDIUM",
    qualified: bool = True,
    failed_gates: list | None = None,
    signal_date: date = date(2026, 1, 2),
    exit_date: date = date(2026, 1, 12),
    flags: dict | None = None,
) -> Trade:
    return Trade(
        ticker="TEST",
        signal_date=signal_date,
        entry_date=date(2026, 1, 3),
        entry_px=100.0,
        exit_date=exit_date,
        exit_px=100.0 + r * 10,  # stop=90 → risk=10; exit=entry+r*risk
        exit_reason=exit_reason,
        r_multiple=r,
        holding_days=10,
        score=score,
        confidence=confidence,
        strategy="pullback",
        qualified=qualified,
        failed_gates=failed_gates or [],
        flags=flags or {},
    )


def _signal(qualified=True, failed_gates=None, sig_date=date(2026, 3, 5)) -> Signal:
    return Signal(
        date=sig_date,
        ticker="TEST",
        strategy="pullback",
        score=60.0,
        confidence="MEDIUM",
        stop=90.0,
        target=110.0,
        atr=1.0,
        qualified=qualified,
        failed_gates=failed_gates or [],
    )


# ── E8.1 — compute_metrics ────────────────────────────────────────────────────

def test_compute_metrics_hand_fixture():
    """3×+2R wins + 3×−1R losses → 50% win rate, +0.5R expectancy."""
    trades = (
        [_trade(+2.0)] * 3
        + [_trade(-1.0, exit_reason="stop")] * 3
    )
    m = compute_metrics(trades)

    assert m["count"] == 6
    assert m["win_rate"] == pytest.approx(0.5)
    assert m["avg_win_r"] == pytest.approx(2.0)
    assert m["avg_loss_r"] == pytest.approx(-1.0)
    assert m["expectancy_r"] == pytest.approx(0.5)  # (3×2 + 3×−1) / 6 = 3/6 = 0.5


def test_compute_metrics_zero_trades():
    """No qualifying trades → graceful output, no crash."""
    m = compute_metrics([])
    assert m["count"] == 0
    assert m["win_rate"] is None
    assert m["expectancy_r"] is None


def test_compute_metrics_gap_skips_excluded_from_count():
    """Gap-skip trades (r=None) do not contribute to count/expectancy."""
    trades = [
        _trade(+2.0),
        _trade(-1.0, exit_reason="stop"),
        Trade(  # gap-skip
            ticker="X", signal_date=date(2026, 1, 2),
            entry_date=date(2026, 1, 3), entry_px=100.0,
            exit_date=date(2026, 1, 3), exit_px=100.0,
            exit_reason="gap_skip_up",
            r_multiple=None, holding_days=0, score=60.0,
            confidence=None, strategy="pullback", qualified=True,
            flags={"skipped_gap": True},
        ),
    ]
    m = compute_metrics(trades)
    assert m["count"] == 2  # gap-skip excluded
    assert m["gap_skip_pct"] == pytest.approx(1 / 3)


def test_compute_metrics_max_drawdown():
    """Drawdown of R-curve: [+2, +2, -1, -1, -1] → peak=4, trough=2 → DD=2."""
    trades = [
        _trade(+2.0, exit_date=date(2026, 1, 3)),
        _trade(+2.0, exit_date=date(2026, 1, 4)),
        _trade(-1.0, exit_date=date(2026, 1, 5), exit_reason="stop"),
        _trade(-1.0, exit_date=date(2026, 1, 6), exit_reason="stop"),
        _trade(-1.0, exit_date=date(2026, 1, 7), exit_reason="stop"),
    ]
    m = compute_metrics(trades)
    assert m["max_drawdown_r"] == pytest.approx(3.0)  # peak=4 at idx 1, then drop 3R


def test_compute_metrics_ambiguous_bar_pct():
    trades = [
        _trade(+2.0, flags={"ambiguous_bar": True}),
        _trade(+1.0),
        _trade(-1.0, exit_reason="stop"),
    ]
    m = compute_metrics(trades)
    assert m["ambiguous_bar_pct"] == pytest.approx(1 / 3)


# ── E8.2 — bucket_by_score / bucket_by_confidence ────────────────────────────

def test_bucket_by_score_basic():
    """50 trades with score 60 land in the 55–69 bucket."""
    trades = [_trade(+1.0, score=60.0)] * 50 + [_trade(-1.0, score=60.0, exit_reason="stop")] * 50
    buckets = bucket_by_score(trades)
    hit = next(b for b in buckets if b["bucket"] == "55–69")
    assert hit["n"] == 100
    assert hit["win_rate"] == pytest.approx(0.5)
    assert hit["verdict"] == "ok"


def test_bucket_by_score_insufficient_n():
    """Fewer than 20 trades → verdict 'insufficient n'."""
    trades = [_trade(+1.0, score=60.0)] * 5
    buckets = bucket_by_score(trades)
    hit = next(b for b in buckets if b["bucket"] == "55–69")
    assert hit["n"] == 5
    assert hit["verdict"] == "insufficient n"


def test_monotonic_verdict_increasing():
    buckets = [
        {"expectancy_r": 0.1, "verdict": "ok"},
        {"expectancy_r": 0.3, "verdict": "ok"},
        {"expectancy_r": 0.5, "verdict": "ok"},
    ]
    assert _monotonic_verdict(buckets) == "monotonically increasing"


def test_monotonic_verdict_non_monotonic():
    buckets = [
        {"expectancy_r": 0.1, "verdict": "ok"},
        {"expectancy_r": 0.5, "verdict": "ok"},
        {"expectancy_r": 0.2, "verdict": "ok"},
    ]
    assert _monotonic_verdict(buckets) == "non-monotonic"


def test_monotonic_verdict_excludes_insufficient():
    """Only 'ok' buckets contribute to the verdict."""
    buckets = [
        {"expectancy_r": 0.1, "verdict": "ok"},
        {"expectancy_r": None, "verdict": "insufficient n"},
        {"expectancy_r": 0.5, "verdict": "ok"},
    ]
    # Only two ok buckets: [0.1, 0.5] → monotonically increasing
    assert _monotonic_verdict(buckets) == "monotonically increasing"


def test_bucket_by_confidence_levels():
    lo = [_trade(+0.5, confidence="LOW")] * 30
    med = [_trade(+1.0, confidence="MEDIUM")] * 30
    hi = [_trade(+2.0, confidence="HIGH")] * 30
    buckets = bucket_by_confidence(lo + med + hi)
    exp_by_conf = {b["bucket"]: b["expectancy_r"] for b in buckets}
    assert exp_by_conf["LOW"] == pytest.approx(0.5)
    assert exp_by_conf["MEDIUM"] == pytest.approx(1.0)
    assert exp_by_conf["HIGH"] == pytest.approx(2.0)


# ── E8.3 — gate_attribution ───────────────────────────────────────────────────

def test_gate_attribution_delta_near_zero():
    """Near-misses matching qualified expectancy → 'no measurable value'."""
    # Qualified expectancy = 0.5R; near-miss single-gate NR7 trades also avg 0.5R
    qualified_exp = 0.5
    near_misses = [
        _trade(+0.5, qualified=False, failed_gates=["NR7 pattern"]) for _ in range(35)
    ]
    all_trades = near_misses

    attr = gate_attribution(all_trades, qualified_exp)
    assert len(attr) == 1
    a = attr[0]
    assert a["gate"] == "NR7 pattern"
    assert a["n"] == 35
    assert a["verdict"] == "no measurable value in this sample"


def test_gate_attribution_insufficient_n():
    """Fewer than 30 near-misses for a gate → 'insufficient n'."""
    near_misses = [
        _trade(+0.5, qualified=False, failed_gates=["NR7 pattern"]) for _ in range(15)
    ]
    attr = gate_attribution(near_misses, 0.5)
    a = attr[0]
    assert a["n"] == 15
    assert a["verdict"] == "insufficient n"


def test_gate_attribution_skips_multi_fail():
    """Trades failing >1 gate are NOT included in single-gate attribution."""
    near_misses = [
        _trade(+0.5, qualified=False, failed_gates=["NR7 pattern", "RSI in range"])
        for _ in range(40)
    ]
    attr = gate_attribution(near_misses, 0.5)
    # No single-gate failures → empty attribution
    assert attr == []


def test_gate_attribution_does_not_affect_headline():
    """Including near_miss_trades in render_report doesn't change qualified metrics."""
    q_trades = [_trade(+2.0)] * 3 + [_trade(-1.0, exit_reason="stop")] * 3
    nm_trades = [_trade(-0.5, qualified=False, failed_gates=["NR7 pattern"])] * 40

    signals = [_signal(qualified=True)] * 6 + [_signal(qualified=False, failed_gates=["NR7 pattern"])] * 40

    md, json_data = render_report(signals, q_trades, nm_trades)

    assert json_data["metrics"]["count"] == 6  # only qualified trades
    assert json_data["metrics"]["expectancy_r"] == pytest.approx(0.5)


# ── render_report — zero trades ───────────────────────────────────────────────

def test_render_report_zero_trades():
    """Zero qualified trades → graceful report, no exception."""
    md, json_data = render_report([], [], [])
    assert "No qualifying trades" in md
    assert json_data["metrics"]["count"] == 0


def test_render_report_contains_bias_block():
    """Bias disclosure block present in every report."""
    md, json_data = render_report([], [], [])
    assert "Survivorship bias" in md
    assert "Look-ahead bias" in md
    assert len(json_data["biases"]) >= 2


def test_render_report_structure():
    """JSON report has expected top-level keys."""
    md, json_data = render_report([], [], [])
    for key in ("metrics", "score_buckets", "conf_buckets", "gate_attribution", "biases"):
        assert key in json_data
