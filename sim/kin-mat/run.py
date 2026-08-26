#!/usr/bin/env python
"""kin-mat: 2D MLS-MPM reference of rolling a sushi sheet (cross-section, plane strain).

Fork of mpm-shell with reworked winding kinematics (four cook phases A/B/C/D, see README.md).
Materials, solver, rasterization and metrics are unchanged; the mat boundary is now a
time-dependent Archimedean spiral whose front-lower branch rides at the height of the sheet
still lying ahead, so nothing is ever scraped off the bed in front of the roll.

Units: T = 1 rice thickness (~5 mm), rho_rice = 1, E_rice = 1, time unit = T / sqrt(E_rice/rho_rice).

CLI: python run.py --layout 1|2|3|4|5 --speed 1.0 --press 1.0 --tuck 1.0 [--grid 240] [--particles 16000]
"""
import argparse, json, math, os, sys, time
import numpy as np

# ----------------------------------------------------------------------------- layouts
T = 1.0
L_SHEET = 38.7          # sheet length, T
L_FLAP = 5.0            # bare nori at the far edge, T
W_NORI = 0.12           # nori thickness, T
KIND_IDS = ['salmon', 'cucumber', 'tamago', 'avocado', 'shrimp']
CLASS_BG, CLASS_RICE, CLASS_NORI = 0, 1, 2
CLASS_OF_KIND = {k: 3 + i for i, k in enumerate(KIND_IDS)}   # salmon 3, cucumber 4, tamago 5, avocado 6, shrimp 7
COLORS = {0: (28, 28, 32), 1: (246, 240, 224), 2: (26, 62, 44), 3: (250, 118, 88), 4: (86, 178, 62),
          5: (250, 208, 66), 6: (152, 202, 92), 7: (250, 168, 150)}

def fill(kind, u, w, h, round_=False, stack=False):
    return dict(kind=kind, u=u, w=w, h=h, round=round_, stack=stack)

LAYOUTS = {
    1: dict(name='empty', fillings=[], press_shape='circle'),
    2: dict(name='tamago-edge', fillings=[fill('tamago', 1.5, 2.4, 2.0)], press_shape='circle'),
    3: dict(name='salmon-mid', fillings=[fill('salmon', L_SHEET * 0.5 - 1.0, 2.0, 1.6)], press_shape='circle'),
    4: dict(name='four-edge', fillings=[fill('cucumber', 1.5, 1.4, 1.4, True), fill('tamago', 3.2, 2.4, 2.0),
                                        fill('salmon', 5.9, 2.0, 1.6), fill('avocado', 8.2, 2.0, 1.1, True)],
            press_shape='circle'),
    5: dict(name='overflow-square', fillings=[fill('tamago', 1.5, 2.4, 2.0), fill('salmon', 1.7, 2.0, 1.6, stack=True),
                                              fill('cucumber', 2.0, 1.4, 1.4, True, stack=True)],
            press_shape='square'),
}

# ----------------------------------------------------------------------------- materials
# name: (E, nu, tau_y (shear yield; 1e9 = elastic), rho)
MATERIALS = {
    'rice':     (1.0, 0.35, 0.03, 1.0),
    'nori':     (25.0, 0.30, 1e9, 2.0),
    'salmon':   (3.0, 0.40, 0.15, 1.0),
    'cucumber': (15.0, 0.30, 1e9, 1.0),
    'tamago':   (10.0, 0.35, 1e9, 1.0),
    'avocado':  (4.0, 0.40, 0.15, 1.0),
    'shrimp':   (6.0, 0.35, 1e9, 1.0),
}
MAT_OF_CLASS = {1: 'rice', 2: 'nori'}
for k, c in CLASS_OF_KIND.items():
    MAT_OF_CLASS[c] = k
N_CLASS = 8

# ----------------------------------------------------------------------------- domain / kinematics constants
X0, X1 = -2.0, 48.0
Y0, Y1 = -0.4, 12.6
X_SHEET = 0.0            # near edge of the sheet
X_MAT0 = -0.5            # near end of the mat
X_END_EXTRA = 1.0        # roll until the tangent point passes the sheet end by this much
V_PULL_REF = 0.25        # tangent-point speed at --speed 1 (units of sqrt(E/rho))
P_ROLL_REF = 0.08        # mat pressure during rolling at --press 1 (units of E_rice)
P_PRESS_REF = 0.16       # mat pressure during final pressing at --press 1
V_RADIAL = 0.075         # max radial speed of the mat controller
R_MIN, R_MAX = 0.8, 6.0
T_PRESS = 12.0           # duration of the closing+pressing phase D
Y_CLEAR_FOLD = 0.0       # phase A/B: front clip height (0 = the fold may press onto the bed)
S_BLEND = 2.0            # travel (T) over which B -> C hands over
V_LIFT = 0.10            # max rate of change of the spiral pitch
LIFT_PRESS = 0.25        # phase D: the closed ring is held this high off the table while pressing
GRAVITY = 0.01
MU_TABLE = 0.4
MU_MAT = 2.0             # effectively sticky while pressed against the mat
CFL = 0.3
CORNER_R = 0.6           # corner radius of the square press
R_CORE_MIN, R_CORE_MAX = 1.25, 4.5
FOLD_REACH = 5.0         # first filling must start within this of the near edge to join the fold zone
FOLD_GAP = 2.5           # max gap between neighbouring fillings inside the fold zone
FOLD_EMPTY = 5.0         # fold length for a sheet with no fillings near the edge, T

