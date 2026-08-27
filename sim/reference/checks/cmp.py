#!/usr/bin/env python
"""Determinism + hand-input analysis for the sushi reference (layout 4).

Reads checks/out/metrics_4_<tag>.json and material_4_<tag>.npy, reports
per-tag metrics, pairwise IoU of class maps, and signal-vs-noise for --speed/--press.
"""
import json, os, sys, math, itertools
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')

def load(tag):
    with open(os.path.join(OUT, f'metrics_4_{tag}.json')) as f:
        m = json.load(f)
    p = os.path.join(OUT, f'material_4_{tag}.npy')
    m['_map'] = np.load(p) if os.path.exists(p) else None
    return m

def iou(a, b, cls=None):
    """IoU of the occupied region (cls=None) or of one class."""
    A = (a > 0) if cls is None else (a == cls)
    B = (b > 0) if cls is None else (b == cls)
    u = np.logical_or(A, B).sum()
    return float(np.logical_and(A, B).sum() / u) if u else 1.0

def px_agree(a, b):
    return float((a == b).mean())

def core_map(m):
    return {c['kind']: (c['r_T'], c['phi_deg']) for c in m.get('core', [])}

def row(tag, m):
    ruf = m.get('rice_under_filling_T', {})
    cm = core_map(m)
    return dict(tag=tag, speed=m['speed'], press=m['press'], seed=m['seed'],
                Rout=m['Rout_T'], Rmed=m['Rout_median_T'], Rmean=m['Rout_mean_T'],
                Rmin=m['Rout_min_T'], Rpred=m['Rout_pred_T'],
                turns=m['nori_turns'], turns_geom=m['nori_turns_geom'],
                d_core=m['turns_minus_predicted_core'], d_lit=m['turns_minus_predicted'],
                cons=m['conservation'], cons_rice=m['conservation_rice'],
                ruf=ruf, core=cm, order=tuple(m['core_order_by_phi']),
                tail=m['tail_outside_frac'], sec=m['timing']['seconds'])

FILL = ['cucumber', 'tamago', 'salmon', 'avocado']

def stats(vals):
    v = np.array(vals, float)
    return v.mean(), v.std(ddof=1) if len(v) > 1 else 0.0, v.max() - v.min()

