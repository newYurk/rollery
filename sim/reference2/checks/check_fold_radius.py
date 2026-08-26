"""Where is the tightest bend of the nori, and is it really a "free-end artifact"?

README §4.6 dismisses fold_radius_min_T (0.13..0.21 T) as "caught on the free ends of the band".
This locates every stretch of the FINAL midline bent tighter than the mat's own minimum radius
(R_MAT_MIN = 0.5 T) and reports how far each is from the two free ends, so the claim can be checked.
A bend tighter than 0.5 T is, by the model's own premise, impossible: the nori is on the mat and the
mat is bamboo.
"""
import json, math
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
WR_DS, WR_EDGE_T = 0.25, 1.0
WR_NOSE_T = math.pi * (T + W_NORI)


def midline(z):
    xs = z['x'].astype(np.float64); nr, nc = z['nori_row'], z['nori_col']
    n = int(nr.max() + 1)
    a, b = nr == 0, nr == n - 1
    pa = xs[a][np.argsort(nc[a])]; pb = xs[b][np.argsort(nc[b])]
    m = min(len(pa), len(pb))
    P = 0.5 * (pa[:m] + pb[:m])
    k = np.ones(3) / 3
    Q = np.column_stack([np.convolve(P[:, 0], k, 'same'), np.convolve(P[:, 1], k, 'same')])
    return Q[1:-1]


def run(n):
    z = np.load(f"{OUT}/particles_{n}.npz")
    met = json.load(open(f"{OUT}/metrics_{n}.json"))
    assert_same_geometry(met)
    P = midline(z)
    s0 = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(P, axis=0).T))])
    L = float(s0[-1])
    sq = np.arange(0.0, L, WR_DS)
    Q = np.column_stack([np.interp(sq, s0, P[:, 0]), np.interp(sq, s0, P[:, 1])])
    d = np.diff(Q, axis=0); seg = np.hypot(d[:, 0], d[:, 1])
    tv = d / np.maximum(seg, 1e-12)[:, None]
    ang = np.arctan2(tv[:-1, 0] * tv[1:, 1] - tv[:-1, 1] * tv[1:, 0], (tv[:-1] * tv[1:]).sum(1))
    kap = ang / np.maximum(0.5 * (seg[:-1] + seg[1:]), 1e-12)
    sv = sq[1:len(ang) + 1]

    # the nose window run.py excludes, recomputed identically
    cum = np.concatenate([[0.0], np.cumsum(np.abs(ang))])
    j = np.minimum(np.searchsorted(sv, sv + WR_NOSE_T), len(sv))
    i0 = int(np.argmax(cum[j] - cum[np.arange(len(sv))]))
    lo, hi = sv[i0], sv[i0] + WR_NOSE_T

    tight = np.abs(kap) >= 1.0 / R_MAT_MIN
    hits = []
    i = 0
    while i < len(tight):
        if tight[i]:
            k = i
            while k + 1 < len(tight) and tight[k + 1]:
                k += 1
            sl, sh = sv[i], sv[k]
            kk = float(np.max(np.abs(kap[i:k + 1])))
            hits.append(dict(s_from=round(float(sl), 2), s_to=round(float(sh), 2),
                             R_T=round(1.0 / kk, 3),
                             dist_to_nearest_end_T=round(float(min(sl, L - sh)), 2),
                             inside_nose_window=bool(sl >= lo and sh <= hi),
                             inside_edge_exclusion=bool(sh < WR_EDGE_T or sl > L - WR_EDGE_T)))
            i = k + 1
        else:
            i += 1
    return dict(layout=n, name=met['layout_name'], band_T=round(L, 2),
                nose_window=[round(float(lo), 2), round(float(hi), 2)],
                json_fold_radius_min_T=met['fold_radius_min_T'],
                json_wrinkles=met['wrinkles'], json_wrinkles_mat=met['wrinkles_mat'],
                tight_spots=hits)


if __name__ == "__main__":
    for n in range(1, 6):
        r = run(n)
        print(f"--- layout {r['layout']} {r['name']}  band {r['band_T']} T, "
              f"nose window excluded {r['nose_window']} T, "
              f"published wrinkles={r['json_wrinkles']} wrinkles_mat={r['json_wrinkles_mat']}")
        if not r['tight_spots']:
            print("    no bend tighter than R_MAT_MIN = 0.5 T")
        for h in r['tight_spots']:
            tag = []
            if h['inside_nose_window']:
                tag.append("HIDDEN by nose window")
            if h['inside_edge_exclusion']:
                tag.append("in 1 T edge exclusion")
            print(f"    s={h['s_from']:>6}..{h['s_to']:<6} R={h['R_T']:.3f} T "
                  f"({R_MAT_MIN / h['R_T']:.1f}x tighter than the mat), "
                  f"{h['dist_to_nearest_end_T']:>5} T from the nearest free end"
                  + ("   <- " + ", ".join(tag) if tag else ""))