# ----------------------------------------------------------------------------- particle sampling
def sample_layout(layout, n_target):
    fl = layout['fillings']
    area_rice = (L_SHEET - L_FLAP) * T
    area_nori = L_SHEET * W_NORI
    rects = []
    y_top = {}   # per filling index: top y (for stacking)
    for i, f in enumerate(fl):
        if f['stack'] and i > 0:
            base_y = y_top[i - 1]
        else:
            base_y = W_NORI + T
        rects.append((f['u'], base_y, f['w'], f['h'], f['round'], CLASS_OF_KIND[f['kind']]))
        y_top[i] = base_y + f['h']
    area_fill = sum((math.pi / 4 if r[4] else 1.0) * r[2] * r[3] for r in rects)
    hp = math.sqrt((area_rice + area_nori + area_fill) / n_target)
    xs, cls, vol, nori_row, nori_col = [], [], [], [], []
    rng = np.random.default_rng(1)
    jit = 0.15 * hp

    # rice: rows across thickness, columns along the sheet
    n_rows = max(2, int(round(T / hp)))
    dy = T / n_rows
    n_cols = int(round((L_SHEET - L_FLAP) / hp))
    dxp = (L_SHEET - L_FLAP) / n_cols
    for r in range(n_rows):
        for c in range(n_cols):
            xs.append((X_SHEET + (c + 0.5) * dxp + rng.uniform(-jit, jit), W_NORI + (r + 0.5) * dy + rng.uniform(-jit, jit)))
            cls.append(CLASS_RICE); vol.append(dxp * dy); nori_row.append(-1); nori_col.append(-1)
    # nori: at least 2 rows, no jitter (clean band)
    nr = max(2, int(round(W_NORI / hp)))
    dyn = W_NORI / nr
    ncn = int(round(L_SHEET / hp))
    dxn = L_SHEET / ncn
    for r in range(nr):
        for c in range(ncn):
            xs.append((X_SHEET + (c + 0.5) * dxn, (r + 0.5) * dyn))
            cls.append(CLASS_NORI); vol.append(dxn * dyn); nori_row.append(r); nori_col.append(c)
    # fillings
    for (u, by, w, h, rnd, cl) in rects:
        ncx = max(2, int(round(w / hp))); ncy = max(2, int(round(h / hp)))
        ddx = w / ncx; ddy = h / ncy
        for i in range(ncx):
            for j in range(ncy):
                px = u + (i + 0.5) * ddx; py = by + (j + 0.5) * ddy
                if rnd:
                    ex = (px - (u + w / 2)) / (w / 2); ey = (py - (by + h / 2)) / (h / 2)
                    if ex * ex + ey * ey > 1.0:
                        continue
                xs.append((px + rng.uniform(-jit, jit) * 0.5, py + rng.uniform(-jit, jit) * 0.5))
                cls.append(cl); vol.append(ddx * ddy); nori_row.append(-1); nori_col.append(-1)
    info = dict(hp=hp, nori_rows=nr, nori_cols=ncn, nori_dx=dxn, area_rice=area_rice, area_nori=area_nori,
                area_fill=area_fill, rects=rects)
    return (np.array(xs, np.float32), np.array(cls, np.int32), np.array(vol, np.float32),
            np.array(nori_row, np.int32), np.array(nori_col, np.int32), info)

# ----------------------------------------------------------------------------- fold zone (phase A/B geometry)
def fold_zone(info):
    """Fillings lying close to the near edge form the core; returns (s_fold_base, selected rects)."""
    sel = []
    reach = FOLD_REACH
    for r in sorted(info['rects'], key=lambda r: r[0]):
        if r[0] <= reach:
            sel.append(r)
            reach = r[0] + r[2] + FOLD_GAP
    if not sel:
        return FOLD_EMPTY, []
    end = max(r[0] + r[2] for r in sel) + 1.0
    return min(end, 0.45 * L_SHEET), sel

