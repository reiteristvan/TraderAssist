"""Target-multiple sweep: replace the resistance-aware target with entry + k*risk."""
import statistics
from collections import Counter
import pandas as pd
from scanner.targets import apply_min_stop_floor
from exit_sweep import load_signals, SPLIT, _bars

def sim(sigs, time_stop=10, k=None):
    out=[]
    for sig in sigs:
        df=_bars(sig.ticker)
        if df is None: continue
        fut=df[df.index>pd.Timestamp(sig.date)]
        if fut.empty: continue
        entry=float(fut.iloc[0]["Open"])
        if entry<=sig.stop: continue
        eff=apply_min_stop_floor(sig.stop, entry, sig.atr)
        risk=entry-eff
        tgt = sig.target if k is None else entry + k*risk
        if entry>=tgt: continue
        px=rsn=None
        for i in range(len(fut)):
            b=fut.iloc[i]; lo,hi,cl=float(b["Low"]),float(b["High"]),float(b["Close"])
            if lo<=eff: px,rsn=eff,"stop"; break
            if hi>=tgt: px,rsn=tgt,"target"; break
            if i==time_stop-1: px,rsn=cl,"time_stop"; break
        if rsn is None: px,rsn=float(fut.iloc[-1]["Close"]),"time_stop"
        out.append((str(sig.date),(px-entry)/risk,rsn))
    return out

def rep(lbl,res):
    rs=[r for _,r,_ in res]; tr=[r for d,r,_ in res if d<SPLIT]; ho=[r for d,r,_ in res if d>=SPLIT]
    mix=Counter(x for _,_,x in res); tot=sum(mix.values())
    print(f"{lbl:22s}{len(rs):>6}{statistics.mean(rs):>+9.4f}{statistics.mean(tr):>+9.4f}"
          f"{statistics.mean(ho):>+9.4f}{100*sum(1 for r in rs if r>0)/len(rs):>7.1f}"
          f"{100*mix['target']/tot:>8.1f}")

sigs=load_signals()
print(f"{'variant':22s}{'n':>6}{'meanR':>9}{'trainR':>9}{'holdR':>9}{'win%':>7}{'tgt-hit%':>8}")
rep('current (resistance)', sim(sigs,10,None))
for k in (1.0,1.5,2.0,2.5,3.0,4.0):
    rep(f'target={k}R  ts=10', sim(sigs,10,k))
print()
rep('current  ts=20', sim(sigs,20,None))
for k in (1.5,2.0,3.0):
    rep(f'target={k}R  ts=20', sim(sigs,20,k))
