"""Layers against the formula -- with the ray measurement de-holed first.

A. crossings on 36 rays, raw and with run.py's own hole tolerance (BG_HOLE_T = 0.35) applied
B. turns straight off the sheet (unwrapped angle) -- ground truth, no ray sampling involved
C. prediction from ACTUAL measured geometry (Rout, core radius, pitch) vs the measured crossings
D. void (air) trapped inside the outer contour, as a real 2D area
E. near edge inside / far edge outside, each against the contour at its OWN angle
F. layout 4: order of the fillings along the sheet, preserved or not
"""
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
W = W_NORI; H_NOM = H_SHEET; STEP = 0.25
N_ANG = 36
LAY4 = [('cucumber', 1.5, 1.4), ('tamago', 3.2, 2.4), ('salmon', 5.9, 2.0), ('avocado', 8.2, 2.0)]
KIND_CLASS = {'salmon': 3, 'cucumber': 4, 'tamago': 5, 'avocado': 6, 'shrimp': 7}


def load(n):
    met = json.load(open(os.path.join(OUT, f'metrics_{n}.json')))
    assert_same_geometry(met)
    img = np.load(os.path.join(OUT, f'material_{n}.npy'))
    z = np.load(os.path.join(OUT, f'particles_{n}.npz'))
    px = met['px_T']; npx = img.shape[0]
    fg = img != 0; rr, cc = np.nonzero(fg); cr, cc0 = rr.mean(), cc.mean()
    cen = met['window_center_xy']
    cw = np.array([cen[0] + (cc0 - npx / 2) * px, cen[1] + (npx / 2 - cr) * px])
    return met, img, z, px, cr, cc0, cw


