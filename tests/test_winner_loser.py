"""Tests for scanner.winner_loser — the analysis engine (train/holdout split,
month-block bootstrap, train-only rule selection, holdout scoring, rho)."""
from __future__ import annotations

import inspect
import random

import pytest

from scanner.winner_loser import (
    FEATURES,
    LEGACY_FEATURES,
    V10_FEATURES,
    Rule,
    WinnerLoserResult,
    analyze,
    bootstrap_ci,
    load_records,
    mean_r,
    quantile,
    score_on_holdout,
    select_rules,
    spearman_rho,
    split_records,
)

# Outcome variables known only after a trade closes — must never appear as a
# predictor (D-05 predictor discipline).
_OUTCOME_VARIABLES = {
    "mae_r", "mfe_r", "holding_days", "exit_px", "exit_reason",
    "post_stop_reached_target", "post_stop_mfe_r", "r_multiple",
}


def _rec(date, r, **overrides):
    """Build one full-shaped record (the dict shape load_records produces)."""
    base = {
        "date": date, "ticker": "AAA", "r": r,
        "score": None, "confidence": None, "conf_label": None,
        "atr_pct": None, "close": 100.0, "target_r": None, "target_atr": None,
        "industry_momentum": None, "industry_above_50ma": None,
        "industry_rank_pct": None, "rsi_entry": None, "rvol": None,
        "pullback_depth_pct": None, "pct_to_52w_high": None,
    }
    base.update(overrides)
    return base


# ── split_records ────────────────────────────────────────────────────────────

def test_split_boundary_date_lands_in_holdout_not_train():
    """D-06: a record dated exactly on --split belongs to HOLDOUT, matching
    the prototype's `>=` comparison — this is the exact boundary rule the
    reference-run parity check depends on."""
    records = [
        _rec("2023-12-31", 0.1),
        _rec("2024-01-01", 0.2),  # on the boundary
        _rec("2024-01-02", 0.3),
    ]
    train, holdout = split_records(records, "2024-01-01")
    assert len(train) == 1
    assert len(holdout) == 2
    assert train[0]["date"] == "2023-12-31"


def test_split_malformed_split_string_raises():
    with pytest.raises(ValueError):
        split_records([_rec("2024-01-01", 0.1)], "2024-1-1")


# ── select_rules: structurally cannot see holdout ───────────────────────────

def test_select_rules_signature_has_no_holdout_parameter():
    """The cheapest possible guarantee of D-05: rule selection cannot read
    holdout rows because its signature does not accept them."""
    params = list(inspect.signature(select_rules).parameters)
    assert "holdout" not in params
    assert params[:1] == ["train"]


def _build_varying_train(n=250, features=LEGACY_FEATURES, start_year=2020):
    """n train records with every listed feature populated with variance
    (i-based), enough to clear the 200-non-null bar for each."""
    records = []
    for i in range(n):
        month = (i % 12) + 1
        day = (i % 27) + 1
        date = f"{start_year}-{month:02d}-{day:02d}"
        row = _rec(date, r=(i % 7) * 0.1 - 0.3)
        if "score" in features:
            row["score"] = float(i)
        if "confidence" in features:
            row["confidence"] = float(i % 3)
        if "atr_pct" in features:
            row["atr_pct"] = i * 0.1
        if "close" in features:
            row["close"] = 50.0 + i
        if "target_r" in features:
            row["target_r"] = i * 0.01
        if "target_atr" in features:
            row["target_atr"] = i * 0.02
        if "industry_momentum" in features:
            row["industry_momentum"] = float(i % 50)
        if "industry_rank_pct" in features:
            row["industry_rank_pct"] = float(i % 100)
        if "rsi_entry" in features:
            row["rsi_entry"] = float(i % 70) + 20
        if "rvol" in features:
            row["rvol"] = 0.5 + (i % 30) * 0.1
        if "pullback_depth_pct" in features:
            row["pullback_depth_pct"] = float(i % 15)
        if "pct_to_52w_high" in features:
            row["pct_to_52w_high"] = float(i % 20)
        records.append(row)
    return records


def test_select_rules_test_count_is_2x3xtested_features_legacy_eight():
    """D-04: 2 directions x 3 quantiles x 8 tested legacy features == 48,
    matching the reference run's published enumerated-test count."""
    train = _build_varying_train(n=250, features=LEGACY_FEATURES)
    skipped: list[dict] = []
    candidates, n_tests = select_rules(train, LEGACY_FEATURES, skipped)
    assert n_tests == 48
    assert skipped == []


