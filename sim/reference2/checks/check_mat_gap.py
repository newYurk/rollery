"""Is the nori actually in contact with the mat, or does it float free of it?

reference2 models the mat analytically (circle of radius R about (xc, y_cen), or a rounded square
of half-side R at press), so there are no mat particles and no metric in run.py measures the
nori-to-mat distance -- `nori_max_gap_T` in metrics_*.json is the gap between CONSECUTIVE NORI
PARTICLES (a tear test), not the nori-to-mat gap.  This measures the real thing on the final dump.

For each angular bin around the roll it reports the distance from the mat surface to the nearest
nori particle.  In contact that distance is about half a nori row thickness (W_NORI/2/rows) and the
tolerance is half a nori particle spacing.  Both follow run.py: they were 0.06 U and ~0.025 U while
the nori was 0.12 U thick, and the first of them is 50x smaller now that it is 0.02 U.
"""
import json
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
NBIN = 180


def mat_sdf(P, xc, yc, R, shape):
    dd = P - np.array([xc, yc])
    if shape == 'circle':
        return np.hypot(dd[:, 0], dd[:, 1]) - R          # >0 outside the mat, <0 inside
    hs = R - CORNER_R
    q = np.abs(dd) - hs
    m = np.maximum(q, 0.0)
    return np.hypot(m[:, 0], m[:, 1]) + np.minimum(np.maximum(q[:, 0], q[:, 1]), 0.0) - CORNER_R


def run(n):
    z = np.load(f"{OUT}/particles_{n}.npz")
    met = json.load(open(f"{OUT}/metrics_{n}.json"))
    assert_same_geometry(met)
    mat = met['mat']
    xc, yc, R, shape = mat['xc_final'], mat['y_cen_press'], mat['R_final'], mat['press_shape']
    x = z['x'].astype(np.float64)
    nori = z['nori_row'] >= 0
    nrows = int(z['nori_row'].max() + 1)
    nori_dy = W_NORI / nrows
    dx_p = met['nori_particle_spacing_T']

    d = mat_sdf(x[nori], xc, yc, R, shape)               # signed distance of every nori particle
    gap = -d                                             # how deep inside the mat it sits
    th = np.arctan2(x[nori][:, 1] - yc, x[nori][:, 0] - xc)
    b = np.clip(((th + np.pi) / (2 * np.pi) * NBIN).astype(int), 0, NBIN - 1)

    per = np.full(NBIN, np.nan)
    for i in range(NBIN):
        m = b == i
        if m.any():
            per[i] = gap[m].min()                        # nearest nori to the mat in this sector
    ok = ~np.isnan(per)
    contact_tol = 0.5 * dx_p
    expect = 0.5 * nori_dy                               # centre of the outer row when touching
    free = per[ok] - expect                              # excess beyond geometric contact
    return dict(layout=n, name=met['layout_name'], shape=shape, R=R,
                nori_rows=nrows, nori_dy=round(nori_dy, 4), particle_dx=dx_p,
                tol_half_spacing_T=round(contact_tol, 4),
                bins_with_nori=int(ok.sum()),
                gap_median_T=round(float(np.median(free)), 4),
                gap_p90_T=round(float(np.percentile(free, 90)), 4),
                gap_max_T=round(float(free.max()), 4),
                bins_off_mat_pct=round(100.0 * float((free > contact_tol).mean()), 1),
                bins_off_mat_gt_0p3T_pct=round(100.0 * float((free > 0.3).mean()), 1),
                json_nori_max_gap_T=met['nori_max_gap_T'])


if __name__ == "__main__":
    rows = [run(n) for n in range(1, 6)]
    print("L  name             shape   bins  tol_T   gap_med  gap_p90  gap_max   %bins_off_mat  %bins>0.3T")
    for r in rows:
        print("%-3d%-16s%-8s%5d%8.3f%9.3f%9.3f%9.3f%15.1f%12.1f" % (
            r['layout'], r['name'], r['shape'], r['bins_with_nori'], r['tol_half_spacing_T'],
            r['gap_median_T'], r['gap_p90_T'], r['gap_max_T'],
            r['bins_off_mat_pct'], r['bins_off_mat_gt_0p3T_pct']))
    print()
    print("note: metrics_*.json 'nori_max_gap_T' =",
          [r['json_nori_max_gap_T'] for r in rows], "is nori-particle-to-nori-particle, NOT nori-to-mat.")
