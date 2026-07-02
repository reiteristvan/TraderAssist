"""E8 — Metrics & attribution.

Core backtest metrics, score/confidence bucketing, and gate attribution via
near-misses. See CLAUDE.md EPIC E8.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date
from typing import Optional

from scanner.simulate import Signal, Trade

# ── E8.2 bucket boundaries ────────────────────────────────────────────────────

SCORE_BUCKETS = [(40, 54), (55, 69), (70, 84), (85, 999)]
CONF_LEVELS = ["LOW", "MEDIUM", "HIGH"]
MIN_BUCKET_N = 20
MIN_ATTRIBUTION_N = 30

# ── Phase 4 — W/L characteristic analysis (pre-registered; WLA-06 anti-cherry-pick guard) ──
# This list is the sole authoritative feature set. Committed to source before any results viewed.
WL_FEATURES = [
    'RSI at entry',
    'RVOL',
    'Pullback depth %',
    'ATR multiple',
    'Industry momentum',
    'Pct to 52w high',
]
WL_MIN_TOTAL = 200   # total qualified trades below this → abort analysis (WLA-05)
WL_MIN_BUCKET = 50   # winner_n OR loser_n below this → suppress strategy (WLA-05)

# ── E6.3 bias disclosure (static text) ───────────────────────────────────────

_BIAS_SURVIVORSHIP = (
    "**Survivorship bias** — universe contains currently-listed names only; "
    "delisted/bankrupt names are absent. Results are optimistic relative to "
    "the real investable universe at each historical date."
)
_BIAS_LOOK_AHEAD = (
    "**Look-ahead bias (fundamentals)** — quality fields (market cap, "
    "profitability, debt/equity, sector) reflect present-day values applied "
    "to all historical dates. A name that went from small-cap to mid-cap "
    "during the backtest period may have been misclassified in early dates."
)


def _active_trades(trades: list[Trade]) -> list[Trade]:
    """Qualified trades with a valid R (excludes gap-skips and incomplete)."""
    return [t for t in trades if t.qualified and t.r_multiple is not None]


# ── Phase 4 — W/L characteristic analysis helpers ─────────────────────────────

def _safe_median(values: list) -> Optional[float]:
    """Compute median of a list, skipping None values. Returns None if no valid data."""
    if not values:
        return None
    non_none = sorted(v for v in values if v is not None)
    if not non_none:
        return None
    n = len(non_none)
    mid = n // 2
    if n % 2 == 1:
        return float(non_none[mid])
    return float((non_none[mid - 1] + non_none[mid]) / 2)


def _extract_wl_metric(metric: str, trades: list, sig_by_key: dict) -> list:
    """Extract non-None metric values from trades, looking up signals via 3-tuple key.

    'ATR multiple' is sourced directly from t.target_atr; all others require a Signal lookup.
    Returns a list of floats (None values excluded).
    """
    values = []
    for t in trades:
        key = (str(t.signal_date), t.ticker, t.strategy)
        sig = sig_by_key.get(key)

        if metric == 'ATR multiple':
            val = t.target_atr
        elif sig is None:
            val = None
        elif metric == 'RSI at entry':
            val = sig.rsi_entry
        elif metric == 'RVOL':
            val = sig.rvol
        elif metric == 'Pullback depth %':
            val = sig.pullback_depth_pct
        elif metric == 'Industry momentum':
            val = sig.industry_momentum
        elif metric == 'Pct to 52w high':
            val = sig.pct_to_52w_high
        else:
            val = None

        if val is not None:
            values.append(float(val))
    return values


def _fmt_wl_value(metric: str, v: Optional[float]) -> str:
    """Format a W/L metric value for the markdown table (mirrors UI-SPEC Format Rules)."""
    if v is None:
        return "—"  # em dash
    if metric == 'RSI at entry':
        return f"{v:.1f}"
    if metric == 'RVOL':
        return f"{v:.2f}x"
    if metric == 'Pullback depth %':
        sign = '+' if v >= 0 else ''
        return f"{sign}{v:.1f}%"
    if metric == 'ATR multiple':
        return f"{v:.2f}"
    if metric == 'Industry momentum':
        sign = '+' if v >= 0 else ''
        return f"{sign}{v:.1f}%"
    if metric == 'Pct to 52w high':
        return f"{v:.1f}%"
    return f"{v:.2f}"


def _fmt_wl_delta(metric: str, v: Optional[float]) -> str:
    """Format a W/L delta value with explicit +/- sign (mirrors Angular fmtWlDelta)."""
    if v is None:
        return "—"  # em dash
    sign = '+' if v >= 0 else ''
    if metric == 'RSI at entry':
        return f"{sign}{v:.1f}"
    if metric == 'RVOL':
        return f"{sign}{v:.2f}"
    if metric == 'Pullback depth %':
        return f"{sign}{v:.1f}%"
    if metric == 'ATR multiple':
        return f"{sign}{v:.2f}"
    if metric == 'Industry momentum':
        return f"{sign}{v:.1f}%"
    if metric == 'Pct to 52w high':
        return f"{sign}{v:.1f}%"
    return f"{sign}{v:.2f}"


def wl_characteristic_analysis(signals: list, qualified_trades: list) -> dict:
    """Pre-registered winner/loser characteristic analysis over 6 entry-time metrics.

    WLA-01: produces wl_analysis dict for >= WL_MIN_TOTAL qualified trades.
    WLA-02: metric rows are exactly WL_FEATURES in order; no additions at run time.
    WLA-03: analysis is grouped per strategy; pullback and breakout are never combined.
    WLA-04: 'Industry momentum' is always one of the 6 rows in a non-suppressed strategy.
    WLA-05: bucket < WL_MIN_BUCKET → suppressed; total < WL_MIN_TOTAL → aborted.
    WLA-06: WL_FEATURES is a pre-registered constant committed before results are viewed.
    """
    active = _active_trades(qualified_trades)
    total = len(active)

    if total < WL_MIN_TOTAL:
        return {
            "total_qualified": total,
            "aborted": True,
            "abort_reason": (
                f"Insufficient data — fewer than 200 qualified trades (n={total}). "
                "W/L analysis suppressed."
            ),
            "strategies": [],
        }

    sig_by_key = {(str(s.date), s.ticker, s.strategy): s for s in signals}
    strategies_result = []

    for strat in sorted(set(t.strategy for t in active)):
        strat_trades = [t for t in active if t.strategy == strat]
        winners = [t for t in strat_trades if t.r_multiple > 0]
        losers = [t for t in strat_trades if t.r_multiple <= 0]
        w_n = len(winners)
        l_n = len(losers)

        if w_n < WL_MIN_BUCKET or l_n < WL_MIN_BUCKET:
            strategies_result.append({
                "strategy": strat,
                "winner_n": w_n,
                "loser_n": l_n,
                "suppressed": True,
                "suppression_reason": (
                    f"Suppressed — fewer than 50 trades in winner or loser bucket "
                    f"(winners: {w_n}, losers: {l_n})."
                ),
                "rows": [],
            })
            continue

        rows = []
        for metric in WL_FEATURES:
            w_vals = _extract_wl_metric(metric, winners, sig_by_key)
            l_vals = _extract_wl_metric(metric, losers, sig_by_key)
            w_med = _safe_median(w_vals)
            l_med = _safe_median(l_vals)
            delta = round(w_med - l_med, 4) if (w_med is not None and l_med is not None) else None
            rows.append({
                "metric": metric,
                "winners_median": round(w_med, 4) if w_med is not None else None,
                "losers_median": round(l_med, 4) if l_med is not None else None,
                "delta": delta,
            })

        strategies_result.append({
            "strategy": strat,
            "winner_n": w_n,
            "loser_n": l_n,
            "suppressed": False,
            "suppression_reason": None,
            "rows": rows,
        })

    return {
        "total_qualified": total,
        "aborted": False,
        "abort_reason": None,
        "strategies": strategies_result,
    }


# ── E8.1 — Core metrics ───────────────────────────────────────────────────────

def compute_metrics(trades: list[Trade]) -> dict:
    """Compute headline metrics from a list of simulated trades.

    Only qualified trades with a real R contribute to win-rate, expectancy, etc.
    Gap-skips and incomplete trades are counted separately.
    """
    active = _active_trades(trades)
    total = len(trades)

    if not active:
        return {
            "count": 0,
            "win_rate": None,
            "avg_win_r": None,
            "avg_loss_r": None,
            "expectancy_r": None,
            "median_holding_days": None,
            "exit_reason_breakdown": {},
            "max_drawdown_r": None,
            "ambiguous_bar_pct": 0.0,
            "gap_skip_pct": 0.0,
            "incomplete_pct": 0.0,
        }

    wins = [t for t in active if t.r_multiple > 0]
    losses = [t for t in active if t.r_multiple <= 0]

    avg_win = sum(t.r_multiple for t in wins) / len(wins) if wins else 0.0
    avg_loss = sum(t.r_multiple for t in losses) / len(losses) if losses else 0.0
    expectancy = sum(t.r_multiple for t in active) / len(active)

    holding = sorted(
        t.holding_days for t in active if t.holding_days is not None
    )
    if not holding:
        median_hold = None
    elif len(holding) % 2 == 1:
        median_hold = holding[len(holding) // 2]
    else:
        mid = len(holding) // 2
        median_hold = (holding[mid - 1] + holding[mid]) / 2

    exit_counts = Counter(t.exit_reason for t in trades if t.qualified)

    # Max drawdown of cumulative-R equity curve (calendar order)
    sorted_active = sorted(active, key=lambda t: t.exit_date or t.signal_date)
    cumr = 0.0
    peak = 0.0
    max_dd = 0.0
    for t in sorted_active:
        cumr += t.r_multiple
        peak = max(peak, cumr)
        max_dd = max(max_dd, peak - cumr)

    ambiguous = sum(1 for t in trades if t.flags.get("ambiguous_bar"))
    gap_skip = sum(1 for t in trades if t.flags.get("skipped_gap"))
    incomplete = sum(1 for t in trades if t.flags.get("incomplete"))

    return {
        "count": len(active),
        "win_rate": len(wins) / len(active),
        "avg_win_r": avg_win,
        "avg_loss_r": avg_loss,
        "expectancy_r": expectancy,
        "median_holding_days": median_hold,
        "exit_reason_breakdown": dict(exit_counts),
        "max_drawdown_r": max_dd,
        "ambiguous_bar_pct": ambiguous / total if total > 0 else 0.0,
        "gap_skip_pct": gap_skip / total if total > 0 else 0.0,
        "incomplete_pct": incomplete / total if total > 0 else 0.0,
    }


# ── E8.2 — Score & confidence buckets ────────────────────────────────────────

def _bucket_stats(trades: list[Trade]) -> dict:
    n = len(trades)
    if n == 0:
        return {"n": 0, "win_rate": None, "expectancy_r": None, "verdict": "insufficient n"}
    wins = sum(1 for t in trades if t.r_multiple > 0)
    exp = sum(t.r_multiple for t in trades) / n
    verdict = "insufficient n" if n < MIN_BUCKET_N else "ok"
    return {"n": n, "win_rate": wins / n, "expectancy_r": exp, "verdict": verdict}


def bucket_by_score(trades: list[Trade]) -> list[dict]:
    """E8.2 — break qualified trades into score buckets and compute metrics."""
    active = _active_trades(trades)
    result = []
    for lo, hi in SCORE_BUCKETS:
        label = f"{lo}–{min(hi, 100)}"
        bucket = [t for t in active if lo <= t.score <= hi]
        result.append({"bucket": label, **_bucket_stats(bucket)})
    return result


def bucket_by_confidence(trades: list[Trade]) -> list[dict]:
    """E8.2 — break qualified trades into confidence buckets."""
    active = _active_trades(trades)
    result = []
    for conf in CONF_LEVELS:
        bucket = [t for t in active if t.confidence == conf]
        result.append({"bucket": conf, **_bucket_stats(bucket)})
    return result


def _monotonic_verdict(buckets: list[dict]) -> str:
    """Check whether expectancy is monotonically increasing across valid buckets."""
    valid = [b for b in buckets if b["verdict"] == "ok" and b["expectancy_r"] is not None]
    if len(valid) < 2:
        return "insufficient data for verdict"
    exps = [b["expectancy_r"] for b in valid]
    if all(exps[i] <= exps[i + 1] for i in range(len(exps) - 1)):
        return "monotonically increasing"
    elif all(exps[i] >= exps[i + 1] for i in range(len(exps) - 1)):
        return "monotonically decreasing"
    return "non-monotonic"


# ── E8.3 — Gate attribution via near-misses ───────────────────────────────────

def gate_attribution(
    all_trades: list[Trade],
    qualified_expectancy: float,
) -> list[dict]:
    """Per-gate attribution: near-misses failing ONLY that gate vs qualified.

    Only trades with exactly one failed gate and a valid R contribute.
    n < 30 ⇒ 'insufficient n'; |delta| small ⇒ 'no measurable value in this sample'.
    """
    single_fail = [
        t for t in all_trades
        if not t.qualified
        and len(t.failed_gates) == 1
        and t.r_multiple is not None
    ]

    by_gate: dict[str, list[Trade]] = defaultdict(list)
    for t in single_fail:
        by_gate[t.failed_gates[0]].append(t)

    result = []
    for gate, gate_trades in sorted(by_gate.items()):
        n = len(gate_trades)
        exp = sum(t.r_multiple for t in gate_trades) / n if n > 0 else None
        delta = (exp - qualified_expectancy) if exp is not None else None

        if n < MIN_ATTRIBUTION_N:
            verdict = "insufficient n"
            recommendation = "insufficient_n"
        elif delta is not None and abs(delta) < 0.1:
            verdict = "no measurable value in this sample"
            recommendation = "cut"
        elif delta is not None and delta > 0:
            # Near-misses outperform qualified: gate blocks trades that would have
            # performed better — no protective value (may actively harm).
            verdict = "near-misses outperform qualified (gate may be blocking good setups)"
            recommendation = "cut"
        else:
            # delta <= -0.1: near-misses underperform qualified — gate correctly
            # identifies weaker setups that should not be taken.
            verdict = "near-misses underperform qualified (gate shows protective value)"
            recommendation = "keep"

        result.append({
            "gate": gate,
            "n": n,
            "expectancy_r": exp,
            "qualified_expectancy_r": qualified_expectancy,
            "delta_r": delta,
            "verdict": verdict,
            "recommendation": recommendation,
        })

    return result


# ── E13.1 — Failure analysis & target-distance bucketing ─────────────────────

def failure_analysis(trades: list[Trade]) -> dict:
    """Split non-winning qualified trades into stop_out vs time_stop."""
    active = _active_trades(trades)
    non_winners = [t for t in active if t.r_multiple <= 0]
    stop_out  = sum(1 for t in non_winners if t.exit_reason == "stop")
    time_stop = sum(1 for t in non_winners if t.exit_reason == "time_stop")
    other = len(non_winners) - stop_out - time_stop
    total = len(non_winners)

    if total == 0:
        interpretation = "No non-winning trades to analyze."
    else:
        ts_pct = time_stop / total
        so_pct = stop_out / total
        if ts_pct > 0.60:
            interpretation = (
                f"Time-stop dominated ({ts_pct:.0%}) — targets may be too far "
                "for the session horizon; consider tightening target distance."
            )
        elif so_pct > 0.60:
            interpretation = (
                f"Stop-out dominated ({so_pct:.0%}) — setups are breaking down; "
                "the issue is setup quality rather than target distance."
            )
        else:
            interpretation = (
                "Mixed breakdown — price reversal and time horizon contribute "
                "roughly equally to non-winning outcomes."
            )

    return {
        "total_non_winners": total,
        "stop_out":  stop_out,
        "time_stop": time_stop,
        "other":     other,
        "interpretation": interpretation,
    }


_TARGET_R_BUCKETS = [
    (1.0, 1.5, "1.0–1.5×R"),
    (1.5, 2.0, "1.5–2.0×R"),
    (2.0, 2.5, "2.0–2.5×R"),
    (2.5, 3.0, "2.5–3.0×R"),
    (3.0, float("inf"), "3.0+×R"),
]

_TARGET_ATR_BUCKETS = [
    (0.0, 1.0, "<1.0 ATR"),
    (1.0, 1.5, "1.0–1.5 ATR"),
    (1.5, 2.0, "1.5–2.0 ATR"),
    (2.0, 2.5, "2.0–2.5 ATR"),
    (2.5, float("inf"), "2.5+ ATR"),
]


def _target_bucket_stats(trades: list[Trade]) -> dict:
    n = len(trades)
    if n == 0:
        return {"n": 0, "hit_rate": None, "expectancy_r": None}
    hits = [t for t in trades if t.exit_reason == "target"]
    hit_rate = len(hits) / n
    expectancy = sum(t.r_multiple for t in trades) / n
    return {"n": n, "hit_rate": hit_rate, "expectancy_r": expectancy}


def bucket_by_target_r(trades: list[Trade]) -> list[dict]:
    """E13.1 — break qualified trades into target-R-distance buckets."""
    active = _active_trades(trades)
    result = []
    for lo, hi, label in _TARGET_R_BUCKETS:
        bucket = [t for t in active if t.target_r is not None and lo <= t.target_r < hi]
        result.append({"bucket": label, **_target_bucket_stats(bucket)})
    return result


def bucket_by_target_atr(trades: list[Trade]) -> list[dict]:
    """E13.1 — break qualified trades into target-ATR-distance buckets."""
    active = _active_trades(trades)
    result = []
    for lo, hi, label in _TARGET_ATR_BUCKETS:
        bucket = [t for t in active if t.target_atr is not None and lo <= t.target_atr < hi]
        result.append({"bucket": label, **_target_bucket_stats(bucket)})
    return result


# ── E14.1 — Stop-out forensics ───────────────────────────────────────────────

def stop_out_forensics(trades: list[Trade]) -> dict:
    """MAE/MFE distribution and post-stop path analysis for stop-outs.

    Branch A (stops too tight): high % of stop-outs that later reach target
    AND winners clustered near −1R MAE → stops sit at the noise boundary.
    Branch B (setup lacks edge): stopped trades keep falling; low reach rate.
    """
    active = _active_trades(trades)
    stop_outs = [t for t in active if t.exit_reason == "stop"]
    winners   = [t for t in active if t.r_multiple > 0]

    n_stop_outs = len(stop_outs)

    if n_stop_outs == 0:
        return {
            "n_stop_outs": 0,
            "pct_reached_target": None,
            "median_post_stop_mfe_r": None,
            "winners_mae_near_minus1_pct": None,
            "branch": None,
            "interpretation": "No stop-out trades to analyze.",
        }

    # Post-stop reach rate (trades with the field populated)
    with_post = [t for t in stop_outs if t.post_stop_reached_target is not None]
    n_reached = sum(1 for t in with_post if t.post_stop_reached_target)
    pct_reached = n_reached / len(with_post) if with_post else None

    # Median post-stop MFE
    post_mfes = sorted(t.post_stop_mfe_r for t in stop_outs if t.post_stop_mfe_r is not None)
    median_post_mfe = post_mfes[len(post_mfes) // 2] if post_mfes else None

    # Winners whose MAE came within 0.25R of the stop (mae_r ≤ −0.75)
    winners_with_mae = [t for t in winners if t.mae_r is not None]
    n_near = sum(1 for t in winners_with_mae if t.mae_r <= -0.75)
    near_minus1_pct = n_near / len(winners_with_mae) if winners_with_mae else None

    # Branch determination
    if pct_reached is not None and near_minus1_pct is not None:
        if pct_reached > 0.35 and near_minus1_pct > 0.30:
            branch = "A"
            mfe_str = f"{median_post_mfe:+.2f}R" if median_post_mfe is not None else "unknown"
            interpretation = (
                f"{pct_reached:.0%} of stopped trades subsequently reached target "
                f"(post-stop MFE median {mfe_str}) and {near_minus1_pct:.0%} of winners "
                "had MAE within 0.25R of the stop — consistent with stops sitting at "
                "the noise boundary (Branch A: stops too tight → consider widening)."
            )
        else:
            branch = "B"
            mfe_str = f"{median_post_mfe:+.2f}R" if median_post_mfe is not None else "unknown"
            interpretation = (
                f"{pct_reached:.0%} of stopped trades subsequently reached target "
                f"(post-stop MFE median {mfe_str}) — stopped trades continued lower, "
                "consistent with genuine breakdown (Branch B: setups may lack edge at "
                "the current stop level → evaluate entry quality via E14.3/E14.4)."
            )
    else:
        branch = None
        interpretation = (
            "Insufficient data — run a backtest with re-simulated trades to populate "
            "MAE/MFE fields."
        )

    return {
        "n_stop_outs": n_stop_outs,
        "pct_reached_target": pct_reached,
        "median_post_stop_mfe_r": median_post_mfe,
        "winners_mae_near_minus1_pct": near_minus1_pct,
        "branch": branch,
        "interpretation": interpretation,
    }


# ── Monthly signal count helper ───────────────────────────────────────────────

def _monthly_signal_counts(signals: list[Signal]) -> dict[str, int]:
    counts: Counter = Counter()
    for s in signals:
        if s.qualified:
            month_key = s.date.strftime("%Y-%m")
            counts[month_key] += 1
    return dict(sorted(counts.items()))


# ── E6.2 / E8.1 — Render report ──────────────────────────────────────────────

def render_report(
    signals: list[Signal],
    qualified_trades: list[Trade],
    near_miss_trades: Optional[list[Trade]] = None,
    run_meta: Optional[dict] = None,
) -> tuple[str, dict]:
    """Render report.md and report.json for a completed backtest run.

    Headline metrics use only qualified_trades. Near-miss trades are used
    for gate attribution only and do NOT enter the headline numbers.
    """
    near_miss_trades = near_miss_trades or []
    all_trades = qualified_trades + near_miss_trades

    metrics = compute_metrics(qualified_trades)
    score_buckets = bucket_by_score(qualified_trades)
    conf_buckets = bucket_by_confidence(qualified_trades)
    monthly = _monthly_signal_counts(signals)

    q_exp = metrics.get("expectancy_r") or 0.0
    attribution = gate_attribution(all_trades, q_exp)
    wl_result = wl_characteristic_analysis(signals, qualified_trades)

    # Ambiguous-bar warning (E7.1 spec: >15% triggers warning)
    amb_pct = metrics.get("ambiguous_bar_pct", 0.0)
    amb_warning = (
        f"\n> **Warning:** {amb_pct:.1%} of trade bars are ambiguous (Low ≤ stop and "
        "High ≥ target on the same bar). Daily bars are too coarse for this stop "
        "distance; R figures may be overstated.\n"
        if amb_pct > 0.15 else ""
    )

    # ── Markdown ──────────────────────────────────────────────────────────────
    lines = ["# Backtest Report\n"]

    if run_meta:
        lines += [
            "## Run Parameters\n",
            f"- Strategy: {run_meta.get('strategy', '?')}",
            f"- Universe: {run_meta.get('universe_size', '?')} tickers",
            f"- Date range: {run_meta.get('start', '?')} → {run_meta.get('end', '?')}",
            f"- Earnings gate: {run_meta.get('earnings_gate', '?')}",
            f"- Time stop: {run_meta.get('time_stop', '?')} sessions",
            f"- Entry: {run_meta.get('entry', '?')}",
            f"- Git hash: {run_meta.get('git_hash', 'unknown')}",
            "",
        ]

    lines += ["## Summary Metrics\n"]
    if metrics["count"] == 0:
        lines.append("*No qualifying trades in this run.*\n")
    else:
        lines += [
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Trades | {metrics['count']} |",
            f"| Win rate | {metrics['win_rate']:.1%} |" if metrics["win_rate"] is not None else "| Win rate | — |",
            f"| Avg win (R) | {metrics['avg_win_r']:.2f} |" if metrics["avg_win_r"] is not None else "| Avg win (R) | — |",
            f"| Avg loss (R) | {metrics['avg_loss_r']:.2f} |" if metrics["avg_loss_r"] is not None else "| Avg loss (R) | — |",
            f"| Expectancy (R) | {metrics['expectancy_r']:.3f} |" if metrics["expectancy_r"] is not None else "| Expectancy (R) | — |",
            f"| Median hold (days) | {metrics['median_holding_days']} |",
            f"| Max drawdown (R) | {metrics['max_drawdown_r']:.2f} |" if metrics["max_drawdown_r"] is not None else "| Max drawdown (R) | — |",
            "",
        ]

    if amb_warning:
        lines.append(amb_warning)

    lines += ["\n## Score Buckets (qualified trades only)\n"]
    lines += ["| Score range | n | Win rate | Expectancy (R) | Verdict |",
              "|-------------|---|----------|----------------|---------|"]
    for b in score_buckets:
        wr = f"{b['win_rate']:.1%}" if b["win_rate"] is not None else "—"
        exp = f"{b['expectancy_r']:.3f}" if b["expectancy_r"] is not None else "—"
        lines.append(f"| {b['bucket']} | {b['n']} | {wr} | {exp} | {b['verdict']} |")
    lines.append(f"\n*Score bucket verdict: {_monotonic_verdict(score_buckets)}*\n")

    lines += ["\n## Confidence Buckets (qualified trades only)\n"]
    lines += ["| Confidence | n | Win rate | Expectancy (R) | Verdict |",
              "|------------|---|----------|----------------|---------|"]
    for b in conf_buckets:
        wr = f"{b['win_rate']:.1%}" if b["win_rate"] is not None else "—"
        exp = f"{b['expectancy_r']:.3f}" if b["expectancy_r"] is not None else "—"
        lines.append(f"| {b['bucket']} | {b['n']} | {wr} | {exp} | {b['verdict']} |")
    lines.append(f"\n*Confidence bucket verdict: {_monotonic_verdict(conf_buckets)}*\n")

    lines += ["\n## Monthly Signal Counts (qualified)\n"]
    if monthly:
        lines += ["| Month | Signals |", "|-------|---------|"]
        for month, cnt in monthly.items():
            lines.append(f"| {month} | {cnt} |")
    else:
        lines.append("*No monthly data.*")
    lines.append("")

    lines += ["\n## Exit Reason Breakdown\n"]
    er = metrics.get("exit_reason_breakdown", {})
    if er:
        lines += ["| Reason | Count |", "|--------|-------|"]
        for reason, cnt in sorted(er.items(), key=lambda x: -x[1]):
            lines.append(f"| {reason} | {cnt} |")
    lines.append("")

    # E13.1 — failure breakdown
    fa = failure_analysis(qualified_trades)
    if fa["total_non_winners"] > 0:
        lines += ["\n## Non-winner Analysis\n"]
        lines += [
            f"| Failure mode | Count | % |",
            f"|--------------|-------|---|",
            f"| Stop-out | {fa['stop_out']} | {fa['stop_out']/fa['total_non_winners']:.0%} |",
            f"| Time-stop | {fa['time_stop']} | {fa['time_stop']/fa['total_non_winners']:.0%} |",
        ]
        if fa["other"]:
            lines.append(f"| Other | {fa['other']} | {fa['other']/fa['total_non_winners']:.0%} |")
        lines.append(f"\n*{fa['interpretation']}*\n")

    # E14.1 — stop-out forensics
    sof = stop_out_forensics(qualified_trades)
    if sof["n_stop_outs"] > 0:
        lines += ["\n## Stop-out Forensics\n"]
        lines += [
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Stop-outs | {sof['n_stop_outs']} |",
        ]
        if sof["pct_reached_target"] is not None:
            lines.append(f"| % reached target post-stop | {sof['pct_reached_target']:.0%} |")
        if sof["median_post_stop_mfe_r"] is not None:
            lines.append(f"| Median post-stop MFE | {sof['median_post_stop_mfe_r']:+.2f}R |")
        if sof["winners_mae_near_minus1_pct"] is not None:
            lines.append(f"| Winners' MAE near −1R (≤ −0.75) | {sof['winners_mae_near_minus1_pct']:.0%} |")
        branch_label = f"Branch {sof['branch']}" if sof["branch"] else "Undetermined"
        lines += [
            f"\n**{branch_label}** — {sof['interpretation']}\n",
        ]

    # E13.1 — target distance
    tr_buckets = bucket_by_target_r(qualified_trades)
    ta_buckets = bucket_by_target_atr(qualified_trades)

    if any(b["n"] > 0 for b in tr_buckets):
        lines += ["\n## Target Distance Analysis — by R-multiple\n"]
        lines += ["| Distance | n | Hit rate | E(R) |", "|----------|---|----------|------|"]
        for b in tr_buckets:
            hr = f"{b['hit_rate']:.0%}" if b["hit_rate"] is not None else "—"
            ex = f"{b['expectancy_r']:.3f}" if b["expectancy_r"] is not None else "—"
            lines.append(f"| {b['bucket']} | {b['n']} | {hr} | {ex} |")
        lines.append("")

    if any(b["n"] > 0 for b in ta_buckets):
        lines += ["\n## Target Distance Analysis — by ATR multiple\n"]
        lines += ["| Distance | n | Hit rate | E(R) |", "|----------|---|----------|------|"]
        for b in ta_buckets:
            hr = f"{b['hit_rate']:.0%}" if b["hit_rate"] is not None else "—"
            ex = f"{b['expectancy_r']:.3f}" if b["expectancy_r"] is not None else "—"
            lines.append(f"| {b['bucket']} | {b['n']} | {hr} | {ex} |")
        lines.append("")

    # Phase 4 — W/L characteristic analysis section
    lines += ["\n## Winner/Loser Characteristic Analysis (Pre-registered)\n"]
    if wl_result['aborted']:
        lines.append(f"> **Warning:** {wl_result['abort_reason']}")
    else:
        for s in wl_result['strategies']:
            if s['suppressed']:
                lines += [f"\n### {s['strategy'].title()}\n"]
                lines.append(f"> **Warning:** {s['suppression_reason']}")
            else:
                lines += [
                    f"\n### {s['strategy'].title()} "
                    f"(winners: {s['winner_n']}, losers: {s['loser_n']})\n"
                ]
                lines += [
                    "| Metric | Winners | Losers | Delta |",
                    "|--------|---------|--------|-------|",
                ]
                for row in s['rows']:
                    w_fmt = _fmt_wl_value(row['metric'], row['winners_median'])
                    l_fmt = _fmt_wl_value(row['metric'], row['losers_median'])
                    d_fmt = _fmt_wl_delta(row['metric'], row['delta'])
                    lines.append(f"| {row['metric']} | {w_fmt} | {l_fmt} | {d_fmt} |")
                lines.append("")
    lines.append("")

    if attribution:
        lines += ["\n## Gate Attribution (near-miss analysis)\n"]
        lines += [
            "| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Recommendation | Verdict |",
            "|------|---------------|----------------|----------------|------|----------------|---------|",
        ]
        for a in attribution:
            exp = f"{a['expectancy_r']:.3f}" if a["expectancy_r"] is not None else "—"
            qexp = f"{a['qualified_expectancy_r']:.3f}" if a["qualified_expectancy_r"] is not None else "—"
            delta = f"{a['delta_r']:.3f}" if a["delta_r"] is not None else "—"
            rec = a["recommendation"].upper().replace("_", "-")
            lines.append(
                f"| {a['gate']} | {a['n']} | {exp} | {qexp} | {delta} | **{rec}** | {a['verdict']} |"
            )
        lines.append("")

    # ── E6.3 Bias disclosure ──────────────────────────────────────────────────
    lines += ["\n## Known Biases\n", _BIAS_SURVIVORSHIP, "", _BIAS_LOOK_AHEAD, ""]

    gap_skip_pct = metrics.get("gap_skip_pct", 0.0)
    earn_skip_n = sum(
        1 for t in all_trades
        if "Earnings clear" in (t.failed_gates or [])
    )
    earn_skip_pct = earn_skip_n / len(signals) if signals else 0.0
    lines.append(
        f"**Earnings gate skip rate** — {earn_skip_pct:.1%} of signals failed the "
        "earnings-proximity gate (earnings within 7 days of entry)."
    )
    lines.append(
        f"\n**Gap-skip rate** — {gap_skip_pct:.1%} of simulated entries were skipped "
        "due to the opening price being outside the stop/target range."
    )
    lines.append("")

    md = "\n".join(lines)

    # ── Trade list ────────────────────────────────────────────────────────────
    # Map (signal_date_str, ticker, strategy) → Signal so each Trade can pull stop/target
    sig_by_key = {(str(s.date), s.ticker, s.strategy): s for s in signals}
    trades_list = []
    for t in qualified_trades:
        if t.exit_reason == "incomplete":
            continue
        sig = sig_by_key.get((str(t.signal_date), t.ticker, t.strategy))
        trades_list.append({
            "ticker":       t.ticker,
            "signal_date":  str(t.signal_date),
            "entry_date":   str(t.entry_date)  if t.entry_date  else None,
            "exit_date":    str(t.exit_date)   if t.exit_date   else None,
            "exit_reason":  t.exit_reason,
            "stop":         sig.stop   if sig else None,
            "target":       sig.target if sig else None,
            "entry_px":     t.entry_px,
            "exit_px":      t.exit_px,
            "r_multiple":   round(t.r_multiple, 3) if t.r_multiple is not None else None,
            "holding_days": t.holding_days,
            "strategy":     t.strategy,
            "confidence":   t.confidence,
            "score":        t.score,
        })
    trades_list.sort(key=lambda x: x.get("entry_date") or x.get("signal_date") or "")

    # ── JSON ──────────────────────────────────────────────────────────────────
    json_out = {
        "metrics": metrics,
        "score_buckets": score_buckets,
        "conf_buckets": conf_buckets,
        "monthly_signals": monthly,
        "gate_attribution": attribution,
        "failure_analysis": fa,
        "stop_out_forensics": sof,
        "target_r_buckets": tr_buckets,
        "target_atr_buckets": ta_buckets,
        "wl_analysis": wl_result,
        "biases": [_BIAS_SURVIVORSHIP, _BIAS_LOOK_AHEAD],
        "run_meta": run_meta or {},
        "trades": trades_list,
    }

    return md, json_out
