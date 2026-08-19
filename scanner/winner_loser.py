"""Winner/loser feature analysis with train/holdout separation.

Answers "which entry-time signal features separate winners from losers?" for
one backtest run_id, read-only against data/scanner.db. No re-backtest, no
model fitting — single-feature threshold rules only, selected on a TRAIN
window and scored UNCHANGED on a HOLDOUT window so a finding has to survive
data that played no part in discovering it.

Train  = signals dated <  --split  (selection window)
Holdout= signals dated >= --split  (confirmation window, touched once)

Promoted from the throwaway prototype at
.planning/quick/260819-jjh-add-winner-loser-split-py-diagnostic-cli/260819-jjh-PROTOTYPE.py
(2026-08-19) — see that task directory for the original run and findings.
See seasonality.py + seasonality_by_week.py for the logic/CLI split this
module mirrors: no argparse, no printing here (CLI at winner_loser_split.py).
"""
from __future__ import annotations

import statistics
from typing import Any, Optional

from scanner import store_db

# LOCKED (D-05): confidence arrives from the DB as a text label; this is the
# only categorical->numeric mapping the analysis performs.
_CONF_LEVELS = {"LOW": 0.0, "MEDIUM": 1.0, "HIGH": 2.0}

# The prototype's original eight features, in the prototype's order.
LEGACY_FEATURES = (
    "score", "confidence", "atr_pct", "close", "target_r", "target_atr",
    "industry_momentum", "industry_rank_pct",
)

# Landed in quick task 260819-gv9 (schema v10). Absent from the live database
# until its lazy migration fires — get_analysis_signals reports them skipped
# with a distinct "column absent" reason rather than "too few non-null".
V10_FEATURES = ("rsi_entry", "rvol", "pullback_depth_pct", "pct_to_52w_high")

# Twelve features total (D-04). Note: industry_above_50ma is deliberately
# categorical-only (see the categorical breakdown section) and is NOT a
# threshold feature here — that matches the prototype and must not drift.
FEATURES = LEGACY_FEATURES + V10_FEATURES


def num(value: Any) -> Optional[float]:
    """Coerce to float; None for anything non-floatable (confidence arrives
    from the DB as a text label, not a number)."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def load_records(
    conn, run_id: str, strategy: Optional[str] = None
) -> tuple[list[dict], set[str]]:
    """Load and shape signal rows for one run_id into analysis records.

    Reproduces the prototype's record shaping exactly: a record is dropped
    when close is falsy/non-positive or atr is None (the falsy test is
    intentional — it rejects 0.0 and None alike, not just None).
    atr_pct = atr / close * 100. confidence is mapped through _CONF_LEVELS;
    conf_label retains the raw text for the categorical section. The four
    v10 features are coerced through num() like every other numeric feature.

    Raises ValueError naming the run_id and the db path when the query
    yields no usable records.
    """
    rows, missing_columns = store_db.get_analysis_signals(conn, run_id, strategy=strategy)

    records: list[dict] = []
    for row in rows:
        close, atr = num(row["close"]), num(row["atr"])
        if not close or close <= 0 or atr is None:
            continue
        records.append({
            "date": row["date"],
            "ticker": row["ticker"],
            "r": float(row["r_multiple"]),
            "score": num(row["score"]),
            "confidence": _CONF_LEVELS.get(row["confidence"]),
            "conf_label": row["confidence"],
            "atr_pct": atr / close * 100,
            "close": close,
            "target_r": num(row["target_r"]),
            "target_atr": num(row["target_atr"]),
            "industry_momentum": num(row["industry_momentum"]),
            "industry_above_50ma": num(row["industry_above_50ma"]),
            "industry_rank_pct": num(row["industry_rank_pct"]),
            "rsi_entry": num(row["rsi_entry"]),
            "rvol": num(row["rvol"]),
            "pullback_depth_pct": num(row["pullback_depth_pct"]),
            "pct_to_52w_high": num(row["pct_to_52w_high"]),
        })

    if not records:
        raise ValueError(
            f"No usable records for run_id={run_id!r} (qualified, resolved, "
            f"close>0, atr not null) — checked against the database opened "
            f"for this connection."
        )

    return records, missing_columns


def split_records(records: list[dict], split: str) -> tuple[list[dict], list[dict]]:
    """Split records into (train, holdout) on a YYYY-MM-DD date boundary.

    A record dated strictly before `split` is train; a record dated on or
    after `split` is holdout (D-06, prototype's `>=`) — a trade dated exactly
    on the boundary belongs to the HOLDOUT. Compares on the first ten
    characters of the stored date string so a stored timestamp (e.g. an
    ISO datetime with a time component) cannot change the classification.
    """
    if len(split) != 10 or split[4] != "-" or split[7] != "-":
        raise ValueError(f"--split must be YYYY-MM-DD, got {split!r}")
    try:
        year, month, day = split[:4], split[5:7], split[8:10]
        if not (year.isdigit() and month.isdigit() and day.isdigit()):
            raise ValueError
    except ValueError:
        raise ValueError(f"--split must be YYYY-MM-DD, got {split!r}") from None

    train = [r for r in records if r["date"][:10] < split]
    holdout = [r for r in records if r["date"][:10] >= split]
    return train, holdout


def mean_r(records: list[dict]) -> float:
    """Mean r_multiple over a record list; pure-python statistics.mean (not
    numpy) — this is what the prototype's published numbers were produced by."""
    return statistics.mean([r["r"] for r in records]) if records else float("nan")
