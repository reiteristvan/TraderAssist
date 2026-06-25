"""scan.py — unified CLI for the TraderAssist scanner package.

Usage:
  python scan.py scan   --strategy {pullback,breakout,both} [options]
  python scan.py refresh --file U.txt [--full]
  python scan.py backtest   (stub — E6)
  python scan.py journal    (stub — E9)
  python scan.py universe   (stub — E10)
  python scan.py worker     (stub — E12.6)

See CLAUDE.md EPIC E4.5.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date
from pathlib import Path

# Windows consoles default to cp1252; force UTF-8 so ✓/✗/– render correctly.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_tickers_file(path: str) -> list[str]:
    lines = Path(path).read_text().splitlines()
    return [l.strip().upper() for l in lines if l.strip() and not l.startswith("#")]


def _load_tickers_arg(arg: str) -> list[str]:
    return [t.strip().upper() for t in arg.split(",") if t.strip()]


def _resolve_tickers(args) -> list[str]:
    if hasattr(args, "ticker") and args.ticker:
        return [args.ticker.upper()]
    if hasattr(args, "tickers") and args.tickers:
        return _load_tickers_arg(args.tickers)
    if hasattr(args, "file") and args.file:
        return _load_tickers_file(args.file)
    # Default to sample universe
    sample = Path("universes/sample.txt")
    if sample.exists():
        tickers = _load_tickers_file(str(sample))
        print("[demo] No universe specified — using universes/sample.txt")
        return tickers
    print("No universe specified and universes/sample.txt not found.", file=sys.stderr)
    sys.exit(1)


def _strategy_fn_for(strategy: str, allow_earnings: bool = False):
    """Return the evaluate() callable for the given strategy name."""
    from scanner.strategies import pullback as pb, breakout as br

    if strategy == "pullback":
        return pb.evaluate
    elif strategy == "breakout":
        return br.evaluate
    raise ValueError(f"Unknown strategy: {strategy}")


# ── subcommand: scan ──────────────────────────────────────────────────────────

def cmd_scan(args) -> None:
    import pandas as pd
    from scanner.core import run_scan, last_closed_session, EARNINGS_BUFFER_DAYS
    import scanner.strategies.pullback as pb
    import scanner.strategies.breakout as br

    t0 = time.time()

    as_of: date | None = None
    if hasattr(args, "date") and args.date:
        as_of = date.fromisoformat(args.date)

    tickers = _resolve_tickers(args)
    strategies = (
        ["pullback", "breakout"] if args.strategy == "both" else [args.strategy]
    )

    label = f"{len(tickers)} ticker(s)"
    if as_of:
        label += f" as of {as_of}"
    print(f"Scan started — {label}, strateg{'ies' if len(strategies) > 1 else 'y'}: {', '.join(strategies)}")

    allow_earnings = getattr(args, "allow_earnings", False)

    frames = []
    for strat in strategies:
        print(f"\n── {strat.upper()} ─────────────────────────────────────")
        fn = _strategy_fn_for(strat, allow_earnings=allow_earnings)

        if allow_earnings:
            # Wrap evaluate to force-skip the earnings gate
            original_fn = fn
            def _allow_earnings_wrapper(ticker, df, ctx, verbose=False, _fn=original_fn):
                from dataclasses import replace
                from scanner.core import EvalContext
                ctx_no_earn = EvalContext(
                    as_of=ctx.as_of,
                    market_data=ctx.market_data,
                    weekly=ctx.weekly,
                    quality=ctx.quality,
                    days_to_earnings=None,  # None → skip gate
                )
                return _fn(ticker, df, ctx_no_earn, verbose=verbose)
            fn = _allow_earnings_wrapper

        verbose = getattr(args, "verbose", False) or (
            hasattr(args, "ticker") and args.ticker and len(tickers) == 1
        )

        df_out = run_scan(
            tickers,
            fn,
            as_of=as_of,
            verbose=verbose,
            capture_all=True,
            attach_risk=True,
            compute_conf=True,
        )

        if df_out.empty:
            print(f"[{strat}] No results.")
            continue

        df_out["strategy"] = strat

        # Apply filters
        if not getattr(args, "show_all", False):
            df_out = df_out[df_out["qualified"]]
        if getattr(args, "high_only", False):
            df_out = df_out[df_out.get("confidence", pd.Series()) == "HIGH"]
        if getattr(args, "min_score", None) is not None:
            df_out = df_out[df_out["score"] >= args.min_score]

        frames.append(df_out)

    if not frames:
        print("No qualified setups found.")
        return

    combined = pd.concat(frames, ignore_index=True)
    _print_scan_results(combined)

    if getattr(args, "csv", None):
        combined.to_csv(args.csv, index=False)
        print(f"\nSaved → {args.csv}")

    # ── E9.2 — write to scanner.db unless --no-journal ────────────────────────
    if not getattr(args, "no_journal", False):
        try:
            from scanner.journal import write_live_signals, write_ohlcv_snapshot
            from scanner.core import last_closed_session
            run_date = str(as_of) if as_of else str(last_closed_session())
            universe_label = getattr(args, "file", None) or getattr(args, "ticker", None) or ""
            qualified_rows = combined[combined["qualified"]].to_dict("records")
            for strat in strategies:
                strat_rows = [r for r in qualified_rows if r.get("strategy") == strat]
                n = write_live_signals(strat_rows, strat, run_date, universe=universe_label)
                if strat_rows:
                    print(f"  [{strat}] {n} signal(s) written to scanner.db (run_id={run_date})")
                else:
                    print(f"  [{strat}] 0 qualified signals — run row recorded (run_id={run_date})")
            # E12.7 — export OHLCV bars for the Diagnosis chart
            unique_tickers = list({r["ticker"] for r in qualified_rows})
            if unique_tickers:
                write_ohlcv_snapshot(unique_tickers)
        except Exception as exc:
            print(f"  [journal] DB write skipped: {exc}")

    elapsed = time.time() - t0
    m, s = divmod(elapsed, 60)
    print(f"\nDone in {int(m)}m {s:.0f}s" if m >= 1 else f"\nDone in {elapsed:.1f}s")


def _print_scan_results(df) -> None:
    import pandas as pd
    qualified = df[df["qualified"]] if "qualified" in df.columns else df
    print(f"\n{'=' * 60}")
    print(f"  {len(qualified)} qualified setup(s)")
    print(f"{'=' * 60}")
    cols = ["ticker", "strategy", "score", "confidence", "close",
            "suggested_stop", "suggested_target", "risk_reward"]
    display_cols = [c for c in cols if c in df.columns]
    if not qualified.empty:
        print(qualified[display_cols].to_string(index=False))
    print()


# ── subcommand: refresh ───────────────────────────────────────────────────────

def cmd_refresh(args) -> None:
    from scanner.data_store import refresh_universe
    tickers = _resolve_tickers(args)
    if getattr(args, "full", False):
        import scanner.data_store as ds
        print(f"Full re-fetch for {len(tickers)} tickers (may take several minutes)...")
        for t in tickers:
            path = ds._cache_path(t)
            if path.exists():
                path.unlink()
        report = refresh_universe(tickers)
    else:
        report = refresh_universe(tickers)
    print(f"Refresh complete: {len(report.succeeded)} ok, "
          f"{len(report.invalidated)} invalidated, {len(report.failed)} failed.")
    for t, err in report.failed:
        print(f"  FAILED: {t}: {err}", file=sys.stderr)


# ── stub subcommands ──────────────────────────────────────────────────────────

def cmd_backtest(args) -> None:
    import json
    from pathlib import Path
    from datetime import date as _date
    from dataclasses import asdict

    import pandas as pd
    from scanner.backtest import generate_signals
    from scanner.simulate import simulate_trades
    from scanner.report import render_report
    from scanner.data_store import get_history

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    tickers = _resolve_tickers(args)
    start = _date.fromisoformat(args.start)
    end = _date.fromisoformat(args.end)
    time_stop = int(args.time_stop)
    earn_gate = (args.earnings_gate == "on")

    print(f"Generating signals: {args.strategy}, {len(tickers)} tickers, {start}→{end}")
    signals = generate_signals(
        universe=tickers,
        start=start,
        end=end,
        strategy=args.strategy,
        capture_near_misses=int(args.capture_near_misses),
        earnings_gate=earn_gate,
    )

    # Persist signals
    sig_dicts = []
    for s in signals:
        d = asdict(s)
        d["date"] = str(d["date"])
        d["failed_gates"] = ";".join(d["failed_gates"])
        sig_dicts.append(d)
    sig_df = pd.DataFrame(sig_dicts)
    sig_df.to_parquet(out_dir / "signals.parquet", index=False)
    print(f"  {len(signals)} signals ({sum(s.qualified for s in signals)} qualified)")

    # Simulate
    def _bars(ticker):
        return get_history(ticker)

    q_signals = [s for s in signals if s.qualified]
    nm_signals = [s for s in signals if not s.qualified]
    q_trades = simulate_trades(q_signals, _bars, entry=args.entry, time_stop=time_stop)
    nm_trades = simulate_trades(nm_signals, _bars, entry=args.entry, time_stop=time_stop)

    all_trade_dicts = []
    for t in q_trades + nm_trades:
        d = asdict(t)
        for k in ("signal_date", "entry_date", "exit_date"):
            if d[k] is not None:
                d[k] = str(d[k])
        d["failed_gates"] = ";".join(d["failed_gates"])
        d["flags"] = json.dumps(d["flags"])
        all_trade_dicts.append(d)
    pd.DataFrame(all_trade_dicts).to_parquet(out_dir / "trades.parquet", index=False)

    # Run meta
    try:
        import subprocess
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        git_hash = "unknown"

    run_meta = {
        "strategy": args.strategy,
        "universe_size": len(tickers),
        "start": str(start),
        "end": str(end),
        "earnings_gate": args.earnings_gate,
        "capture_near_misses": args.capture_near_misses,
        "time_stop": time_stop,
        "entry": args.entry,
        "git_hash": git_hash,
        "total_signals": len(signals),
        "qualified_signals": sum(s.qualified for s in signals),
    }
    (out_dir / "run_meta.json").write_text(json.dumps(run_meta, indent=2))

    # Report
    md, json_data = render_report(signals, q_trades, nm_trades, run_meta)
    (out_dir / "report.md").write_text(md, encoding="utf-8")
    (out_dir / "report.json").write_text(json.dumps(json_data, indent=2, default=str))

    print(f"  Trades simulated: {len(q_trades)} qualified, {len(nm_trades)} near-miss")
    print(f"  Output → {out_dir}/")
    print("    signals.parquet  trades.parquet  report.md  report.json  run_meta.json")

    # ── E9.4 — ingest into scanner.db ─────────────────────────────────────────
    try:
        from scanner.journal import write_backtest_to_db
        from datetime import datetime as _dtime
        run_meta["started_at"] = run_meta.get("started_at", _dtime.now().isoformat())
        run_meta["finished_at"] = _dtime.now().isoformat()
        write_backtest_to_db(
            signals, q_trades, nm_trades,
            run_id=run_meta.get("git_hash", "unknown") + "_" + run_meta["start"],
            run_meta=run_meta,
            metrics=json_data,  # full report: metrics + score_buckets + gate_attribution
            biases=json_data["biases"],
        )
        print("  Backtest ingested into scanner.db")
    except Exception as exc:
        print(f"  [db] Ingest skipped: {exc}")


def cmd_journal(args) -> None:
    subcmd = getattr(args, "journal_cmd", None)
    if subcmd == "resolve":
        from scanner.journal import resolve_open_signals
        result = resolve_open_signals()
        print(f"Resolved: {result['resolved']}  Open (in-flight): {result['open']}  "
              f"Failures: {result['failures']}")
    elif subcmd == "compare":
        from scanner.journal import compare_with_backtest
        result = compare_with_backtest(args.backtest)
        print(f"\nLive (n={result['live_n']}):     "
              f"E(R)={result['live_expectancy_r']}, W={result['live_win_rate']}")
        print(f"Backtest {args.backtest} (n={result['backtest_n']}): "
              f"E(R)={result['backtest_expectancy_r']}, W={result['backtest_win_rate']}")
        if result.get("warning"):
            print(f"\n⚠ {result['warning']}")
    else:
        print("Usage: scan.py journal {resolve|compare --backtest <run_id>}")


def cmd_universe(args) -> None:
    subcmd = getattr(args, "universe_cmd", None)
    if subcmd == "build":
        from scanner.universe import build_universe
        tickers = build_universe(args.index, out_path=Path(args.out))
        print(f"Built {args.index.upper()} universe: {len(tickers)} tickers → {args.out}")
    elif subcmd == "audit":
        from scanner.universe import audit_universe
        result = audit_universe(Path(args.file))
        print(f"OK: {len(result['ok'])} tickers")
        for t, err in result["failed"]:
            print(f"  FAILED: {t}: {err}", file=sys.stderr)
        if result["failed"]:
            print(f"{len(result['failed'])} ticker(s) could not be fetched.", file=sys.stderr)
    else:
        print("Usage: scan.py universe {build --index sp500|sp400|sp600 --out FILE | audit --file FILE}")


def _process_diagnose_job(conn, job: dict) -> str:
    """Run a diagnose job; returns the new signal's row id as result_ref."""
    import json as _json
    from scanner import store_db as _db

    params = _json.loads(job.get("params_json") or "{}")
    ticker = params.get("ticker", "").strip().upper()
    strategy = params.get("strategy", "pullback")
    if not ticker:
        raise ValueError("diagnose job missing 'ticker' param")
    if strategy == "pullback":
        from scanner.strategies.pullback import evaluate
    elif strategy == "breakout":
        from scanner.strategies.breakout import evaluate
    else:
        raise ValueError(f"unknown strategy: {strategy!r}")

    from scanner.core import run_scan
    df_out = run_scan([ticker], evaluate, as_of=None, verbose=False,
                      capture_all=True, attach_risk=True, compute_conf=True)
    if df_out.empty:
        raise ValueError(f"no data available for {ticker}")

    row = df_out.iloc[0].to_dict()
    run_id = f"diagnose_{job['id']}"
    gate_detail = row.get("gate_detail") or []
    failed = row.get("failed_gates") or []

    sig = {
        "date": str(row.get("as_of", "")),
        "ticker": ticker,
        "strategy": strategy,
        "source": "diagnose",
        "run_id": run_id,
        "score": row.get("score"),
        "confidence": row.get("confidence"),
        "stop": row.get("suggested_stop"),
        "target": row.get("suggested_target"),
        "atr": row.get("atr"),
        "qualified": 1 if row.get("qualified") else 0,
        "failed_gates": ";".join(failed) if isinstance(failed, list) else (failed or ""),
        "close": row.get("close"),
        "gate_detail_json": _json.dumps(gate_detail),
        "ath_zone": row.get("ath_zone"),
    }
    cur = conn.execute(
        """INSERT OR REPLACE INTO signals
           (date, ticker, strategy, source, run_id, score, confidence,
            stop, target, atr, qualified, failed_gates, close,
            gate_detail_json, ath_zone)
           VALUES (:date, :ticker, :strategy, :source, :run_id, :score, :confidence,
                   :stop, :target, :atr, :qualified, :failed_gates, :close,
                   :gate_detail_json, :ath_zone)""",
        sig,
    )
    conn.commit()
    # E12.7 — export OHLCV bars for the Diagnosis chart
    try:
        from scanner.journal import write_ohlcv_snapshot
        write_ohlcv_snapshot([ticker])
    except Exception:
        pass
    return str(cur.lastrowid)


