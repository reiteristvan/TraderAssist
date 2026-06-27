"""E14.4 — Loser post-mortem and hypothesis-driven dimension analysis.

Usage (typically via scan.py postmortem):
  1. enrich_trades()    — compute SPY regime, dist-above-20MA, RS per trade
  2. loser_postmortem() — find worst N stop-outs; compare vs full population
  3. dimension_analysis() — bucket ALL trades by candidate dimensions; no gates
  4. render_postmortem() — produce markdown report (AC1 + AC2)
"""
from __future__ import annotations

from typing import Callable, Optional

import pandas as pd

from scanner.simulate import Signal, Trade


# ── Dimension helpers ─────────────────────────────────────────────────────────

def _spy_regime_at(spy_close: pd.Series, as_of: pd.Timestamp) -> str:
    sliced = spy_close[spy_close.index <= as_of]
    if len(sliced) < 50:
        return "UNKNOWN"
    sma50 = float(sliced.rolling(50).mean().iloc[-1])
    ema20 = float(sliced.ewm(span=20).mean().iloc[-1])
    price = float(sliced.iloc[-1])
    if price > sma50 and price > ema20:
        return "BULLISH"
    elif price < sma50 and price < ema20:
        return "BEARISH"
    return "NEUTRAL"


def _dist_above_20ma(sma20_series: pd.Series, close_series: pd.Series,
                     as_of: pd.Timestamp) -> Optional[float]:
    """(close − SMA20) / SMA20 × 100 at as_of, or None if insufficient data."""
    sma20 = sma20_series.asof(as_of)
    close = close_series.asof(as_of)
    if pd.isna(sma20) or pd.isna(close) or sma20 == 0:
        return None
    return float((close - sma20) / sma20 * 100.0)


# ── Trade enrichment ──────────────────────────────────────────────────────────

def enrich_trades(
    trades: list[Trade],
    signals: list[Signal],
    get_history: Callable[[str], Optional[pd.DataFrame]],
    spy_bars: Optional[pd.DataFrame] = None,
) -> list[dict]:
    """Add computed dimensions to each qualified trade for post-mortem analysis.

    Computed dimensions per trade:
    - spy_regime     : BULLISH / NEUTRAL / BEARISH / UNKNOWN at signal_date
    - dist_above_20ma: (close − SMA20) / SMA20 × 100 at signal_date
    - rs_strength    : 60-day RS ratio vs SPY at signal_date

    Returns list of dicts — each Trade's fields plus the three dimensions.
    """
    from scanner.backtest import _precompute_bars

    sig_map = {(str(s.date), s.ticker): s for s in signals}
    spy_close = spy_bars["Close"] if spy_bars is not None else pd.Series(dtype=float)

    tickers = {t.ticker for t in trades if t.qualified and t.r_multiple is not None}
    print(f"  Loading OHLCV for {len(tickers)} ticker(s) to enrich trades…")

    precomp_cache: dict[str, object] = {}
    close_cache: dict[str, pd.Series] = {}
    for ticker in sorted(tickers):
        df = get_history(ticker)
        if df is not None:
            close_cache[ticker] = df["Close"]
            precomp_cache[ticker] = _precompute_bars(df, spy_bars)

    enriched = []
    for t in trades:
        if not t.qualified or t.r_multiple is None:
            continue
        sig = sig_map.get((str(t.signal_date), t.ticker))
        as_of_ts = pd.Timestamp(t.signal_date)
        precomp = precomp_cache.get(t.ticker)
        close_s = close_cache.get(t.ticker)

        spy_regime = _spy_regime_at(spy_close, as_of_ts) if len(spy_close) > 0 else "UNKNOWN"

        dist_20ma = None
        if precomp is not None and close_s is not None:
            dist_20ma = _dist_above_20ma(precomp.sma20, close_s, as_of_ts)

        rs = None
        if precomp is not None:
            v = precomp.rs_strength.asof(as_of_ts)
            if pd.notna(v):
                rs = round(float(v), 3)

        enriched.append({
            "ticker":             t.ticker,
            "signal_date":        t.signal_date,
            "exit_reason":        t.exit_reason,
            "r_multiple":         t.r_multiple,
            "score":              t.score,
            "confidence":         t.confidence,
            "close":              sig.close if sig else None,
            "spy_regime":         spy_regime,
            "dist_above_20ma":    round(dist_20ma, 2) if dist_20ma is not None else None,
            "rs_strength":        rs,
        })

    return enriched


# ── Post-mortem ───────────────────────────────────────────────────────────────

_DIST_BUCKETS = [("<2%", -999, 2.0), ("2–5%", 2.0, 5.0), ("5–8%", 5.0, 8.0), (">8%", 8.0, 999)]
_RS_BUCKETS   = [("<0.95", 0, 0.95), ("0.95–1.05", 0.95, 1.05), (">1.05", 1.05, 99)]


