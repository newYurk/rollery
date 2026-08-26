"""Adversarial check of sim/reference: layer count from ACTUAL final geometry vs measured
wrapper crossings on 36 rays; near-edge-inside / far-flap-outside; layout-4 core compactness+order.

Independent of run.py: reads only out/material_<L>.npy and out/particles_<L>.npz.
"""
import json, math, sys
import numpy as np

ROOT = '/Users/newyurk/Desktop/Home/Projects/rollery/sim/reference'
T, W = 1.0, 0.12
H = T + W                      # spiral pitch
BG, RICE, NORI = 0, 1, 2
KIND = {3: 'salmon', 4: 'cucumber', 5: 'tamago', 6: 'avocado', 7: 'shrimp'}
PX = 0.02
NRAY = 36

def ray(img, cr, cc, ang, step=0.25):
    n = int(img.shape[0] / 2 / step)
    d = np.arange(n) * step
    rr = np.round(cr - d * math.sin(ang)).astype(int)
    cc2 = np.round(cc + d * math.cos(ang)).astype(int)
    ok = (rr >= 0) & (rr < img.shape[0]) & (cc2 >= 0) & (cc2 < img.shape[1])
    return d[ok] * PX, img[rr[ok], cc2[ok]]

def runs_bounds(dist, seq, c, min_len=0.0, merge_gap=0.0):
    """contiguous runs of class c -> list of (r_in, r_out); optionally merge runs separated
    by a gap < merge_gap and drop runs thinner than min_len."""
    m = seq == c
    idx = np.nonzero(m)[0]
    if len(idx) == 0:
        return []
    br = np.nonzero(np.diff(idx) > 1)[0]
    groups = np.split(idx, br + 1)
    seg = [(dist[g[0]], dist[g[-1]]) for g in groups]
    if merge_gap > 0:
        out = [list(seg[0])]
        for a, b in seg[1:]:
            if a - out[-1][1] < merge_gap:
                out[-1][1] = b
            else:
                out.append([a, b])
        seg = [tuple(s) for s in out]
    if min_len > 0:
        seg = [s for s in seg if s[1] - s[0] >= min_len]
    return seg