# ----------------------------------------------------------------------------- simulation
def build(nx, ny, n_part):
    import gstaichi as ti
    ti.init(arch=ti.cpu, default_fp=ti.f32, random_seed=1)
    S = dict()
    S['x'] = ti.Vector.field(2, float, n_part)
    S['v'] = ti.Vector.field(2, float, n_part)
    S['C'] = ti.Matrix.field(2, 2, float, n_part)
    S['F'] = ti.Matrix.field(2, 2, float, n_part)
    S['cls'] = ti.field(ti.i32, n_part)
    S['vol'] = ti.field(float, n_part)
    S['mass'] = ti.field(float, n_part)
    S['J'] = ti.field(float, n_part)
    S['mu'] = ti.field(float, N_CLASS)
    S['la'] = ti.field(float, N_CLASS)
    S['tauy'] = ti.field(float, N_CLASS)
    S['gv'] = ti.Vector.field(2, float, (nx, ny))
    S['gm'] = ti.field(float, (nx, ny))
    S['fn'] = ti.field(float, ())       # normal force on the mat (this substep)
    S['esc'] = ti.field(ti.i32, ())     # escaped-particle counter
    x, v, C, F, cls, vol, mass, J = (S[k] for k in ['x', 'v', 'C', 'F', 'cls', 'vol', 'mass', 'J'])
    mu, la, tauy, gv, gm, fn, esc = (S[k] for k in ['mu', 'la', 'tauy', 'gv', 'gm', 'fn', 'esc'])
    dx = (Y1 - Y0) / ny
    inv_dx = 1.0 / dx

    @ti.kernel
    def init_particles(xs: ti.types.ndarray(), cl: ti.types.ndarray(), vo: ti.types.ndarray(), rho: ti.types.ndarray()):
        for p in x:
            x[p] = [xs[p, 0], xs[p, 1]]
            v[p] = [0.0, 0.0]
            C[p] = ti.Matrix.zero(float, 2, 2)
            F[p] = ti.Matrix.identity(float, 2)
            cls[p] = cl[p]
            vol[p] = vo[p]
            mass[p] = vo[p] * rho[cl[p]]
            J[p] = 1.0

    @ti.kernel
    def substep(dt: float, xc: float, yc: float, R: float, Rdot: float, ycdot: float, vc: float, phi: float,
                shape: ti.i32, mu_mat: float, y_clear: float, unroll: float, pitch: float, vt_pull: float):
        for I in ti.grouped(gm):
            gv[I] = [0.0, 0.0]
            gm[I] = 0.0
        fn[None] = 0.0
        # ---- P2G
        for p in x:
            Xp = ti.Vector([(x[p][0] - X0) * inv_dx, (x[p][1] - Y0) * inv_dx])
            base = int(Xp - 0.5)
            fx = Xp - base.cast(float)
            w = [0.5 * (1.5 - fx) ** 2, 0.75 - (fx - 1.0) ** 2, 0.5 * (fx - 0.5) ** 2]
            Fp = (ti.Matrix.identity(float, 2) + dt * C[p]) @ F[p]
            U, sig, V = ti.svd(Fp)
            s0 = ti.max(sig[0, 0], 0.05); s1 = ti.max(sig[1, 1], 0.05)
            e0 = ti.log(s0); e1 = ti.log(s1)
            m = cls[p]
            mu_ = mu[m]; la_ = la[m]; ty = tauy[m]
            # von Mises-type return mapping on Hencky strain (volume preserving)
            em = 0.5 * (e0 + e1)
            d = 0.5 * (e0 - e1)
            if mu_ * ti.abs(d) * 2.0 > ty:
                dn = ty / (2.0 * mu_)
                d = dn if d > 0 else -dn
                e0 = em + d; e1 = em - d
                Fp = U @ ti.Matrix([[ti.exp(e0), 0.0], [0.0, ti.exp(e1)]]) @ V.transpose()
            F[p] = Fp
            J[p] = ti.exp(e0 + e1)
            tr = e0 + e1
            tau = U @ ti.Matrix([[2.0 * mu_ * e0 + la_ * tr, 0.0], [0.0, 2.0 * mu_ * e1 + la_ * tr]]) @ U.transpose()
            affine = -dt * 4.0 * inv_dx * inv_dx * vol[p] * tau + mass[p] * C[p]
            mp = mass[p]
            for i, j in ti.static(ti.ndrange(3, 3)):
                off = ti.Vector([i, j])
                dpos = (off.cast(float) - fx) * dx
                wt = w[i][0] * w[j][1]
                gv[base + off] += wt * (mp * v[p] + affine @ dpos)
                gm[base + off] += wt * mp
        # ---- grid update + boundaries
        for I in ti.grouped(gm):
            if gm[I] > 0:
                vv = gv[I] / gm[I]
                vv[1] -= dt * GRAVITY
                px = X0 + I[0] * dx
                py = Y0 + I[1] * dx
                # --- mat (clipped arc of a rolling circle, or square press)
                ddx = px - xc
                ddy = py - yc
                if shape == 0:
                    r = ti.sqrt(ddx * ddx + ddy * ddy)
                    th = ti.atan2(-ddx, -ddy)
                    if th < 0:
                        th += 2.0 * math.pi
                    # the mat is an Archimedean spiral: one turn back from the contact the roll is
                    # one sheet thickness thinner, so the spiral rides over the bed still lying ahead
                    rb = R - pitch * th / (2.0 * math.pi)
                    dsd = r - rb
                    if dsd > -0.5 * dx and dsd < 3.0 * dx:
                        # front clip: never touch the sheet still lying flat in front of the roll
                        ahead_low = (px > xc + 0.15) and (py < y_clear)
                        if th <= phi and not ahead_low:
                            sn = ti.sin(th); cs = ti.cos(th)
                            n = ti.Vector([sn, cs])            # inward normal
                            vb = ti.Vector([vc, ycdot]) + Rdot * ti.Vector([-sn, -cs]) \
                                 + (vt_pull * rb / R - unroll * th * Rdot) * ti.Vector([-cs, sn])
                            vrel = vv - vb
                            vn = vrel.dot(n)
                            if vn < 0:
                                vt = vrel - vn * n
                                vtn = vt.norm()
                                if vtn > 1e-12:
                                    vt *= ti.max(0.0, 1.0 - mu_mat * (-vn) / vtn)
                                vv = vb + vt
                                fn[None] += gm[I] * (-vn) / dt
                else:
                    # rounded square of half-side R, corner radius CORNER_R, tangent to the table, shrinking at Rdot
                    hs = R - CORNER_R
                    qx = ti.abs(ddx) - hs; qy = ti.abs(ddy) - hs
                    mx = ti.max(qx, 0.0); my = ti.max(qy, 0.0)
                    dsd = ti.sqrt(mx * mx + my * my) + ti.min(ti.max(qx, qy), 0.0) - CORNER_R
                    if dsd > -0.5 * dx and dsd < 3.0 * dx:
                        nout = ti.Vector([0.0, 1.0])
                        if qx > 0 and qy > 0:
                            nout = ti.Vector([mx, my]).normalized()
                        elif qx > qy:
                            nout = ti.Vector([1.0, 0.0])
                        nout[0] *= 1.0 if ddx >= 0 else -1.0
                        nout[1] *= 1.0 if ddy >= 0 else -1.0
                        n = -nout
                        vb = ti.Vector([0.0, ycdot]) + Rdot * nout
                        vrel = vv - vb
                        vn = vrel.dot(n)
                        if vn < 0:
                            vt = vrel - vn * n
                            vtn = vt.norm()
                            if vtn > 1e-12:
                                vt *= ti.max(0.0, 1.0 - mu_mat * (-vn) / vtn)
                            vv = vb + vt
                            fn[None] += gm[I] * (-vn) / dt
                # --- table (y <= 0), separable with Coulomb friction
                if py <= 1e-6:
                    if vv[1] < 0:
                        vtn = ti.abs(vv[0])
                        if vtn > 1e-12:
                            vv[0] *= ti.max(0.0, 1.0 - MU_TABLE * (-vv[1]) / vtn)
                        vv[1] = 0.0
                # --- domain walls
                if I[0] < 3 and vv[0] < 0:
                    vv[0] = 0.0
                if I[0] > gm.shape[0] - 4 and vv[0] > 0:
                    vv[0] = 0.0
                if I[1] > gm.shape[1] - 4 and vv[1] > 0:
                    vv[1] = 0.0
                gv[I] = vv
        # ---- G2P
        for p in x:
            Xp = ti.Vector([(x[p][0] - X0) * inv_dx, (x[p][1] - Y0) * inv_dx])
            base = int(Xp - 0.5)
            fx = Xp - base.cast(float)
            w = [0.5 * (1.5 - fx) ** 2, 0.75 - (fx - 1.0) ** 2, 0.5 * (fx - 0.5) ** 2]
            nv = ti.Vector.zero(float, 2)
            nC = ti.Matrix.zero(float, 2, 2)
            for i, j in ti.static(ti.ndrange(3, 3)):
                off = ti.Vector([i, j])
                dpos = off.cast(float) - fx
                g = gv[base + off]
                wt = w[i][0] * w[j][1]
                nv += wt * g
                nC += 4.0 * inv_dx * wt * g.outer_product(dpos)
            v[p] = nv
            C[p] = nC
            xn = x[p] + dt * nv
            # keep inside the grid (count escapes)
            lo0 = X0 + 2.0 * dx; hi0 = X1 - 3.0 * dx
            lo1 = Y0 + 2.0 * dx; hi1 = Y1 - 3.0 * dx
            if xn[0] < lo0 or xn[0] > hi0 or xn[1] < lo1 or xn[1] > hi1:
                esc[None] += 1
                xn[0] = ti.min(ti.max(xn[0], lo0), hi0)
                xn[1] = ti.min(ti.max(xn[1], lo1), hi1)
            x[p] = xn

    S['init_particles'] = init_particles
    S['substep'] = substep
    S['dx'] = dx
    S['ti'] = ti
    return S

