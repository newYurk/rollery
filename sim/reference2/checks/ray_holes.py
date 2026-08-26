"""Is `nori_turns` counting layers, or counting rasterisation holes?

run.py already knows raster holes exist -- BG_HOLE_T = 0.35, "a background run shorter
than this along a ray is a hole between particles" -- and bridges them when it measures
how much rice lies under a filling.  It does NOT bridge them when it counts nori runs.
This script counts how many of the 36-ray nori runs are separated by a gap too small to
be a real layer boundary.
"""
import json, math, os
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
CLASS_BG, CLASS_NORI = 0, 2
STEP = 0.25
H_NOM = H_SHEET


def ray(img, c_row, c_col, ang, px, step=STEP):
    npx = img.shape[0]
    d = np.arange(int(npx / 2 / step)) * step
    rr = np.round(c_row - d * math.sin(ang)).astype(int)
    cc = np.round(c_col + d * math.cos(ang)).astype(int)
    ok = (rr >= 0) & (rr < npx) & (cc >= 0) & (cc < npx)
    return d[ok] * px, img[rr[ok], cc[ok]]


def groups(mask, d):
    if not mask.any():
        return []
    idx = np.nonzero(mask)[0]
    brk = np.nonzero(np.diff(idx) > 1)[0]
    return [(float(d[g[0]]), float(d[g[-1]])) for g in np.split(idx, brk + 1)]


def bridge(sp, tol):
    out = []
    for s, e in sp:
        if out and s - out[-1][1] <= tol:
            out[-1] = (out[-1][0], e)
        else:
            out.append((s, e))
    return out


print(f"{'L':<3}{'runs':>7}{'gaps':>7}{'<0.35':>7}{'<0.20':>7}{'gap p10':>9}{'p50':>7}{'p90':>7}"
      f"{'turns':>8}{'br.35':>8}{'br.20':>8}{'unwrap':>8}")
res = {}
for n in (1, 2, 3, 4, 5):
    img = np.load(os.path.join(OUT, f'material_{n}.npy'))
    met = json.load(open(os.path.join(OUT, f'metrics_{n}.json')))
    assert_same_geometry(met)
    px = met['px_T']
    fg = img != CLASS_BG
    rows, cols = np.nonzero(fg)
    c_row, c_col = rows.mean(), cols.mean()
    raw, b35, b20, gaps = [], [], [], []
    for a in np.deg2rad(np.arange(0, 360, 10)):
        d, seq = ray(img, c_row, c_col, a, px)
        sp = groups(seq == CLASS_NORI, d)
        raw.append(len(sp))
        b35.append(len(bridge(sp, BG_HOLE_T)))
        b20.append(len(bridge(sp, 0.20)))
        for i in range(1, len(sp)):
            gaps.append(sp[i][0] - sp[i - 1][1])
    gaps = np.array(gaps)
    res[n] = dict(raw=float(np.mean(raw)), b35=float(np.mean(b35)), b20=float(np.mean(b20)),
                  gaps=gaps.tolist())
    print(f"{n:<3}{np.sum(raw):>7}{len(gaps):>7}{int((gaps<0.35).sum()):>7}{int((gaps<0.20).sum()):>7}"
          f"{np.percentile(gaps,10):>9.3f}{np.percentile(gaps,50):>7.3f}{np.percentile(gaps,90):>7.3f}"
          f"{np.mean(raw):>8.3f}{np.mean(b35):>8.3f}{np.mean(b20):>8.3f}{met.get('nori_turns_geom',0):>8.3f}")

print()
print("gap histogram, all layouts pooled (T):")
allg = np.concatenate([np.array(res[n]['gaps']) for n in res])
h, e = np.histogram(allg, bins=[0, .05, .1, .15, .2, .3, .4, .6, .8, 1.0, 1.5, 2.0, 10])
for i in range(len(h)):
    print(f"   {e[i]:>5.2f}..{e[i+1]:<5.2f} {h[i]:>5}  {'#'*int(60*h[i]/h.max())}")
print(f"   total gaps {len(allg)}, below 0.35 T: {int((allg<0.35).sum())} "
      f"({100*(allg<0.35).mean():.1f} %)")
json.dump({str(k): {kk: vv for kk, vv in v.items() if kk != 'gaps'} for k, v in res.items()},
          open(os.path.join(HERE, 'ray_holes.json'), 'w'), indent=1)
