#!/usr/bin/env python3
"""IoU between class maps + metric table for the reference2 hand-repeatability check."""
import json, os, sys, itertools
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'out_hand')
NAMES = {0: 'bg', 1: 'rice', 2: 'nori', 3: 'salmon', 4: 'cucumber', 5: 'tamago', 6: 'avocado', 7: 'shrimp'}
KINDS = ['cucumber', 'tamago', 'salmon', 'avocado']


def mp(tag):
    return np.load(os.path.join(OUT, f'material_4{tag}.npy'))


def mj(tag):
    return json.load(open(os.path.join(OUT, f'metrics_4{tag}.json')))


def iou(a, b):
    """returns (mean IoU over non-bg classes present, roll-mask IoU, exact pixel agreement)"""
    per = {}
    for c in range(1, 8):
        A = a == c; B = b == c
        u = (A | B).sum()
        if u == 0:
            continue
        per[NAMES[c]] = round(float((A & B).sum()) / u, 4)
    ra, rb = a > 0, b > 0
    roll = float((ra & rb).sum()) / max((ra | rb).sum(), 1)
    exact = float((a == b).sum()) / a.size
    return per, round(roll, 4), round(exact, 4)


def row(tag):
    m = mj(tag)
    f = {x['kind']: x for x in m['fillings']}
    d = dict(tag=tag,
             Rout=m['Rout_T'], Rout_mean=m['Rout_mean_T'], Rout_med=m['Rout_median_T'],
             layers=m['layers_predicted'], turns=m['nori_turns'], turns_geom=m['nori_turns_geom'],
             cross_best=m['crossings_predicted_best'],
             cons=m['conservation'], riceJ=m['rice_J_min_run'],
             wr_fin=m['wrinkles'], wr_max=m['wrinkles_max'], wr_mat_max=m['wrinkles_mat_max'],
             cx=round(m['centroid_xy'][0], 3), cy=round(m['centroid_xy'][1], 3),
             order_ok=m['core_order_preserved'], stable=m['stable'],
             Rfold=m['R_fold_T'], tuck_eff=m['tuck_effective'],
             steps_press=m.get('phases', {}).get('press', None))
    for k in KINDS:
        d[f'r_{k}'] = f[k]['r_T'] if k in f else None
        d[f'phi_{k}'] = f[k]['phi_deg'] if k in f else None
        d[f'u_{k}'] = f[k]['rice_under_filling_T'] if k in f else None
    return d


def stat(rows, key):
    v = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
    if not v:
        return None
    return dict(mean=round(float(np.mean(v)), 4), sd=round(float(np.std(v, ddof=1)) if len(v) > 1 else 0.0, 4),
                min=round(float(min(v)), 4), max=round(float(max(v)), 4), n=len(v))


if __name__ == '__main__':
    groups = json.load(open(sys.argv[1]))          # {label: [tags]}
    allrows = {}
    print('=== PER-RUN METRICS ===')
    hdr = ['tag', 'Rout', 'Rout_mean', 'layers', 'turns_geom', 'cross_best', 'cons', 'riceJ',
           'wr_max', 'wr_mat_max', 'r_cucumber', 'phi_cucumber', 'u_cucumber', 'r_tamago', 'phi_tamago',
           'u_tamago', 'r_salmon', 'phi_salmon', 'u_salmon', 'r_avocado', 'phi_avocado', 'u_avocado',
           'cx', 'cy', 'Rfold']
    print('\t'.join(hdr))
    for lbl, tags in groups.items():
        for t in tags:
            r = row(t)
            allrows.setdefault(lbl, []).append(r)
            print('\t'.join(str(r.get(h)) for h in hdr))

    print('\n=== IoU WITHIN GROUP (all pairs) ===')
    for lbl, tags in groups.items():
        if len(tags) < 2:
            continue
        maps = {t: mp(t) for t in tags}
        for a, b in itertools.combinations(tags, 2):
            per, roll, exact = iou(maps[a], maps[b])
            print(f'{lbl:<10} {a} vs {b}: roll_IoU={roll} exact_px={exact} per_class={per}')

    print('\n=== GROUP STATS ===')
    keys = ['Rout', 'Rout_mean', 'layers', 'turns_geom', 'cross_best', 'cons', 'riceJ', 'wr_max',
            'wr_mat_max', 'Rfold'] + [f'{p}_{k}' for k in KINDS for p in ('r', 'phi', 'u')]
    print('group\tkey\tmean\tsd\tmin\tmax\tn')
    for lbl, rows in allrows.items():
        for k in keys:
            s = stat(rows, k)
            if s:
                print(f"{lbl}\t{k}\t{s['mean']}\t{s['sd']}\t{s['min']}\t{s['max']}\t{s['n']}")
    json.dump({k: v for k, v in allrows.items()}, open(os.path.join(HERE, 'rows.json'), 'w'), indent=1)
