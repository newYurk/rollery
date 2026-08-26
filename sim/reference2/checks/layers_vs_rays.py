"""Adversarial check: layer count predicted from ACTUAL final geometry
(measured Rout, measured core radius, measured radial pitch) against the
crossings actually counted on 36 rays.  Tolerance 0.25.

Nothing here reads run.py's own prediction except for reporting the delta:
every input is re-measured from out/material_<N>.npy and out/particles_<N>.npz.
"""
import json, math, sys, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, '..', 'out')
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _geom import (T_RICE, W_NORI, H_SHEET, L_SHEET, L_FLAP, R_MAT_MIN, BG_HOLE_T,
                   WR_DS, WR_KAPPA_MIN, WR_NOSE_T, WR_EDGE_T, WR_FIT_T, PACK_AIR, CORNER_R,
                   assert_same_geometry)
# The geometry used to live as a private copy in every one of these scripts (T = 1.0,
# W_NORI = 0.12, L_SHEET = 38.7, pitch H_NOM = 1.12). It is imported from run.py now: after the
# thickness correction of 26.08.2026 a stale copy would judge new dumps by the old spiral pitch
# and print plausible, wrong numbers without raising anything.
H_NOM = H_SHEET                         # pitch the formula in run.py assumes
CLASS_BG, CLASS_RICE, CLASS_NORI = 0, 1, 2
STEP = 0.25                             # ray sampling step, in pixels (same as run.py)


def ray(img, c_row, c_col, ang, px, step=STEP):
    npx = img.shape[0]
    n = int(npx / 2 / step)
    d = np.arange(n) * step
    rr = np.round(c_row - d * math.sin(ang)).astype(int)
    cc = np.round(c_col + d * math.cos(ang)).astype(int)
    ok = (rr >= 0) & (rr < npx) & (cc >= 0) & (cc < npx)
    return d[ok] * px, img[rr[ok], cc[ok]]


def spans(d, seq, c):
    """[(r_start, r_end)] of each contiguous run of class c along the ray."""
    m = seq == c
    if not m.any():
        return []
    idx = np.nonzero(m)[0]
    brk = np.nonzero(np.diff(idx) > 1)[0]
    groups = np.split(idx, brk + 1)
    return [(float(d[g[0]]), float(d[g[-1]])) for g in groups]


def analyse(n):
    img = np.load(os.path.join(OUT, f'material_{n}.npy'))
    met = json.load(open(os.path.join(OUT, f'metrics_{n}.json')))
    assert_same_geometry(met)
    px = met['px_T']
    cen = met['window_center_xy']
    npx = img.shape[0]
    fg = img != CLASS_BG
    rows, cols = np.nonzero(fg)
    c_row, c_col = rows.mean(), cols.mean()
    cen_world = (cen[0] + (c_col - npx / 2) * px, cen[1] + (npx / 2 - c_row) * px)

    angs = np.deg2rad(np.arange(0, 360, 10))
    rout, cross, pitches, inner, outer_nori = [], [], [], [], []
    void_between = 0.0          # background area trapped between nori layers
    for a in angs:
        d, seq = ray(img, c_row, c_col, a, px)
        nz = np.nonzero(seq != CLASS_BG)[0]
        ro = float(d[nz[-1]]) if len(nz) else 0.0
        rout.append(ro)
        sp = spans(d, seq, CLASS_NORI)
        cross.append(len(sp))
        if sp:
            inner.append(sp[0][0])
            outer_nori.append(sp[-1][1])
            mids = [0.5 * (s + e) for s, e in sp]
            for i in range(1, len(mids)):
                pitches.append(mids[i] - mids[i - 1])
        # background sitting strictly inside the outer contour = air between turns
        ins = d <= ro
        void_between += float(np.sum((seq[ins] == CLASS_BG))) * (STEP * px)
    rout = np.array(rout); cross = np.array(cross, float)
    pitches = np.array(pitches)

    # ---- core radius, measured three independent ways -----------------------
    z = np.load(os.path.join(OUT, f'particles_{n}.npz'))
    xs, cl, ncol = z['x'], z['cls'], z['nori_col']
    rel = xs - np.array(cen_world, np.float64)
    rp = np.hypot(rel[:, 0], rel[:, 1])
    nori = cl == CLASS_NORI
    cmin, cmax = int(ncol[nori].min()), int(ncol[nori].max())
    r_near = float(np.mean(rp[nori & (ncol == cmin)]))     # near edge = start of the spiral
    r_far = float(np.mean(rp[nori & (ncol == cmax)]))
    r_inner_ray = float(np.median(inner))                  # innermost nori seen on the rays
    # ---- unwrapped spiral turns straight off the sheet ----------------------
    ph = np.mod(np.arctan2(rel[nori, 1], rel[nori, 0]), 2 * math.pi)
    order = np.argsort(ncol[nori])
    ph_s = ph[order]
    # average the (2) rows at each column so the midline is used
    cols_s = ncol[nori][order]
    uniq, inv = np.unique(cols_s, return_inverse=True)
    ph_col = np.array([np.mean(np.unwrap(ph_s[inv == i])) for i in range(len(uniq))])
    unw = np.unwrap(ph_col)
    turns_unwrap = abs(unw[-1] - unw[0]) / (2 * math.pi)

    Rout_m = float(np.mean(rout))
    pitch_m = float(np.median(pitches)) if len(pitches) else float('nan')
    return dict(
        n=n, name=met['layout_name'],
        Rout_meas=Rout_m, Rout_metric=met['Rout_mean_T'],
        Rcore_near_edge=r_near, Rcore_ray=r_inner_ray, r_far_edge=r_far,
        pitch_meas=pitch_m, pitch_p25=float(np.percentile(pitches, 25)) if len(pitches) else float('nan'),
        pitch_p75=float(np.percentile(pitches, 75)) if len(pitches) else float('nan'),
        n_pitch=len(pitches),
        cross_meas=float(cross.mean()), cross_min=int(cross.min()), cross_max=int(cross.max()),
        cross_metric=met['nori_turns'],
        turns_unwrap=turns_unwrap,
        void_T2=void_between,
        run_pred_best=met['crossings_predicted_best'], run_pred_src=met['crossings_best_source'],
        run_pred_lit=met['crossings_predicted'], run_pred_core=met['crossings_predicted_core'],
        Rout_pred=met['Rout_pred_T'], area_pred=met['area_pred_T2'],
        cen_world=cen_world,
    )