# ----------------------------------------------------------------------------- rasterization + metrics
def rasterize(xs, cls, hp, nori_dy, center, size_T=12.0, npx=600):
    px = size_T / npx
    img = np.zeros((npx, npx), np.uint8)
    col = (xs[:, 0] - center[0]) / px + npx / 2
    row = npx / 2 - (xs[:, 1] - center[1]) / px
    order = [CLASS_RICE] + [c for c in range(3, N_CLASS)] + [CLASS_NORI]
    for c in order:
        m = cls == c
        if not m.any():
            continue
        rad = 0.6 * (max(hp, nori_dy) if c == CLASS_NORI else hp) / px
        rpx = int(math.ceil(rad))
        ci = np.round(col[m]).astype(int); ri = np.round(row[m]).astype(int)
        for di in range(-rpx, rpx + 1):
            for dj in range(-rpx, rpx + 1):
                if di * di + dj * dj > rad * rad + 0.25:
                    continue
                rr = ri + di; cc = ci + dj
                ok = (rr >= 0) & (rr < npx) & (cc >= 0) & (cc < npx)
                img[rr[ok], cc[ok]] = c
    return img, px


def raster_class_area(xs, cls, hp, nori_dy, px, which=CLASS_RICE):
    """Same disc rasterization as `rasterize`, but over a bounding box of the whole scene.
    Used once on the initial state to calibrate the rasterization bias of rice_area_ratio."""
    x0 = float(xs[:, 0].min()) - 0.3; y0 = float(xs[:, 1].min()) - 0.3
    W = int((float(xs[:, 0].max()) + 0.3 - x0) / px) + 2
    H = int((float(xs[:, 1].max()) + 0.3 - y0) / px) + 2
    img = np.zeros((H, W), np.uint8)
    order = [CLASS_RICE] + [c for c in range(3, N_CLASS)] + [CLASS_NORI]
    for c in order:
        m = cls == c
        if not m.any():
            continue
        rad = 0.6 * (max(hp, nori_dy) if c == CLASS_NORI else hp) / px
        rpx = int(math.ceil(rad))
        ci = np.round((xs[m, 0] - x0) / px).astype(int)
        ri = np.round((xs[m, 1] - y0) / px).astype(int)
        for di in range(-rpx, rpx + 1):
            for dj in range(-rpx, rpx + 1):
                if di * di + dj * dj > rad * rad + 0.25:
                    continue
                rr = ri + di; cc = ci + dj
                ok = (rr >= 0) & (rr < H) & (cc >= 0) & (cc < W)
                img[rr[ok], cc[ok]] = c
    return float(np.sum(img == which)) * px * px



def ray_classes(img, c_row, c_col, ang, px, step=0.25):
    """Classes sampled along a ray from the centroid; returns (dist_T array, class array)."""
    npx = img.shape[0]
    n = int(npx / 2 / step)
    d = np.arange(n) * step
    rr = np.round(c_row - d * math.sin(ang)).astype(int)
    cc = np.round(c_col + d * math.cos(ang)).astype(int)
    ok = (rr >= 0) & (rr < npx) & (cc >= 0) & (cc < npx)
    rr = rr[ok]; cc = cc[ok]; d = d[ok]
    return d * px, img[rr, cc]

def runs(seq, c):
    """number of contiguous runs of class c in seq"""
    m = seq == c
    if not m.any():
        return 0
    return int(np.sum(m[1:] & ~m[:-1]) + (1 if m[0] else 0))

def nori_components(img):
    m = img == CLASS_NORI
    lab = np.zeros(img.shape, np.int32)
    n = 0
    H, W = img.shape
    pts = np.argwhere(m)
    for (r0, c0) in pts:
        if lab[r0, c0]:
            continue
        n += 1
        stack = [(r0, c0)]; lab[r0, c0] = n
        while stack:
            r, c = stack.pop()
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    rr = r + dr; cc = c + dc
                    if 0 <= rr < H and 0 <= cc < W and m[rr, cc] and not lab[rr, cc]:
                        lab[rr, cc] = n; stack.append((rr, cc))
    sizes = np.bincount(lab.ravel())[1:] if n else np.array([])
    return n, sizes


def tail_metrics(xs, cen, thr=0.3, nb=72, half_win=6):
    """Fitted roll contour = per-sector 98th percentile radius, median-smoothed over +-half_win
    sectors (so a narrow protruding tail cannot define the contour it is measured against).
    Returns (tail_outside, max excess T, #particles beyond thr, contour array, angles)."""
    rel = xs - np.asarray(cen, np.float64)
    r = np.hypot(rel[:, 0], rel[:, 1])
    ang = np.arctan2(rel[:, 1], rel[:, 0])
    b = np.clip(((ang + math.pi) / (2 * math.pi) * nb).astype(int), 0, nb - 1)
    rout = np.zeros(nb)
    for i in range(nb):
        m = b == i
        rout[i] = np.percentile(r[m], 98.0) if int(m.sum()) >= 5 else np.nan
    good = np.isfinite(rout)
    if good.sum() < nb // 2:
        return False, 0.0, 0, rout, None
    rout[~good] = np.interp(np.nonzero(~good)[0], np.nonzero(good)[0], rout[good])
    cont = np.array([np.median(np.take(rout, range(i - half_win, i + half_win + 1), mode='wrap'))
                     for i in range(nb)])
    excess = r - cont[b]
    n_out = int(np.sum(excess > thr))
    return bool(n_out > 0), float(excess.max()), n_out, cont, rout


