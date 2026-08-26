#!/usr/bin/env python3
"""Common, attempt-agnostic judging metrics for kin-grab / kin-mat outputs.

Reads out*/particles_<L>.npz + metrics_<L>.json, recomputes every number with ONE
implementation so the two attempts are compared on the same ruler.
"""
import importlib.util, json, math, sys
import numpy as np

ROOT = '/Users/newyurk/Desktop/Home/Projects/rollery/sim'


def geometry(mod):
    """Sheet geometry of the attempt being judged, read from ITS OWN run.py.

    These four numbers used to be hardcoded here as T = 1.0, W = 0.12, L_SHEET = 38.7, L_FLAP = 5.0.
    That was fine only while every attempt shared them. reference2 corrected its thicknesses to the
    sourced ones on 26.08.2026 (rice bed 1.4 U = 7 mm, nori 0.02 U = 0.1 mm, sheet 42 U = 21 cm) and
    renamed `T` to `T_RICE`, so a hardcoded copy here would silently judge a reference2 dump with the
    old spiral pitch. Both spellings are accepted; nothing is guessed.
    """
    t_rice = getattr(mod, 'T_RICE', None)
    if t_rice is None:
        t_rice = mod.T                       # attempts predating the 26.08.2026 rename
    w = mod.W_NORI
    pitch = getattr(mod, 'H_SHEET', t_rice + w)
    return t_rice, w, mod.L_SHEET, mod.L_FLAP, pitch


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def predicted(mod, L):
    lay = mod.LAYOUTS[L]
    xs, cls, vol, nr, nc, info = mod.sample_layout(lay, 16000)
    T, W, L_SHEET, L_FLAP, PITCH = geometry(mod)
    a_rice = (L_SHEET - L_FLAP) * T
    a_nori = L_SHEET * W
    a_fill = info['area_fill']
    A = a_rice + a_nori + a_fill
    Rout = math.sqrt(A / math.pi)
    # fold length: fillings lying near the near edge + 1 T, else 5 T  (same rule in both attempts)
    rects = sorted(info['rects'], key=lambda r: r[0])
    sel, reach = [], 5.0
    for r in rects:
        if r[0] <= reach:
            sel.append(r); reach = r[0] + r[2] + 2.5
    s_fold = (max(r[0] + r[2] for r in sel) + 1.0) if sel else 5.0
    s_fold = min(s_fold, 0.45 * L_SHEET)
    Rcore = math.sqrt(s_fold * PITCH / math.pi)
    layers = (Rout - Rcore) / PITCH
    return dict(A=A, Rout_pred=Rout, Rcore_pred=Rcore, s_fold=s_fold,
                layers_pred=layers, cross_pred=layers + 1.0, a_fill=a_fill), (xs, cls, vol, nr, nc, info)


def contour(xs, cen, nb=36, pct=98.0, half=2):
    rel = xs - np.asarray(cen)
    r = np.hypot(rel[:, 0], rel[:, 1])
    a = np.arctan2(rel[:, 1], rel[:, 0])
    b = np.clip(((a + math.pi) / (2 * math.pi) * nb).astype(int), 0, nb - 1)
    c = np.zeros(nb)
    for k in range(nb):
        m = b == k
        c[k] = np.percentile(r[m], pct) if m.sum() >= 3 else np.nan
    good = ~np.isnan(c)
    if not good.all():
        c[~good] = np.interp(np.nonzero(~good)[0], np.nonzero(good)[0], c[good])
    sm = np.array([np.median(np.take(c, range(k - half, k + half + 1), mode='wrap')) for k in range(nb)])
    return r, b, c, sm


