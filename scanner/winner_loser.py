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

import random
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

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


# ── month-block bootstrap ────────────────────────────────────────────────────

_MIN_BOOTSTRAP_RECORDS = 20


def _month_blocks(records: list[dict]) -> dict[str, list[float]]:
    by: dict[str, list[float]] = defaultdict(list)
    for x in records:
        by[x["date"][:7]].append(x["r"])
    return by


def bootstrap_ci(
    records: list[dict], rng: random.Random, iters: int = 2000
) -> tuple[float, float]:
    """Month-block percentile bootstrap 95% CI on mean R.

    Resamples whole calendar-month blocks with replacement — not per-trade
    resampling (D-05): dozens of trades fire the same day and share one
    market move, so a naive standard error is far too small. Returns NaN
    bounds when fewer than 20 records (a bootstrap on too few blocks is
    noise dressed up as statistics). Takes an explicit random.Random
    instance so callers can thread one seeded RNG through every bootstrap
    call rather than touching global random state.
    """
    if len(records) < _MIN_BOOTSTRAP_RECORDS:
        return (float("nan"), float("nan"))
    by = _month_blocks(records)
    months = list(by)
    out = []
    for _ in range(iters):
        sample: list[float] = []
        for _ in range(len(months)):
            sample += by[rng.choice(months)]
        out.append(statistics.mean(sample))
    out.sort()
    k = int(iters * 0.025)
    return (out[k], out[-k - 1])


def quantile(values: list[float], p: float) -> float:
    """Verbatim port of the prototype's quantile index formula.

    NOT numpy.percentile / statistics.quantiles — those interpolate, this
    does not, and the published reference threshold `atr_pct >= 3.47` is a
    product of this exact non-interpolated index formula. A silent
    substitution here is precisely the failure mode the reference-run
    parity check (Task 4) exists to catch.
    """
    v = sorted(values)
    i = max(0, min(len(v) - 1, int(round(p * (len(v) - 1)))))
    return v[i]


# ── rule selection (train-only) and holdout scoring ─────────────────────────

_QUANTILES = ((0.25, "Q1"), (0.50, "median"), (0.75, "Q3"))
_DIRECTIONS = (">=", "<")
_MIN_NON_NULL = 200
_MIN_KEPT = 150


@dataclass
class Rule:
    """A single-feature threshold rule. Train fields are set once by
    select_rules and never touched again; holdout fields default to
    "not yet scored" and are filled in-place by score_on_holdout."""

    feature: str
    threshold: float
    direction: str  # ">=" or "<"
    pname: str  # "Q1" / "median" / "Q3"
    train_n: int
    train_r: float
    holdout_n: int = 0
    holdout_r: float = field(default_factory=lambda: float("nan"))
    holdout_ci: tuple[float, float] = field(
        default_factory=lambda: (float("nan"), float("nan"))
    )


def _matches(record: dict, feature: str, threshold: float, direction: str) -> bool:
    value = record[feature]
    if value is None:
        return False
    return value >= threshold if direction == ">=" else value < threshold


def _apply_rule(rule: Rule, records: list[dict]) -> list[dict]:
    return [r for r in records if _matches(r, rule.feature, rule.threshold, rule.direction)]


def select_rules(
    train: list[dict], features: Iterable[str], skipped_out: list[dict]
) -> tuple[list[Rule], int]:
    """Search single-feature threshold rules on TRAIN ONLY.

    Signature takes the train list and nothing else — the holdout is
    structurally unreachable from rule selection (D-05), which is the
    cheapest way to guarantee train/holdout separation rather than merely
    test for it. For each feature, collects non-null train values; when
    fewer than 200 exist, appends a skip entry (feature, count, reason) to
    skipped_out and moves on without testing it. For each surviving
    feature, walks the three quantiles and both directions, incrementing
    the test counter once per ENUMERATED rule before the kept-size filter
    (the prototype counts enumeration, not survival — this is what makes
    the reference-run count 48 for the legacy eight features), then
    discards any rule keeping fewer than 150 train rows. Returns candidates
    sorted by descending train mean R, plus the total enumerated test count.
    """
    candidates: list[Rule] = []
    n_tests = 0
    for f in features:
        train_values = [x[f] for x in train if x[f] is not None]
        if len(train_values) < _MIN_NON_NULL:
            skipped_out.append({
                "feature": f,
                "count": len(train_values),
                "reason": f"only {len(train_values)} non-null values in train (< {_MIN_NON_NULL})",
            })
            continue
        for p, pname in _QUANTILES:
            thr = quantile(train_values, p)
            for direction in _DIRECTIONS:
                n_tests += 1
                kept = [x for x in train if _matches(x, f, thr, direction)]
                if len(kept) < _MIN_KEPT:
                    continue
                candidates.append(Rule(
                    feature=f, threshold=thr, direction=direction, pname=pname,
                    train_n=len(kept), train_r=mean_r(kept),
                ))

    candidates.sort(key=lambda r: -r.train_r)
    return candidates, n_tests


def score_on_holdout(
    rules: list[Rule], holdout: list[dict], rng: random.Random, top: int
) -> list[Rule]:
    """Apply each of the top-N rules UNCHANGED to the holdout.

    Same feature, same threshold, same direction, no re-fitting — records
    holdout n, holdout mean R, and the bootstrap CI onto each Rule in place.
    """
    scored = []
    for rule in rules[:top]:
        kept_h = _apply_rule(rule, holdout)
        rule.holdout_n = len(kept_h)
        rule.holdout_r = mean_r(kept_h)
        rule.holdout_ci = bootstrap_ci(kept_h, rng)
        scored.append(rule)
    return scored