_JOB_HANDLERS: dict = {
    "diagnose": _process_diagnose_job,
}


def cmd_worker(args) -> None:
    """Process queued jobs from the jobs table. --once drains the queue and exits."""
    import time as _time
    from scanner import store_db as _db

    once = getattr(args, "once", False)
    poll_interval = getattr(args, "poll_interval", 10)

    conn = _db.get_connection()
    _db.migrate(conn=conn)

    stale = _db.reset_stale_jobs(conn)
    if stale:
        print(f"worker: re-queued {stale} stale job(s)")

    print(f"worker: started (once={once}, poll={poll_interval}s)")
    while True:
        job = _db.claim_next_job(conn)
        if job is None:
            if once:
                print("worker: queue empty, exiting")
                break
            _time.sleep(poll_interval)
            continue

        kind = job["kind"]
        jid = job["id"]
        print(f"worker: processing job #{jid} ({kind})")
        handler = _JOB_HANDLERS.get(kind)
        if handler is None:
            _db.fail_job(conn, jid, f"unknown job kind: {kind!r}")
            print(f"worker: job #{jid} failed — unknown kind")
            continue
        try:
            result_ref = handler(conn, job)
            _db.complete_job(conn, jid, result_ref)
            print(f"worker: job #{jid} done — result_ref={result_ref}")
        except Exception as exc:
            _db.fail_job(conn, jid, str(exc))
            print(f"worker: job #{jid} error — {exc}", file=sys.stderr)


# ── argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scan.py",
        description="TraderAssist swing scanner — scan | refresh | backtest | journal | universe | worker",
    )
    sub = p.add_subparsers(dest="command")

    # ── scan ──────────────────────────────────────────────────────────────────
    scan_p = sub.add_parser("scan", help="Evaluate tickers against a strategy")
    scan_p.add_argument("--strategy", choices=["pullback", "breakout", "both"],
                        default="pullback")
    grp = scan_p.add_mutually_exclusive_group()
    grp.add_argument("--file", metavar="PATH", help="Newline-separated ticker file")
    grp.add_argument("--tickers", metavar="A,B,...", help="Comma-separated tickers")
    grp.add_argument("--ticker", metavar="TICKER", help="Single ticker (implies --verbose)")
    scan_p.add_argument("--csv", metavar="PATH", help="Save results to CSV")
    scan_p.add_argument("--show-all", action="store_true",
                        help="Include non-qualifying setups in output")
    scan_p.add_argument("--verbose", action="store_true",
                        help="Print full gate log per ticker")
    scan_p.add_argument("--high-only", action="store_true",
                        help="Show only HIGH confidence setups")
    scan_p.add_argument("--min-score", type=float, metavar="N",
                        help="Minimum score threshold")
    scan_p.add_argument("--date", metavar="YYYY-MM-DD",
                        help="Evaluate as of historical date (point-in-time)")
    scan_p.add_argument("--allow-earnings", action="store_true",
                        help="Skip the earnings-proximity gate for both strategies")
    scan_p.add_argument("--no-journal", action="store_true",
                        help="Do not write results to scanner.db (default: write)")

    # ── refresh ───────────────────────────────────────────────────────────────
    ref_p = sub.add_parser("refresh", help="Warm the Parquet OHLCV cache")
    ref_grp = ref_p.add_mutually_exclusive_group()
    ref_grp.add_argument("--file", metavar="PATH")
    ref_grp.add_argument("--tickers", metavar="A,B,...")
    ref_p.add_argument("--full", action="store_true",
                       help="Force full re-fetch (period=max) for all tickers")

    # ── backtest ──────────────────────────────────────────────────────────────
    bt_p = sub.add_parser("backtest", help="Run historical backtest")
    bt_p.add_argument("--strategy", choices=["pullback", "breakout"], default="pullback")
    bt_grp = bt_p.add_mutually_exclusive_group()
    bt_grp.add_argument("--file", metavar="PATH", help="Universe ticker file")
    bt_grp.add_argument("--tickers", metavar="A,B,...")
    bt_p.add_argument("--start", metavar="YYYY-MM-DD", required=True)
    bt_p.add_argument("--end", metavar="YYYY-MM-DD", required=True)
    bt_p.add_argument("--out", metavar="DIR", default="runs/latest",
                      help="Output directory for artifacts")
    bt_p.add_argument("--earnings-gate", choices=["on", "off"], default="on",
                      help="Enable/disable earnings-proximity gate (default: on)")
    bt_p.add_argument("--capture-near-misses", type=int, default=1, metavar="N",
                      help="Capture near-misses failing at most N gates (default: 1)")
    bt_p.add_argument("--time-stop", type=int, default=10, metavar="SESSIONS",
                      help="Exit after N sessions if neither stop nor target hit (default: 10)")
    bt_p.add_argument("--entry", choices=["next_open", "signal_close"], default="next_open",
                      help="Entry price convention (default: next_open)")

    # ── journal ───────────────────────────────────────────────────────────────
    jnl_p = sub.add_parser("journal", help="Live signal journal (resolve, compare)")
    jnl_sub = jnl_p.add_subparsers(dest="journal_cmd")
    jnl_sub.add_parser("resolve",
                       help="Resolve open live signals against subsequent bars")
    cmp_p = jnl_sub.add_parser("compare",
                                help="Compare live expectancy vs a backtest run")
    cmp_p.add_argument("--backtest", metavar="RUN_ID", required=True,
                       help="Backtest run_id to compare against")

    # ── universe ──────────────────────────────────────────────────────────────
    univ_p = sub.add_parser("universe", help="Universe builder and audit")
    univ_sub = univ_p.add_subparsers(dest="universe_cmd")
    bld_p = univ_sub.add_parser("build", help="Build a universe from an S&P index")
    bld_p.add_argument("--index", choices=["sp500", "sp400", "sp600"], required=True)
    bld_p.add_argument("--out", metavar="PATH", required=True,
                       help="Output file path (e.g. universes/sp600.txt)")
    aud_p = univ_sub.add_parser("audit", help="Audit a universe file for bad tickers")
    aud_p.add_argument("--file", metavar="PATH", required=True)

    # ── worker (E12.6) ───────────────────────────────────────────────────────
    wk_p = sub.add_parser("worker", help="Process queued jobs (on-demand diagnose/backtest)")
    wk_p.add_argument("--once", action="store_true",
                      help="Drain the queue once and exit (vs. continuous loop)")
    wk_p.add_argument("--poll-interval", type=int, default=10, metavar="SEC",
                      help="Seconds to wait between queue polls in continuous mode (default 10)")

    return p


def main(argv=None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch = {
        "scan":     cmd_scan,
        "refresh":  cmd_refresh,
        "backtest": cmd_backtest,
        "journal":  cmd_journal,
        "universe": cmd_universe,
        "worker":   cmd_worker,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
