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
    failure_analysis,
    bucket_by_target_r,
    bucket_by_target_atr,
    stop_out_forensics,
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
    target_r: float | None = None,
    target_atr: float | None = None,
    mae_r: float | None = None,
    mfe_r: float | None = None,
    post_stop_reached_target: bool | None = None,
    post_stop_mfe_r: float | None = None,
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
        target_r=target_r,
        target_atr=target_atr,
        mae_r=mae_r,
        mfe_r=mfe_r,
        post_stop_reached_target=post_stop_reached_target,
        post_stop_mfe_r=post_stop_mfe_r,
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


# ── E13.1 — failure_analysis ──────────────────────────────────────────────────

def test_failure_analysis_mixed():
    """Equal stop/time-stop split → mixed interpretation."""
    trades = (
        [_trade(-1.0, exit_reason="stop")] * 3
        + [_trade(0.0, exit_reason="time_stop")] * 3
    )
    fa = failure_analysis(trades)
    assert fa["total_non_winners"] == 6
    assert fa["stop_out"] == 3
    assert fa["time_stop"] == 3
    assert fa["stop_out"] + fa["time_stop"] + fa["other"] == fa["total_non_winners"]
    assert "mixed" in fa["interpretation"].lower() or "Mixed" in fa["interpretation"]


def test_failure_analysis_time_stop_heavy():
    """7 time-stops vs 1 stop-out → time-stop-dominated interpretation."""
    trades = (
        [_trade(-1.0, exit_reason="stop")] * 1
        + [_trade(0.0, exit_reason="time_stop")] * 7
    )
    fa = failure_analysis(trades)
    assert fa["total_non_winners"] == 8
    assert fa["time_stop"] == 7
    assert "time" in fa["interpretation"].lower()


def test_failure_analysis_stop_heavy():
    """7 stop-outs vs 1 time-stop → stop-out-dominated interpretation."""
    trades = (
        [_trade(-1.0, exit_reason="stop")] * 7
        + [_trade(0.0, exit_reason="time_stop")] * 1
    )
    fa = failure_analysis(trades)
    assert fa["stop_out"] == 7
    assert fa["stop_out"] + fa["time_stop"] + fa["other"] == fa["total_non_winners"]
    assert "stop" in fa["interpretation"].lower()


def test_failure_analysis_wins_excluded():
    """Winning trades are not included in the non-winner count."""
    trades = (
        [_trade(+2.0, exit_reason="target")] * 3
        + [_trade(-1.0, exit_reason="stop")] * 2
    )
    fa = failure_analysis(trades)
    assert fa["total_non_winners"] == 2
    assert fa["stop_out"] == 2


def test_failure_analysis_no_losers():
    """Zero non-winners → graceful output."""
    trades = [_trade(+1.0)] * 5
    fa = failure_analysis(trades)
    assert fa["total_non_winners"] == 0
    assert fa["stop_out"] == 0
    assert fa["time_stop"] == 0
    assert "No non-winning" in fa["interpretation"]


# ── E13.1 — bucket_by_target_r / bucket_by_target_atr ────────────────────────

def test_bucket_by_target_r_basic():
    """Trades with target_r=2.2 land in the 2.0–2.5 bucket."""
    trades = (
        [_trade(+1.0, target_r=2.2)] * 30
        + [_trade(-1.0, exit_reason="stop", target_r=2.2)] * 30
    )
    buckets = bucket_by_target_r(trades)
    hit = next(b for b in buckets if b["bucket"].startswith("2.0"))
    assert hit["n"] == 60
    assert hit["hit_rate"] == pytest.approx(0.5)


def test_bucket_by_target_r_none_excluded():
    """Trades with target_r=None are not counted in any bucket."""
    trades = [_trade(+1.0, target_r=None)] * 10
    buckets = bucket_by_target_r(trades)
    assert all(b["n"] == 0 for b in buckets)


def test_bucket_by_target_atr_basic():
    """Trades with target_atr=1.8 land in the 1.5–2.0 bucket."""
    trades = [_trade(+1.0, target_atr=1.8)] * 20
    buckets = bucket_by_target_atr(trades)
    hit = next(b for b in buckets if b["bucket"].startswith("1.5"))
    assert hit["n"] == 20
    assert hit["hit_rate"] == pytest.approx(1.0)


# ── E13.1 — render_report has new keys ───────────────────────────────────────

def test_render_report_has_failure_and_bucket_keys():
    """render_report JSON output contains E13.1 keys."""
    md, json_data = render_report([], [], [])
    assert "failure_analysis" in json_data
    assert "target_r_buckets" in json_data
    assert "target_atr_buckets" in json_data


# ── E14.1 — stop_out_forensics ────────────────────────────────────────────────

def test_stop_out_forensics_branch_a():
    """High reach rate + winners' MAE near −1 → Branch A."""
    # 40 stop-outs: 50% reach target post-stop
    stop_outs = (
        [_trade(-1.0, exit_reason="stop",
                post_stop_reached_target=True, post_stop_mfe_r=1.5)] * 20
        + [_trade(-1.0, exit_reason="stop",
                  post_stop_reached_target=False, post_stop_mfe_r=-0.5)] * 20
    )
    # 20 winners: 40% had MAE within 0.25R of stop (mae_r ≤ −0.75)
    winners = [_trade(+1.5, mae_r=-0.9)] * 8 + [_trade(+2.0, mae_r=-0.2)] * 12

    fo = stop_out_forensics(stop_outs + winners)

    assert fo["n_stop_outs"] == 40
    assert fo["pct_reached_target"] == pytest.approx(0.5)
    assert fo["winners_mae_near_minus1_pct"] == pytest.approx(8 / 20)
    assert fo["branch"] == "A"
    assert "Branch A" in fo["interpretation"] or "stops too tight" in fo["interpretation"]


def test_stop_out_forensics_branch_b():
    """Low reach rate → Branch B."""
    stop_outs = (
        [_trade(-1.0, exit_reason="stop",
                post_stop_reached_target=True, post_stop_mfe_r=1.2)] * 4
        + [_trade(-1.0, exit_reason="stop",
                  post_stop_reached_target=False, post_stop_mfe_r=-0.8)] * 36
    )
    winners = [_trade(+1.5, mae_r=-0.3)] * 20  # none near −1

    fo = stop_out_forensics(stop_outs + winners)

    assert fo["pct_reached_target"] == pytest.approx(0.1)
    assert fo["branch"] == "B"
    assert "Branch B" in fo["interpretation"] or "edge" in fo["interpretation"]


def test_stop_out_forensics_no_stop_outs():
    """No stop-outs → n=0 and graceful None fields."""
    trades = [_trade(+1.0)] * 5 + [_trade(0.0, exit_reason="time_stop")] * 3
    fo = stop_out_forensics(trades)
    assert fo["n_stop_outs"] == 0
    assert fo["pct_reached_target"] is None
    assert fo["branch"] is None
    assert "No stop-out" in fo["interpretation"]


def test_stop_out_forensics_no_post_data():
    """Stop-outs with post_stop_reached_target=None → pct_reached=None, no branch."""
    trades = [_trade(-1.0, exit_reason="stop")] * 10  # no post-stop fields set
    fo = stop_out_forensics(trades)
    assert fo["n_stop_outs"] == 10
    assert fo["pct_reached_target"] is None
    assert fo["branch"] is None


def test_render_report_has_stop_out_forensics():
    """render_report JSON output contains E14.1 stop_out_forensics key."""
    md, json_data = render_report([], [], [])
    assert "stop_out_forensics" in json_data
