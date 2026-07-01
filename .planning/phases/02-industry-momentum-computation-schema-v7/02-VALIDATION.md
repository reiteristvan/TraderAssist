---
phase: 2
slug: industry-momentum-computation-schema-v7
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-01
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini / pyproject.toml (existing) |
| **Quick run command** | `pytest -q tests/test_core.py tests/test_store.py` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest -q tests/test_core.py tests/test_store.py`
- **After every plan wave:** Run `pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Status |
|---------|------|------|-------------|-----------|-------------------|--------|
| 02-01-01 | 01 | 1 | IND-02, IND-03 | unit | `pytest -q tests/test_core.py -k "industry_strength"` | ⬜ pending |
| 02-01-02 | 01 | 1 | IND-04 | unit | `pytest -q tests/test_core.py -k "industry_rank"` | ⬜ pending |
| 02-01-03 | 01 | 1 | IND-06 | unit | `pytest -q tests/test_core.py -k "look_ahead"` | ⬜ pending |
| 02-02-01 | 02 | 2 | IND-05 | unit | `pytest -q tests/test_store.py -k "schema_v9"` | ⬜ pending |
| 02-02-02 | 02 | 2 | IND-05 | unit | `pytest -q tests/test_store.py -k "industry_null"` | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- Existing infrastructure covers all phase requirements (pytest suite already at 221 tests).
- No new test files needed for Wave 0; new test functions added inline to existing test files.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| schema_version reads 9 in production DB | IND-05 | Requires live scan run | Run `python scan.py scan --strategy pullback --ticker AAPL` and check `SELECT version FROM schema_version` |
| NULL industry_momentum survives DB round-trip | IND-05 | Requires actual DB write | Insert signal with NULL industry_momentum and re-read; confirm it is not coerced to 0.0 |
| Look-ahead bias spot-check | IND-06 | Requires historical backtest | Run backtest on 2024-01-15 and confirm ETF close used matches yfinance historical close for that date |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
