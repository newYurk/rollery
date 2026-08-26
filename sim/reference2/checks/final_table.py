import json, math, os
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.join(HERE, '..', 'out')
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _geom import (T_RICE, W_NORI, H_SHEET, L_SHEET, L_FLAP, R_MAT_MIN, BG_HOLE_T,
                   WR_DS, WR_KAPPA_MIN, WR_NOSE_T, WR_EDGE_T, WR_FIT_T, PACK_AIR, CORNER_R,
                   assert_same_geometry)
# The geometry used to live as a private copy in every one of these scripts (T = 1.0,
# W_NORI = 0.12, L_SHEET = 38.7, pitch H_NOM = 1.12). It is imported from run.py now: after the
# thickness correction of 26.08.2026 a stale copy would judge new dumps by the old spiral pitch
# and print plausible, wrong numbers without raising anything.
N_ANG = 36; STEP = 0.25; H = H_SHEET


def prep(n):
    met = json.load(open(os.path.join(OUT, f'metrics_{n}.json')))
    assert_same_geometry(met)
    img = np.load(os.path.join(OUT, f'material_{n}.npy')); px = met['px_T']; npx = img.shape[0]
    fg = img != 0; rr, cc = np.nonzero(fg); cr, cc0 = rr.mean(), cc.mean()
    cen = met['window_center_xy']
    cw = np.array([cen[0] + (cc0 - npx / 2) * px, cen[1] + (npx / 2 - cr) * px])
    return met, img, px, cr, cc0, cw


def cross(img, cr, cc0, px, tol):
    npx = img.shape[0]; d0 = np.arange(int(npx / 2 / STEP)) * STEP; out = []
    for a in np.deg2rad(np.arange(0, 360, 10)):
        rr = np.round(cr - d0 * math.sin(a)).astype(int); cc = np.round(cc0 + d0 * math.cos(a)).astype(int)
        ok = (rr >= 0) & (rr < npx) & (cc >= 0) & (cc < npx)
        d = d0[ok] * px; seq = img[rr[ok], cc[ok]]
        idx = np.nonzero(seq == 2)[0]
        if not len(idx): out.append(0); continue
        sp = [(float(d[g[0]]), float(d[g[-1]])) for g in np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)]
        m = [sp[0]]
        for s, e in sp[1:]:
            if s - m[-1][1] <= tol: m[-1] = (m[-1][0], e)
            else: m.append((s, e))
        out.append(len(m))
    return float(np.mean(out))


def turns(n, cw):
    z = np.load(os.path.join(OUT, f'particles_{n}.npz'))
    m = z['cls'] == 2; rel = z['x'][m] - cw
    ph = np.arctan2(rel[:, 1], rel[:, 0]); col = z['nori_col'][m]
    u, inv = np.unique(col, return_inverse=True)
    th = np.unwrap(np.arctan2(np.array([np.sin(ph[inv == i]).mean() for i in range(len(u))]),
                              np.array([np.cos(ph[inv == i]).mean() for i in range(len(u))])))
    return abs(th[-1] - th[0]) / (2 * math.pi)


print('--- a raw ray through layout 1, showing what splits a nori run ---')
met, img, px, cr, cc0, cw = prep(1)
d0 = np.arange(int(img.shape[0] / 2 / STEP)) * STEP
a = math.radians(120)
rr = np.round(cr - d0 * math.sin(a)).astype(int); cc = np.round(cc0 + d0 * math.cos(a)).astype(int)
ok = (rr >= 0) & (rr < img.shape[0]) & (cc >= 0) & (cc < img.shape[0])
d = d0[ok] * px; seq = img[rr[ok], cc[ok]]
w = np.nonzero(seq == 2)[0]
if len(w):
    lo, hi = max(0, w[0] - 4), min(len(seq), w[0] + 40)
    print('   r,T  :', ' '.join(f"{v:5.2f}" for v in d[lo:hi:2]))
    print('   class:', ' '.join(f"{v:5d}" for v in seq[lo:hi:2]))
    print(f'   (class 2 = nori, 1 = rice, 0 = background; nori band is w = {W_NORI} U thick,')
    print('    nori particle spacing is 0.049 T -- a single 0 inside the band is a raster pinhole)')

print()
print('=== CORRECTED LAYER TABLE ===')
print(f"  {'L':<3}{'nori_turns':>11}{'de-holed':>10}{'inflation':>11}{'turns(sheet)':>14}"
      f"{'|de-holed-truth|':>18}{'|raw-truth|':>13}")
rows = []
for n in (1, 2, 3, 4, 5):
    met, img, px, cr, cc0, cw = prep(n)
    raw = cross(img, cr, cc0, px, 0.0); dh = cross(img, cr, cc0, px, 0.05); tr = turns(n, cw)
    rows.append((n, met, raw, dh, tr))
    print(f"  {n:<3}{raw:>11.3f}{dh:>10.3f}{raw-dh:>+11.3f}{tr:>14.3f}{abs(dh-tr):>18.3f}{abs(raw-tr):>13.3f}")

print()
print('=== formula vs the corrected measurement (tolerance 0.25) ===')
print(f"  {'L':<3}{'pred_best':>11}{'src':>9}{'pred-1':>9}{'measured':>10}{'d(+1 form)':>12}{'ok':>6}"
      f"{'d(no +1)':>10}{'ok':>6}{'run.py verdict':>16}")
for n, met, raw, dh, tr in rows:
    pb = met['crossings_predicted_best']
    d1 = dh - pb; d0_ = dh - (pb - 1.0)
    print(f"  {n:<3}{pb:>11.3f}{met['crossings_best_source']:>9}{pb-1:>9.3f}{dh:>10.3f}{d1:>+12.3f}"
          f"{str(abs(d1)<=0.25):>6}{d0_:>+10.3f}{str(abs(d0_)<=0.25):>6}"
          f"{str(met['turns_match_formula_best']):>16}")
n_pass_run = sum(1 for _, m, _, _, _ in rows if m['turns_match_formula_best'])
n_pass_fix = sum(1 for _, m, _, dh, _ in rows if abs(dh - m['crossings_predicted_best']) <= 0.25)
print(f"  run.py reports {n_pass_run}/5 inside tolerance; against the corrected measurement it is {n_pass_fix}/5")

print()
print('=== the two errors that cancel ===')
inf = np.mean([raw - dh for _, _, raw, dh, _ in rows])
off = np.mean([dh - (m['crossings_predicted_best'] - 1.0) for _, m, _, dh, _ in rows])
print(f"  mean measurement inflation from raster pinholes : {inf:+.3f} crossings")
print(f"  mean offset the '+1 for the tuck' should have been: {off:+.3f} (run.py uses +1.000)")
print(f"  they differ by {abs(inf-(1.0-off)):.3f}, which is why 3 of 5 layouts appeared to pass")