rows = [analyse(n) for n in (1, 2, 3, 4, 5)]

print('=== A. reproduce the ray metric (sanity: my counter vs run.py) ===')
for r in rows:
    print(f"  L{r['n']} {r['name']:<16} mine {r['cross_meas']:.3f}  run.py {r['cross_metric']:.3f}"
          f"   delta {r['cross_meas']-r['cross_metric']:+.3f}")

print()
print('=== B. measured geometry ===')
print(f"  {'L':<3}{'Rout':>7}{'Rcore(edge)':>13}{'Rcore(ray)':>12}{'pitch':>8}{'p25..p75':>15}{'nom h':>7}{'void T2':>9}")
for r in rows:
    print(f"  {r['n']:<3}{r['Rout_meas']:>7.3f}{r['Rcore_near_edge']:>13.3f}{r['Rcore_ray']:>12.3f}"
          f"{r['pitch_meas']:>8.3f}{r['pitch_p25']:>8.3f}..{r['pitch_p75']:<6.3f}{H_NOM:>7.2f}{r['void_T2']:>9.3f}")

print()
print('=== C. prediction from ACTUAL geometry vs measured crossings (tol 0.25) ===')
print(f"  {'L':<3}{'pred(act pitch)':>16}{'pred(nom h)':>13}{'measured':>10}{'d_act':>8}{'d_nom':>8}{'ok_act':>8}{'ok_nom':>8}")
fails_act, fails_nom = [], []
for r in rows:
    rc = r['Rcore_near_edge']
    p_act = (r['Rout_meas'] - rc) / r['pitch_meas'] + 1.0
    p_nom = (r['Rout_meas'] - rc) / H_NOM + 1.0
    d_act = r['cross_meas'] - p_act
    d_nom = r['cross_meas'] - p_nom
    r['p_act'], r['p_nom'], r['d_act'], r['d_nom'] = p_act, p_nom, d_act, d_nom
    ok_a, ok_n = abs(d_act) <= 0.25, abs(d_nom) <= 0.25
    if not ok_a: fails_act.append(r['n'])
    if not ok_n: fails_nom.append(r['n'])
    print(f"  {r['n']:<3}{p_act:>16.3f}{p_nom:>13.3f}{r['cross_meas']:>10.3f}{d_act:>+8.3f}{d_nom:>+8.3f}"
          f"{str(ok_a):>8}{str(ok_n):>8}")
print(f"  fails with measured pitch: {fails_act}   fails with nominal pitch h={H_NOM:.2f}: {fails_nom}")

print()
print('=== D. run.py own prediction vs the same measured crossings ===')
print(f"  {'L':<3}{'best':>8}{'src':>9}{'literal':>9}{'core':>8}{'meas':>8}{'d_best':>9}{'ok':>7}")
for r in rows:
    d = r['cross_meas'] - r['run_pred_best']
    print(f"  {r['n']:<3}{r['run_pred_best']:>8.3f}{r['run_pred_src']:>9}{r['run_pred_lit']:>9.3f}"
          f"{r['run_pred_core']:>8.3f}{r['cross_meas']:>8.3f}{d:>+9.3f}{str(abs(d)<=0.25):>7}")

print()
print('=== E. cross-check: turns from unwrapping the sheet itself ===')
for r in rows:
    print(f"  L{r['n']} unwrapped turns {r['turns_unwrap']:.3f}   rays {r['cross_meas']:.3f}"
          f"   rays-1 {r['cross_meas']-1:.3f}   |unwrap-(rays-1)| {abs(r['turns_unwrap']-(r['cross_meas']-1)):.3f}")

print()
print('=== F. Rout: measured vs area-conservation prediction ===')
for r in rows:
    e = 100.0 * (r['Rout_meas'] - r['Rout_pred']) / r['Rout_pred']
    print(f"  L{r['n']} Rout meas {r['Rout_meas']:.3f}  pred {r['Rout_pred']:.3f}  {e:+.1f} %"
          f"   implied area meas {math.pi*r['Rout_meas']**2:.2f} T2 vs {r['area_pred']:.2f} T2"
          f"  ({100*(math.pi*r['Rout_meas']**2/r['area_pred']-1):+.1f} %)")

json.dump([{k: v for k, v in r.items()} for r in rows],
          open(os.path.join(HERE, 'layers_vs_rays.json'), 'w'), indent=1, default=float)
