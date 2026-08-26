"""Where the two sheet ends and the layout-4 fillings actually sit, relative to the
innermost nori turn (the core boundary) and the outer contour. Raster-free where possible."""
import json, math
import numpy as np

OUTD = '/Users/newyurk/Desktop/Home/Projects/rollery/sim/reference/checks/rerun'
ROOT = '/Users/newyurk/Desktop/Home/Projects/rollery/sim/reference'
BG, RICE, NORI = 0, 1, 2
KIND = {3: 'salmon', 4: 'cucumber', 5: 'tamago', 6: 'avocado', 7: 'shrimp'}
PX, NRAY, H = 0.02, 36, 1.12
INIT_U = {4: dict(cucumber=1.5, tamago=3.2, salmon=5.9, avocado=8.2),
          2: dict(tamago=1.5), 1: {}}

def load(L):
    met = json.load(open(f'{OUTD}/metrics_{L}.json'))
    img = np.load(f'{OUTD}/material_{L}.npy')
    d = np.load(f'{OUTD}/particles_{L}.npz')
    npx = img.shape[0]
    cen_w = np.array(met['window_center_xy'], float)
    rows, cols_ = np.nonzero(img != BG)
    cr, cc = rows.mean(), cols_.mean()
    cen = np.array([cen_w[0] + (cc - npx / 2) * PX, cen_w[1] + (npx / 2 - cr) * PX])
    return met, img, d, cen, cr, cc

