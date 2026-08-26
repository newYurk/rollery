"""Does the adaptive 'fold nose' exclusion window hide real curvature reversals?

Recomputes the reference2 wrinkle metric on the FINAL particle dump of each layout and reports,
for the exact same midline/threshold, the count inside vs outside the excluded nose window.
Read-only: imports nothing from run.py, reimplements the published formula verbatim.
"""
import json, math, sys
import numpy as np

OUT = "/Users/newyurk/Desktop/Home/Projects/rollery/sim/reference2/out"
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _geom import (T_RICE, W_NORI, H_SHEET, L_SHEET, L_FLAP, R_MAT_MIN, BG_HOLE_T,
                   WR_DS, WR_KAPPA_MIN, WR_NOSE_T, WR_EDGE_T, WR_FIT_T, PACK_AIR, CORNER_R,
                   assert_same_geometry)
# The geometry used to live as a private copy in every one of these scripts (T = 1.0,
# W_NORI = 0.12, L_SHEET = 38.7, pitch H_NOM = 1.12). It is imported from run.py now: after the
# thickness correction of 26.08.2026 a stale copy would judge new dumps by the old spiral pitch
# and print plausible, wrong numbers without raising anything.


def movavg(P, k=3):
    ker = np.ones(k) / k
    Q = np.column_stack([np.convolve(P[:, 0], ker, 'same'), np.convolve(P[:, 1], ker, 'same')])
    m = k // 2
    return Q[m:len(Q) - m]


def midline(xs, nori_row, nori_col, nrows):
    a, b = nori_row == 0, nori_row == (nrows - 1)
    pa = xs[a][np.argsort(nori_col[a])]
    pb = xs[b][np.argsort(nori_col[b])]
    m = min(len(pa), len(pb))
    return movavg(np.asarray(0.5 * (pa[:m] + pb[:m]), np.float64))


def analyse(n):
    z = np.load(f"{OUT}/particles_{n}.npz")
    met = json.load(open(f"{OUT}/metrics_{n}.json"))
    assert_same_geometry(met)
    nrows = int(max(z['nori_row']) + 1)
    P = midline(z['x'].astype(np.float64), z['nori_row'], z['nori_col'], nrows)
    s0 = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])
    sq = np.arange(0.0, s0[-1], WR_DS)
    Q = np.column_stack([np.interp(sq, s0, P[:, 0]), np.interp(sq, s0, P[:, 1])])
    d = np.diff(Q, axis=0); seg = np.hypot(d[:, 0], d[:, 1])
    tv = d / np.maximum(seg, 1e-12)[:, None]
    cr = tv[:-1, 0] * tv[1:, 1] - tv[:-1, 1] * tv[1:, 0]
    dp = (tv[:-1] * tv[1:]).sum(1)
    ang = np.arctan2(cr, dp)
    ds = 0.5 * (seg[:-1] + seg[1:])
    kap = ang / np.maximum(ds, 1e-12)
    sv = sq[1:len(ang) + 1]
    cum = np.concatenate([[0.0], np.cumsum(np.abs(ang))])
    j = np.minimum(np.searchsorted(sv, sv + WR_NOSE_T), len(sv))
    i0 = int(np.argmax(cum[j] - cum[np.arange(len(sv))]))
    lo, hi = sv[i0], sv[i0] + WR_NOSE_T
    edge = (sv >= WR_EDGE_T) & (sv <= s0[-1] - WR_EDGE_T)
    strong = np.abs(kap) >= WR_KAPPA_MIN
    bamboo = np.abs(kap) >= 1.0 / R_MAT_MIN
    innose = (sv >= lo) & (sv <= hi)

    def rev(mask):
        s = np.sign(kap[mask])
        return int(np.sum(s[1:] != s[:-1])) if len(s) > 1 else 0

    pub = rev(edge & ~innose & strong)
    nonose = rev(edge & strong)
    hidden_bam = rev(edge & innose & bamboo)
    kmax_nose = float(np.max(np.abs(kap[edge & innose]))) if (edge & innose).any() else 0.0
    return dict(layout=n, name=met['layout_name'], len_T=round(float(s0[-1]), 2),
                nose_from=round(float(lo), 2), nose_to=round(float(hi), 2),
                nose_frac_pct=round(100 * WR_NOSE_T / float(s0[-1]), 1),
                published=pub, json_published=met['wrinkles'],
                nonose=nonose, json_nonose=met['wrinkles_nonose'],
                hidden_by_nose=nonose - pub,
                rev_in_nose_bamboo=hidden_bam,
                tightest_in_nose_kappa=round(kmax_nose, 2),
                tightest_in_nose_R_T=round(1.0 / kmax_nose, 3) if kmax_nose > 1e-6 else None)