def judge(attempt, out, L, mod):
    pred, (xs0, cls0, vol, nr, nc, info) = predicted(mod, L)
    z = np.load(f'{ROOT}/{attempt}/{out}/particles_{L}.npz')
    met = json.load(open(f'{ROOT}/{attempt}/{out}/metrics_{L}.json'))
    x, cls, J = z['x'], z['cls'], z['J']
    assert len(x) == len(vol), (len(x), len(vol))
    rice, nori, fil = cls == 1, cls == 2, cls > 2
    cons = float(np.sum(vol * J) / np.sum(vol))
    cons_rice = float(np.sum(vol[rice] * J[rice]) / np.sum(vol[rice]))
    cen = (float(x[:, 0].mean()), float(x[:, 1].mean()))
    r, b, craw, sm = contour(x, cen)
    excess = r - sm[b]
    out_m = excess > 0.3
    rmed, rmax, rmin = float(np.median(sm)), float(sm.max()), float(sm.min())
    round_cv = float(sm.std() / sm.mean())
    # near edge (tuck) and far edge (flap) radial position, normalised
    ne = nori & (nc <= 2)
    fe = nori & (nc >= info['nori_cols'] - 3)
    r_near = float(np.median(r[ne])) / rmed
    r_far = float(np.median(r[fe])) / rmed
    # core
    core = []
    for f in mod.LAYOUTS[L]['fillings']:
        c = mod.CLASS_OF_KIND[f['kind']]
        m = cls == c
        if not m.any():
            continue
        cx, cy = float(x[m, 0].mean()), float(x[m, 1].mean())
        rr = math.hypot(cx - cen[0], cy - cen[1])
        ph = math.degrees(math.atan2(cy - cen[1], cx - cen[0]))
        core.append((f['kind'], rr, ph, cx, float(np.percentile(np.hypot(x[m, 0] - cen[0], x[m, 1] - cen[1]), 95))))
    order_x = [c[0] for c in sorted(core, key=lambda c: c[3])]
    core_rmax = max((c[4] for c in core), default=0.0)
    return dict(
        attempt=attempt, L=L,
        turns=met['nori_turns'], cross_pred=round(pred['cross_pred'], 3),
        d_turns=round(met['nori_turns'] - pred['cross_pred'], 3),
        layers_pred=round(pred['layers_pred'], 3),
        Rout_pred=round(pred['Rout_pred'], 3), Rout_med=round(rmed, 3), Rout_max=round(rmax, 3),
        round_cv=round(round_cv, 4), rmin_rmax=round(rmin / rmax, 3),
        cons=round(cons, 4), cons_rice=round(cons_rice, 4), J_rice=met['rice_J_mean'],
        map_ratio=met['rice_area_ratio'],
        out_frac=round(float(out_m.mean()), 5), out_n=int(out_m.sum()),
        out_nori=int((out_m & nori).sum()), out_max=round(float(excess.max()), 3),
        r_near=round(r_near, 3), r_far=round(r_far, 3),
        core_rmax=round(core_rmax, 2), order_x=order_x,
        core=[(c[0], round(c[1], 2), round(c[2], 1)) for c in core],
        sec=met['timing']['seconds'], stable=met['stable'], esc=met['escaped'],
        gap=met['nori_max_gap_T'], torn=met['nori_torn'],
    )


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'out_judge'
    mods = {'kin-grab': load(f'{ROOT}/kin-grab/run.py', 'rg'), 'kin-mat': load(f'{ROOT}/kin-mat/run.py', 'rm')}
    rows = []
    for L in (1, 2, 3, 4, 5):
        for a, mod in mods.items():
            try:
                rows.append(judge(a, out, L, mod))
            except FileNotFoundError:
                pass
    hdr = ['attempt', 'L', 'turns', 'cross_pred', 'd_turns', 'cons', 'cons_rice', 'map_ratio',
           'Rout_med', 'Rout_pred', 'round_cv', 'out_frac', 'out_max', 'out_nori', 'r_near', 'r_far',
           'core_rmax', 'sec', 'stable', 'gap']
    print(' | '.join(f'{h:>10}' for h in hdr))
    for r in rows:
        print(' | '.join(f'{str(r[h]):>10}' for h in hdr))
    print()
    for r in rows:
        print(r['attempt'], r['L'], 'order_x=', r['order_x'], 'core=', r['core'])
    json.dump(rows, open(f'{ROOT}/judge_{out}.json', 'w'), indent=1)
