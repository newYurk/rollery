"""Pitch measured the only unambiguous way: the same sheet, one full turn apart.
p(theta) = r(theta + 2pi) - r(theta), read off the particle dump.
Plus the trapped air, split into real blobs and one-pixel raster pinholes."""
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
H_NOM = H_SHEET; N_ANG = 36; STEP = 0.25


def sheet(n):
    met = json.load(open(os.path.join(OUT, f'metrics_{n}.json')))
    assert_same_geometry(met)
    img = np.load(os.path.join(OUT, f'material_{n}.npy')); px = met['px_T']; npx = img.shape[0]
    fg = img != 0; rr, cc = np.nonzero(fg); cr, cc0 = rr.mean(), cc.mean()
    cen = met['window_center_xy']
    cw = np.array([cen[0] + (cc0 - npx / 2) * px, cen[1] + (npx / 2 - cr) * px])
    z = np.load(os.path.join(OUT, f'particles_{n}.npz'))
    m = z['cls'] == 2; rel = z['x'][m] - cw
    r = np.hypot(rel[:, 0], rel[:, 1]); ph = np.arctan2(rel[:, 1], rel[:, 0]); col = z['nori_col'][m]
    u, inv = np.unique(col, return_inverse=True)
    rc = np.array([r[inv == i].mean() for i in range(len(u))])
    th = np.unwrap(np.arctan2(np.array([np.sin(ph[inv == i]).mean() for i in range(len(u))]),
                              np.array([np.cos(ph[inv == i]).mean() for i in range(len(u))])))
    s = u / u.max() * L_SHEET
    return met, img, px, cr, cc0, s, rc, th


def contour(img, cr, cc0, px):
    npx = img.shape[0]; d0 = np.arange(int(npx / 2 / STEP)) * STEP; ro = []
    for a in np.deg2rad(np.arange(0, 360, 10)):
        rr = np.round(cr - d0 * math.sin(a)).astype(int); cc = np.round(cc0 + d0 * math.cos(a)).astype(int)
        ok = (rr >= 0) & (rr < npx) & (cc >= 0) & (cc < npx)
        seq = img[rr[ok], cc[ok]]; nz = np.nonzero(seq != 0)[0]
        ro.append(float((d0[ok] * px)[nz[-1]]) if len(nz) else 0.0)
    ro = np.array(ro)
    return np.array([np.median(ro[np.arange(i - 2, i + 3) % N_ANG]) for i in range(N_ANG)]), ro


def blobs(mask):
    lab = np.zeros(mask.shape, np.int32); n = 0; sizes = []
    H, W = mask.shape
    for r0, c0 in np.argwhere(mask):
        if lab[r0, c0]: continue
        n += 1; st = [(r0, c0)]; lab[r0, c0] = n; k = 0
        while st:
            r, c = st.pop(); k += 1
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    a, b = r + dr, c + dc
                    if 0 <= a < H and 0 <= b < W and mask[a, b] and not lab[a, b]:
                        lab[a, b] = n; st.append((a, b))
        sizes.append(k)
    return np.array(sizes)


print('=== pitch: r(theta+2pi) - r(theta) on the sheet itself ===')
print(f"  {'L':<3}{'n samples':>10}{'p median':>10}{'p p25':>8}{'p p75':>8}{'h=T+w':>8}{'p/h':>7}"
      f"{'PACK_AIR budget':>17}")
P = {}
for n in (1, 2, 3, 4, 5):
    met, img, px, cr, cc0, s, rc, th = sheet(n)
    t = np.abs(th - th[0]) / (2 * math.pi)
    ok = t[-1] > 1.05
    ps = []
    if ok:
        tt = np.linspace(t[0], t[-1] - 1.0, 400)
        ps = np.interp(tt + 1.0, t, rc) - np.interp(tt, t, rc)
    ps = np.array(ps)
    P[n] = dict(met=met, img=img, px=px, cr=cr, cc0=cc0, s=s, rc=rc, th=th, t=t, ps=ps)
    print(f"  {n:<3}{len(ps):>10}{np.median(ps):>10.3f}{np.percentile(ps,25):>8.3f}"
          f"{np.percentile(ps,75):>8.3f}{H_NOM:>8.2f}{np.median(ps)/H_NOM:>7.3f}{H_NOM*(1+PACK_AIR):>17.3f}")

print()
print('=== geometric identity: turns = L / (2*pi*r_mean), r_mean weighted by arclength ===')
print(f"  {'L':<3}{'r_mean':>8}{'N = L/2pi r':>13}{'N unwrapped':>13}{'delta':>8}{'ok(0.25)':>10}")
for n in P:
    d = P[n]; rc, th = d['rc'], d['th']
    ds = np.abs(np.diff(th)) * 0.5 * (rc[1:] + rc[:-1])          # arclength element r*dtheta
    rbar = float(np.sum(0.5 * (rc[1:] + rc[:-1]) * ds) / np.sum(ds))
    Lg = float(np.sum(ds))
    N = Lg / (2 * math.pi * rbar)
    Nu = d['t'][-1]
    print(f"  {n:<3}{rbar:>8.3f}{N:>13.3f}{Nu:>13.3f}{N-Nu:>+8.3f}{str(abs(N-Nu)<=0.25):>10}"
          f"    (arclength recovered {Lg:.1f} T of {L_SHEET} T)")

print()
print('=== air inside the roll ===')
print(f"  {'L':<3}{'void T2':>9}{'blobs':>7}{'>=0.02 T2':>11}{'in blobs':>10}{'pinholes(1-4px)':>17}"
      f"{'deep void':>11}{'PACK_AIR would allow':>22}")
for n in P:
    d = P[n]; img, px, cr, cc0 = d['img'], d['px'], d['cr'], d['cc0']
    cont, ro = contour(img, cr, cc0, px)
    npx = img.shape[0]; yy, xx = np.mgrid[0:npx, 0:npx]
    dr = np.hypot(yy - cr, xx - cc0) * px
    th2 = np.mod(np.arctan2(cr - yy, xx - cc0), 2 * math.pi)
    bi = np.mod(np.round(th2 / (2 * math.pi / N_ANG)).astype(int), N_ANG)
    inside = dr <= cont[bi]
    vm = inside & (img == 0)
    sz = blobs(vm)
    a = px * px
    big = sz[sz * a >= 0.02]; pin = sz[sz <= 4]
    deep = float(np.sum((dr <= 0.85 * cont[bi]) & (img == 0))) * a
    tot = float(vm.sum()) * a
    allow = PACK_AIR * float(np.sum(img != 0)) * a
    print(f"  {n:<3}{tot:>9.3f}{len(sz):>7}{len(big):>11}{float(big.sum())*a:>10.3f}"
          f"{len(pin):>10} / {float(pin.sum())*a:.3f} T2{deep:>11.3f}{allow:>22.3f}")
