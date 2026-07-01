---
phase: 4
slug: winner-loser-characteristic-analysis
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-01
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Python) + Karma/Angular (TypeScript) |
| **Config file** | `pytest.ini` / `web/ui/karma.conf.js` |
| **Quick run command** | `pytest -q` |
| **Full suite command** | `pytest -q && cd web/ui && ng test --watch=false --browsers=ChromeHeadless` |
| **Estimated runtime** | ~15 seconds (pytest) + ~45 seconds (ng test) |

---

## Sampling Rate

- **After every task commit:** Run `pytest -q`
- **After every plan wave:** Run full suite (`pytest -q` + `ng test`)
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Automated Command | Status |
|---------|------|------|-------------|-------------------|--------|
| 04-01-T1 | 01 | 1 | WLA-02 | `pytest -q` | ⬜ pending |
| 04-01-T2 | 01 | 1 | WLA-01, WLA-03, WLA-04 | `pytest -q` | ⬜ pending |
| 04-01-T3 | 01 | 1 | WLA-01, WLA-05, WLA-06 | `pytest tests/test_report.py -q` | ⬜ pending |
| 04-02-T1 | 02 | 2 | WLA-01, WLA-04 | `cd web/api && npm test` | ⬜ pending |
| 04-02-T2 | 02 | 2 | WLA-01, WLA-05 | `cd web/ui && ng build` | ⬜ pending |
| 04-02-T3 | 02 | 2 | WLA-01, WLA-04, WLA-05 | `cd web/ui && ng test --watch=false --browsers=ChromeHeadless` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test setup needed:
- `tests/` directory with pytest configured
- `web/ui/karma.conf.js` already configured for ChromeHeadless

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| W/L table renders correctly in Angular UI with real backtest data | WLA-01 | Requires a completed backtest run with ≥ 200 qualified trades | Run `scan.py backtest`, open Backtest page, verify W/L cards appear with correct median values |
| pct_to_52w_high formula direction (distance-below-high convention) | WLA-01 | Formula assumption A1 from RESEARCH.md — owner confirmation needed | Check that values are displayed as distance below the 52w high (e.g., 18.3% means 18.3% below peak), not as ratio |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-01
