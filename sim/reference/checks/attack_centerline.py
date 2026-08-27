"""Raster-free version of the same attack: reconstruct the nori sheet centreline from
nori_col (arclength index along the sheet), then measure winding, crossings on 36 rays,
Rcore/Rout from the ACTUAL final geometry, and where the two sheet ends sit.
"""
import json, math
import numpy as np

ROOT = '/Users/newyurk/Desktop/Home/Projects/rollery/sim/reference'
T, W = 1.0, 0.12
H = T + W
BG, RICE, NORI = 0, 1, 2
PX = 0.02
NRAY = 36

def centreline(L):
    d = np.load(f'{ROOT}/out/particles_{L}.npz')
    xs, cls, ncol = d['x'].astype(np.float64), d['cls'], d['nori_col']
    m = cls == NORI
    cols = ncol[m]; p = xs[m]
    order = np.argsort(cols)
    cols = cols[order]; p = p[order]
    uc, start = np.unique(cols, return_index=True)
    seg = np.split(np.arange(len(cols)), start[1:])
    cl = np.array([p[s].mean(axis=0) for s in seg])       # centreline point per column
    return uc, cl, xs, cls

def analyse(L):
    met = json.load(open(f'{ROOT}/out/metrics_{L}.json'))
    img = np.load(f'{ROOT}/out/material_{L}.npy')
    uc, cl, xs, cls = centreline(L)
    npx = img.shape[0]
    cen_w = np.array(met['window_center_xy'], float)
    fg = img != BG
    rows, cols_ = np.nonzero(fg)
    cr, cc = rows.mean(), cols_.mean()
    cen = np.array([cen_w[0] + (cc - npx / 2) * PX, cen_w[1] + (npx / 2 - cr) * PX])

    rel = cl - cen
    r = np.hypot(rel[:, 0], rel[:, 1])
    ph = np.arctan2(rel[:, 1], rel[:, 0])
    php = np.unwrap(ph)
    winding = abs(php[-1] - php[0]) / (2 * math.pi)

    # crossings on 36 rays, raster-free: count sign changes of (phi(s) - a) mod 2pi
    angs = np.deg2rad(np.arange(0, 360, 360 / NRAY))
    cross = []
    for a in angs:
        # unwrapped phi crosses a + 2*pi*k
        lo, hi = php.min(), php.max()
        k0 = math.floor((lo - a) / (2 * math.pi)); k1 = math.ceil((hi - a) / (2 * math.pi))
        n = 0
        for k in range(k0, k1 + 1):
            lev = a + 2 * math.pi * k
            s = np.sign(php - lev)
            n += int(np.sum(s[1:] * s[:-1] < 0))
        cross.append(n)
    cross = np.array(cross, float)

    # ACTUAL geometry: Rcore = min radius reached by the sheet (the hole it winds around),
    #                  Rout  = max radius reached by the sheet (outer wrap)
    # plus the 36-ray outer contour of ALL material
    Rout36 = []
    for a in angs:
        step = 0.25
        nn = int(npx / 2 / step); dd = np.arange(nn) * step
        rr = np.round(cr - dd * math.sin(a)).astype(int); cc2 = np.round(cc + dd * math.cos(a)).astype(int)
        ok = (rr >= 0) & (rr < npx) & (cc2 >= 0) & (cc2 < npx)
        seq = img[rr[ok], cc2[ok]]; dist = dd[ok] * PX
        nz = np.nonzero(seq != BG)[0]
        Rout36.append(dist[nz[-1]] if len(nz) else 0.0)
    Rout36 = np.array(Rout36)
    Rout_med = float(np.median(Rout36))

    # per-ray innermost / outermost nori radius from the CENTRELINE (raster-free)
    bi = np.mod(np.round(np.mod(ph, 2 * math.pi) / (2 * math.pi / NRAY)).astype(int), NRAY)
    r_in_ray, r_out_ray = [], []
    for i in range(NRAY):
        sel = r[bi == i]
        r_in_ray.append(sel.min() if len(sel) else np.nan)
        r_out_ray.append(sel.max() if len(sel) else np.nan)
    r_in_ray = np.array(r_in_ray); r_out_ray = np.array(r_out_ray)
    Rcore_ray_med = float(np.nanmedian(r_in_ray))
    Rcore_ray_eq = float(math.sqrt(np.nanmean(r_in_ray ** 2)))
    Rnori_out_med = float(np.nanmedian(r_out_ray))

    variants = {}
    for tag, (Ro, Rc) in dict(
        contour_vs_ray_core=(Rout_med, Rcore_ray_med),
        contour_vs_eqcore=(Rout_med, Rcore_ray_eq),
        noriout_vs_raycore=(Rnori_out_med, Rcore_ray_med),
        sheet_span=(float(r.max()), float(r.min())),
    ).items():
        lay = (Ro - Rc) / H
        variants[tag] = dict(Rout=round(Ro, 3), Rcore=round(Rc, 3), layers=round(lay, 3),
                             crossings_pred=round(lay + 1, 3),
                             delta_vs_measured=round(float(cross.mean()) - (lay + 1), 3))

    # sheet ends: s=0 is the near (grabbed/tucked) edge, s=max the far flap
    k = 2
    Rc36 = np.array([np.median(Rout36[np.arange(i - k, i + k + 1) % NRAY]) for i in range(NRAY)])
    def frac_at(idx):
        b = int(np.mod(round(np.mod(ph[idx], 2 * math.pi) / (2 * math.pi / NRAY)), NRAY))
        return round(float(r[idx] / Rc36[b]), 3)
    n_end = max(3, len(r) // 100)
    ends = dict(near_r=round(float(r[:n_end].mean()), 3), near_frac=frac_at(0),
                far_r=round(float(r[-n_end:].mean()), 3), far_frac=frac_at(len(r) - 1),
                r_min=round(float(r.min()), 3), r_min_at_s=int(uc[int(np.argmin(r))]),
                r_max=round(float(r.max()), 3), r_max_at_s=int(uc[int(np.argmax(r))]),
                s_max=int(uc[-1]), Rout_med=round(Rout_med, 3))

    return dict(layout=L, winding_turns=round(float(winding), 3),
                crossings_centreline_mean=round(float(cross.mean()), 3),
                crossings_hist=np.bincount(cross.astype(int)).tolist(),
                ref_nori_turns=met['nori_turns'],
                ref_crossings_pred=met['crossings_predicted'],
                ref_crossings_pred_core=met['crossings_predicted_core'],
                Rcore_ray_med=round(Rcore_ray_med, 3), Rcore_ray_eq=round(Rcore_ray_eq, 3),
                ref_Rcore_pred=met['Rcore_pred_T'], ref_Rcore_hollow=met['Rcore_hollow_T'],
                variants=variants, ends=ends)

if __name__ == '__main__':
    out = {}
    for L in (1, 2, 4):
        out[L] = analyse(L)
        print(json.dumps(out[L], indent=1))
    json.dump(out, open(f'{ROOT}/checks/attack_centerline.json', 'w'), indent=1)
