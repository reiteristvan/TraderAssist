---
phase: 6
slug: seasonality-statistics-verification
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-10
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (installed; `pythonpath = ["."]` set in `pyproject.toml`, no other config) |
| **Config file** | `pyproject.toml` (`[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest -q tests/test_seasonality.py` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~5 seconds (quick), full suite already fast per existing project convention |

---

## Sampling Rate

- **After every task commit:** Run `pytest -q tests/test_seasonality.py`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-xx | 01 | 1 | SEAS-06 | — | Per-week mean/median/std/n_obs/n_years computed correctly from a known synthetic panel | unit | `pytest -q tests/test_seasonality.py -k week_observed_stats -x` | ❌ Wave 0 | ⬜ pending |
| 06-01-xx | 01 | 1 | SEAS-07 | — | Delta vs. full-sample baseline computed correctly | unit | `pytest -q tests/test_seasonality.py -k baseline -x` | ❌ Wave 0 | ⬜ pending |
| 06-01-xx | 01 | 1 | SEAS-08 | — | Bootstrap CI reproducible across two runs with same `--seed`; distinct from a different seed | unit | `pytest -q tests/test_seasonality.py -k bootstrap_ci -x` | ❌ Wave 0 | ⬜ pending |
| 06-01-xx | 01 | 1 | SEAS-08 (D-05 guard) | T-6-01 | `< 5` distinct years raises `ValueError` before computing a CI | unit | `pytest -q tests/test_seasonality.py -k thin_data -x` | ❌ Wave 0 | ⬜ pending |
| 06-01-xx | 01 | 1 | SEAS-09 | — | Significance flag is `True` iff CI excludes zero (boundary cases: CI touching zero exactly) | unit | `pytest -q tests/test_seasonality.py -k significant -x` | ❌ Wave 0 | ⬜ pending |
| 06-02-xx | 02 | 2 | SEAS-14 | — | Injected -30bps week-28 effect flags week 28 significant (fixed seed) | integration/synthetic | `pytest -q tests/test_seasonality.py -k synthetic_injected -x` | ❌ Wave 0 | ⬜ pending |
| 06-02-xx | 02 | 2 | SEAS-15 | — | Pure-noise run flags 0-3 of 52 weeks (fixed seed) | integration/synthetic | `pytest -q tests/test_seasonality.py -k synthetic_noise -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Exact task IDs assigned by the planner; this map is pre-populated from RESEARCH.md's Phase Requirements → Test Map and refined once PLAN.md files exist.*

---

## Wave 0 Requirements

- [ ] New test functions in `tests/test_seasonality.py` covering SEAS-06/07/08/09/14/15 (file already exists from Phase 5 — this phase adds cases, doesn't create the file)
- [ ] No new fixtures/conftest needed — the existing `_synthetic_frame` helper pattern in `tests/test_seasonality.py` can be extended with a panel-building helper
- [ ] No framework install needed — pytest already present

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification per RESEARCH.md's Phase Requirements → Test Map.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
