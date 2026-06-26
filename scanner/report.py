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
    median_hold = holding[len(holding) // 2] if holding else None

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
        elif delta is not None and abs(delta) < 0.1:
            verdict = "no measurable value in this sample"
        elif delta is not None and delta > 0:
            verdict = "positive gate value (near-misses underperform qualified)"
        else:
            verdict = "questionable gate value (near-misses match or beat qualified)"

        result.append({
            "gate": gate,
            "n": n,
            "expectancy_r": exp,
            "qualified_expectancy_r": qualified_expectancy,
            "delta_r": delta,
            "verdict": verdict,
        })

    return result


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

    if attribution:
        lines += ["\n## Gate Attribution (near-miss analysis)\n"]
        lines += [
            "| Gate | n (near-miss) | Near-miss E(R) | Qualified E(R) | Δ(R) | Verdict |",
            "|------|---------------|----------------|----------------|------|---------|",
        ]
        for a in attribution:
            exp = f"{a['expectancy_r']:.3f}" if a["expectancy_r"] is not None else "—"
            qexp = f"{a['qualified_expectancy_r']:.3f}" if a["qualified_expectancy_r"] is not None else "—"
            delta = f"{a['delta_r']:.3f}" if a["delta_r"] is not None else "—"
            lines.append(
                f"| {a['gate']} | {a['n']} | {exp} | {qexp} | {delta} | {a['verdict']} |"
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
        f"**Earnings gate skip rate** — {earn_skip_pct:.1%} of signals had no earnings "
        "data and were evaluated without the earnings-proximity gate."
    )
    lines.append(
        f"\n**Gap-skip rate** — {gap_skip_pct:.1%} of simulated entries were skipped "
        "due to the opening price being outside the stop/target range."
    )
    lines.append("")

    md = "\n".join(lines)

    # ── Trade list ────────────────────────────────────────────────────────────
    # Map (signal_date_str, ticker) → Signal so each Trade can pull stop/target
    sig_by_key = {(str(s.date), s.ticker): s for s in signals}
    trades_list = []
    for t in qualified_trades:
        if t.exit_reason == "incomplete":
            continue
        sig = sig_by_key.get((str(t.signal_date), t.ticker))
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
        "biases": [_BIAS_SURVIVORSHIP, _BIAS_LOOK_AHEAD],
        "run_meta": run_meta or {},
        "trades": trades_list,
    }

    return md, json_out