def rays(img, cr, cc0, px):
    npx = img.shape[0]; d0 = np.arange(int(npx / 2 / STEP)) * STEP
    out = []
    for a in np.deg2rad(np.arange(0, 360, 360 // N_ANG)):
        rr = np.round(cr - d0 * math.sin(a)).astype(int); cc = np.round(cc0 + d0 * math.cos(a)).astype(int)
        ok = (rr >= 0) & (rr < npx) & (cc >= 0) & (cc < npx)
        out.append((a, d0[ok] * px, img[rr[ok], cc[ok]]))
    return out


def nori_spans(d, seq, tol=None):
    idx = np.nonzero(seq == 2)[0]
    if not len(idx): return []
    brk = np.nonzero(np.diff(idx) > 1)[0]
    sp = [(float(d[g[0]]), float(d[g[-1]])) for g in np.split(idx, brk + 1)]
    if tol is None: return sp
    m = [sp[0]]
    for s, e in sp[1:]:
        if s - m[-1][1] <= tol: m[-1] = (m[-1][0], e)
        else: m.append((s, e))
    return m


R = {}
for n in (1, 2, 3, 4, 5):
    met, img, z, px, cr, cc0, cw = load(n)
    rs = rays(img, cr, cc0, px)
    raw, brd, rout, pit = [], [], [], []
    for a, d, seq in rs:
        nz = np.nonzero(seq != 0)[0]
        rout.append(float(d[nz[-1]]) if len(nz) else 0.0)
        raw.append(len(nori_spans(d, seq)))
        sp = nori_spans(d, seq, BG_HOLE_T)
        brd.append(len(sp))
        mid = [0.5 * (s + e) for s, e in sp]
        pit += [mid[i] - mid[i - 1] for i in range(1, len(mid))]
    rout = np.array(rout); pit = np.array(pit)
    # contour, median-smoothed exactly as run.py's tail metric does
    cont = np.array([np.median(rout[np.arange(i - 2, i + 3) % N_ANG]) for i in range(N_ANG)])
    # --- void: real 2D area of background strictly inside the contour
    npx = img.shape[0]
    yy, xx = np.mgrid[0:npx, 0:npx]
    dr = np.hypot(yy - cr, xx - cc0) * px
    th = np.mod(np.arctan2(cr - yy, xx - cc0), 2 * math.pi)
    bi = np.mod(np.round(th / (2 * math.pi / N_ANG)).astype(int), N_ANG)
    inside = dr <= cont[bi]
    void = float(np.sum(inside & (img == 0))) * px * px
    solid = float(np.sum(inside)) * px * px
    # --- spiral off the particles
    x, cl, ncol = z['x'], z['cls'], z['nori_col']
    m = cl == 2; rel = x[m] - cw
    r = np.hypot(rel[:, 0], rel[:, 1]); ph = np.arctan2(rel[:, 1], rel[:, 0]); col = ncol[m]
    u, inv = np.unique(col, return_inverse=True)
    rc = np.array([r[inv == i].mean() for i in range(len(u))])
    thc = np.unwrap(np.arctan2(np.array([np.sin(ph[inv == i]).mean() for i in range(len(u))]),
                               np.array([np.cos(ph[inv == i]).mean() for i in range(len(u))])))
    s = u / u.max() * L_SHEET
    turns = abs(thc[-1] - thc[0]) / (2 * math.pi)
    # edges against the contour AT THEIR OWN ANGLE
    def at(i):
        b = int(round((np.mod(np.arctan2(rel[:, 1], rel[:, 0])[0] if False else 0, 1))))
        return None
    phn = np.mod(np.arctan2(np.sin(ph[inv == 0]).mean(), np.cos(ph[inv == 0]).mean()), 2 * math.pi)
    phf = np.mod(np.arctan2(np.sin(ph[inv == len(u) - 1]).mean(), np.cos(ph[inv == len(u) - 1]).mean()), 2 * math.pi)
    cn = cont[int(np.mod(round(phn / (2 * math.pi / N_ANG)), N_ANG))]
    cf = cont[int(np.mod(round(phf / (2 * math.pi / N_ANG)), N_ANG))]
    R[n] = dict(met=met, raw=float(np.mean(raw)), brd=float(np.mean(brd)), rout=float(rout.mean()),
                pit=pit, turns=turns, s=s, rc=rc, thc=thc, void=void, solid=solid,
                rnear=rc[0], rfar=rc[-1], cn=cn, cf=cf, rmin=float(rc.min()), smin=float(s[np.argmin(rc)]),
                cw=cw, img=img, px=px, cr=cr, cc0=cc0, cont=cont, z=z)

print('=== A. what the 36 rays really counted ===')
print(f"  {'L':<3}{'raw (=nori_turns)':>19}{'holes bridged':>15}{'inflation':>11}{'% of runs':>11}")
for n in R:
    r = R[n]; inf = r['raw'] - r['brd']
    print(f"  {n:<3}{r['raw']:>19.3f}{r['brd']:>15.3f}{inf:>+11.3f}{100*inf/r['raw']:>10.1f}%")

print()
print('=== B. ground truth: turns from the sheet itself (no rays) ===')
print(f"  {'L':<3}{'turns':>8}{'bridged rays':>14}{'delta':>8}{'raw rays':>10}{'delta':>8}")
for n in R:
    r = R[n]
    print(f"  {n:<3}{r['turns']:>8.3f}{r['brd']:>14.3f}{r['brd']-r['turns']:>+8.3f}"
          f"{r['raw']:>10.3f}{r['raw']-r['turns']:>+8.3f}")

print()
print('=== C. prediction from ACTUAL geometry vs measured crossings, tol 0.25 ===')
print(f"  {'L':<3}{'Rout':>7}{'Rcore':>7}{'pitch':>7}{'pred=(R-Rc)/p':>15}{'meas(bridged)':>15}{'delta':>8}{'ok':>6}"
      f"{'  vs raw':>9}{'delta':>8}{'ok':>6}")
bad = []
for n in R:
    r = R[n]
    p = float(np.median(r['pit'][r['pit'] > BG_HOLE_T])) if (r['pit'] > BG_HOLE_T).any() else float('nan')
    pred = (r['rout'] - r['rmin']) / p
    d1 = r['brd'] - pred; d2 = r['raw'] - pred
    if abs(d1) > 0.25: bad.append(n)
    print(f"  {n:<3}{r['rout']:>7.3f}{r['rmin']:>7.3f}{p:>7.3f}{pred:>15.3f}{r['brd']:>15.3f}{d1:>+8.3f}"
          f"{str(abs(d1)<=0.25):>6}{r['raw']:>9.3f}{d2:>+8.3f}{str(abs(d2)<=0.25):>6}")
    r['pitch'] = p; r['pred'] = pred
print(f"  outside tolerance against the clean measurement: {bad}")

print()
print('=== D. air trapped between the turns (2D area inside the contour) ===')
print(f"  {'L':<3}{'void T2':>9}{'inside T2':>11}{'void %':>9}{'pitch':>8}{'nominal h':>11}{'pitch/h':>9}")
for n in R:
    r = R[n]
    print(f"  {n:<3}{r['void']:>9.3f}{r['solid']:>11.3f}{100*r['void']/r['solid']:>8.1f}%"
          f"{r['pitch']:>8.3f}{H_NOM:>11.2f}{r['pitch']/H_NOM:>9.3f}")

print()
print('=== E. near edge inside, far edge outside ===')
print(f"  {'L':<3}{'r near':>8}{'contour@near':>14}{'cover T':>9}{'inside?':>9}   "
      f"{'r far':>7}{'contour@far':>13}{'excess':>8}{'outside?':>10}")
for n in R:
    r = R[n]
    cov = r['cn'] - r['rnear']; exc = r['rfar'] - r['cf']
    print(f"  {n:<3}{r['rnear']:>8.3f}{r['cn']:>14.3f}{cov:>9.3f}{str(cov > 0):>9}   "
          f"{r['rfar']:>7.3f}{r['cf']:>13.3f}{exc:>+8.3f}{str(exc > -W):>10}")

print()
print('=== F. layout 4: order of the fillings along the sheet ===')
r = R[4]; z = r['z']; cw = r['cw']
x, cl = z['x'], z['cls']
s_sheet, rc, thc = r['s'], r['rc'], r['thc']
# sheet point positions in the plane, per arclength sample
sx = cw[0] + rc * np.cos(thc); sy = cw[1] + rc * np.sin(thc)
print(f"  {'filling':<10}{'u init':>8}{'s nearest sheet':>17}{'r fill':>8}{'r sheet@u':>11}{'phi deg':>9}")
rows = []
for kind, u, w in LAY4:
    c = KIND_CLASS[kind]; m = cl == c
    cxy = x[m].mean(axis=0)
    j = int(np.argmin((sx - cxy[0]) ** 2 + (sy - cxy[1]) ** 2))
    rel = cxy - cw
    rows.append((kind, u + w / 2, s_sheet[j], math.hypot(*rel), float(np.interp(u + w / 2, s_sheet, rc)),
                 math.degrees(math.atan2(rel[1], rel[0]))))
    print(f"  {kind:<10}{u + w/2:>8.2f}{s_sheet[j]:>17.2f}{rows[-1][3]:>8.3f}{rows[-1][4]:>11.3f}{rows[-1][5]:>9.1f}")
init = [q[0] for q in rows]
by_s = [q[0] for q in sorted(rows, key=lambda q: q[2])]
by_r = [q[0] for q in sorted(rows, key=lambda q: q[3])]
print(f"  order by initial u        : {init}")
print(f"  order by arclength on sheet: {by_s}   preserved: {by_s == init}")
print(f"  order by radius            : {by_r}   monotone-with-u: {by_r == init}")
print(f"  run.py core_order_by_phi   : {r['met']['core_order_by_phi']}  -> preserved={r['met']['core_order_preserved']}")