def analyse(L):
    met, img, d, cen, cr, cc = load(L)
    xs, cls, ncol = d['x'].astype(np.float64), d['cls'], d['nori_col']
    npx = img.shape[0]
    angs = np.deg2rad(np.arange(0, 360, 360 / NRAY))

    # nori centreline -> per-ray innermost nori radius (core boundary), raster-free
    m = cls == NORI
    o = np.argsort(ncol[m]); colsn = ncol[m][o]; pn = xs[m][o]
    uc, st = np.unique(colsn, return_index=True)
    cl = np.array([pn[s].mean(axis=0) for s in np.split(np.arange(len(colsn)), st[1:])])
    reln = cl - cen; rn = np.hypot(reln[:, 0], reln[:, 1]); phn = np.mod(np.arctan2(reln[:, 1], reln[:, 0]), 2 * math.pi)
    bin_n = np.mod(np.round(phn / (2 * math.pi / NRAY)).astype(int), NRAY)
    r_core_ray = np.array([rn[bin_n == i].min() if (bin_n == i).any() else np.nan for i in range(NRAY)])

    # outer contour of ALL material, 36 rays, 5-pt median smoothed
    Rout = []
    for a in angs:
        step = 0.25; nn = int(npx / 2 / step); dd = np.arange(nn) * step
        rr = np.round(cr - dd * math.sin(a)).astype(int); c2 = np.round(cc + dd * math.cos(a)).astype(int)
        ok = (rr >= 0) & (rr < npx) & (c2 >= 0) & (c2 < npx)
        seq = img[rr[ok], c2[ok]]; dist = dd[ok] * PX
        nz = np.nonzero(seq != BG)[0]
        Rout.append(dist[nz[-1]] if len(nz) else 0.0)
    Rout = np.array(Rout)
    Rs = np.array([np.median(Rout[np.arange(i - 2, i + 3) % NRAY]) for i in range(NRAY)])

    def at(r_, ph_):
        b = int(np.mod(round(np.mod(ph_, 2 * math.pi) / (2 * math.pi / NRAY)), NRAY))
        return Rs[b], r_core_ray[b]

    # --- void fraction inside the core boundary -------------------------------------
    yy, xx = np.mgrid[0:npx, 0:npx]
    rr_px = np.hypot(yy - cr, xx - cc) * PX
    ppx = np.mod(np.arctan2(-(yy - cr), xx - cc), 2 * math.pi)
    bpx = np.mod(np.round(ppx / (2 * math.pi / NRAY)).astype(int), NRAY)
    core_mask = rr_px < np.nan_to_num(r_core_ray, nan=0.0)[bpx]
    void = float(np.mean(img[core_mask] == BG)) if core_mask.any() else float('nan')
    core_area = float(core_mask.sum()) * PX * PX

    # --- sheet ends -----------------------------------------------------------------
    Rc_med = float(np.nanmedian(r_core_ray)); Rout_med = float(np.median(Rout))
    ends = {}
    for tag, idx in (('near', 0), ('far', len(rn) - 1)):
        Rl, Rcl = at(rn[idx], phn[idx])
        ends[tag] = dict(r=round(float(rn[idx]), 3), phi=round(math.degrees(phn[idx]), 1),
                         R_contour_local=round(float(Rl), 3), R_core_local=round(float(Rcl), 3),
                         frac_of_contour=round(float(rn[idx] / Rl), 3),
                         inside_core=bool(rn[idx] < Rcl + 1e-9))
    ends['r_min_along_sheet'] = round(float(rn.min()), 3)
    ends['s_of_r_min_frac'] = round(float(np.argmin(rn) / (len(rn) - 1)), 3)
    ends['near_is_innermost'] = bool(np.argmin(rn) < 0.05 * len(rn))

    # --- fillings -------------------------------------------------------------------
    fills = []
    for c in sorted(set(int(v) for v in np.unique(cls) if v > NORI)):
        mm = cls == c
        cx, cy = xs[mm, 0].mean(), xs[mm, 1].mean()
        rr_ = math.hypot(cx - cen[0], cy - cen[1]); pp = np.mod(math.atan2(cy - cen[1], cx - cen[0]), 2 * math.pi)
        Rl, Rcl = at(rr_, pp)
        # fraction of this filling's particles that lie inside the core boundary
        rel = xs[mm] - cen; rp = np.hypot(rel[:, 0], rel[:, 1]); php = np.mod(np.arctan2(rel[:, 1], rel[:, 0]), 2 * math.pi)
        b = np.mod(np.round(php / (2 * math.pi / NRAY)).astype(int), NRAY)
        inside = float(np.mean(rp < np.nan_to_num(r_core_ray, nan=0.0)[b]))
        fills.append(dict(kind=KIND[c], x=round(float(cx), 3), y=round(float(cy), 3),
                          r=round(rr_, 3), phi_deg=round(float(math.degrees(pp)), 1),
                          r_over_Rout_med=round(rr_ / Rout_med, 3),
                          R_core_local=round(float(Rcl), 3), R_contour_local=round(float(Rl), 3),
                          centroid_inside_core=bool(rr_ < Rcl), frac_particles_inside_core=round(inside, 3)))
    # order + compactness
    byx = [f['kind'] for f in sorted(fills, key=lambda f: f['x'])]
    init = [k for k, _ in sorted(INIT_U.get(L, {}).items(), key=lambda kv: kv[1])]
    P = np.array([[f['x'], f['y']] for f in fills])
    if len(P) > 1:
        dm = np.hypot(P[:, None, 0] - P[None, :, 0], P[:, None, 1] - P[None, :, 1])
        spread = float(dm.max())
    else:
        spread = 0.0
    return dict(layout=L, Rout_med=round(Rout_med, 3), Rcore_med=round(Rc_med, 3),
                core_area_T2=round(core_area, 3), core_void_frac=round(void, 3),
                ends=ends, fillings=fills, order_final_by_x=byx, order_initial_by_x=init,
                order_preserved=bool(byx == init) if init else None,
                core_spread_T=round(spread, 3), core_spread_over_Rout=round(spread / Rout_med, 3),
                ref_core_order_left_to_right=met['core_order_left_to_right'])

if __name__ == '__main__':
    out = {}
    for L in (4,):
        out[L] = analyse(L)
        print(json.dumps(out[L], indent=1))
    json.dump(out, open(f'{ROOT}/checks/rerun_core_edges.json', 'w'), indent=1)
