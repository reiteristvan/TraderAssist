# Phase 6: Seasonality Statistics & Verification - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-10
**Phase:** 6-Seasonality Statistics & Verification
**Areas discussed:** Return aggregation & weighting, Bootstrap defaults, Thin-data guard, Synthetic verification rigor

---

## Return Aggregation & Weighting

| Option | Description | Selected |
|--------|-------------|----------|
| Pool ticker-days | Every (ticker, day) observation in a week is an equal data point; n_obs = total ticker-days across all years; matches the block-bootstrap wording literally | ✓ |
| Sector daily average first | Average all tickers' returns within a day into one sector-day return first; n_obs = trading-days across years (much smaller n); more like an index return | |

**User's choice:** Pool ticker-days (Recommended)
**Notes:** None — recommended option accepted directly.

---

## Bootstrap Defaults

| Option | Description | Selected |
|--------|-------------|----------|
| 1000 iters, fixed seed | Standard-enough for stable 95% CIs at reasonable runtime; fixed default seed means two unflagged runs produce identical output | ✓ |
| 5000 iters, fixed seed | Tighter CI precision, slower | |
| 1000 iters, no default seed | Truly random unless pinned; risk of different results near CI boundary across runs | |

**User's choice:** 1000 iters, fixed seed (Recommended)
**Notes:** None — recommended option accepted directly.

---

## Thin-Data Guard

| Option | Description | Selected |
|--------|-------------|----------|
| Hard minimum, abort below it | Require a minimum number of distinct years or exit with a clear error | ✓ |
| Warn but proceed | Print a caveat and still compute/report | |
| No guard — Claude's discretion | Let researcher/planner decide a sensible threshold | |

**User's choice:** Hard minimum, abort below it (Recommended)
**Notes:** Follow-up question nailed down the exact threshold.

### Follow-up: Minimum Years Threshold

| Option | Description | Selected |
|--------|-------------|----------|
| 5 years | Enough distinct year-blocks for real resampling diversity; matches typical swing-trading lookback windows elsewhere in the codebase | ✓ |
| 3 years | Lower bar, more sectors/tickers pass, but bootstrap draws from too few blocks | |
| 10 years | Much more robust CI but excludes newly-listed sectors/short `--years` windows entirely | |

**User's choice:** 5 years (Recommended)
**Notes:** None — recommended option accepted directly.

---

## Synthetic Verification Rigor

| Option | Description | Selected |
|--------|-------------|----------|
| Single fixed-seed run | Deterministic, fast, easy to debug in CI; risk of flakiness mitigated by pinning a verified-stable seed | ✓ |
| Multiple noise trials, check distribution | Run pure-noise several times and assert the average/median flagged count stays near ~5%; more convincing but slower and more complex | |

**User's choice:** Single fixed-seed run (Recommended)
**Notes:** None — recommended option accepted directly.

---

## Claude's Discretion

- CI construction method (percentile bootstrap expected to be sufficient; confirm during research)
- Exact function names/signatures added to `scanner/seasonality.py`
- Log-return formula details and NaN/gap-day handling within a ticker's series
- Exact default seed value (42 given as an example, not locked)
- Synthetic test dataset size/shape (years, ticker count, noise model) — must itself satisfy the 5-year thin-data guard
- Exact abort behavior (exit code, message format) for the thin-data guard — mirror Phase 5's `ValueError` pattern

## Deferred Ideas

None — discussion stayed within phase scope.