def spearman_rho(pairs: list[tuple[float, float]]) -> Optional[float]:
    """Spearman rank correlation over (train_r, holdout_r) pairs.

    Ports the prototype's rank formula (1 - 6*d2/(n*(n*n-1))) and its tie
    handling — ranks assigned by dict-of-sorted-value position, NOT
    upgraded to average ranks, matching the prototype exactly. Returns None
    when fewer than five pairs are given (too few to be meaningful).
    """
    if len(pairs) < 5:
        return None
    a = [p[0] for p in pairs]
    b = [p[1] for p in pairs]
    rank_a = {v: i for i, v in enumerate(sorted(a))}
    rank_b = {v: i for i, v in enumerate(sorted(b))}
    n = len(pairs)
    d2 = sum((rank_a[p[0]] - rank_b[p[1]]) ** 2 for p in pairs)
    return 1 - 6 * d2 / (n * (n * n - 1))


# ── categorical breakdown ────────────────────────────────────────────────────

# conf_label across LOW/MEDIUM/HIGH and industry_above_50ma across 0.0/1.0 —
# deliberately categorical-only, matching the prototype. industry_above_50ma
# is NOT in FEATURES as a threshold feature; this is its only appearance.
_CATEGORICAL_SPECS: tuple[tuple[str, tuple[Any, ...]], ...] = (
    ("conf_label", ("LOW", "MEDIUM", "HIGH")),
    ("industry_above_50ma", (0.0, 1.0)),
)


def _categorical_breakdown(train: list[dict], holdout: list[dict]) -> list[dict]:
    rows = []
    for key, levels in _CATEGORICAL_SPECS:
        for level in levels:
            t = [x for x in train if x[key] == level]
            h = [x for x in holdout if x[key] == level]
            rows.append({
                "key": key, "level": level,
                "train_n": len(t), "train_r": mean_r(t),
                "holdout_n": len(h), "holdout_r": mean_r(h),
            })
    return rows


# ── orchestration ─────────────────────────────────────────────────────────────

@dataclass
class WinnerLoserResult:
    """Everything render_report needs to print the full diagnostic."""

    run_id: str
    db_path: str
    split: str
    strategy: Optional[str]
    train_n: int
    holdout_n: int
    train_baseline_r: float
    train_baseline_ci: tuple[float, float]
    holdout_baseline_r: float
    holdout_baseline_ci: tuple[float, float]
    categorical_rows: list[dict]
    features_defined: int
    tested_features: list[str]
    skipped_features: list[dict]
    n_tests: int
    top_rules: list[Rule]
    rho: Optional[float]
    rho_n: int


def analyze(
    records: list[dict],
    run_id: str = "",
    db_path: str = "",
    split: str = "2024-01-01",
    strategy: Optional[str] = None,
    features: tuple[str, ...] = FEATURES,
    top: int = 8,
    iters: int = 2000,
    seed: int = 11,
    missing_columns: Iterable[str] = (),
) -> WinnerLoserResult:
    """Assemble the full winner/loser diagnostic result.

    Composes split -> baselines -> categorical breakdown -> train-only rule
    search -> holdout scoring -> rank correlation, in that order. Seeds one
    dedicated random.Random(seed) instance rather than touching global
    random state, and threads it through every bootstrap call so the whole
    run is reproducible from one seed. `features` is a real parameter (not
    hardcoded to the FEATURES constant) so a caller — e.g. the Task 4 parity
    check — can re-run against LEGACY_FEATURES in isolation.

    Raises ValueError naming run_id when train or holdout ends up empty — a
    valid run_id whose trades all fall on one side of the split must say so,
    not silently print NaN rows.
    """
    missing_columns = set(missing_columns)
    train, holdout = split_records(records, split)
    if not train:
        raise ValueError(
            f"No train records before split={split!r} for run_id={run_id!r} "
            "— every record falls in the holdout window."
        )
    if not holdout:
        raise ValueError(
            f"No holdout records on/after split={split!r} for run_id={run_id!r} "
            "— every record falls in the train window."
        )

    rng = random.Random(seed)

    train_ci = bootstrap_ci(train, rng, iters=iters)
    holdout_ci = bootstrap_ci(holdout, rng, iters=iters)

    categorical_rows = _categorical_breakdown(train, holdout)

    skipped: list[dict] = [
        {
            "feature": f,
            "count": None,
            "reason": "column absent from this database (schema migration not yet run)",
        }
        for f in features
        if f in missing_columns
    ]
    testable_features = [f for f in features if f not in missing_columns]

    candidates, n_tests = select_rules(train, testable_features, skipped)

    top_rules = score_on_holdout(candidates[:top], holdout, rng, top)

    rho_pairs: list[tuple[float, float]] = []
    for rule in candidates:
        kept_h = _apply_rule(rule, holdout)
        if len(kept_h) >= _MIN_KEPT:
            rho_pairs.append((rule.train_r, mean_r(kept_h)))
    rho = spearman_rho(rho_pairs)

    already_skipped = {s["feature"] for s in skipped}
    tested_features = [f for f in testable_features if f not in already_skipped]

    return WinnerLoserResult(
        run_id=run_id,
        db_path=db_path,
        split=split,
        strategy=strategy,
        train_n=len(train),
        holdout_n=len(holdout),
        train_baseline_r=mean_r(train),
        train_baseline_ci=train_ci,
        holdout_baseline_r=mean_r(holdout),
        holdout_baseline_ci=holdout_ci,
        categorical_rows=categorical_rows,
        features_defined=len(features),
        tested_features=tested_features,
        skipped_features=skipped,
        n_tests=n_tests,
        top_rules=top_rules,
        rho=rho,
        rho_n=len(rho_pairs),
    )