def _bucket_stats(rows: list[dict], overall_stop_rate: float = 0.0) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0, "expectancy_r": None, "stop_rate": None}
    exp = sum(r["r_multiple"] for r in rows) / n
    stop_rate = sum(1 for r in rows if r["exit_reason"] == "stop") / n
    return {
        "n":           n,
        "expectancy_r": round(exp, 3),
        "stop_rate":   round(stop_rate, 3),
        "stop_rate_vs_overall": round(stop_rate - overall_stop_rate, 3),
    }


def loser_postmortem(enriched: list[dict], n: int = 25) -> dict:
    """Find the N most-concerning stop-outs and compare their dimension distribution
    against the full qualified-trade population.

    "Most concerning" = highest score that still stopped out (the high-confidence
    failures expose the most about what the strategy misses).  All stop-outs carry
    exactly -1R for a fixed-stop strategy, so r_multiple is not a useful sort key.

    Returns a dict used by render_postmortem() to produce the written note (AC1).
    """
    _CONF_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, None: 3}
    stop_outs = sorted(
        [r for r in enriched if r["exit_reason"] == "stop"],
        key=lambda r: (_CONF_ORDER.get(r.get("confidence"), 3), -(r.get("score") or 0)),
    )
    worst = stop_outs[:n]

    def _freq_table(rows: list[dict], key: str, values: list) -> dict[str, float]:
        valid = [r for r in rows if r.get(key) is not None]
        total = len(valid) or 1
        return {v: sum(1 for r in valid if r[key] == v) / total for v in values}

    def _dist_table(rows: list[dict]) -> dict[str, float]:
        valid = [r for r in rows if r.get("dist_above_20ma") is not None]
        total = len(valid) or 1
        return {
            label: sum(1 for r in valid if lo <= r["dist_above_20ma"] < hi) / total
            for label, lo, hi in _DIST_BUCKETS
        }

    return {
        "n_worst":     len(worst),
        "n_total":     len(enriched),
        "n_stop_outs": len(stop_outs),
        "worst_trades": worst,
        "spy_regime": {
            "all":   _freq_table(enriched, "spy_regime", ["BULLISH", "NEUTRAL", "BEARISH"]),
            "worst": _freq_table(worst,    "spy_regime", ["BULLISH", "NEUTRAL", "BEARISH"]),
        },
        "dist_20ma": {
            "all":   _dist_table(enriched),
            "worst": _dist_table(worst),
        },
        "rs_strength": {
            "all":   _freq_table(enriched, "rs_strength_bucket", []),  # computed below
            "worst": _freq_table(worst,    "rs_strength_bucket", []),
        },
    }


# ── Dimension analysis (AC2) ──────────────────────────────────────────────────

def dimension_analysis(enriched: list[dict], qualified_exp: float) -> dict:
    """Bucket ALL qualified trades by each candidate dimension and compute
    expectancy and stop-out rate per bucket.  NO gate applied — observation only (AC2).

    Returns a nested dict: dimension → bucket_label → {n, expectancy_r, delta_r,
                                                         stop_rate, stop_rate_vs_overall}.
    """
    results: dict[str, dict] = {}
    overall_stop_rate = (
        sum(1 for r in enriched if r["exit_reason"] == "stop") / len(enriched)
        if enriched else 0.0
    )

    # 1. SPY regime
    for regime in ("BULLISH", "NEUTRAL", "BEARISH", "UNKNOWN"):
        bucket = [r for r in enriched if r.get("spy_regime") == regime]
        if bucket:
            stats = _bucket_stats(bucket, overall_stop_rate)
            stats["delta_r"] = round(stats["expectancy_r"] - qualified_exp, 3)
            results.setdefault("spy_regime", {})[regime] = stats

    # 2. Distance above 20-MA
    valid_dist = [r for r in enriched if r.get("dist_above_20ma") is not None]
    for label, lo, hi in _DIST_BUCKETS:
        bucket = [r for r in valid_dist if lo <= r["dist_above_20ma"] < hi]
        if bucket:
            stats = _bucket_stats(bucket, overall_stop_rate)
            stats["delta_r"] = round(stats["expectancy_r"] - qualified_exp, 3)
            results.setdefault("dist_above_20ma", {})[label] = stats

    # 3. RS strength vs SPY
    valid_rs = [r for r in enriched if r.get("rs_strength") is not None]
    for label, lo, hi in _RS_BUCKETS:
        bucket = [r for r in valid_rs if lo <= r["rs_strength"] < hi]
        if bucket:
            stats = _bucket_stats(bucket, overall_stop_rate)
            stats["delta_r"] = round(stats["expectancy_r"] - qualified_exp, 3)
            results.setdefault("rs_strength", {})[label] = stats

    return results