def test_select_rules_test_count_is_2x3xtested_features_all_twelve():
    """D-04: with all twelve features testable, 2 x 3 x 12 == 72."""
    train = _build_varying_train(n=250, features=FEATURES)
    skipped: list[dict] = []
    candidates, n_tests = select_rules(train, FEATURES, skipped)
    assert n_tests == 72
    assert skipped == []


def test_select_rules_skips_feature_with_fewer_than_200_non_null():
    """A feature with <200 non-null train values is skipped with its count
    and reason, and the enumerated test count reflects only tested features."""
    train = _build_varying_train(n=250, features=LEGACY_FEATURES)
    # Blank out "score" on all but 150 records -> only 150 non-null.
    for row in train[150:]:
        row["score"] = None
    skipped: list[dict] = []
    candidates, n_tests = select_rules(train, LEGACY_FEATURES, skipped)

    skip_entry = next(s for s in skipped if s["feature"] == "score")
    assert skip_entry["count"] == 150
    assert "200" in skip_entry["reason"] or "non-null" in skip_entry["reason"]
    # 7 remaining testable features x 2 x 3 == 42, "score" excluded.
    assert n_tests == 42
    assert all(c.feature != "score" for c in candidates)


def test_select_rules_quantile_formula_no_interpolation():
    """The published reference threshold atr_pct >= 3.47 is a product of
    this exact non-interpolated index formula -- must not silently move."""
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    # p=0.5 -> index = round(0.5 * 4) = 2 -> value 3.0 (median, exact match
    # here, but the formula is index-based, not statistics.median).
    assert quantile(values, 0.5) == 3.0
    # p=0.25 -> index = round(0.25 * 4) = 1 -> value 2.0.
    assert quantile(values, 0.25) == 2.0
    # p=0.75 -> index = round(0.75 * 4) = 3 -> value 4.0.
    assert quantile(values, 0.75) == 4.0


# ── D-05: selection cannot see holdout, end-to-end via analyze() ───────────

def _build_analyze_fixture():
    train = _build_varying_train(n=250, features=FEATURES, start_year=2020)
    holdout = []
    for i in range(60):
        month = (i % 12) + 1
        day = (i % 27) + 1
        date = f"2024-{month:02d}-{day:02d}"
        row = _rec(date, r=(i % 5) * 0.1)
        row["score"] = float(i * 3)
        row["confidence"] = float(i % 3)
        row["atr_pct"] = i * 0.2
        row["close"] = 60.0 + i
        row["target_r"] = i * 0.02
        row["target_atr"] = i * 0.03
        row["industry_momentum"] = float(i % 40)
        row["industry_rank_pct"] = float(i % 90)
        row["rsi_entry"] = float(i % 60) + 20
        row["rvol"] = 0.4 + (i % 25) * 0.1
        row["pullback_depth_pct"] = float(i % 12)
        row["pct_to_52w_high"] = float(i % 18)
        holdout.append(row)
    return train, holdout


def test_perturbing_holdout_r_leaves_selected_rules_bit_identical():
    """D-05: perturbing every holdout r value must leave every selected
    rule's feature, threshold, direction, train_n and train_r bit-identical
    -- selection is structurally incapable of seeing the holdout."""
    train, holdout = _build_analyze_fixture()

    result_a = analyze(train + holdout, run_id="r1", split="2024-01-01", seed=11)

    holdout_perturbed = [dict(r, r=999.0) for r in holdout]
    result_b = analyze(train + holdout_perturbed, run_id="r1", split="2024-01-01", seed=11)

    assert len(result_a.top_rules) == len(result_b.top_rules) > 0
    for ra, rb in zip(result_a.top_rules, result_b.top_rules):
        assert ra.feature == rb.feature
        assert ra.threshold == rb.threshold
        assert ra.direction == rb.direction
        assert ra.train_n == rb.train_n
        assert ra.train_r == rb.train_r
        # Holdout mean R must reflect the perturbation (999.0 for every
        # holdout row matching the rule).
        if rb.holdout_n > 0:
            assert rb.holdout_r == pytest.approx(999.0)


# ── missing-column skip (distinct reason from too-few-non-null) ────────────

