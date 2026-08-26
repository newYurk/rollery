"""Adversarial re-measurement of the reference's conservation / leakage claims.

Reads ONLY the outputs of run.py (out/particles_<L>.npz, out/material_<L>.npy, out/metrics_<L>.json)
and recomputes, independently of run.py's own code path:

  1. conservation  Sum(vol0 * J_end) / Sum(vol0), total and per class
  2. escaped       clamp-boundary occupancy + non-finite + out-of-domain particle count
  3. leakage       material further than TOL outside the fitted contour, under TWO contour
                   definitions: run.py's (36 rays on the raster, 5-ray running median) and an
                   independent particle-only contour (per-bin high percentile, median-smoothed)
  4. nori band     max particle gap along the band vs the initial spacing, plus a real
                   connected-component test on the nori point cloud

Usage:  python verify_conservation.py [--layouts 1,4,5] [--dir ../out]
"""
import argparse, json, math, os
import numpy as np

CLASS_BG, CLASS_RICE, CLASS_NORI = 0, 1, 2
MAT = {0: 'bg', 1: 'rice', 2: 'nori', 3: 'salmon', 4: 'cucumber', 5: 'tamago', 6: 'avocado', 7: 'shrimp'}
X0, X1, Y0, Y1 = -2.0, 48.0, -0.4, 12.6
TOL = 0.3
N_ANG = 36


def ray_rout(img, c_row, c_col, ang, px, step=0.25):
    npx = img.shape[0]
    n = int(npx / 2 / step)
    d = np.arange(n) * step
    rr = np.round(c_row - d * math.sin(ang)).astype(int)
    cc = np.round(c_col + d * math.cos(ang)).astype(int)
    ok = (rr >= 0) & (rr < npx) & (cc >= 0) & (cc < npx)
    rr, cc, d = rr[ok], cc[ok], d[ok]
    seq = img[rr, cc]
    nz = np.nonzero(seq != CLASS_BG)[0]
    return (d[nz[-1]] * px) if len(nz) else 0.0


def median_smooth(r, k=2):
    n = len(r)
    return np.array([np.median(r[np.arange(i - k, i + k + 1) % n]) for i in range(n)])