if __name__ == '__main__':
    tags = sys.argv[1:] or ['detA','detB','detC','detD','s2','s3',
                            'sp05','sp05b','sp20','sp20b','pr05','pr05b','pr20','pr20b']
    R = {t: row(t, load(t)) for t in tags}
    M = {t: load(t)['_map'] for t in tags}

    hdr = f"{'tag':7}{'sp':>5}{'pr':>5}{'sd':>3}{'Rout':>7}{'Rmed':>7}{'Rmin':>7}{'turns':>7}{'dcore':>7}{'cons':>7}{'cons_r':>8}{'tail':>8}"
    print(hdr); print('-'*len(hdr))
    for t in tags:
        r = R[t]
        print(f"{t:7}{r['speed']:>5}{r['press']:>5}{r['seed']:>3}{r['Rout']:>7.3f}{r['Rmed']:>7.3f}"
              f"{r['Rmin']:>7.3f}{r['turns']:>7.3f}{r['d_core']:>7.3f}{r['cons']:>7.4f}{r['cons_rice']:>8.4f}{r['tail']:>8.5f}")

    print('\n--- rice_under_filling_T ---')
    print(f"{'tag':7}" + ''.join(f'{f:>10}' for f in FILL) + f"{'order_by_phi':>44}")
    for t in tags:
        r = R[t]
        print(f"{t:7}" + ''.join(f"{r['ruf'].get(f, float('nan')):>10.3f}" for f in FILL)
              + f"  {'>'.join(k[:3] for k in r['order']):>42}")

    print('\n--- core (r_T / phi_deg) ---')
    print(f"{'tag':7}" + ''.join(f'{f[:4]+" r":>9}{f[:4]+" phi":>11}' for f in FILL))
    for t in tags:
        c = R[t]['core']
        s = ''
        for f in FILL:
            if f in c: s += f'{c[f][0]:>9.3f}{c[f][1]:>11.1f}'
            else: s += f'{"-":>9}{"-":>11}'
        print(f'{t:7}' + s)

    def group(ts, label):
        print(f'\n=== {label}: n={len(ts)} ({", ".join(ts)}) ===')
        out = {}
        for k in ['Rout','Rmed','Rmin','turns','cons','cons_rice','d_core']:
            m, s, rng = stats([R[t][k] for t in ts])
            out[k] = (m, s, rng)
            print(f'  {k:9} mean {m:8.4f}  sd {s:8.4f}  range {rng:8.4f}')
        for f in FILL:
            vals = [R[t]['ruf'].get(f, float("nan")) for t in ts]
            m, s, rng = stats(vals); out['ruf_'+f] = (m, s, rng)
            print(f'  ruf.{f:8} mean {m:7.3f}  sd {s:7.3f}  range {rng:7.3f}')
        for f in FILL:
            rs = [R[t]['core'][f][0] for t in ts if f in R[t]['core']]
            ph = [R[t]['core'][f][1] for t in ts if f in R[t]['core']]
            m, s, rng = stats(rs); out['r_'+f] = (m, s, rng)
            mp, sp_, rp = stats(ph); out['phi_'+f] = (mp, sp_, rp)
            print(f'  core.{f:8} r {m:6.3f}±{s:.3f} (rng {rng:.3f})   phi {mp:7.1f}±{sp_:5.1f} (rng {rp:5.1f})')
        return out

    det = [t for t in tags if t.startswith('det')]
    seedg = det + [t for t in tags if t in ('s2','s3')]
    NOISE = group(det, 'REPEAT NOISE, identical args+seed') if det else None
    SEEDN = group(seedg, 'SEED+REPEAT NOISE') if len(seedg) > 1 else None

    if det:
        print('\n=== class-map IoU / pixel agreement ===')
        base = det[0]
        for a, b in itertools.combinations(tags, 2):
            if M[a] is None or M[b] is None: continue
            if not (a in det and b in det) and not (a.rstrip('b') == b.rstrip('b')): continue
            print(f'  {a:6} vs {b:6}  IoU(all) {iou(M[a],M[b]):.4f}   '
                  f'IoU(rice) {iou(M[a],M[b],1):.4f}  IoU(nori) {iou(M[a],M[b],2):.4f}  '
                  f'px= {px_agree(M[a],M[b]):.4f}   identical={np.array_equal(M[a],M[b])}')
        print('\n  cross-condition (for scale):')
        for b in tags:
            if b in det or M[b] is None: continue
            print(f'  {base:6} vs {b:6}  IoU(all) {iou(M[base],M[b]):.4f}   '
                  f'IoU(rice) {iou(M[base],M[b],1):.4f}  IoU(nori) {iou(M[base],M[b],2):.4f}  '
                  f'px= {px_agree(M[base],M[b]):.4f}')

    # signal vs noise
    if NOISE:
        print('\n=== SIGNAL vs NOISE (|Δ from press1/speed1 mean| / repeat sd) ===')
        def sweep(name, groups):
            print(f'\n  -- {name} --')
            print(f"    {'level':>8}{'metric':>10}{'mean':>9}{'delta':>9}{'noise sd':>10}{'|d|/sd':>9}{'|d|/rng':>9}")
            for lvl, ts in groups:
                for k in ['Rmed','Rout','turns','cons_rice'] + ['ruf_'+f for f in FILL] + ['r_'+f for f in FILL]:
                    if k.startswith('ruf_'):
                        f = k[4:]; vals = [R[t]['ruf'].get(f, float('nan')) for t in ts]
                    elif k.startswith('r_'):
                        f = k[2:]; vals = [R[t]['core'][f][0] for t in ts if f in R[t]['core']]
                    else:
                        vals = [R[t][k] for t in ts]
                    m = float(np.nanmean(vals))
                    b, sd, rng = NOISE[k]
                    d = m - b
                    r1 = abs(d)/sd if sd > 1e-12 else float('inf')
                    r2 = abs(d)/rng if rng > 1e-12 else float('inf')
                    print(f'    {lvl:>8}{k:>10}{m:>9.3f}{d:>9.3f}{sd:>10.4f}{r1:>9.1f}{r2:>9.1f}')
        sweep('--speed', [('0.5', [t for t in tags if t.startswith('sp05')]),
                          ('1.0', det),
                          ('2.0', [t for t in tags if t.startswith('sp20')])])
        sweep('--press', [('0.5', [t for t in tags if t.startswith('pr05')]),
                          ('1.0', det),
                          ('2.0', [t for t in tags if t.startswith('pr20')])])
