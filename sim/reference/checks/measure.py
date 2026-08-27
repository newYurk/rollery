"""Constitutive-sanity measurements on a reference particle dump (layout 2 by default).

Usage: python checks/measure.py out/particles_2.npz [--kind tamago] [--label final]
Everything is measured from PARTICLES, not from the 600x600 raster, so that the raster's
disc-splat radius cannot invent or hide a gap.
"""
import sys, os, math, json
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import run as R   # constants + layouts only; nothing is executed (main() is under __main__)


def load(path):
    z = np.load(path)
    return {k: z[k] for k in z.files}


def gap_profile(x, cls, kind, n_ang=None, half_win_deg=4.0):
    """Rice thickness between the filling and the first nori layer outside it, per ray.

    For each ray through the roll centroid inside the filling's angular span:
      r_fill_max = outermost filling particle within +-half_win of the ray
      r_nori     = innermost NORI particle with r > r_fill_max within the same window
      gap        = r_nori - r_fill_max      (T)
    """
    c = R.CLASS_OF_KIND[kind]
    cen = np.array([x[:, 0].mean(), x[:, 1].mean()])
    rel = x - cen
    r = np.hypot(rel[:, 0], rel[:, 1])
    ph = np.degrees(np.arctan2(rel[:, 1], rel[:, 0]))
    mf = cls == c
    mn = cls == R.CLASS_NORI
    # angular span of the filling, unwrapped around its own centroid direction
    fc = rel[mf].mean(axis=0)
    ph0 = math.degrees(math.atan2(fc[1], fc[0]))
    def unwrap(a):
        return (a - ph0 + 180.0) % 360.0 - 180.0
    phf = unwrap(ph[mf]); phn = unwrap(ph[mn])
    lo, hi = np.percentile(phf, 3), np.percentile(phf, 97)
    n_ang = n_ang or 25
    out = []
    for a in np.linspace(lo, hi, n_ang):
        sf = mf.nonzero()[0][np.abs(phf - a) <= half_win_deg]
        sn = mn.nonzero()[0][np.abs(phn - a) <= half_win_deg]
        if len(sf) < 3 or len(sn) == 0:
            continue
        rf = float(np.percentile(r[sf], 99))
        cand = r[sn][r[sn] > rf]
        if not len(cand):
            continue
        out.append((float(a), rf, float(cand.min()), float(cand.min() - rf)))
    return np.array(out), cen


def nori_len(x, nori_row, nori_col, info_rows):
    """Polyline length through nori particle centres, per initial row."""
    ls = []
    for rr in range(info_rows):
        m = nori_row == rr
        if not m.any():
            continue
        o = np.argsort(nori_col[m])
        p = x[m][o]
        ls.append(float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum()))
    return ls


def shape_of(x, cls, kind):
    c = R.CLASS_OF_KIND[kind]
    m = cls == c
    p = x[m] - x[m].mean(axis=0)
    ev = np.linalg.eigvalsh(np.cov(p.T))
    # principal extents (p2-p98 along each eigenvector) -- a real length, unlike sqrt(eigen ratio)
    w, V = np.linalg.eigh(np.cov(p.T))
    proj = p @ V
    ext = np.percentile(proj, 98, axis=0) - np.percentile(proj, 2, axis=0)
    return dict(n=int(m.sum()), aspect_cov=float(math.sqrt(ev[1] / ev[0])),
                ext_major=float(max(ext)), ext_minor=float(min(ext)),
                aspect_ext=float(max(ext) / min(ext)))


def report(path, kind='tamago', label=None):
    d = load(path)
    x, cls, J, vol = d['x'].astype(np.float64), d['cls'], d['J'].astype(np.float64), d['vol'].astype(np.float64)
    nr = int(d['nori_row'].max()) + 1
    label = label or os.path.basename(path)
    out = {'label': label, 'file': path}

    prof, cen = gap_profile(x, cls, kind)
    if len(prof):
        g = prof[:, 3]
        out['gap'] = dict(n_rays=len(g), min=round(float(g.min()), 3), p25=round(float(np.percentile(g, 25)), 3),
                          median=round(float(np.median(g)), 3), mean=round(float(g.mean()), 3),
                          p75=round(float(np.percentile(g, 75)), 3), max=round(float(g.max()), 3))
        out['gap_at_centroid_ray'] = round(float(prof[np.argmin(np.abs(prof[:, 0])), 3]), 3)

    # rice J
    mr = cls == R.CLASS_RICE
    out['rice_J'] = dict(mean=round(float(J[mr].mean()), 4), p01=round(float(np.percentile(J[mr], 1)), 4),
                         p99=round(float(np.percentile(J[mr], 99)), 4),
                         frac_below_0_88=round(float((J[mr] < 0.88).mean()), 4),
                         frac_above_1_0=round(float((J[mr] > 1.0).mean()), 4))
    out['rice_conservation'] = round(float((vol[mr] * J[mr]).sum() / vol[mr].sum()), 4)

    # filling area (J-weighted -- true deformed area) and shape
    mf = cls == R.CLASS_OF_KIND[kind]
    a0 = float(vol[mf].sum())
    a1 = float((vol[mf] * J[mf]).sum())
    out['filling'] = dict(kind=kind, area0_T2=round(a0, 4), area_T2=round(a1, 4),
                          d_area_pct=round(100 * (a1 / a0 - 1), 2), J_mean=round(float(J[mf].mean()), 4))
    out['filling'].update({('shape_' + k): (round(v, 4) if isinstance(v, float) else v)
                           for k, v in shape_of(x, cls, kind).items()})

    # nori length
    ls = nori_len(x, d['nori_row'], d['nori_col'], nr)
    ncn = int(d['nori_col'].max()) + 1
    L0 = R.L_SHEET / ncn * (ncn - 1)     # polyline through centres of the initial band
    out['nori'] = dict(rows=nr, L0_T=round(L0, 3), L_mean_T=round(float(np.mean(ls)), 3),
                       L_min_T=round(float(np.min(ls)), 3), L_max_T=round(float(np.max(ls)), 3),
                       d_pct_mean=round(100 * (float(np.mean(ls)) / L0 - 1), 2),
                       d_pct_max=round(100 * (float(np.max(ls)) / L0 - 1), 2),
                       J_mean=round(float(J[cls == R.CLASS_NORI].mean()), 4))
    return out, prof


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    kind = 'tamago'
    if '--kind' in sys.argv:
        kind = sys.argv[sys.argv.index('--kind') + 1]
    res = []
    for p in args:
        o, prof = report(p, kind)
        res.append(o)
        print(json.dumps(o, indent=1))
        if len(prof):
            print('  ray profile (deg, r_fill, r_nori, gap):')
            for row in prof:
                print('   %7.1f %7.3f %7.3f %7.3f' % tuple(row))
    if len(res) == 2:
        a, b = res
        if 'gap' in a and 'gap' in b:
            print('\nSPRINGBACK  gap median %.3f -> %.3f  (delta %+.3f T)' %
                  (a['gap']['median'], b['gap']['median'], b['gap']['median'] - a['gap']['median']))
            print('            gap mean   %.3f -> %.3f  (delta %+.3f T)' %
                  (a['gap']['mean'], b['gap']['mean'], b['gap']['mean'] - a['gap']['mean']))
