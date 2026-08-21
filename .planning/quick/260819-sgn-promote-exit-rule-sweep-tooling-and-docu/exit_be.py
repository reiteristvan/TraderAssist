"""Breakeven-stop variant sweep. Read-only.

Replicates scanner.simulate.simulate_trades bar precedence EXACTLY, then adds an
optional breakeven rule: once a bar's high reaches entry + k*risk, the stop moves
to entry for SUBSEQUENT bars (pessimistic - the trigger bar itself is unchanged).

be_trigger=None must reproduce the real simulator exactly. That equivalence is
asserted before any variant is reported.
"""
import statistics
from collections import Counter
from functools import lru_cache

import pandas as pd

from scanner.data_store import get_history
from scanner.targets import apply_min_stop_floor
from exit_sweep import load_signals, SPLIT


@lru_cache(maxsize=None)
def _bars(t):
    return get_history(t)


def simulate_variant(sigs, time_stop=10, be_trigger=None):
    """Returns list of (signal_date, r_multiple, exit_reason)."""
    out = []
    for sig in sigs:
        df = _bars(sig.ticker)
        if df is None:
            continue
        future = df[df.index > pd.Timestamp(sig.date)]
        if future.empty:
            continue
        entry_bar = future.iloc[0]
        entry_px = float(entry_bar["Open"])
        if entry_px >= sig.target or entry_px <= sig.stop:
            continue  # gap_skip_up / gap_skip_down
        eff_stop = apply_min_stop_floor(sig.stop, entry_px, sig.atr)
        risk = entry_px - eff_stop
        future = future.iloc[1:] if False else future  # walk from entry bar itself
        cur_stop = eff_stop
        armed = False
        exit_px = exit_reason = None
        n = len(future)
        for i in range(n):
            bar = future.iloc[i]
            low, high, close = float(bar["Low"]), float(bar["High"]), float(bar["Close"])
            stop_hit = low <= cur_stop
            target_hit = high >= sig.target
            if stop_hit:
                exit_px, exit_reason = cur_stop, ("be_stop" if armed else "stop")
                break
            elif target_hit:
                exit_px, exit_reason = sig.target, "target"
                break
            elif i == time_stop - 1:
                exit_px, exit_reason = close, "time_stop"
                break
            # arm breakeven from the NEXT bar onward (pessimistic)
            if be_trigger is not None and not armed and high >= entry_px + be_trigger * risk:
                armed = True
                cur_stop = entry_px
        if exit_reason is None:
            exit_px, exit_reason = float(future.iloc[-1]["Close"]), "time_stop"
        out.append((str(sig.date), (exit_px - entry_px) / risk, exit_reason))
    return out


def rep(label, res):
    rs = [r for _, r, _ in res]
    tr = [r for d, r, _ in res if d < SPLIT]
    ho = [r for d, r, _ in res if d >= SPLIT]
    mix = Counter(x for _, _, x in res)
    tot = sum(mix.values())
    print(f"{label:22s}{len(rs):>6}{statistics.mean(rs):>+9.4f}{statistics.mean(tr):>+9.4f}"
          f"{statistics.mean(ho):>+9.4f}{100*sum(1 for r in rs if r>0)/len(rs):>7.1f}"
          f"{100*(mix['stop']+mix['be_stop'])/tot:>7.1f}{100*mix['target']/tot:>7.1f}"
          f"{100*mix['time_stop']/tot:>7.1f}")


if __name__ == '__main__':
    sigs = load_signals()
    print(f'{len(sigs)} qualified signals')

    # ---- equivalence gate: be_trigger=None must reproduce the real simulator
    base = simulate_variant(sigs, time_stop=10, be_trigger=None)
    m = statistics.mean([r for _, r, _ in base])
    print(f'equivalence check: variant(be=None) meanR={m:+.4f}  vs real +0.0293')
    assert abs(m - 0.0293) < 0.0005, f'HARNESS MISMATCH {m}'
    print('  PASS - variant simulator matches the real one\n')

    print(f"{'variant':22s}{'n':>6}{'meanR':>9}{'trainR':>9}{'holdR':>9}{'win%':>7}"
          f"{'stop%':>7}{'tgt%':>7}{'time%':>7}")
    rep('baseline ts=10', base)
    for k in (0.5, 0.75, 1.0, 1.5, 2.0):
        rep(f'BE@{k}R ts=10', simulate_variant(sigs, 10, k))
    print()
    for ts in (20, 40):
        rep(f'baseline ts={ts}', simulate_variant(sigs, ts, None))
        for k in (1.0, 1.5):
            rep(f'BE@{k}R ts={ts}', simulate_variant(sigs, ts, k))