def contour_from_raster(img, px, center):
    """run.py's own definition: centroid of the foreground, 36 rays, last non-bg pixel, 5-ray median."""
    npx = img.shape[0]
    rows, cols = np.nonzero(img != CLASS_BG)
    c_row, c_col = rows.mean(), cols.mean()
    cen = (center[0] + (c_col - npx / 2) * px, center[1] + (npx / 2 - c_row) * px)
    angs = np.deg2rad(np.arange(0, 360, 360 // N_ANG))
    rout = np.array([ray_rout(img, c_row, c_col, a, px) for a in angs])
    return cen, median_smooth(rout), rout


def contour_from_particles(xs, cen, pct=99.0):
    """Independent contour: per-bin high percentile of the particle radius, then a 5-bin median.
    Uses no raster, so a rasterised stray disc cannot inflate it."""
    rel = xs - np.asarray(cen, np.float64)
    r = np.hypot(rel[:, 0], rel[:, 1])
    ph = np.mod(np.arctan2(rel[:, 1], rel[:, 0]), 2 * math.pi)
    bi = np.mod(np.round(ph / (2 * math.pi / N_ANG)).astype(int), N_ANG)
    rb = np.zeros(N_ANG)
    for i in range(N_ANG):
        m = bi == i
        rb[i] = np.percentile(r[m], pct) if m.any() else 0.0
    return median_smooth(rb), r, bi


def components(pts, rad):
    """Connected components of a point cloud at linking radius `rad` (uniform grid + union-find)."""
    n = len(pts)
    parent = np.arange(n)

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    lo = pts.min(0)
    cell = np.floor((pts - lo) / rad).astype(np.int64)
    buckets = {}
    for i, (cx, cy) in enumerate(cell):
        buckets.setdefault((cx, cy), []).append(i)
    r2 = rad * rad
    for (cx, cy), idx in buckets.items():
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nb = buckets.get((cx + dx, cy + dy))
                if not nb:
                    continue
                for i in idx:
                    d = pts[nb] - pts[i]
                    hit = np.nonzero(d[:, 0] ** 2 + d[:, 1] ** 2 <= r2)[0]
                    for h in hit:
                        union(i, nb[h])
    roots = np.array([find(i) for i in range(n)])
    _, inv, cnt = np.unique(roots, return_inverse=True, return_counts=True)
    return len(cnt), np.sort(cnt)[::-1]


def check(layout, d):
    """`layout` is the run TAG used by run.py (out/metrics_<tag>.json)."""
    npz = np.load(os.path.join(d, f'particles_{layout}.npz'))
    img = np.load(os.path.join(d, f'material_{layout}.npy'))
    met = json.load(open(os.path.join(d, f'metrics_{layout}.json')))
    xs = npz['x'].astype(np.float64)
    cls = npz['cls']
    J = npz['J'].astype(np.float64)
    vol = npz['vol'].astype(np.float64)
    nrow, ncol = npz['nori_row'], npz['nori_col']
    px = met['px_T']
    center = tuple(met['window_center_xy'])
    out = {'tag': str(layout), 'layout': met['layout'], 'layout_name': met['layout_name'], 'n_particles': int(len(cls))}

    # ---- 1. conservation
    tot0, tot1 = float(vol.sum()), float((vol * J).sum())
    out['conservation'] = round(tot1 / tot0, 4)
    out['conservation_json'] = met['conservation']
    out['volume_start_T2'] = round(tot0, 3)
    out['volume_end_T2'] = round(tot1, 3)
    out['deficit_T2'] = round(tot0 - tot1, 3)
    per = {}
    for c in np.unique(cls):
        m = cls == c
        per[MAT[int(c)]] = dict(n=int(m.sum()),
                                cons=round(float((vol[m] * J[m]).sum() / vol[m].sum()), 4),
                                deficit_T2=round(float((vol[m] * (1 - J[m])).sum()), 3),
                                J_min=round(float(J[m].min()), 3), J_p01=round(float(np.percentile(J[m], 1)), 3),
                                J_med=round(float(np.median(J[m])), 3), J_max=round(float(J[m].max()), 3))
    out['per_class'] = per
    out['J_frac_below_0.9'] = round(float(np.mean(J < 0.9)), 4)
    out['J_frac_above_1.0'] = round(float(np.mean(J > 1.0)), 4)
    out['conservation_pass'] = bool(tot1 / tot0 >= 0.97)

    # ---- 2. escaped / clamp boundary
    dx = met['timing']['dx']
    lo0, hi0 = X0 + 2 * dx, X1 - 3 * dx
    lo1, hi1 = Y0 + 2 * dx, Y1 - 3 * dx
    eps = 1e-5
    on_wall = int(np.sum((np.abs(xs[:, 0] - lo0) < eps) | (np.abs(xs[:, 0] - hi0) < eps) |
                         (np.abs(xs[:, 1] - lo1) < eps) | (np.abs(xs[:, 1] - hi1) < eps)))
    out['escaped_counter'] = int(met['escaped'])
    out['particles_on_clamp_wall'] = on_wall
    out['nonfinite'] = int(np.sum(~np.isfinite(xs).all(1)))
    out['outside_domain'] = int(np.sum((xs[:, 0] < lo0 - eps) | (xs[:, 0] > hi0 + eps) |
                                       (xs[:, 1] < lo1 - eps) | (xs[:, 1] > hi1 + eps)))
    out['y_min'] = round(float(xs[:, 1].min()), 4)
    out['escaped_pass'] = bool(met['escaped'] == 0 and on_wall == 0 and out['nonfinite'] == 0)

    # ---- 3. leakage past the contour
    cen, rs_raster, rout_raw = contour_from_raster(img, px, center)
    rel = xs - np.asarray(cen, np.float64)
    r = np.hypot(rel[:, 0], rel[:, 1])
    ph = np.mod(np.arctan2(rel[:, 1], rel[:, 0]), 2 * math.pi)
    bi = np.mod(np.round(ph / (2 * math.pi / N_ANG)).astype(int), N_ANG)
    exc_r = r - rs_raster[bi]
    out['contour_raster'] = dict(
        max_excess_T=round(float(exc_r.max()), 3),
        n_beyond_tol=int(np.sum(exc_r > TOL)),
        frac_beyond_tol=round(float(np.mean(exc_r > TOL)), 5),
        by_class={MAT[int(c)]: int(np.sum((exc_r > TOL) & (cls == c))) for c in np.unique(cls)
                  if np.any((exc_r > TOL) & (cls == c))},
        json_max_excess=met['tail_outside_max_excess_T'], json_n=met['tail_outside_particles'],
        Rout_ray_min=round(float(rout_raw.min()), 3), Rout_ray_max=round(float(rout_raw.max()), 3))
    rs_part, r2, bi2 = contour_from_particles(xs, cen, pct=99.0)
    exc_p = r2 - rs_part[bi2]
    out['contour_particles_p99'] = dict(
        max_excess_T=round(float(exc_p.max()), 3),
        n_beyond_tol=int(np.sum(exc_p > TOL)),
        frac_beyond_tol=round(float(np.mean(exc_p > TOL)), 5),
        by_class={MAT[int(c)]: int(np.sum((exc_p > TOL) & (cls == c))) for c in np.unique(cls)
                  if np.any((exc_p > TOL) & (cls == c))})
    lk = exc_r > TOL
    if lk.any():
        deg = np.degrees(ph[lk])
        out['contour_raster']['leak_phi_deg'] = [round(float(np.percentile(deg, 5)), 0), round(float(np.percentile(deg, 95)), 0)]
        out['contour_raster']['leak_r_T'] = [round(float(r[lk].min()), 2), round(float(r[lk].max()), 2)]
        nn = (cls == CLASS_NORI) & lk
        if nn.any():
            out['contour_raster']['leak_nori_col_frac'] = [round(float(ncol[nn].min()) / (ncol.max() + 1), 3),
                                                           round(float(ncol[nn].max()) / (ncol.max() + 1), 3)]
    out['leakage_pass_raster'] = bool(exc_r.max() <= TOL)
    out['leakage_pass_particles'] = bool(exc_p.max() <= TOL)

    # ---- 4. nori band
    sp = met['nori_particle_spacing_T']
    nrows = int(nrow.max()) + 1
    gmax, gmax_s, worst = 0.0, 0.0, None
    L_SHEET = 38.7
    ncols = int(ncol.max()) + 1
    for rr in range(nrows):
        m = nrow == rr
        o = np.argsort(ncol[m])
        p = xs[m][o]
        g = np.linalg.norm(np.diff(p, axis=0), axis=1)
        if g.max() > gmax:
            gmax = float(g.max())
            worst = float(ncol[m][o][int(np.argmax(g))]) / ncols * L_SHEET
    nori_pts = xs[cls == CLASS_NORI]
    ncomp25, sizes25 = components(nori_pts, 2.5 * sp)
    ncomp15, sizes15 = components(nori_pts, 1.5 * sp)
    out['nori'] = dict(spacing_T=sp, max_gap_T=round(gmax, 4), max_gap_in_spacings=round(gmax / sp, 2),
                       worst_gap_at_s_T=round(worst, 1) if worst is not None else None,
                       json_max_gap=met['nori_max_gap_T'],
                       comp_link_2p5sp=ncomp25, comp_sizes_2p5sp=[int(s) for s in sizes25[:5]],
                       comp_link_1p5sp=ncomp15, comp_sizes_1p5sp=[int(s) for s in sizes15[:5]],
                       map_components=met['nori_components_map'])
    out['nori_pass'] = bool(gmax < 2.5 * sp and ncomp25 == 1)
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--layouts', default='1,4,5')
    ap.add_argument('--dir', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out'))
    a = ap.parse_args()
    res = [check(l, a.dir) for l in a.layouts.split(',')]
    print(json.dumps(res, indent=1))
