"""Where is the air, and does the bump widen the pitch?
1. void fraction as a function of relative radius (core vs annulus)
2. local turn-to-turn pitch vs whether a filling sits between those two turns
3. robustness of the hole-bridging threshold"""
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
N_ANG = 36; STEP = 0.25; H_NOM = H_SHEET


def setup(n):
    met = json.load(open(os.path.join(OUT, f'metrics_{n}.json')))
    assert_same_geometry(met)
    img = np.load(os.path.join(OUT, f'material_{n}.npy')); px = met['px_T']; npx = img.shape[0]
    fg = img != 0; rr, cc = np.nonzero(fg); cr, cc0 = rr.mean(), cc.mean()
    cen = met['window_center_xy']
    cw = np.array([cen[0] + (cc0 - npx / 2) * px, cen[1] + (npx / 2 - cr) * px])
    return met, img, px, cr, cc0, cw


def contour(img, cr, cc0, px):
    npx = img.shape[0]; d0 = np.arange(int(npx / 2 / STEP)) * STEP; ro = []
    for a in np.deg2rad(np.arange(0, 360, 10)):
        rr = np.round(cr - d0 * math.sin(a)).astype(int); cc = np.round(cc0 + d0 * math.cos(a)).astype(int)
        ok = (rr >= 0) & (rr < npx) & (cc >= 0) & (cc < npx)
        seq = img[rr[ok], cc[ok]]; nz = np.nonzero(seq != 0)[0]
        ro.append(float((d0[ok] * px)[nz[-1]]) if len(nz) else 0.0)
    ro = np.array(ro)
    return np.array([np.median(ro[np.arange(i - 2, i + 3) % N_ANG]) for i in range(N_ANG)]), ro


print('=== 1. void fraction by relative radius r/Rcontour (pinholes <=4 px removed) ===')
bins = np.arange(0, 1.01, 0.1)
print('  L  ' + ''.join(f"{bins[i]:.1f}-{bins[i+1]:.1f}" .rjust(9) for i in range(10)))
for n in (1, 2, 3, 4, 5):
    met, img, px, cr, cc0, cw = setup(n)
    cont, _ = contour(img, cr, cc0, px)
    npx = img.shape[0]; yy, xx = np.mgrid[0:npx, 0:npx]
    dr = np.hypot(yy - cr, xx - cc0) * px
    th = np.mod(np.arctan2(cr - yy, xx - cc0), 2 * math.pi)
    bi = np.mod(np.round(th / (2 * math.pi / N_ANG)).astype(int), N_ANG)
    rel = dr / cont[bi]
    # drop 1-4 px void blobs (raster pinholes) before profiling
    vm = (img == 0) & (rel <= 1.0)
    lab = np.zeros(img.shape, np.int32); nn = 0; keep = np.zeros(img.shape, bool)
    for r0, c0 in np.argwhere(vm):
        if lab[r0, c0]: continue
        nn += 1; st = [(r0, c0)]; lab[r0, c0] = nn; cells = []
        while st:
            r, c = st.pop(); cells.append((r, c))
            for d1 in (-1, 0, 1):
                for d2 in (-1, 0, 1):
                    a, b = r + d1, c + d2
                    if 0 <= a < npx and 0 <= b < npx and vm[a, b] and not lab[a, b]:
                        lab[a, b] = nn; st.append((a, b))
        if len(cells) > 4:
            for (a, b) in cells: keep[a, b] = True
    row = []
    for i in range(10):
        m = (rel > bins[i]) & (rel <= bins[i + 1])
        row.append(100.0 * float((keep & m).sum()) / max(float(m.sum()), 1))
    print(f"  {n}  " + ''.join(f"{v:8.1f}%" for v in row))

print()
print('=== 2. local pitch vs the bump: pitch(theta) and what lies between the turns ===')
for n in (1, 2, 3, 4, 5):
    met, img, px, cr, cc0, cw = setup(n)
    z = np.load(os.path.join(OUT, f'particles_{n}.npz'))
    m = z['cls'] == 2; rel = z['x'][m] - cw
    r = np.hypot(rel[:, 0], rel[:, 1]); ph = np.arctan2(rel[:, 1], rel[:, 0]); col = z['nori_col'][m]
    u, inv = np.unique(col, return_inverse=True)
    rc = np.array([r[inv == i].mean() for i in range(len(u))])
    th = np.unwrap(np.arctan2(np.array([np.sin(ph[inv == i]).mean() for i in range(len(u))]),
                              np.array([np.cos(ph[inv == i]).mean() for i in range(len(u))])))
    t = np.abs(th - th[0]) / (2 * math.pi)
    tt = np.linspace(t[0], t[-1] - 1.0, 200)
    r0 = np.interp(tt, t, rc); r1 = np.interp(tt + 1.0, t, rc)
    p = r1 - r0
    # what is between the two turns, at the midpoint angle
    ang = np.interp(tt + 0.5, t, th)
    fillfrac = []
    for k in range(len(tt)):
        a = ang[k]
        dd = np.arange(int(min(r0[k], r1[k]) / px), int(max(r0[k], r1[k]) / px) + 1)
        rr = np.round(cr - dd * math.sin(a)).astype(int); cc = np.round(cc0 + dd * math.cos(a)).astype(int)
        ok = (rr >= 0) & (rr < img.shape[0]) & (cc >= 0) & (cc < img.shape[0])
        seq = img[rr[ok], cc[ok]]
        fillfrac.append(float(np.mean(seq > 2)) if len(seq) else 0.0)
    fillfrac = np.array(fillfrac)
    has = fillfrac > 0.15
    pf = np.median(p[has]) if has.any() else float('nan')
    pn = np.median(p[~has]) if (~has).any() else float('nan')
    print(f"  L{n}: pitch with a filling between the turns {pf:6.3f} T ({int(has.sum())} samples), "
          f"without {pn:6.3f} T ({int((~has).sum())})   difference {pf-pn:+.3f} T"
          if has.any() else
          f"  L{n}: no filling ever sits between two turns; pitch {pn:.3f} T (nominal {H_NOM})")

print()
print('=== 3. is the hole-bridging threshold doing the work, or the bimodality? ===')
def bridged(n, tol):
    met, img, px, cr, cc0, cw = setup(n)
    npx = img.shape[0]; d0 = np.arange(int(npx / 2 / STEP)) * STEP; out = []
    for a in np.deg2rad(np.arange(0, 360, 10)):
        rr = np.round(cr - d0 * math.sin(a)).astype(int); cc = np.round(cc0 + d0 * math.cos(a)).astype(int)
        ok = (rr >= 0) & (rr < npx) & (cc >= 0) & (cc < npx)
        d = d0[ok] * px; seq = img[rr[ok], cc[ok]]
        idx = np.nonzero(seq == 2)[0]
        if not len(idx): out.append(0); continue
        brk = np.nonzero(np.diff(idx) > 1)[0]
        sp = [(float(d[g[0]]), float(d[g[-1]])) for g in np.split(idx, brk + 1)]
        mm = [sp[0]]
        for s, e in sp[1:]:
            if s - mm[-1][1] <= tol: mm[-1] = (mm[-1][0], e)
            else: mm.append((s, e))
        out.append(len(mm))
    return float(np.mean(out))
tols = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.45]
print('  tol T ' + ''.join(f"{t:>8.2f}" for t in tols))
for n in (1, 2, 3, 4, 5):
    print(f"  L{n}    " + ''.join(f"{bridged(n,t):>8.3f}" for t in tols))