def analyse(L):
    img = np.load(f'{ROOT}/out/material_{L}.npy')
    d = np.load(f'{ROOT}/out/particles_{L}.npz')
    xs, cls, ncol, Jp, vol = d['x'].astype(np.float64), d['cls'], d['nori_col'], d['J'], d['vol']
    met = json.load(open(f'{ROOT}/out/metrics_{L}.json'))
    cen_w = np.array(met['window_center_xy'], float)   # map window centre (world)
    npx = img.shape[0]
    fg = img != BG
    rows, cols = np.nonzero(fg)
    cr, cc = rows.mean(), cols.mean()
    # map centroid in world coords
    cen = np.array([cen_w[0] + (cc - npx / 2) * PX, cen_w[1] + (npx / 2 - cr) * PX])

    angs = np.deg2rad(np.arange(0, 360, 360 / NRAY))
    Rout, Rnori_in, Rnori_out, cross_raw, cross_rob = [], [], [], [], []
    for a in angs:
        dist, seq = ray(img, cr, cc, a)
        nz = np.nonzero(seq != BG)[0]
        Rout.append(dist[nz[-1]] if len(nz) else 0.0)
        raw = runs_bounds(dist, seq, NORI)
        rob = runs_bounds(dist, seq, NORI, min_len=0.04, merge_gap=0.04)  # ~1/3 band, ~2px gap
        cross_raw.append(len(raw)); cross_rob.append(len(rob))
        if rob:
            Rnori_in.append(rob[0][0]); Rnori_out.append(rob[-1][1])
        else:
            Rnori_in.append(np.nan); Rnori_out.append(np.nan)
    Rout = np.array(Rout); Rni = np.array(Rnori_in); Rno = np.array(Rnori_out)
    cross_raw = np.array(cross_raw, float); cross_rob = np.array(cross_rob, float)

    # --- ACTUAL final geometry ---------------------------------------------------
    # Rout: median of the 36-ray outer contour, and equal-area radius of the whole map
    Rout_med = float(np.median(Rout))
    A_map = float(fg.sum()) * PX * PX
    Rout_area = math.sqrt(A_map / math.pi)
    # Rcore: median inner radius of the innermost nori layer (the hole the spiral winds around)
    Rcore_med = float(np.nanmedian(Rni))
    # Rcore by area: everything strictly inside the innermost nori, per ray -> equal-area radius
    Rcore_area = math.sqrt(float(np.nanmean(Rni ** 2)))   # rms == equal-area for a star domain

    res = {}
    for tag, (Ro, Rc) in dict(
            med_med=(Rout_med, Rcore_med),
            area_area=(Rout_area, Rcore_area),
            med_area=(Rout_med, Rcore_area)).items():
        lay = (Ro - Rc) / H
        res[tag] = dict(Rout=round(Ro, 3), Rcore=round(Rc, 3), layers=round(lay, 3),
                        crossings_pred=round(lay + 1, 3),
                        d_raw=round(float(cross_raw.mean()) - (lay + 1), 3),
                        d_rob=round(float(cross_rob.mean()) - (lay + 1), 3))

    # --- near edge inside / far flap outside -------------------------------------
    nm = cls == NORI
    cmax = int(ncol[nm].max())
    rel = xs - cen
    r = np.hypot(rel[:, 0], rel[:, 1])
    ph = np.mod(np.arctan2(rel[:, 1], rel[:, 0]), 2 * math.pi)
    bi = np.mod(np.round(ph / (2 * math.pi / NRAY)).astype(int), NRAY)
    # smoothed contour (5-pt running median), same idea as run.py
    k = 2
    Rc36 = np.array([np.median(Rout[np.arange(i - k, i + k + 1) % NRAY]) for i in range(NRAY)])
    frac = r / Rc36[bi]
    near = nm & (ncol <= 0.02 * cmax)
    far = nm & (ncol >= 0.98 * cmax)
    edges = dict(
        near_frac_med=round(float(np.median(frac[near])), 3),
        near_r_med=round(float(np.median(r[near])), 3),
        near_n=int(near.sum()),
        far_frac_med=round(float(np.median(frac[far])), 3),
        far_r_med=round(float(np.median(r[far])), 3),
        far_n=int(far.sum()),
        Rout_med=round(Rout_med, 3), Rcore_med=round(Rcore_med, 3))

    # --- fillings: compactness + order -------------------------------------------
    core = []
    for c in sorted(set(int(v) for v in np.unique(cls) if v > NORI)):
        m = cls == c
        cx, cy = xs[m, 0].mean(), xs[m, 1].mean()
        rr = math.hypot(cx - cen[0], cy - cen[1])
        pp = math.degrees(math.atan2(cy - cen[1], cx - cen[0]))
        core.append(dict(kind=KIND[c], x=round(float(cx), 3), y=round(float(cy), 3),
                         r=round(rr, 3), r_over_Rout=round(rr / Rout_med, 3), phi=round(pp, 1),
                         n=int(m.sum())))
    return dict(layout=L, n_rays=NRAY, cross_raw_mean=round(float(cross_raw.mean()), 3),
                cross_rob_mean=round(float(cross_rob.mean()), 3),
                cross_raw_hist=np.bincount(cross_raw.astype(int)).tolist(),
                cross_rob_hist=np.bincount(cross_rob.astype(int)).tolist(),
                A_map_T2=round(A_map, 3), formulas=res, edges=edges, core=core,
                ref_nori_turns=met['nori_turns'],
                ref_crossings_predicted=met['crossings_predicted'],
                ref_crossings_predicted_core=met['crossings_predicted_core'])

if __name__ == '__main__':
    out = {}
    for L in (1, 2, 4):
        out[L] = analyse(L)
        print(json.dumps(out[L], indent=1))
    json.dump(out, open(f'{ROOT}/checks/attack_layers.json', 'w'), indent=1)