def compute_metrics(xs, vs, cls, Jp, nori_row, nori_col, info, layout, img, px, center, esc, extra):
    npx = img.shape[0]
    fg = img != CLASS_BG
    rows, cols = np.nonzero(fg)
    c_row, c_col = rows.mean(), cols.mean()
    cen_world = (center[0] + (c_col - npx / 2) * px, center[1] + (npx / 2 - c_row) * px)
    angs = np.deg2rad(np.arange(0, 360, 10))
    rout, turns, r_nori_out = [], [], []
    for a in angs:
        d, seq = ray_classes(img, c_row, c_col, a, px)
        nz = np.nonzero(seq != CLASS_BG)[0]
        rout.append(d[nz[-1]] if len(nz) else 0.0)
        turns.append(runs(seq, CLASS_NORI))
        nn = np.nonzero(seq == CLASS_NORI)[0]
        r_nori_out.append(d[nn[-1]] if len(nn) else 0.0)
    rout = np.array(rout)
    # fillings
    fills = []
    for i, f in enumerate(layout['fillings']):
        c = CLASS_OF_KIND[f['kind']]
        m = cls == c
        if not m.any():
            continue
        cx, cy = xs[m, 0].mean(), xs[m, 1].mean()
        rel = (cx - cen_world[0], cy - cen_world[1])
        r = math.hypot(*rel); phi = math.degrees(math.atan2(rel[1], rel[0]))
        ang = math.atan2(rel[1], rel[0])
        d, seq = ray_classes(img, c_row, c_col, ang, px, step=0.2)
        # walk from the filling centroid outward: skip own class, count rice until nori
        start = min(int(np.searchsorted(d, r)), len(seq) - 1)
        k = start
        while k < len(seq) and seq[k] == c:
            k += 1
        under = 0.0; hit = 'none'; k2 = k
        while k2 < len(seq):
            if seq[k2] == CLASS_NORI:
                hit = 'nori'; break
            if seq[k2] == CLASS_RICE:
                under += 0.2 * px
            elif seq[k2] == CLASS_BG:
                hit = 'bg'; break
            elif seq[k2] != c:
                hit = MAT_OF_CLASS.get(int(seq[k2]), 'other'); break
            k2 += 1
        # inward: rice between filling and the previous turn's nori (or the center)
        k3 = start
        while k3 >= 0 and seq[k3] == c:
            k3 -= 1
        inner = 0.0; hit_in = 'center'
        while k3 >= 0:
            if seq[k3] == CLASS_NORI:
                hit_in = 'nori'; break
            if seq[k3] == CLASS_RICE:
                inner += 0.2 * px
            elif seq[k3] != c and seq[k3] != CLASS_BG:
                hit_in = MAT_OF_CLASS.get(int(seq[k3]), 'other'); break
            k3 -= 1
        pts = xs[m] - np.array([cx, cy])
        cov = np.cov(pts.T); ev = np.linalg.eigvalsh(cov)
        fills.append(dict(kind=f['kind'], r_T=round(r, 3), phi_deg=round(phi, 1), centroid_xy=[round(cx, 3), round(cy, 3)],
                          rice_under_filling_T=round(under, 3), outer_hit=hit, rice_inside_T=round(inner, 3), inner_hit=hit_in,
                          aspect=round(math.sqrt(ev[1] / max(ev[0], 1e-9)), 3), area_T2=round(float(vol_of(cls, c, info)), 3)))
    t_out, t_exc, t_n, cont, _ = tail_metrics(xs.astype(np.float64), cen_world, thr=0.3)
    if cont is None:
        cont = np.zeros(72)
    # rice conservation
    rice_m = cls == CLASS_RICE
    _dummy = 0
    rice_area_map = float(np.sum(img == CLASS_RICE)) * px * px
    img_r, _ = rasterize(xs[rice_m], cls[rice_m], info['hp'], 1e-9, center, extra['window_T'], img.shape[0])
    rice_area_alone = float(np.sum(img_r == CLASS_RICE)) * px * px
    r_rel = xs[rice_m] - np.array(cen_world, np.float32)
    r_r = np.hypot(r_rel[:, 0], r_rel[:, 1])
    r_b = np.clip(((np.arctan2(r_rel[:, 1], r_rel[:, 0]) + math.pi) / (2 * math.pi) * 72).astype(int), 0, 71)
    Jmean = float(np.mean(Jp[rice_m]))
    # nori connectivity from particles: max gap between consecutive particles of the same initial row
    max_gap = 0.0
    for r in range(info['nori_rows']):
        m = nori_row == r
        order = np.argsort(nori_col[m])
        p = xs[m][order]
        gaps = np.linalg.norm(np.diff(p, axis=0), axis=1)
        max_gap = max(max_gap, float(gaps.max()))
    ncomp, sizes = nori_components(img)
    big = int(np.sum(sizes >= 20)) if len(sizes) else 0
    vmax = float(np.max(np.linalg.norm(vs, axis=1)))
    finite = bool(np.all(np.isfinite(xs)) and np.all(np.isfinite(vs)))
    torn = max_gap > 2.5 * info['nori_dx']
    stable = finite and esc == 0 and vmax < 5.0 and not torn
    core = [dict(kind=f['kind'], r_T=f['r_T'], phi_deg=f['phi_deg']) for f in fills]
    order_by_x = [f['kind'] for f in sorted(fills, key=lambda f: f['centroid_xy'][0])]
    # tail: anything sticking out of the fitted roll contour after phase D
    met = dict(
        layout=int(extra['layout']), layout_name=layout['name'], speed=extra['speed'], press=extra['press'],
        tuck=extra['tuck'],
        Rout_T=round(float(rout.max()), 3), Rout_mean_T=round(float(rout.mean()), 3), Rout_min_T=round(float(rout.min()), 3),
        R_mat_T=round(extra['R'], 3), R_nori_outer_mean_T=round(float(np.mean(r_nori_out)), 3),
        nori_turns=round(float(np.mean(turns)), 3), nori_turns_min=int(np.min(turns)), nori_turns_max=int(np.max(turns)),
        tail_outside=bool(t_out), tail_excess_max_T=round(t_exc, 3), tail_particles=int(t_n),
        tail_particles_frac=round(t_n / max(len(cls), 1), 5),
        contour_mean_T=round(float(np.mean(cont)), 3), contour_max_T=round(float(np.max(cont)), 3),
        rice_under_filling_T={f['kind']: f['rice_under_filling_T'] for f in fills},
        core=core, fillings=fills, core_order_left_to_right=order_by_x,
        rice_area_initial_T2=round(info['area_rice'], 3), rice_area_map_T2=round(rice_area_map, 3),
        rice_area_ratio=round(rice_area_map / info['area_rice'], 3), rice_J_mean=round(Jmean, 4),
        rice_area_map_initial_T2=round(extra['rice_map0'], 3),
        rice_area_map_alone_T2=round(rice_area_alone, 3),
        rice_area_J_T2=round(float(np.sum(extra['vol'][rice_m] * Jp[rice_m])), 3),
        rice_area_ratio_J=round(float(np.sum(extra['vol'][rice_m] * Jp[rice_m])) / info['area_rice'], 3),
        rice_outside_contour_frac=round(float(np.mean(r_r > cont[r_b] + 0.3)), 5),
        rice_area_ratio_alone=round(rice_area_alone / info['area_rice'], 3),
        rice_area_ratio_ref=round(rice_area_map / max(extra['rice_map0'], 1e-9), 3),
        rice_particles=int(rice_m.sum()), particles=int(len(cls)), escaped=int(esc),
        nori_max_gap_T=round(max_gap, 4), nori_particle_spacing_T=round(info['nori_dx'], 4), nori_torn=bool(torn),
        nori_components_map=int(ncomp), nori_components_map_ge20px=big,
        v_max_final=round(vmax, 4), finite=finite, stable=bool(stable),
        window_T=extra['window_T'], px_T=round(px, 5), window_center_xy=[round(center[0], 3), round(center[1], 3)],
        centroid_xy=[round(cen_world[0], 3), round(cen_world[1], 3)],
        mat=extra['mat'], timing=extra['timing'], phases=extra['phases'],
    )
    return met

