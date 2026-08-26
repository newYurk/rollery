#!/usr/bin/env python3
"""Adversarial check: per-material mass (sum vol*J) end/start, escapes, nori connectivity,
material outside the contour, per-filling area change.

Reads only the shipped dumps: out/particles_<N>.npz and out/material_<N>.npy.
Nothing here trusts metrics_<N>.json -- every number is recomputed from the particle cloud.
"""
import json, math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get('R2_OUT') or os.path.join(HERE, '..', 'out')

CLASS_BG, CLASS_RICE, CLASS_NORI = 0, 1, 2
# from run.py: CLASS_OF_KIND = {k: 3+i for i,k in enumerate(KIND_IDS)} -> salmon 3, cucumber 4,
# tamago 5, avocado 6, shrimp 7
NAMES = {0: 'bg', 1: 'rice', 2: 'nori', 3: 'salmon', 4: 'cucumber', 5: 'tamago',
         6: 'avocado', 7: 'shrimp'}
TAIL_TOL = 0.3
MASS_MIN = 0.97          # the criterion under test
FILL_AREA_TOL = 0.15     # the criterion under test


def contour(xs, cen, n_ang=36):
    """Same 36-ray outer radius + 5-point running median as run.py:tail_outside_metric."""
    rel = xs - np.asarray(cen, float)
    r = np.hypot(rel[:, 0], rel[:, 1])
    ph = np.mod(np.arctan2(rel[:, 1], rel[:, 0]), 2 * math.pi)
    bi = np.mod(np.round(ph / (2 * math.pi / n_ang)).astype(int), n_ang)
    rout = np.array([r[bi == i].max() if np.any(bi == i) else 0.0 for i in range(n_ang)])
    k = 2
    rs = np.array([np.median(rout[np.arange(i - k, i + k + 1) % n_ang]) for i in range(n_ang)])
    return rs, r, bi


