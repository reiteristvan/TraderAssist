"""Exit-rule sweep on an existing backtest signal set. Read-only.

Phase 1 uses the REAL scanner.simulate.simulate_trades with varied time_stop,
so there is no reimplementation risk. It first validates that re-simulating at
time_stop=10 reproduces the stored r_multiple values.
"""
import statistics
import sys
from datetime import date
from functools import lru_cache

import pandas as pd

from scanner.data_store import get_history
from scanner.simulate import Signal, simulate_trades

RUN_DIR = 'runs/pb_2021_2026_v10'
SPLIT = '2024-01-01'


@lru_cache(maxsize=None)
def _bars(ticker):
    return get_history(ticker)


def load_signals(qualified_only=True):
    df = pd.read_parquet(f'{RUN_DIR}/signals.parquet')
    if qualified_only:
        df = df[df['qualified']]
    sigs = []
    for r in df.itertuples(index=False):
        d = r.date
        if isinstance(d, str):
            d = date.fromisoformat(d)
        elif hasattr(d, 'date'):
            d = d.date()
        sigs.append(Signal(
            date=d, ticker=r.ticker, strategy=r.strategy, score=float(r.score),
            confidence=r.confidence, stop=float(r.stop), target=float(r.target),
            atr=float(r.atr), qualified=bool(r.qualified),
            failed_gates=[], close=float(r.close),
        ))
    return sigs


def run(sigs, time_stop):
    return simulate_trades(sigs, _bars, time_stop=time_stop)


def summarize(trades):
    """Return (n, meanR, trainR, holdR, win%, exit-mix) for resolved trades."""
    res = [t for t in trades if t.r_multiple is not None]
    rs = [t.r_multiple for t in res]
    tr = [t.r_multiple for t in res if str(t.signal_date) < SPLIT]
    ho = [t.r_multiple for t in res if str(t.signal_date) >= SPLIT]
    from collections import Counter
    mix = Counter(t.exit_reason for t in res)
    return {
        'n': len(res),
        'mean': statistics.mean(rs) if rs else float('nan'),
        'train': statistics.mean(tr) if tr else float('nan'),
        'hold': statistics.mean(ho) if ho else float('nan'),
        'win': 100 * sum(1 for r in rs if r > 0) / len(rs) if rs else float('nan'),
        'mix': mix,
    }


if __name__ == '__main__':
    print('loading signals...', flush=True)
    sigs = load_signals()
    print(f'  {len(sigs)} qualified signals', flush=True)

    # ---- validation: re-simulating at the original time_stop=10 must reproduce the run
    print('validating harness against stored outcomes (time_stop=10)...', flush=True)
    base = run(sigs, 10)
    b = summarize(base)
    print(f"  re-simulated: n={b['n']} meanR={b['mean']:+.4f} win={b['win']:.1f}%")
    print("  stored      : n=3813 meanR=+0.0293 win=35.9%   <- must match")
    print()

    print(f"{'time_stop':>10}{'n':>7}{'meanR':>9}{'trainR':>9}{'holdR':>9}{'win%':>7}"
          f"{'stop%':>7}{'tgt%':>7}{'time%':>7}")
    for ts in (5, 8, 10, 15, 20, 30, 40):
        t = summarize(run(sigs, ts))
        m = t['mix']
        tot = sum(m.values())
        print(f"{ts:>10}{t['n']:>7}{t['mean']:>+9.4f}{t['train']:>+9.4f}{t['hold']:>+9.4f}"
              f"{t['win']:>7.1f}{100*m['stop']/tot:>7.1f}{100*m['target']/tot:>7.1f}"
              f"{100*m['time_stop']/tot:>7.1f}", flush=True)
