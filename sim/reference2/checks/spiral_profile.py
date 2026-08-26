"""The actual spiral: radius and unwrapped angle as a function of arclength along the sheet.
Everything is read off the particle dump; no model, no formula."""
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
H_NOM = H_SHEET

def profile(n):
    met = json.load(open(os.path.join(OUT, f'metrics_{n}.json')))
    assert_same_geometry(met)
    img = np.load(os.path.join(OUT, f'material_{n}.npy')); px = met['px_T']
    npx = img.shape[0]; fg = img != 0; r_, c_ = np.nonzero(fg)
    cr, cc = r_.mean(), c_.mean()
    cen = met['window_center_xy']
    cw = np.array([cen[0] + (cc - npx / 2) * px, cen[1] + (npx / 2 - cr) * px])
    z = np.load(os.path.join(OUT, f'particles_{n}.npz'))
    x, cl, ncol = z['x'], z['cls'], z['nori_col']
    m = cl == 2
    rel = x[m] - cw
    r = np.hypot(rel[:, 0], rel[:, 1]); ph = np.arctan2(rel[:, 1], rel[:, 0]); col = ncol[m]
    u, inv = np.unique(col, return_inverse=True)
    rc = np.array([r[inv == i].mean() for i in range(len(u))])
    # angle: average the rows at each column on the unit circle, then unwrap along the sheet
    cx = np.array([np.cos(ph[inv == i]).mean() for i in range(len(u))])
    cy = np.array([np.sin(ph[inv == i]).mean() for i in range(len(u))])
    th = np.unwrap(np.arctan2(cy, cx))
    s = u / u.max() * L_SHEET
    return met, s, rc, th, cw

print(f"{'L':<3}{'r(near edge)':>13}{'r(far edge)':>12}{'r min':>8}{'s@rmin':>8}{'Rout':>7}"
      f"{'turns':>8}{'dr/dturn':>10}")
prof = {}
for n in (1, 2, 3, 4, 5):
    met, s, rc, th, cw = profile(n)
    prof[n] = (s, rc, th)
    turns = abs(th[-1] - th[0]) / (2 * math.pi)
    i = int(np.argmin(rc))
    # pitch straight off the spiral: linear fit of r against unwrapped turns, over the
    # monotone rising part only (from the radial minimum to the far end)
    tt = np.abs(th - th[0]) / (2 * math.pi)
    sl = slice(i, len(rc))
    A = np.polyfit(tt[sl], rc[sl], 1) if len(rc) - i > 10 else [float('nan'), 0]
    print(f"{n:<3}{rc[0]:>13.3f}{rc[-1]:>12.3f}{rc.min():>8.3f}{s[i]:>8.2f}"
          f"{met['Rout_mean_T']:>7.3f}{turns:>8.3f}{A[0]:>10.3f}")

print()
print('radius along the sheet, sampled every 2 T of arclength (near edge = s 0):')
hdr = '  s,T |' + ''.join(f"{v:>6.0f}" for v in np.arange(0, 39, 2))
for n in (1, 2, 3, 4, 5):
    s, rc, th = prof[n]
    print(hdr) if n == 1 else None
    vals = np.interp(np.arange(0, 39, 2), s, rc)
    print(f"  L{n}  |" + ''.join(f"{v:>6.2f}" for v in vals))

print()
print('unwrapped turns along the sheet (same sampling):')
for n in (1, 2, 3, 4, 5):
    s, rc, th = prof[n]
    tt = np.abs(th - th[0]) / (2 * math.pi)
    vals = np.interp(np.arange(0, 39, 2), s, tt)
    print(f"  L{n}  |" + ''.join(f"{v:>6.2f}" for v in vals))