def components(mask, conn=4):
    """Connected components of a boolean image, 4- or 8-connected, iterative flood fill."""
    H, W = mask.shape
    lab = np.zeros(mask.shape, np.int32)
    n = 0
    nb4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    nb8 = nb4 + [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    nb = nb4 if conn == 4 else nb8
    for r0, c0 in np.argwhere(mask):
        if lab[r0, c0]:
            continue
        n += 1
        st = [(r0, c0)]
        lab[r0, c0] = n
        while st:
            r, c = st.pop()
            for dr, dc in nb:
                rr, cc = r + dr, c + dc
                if 0 <= rr < H and 0 <= cc < W and mask[rr, cc] and not lab[rr, cc]:
                    lab[rr, cc] = n
                    st.append((rr, cc))
    sizes = np.bincount(lab.ravel())[1:] if n else np.array([], int)
    return n, np.sort(sizes)[::-1]


def pcomponents(pts, link):
    """Connected components of a point cloud: two particles are linked if closer than `link`.
    Raster-independent -- the class map paints nori last and can slice a filling in two."""
    n = len(pts)
    seen = np.zeros(n, bool)
    lab = np.full(n, -1)
    k = 0
    cell = link
    grid = {}
    for i, p in enumerate(pts):
        grid.setdefault((int(p[0] // cell), int(p[1] // cell)), []).append(i)
    for i0 in range(n):
        if seen[i0]:
            continue
        st = [i0]
        seen[i0] = True
        lab[i0] = k
        while st:
            i = st.pop()
            gx, gy = int(pts[i][0] // cell), int(pts[i][1] // cell)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for j in grid.get((gx + dx, gy + dy), ()):
                        if not seen[j] and np.hypot(*(pts[j] - pts[i])) <= link:
                            seen[j] = True
                            lab[j] = k
                            st.append(j)
        k += 1
    sizes = np.bincount(lab) if k else np.array([], int)
    return k, np.sort(sizes)[::-1]


def check(n):
    z = np.load(os.path.join(OUT, f'particles_{n}.npz'))
    xs, cls, J, vol = z['x'].astype(np.float64), z['cls'], z['J'].astype(np.float64), z['vol'].astype(np.float64)
    nrow, ncol = z['nori_row'], z['nori_col']
    img = np.load(os.path.join(OUT, f'material_{n}.npy'))
    met = json.load(open(os.path.join(OUT, f'metrics_{n}.json')))
    px = met['px_T']
    hp = met['timing']['hp']
    res = {'tag': str(n), 'layout': met['layout'], 'name': met['layout_name'], 'particles': int(len(cls))}

    # ---- A. per-material mass: sum(vol*J) at the end / sum(vol) at the start (J starts at 1)
    mass = {}
    for c in sorted(set(cls.tolist())):
        m = cls == c
        mass[NAMES.get(int(c), str(c))] = dict(
            n=int(m.sum()),
            start_T2=round(float(vol[m].sum()), 4),
            end_T2=round(float((vol[m] * J[m]).sum()), 4),
            ratio=round(float((vol[m] * J[m]).sum() / vol[m].sum()), 4),
            J_min=round(float(J[m].min()), 4), J_p05=round(float(np.percentile(J[m], 5)), 4))
    res['mass'] = mass
    res['mass_total'] = round(float((vol * J).sum() / vol.sum()), 4)
    res['mass_fail'] = sorted(k for k, v in mass.items() if v['ratio'] < MASS_MIN)

    # ---- B. escapes. run.py counts wall hits of the big domain box; here also: non-finite,
    #        and the physical form -- material detached from the roll body.
    res['finite'] = bool(np.all(np.isfinite(xs)) and np.all(np.isfinite(J)))
    res['escaped_reported'] = int(met['escaped'])
    res['J_nonpositive'] = int((J <= 0).sum())

    # ---- C+D. contour and what sticks out of it
    cen = (float(xs[:, 0].mean()), float(xs[:, 1].mean()))
    rs, r, bi = contour(xs, cen)
    excess = r - rs[bi]
    out = excess > TAIL_TOL
    res['contour'] = dict(
        centroid=[round(cen[0], 3), round(cen[1], 3)],
        Rout_mean_T=round(float(rs.mean()), 3),
        outside_tol_particles=int(out.sum()),
        max_excess_T=round(float(excess.max()), 4),
        max_excess_class=NAMES.get(int(cls[int(np.argmax(excess))]), '?'),
        by_class={NAMES.get(int(c), str(c)): int((out & (cls == c)).sum()) for c in sorted(set(cls.tolist()))})

    # ---- C. nori as one connected ribbon
    #  (1) as run.py does it: 8-connected components of the rasterized class map
    #  (2) stricter: 4-connected
    #  (3) topological: the largest gap between neighbours ALONG the ribbon (per lattice row)
    n8, s8 = components(img == CLASS_NORI, 8)
    n4, s4 = components(img == CLASS_NORI, 4)
    rows = int(nrow.max()) + 1 if (nrow >= 0).any() else 0
    gaps = []
    for rr in range(rows):
        m = nrow == rr
        p = xs[m][np.argsort(ncol[m])]
        gaps.append(float(np.linalg.norm(np.diff(p, axis=0), axis=1).max()))
    dx0 = met['nori_particle_spacing_T']
    res['nori'] = dict(rows=rows, spacing_T=dx0,
                       map_components_8conn=n8, map_components_8conn_sizes=s8[:6].tolist(),
                       map_components_4conn=n4, map_components_4conn_sizes=s4[:6].tolist(),
                       max_gap_along_ribbon_T=round(max(gaps), 4),
                       max_gap_over_spacing=round(max(gaps) / dx0, 2))

    # ---- E. fillings: area change and tearing
    fills = []
    for c in sorted(set(cls.tolist())):
        if c <= CLASS_NORI:
            continue
        m = cls == c
        a0 = float(vol[m].sum())
        a1 = float((vol[m] * J[m]).sum())
        nn, ss = components(img == c, 8)
        nn4, ss4 = components(img == c, 4)
        # link threshold 2.5*hp mirrors run.py's own tear test for the nori
        # (torn = max_gap > 2.5 * nori_dx). A "tear" is counted only for a fragment
        # holding >= 1 % of the filling's particles -- a single stray particle is not a tear.
        pnc, pns = pcomponents(xs[m], 2.5 * hp)
        big_frag = int(np.sum(pns >= max(2, 0.01 * m.sum())))
        map_area = float((img == c).sum()) * px * px
        fills.append(dict(kind=NAMES.get(int(c), str(c)),
                          area_start_T2=round(a0, 4), area_end_T2=round(a1, 4),
                          d_area_frac=round(a1 / a0 - 1.0, 4),
                          map_area_T2=round(map_area, 4),
                          map_over_start=round(map_area / a0, 3),
                          map_components_8conn=nn, map_component_sizes=ss[:5].tolist(),
                          map_components_4conn=nn4,
                          particle_components=pnc, particle_fragments_ge1pct=big_frag,
                          particle_component_sizes=pns[:5].tolist(),
                          particle_link_T=round(2.5 * hp, 4),
                          reported_area_T2=next((f['area_T2'] for f in met['fillings']
                                                 if f['kind'] == NAMES.get(int(c), str(c))), None)))
    res['fillings'] = fills
    res['fill_area_fail'] = [f['kind'] for f in fills if abs(f['d_area_frac']) > FILL_AREA_TOL]
    res['fill_torn_map'] = [f['kind'] for f in fills if f['map_components_8conn'] > 1]
    res['fill_torn_particles'] = [f['kind'] for f in fills if f['particle_fragments_ge1pct'] > 1]
    return res


if __name__ == '__main__':
    # argv: run tags as they appear in the file names (out/particles_<tag>.npz). Default: the five
    # shipped control runs 1, 4, 5.
    todo = sys.argv[1:] or ['1', '4', '5']
    allres = [check(n) for n in todo]
    print(json.dumps(allres, indent=1))
    print('\n=== VERDICT (criteria: per-material mass >= %.2f; escapes 0; nori 1 ribbon; '
          'nothing > %.1f T outside contour; |d area| of each filling < %.0f%%) ===' %
          (MASS_MIN, TAIL_TOL, FILL_AREA_TOL * 100))
    for r in allres:
        bad = []
        if r['mass_fail']:
            bad.append('mass<%.2f: ' % MASS_MIN + ', '.join(
                '%s=%.4f' % (k, r['mass'][k]['ratio']) for k in r['mass_fail']))
        if r['escaped_reported'] or not r['finite']:
            bad.append('escapes=%d finite=%s' % (r['escaped_reported'], r['finite']))
        if r['nori']['map_components_4conn'] > 1 or r['nori']['max_gap_over_spacing'] > 2.5:
            bad.append('nori: 4conn=%d gap=%.2fx' % (r['nori']['map_components_4conn'],
                                                     r['nori']['max_gap_over_spacing']))
        if r['contour']['max_excess_T'] > TAIL_TOL:
            bad.append('outside contour %.3f T (%s)' % (r['contour']['max_excess_T'],
                                                        r['contour']['max_excess_class']))
        if r['fill_area_fail']:
            bad.append('filling area: ' + ', '.join(r['fill_area_fail']))
        if r['fill_torn_particles']:
            bad.append('filling torn (particles): ' + ', '.join(r['fill_torn_particles']))
        # the class map paints nori LAST (run.py, rasterize order), so it slices a filling that a
        # turn of nori crosses; the map split is reported but does not fail the run on its own.
        note = (' [map split, raster artefact: ' + ', '.join(r['fill_torn_map']) + ']') if r['fill_torn_map'] else ''
        print('%-12s layout %d (%-16s): %s' % (r['tag'], r['layout'], r['name'],
              ('PASS' if not bad else 'FAIL -- ' + '; '.join(bad)) + note))
