# Phase 7: CLI Output & Reporting - Context

**Gathered:** 2026-07-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 7 is the presentation layer over Phase 6's `SeasonalityResult`: render the 52-row
per-week table to stdout, print an interpretive summary (baseline, significant weeks with
context, top-5/bottom-5 by delta, a multiple-comparison caveat), print a one-line
survivorship-bias warning in the output header, and optionally write the same table to CSV
via `--output`. No new statistics are computed here — Phase 7 formats and communicates what
Phase 6 already produced.

**In scope:**
- Rendering `SeasonalityResult.weeks` as a fixed 52-row stdout table (SEAS-10)
- Padding logic for weeks absent from Phase 6's result and for `insufficient_years` weeks
- Interpretive summary text: baseline mean, significant-weeks list, top-5/bottom-5 by delta,
  multiple-comparison caveat (SEAS-11)
- One-line survivorship-bias warning in the output header (SEAS-12)
- `--output <path>` CSV export of the same padded table (SEAS-13); stdout always happens
  regardless of `--output`

**Out of scope (belongs to prior/other phases):**
- Any change to Phase 6's statistics (`week_observed_stats`, `bootstrap_week_ci`,
  `compute_seasonality_stats`) — Phase 7 only consumes `SeasonalityResult`
- Any change to Phase 5's data loading (`load_sector_dataset`, `resolve_sector`, etc.)
- Multiple-comparison correction (Bonferroni/FDR) — explicitly rejected in Phase 6; the
  caveat is informational text, not a statistical adjustment

</domain>

<decisions>
## Implementation Decisions

### Table Rendering & Missing/Insufficient Weeks
- **D-01:** Pad the table to exactly 52 rows. Any week absent from
  `SeasonalityResult.weeks` (Phase 6 only returns weeks actually present in the panel) gets
  an inserted row with `N/A` in all numeric columns and `significant=False`. This satisfies
  SEAS-10's literal "52-row table" requirement even for a thin/newly-formed sector missing
  some weeks entirely.
- **D-02:** Weeks flagged `insufficient_years=True` (Phase 6's CR-01 flag — every bootstrap
  draw missed that week, so the CI is genuinely uncomputable) show `N/A` for `ci_low_bps`/
  `ci_high_bps` in the table, with `significant=False` (already forced by Phase 6). The
  summary section explicitly calls out which weeks were uncomputable, so a reader never
  confuses "CI uncomputable" with "tested and not significant." `insufficient_years` itself
  is not a literal SEAS-10 column — it's communicated via the N/A cells plus the summary
  callout, not as a 10th table column.
- **D-03:** Numeric bps columns (`mean_daily_ret_bps`, `delta_vs_baseline_bps`,
  `ci_low_bps`, `ci_high_bps`, `median_bps`) render to 2 decimal places.
- **D-04:** Render via `pandas.DataFrame.to_string(index=False)` — no new dependency,
  consistent with `report.py`'s existing plain-text print style. (Considered `tabulate` for
  nicer box-drawing output; rejected to avoid an unnecessary new pip dependency for a
  milestone whose ethos is minimal additions.)

### Summary & Multiple-Comparison Caveat
- **D-05:** The caveat explains the actual false-positive math, tied to Phase 6's SEAS-15
  expectation — e.g. "with 52 independent tests at ~5% significance, ~2-3 false positives
  are expected by chance alone; treat any single flagged week with caution." Not a generic
  "not corrected for multiple comparisons" disclaimer — the user wants the reasoning spelled
  out, not just a warning label.
- **D-06:** The significant-weeks list (or the explicit "none — no week deviates
  significantly from baseline" message per SEAS-11) shows week + delta + CI per entry, e.g.
  `"Week 28: -12.4 bps (CI: -18.2 to -3.1)"` — self-contained, no need to cross-reference the
  table above it.
- **D-07:** The top-5/bottom-5-by-delta list always prints, even when zero weeks are
  significant — it's descriptive context (biggest observed deltas), not a significance
  claim, and SEAS-11 lists it as a separate summary item from the significant-weeks list.
- **D-08:** If fewer than 10 distinct weeks exist (thin dataset), show `min(5, available)`
  for each of top/bottom with no double-counting — dedup any week that would otherwise
  appear in both the "highest" and "lowest" lists rather than forcing exactly 5+5.

### Survivorship-Bias Warning
- **D-09:** The warning explains the actual mechanism, not just a generic disclaimer:
  the tool filters to TODAY's sector membership (via `sector_store`) and applies it to each
  ticker's full historical price series — it does not reconstruct historical sector
  membership and excludes delisted/removed tickers, which can inflate apparent seasonality.
  Example: "Survivorship bias: this analysis uses today's sector membership applied to
  historical prices — delisted/removed tickers are excluded, which can inflate apparent
  seasonality."
- **D-10:** The warning text is static — the same string every run, not interpolated with
  the run's sector/universe/n_years. The bias mechanism is structural (how `sector_store` +
  `data_store.get_history` work together), not run-specific, so a fixed one-line string
  satisfies SEAS-12 literally without added formatting complexity.

### CSV Export (`--output`)
- **D-11:** CSV columns match the same 9 SEAS-10 display columns: `week`,
  `mean_daily_ret_bps`, `delta_vs_baseline_bps`, `ci_low_bps`, `ci_high_bps`, `median_bps`,
  `n_obs`, `n_years`, `significant`. No extra `insufficient_years` column — keep stdout and
  CSV column sets identical.
