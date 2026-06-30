# TraderAssist — Signal Quality Milestone

## What This Is

TraderAssist is a personal swing trading scanner that identifies pullback and breakout setups across S&P 400/500/600 universes. It runs nightly scans, generates signals with gate-based filtering, backtests strategies over historical data, and displays results through a web UI. The owner uses it to surface actionable trade candidates with defined risk parameters.

## Core Value

Surface high-quality swing trade setups where the signal has a genuine edge — not just gate compliance.

## Requirements

### Validated

- ✓ Pullback strategy scanner with gate-based evaluation — existing
- ✓ Breakout strategy scanner with gate-based evaluation — existing
- ✓ Risk-based position sizing (stop/target engine) — existing
- ✓ Backtest infrastructure with trade simulator — existing
- ✓ Gate attribution analysis (which gates block what) — existing
- ✓ Post-mortem analysis for losing trades — existing
- ✓ Confidence scoring (regime-aware) — existing
- ✓ Web UI (Angular SPA + Express API) — existing
- ✓ SQLite signal/run/report persistence — existing
- ✓ Universe management (SP400/500/600) — existing
- ✓ Journal and live signal resolution — existing

### Active

- [ ] Industry/sector momentum as a display field on every signal — show the momentum strength of each stock's industry group so the owner can visually correlate it with outcomes before deciding whether it earns gate status
- [ ] Winner vs loser characteristic analysis in backtest reports — side-by-side breakdown of what entry-time metrics (RSI level, ATR multiple, industry momentum, etc.) winners had that losers didn't

### Out of Scope

- Adding industry momentum as a hard gate — display-only first; promote only after backtest evidence supports it (same discipline applied to ADX/volume contraction)
- Changing existing pullback/breakout gate thresholds or score formulas — stable, do not touch without new data
- Signal ranking / top-N selection — not the current focus
- Macro timing rules (FOMC avoidance, earnings season filters) — not prioritized

## Context

The scanner currently produces signals where ~50% eventually hit stop loss. All passing signals have cleared every gate, so the problem isn't a missing gate condition — it's that the gates are necessary but not sufficient. The hypothesis is that industry/sector momentum is a dimension not currently captured: a pullback in a weak industry may meet all technical gates but lack the directional tailwind that distinguishes winners.

Key lessons from prior work:
- ADX gate removal degraded performance (reverted)
- Volume contraction gate removal also degraded performance (reverted)
- Empirical validation before any gate change is mandatory
- Post-mortem analysis infrastructure already exists but hasn't surfaced a discriminating feature yet

Stack: Python scanner, SQLite DB (`data/scanner.db`), Express API (port 3000), Angular SPA (port 4200). Data via yfinance with Parquet cache. All tests via `pytest -q`.

## Constraints

- **Data source**: yfinance only — no paid data feeds; industry group data must be derivable from yfinance or the tickers themselves
- **Gate stability**: Do not change existing gate thresholds or score formulas without an explicit task backed by data
- **Test suite**: `pytest -q` must stay green after every Python change; `npm test` and `ng test` must stay green after web changes
- **Architecture**: New display fields flow through the same signal pipeline (scanner → DB → API → UI); no new tables without schema version bump

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Display-only for industry momentum | Follow the same evidence-first discipline that prevented two gate-removal mistakes | — Pending |
| Industry group granularity over GICS sectors | Finer discrimination — sectors are too broad to be predictive at the individual stock level | — Pending |
| Winner vs loser analysis in backtest reports | ~50% stop rate with no single causal gate means the answer is in the distribution, not a single threshold | — Pending |

---

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-30 after initialization*