def test_analyze_missing_columns_reported_with_distinct_reason():
    train, holdout = _build_analyze_fixture()
    missing = ("rsi_entry", "rvol", "pullback_depth_pct", "pct_to_52w_high")

    result = analyze(
        train + holdout, run_id="r1", split="2024-01-01", seed=11,
        missing_columns=missing,
    )

    missing_reasons = {s["feature"]: s["reason"] for s in result.skipped_features if s["feature"] in missing}
    assert set(missing_reasons) == set(missing)
    for reason in missing_reasons.values():
        assert "absent" in reason.lower() or "column" in reason.lower()
    assert len(result.tested_features) == 8
    assert len(result.skipped_features) == 4


# ── FEATURES / outcome variable discipline (D-05) ───────────────────────────

def test_features_share_no_member_with_outcome_variables():
    assert set(FEATURES).isdisjoint(_OUTCOME_VARIABLES)
    assert set(LEGACY_FEATURES) | set(V10_FEATURES) == set(FEATURES)


# ── bootstrap_ci ─────────────────────────────────────────────────────────────

def test_bootstrap_ci_reproducible_same_seed():
    records = [_rec(f"2021-{(i % 12) + 1:02d}-01", i * 0.01) for i in range(40)]
    ci_a = bootstrap_ci(records, random.Random(11), iters=200)
    ci_b = bootstrap_ci(records, random.Random(11), iters=200)
    assert ci_a == ci_b


def test_bootstrap_ci_fewer_than_20_records_returns_nan():
    records = [_rec(f"2021-01-{i+1:02d}", i * 0.01) for i in range(10)]
    lo, hi = bootstrap_ci(records, random.Random(11), iters=200)
    assert lo != lo  # NaN != NaN
    assert hi != hi


# ── spearman_rho ─────────────────────────────────────────────────────────────

def test_spearman_rho_perfect_concordance_is_plus_one():
    pairs = [(1.0, 10.0), (2.0, 20.0), (3.0, 30.0), (4.0, 40.0), (5.0, 50.0)]
    assert spearman_rho(pairs) == pytest.approx(1.0)


def test_spearman_rho_fewer_than_five_pairs_returns_none():
    pairs = [(1.0, 10.0), (2.0, 20.0)]
    assert spearman_rho(pairs) is None


# ── empty records / malformed split raise ValueError ────────────────────────

def test_analyze_empty_records_raises_valueerror_naming_run_id():
    with pytest.raises(ValueError, match="empty-run"):
        analyze([], run_id="empty-run", split="2024-01-01")


def test_analyze_malformed_split_raises_valueerror():
    train, holdout = _build_analyze_fixture()
    with pytest.raises(ValueError):
        analyze(train + holdout, run_id="r1", split="2024-1-1")


def test_load_records_no_usable_rows_raises_valueerror_naming_run_id():
    class _FakeConn:
        pass

    import scanner.winner_loser as wl_module

    def _fake_get_analysis_signals(conn, run_id, strategy=None):
        return [], set()

    orig = wl_module.store_db.get_analysis_signals
    wl_module.store_db.get_analysis_signals = _fake_get_analysis_signals
    try:
        with pytest.raises(ValueError, match="nope-run"):
            load_records(_FakeConn(), "nope-run")
    finally:
        wl_module.store_db.get_analysis_signals = orig


# ── score_on_holdout ─────────────────────────────────────────────────────────

def test_score_on_holdout_fills_holdout_fields():
    train, holdout = _build_analyze_fixture()
    skipped: list[dict] = []
    candidates, _ = select_rules(train, LEGACY_FEATURES, skipped)
    assert candidates, "fixture must produce at least one candidate rule"

    scored = score_on_holdout(candidates[:3], holdout, random.Random(11), top=3)
    for rule in scored:
        assert rule.holdout_n >= 0
        assert isinstance(rule.holdout_r, float)


# ── WinnerLoserResult / Rule dataclasses ─────────────────────────────────────

def test_analyze_returns_fully_populated_result():
    train, holdout = _build_analyze_fixture()
    result = analyze(train + holdout, run_id="r1", db_path="fake.db",
                      split="2024-01-01", strategy=None, seed=11)

    assert isinstance(result, WinnerLoserResult)
    assert result.run_id == "r1"
    assert result.db_path == "fake.db"
    assert result.train_n == len(train)
    assert result.holdout_n == len(holdout)
    assert result.categorical_rows
    assert result.n_tests > 0
    assert all(isinstance(r, Rule) for r in result.top_rules)