- **D-12:** CSV rows get the SAME padding as the stdout table — exactly 52 rows, `N/A` for
  missing/insufficient weeks. One shared, already-padded DataFrame feeds both the stdout
  render and the CSV write, so the two outputs never disagree on row count or content.
- **D-13:** If `--output`'s parent directory doesn't exist, auto-create it
  (`Path.mkdir(parents=True, exist_ok=True)`, mirroring `scan.py`'s existing `--out`
  behavior at `scan.py:283`). If the target file already exists, overwrite it silently — no
  new dependency, least friction for repeated exploration runs.
- **D-14:** Per SEAS-13, stdout output always happens regardless of whether `--output` is
  passed — `--output` is additive, not a stdout replacement.

### Claude's Discretion
- Exact function names/signatures added to `scanner/seasonality.py` (or a new module, if
  planning determines the rendering logic warrants separation) for table padding, table
  string formatting, summary text assembly, and CSV writing
- Whether table-padding logic lives as one shared helper called by both the stdout and CSV
  paths, or is computed once in the orchestrator and passed to both — as long as D-12's
  "one shared DataFrame" guarantee holds
- Exact column header capitalization/spacing in the printed table (beyond the 2-decimal
  number formatting and column order already decided)
- Where in `seasonality_by_week.py::main` the render/CSV calls get wired in, following the
  existing thin-CLI-delegates-to-`scanner/`-module shape

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Planning & Requirements
- `.planning/ROADMAP.md` §Phase 7 (lines 85-96) — Goal, 4 success criteria, requirements
  mapping (SEAS-10, SEAS-11, SEAS-12, SEAS-13)
- `.planning/REQUIREMENTS.md` lines 25-28, 59-62 — the four requirements mapped to Phase 7
  with exact column/behavior wording
- `.planning/PROJECT.md` §Current Milestone — v1.1 Weekly Seasonality Analyzer goal and
  target features; §Key lessons — the `np.percentile`/`np.nanpercentile` lesson explaining
  why `insufficient_years` exists and must not be silently dropped

### Codebase Extension Points (patterns to mirror)
- `scanner/seasonality.py::compute_seasonality_stats` (lines 422-478) and
  `SeasonalityResult` dataclass (lines 67-81) — the exact input Phase 7 consumes. `weeks` is
  a DataFrame with columns `[week, mean_daily_ret_bps, delta_vs_baseline_bps, ci_low_bps,
  ci_high_bps, median_bps, n_obs, n_years, significant, insufficient_years, std_bps]`, only
  for weeks actually present in the panel.
- `scanner/seasonality.py::bootstrap_week_ci` (lines 316-419), especially the CR-01
  docstring (lines 332-344) — explains exactly what `insufficient_years=True` means and why
  it must be distinguished from "not significant" in the UI (D-02/D-05 above depend on this).
- `seasonality_by_week.py` (repo root) — thin CLI; already declares `--output` as an unused
  placeholder (line 46-48) and prints a plain per-run summary (lines 74-87) that Phase 7
  replaces/extends with the full table + interpretive summary + warning.
- `scan.py:283` — `out_dir.mkdir(parents=True, exist_ok=True)` — the auto-create-parent-dirs
  pattern D-13 mirrors.
- `.planning/phases/06-seasonality-statistics-verification/06-CONTEXT.md` — Phase 6's full
  context; explains D-01/D-02 pooling design and the "prefer being loud and honest" theme
  that also motivates D-02's insufficient_years callout and D-09's mechanism-explaining
  survivorship warning.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scanner/seasonality.py::SeasonalityResult` — already carries everything Phase 7 table/
  summary/CSV logic needs: `sector`, `universe`, `baseline_mean_bps`, `n_years`,
  `bootstrap_iters`, `seed`, `weeks` (DataFrame).
- `pandas.DataFrame.to_string(index=False)` and `DataFrame.to_csv(path, index=False)` —
  standard pandas, already a project dependency, no new imports needed for D-04/D-11.

### Established Patterns
- Thin-CLI-delegates-to-`scanner/`-module shape (Phase 5/6 precedent) —
  `seasonality_by_week.py::main` should stay thin; rendering/CSV logic belongs in
  `scanner/seasonality.py` (or a sibling function in the same module) so it's testable
  without going through argparse.
- `ValueError`-with-descriptive-message-then-CLI-catches-and-exits-2 pattern
  (`resolve_sector`, `universe_path`, `check_thin_data`) — if CSV writing can fail in a way
  worth surfacing distinctly (e.g. a genuinely unwritable path after mkdir), follow the same
  convention; not expected to be a major concern given D-13's auto-create/overwrite choice.
- "SKIP, don't fail" / "loud and honest over silently plausible" theme carries through from
  Phase 5/6 into Phase 7's N/A-padding and insufficient_years-callout decisions (D-01/D-02) —
  never let a padded or uncomputed cell look like a real, tested "not significant" result.

### Integration Points
- Phase 7 code is called from `seasonality_by_week.py::main` after
  `compute_seasonality_stats` returns (currently at line 67-69), replacing the placeholder
  summary print at lines 82-87.

</code_context>

<specifics>
## Specific Ideas

The user consistently favored the more explanatory option at every either/or choice in this
discussion (caveat math over generic disclaimer, mechanism-explaining survivorship warning
over generic one-liner, week+delta+CI over bare week numbers) — this mirrors the "loud and
honest, not just compliant" theme already established in Phase 6's context. Downstream
planning/execution should default to writing MORE explanatory text rather than terser text
when a formatting choice isn't explicitly locked above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 7-CLI Output & Reporting*
*Context gathered: 2026-07-10*
