# Phase 7: CLI Output & Reporting - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 2 (1 extended module, 1 extended CLI entry point)
**Analogs found:** 2 / 2

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `scanner/seasonality.py` (new functions: table padding, summary text, CSV write) | service/utility (pure transform) | transform (DataFrame → DataFrame/str/file) | `scanner/report.py::render_report` + bucket/format helpers | role-match (same module-of-origin already extended by Phase 5/6) |
| `seasonality_by_week.py::main` (wire render/summary/CSV calls) | CLI entry point | request-response (argparse → stdout/file) | `scan.py::cmd_scan` / `cmd_backtest` (stdout print + optional CSV + mkdir) | exact (same thin-CLI-delegates shape, same `--output`/`--csv`/`--out` idiom) |

## Pattern Assignments

### `scanner/seasonality.py` — new padding/render/summary/CSV functions

**Analog 1 (transform/format style):** `scanner/report.py::compute_metrics` / `render_report` (`D:\Projects\TraderAssist\scanner\report.py`)

**Analog 2 (table padding source data shape):** `scanner/seasonality.py::week_observed_stats` and `bootstrap_week_ci` (same file, lines 263-419) — these already establish the exact column set and the "only weeks present" pattern that Phase 7's padding function must extend to all 52 weeks.

**Pure-function, no-I/O style** (mirrors `compute_seasonality_stats`, lines 422-478):
```python
def compute_seasonality_stats(
    dataset: SectorDataset,
    bootstrap_iters: int | None = None,
    seed: int | None = None,
) -> SeasonalityResult:
    """... Pure function: no I/O, no wall-clock date."""
```
Phase 7's padding/render functions should follow the same shape: take a `SeasonalityResult` (or its `.weeks` DataFrame) in, return a DataFrame/string out, with the CLI (`seasonality_by_week.py`) owning all I/O (print, file write). This is the same "small pure functions composed by an orchestrator" style used throughout this module (`load_sector_dataset`, `compute_seasonality_stats`).

**Docstring/comment convention** — every function in this module documents *why*, referencing decision IDs (D-0x) and requirement IDs (SEAS-xx), e.g.:
```python
def check_thin_data(panel: pd.DataFrame, min_years: int = _MIN_BOOTSTRAP_YEARS) -> None:
    """Abort before any bootstrap work if too few distinct years exist (D-05, SEAS-08).
    ...
    """
```
New Phase 7 functions (e.g. `pad_weeks_table`, `render_weeks_table`, `build_summary`, `write_weeks_csv`) should follow this same docstring convention, citing D-01..D-14 and SEAS-10..13 inline.

**Table rendering pattern** (`to_string(index=False)`), analog from `scan.py:243`:
```python
display_cols = [c for c in cols if c in display_df.columns]
print(display_df[display_cols].to_string(index=False))
```
Per D-04, Phase 7 should build a padded/formatted display DataFrame (2-decimal bps columns, `N/A` for missing/insufficient_years cells) and call `.to_string(index=False)` on it — same idiom, no new dependency (`tabulate` explicitly rejected).

**NULL/NaN → sentinel display formatting**, analog from `scan.py::_print_scan_results` (lines 205-240):
```python
if "industry_momentum" in display_df.columns:
    display_df["Mom"] = display_df["industry_momentum"].apply(
        lambda v: f"{v:+.1f}%" if v is not None and not pd.isna(v) else "—"
    )
else:
    display_df["Mom"] = "—"
```
Phase 7's `N/A`-for-missing/insufficient_years cell formatting (D-01/D-02) should follow this same explicit `None`/`pd.isna` guard-before-format pattern — never a bare truthy check (the codebase has a documented pitfall around `0`-vs-`None`/`NaN` ambiguity here worth re-reading if padding logic touches boolean-like columns like `significant`).

**Markdown/text summary assembly pattern**, analog from `report.py::render_report` (lines 612-799):
```python
lines = ["# Backtest Report\n"]
...
lines += ["\n## Summary Metrics\n"]
if metrics["count"] == 0:
    lines.append("*No qualifying trades in this run.*\n")
else:
    lines += [
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Trades | {metrics['count']} |",
        ...
    ]
...
md = "\n".join(lines)
```
Phase 7's interpretive summary (baseline, significant-weeks list, top-5/bottom-5, multiple-comparison caveat, survivorship warning) should build a `list[str]` of text lines and join once at the end — same "accumulate lines, join once" idiom, adapted to plain-text (not markdown headers) since this is a CLI stdout summary, not a `report.md` file.