def vol_of(cls, c, info):
    return 0.0  # placeholder, replaced below via closure in main (area from particle volumes)

# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layout', type=int, default=1)
    ap.add_argument('--speed', type=float, default=1.0)
    ap.add_argument('--press', type=float, default=1.0)
    ap.add_argument('--tuck', type=float, default=1.0, help='how far the near edge is tucked, 0.6..1.3')
    ap.add_argument('--grid', type=int, default=240, help='total grid nodes ~ grid^2 (aspect follows the domain)')
    ap.add_argument('--particles', type=int, default=16000)
    ap.add_argument('--out', type=str, default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out'))
    ap.add_argument('--frames', type=int, default=10, help='number of debug snapshots (0 = none)')
    ap.add_argument('--window', type=float, default=12.0, help='material map window side, T')
    ap.add_argument('--tag', type=str, default='')
    args = ap.parse_args()
    layout = LAYOUTS[args.layout]
    os.makedirs(args.out, exist_ok=True)
    tag = f'{args.layout}{args.tag}'

    aspect = (X1 - X0) / (Y1 - Y0)
    ny = int(round(args.grid / math.sqrt(aspect)))
    nx = int(round(ny * aspect))
    xs, cls, vol, nori_row, nori_col, info = sample_layout(layout, args.particles)
    n = len(cls)
    S = build(nx, ny, n)
    dx = S['dx']
    rho = np.zeros(N_CLASS, np.float32); mu = np.zeros(N_CLASS, np.float32); la = np.zeros(N_CLASS, np.float32); ty = np.zeros(N_CLASS, np.float32)
    cmax = 0.0
    present = set(int(c) for c in np.unique(cls))
    for c, name in MAT_OF_CLASS.items():
        E, nu, tau_y, r = MATERIALS[name]
        mu[c] = E / (2 * (1 + nu)); la[c] = E * nu / ((1 + nu) * (1 - 2 * nu)); ty[c] = tau_y; rho[c] = r
        if c in present:
            cmax = max(cmax, math.sqrt((la[c] + 2 * mu[c]) / r))
    S['mu'].from_numpy(mu); S['la'].from_numpy(la); S['tauy'].from_numpy(ty)
    S['init_particles'](xs.astype(np.float32), cls.astype(np.int32), vol.astype(np.float32), rho)
    dt = CFL * dx / cmax

    # ---- fold geometry (phases A/B): where the near edge lands, how tight the core is
    s_fold_base, fold_rects = fold_zone(info)
    s_fold = args.tuck * s_fold_base
    top_max = max([r[1] + r[3] for r in fold_rects], default=W_NORI + T)
    a_fold = sum((math.pi / 4 if r[4] else 1.0) * r[2] * r[3] for r in fold_rects)
    # closed fold: pi R^2 = 2 pi R (T + W_NORI) + A_fill  ->  R = c + sqrt(c^2 + A_fill/pi), c = T + W_NORI
    c_bed = T + W_NORI
    R_fit = c_bed + math.sqrt(c_bed * c_bed + a_fold / math.pi)
    # a closed fold cannot be tighter than the area of the bed it swallows (R_fit), nor shorter
    # than the stack it has to clear; --tuck scales both, and the geometric landing point s_fold
    R_hold = max(R_fit, 0.5 * (top_max + 0.3))
    R_core = max((s_fold - X_MAT0) / (2 * math.pi), args.tuck * R_hold)
    R_core = min(max(R_core, R_CORE_MIN), R_CORE_MAX)

    v_c = V_PULL_REF * args.speed
    x_end = X_SHEET + L_SHEET + X_END_EXTRA
    # estimate only (used for frame spacing and progress): fold + roll + press
    t_fold_est = 2 * math.pi * R_core * 1.4 / v_c
    t_roll = t_fold_est + max(0.0, x_end - s_fold) / v_c
    t_total = t_roll + T_PRESS
    n_steps = int(math.ceil(t_total / dt))
    y_clear0 = Y_CLEAR_FOLD
    px_ref = args.window / 600.0
    rice_map0 = raster_class_area(xs, cls, info['hp'], W_NORI / info['nori_rows'], px_ref, CLASS_RICE)
    print(f'grid {nx}x{ny} dx={dx:.4f} particles={n} hp={info["hp"]:.4f} nori rows={info["nori_rows"]} '
          f'dt={dt:.5f} cmax={cmax:.2f} v_c={v_c} t_roll={t_roll:.1f} steps={n_steps}\n'
          f'fold: s_fold_base={s_fold_base:.2f} s_fold={s_fold:.2f} R_hold={R_hold:.2f} R_core={R_core:.3f} '
          f'y_clear_C>={y_clear0:.2f} rice_map0={rice_map0:.2f}', flush=True)

    # controller state
    R = R_core; Rdot = 0.0; F_f = 0.0
    tau_f = 0.5
    shape = 0 if layout['press_shape'] == 'circle' else 1
    frames_dir = os.path.join(args.out, f'frames_{tag}')
    if args.frames:
        os.makedirs(frames_dir, exist_ok=True)
    snap_every = max(1, n_steps // max(args.frames, 1))
    t0 = time.time()
    log = []
    phases = {}
    t = 0.0
    ctrl_every = 8
    phase = 'A'
    xc = X_MAT0          # abscissa where the mat leaves the table
    h_lift = 0.0         # spiral pitch of the mat (0 = circle)
    lift = 0.0           # phase D: height of the closed ring above the table
    s_mat = 0.0          # mat arclength already wrapped on the roll
    xc_C = None          # xc when phase C started
    t_D0 = None          # time when phase D started
    step = -1
    n_cap = int(2.5 * n_steps)
    while True:
        step += 1
        if step > n_cap:
            print('  ! step cap reached', flush=True)
            break
        y_c_full = Y_CLEAR_FOLD
        phi = min(2.0 * math.pi, s_mat / R)
        h_tgt = 0.0
        lift_tgt = 0.0
        if phase in ('A', 'B'):
            # Fold: the cook pulls the mat's near end along the mat (ds/dt = v_c) while the
            # contact line only creeps forward, so the near edge lands at x ~ s_fold, not
            # 2*pi*R further on. lam = (s_fold - x_mat0) / (2 pi R) <= 1.
            lam = min(1.0, max(0.15, (s_fold - X_MAT0) / (2.0 * math.pi * R)))
            vc_now = lam * v_c      # the bend point only creeps forward ...
            vt_now = v_c            # ... while the mat itself is pulled at v_c along its length
            unroll = 1.0
            y_cl = 0.0
            P_ref = P_ROLL_REF * args.press
            shp = 0
            phase = 'A' if phi < math.pi else 'B'
            if phi >= 2.0 * math.pi - 1e-9:
                phase = 'C'; xc_C = xc
        if phase == 'C':
            # C: the mat hugs the roll as a full-turn spiral and the roll rolls on the
            # table without slipping; the sheet ahead feeds in under the spiral's front-lower branch
            vc_now = v_c
            unroll = 0.0
            phi = 2.0 * math.pi
            # spiral pitch = thickness of the sheet still lying ahead, so the mat's front-lower
            # branch rides at the height of the bed instead of cutting through it
            h_ahead = (T + W_NORI) if xc < X_SHEET + (L_SHEET - L_FLAP) + 0.6 else W_NORI
            h_tgt = h_ahead
            y_cl = 0.0
            P_ref = P_ROLL_REF * args.press
            shp = 0
            if xc >= x_end:
                phase = 'D'; t_D0 = t
                # gather: open the ring just enough to contain every particle, then press it down
                xp = S['x'].to_numpy()
                m = xp[:, 1] > 0.35
                need = np.percentile(((xp[m, 0] - xc) ** 2 + xp[m, 1] ** 2) / (2.0 * xp[m, 1]), 99.9)
                R = float(min(R_MAX, 1.25 * R, max(R, need + 0.05)))
                print(f'  [D] gather R -> {R:.3f}', flush=True)
        if phase == 'D':
            k = min(1.0, (t - t_D0) / (0.35 * T_PRESS))
            phi = 2.0 * math.pi
            h_tgt = 0.0                                       # spiral closes into a ring, flap pressed
            lift_tgt = LIFT_PRESS                             # ring lifted off the table so the
            unroll = 0.0                                      # press cannot extrude rice sideways
            vc_now = 0.0
            vt_now = 0.0
            y_cl = 0.0
            P_ref = (P_ROLL_REF + (P_PRESS_REF - P_ROLL_REF) * k) * args.press
            shp = shape if k >= 1.0 else 0
            if t - t_D0 >= T_PRESS:
                break
        phases.setdefault(phase, round(t, 2))
        dh = max(-V_LIFT * dt, min(V_LIFT * dt, h_tgt - h_lift))
        h_lift += dh
        dl = max(-V_LIFT * dt, min(V_LIFT * dt, lift_tgt - lift))
        S['substep'](dt, xc, R + lift, R, Rdot, Rdot + dl / dt, vc_now, phi, shp, MU_MAT, y_cl, unroll, h_lift, vt_now)
        lift += dl
        fnow = S['fn'][None]
        F_f += (fnow - F_f) * min(1.0, dt / tau_f)
        if step % ctrl_every == 0:
            arc_len = R * phi if shp == 0 else 8 * R
            F_t = P_ref * arc_len
            err = (F_f - F_t) / max(F_t, 1e-6)
            Rdot = V_RADIAL * max(-1.0, min(1.0, err))
            if R <= max(R_MIN, R_core) and Rdot < 0: Rdot = 0.0
            if R >= R_MAX and Rdot > 0: Rdot = 0.0
        R += Rdot * dt
        R = min(max(R, max(R_MIN, R_core)), R_MAX)
        t += dt
        xc += vc_now * dt
        if phase in ('A', 'B'):
            s_mat += v_c * dt
        if step % 400 == 0:
            log.append(dict(t=round(t, 2), ph=phase, xc=round(xc, 3), R=round(R, 3), h=round(h_lift, 3), phi=round(phi, 3),
                            yc=round(y_cl, 2), F=round(F_f, 4), Ft=round(P_ref * (R * phi if shp == 0 else 8 * R), 4)))
        if args.frames and step % snap_every == 0:
            save_frame(S, cls, xc, R, phi, shp, os.path.join(frames_dir, f'f{step:07d}.png'), t, F_f, y_clear=y_cl, phase=phase, h=h_lift)
            save_frame(S, cls, xc, R, phi, shp, os.path.join(frames_dir, f'f{step:07d}z.png'), t, F_f, y_clear=y_cl,
                       phase=phase, h=h_lift, zoom=((xc + 1.5, 2.6), 12.0))
        if step % 2000 == 0:
            el = time.time() - t0
            print(f'  step {step}/~{n_steps} [{phase}] t={t:.1f} xc={xc:.2f} R={R:.3f} phi={phi:.2f} F={F_f:.3f} '
                  f'esc={S["esc"][None]} {el:.0f}s', flush=True)
    n_steps = step
    if args.frames:
        save_frame(S, cls, xc, R, phi, shp, os.path.join(frames_dir, f'f{step:07d}.png'), t, F_f, y_clear=y_cl, phase=phase, h=h_lift)
    S['ti'].sync()
    elapsed = time.time() - t0
    esc_total = int(S['esc'][None])
    xs_f = S['x'].to_numpy(); vs_f = S['v'].to_numpy(); Jp = S['J'].to_numpy(); Ff = S['F'].to_numpy()

    # ---- outputs
    center = (xs_f[:, 0].mean(), xs_f[:, 1].mean())
    img, px = rasterize(xs_f, cls, info['hp'], W_NORI / info['nori_rows'], center, args.window, 600)
    np.save(os.path.join(args.out, f'material_{tag}.npy'), img)
    np.savez_compressed(os.path.join(args.out, f'particles_{tag}.npz'), x=xs_f, cls=cls, J=Jp, F=Ff)
    from PIL import Image
    rgb = np.zeros((600, 600, 3), np.uint8)
    for c, col in COLORS.items():
        rgb[img == c] = col
    Image.fromarray(rgb).save(os.path.join(args.out, f'material_{tag}.png'))
    global vol_of
    def vol_of(cl, c, inf):
        return float(np.sum(vol[cl == c]))
    extra = dict(layout=args.layout, speed=args.speed, press=args.press, tuck=args.tuck, R=R, window_T=args.window,
                 rice_map0=rice_map0, vol=vol,
                 mat=dict(v_pull=v_c, P_roll=P_ROLL_REF * args.press, P_press=P_PRESS_REF * args.press, mu_mat=MU_MAT,
                          mu_table=MU_TABLE, press_shape=layout['press_shape'], x_mat0=X_MAT0, x_end=x_end,
                          s_fold_base=round(s_fold_base, 3), s_fold=round(s_fold, 3), R_core=round(R_core, 3),
                          R_hold=round(R_hold, 3), lift_press=LIFT_PRESS, R_fit=round(R_fit, 3), a_fold=round(a_fold, 3), y_clear_fold=round(y_clear0, 3), pitch_rice=round(T + W_NORI, 3), pitch_flap=W_NORI,
                          t_roll_est=round(t_roll, 2), t_end=round(t, 2), t_press=T_PRESS),
                 phases=phases,
                 timing=dict(seconds=round(elapsed, 1), steps=n_steps, dt=round(dt, 6), grid=[nx, ny], dx=round(dx, 5),
                             particles=n, hp=round(info['hp'], 5)))
    met = compute_metrics(xs_f, vs_f, cls, Jp, nori_row, nori_col, info, layout, img, px, center, esc_total, extra)
    met['controller_log'] = log[-40:]
    def _js(o):
        if isinstance(o, (np.floating,)): return float(o)
        if isinstance(o, (np.integer,)): return int(o)
        if isinstance(o, (np.bool_,)): return bool(o)
        if isinstance(o, np.ndarray): return o.tolist()
        raise TypeError(str(type(o)))
    with open(os.path.join(args.out, f'metrics_{tag}.json'), 'w') as f:
        json.dump(met, f, indent=1, default=_js)
    save_frame(S, cls, xc, R, 2 * math.pi, shp, os.path.join(args.out, f'final_{tag}.png'), t, F_f,
               zoom=(center, args.window), y_clear=0.0, phase='D',
               contour=(met['centroid_xy'], tail_metrics(xs_f.astype(np.float64), met['centroid_xy'])[3]))
    print(json.dumps({k: v for k, v in met.items() if k not in ('controller_log', 'fillings')}, indent=1, default=_js))
    print(f'done in {elapsed:.1f}s')

def save_frame(S, cls, xc, R, phi, shp, path, t, F, zoom=None, y_clear=0.0, phase='', contour=None, h=0.0):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    xs = S['x'].to_numpy()
    fig, ax = plt.subplots(figsize=(12, 3.6) if zoom is None else (6, 6), dpi=100)
    colors = np.array([COLORS[c] for c in range(N_CLASS)]) / 255.0
    ax.scatter(xs[:, 0], xs[:, 1], c=colors[cls], s=1.2 if zoom is None else 4, linewidths=0)
    if shp == 0:
        th = np.linspace(0, phi, 400)
        rr_ = R - h * th / (2.0 * math.pi)
        ax_ = xc - rr_ * np.sin(th); ay_ = R - rr_ * np.cos(th)
        act = ~((ax_ > xc + 0.15) & (ay_ < y_clear))
        ax.plot(np.where(act, ax_, np.nan), np.where(act, ay_, np.nan), 'r-', lw=1.4)
        ax.plot(np.where(~act, ax_, np.nan), np.where(~act, ay_, np.nan), color='#804040', lw=0.6, ls=':')
    else:
        ax.plot([xc - R, xc + R, xc + R, xc - R, xc - R], [0, 0, 2 * R, 2 * R, 0], 'r-', lw=1)
    if contour is not None and contour[1] is not None:
        (cx0, cy0), cont = contour
        a = np.linspace(-math.pi, math.pi, len(cont), endpoint=False)
        ax.plot(cx0 + cont * np.cos(a), cy0 + cont * np.sin(a), color='#6cf', lw=0.8)
    ax.axhline(0, color='k', lw=0.5)
    if zoom is None:
        ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
    else:
        (cx, cy), wdt = zoom
        ax.set_xlim(cx - wdt / 2, cx + wdt / 2); ax.set_ylim(cy - wdt / 2, cy + wdt / 2)
    ax.set_aspect('equal'); ax.set_facecolor('#1c1c20')
    ax.set_title(f'[{phase}] t={t:.1f} xc={xc:.2f} R={R:.3f} phi={phi:.2f} yc={y_clear:.2f} F={F:.3f}', fontsize=8)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)

if __name__ == '__main__':
    main()
