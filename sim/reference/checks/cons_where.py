"""Localise the conservation deficit and the leakage: where in the roll do the low-J particles and
the outside-the-contour particles sit? Answers 'is this the press squeezing, or material lost'."""
import json, math, os, sys
import numpy as np

CLASS_BG, CLASS_RICE, CLASS_NORI = 0, 1, 2
MAT = {1: 'rice', 2: 'nori', 3: 'salmon', 4: 'cucumber', 5: 'tamago', 6: 'avocado'}
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out')

for L in (int(a) for a in (sys.argv[1:] or ['1', '4', '5'])):
    npz = np.load(os.path.join(D, f'particles_{L}.npz'))
    met = json.load(open(os.path.join(D, f'metrics_{L}.json')))
    xs = npz['x'].astype(np.float64); cls = npz['cls']; J = npz['J'].astype(np.float64); vol = npz['vol'].astype(np.float64)
    cen = np.array(met['centroid_xy'])
    R = met['R_mat_T']                      # radius of the pressing mat at the end
    rel = xs - cen
    r = np.hypot(rel[:, 0], rel[:, 1])
    rice = cls == CLASS_RICE
    print(f'--- L{L} {met["layout_name"]}  R_mat={R:.3f}  press_shape={met["mat"]["press_shape"]}  '
          f'P_press={met["mat"]["P_press"]}  t_end={met["phases"]["end"]}  D_press at {met["phases"]["D_press"]}')
    # J profile vs radius (rice only)
    edges = np.linspace(0, max(r[rice].max(), R) + 1e-6, 9)
    print('   rice J by radius:  ', end='')
    for i in range(len(edges) - 1):
        m = rice & (r >= edges[i]) & (r < edges[i + 1])
        if m.sum() > 20:
            print(f'[{edges[i]:.1f}-{edges[i+1]:.1f}) {np.median(J[m]):.3f}(n{m.sum()})  ', end='')
    print()
    # deficit split: near the pressing shell vs the interior
    shell = rice & (r > R - 0.8)
    inner = rice & (r <= R - 0.8)
    for nm, m in (('shell(r>R-0.8)', shell), ('interior', inner)):
        if m.sum():
            print(f'   {nm:16s} n={m.sum():6d}  cons={np.sum(vol[m]*J[m])/np.sum(vol[m]):.4f}  '
                  f'deficit={np.sum(vol[m]*(1-J[m])):.3f} T2  ({np.sum(vol[m]*(1-J[m]))/np.sum(vol*(1-J)) * 100:.0f}% of total)')
    # contact with the table: y_min of the roll
    print(f'   J: frac<0.9={np.mean(J<0.9):.3f}  frac>1.0={np.mean(J>1.0):.3f}  '
          f'mean(J)={J.mean():.4f}  vol-weighted={np.sum(vol*J)/np.sum(vol):.4f}')
    # leakage: angular location of the outside-contour particles (raster contour, run.py definition)
    img = np.load(os.path.join(D, f'material_{L}.npy')); px = met['px_T']; center = met['window_center_xy']
    npx = img.shape[0]
    rows, cols = np.nonzero(img != CLASS_BG); c_row, c_col = rows.mean(), cols.mean()
    cw = (center[0] + (c_col - npx/2)*px, center[1] + (npx/2 - c_row)*px)
    angs = np.deg2rad(np.arange(0, 360, 10)); rout = []
    for a in angs:
        n = int(npx/2/0.25); d = np.arange(n)*0.25
        rr = np.round(c_row - d*math.sin(a)).astype(int); cc = np.round(c_col + d*math.cos(a)).astype(int)
        ok = (rr>=0)&(rr<npx)&(cc>=0)&(cc<npx); seq = img[rr[ok], cc[ok]]; dd = d[ok]*px
        nz = np.nonzero(seq != CLASS_BG)[0]; rout.append(dd[nz[-1]] if len(nz) else 0.0)
    rout = np.array(rout)
    rs = np.array([np.median(rout[np.arange(i-2, i+3) % 36]) for i in range(36)])
    rel2 = xs - np.array(cw); r2 = np.hypot(rel2[:,0], rel2[:,1])
    ph = np.mod(np.arctan2(rel2[:,1], rel2[:,0]), 2*math.pi)
    bi = np.mod(np.round(ph/(2*math.pi/36)).astype(int), 36)
    out = r2 - rs[bi] > 0.3
    if out.any():
        deg = np.degrees(ph[out])
        print(f'   outside>0.3: n={out.sum()} at phi {np.percentile(deg,5):.0f}..{np.percentile(deg,95):.0f} deg '
              f'(median {np.median(deg):.0f}), r {r2[out].min():.2f}..{r2[out].max():.2f}, '
              f'classes ' + ', '.join(f'{MAT[int(c)]}:{int(np.sum(out & (cls==c)))}' for c in np.unique(cls[out])))
        # is the contour just low there? compare ray radius at those angles with the max ray radius
        b = np.unique(bi[out])
        print(f'   ... contour at those rays: {np.round(rs[b],2).tolist()}  (raw ray {np.round(rout[b],2).tolist()}), '
              f'global Rout_max={rout.max():.2f}')
    print()