**Per-item formatted-string list pattern** (for D-06's `"Week 28: -12.4 bps (CI: -18.2 to -3.1)"` entries), analog from `report.py::gate_attribution` output loop (lines 765-779):
```python
for a in attribution:
    exp = f"{a['expectancy_r']:.3f}" if a["expectancy_r"] is not None else "—"
    ...
    lines.append(
        f"| {a['gate']} | {a['n']} | {exp} | {qexp} | {delta} | **{rec}** | {a['verdict']} |"
    )
```
Adapt this per-row-format-then-append idiom for the significant-weeks list and top-5/bottom-5 list, iterating the (already-computed, Phase-6-produced) `weeks` DataFrame rows via `.itertuples()` or `.to_dict("records")`.

**Static one-line warning string constant**, analog from `report.py`'s `_BIAS_SURVIVORSHIP` (lines 37-41):
```python
_BIAS_SURVIVORSHIP = (
    "**Survivorship bias** — universe contains currently-listed names only; "
    "delisted/bankrupt names are absent. Results are optimistic relative to "
    "the real investable universe at each historical date."
)
```
D-09/D-10's fixed, non-interpolated survivorship-bias warning string should be defined as a module-level constant in `scanner/seasonality.py` in exactly this style (a `_`-prefixed private constant, multi-line string literal, printed verbatim by the CLI) — not built dynamically per run.

**CSV export pattern**, analog from `scan.py:158-160`:
```python
if getattr(args, "csv", None):
    combined.to_csv(args.csv, index=False)
    print(f"\nSaved → {args.csv}")
```
And the parent-dir auto-create pattern from `scan.py:282-283`:
```python
out_dir = Path(args.out)
out_dir.mkdir(parents=True, exist_ok=True)
```
Per D-11..D-14, Phase 7's CSV writer should combine both: resolve `Path(args.output).parent`, `mkdir(parents=True, exist_ok=True)`, then `padded_df[csv_columns].to_csv(args.output, index=False)`, and print a confirmation line — same idiom, applied to a file path rather than a directory.

---

### `seasonality_by_week.py::main` — wire render/summary/CSV calls

**Analog:** `scan.py::cmd_scan` (`D:\Projects\TraderAssist\scan.py`, lines ~120-186) and `scan.py::cmd_backtest` (lines 270-283)

**Current placeholder to replace** (`seasonality_by_week.py`, lines 74-87):
```python
significant_count = int(result.weeks["significant"].sum())
print(
    f"Baseline: {result.baseline_mean_bps:.4f} bps/day  Years: {result.n_years}  "
    f"Bootstrap iters: {result.bootstrap_iters}  Seed: {result.seed}"
)
print(f"Significant weeks: {significant_count} of {len(result.weeks)}")
```

**Existing `--output` placeholder to activate** (lines 45-48):
```python
parser.add_argument(
    "--output", default=None,
    help="Output path for results (consumed in a later phase; not used yet)",
)
```
Per D-14/SEAS-13, `main` must print the table+summary+warning to stdout unconditionally, then — only if `args.output` is truthy — call the new CSV-writing function, mirroring `scan.py`'s `if getattr(args, "csv", None): ... ; print(f"\nSaved → {args.csv}")` idiom (adjust the help string to reflect Phase 7 activation).

**Existing `ValueError`-catch-exit-2 CLI convention to preserve** (`seasonality_by_week.py`, lines 65-72):
```python
try:
    ds = seasonality.load_sector_dataset(args.sector, args.universe, years=args.years)
    result = seasonality.compute_seasonality_stats(
        ds, bootstrap_iters=args.bootstrap_iters, seed=args.seed
    )
except ValueError as exc:
    print(str(exc), file=sys.stderr)
    return 2
```
Any new failure surfaced by CSV writing (e.g., genuinely unwritable path per the code_context note) should raise `ValueError` from `scanner/seasonality.py` and be caught by this same `try/except ValueError` block in `main`, extending its scope rather than adding a second catch block.

**Thin-CLI shape to maintain**: `main` should stay a sequence of `scanner.seasonality` calls plus prints — no rendering/padding/CSV logic inline in `seasonality_by_week.py` itself, consistent with the module docstring's stated convention (lines 1-16) and D-11's discretion note ("planning determines... rendering logic... `scanner/seasonality.py` (or a sibling module)").

## Shared Patterns

### Pure-transform + thin-CLI-orchestrator split
**Source:** `scanner/seasonality.py` (whole module, Phase 5/6 precedent) vs. `seasonality_by_week.py::main`
**Apply to:** All new Phase 7 functions — computation/formatting logic lives in `scanner/seasonality.py` as pure functions (DataFrame/dataclass in, DataFrame/str out), `main` in `seasonality_by_week.py` handles all actual I/O (print, file write, sys.exit codes).

### `to_string(index=False)` for stdout tables
**Source:** `scan.py:243` (`display_df[display_cols].to_string(index=False)`)
**Apply to:** The SEAS-10 52-row table print (D-04) — no new dependency.

### `Path(...).mkdir(parents=True, exist_ok=True)` before file write
**Source:** `scan.py:282-283`
**Apply to:** CSV export (D-13), applied to `Path(args.output).parent` instead of a whole output directory.

### Explicit `None`/`pd.isna` guard before formatting a display cell
**Source:** `scan.py:205-240` (`_print_scan_results`)
**Apply to:** Every N/A-for-missing/insufficient_years cell in the padded table (D-01/D-02) and every optional numeric field in the summary text.

### Module-level static warning-text constant
**Source:** `scanner/report.py:37-47` (`_BIAS_SURVIVORSHIP`, `_BIAS_LOOK_AHEAD`)
**Apply to:** The static survivorship-bias warning string (D-09/D-10) and the multiple-comparison caveat text (D-05) — define as `_`-prefixed module constants in `scanner/seasonality.py`, printed verbatim.

### `ValueError`-with-message → CLI catches, prints to stderr, exits 2
**Source:** `seasonality_by_week.py:70-72`; also `resolve_sector`, `universe_path`, `check_thin_data` in `scanner/seasonality.py`
**Apply to:** Any new failure path in CSV writing that's worth surfacing distinctly (code_context note; not expected to trigger given D-13's auto-create/overwrite choice).

## No Analog Found

None — every new piece of Phase 7 logic has a direct or close analog already in the codebase (`report.py` for markdown/summary assembly and static bias-warning constants, `scan.py` for CSV export + mkdir + stdout table printing, and `scanner/seasonality.py` itself for the pure-function/orchestrator split and docstring convention).

## Metadata

**Analog search scope:** `scanner/report.py`, `scanner/seasonality.py`, `scan.py`, `seasonality_by_week.py`
**Files scanned:** 4
**Pattern extraction date:** 2026-07-10