# ── Report rendering ──────────────────────────────────────────────────────────

def render_postmortem(
    pm: dict,
    dim: dict,
    qualified_exp: float,
    run_label: str = "",
) -> str:
    """Produce the E14.4 post-mortem markdown (AC1 + AC2)."""
    worst   = pm["worst_trades"]
    n_worst = pm["n_worst"]
    n_total = pm["n_total"]
    n_so    = pm["n_stop_outs"]
    lines   = [f"# E14.4 — Loser Post-Mortem{f' ({run_label})' if run_label else ''}\n"]

    lines += [
        f"**Baseline:** {n_total} qualified trades | "
        f"{n_so} stop-outs | "
        f"overall E(R) = {qualified_exp:+.3f}R\n",
    ]

    # ── Worst N stop-outs ─────────────────────────────────────────────────────
    lines += [
        f"\n## {n_worst} High-Confidence Stop-outs (sorted by conf → score DESC)\n",
        "_All fixed-stop exits carry exactly -1R; 'worst' here means highest-confidence setups"
        " that still failed — the cases most informative about what the strategy misses._\n",
    ]
    lines += ["| # | Ticker | Date | Conf | Score | Regime | Dist 20MA | RS |",
              "|---|--------|------|------|-------|--------|-----------|-----|"]
    for i, r in enumerate(worst, 1):
        dist = f"{r['dist_above_20ma']:+.1f}%" if r.get("dist_above_20ma") is not None else "—"
        rs   = f"{r['rs_strength']:.3f}"       if r.get("rs_strength")     is not None else "—"
        conf = r.get("confidence") or "—"
        score = f"{r.get('score', 0):.0f}"
        lines.append(
            f"| {i} | {r['ticker']} | {r['signal_date']} | {conf} | {score} | "
            f"{r.get('spy_regime','—')} | {dist} | {rs} |"
        )
    lines.append("")

    # ── SPY regime: worst vs population ──────────────────────────────────────
    lines += ["\n## Pattern 1 — SPY Regime at Entry\n"]
    lines += ["| Regime | All trades | Worst stop-outs | Over-rep? |",
              "|--------|-----------|-----------------|-----------|"]
    for regime in ("BULLISH", "NEUTRAL", "BEARISH"):
        pall  = pm["spy_regime"]["all"].get(regime, 0)
        pworst = pm["spy_regime"]["worst"].get(regime, 0)
        ratio = pworst / pall if pall > 0 else float("nan")
        flag = "**YES**" if ratio > 1.5 else ("yes" if ratio > 1.2 else "—")
        lines.append(
            f"| {regime} | {pall:.0%} | {pworst:.0%} | {flag} |"
        )
    lines.append("")

    # ── Distance above 20-MA: worst vs population ─────────────────────────────
    lines += ["\n## Pattern 2 — Distance Above 20-MA at Entry\n"]
    lines += ["| Bucket | All trades | Worst stop-outs | Over-rep? |",
              "|--------|-----------|-----------------|-----------|"]
    for label, _, _ in _DIST_BUCKETS:
        pall   = pm["dist_20ma"]["all"].get(label, 0)
        pworst = pm["dist_20ma"]["worst"].get(label, 0)
        ratio  = pworst / pall if pall > 0 else float("nan")
        flag = "**YES**" if ratio > 1.5 else ("yes" if ratio > 1.2 else "—")
        lines.append(f"| {label} | {pall:.0%} | {pworst:.0%} | {flag} |")
    lines.append("")

    # ── Dimension analysis (AC2) ──────────────────────────────────────────────
    lines += ["\n## Dimension Analysis — Expectancy and Stop-out Rate by Bucket (no gate applied)\n"]

    for dim_name, buckets in dim.items():
        pretty = {
            "spy_regime":      "SPY Regime",
            "dist_above_20ma": "Distance Above 20-MA",
            "rs_strength":     "RS vs SPY",
        }.get(dim_name, dim_name)
        lines += [f"\n### {pretty}\n"]
        lines += [
            "| Bucket | n | E(R) | vs overall | Stop% | vs overall |",
            "|--------|---|------|-----------|-------|-----------|",
        ]
        for label, stats in buckets.items():
            exp   = f"{stats['expectancy_r']:+.3f}R"      if stats.get("expectancy_r") is not None else "—"
            delta = f"{stats['delta_r']:+.3f}R"           if stats.get("delta_r")      is not None else "—"
            sr    = f"{stats['stop_rate']:.0%}"           if stats.get("stop_rate")    is not None else "—"
            srd   = f"{stats['stop_rate_vs_overall']:+.0%}" if stats.get("stop_rate_vs_overall") is not None else "—"
            lines.append(f"| {label} | {stats['n']} | {exp} | {delta} | {sr} | {srd} |")
        lines.append("")

    return "\n".join(lines)