if __name__ == "__main__":
    rows = [analyse(n) for n in range(1, 6)]
    hdr = ("L  name             band_T   nose_window_T   %band  wrinkles  nonose  hidden  "
           "rev_in_nose_bamboo  R_min_in_nose_T")
    print(hdr)
    for r in rows:
        flag = "" if r['published'] == r['json_published'] else "  <<MISMATCH vs json>>"
        print("%-3d%-16s%8.2f  %5.2f..%-6.2f%6.1f%10d%8d%8d%20d%17s%s" % (
            r['layout'], r['name'], r['len_T'], r['nose_from'], r['nose_to'], r['nose_frac_pct'],
            r['published'], r['nonose'], r['hidden_by_nose'], r['rev_in_nose_bamboo'],
            r['tightest_in_nose_R_T'], flag))


# --------------------------------------------------------------------------- amplitude, nose included
def amp_split(n):
    """wrinkle_amp_T as run.py computes it (nose window + 0.9 T pad excluded) vs the same residual
    measured INSIDE that window.  run.py never looks inside, so its 'amplitude < 0.3 T' is untested there."""
    z = np.load(f"{OUT}/particles_{n}.npz")
    met = json.load(open(f"{OUT}/metrics_{n}.json"))
    assert_same_geometry(met)
    nrows = int(max(z['nori_row']) + 1)
    P = midline(z['x'].astype(np.float64), z['nori_row'], z['nori_col'], nrows)
    s0 = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])
    sq = np.arange(0.0, s0[-1], WR_DS)
    Q = np.column_stack([np.interp(sq, s0, P[:, 0]), np.interp(sq, s0, P[:, 1])])
    d = np.diff(Q, axis=0); seg = np.hypot(d[:, 0], d[:, 1])
    tv = d / np.maximum(seg, 1e-12)[:, None]
    ang = np.arctan2(tv[:-1, 0] * tv[1:, 1] - tv[:-1, 1] * tv[1:, 0], (tv[:-1] * tv[1:]).sum(1))
    sv = sq[1:len(ang) + 1]
    cum = np.concatenate([[0.0], np.cumsum(np.abs(ang))])
    j = np.minimum(np.searchsorted(sv, sv + WR_NOSE_T), len(sv))
    i0 = int(np.argmax(cum[j] - cum[np.arange(len(sv))]))
    lo, hi = sv[i0], sv[i0] + WR_NOSE_T
    nfit = 2 * int(round(WR_FIT_T / WR_DS)) + 1
    m = (nfit - 1) // 2
    xx = np.arange(-m, m + 1, dtype=float)
    ker = np.linalg.pinv(np.vander(xx, 3, increasing=True))[0][::-1]
    dev = np.hypot(Q[:, 0] - np.convolve(Q[:, 0], ker, 'same'), Q[:, 1] - np.convolve(Q[:, 1], ker, 'same'))
    valid = np.zeros(len(Q), bool); valid[m:len(Q) - m] = True
    valid &= (sq >= WR_EDGE_T) & (sq <= s0[-1] - WR_EDGE_T)
    outside = valid & ~((sq >= lo - WR_FIT_T) & (sq <= hi + WR_FIT_T))
    inside = valid & (sq >= lo) & (sq <= hi)
    return dict(layout=n, name=met['layout_name'],
                amp_published=met['wrinkle_amp_T'],
                amp_recomputed_outside=round(float(dev[outside].max()), 4),
                amp_inside_nose=round(float(dev[inside].max()), 4) if inside.any() else None,
                exceeds_0p3T_inside=bool(inside.any() and dev[inside].max() >= 0.3))


print()
print("amplitude of the residual, T   (run.py reports only the 'outside' column)")
print("L  name             published  outside  INSIDE_nose_window  >=0.3 T?")
for n in range(1, 6):
    a = amp_split(n)
    print("%-3d%-16s%10.4f%9.4f%20.4f%10s" % (a['layout'], a['name'], a['amp_published'],
          a['amp_recomputed_outside'], a['amp_inside_nose'], "YES" if a['exceeds_0p3T_inside'] else "no"))
