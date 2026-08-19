"""Pooled winner/loser feature analysis with train/holdout separation.

Read-only against data/scanner.db. No re-backtest.
Train  = signals dated < 2024-01-01   (selection window)
Holdout= signals dated >= 2024-01-01  (confirmation window, touched once)
"""
import sqlite3, statistics, random
from collections import defaultdict

random.seed(11)
RUN = '4f4fe68_2021-01-01_20260702_090418'
SPLIT = '2024-01-01'
DB = 'data/scanner.db'

c = sqlite3.connect(DB)
rows = c.execute("""
    select date, ticker, r_multiple, score, confidence, atr, close,
           target_r, target_atr, industry_momentum, industry_above_50ma,
           industry_rank_pct
    from signals
    where run_id=? and qualified=1 and r_multiple is not null
    order by date
""", (RUN,)).fetchall()

def num(v):
    """Coerce to float; None for non-numeric (confidence may be a text label)."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


recs = []
for (d, tk, r, score, conf, atr, close, tr, ta, imom, i50, irank) in rows:
    close, atr = num(close), num(atr)
    if not close or close <= 0 or atr is None:
        continue
    recs.append({
        'date': d, 'ticker': tk, 'r': float(r),
        'score': num(score),
        'confidence': {'LOW': 0.0, 'MEDIUM': 1.0, 'HIGH': 2.0}.get(conf),
        'conf_label': conf,
        'atr_pct': atr / close * 100,
        'close': close, 'target_r': num(tr), 'target_atr': num(ta),
        'industry_momentum': num(imom),
        'industry_above_50ma': num(i50),
        'industry_rank_pct': num(irank),
    })

FEATURES = ['score', 'confidence', 'atr_pct', 'close', 'target_r', 'target_atr',
            'industry_momentum', 'industry_rank_pct']

train = [x for x in recs if x['date'] < SPLIT]
hold = [x for x in recs if x['date'] >= SPLIT]


def mblocks(rs):
    by = defaultdict(list)
    for x in rs:
        by[x['date'][:7]].append(x['r'])
    return by


def boot_ci(rs, n=2000):
    """Month-block bootstrap CI on mean R."""
    if len(rs) < 20:
        return (float('nan'), float('nan'))
    by = mblocks(rs)
    ms = list(by)
    out = []
    for _ in range(n):
        s = []
        for _ in range(len(ms)):
            s += by[random.choice(ms)]
        out.append(statistics.mean(s))
    out.sort()
    k = int(n * 0.025)
    return (out[k], out[-k - 1])


def mean_r(rs):
    return statistics.mean([x['r'] for x in rs]) if rs else float('nan')


def q(vals, p):
    v = sorted(vals)
    i = max(0, min(len(v) - 1, int(round(p * (len(v) - 1)))))
    return v[i]


print(f"trades: train(<{SPLIT}) n={len(train)}  holdout(>={SPLIT}) n={len(hold)}")
lo, hi = boot_ci(train)
print(f"BASELINE train   mean R = {mean_r(train):+.3f}   95% CI [{lo:+.3f}, {hi:+.3f}]")
lo, hi = boot_ci(hold)
print(f"BASELINE holdout mean R = {mean_r(hold):+.3f}   95% CI [{lo:+.3f}, {hi:+.3f}]")
print()

# ── categorical features: straight train/holdout comparison ───────────────────
print("CATEGORICAL FEATURES (mean R by level)")
print(f"{'level':32s} {'trainN':>6s} {'trainR':>8s} {'holdN':>6s} {'holdR':>8s}")
print('-' * 66)
for key, levels in (('conf_label', ['LOW', 'MEDIUM', 'HIGH']),
                    ('industry_above_50ma', [0.0, 1.0])):
    for lv in levels:
        t = [x for x in train if x[key] == lv]
        h = [x for x in hold if x[key] == lv]
        print(f"{key + '=' + str(lv):32s} {len(t):6d} {mean_r(t):+8.3f} "
              f"{len(h):6d} {mean_r(h):+8.3f}")
print()

# ── selection on TRAIN only ────────────────────────────────────────────────────
cands = []
n_tests = 0
for f in FEATURES:
    tv = [x[f] for x in train if x[f] is not None]
    if len(tv) < 200:
        print(f"  skip {f}: only {len(tv)} non-null in train")
        continue
    for p, pname in ((0.25, 'Q1'), (0.50, 'median'), (0.75, 'Q3')):
        thr = q(tv, p)
        for direction in ('>=', '<'):
            n_tests += 1
            kept = [x for x in train if x[f] is not None and
                    (x[f] >= thr if direction == '>=' else x[f] < thr)]
            if len(kept) < 150:
                continue
            cands.append({
                'feature': f, 'thr': thr, 'dir': direction, 'pname': pname,
                'train_n': len(kept), 'train_r': mean_r(kept),
                'lift': mean_r(kept) - mean_r(train),
            })

cands.sort(key=lambda x: -x['train_r'])
print(f"tests evaluated on train: {n_tests}  "
      f"(expect ~{n_tests * 0.05:.0f} spurious 'winners' at p<0.05)")
print()
print("TOP 8 RULES BY TRAIN PERFORMANCE  ->  applied UNCHANGED to holdout")
print(f"{'rule':44s} {'trainN':>6s} {'trainR':>8s} {'holdN':>6s} {'holdR':>8s} "
      f"{'holdout 95% CI':>20s}")
print('-' * 100)
for cd in cands[:8]:
    f, thr, direction = cd['feature'], cd['thr'], cd['dir']
    kept_h = [x for x in hold if x[f] is not None and
              (x[f] >= thr if direction == '>=' else x[f] < thr)]
    lo, hi = boot_ci(kept_h)
    rule = f"{f} {direction} {thr:.3g} ({cd['pname']})"
    print(f"{rule:44s} {cd['train_n']:6d} {cd['train_r']:+8.3f} "
          f"{len(kept_h):6d} {mean_r(kept_h):+8.3f} "
          f"[{lo:+.3f}, {hi:+.3f}]")

print()
print("Rank correlation of rule performance train -> holdout:")
xs = []
for cd in cands:
    f, thr, direction = cd['feature'], cd['thr'], cd['dir']
    kept_h = [x for x in hold if x[f] is not None and
              (x[f] >= thr if direction == '>=' else x[f] < thr)]
    if len(kept_h) >= 150:
        xs.append((cd['train_r'], mean_r(kept_h)))
if len(xs) >= 5:
    a = [p[0] for p in xs]
    b = [p[1] for p in xs]
    ra = {v: i for i, v in enumerate(sorted(a))}
    rb = {v: i for i, v in enumerate(sorted(b))}
    n = len(xs)
    d2 = sum((ra[p[0]] - rb[p[1]]) ** 2 for p in xs)
    rho = 1 - 6 * d2 / (n * (n * n - 1))
    print(f"  Spearman rho = {rho:+.3f} over {n} rules "
          f"(rho~0 => train ranking carries no information)")
