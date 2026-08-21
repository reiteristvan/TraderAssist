"""Tests for exit_rule_sweep.py -- the thin CLI wrapper.

No test names a backtest run directory, the SQLite database, the OHLCV
cache directory, or the module/function this tool reads prices through --
not in code, not in a comment, not in a docstring. Fixtures are built in
tmp_path; the bars-provider factory is monkeypatched to a dict-backed
callable so nothing here touches the real price cache.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

import exit_rule_sweep as cli
from scanner import exit_sweep


def _bars(rows, start="2020-01-02"):
    idx = pd.bdate_range(start=start, periods=len(rows))
    return pd.DataFrame(
        {
            "Open": [r[0] for r in rows],
            "High": [r[1] for r in rows],
            "Low": [r[2] for r in rows],
            "Close": [r[3] for r in rows],
            "Volume": [1000] * len(rows),
        },
        index=idx,
    )


def _signal_row(ticker, date, strategy="pullback", stop=90.0, target=120.0,
                 atr=2.0, qualified=True, score=50.0, confidence="MEDIUM",
                 close=100.0):
    return {
        "date": date, "ticker": ticker, "strategy": strategy, "score": score,
        "confidence": confidence, "stop": stop, "target": target, "atr": atr,
        "qualified": qualified, "close": close,
    }


def _write_run_dir(tmp_path, rows, name="fixture_run"):
    run_dir = tmp_path / name
    run_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(run_dir / "signals.parquet")
    return run_dir


# 45 bars per ticker, all safely inside (90, 120) -- clears every configured
# time stop (max 40) with a uniform time-stop-close resolution.
_SAFE_BAR_ROWS = [(100.0, 105.0, 96.0, 101.0)] * 45


def _build_fixture(tmp_path, n=30, strategy="pullback", name="fixture_run"):
    rows = []
    bars_map = {}
    for i in range(n):
        ticker = f"T{i}"
        month, day = (i % 12) + 1, (i % 27) + 1
        rows.append(_signal_row(ticker, f"2020-{month:02d}-{day:02d}", strategy=strategy))
        bars_map[ticker] = _bars(_SAFE_BAR_ROWS)
    run_dir = _write_run_dir(tmp_path, rows, name=name)
    return run_dir, bars_map


def _patch_bars(monkeypatch, bars_map):
    monkeypatch.setattr(
        exit_sweep, "make_bars_provider",
        lambda: (lambda ticker: bars_map.get(ticker)),
    )


# -- success paths ------------------------------------------------------------

def test_mode_time_exits_0_and_prints_row_per_time_stop(tmp_path, monkeypatch, capsys):
    run_dir, bars_map = _build_fixture(tmp_path)
    _patch_bars(monkeypatch, bars_map)

    result = cli.main(["--run-dir", str(run_dir), "--mode", "time"])

    captured = capsys.readouterr()
    assert result == 0
    assert "EQUIVALENCE GATE: PASS" in captured.out
    for ts in exit_sweep.TIME_STOPS:
        assert f"{ts:>10}" in captured.out or str(ts) in captured.out


def test_mode_all_exits_0_and_prints_all_three_tables_plus_gate(tmp_path, monkeypatch, capsys):
    run_dir, bars_map = _build_fixture(tmp_path)
    _patch_bars(monkeypatch, bars_map)

    result = cli.main(["--run-dir", str(run_dir), "--mode", "all"])

    captured = capsys.readouterr()
    assert result == 0
    assert "EQUIVALENCE GATE: PASS" in captured.out
    assert "time_stop" in captured.out
    assert "variant" in captured.out
    assert "tgt-hit%" in captured.out


# -- error paths ---------------------------------------------------------------

def test_missing_run_dir_exits_2_names_path_no_traceback(tmp_path, capsys):
    missing = tmp_path / "does-not-exist"

    result = cli.main(["--run-dir", str(missing), "--mode", "time"])

    captured = capsys.readouterr()
    assert result == 2
    assert str(missing) in captured.err
    assert "Traceback" not in captured.err


def test_zero_qualified_rows_exits_2_with_clear_message(tmp_path, monkeypatch, capsys):
    rows = [_signal_row("T0", "2020-01-02", qualified=False)]
    run_dir = _write_run_dir(tmp_path, rows)
    _patch_bars(monkeypatch, {"T0": _bars(_SAFE_BAR_ROWS)})

    result = cli.main(["--run-dir", str(run_dir), "--mode", "time"])

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert str(run_dir) in captured.err or "fixture_run" in captured.err


def test_malformed_split_exits_2_before_doing_any_work(tmp_path, capsys):
    # Points at a run dir that does not exist -- if the CLI tried to load
    # signals before validating --split, this would fail for the wrong
    # reason (missing directory) rather than the malformed split.
    missing = tmp_path / "never-created"

    result = cli.main(["--run-dir", str(missing), "--split", "2024-1-1", "--mode", "time"])

    captured = capsys.readouterr()
    assert result == 2
    assert "2024-1-1" in captured.err


def test_strategy_filter_excludes_all_rows_exits_2_not_empty_table(tmp_path, monkeypatch, capsys):
    run_dir, bars_map = _build_fixture(tmp_path, strategy="pullback")
    _patch_bars(monkeypatch, bars_map)

    result = cli.main(["--run-dir", str(run_dir), "--strategy", "breakout", "--mode", "time"])

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""


def test_failing_gate_suppresses_every_table(tmp_path, monkeypatch, capsys):
    run_dir, bars_map = _build_fixture(tmp_path)
    _patch_bars(monkeypatch, bars_map)

    def _drifted_check_equivalence(signals, bars_provider, time_stop=10, **kwargs):
        return exit_sweep.EquivalenceReport(
            time_stop=time_stop, n_real=1, n_variant=0,
            missing_keys=[("2020-01-02", "T0", "pullback")],
            extra_keys=[], mismatches=[], max_abs_diff=1.0, ok=False,
        )

    monkeypatch.setattr(exit_sweep, "check_equivalence", _drifted_check_equivalence)

    result = cli.main(["--run-dir", str(run_dir), "--mode", "all"])

    captured = capsys.readouterr()
    assert result == 3
    assert captured.out == ""
    assert "EQUIVALENCE GATE FAILED" in captured.err
    assert "time_stop" not in captured.out
    assert "variant" not in captured.out


# -- read-only guarantee -------------------------------------------------------

def test_run_dir_unchanged_after_successful_run(tmp_path, monkeypatch):
    run_dir, bars_map = _build_fixture(tmp_path)
    _patch_bars(monkeypatch, bars_map)

    parquet_path = run_dir / "signals.parquet"
    before_files = sorted(p.name for p in run_dir.iterdir())
    before_hash = hashlib.sha256(parquet_path.read_bytes()).hexdigest()

    result = cli.main(["--run-dir", str(run_dir), "--mode", "all"])

    after_files = sorted(p.name for p in run_dir.iterdir())
    after_hash = hashlib.sha256(parquet_path.read_bytes()).hexdigest()

    assert result == 0
    assert before_files == after_files
    assert before_hash == after_hash


# -- cp1252 stream-encoding regression (260712-h7l precedent) --------------

def test_cli_survives_cp1252_stream_encoding_success_path(tmp_path):
    helper = Path(__file__).resolve().parent / "_regression_cp1252_exit_sweep_helper.py"
    repo_root = Path(__file__).resolve().parent.parent

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    env.pop("PYTHONUTF8", None)

    result = subprocess.run(
        [sys.executable, str(helper), str(tmp_path), "success"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
    assert "UnicodeEncodeError" not in result.stderr
    assert "UnicodeEncodeError" not in result.stdout


def test_cli_survives_cp1252_stream_encoding_error_path(tmp_path):
    helper = Path(__file__).resolve().parent / "_regression_cp1252_exit_sweep_helper.py"
    repo_root = Path(__file__).resolve().parent.parent

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp1252"
    env.pop("PYTHONUTF8", None)

    result = subprocess.run(
        [sys.executable, str(helper), str(tmp_path), "missing"],
        cwd=str(repo_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "UnicodeEncodeError" not in result.stderr
