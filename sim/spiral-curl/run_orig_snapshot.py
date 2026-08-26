#!/usr/bin/env python
"""kin-grab: 2D MLS-MPM reference of rolling a sushi sheet (cross-section, plane strain),
with chef-like four-phase winding kinematics (see KINEMATICS.md and README.md in this dir).

Difference from ../mpm-shell: materials, solver, rasterization and metrics are unchanged; the mat
kinematics are rewritten.

  phase A  edge lift   -- the near-edge nori particles (x < GRAB_W) are a kinematic GRAB ("fingers"):
                          their velocity is prescribed along a circular arc of radius x_p = s_fold/2
                          about the crease point (x_p, 0). The arc is exactly inextensible: the taut
                          sheet segment from the crease to the grabbed edge keeps length x_p at all
                          angles, so the near half of the fold rotates rigidly about the crease.
  phase B  tuck        -- the same arc continues past the apex down onto the sheet behind the fillings
                          (theta -> pi - TH_END_MARGIN), then the grab is driven straight down into the
                          rice bed to y_tuck and held; the mat arc engages from ABOVE (a cap around
                          theta = pi that widens with time) and its radius is force-controlled.
  phase C  rolling     -- the grab is released; the mat cylinder rolls ON the sheet: the roll centre
                          advances at omega*R (rolling without slipping, xc' = v_c, omega = v_c/R) and
                          the arc spans ~280 deg but its lower FRONT end is clamped above
                          y = Y_FRONT_MIN, so the mat never sweeps the table / the rice bed in front
                          of the roll.
  phase D  close+press -- the arc closes to 360 deg (pressing the bare nori flap onto the roll), then
                          the final pressing: radius shrinks to force equilibrium at P_press
                          (circle SDF, or rounded-square SDF for layout 5).

Units: T = 1 rice thickness (~5 mm), rho_rice = 1, E_rice = 1, time unit = T / sqrt(E_rice/rho_rice).

CLI: python run.py --layout 1|2|3|4|5 --speed 1.0 --press 1.0 --tuck 1.0
                   [--grid 240] [--particles 16000] [--frames 10] [--out DIR] [--tag ...]
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

# ----------------------------------------------------------------------------- materials  (unchanged)
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
X_END_EXTRA = 2.0        # hard cap: the roll centre never goes past sheet end + this

# --- grab ("fingers" of the mat holding the near edge)
GRAB_W = 0.9             # near-edge strip of nori that is kinematically grabbed, T
                         # (KINEMATICS.md says ~0.5 T; 0.9 T is needed so the prescribed strip does
                         #  not rip away from the rest of the sheet -- see README.md)
R_FINGER = 0.65          # radius of the rigid 'finger' disk that carries the grabbed strip, T
V_GRAB_REF = 0.20        # speed of the grabbed edge along its arc at --speed 1
TH_END_MARGIN = 0.30     # the fold arc stops at theta = pi - this (so the edge lands ON the rice bed)
B_CLEAR = 0.8            # the fold arc clears the tallest filling by this much, T
V_TUCK_FRAC = 0.5        # downward tuck speed as a fraction of the grab speed
Y_TUCK = W_NORI + 0.55 * T   # target height of the tucked edge (pressed into the rice bed)
T_HOLD = 5.0             # hold the tucked edge before releasing the grab
S_FOLD_EMPTY = 5.0       # s_fold for a sheet with no fillings, T
S_FOLD_MARGIN = 1.0      # s_fold = (end of the filling zone) + this, T

# --- mat
V_PULL_REF = 0.25        # roll-centre speed during phase C at --speed 1
P_ROLL_REF = 0.04        # mat pressure during rolling at --press 1 (units of E_rice)
                         # (halved vs ../mpm-shell after the sweep in README.md: at 0.08 the rice is
                         #  over-compacted, J drops to ~0.86 and the outer turn is shed)
P_PRESS_REF = 0.08       # mat pressure during final pressing at --press 1
P_FOLD_FRAC = 0.6        # phase-B pressure as a fraction of P_roll
V_RADIAL = 0.075         # max radial speed of the mat controller
R_MIN, R_MAX = 0.8, 8.0
PHI_ROLL = 5.50          # angular span of the mat during rolling, rad (~315 deg)
T_LIFT = 8.0             # time for the mat circle to rise onto the sheet at the start of phase C
V_LIFT = 0.08            # max rate of change of the mat lift
V_RADIAL_PRESS = 0.12    # radial speed of the mat controller during the final pressing
TH_BACK_MIN = 0.15       # the mat's back end stays this far (in angle) off the table
Y_BED = W_NORI + T       # thickness of the incoming sheet: the roll rolls without slip on ITS top
Y_FRONT_MIN = max(0.30, W_NORI + T + 0.15)   # lower FRONT end of the arc never goes below this (T).
                                             # KINEMATICS.md asks for >= 0.3 T; we also keep it above the
                                             # incoming rice bed (top = W_NORI + T) so the mat cannot scrape it.
T_WRAP = 12.0            # time for the phase-B cap to widen to the full rolling arc
T_CLOSE = 6.0            # phase-D closing of the arc to 360 deg
T_PRESS = 8.0            # minimum duration of the final pressing
T_PRESS_MAX = 46.0       # give up on force equilibrium after this
GRAVITY = 0.01
MU_TABLE = 0.4
MU_MAT = 2.0             # effectively sticky while pressed against the mat
CFL = 0.3
CORNER_R = 0.6           # corner radius of the square press
TAIL_TOL = 0.3           # a particle further than this outside the fitted contour counts as "tail outside"
TAIL_FRAC = 0.002        # fraction of particles above which tail_outside becomes True

# ----------------------------------------------------------------------------- particle sampling (unchanged)
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
    S['grab'] = ti.field(float, n_part)
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
    mu, la, tauy, gv, gm, fn, esc, grab = (S[k] for k in ['mu', 'la', 'tauy', 'gv', 'gm', 'fn', 'esc', 'grab'])
    dx = (Y1 - Y0) / ny
    inv_dx = 1.0 / dx

    @ti.kernel
    def init_particles(xs: ti.types.ndarray(), cl: ti.types.ndarray(), vo: ti.types.ndarray(),
                       rho: ti.types.ndarray(), gr: ti.types.ndarray()):
        for p in x:
            x[p] = [xs[p, 0], xs[p, 1]]
            v[p] = [0.0, 0.0]
            C[p] = ti.Matrix.zero(float, 2, 2)
            F[p] = ti.Matrix.identity(float, 2)
            cls[p] = cl[p]
            grab[p] = gr[p]
            vol[p] = vo[p]
            mass[p] = vo[p] * rho[cl[p]]
            J[p] = 1.0

    @ti.kernel
    def substep(dt: float, xc: float, R: float, Rdot: float, ylift: float, vly: float,
                vc: float, vspin: float, th_lo: float, th_hi: float,
                shape: ti.i32, mu_mat: float, gx: float, gy: float, gvx: float, gvy: float,
                gom: float, grad: float, grabbing: ti.i32):
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
            tau = ti.Matrix.zero(float, 2, 2)
            if True:
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
                # --- mat: arc of a circle centred at (xc, R), tangent to the table, spanning [th_lo, th_hi];
                #     th = 0 at the bottom, pi/2 behind, pi on top, 3pi/2 in front.
                ddx = px - xc
                ddy = py - (R + ylift)
                if shape == 0:
                    r = ti.sqrt(ddx * ddx + ddy * ddy)
                    dsd = r - R
                    if dsd > -0.5 * dx and dsd < 2.5 * dx and th_hi > th_lo:
                        th = ti.atan2(-ddx, -ddy)
                        if th < 0:
                            th += 2.0 * math.pi
                        if th >= th_lo and th <= th_hi:
                            sn = ti.sin(th); cs = ti.cos(th)
                            n = ti.Vector([sn, cs])            # inward normal
                            # rigid-body field of the mat: centre translates at vc, the cylinder spins
                            # at omega = vspin/R (vspin > vc => no slip on the SHEET TOP, not on the table)
                            vb = ti.Vector([vc, Rdot + vly]) + Rdot * ti.Vector([-sn, -cs]) + (vspin - th * Rdot) * ti.Vector([-cs, sn])
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
                    if dsd > -0.5 * dx and dsd < 2.5 * dx:
                        nout = ti.Vector([0.0, 1.0])
                        if qx > 0 and qy > 0:
                            nout = ti.Vector([mx, my]).normalized()
                        elif qx > qy:
                            nout = ti.Vector([1.0, 0.0])
                        nout[0] *= 1.0 if ddx >= 0 else -1.0
                        nout[1] *= 1.0 if ddy >= 0 else -1.0
                        n = -nout
                        vb = ti.Vector([0.0, Rdot]) + Rdot * nout
                        vrel = vv - vb
                        vn = vrel.dot(n)
                        if vn < 0:
                            vt = vrel - vn * n
                            vtn = vt.norm()
                            if vtn > 1e-12:
                                vt *= ti.max(0.0, 1.0 - mu_mat * (-vn) / vtn)
                            vv = vb + vt
                            fn[None] += gm[I] * (-vn) / dt
                # --- grab: "fingers" disk of radius grad, centre (gx, gy), rigid-body velocity, blended
                #     in over the outer 35% of the disk so the sheet is not sheared apart at its rim
                if grabbing == 1:
                    fdx = px - gx; fdy = py - gy
                    dd = ti.sqrt(fdx * fdx + fdy * fdy)
                    if dd < grad:
                        wg = ti.min(1.0, (grad - dd) / (0.35 * grad))
                        vv = (1.0 - wg) * vv + wg * ti.Vector([gvx - gom * fdy, gvy + gom * fdx])
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
            if (grabbing == 1) and (grab[p] > 0.0):
                wp = grab[p]
                nv = (1.0 - wp) * nv + wp * ti.Vector([gvx - gom * (x[p][1] - gy), gvy + gom * (x[p][0] - gx)])
                nC = (1.0 - wp) * nC
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

def tail_outside_metric(xs, cen_world, rout, n_ang, tol=TAIL_TOL):
    """Particles further than `tol` outside the fitted roll contour.

    The contour is the 36-ray outer radius smoothed with a 5-point running MEDIAN, so a tail sticking
    out over two or three rays cannot lift the contour under itself.
    """
    k = 2
    idxs = [np.arange(i - k, i + k + 1) % n_ang for i in range(n_ang)]
    rs = np.array([np.median(rout[ix]) for ix in idxs])
    rel = xs - np.array(cen_world, np.float64)
    r = np.hypot(rel[:, 0], rel[:, 1])
    ph = np.mod(np.arctan2(rel[:, 1], rel[:, 0]), 2 * math.pi)
    bi = np.mod(np.round(ph / (2 * math.pi / n_ang)).astype(int), n_ang)
    out = r > (rs[bi] + tol)
    excess = float(np.max(r - rs[bi])) if len(r) else 0.0
    return int(out.sum()), float(out.mean()), rs, out, excess

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
    tail_n, tail_frac, r_contour, tail_mask, tail_excess = tail_outside_metric(xs, cen_world, rout, len(angs))
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
        start = np.searchsorted(d, r)
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
        # deformation: bounding extent of the filling (max/min along principal axes)
        pts = xs[m] - np.array([cx, cy])
        cov = np.cov(pts.T); ev = np.linalg.eigvalsh(cov)
        fills.append(dict(kind=f['kind'], r_T=round(r, 3), phi_deg=round(phi, 1), centroid_xy=[round(cx, 3), round(cy, 3)],
                          rice_under_filling_T=round(under, 3), outer_hit=hit, rice_inside_T=round(inner, 3), inner_hit=hit_in,
                          aspect=round(math.sqrt(ev[1] / max(ev[0], 1e-9)), 3), area_T2=round(float(vol_of(cls, c, info)), 3)))
    # rice conservation
    rice_m = cls == CLASS_RICE
    rice_area_map = float(np.sum(img == CLASS_RICE)) * px * px
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
    order_by_phi = [f['kind'] for f in sorted(fills, key=lambda f: f['phi_deg'])]
    met = dict(
        layout=int(extra['layout']), layout_name=layout['name'], speed=extra['speed'], press=extra['press'],
        tuck=extra['tuck'],
        Rout_T=round(float(rout.max()), 3), Rout_mean_T=round(float(rout.mean()), 3), Rout_min_T=round(float(rout.min()), 3),
        Rout_median_T=round(float(np.median(rout)), 3),
        R_mat_T=round(extra['R'], 3), R_nori_outer_mean_T=round(float(np.mean(r_nori_out)), 3),
        nori_turns=round(float(np.mean(turns)), 3), nori_turns_min=int(np.min(turns)), nori_turns_max=int(np.max(turns)),
        tail_outside=bool(tail_frac > TAIL_FRAC), tail_outside_particles=int(tail_n),
        tail_outside_frac=round(tail_frac, 5), tail_tol_T=TAIL_TOL,
        tail_outside_nori=int(np.sum(tail_mask & (cls == CLASS_NORI))),
        tail_outside_max_excess_T=round(tail_excess, 3),
        rice_under_filling_T={f['kind']: f['rice_under_filling_T'] for f in fills},
        core=core, fillings=fills, core_order_left_to_right=order_by_x, core_order_by_phi=order_by_phi,
        rice_area_initial_T2=round(info['area_rice'], 3), rice_area_map_T2=round(rice_area_map, 3),
        rice_area_ratio=round(rice_area_map / info['area_rice'], 3), rice_J_mean=round(Jmean, 4),
        rice_particles=int(rice_m.sum()), particles=int(len(cls)), escaped=int(esc),
        nori_max_gap_T=round(max_gap, 4), nori_particle_spacing_T=round(info['nori_dx'], 4), nori_torn=bool(torn),
        nori_components_map=int(ncomp), nori_components_map_ge20px=big,
        v_max_final=round(vmax, 4), finite=finite, stable=bool(stable),
        window_T=extra['window_T'], px_T=round(px, 5), window_center_xy=[round(center[0], 3), round(center[1], 3)],
        centroid_xy=[round(cen_world[0], 3), round(cen_world[1], 3)],
        mat=extra['mat'], grab=extra['grab'], phases=extra['phases'], timing=extra['timing'],
    )
    return met

def vol_of(cls, c, info):
    return 0.0  # placeholder, replaced below via closure in main (area from particle volumes)

# ----------------------------------------------------------------------------- mat arc geometry
def enclosing_R(xnp, xc, ylift, R, q=99.5):
    """Smallest radius whose circle centred at (xc, R + ylift) wraps the material of the ROLL.
    For a point (px, py):  (px-xc)^2 + (py-ylift-R)^2 <= R^2  <=>  R >= (u^2+w^2)/(2w), u = px-xc,
    w = py-ylift.  Only material that is already lifted off the flat sheet (py > Y_BED + 0.35) and
    within a window around the roll counts, so the sheet still lying on the table cannot inflate it."""
    u = xnp[:, 0] - xc
    w = xnp[:, 1] - ylift
    m = (xnp[:, 1] > Y_BED + 0.35) & (w > 0.25) & (np.abs(u) < 1.4 * R + 1.2)
    if int(m.sum()) < 50:
        return 0.0
    return float(np.percentile((u[m] ** 2 + w[m] ** 2) / (2.0 * w[m]), q))


def arc_front_max(R, y_min):
    """Largest th (in (pi, 2pi]) whose point on the circle is still at height >= y_min."""
    if y_min <= 1e-9:
        return 2.0 * math.pi        # nothing to clear
    a = 1.0 - y_min / max(R, 1e-6)
    if a <= -1.0:
        return 2.0 * math.pi        # the whole front is above y_min
    if a >= 1.0:
        return math.pi              # even the top is below y_min -> only the top point
    return 2.0 * math.pi - math.acos(a)

# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layout', type=int, default=1)
    ap.add_argument('--speed', type=float, default=1.0)
    ap.add_argument('--press', type=float, default=1.0)
    ap.add_argument('--tuck', type=float, default=1.0, help='how far the grabbed edge is carried in phase B (0.6..1.3)')
    ap.add_argument('--fronty', type=float, default=-1.0,
                    help='height of the lower FRONT end of the mat arc, T (default: sheet top + 0.15)')
    ap.add_argument('--lift', type=float, default=1.0,
                    help='raise the mat circle by this fraction of the incoming sheet thickness, so the roll '
                         'rides ON the sheet instead of on the table (KINEMATICS.md phase C); 0 = on the table')
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
    tuck = min(1.3, max(0.6, args.tuck))
    lift_f = min(1.2, max(0.0, args.lift))
    y_front = Y_FRONT_MIN if args.fronty < 0 else max(0.30, args.fronty)

    aspect = (X1 - X0) / (Y1 - Y0)
    ny = int(round(args.grid / math.sqrt(aspect)))
    nx = int(round(ny * aspect))
    xs, cls, vol, nori_row, nori_col, info = sample_layout(layout, args.particles)
    n = len(cls)

    # ---------------- grab path (phases A and B) -------------------------------------------------
    if info['rects']:
        s_fold_base = max(r[0] + r[2] for r in info['rects']) + S_FOLD_MARGIN
        h_top = max(r[1] + r[3] for r in info['rects'])
    else:
        s_fold_base = S_FOLD_EMPTY
        h_top = W_NORI + T
    s_fold = tuck * s_fold_base
    x_p = 0.5 * s_fold                      # half-span of the fold arc (the crease sits near here)
    b_ap = min(x_p, h_top + B_CLEAR)        # apex height of the fold arc
    y_edge0 = 0.5 * W_NORI
    th_end = math.pi - TH_END_MARGIN
    # Fold arc of the grabbed edge (phases A and B):
    #     P(th) = ( x_p*(1 - cos th),  y_edge0 + b_ap*sin th ),  th: 0 -> th_end
    # a half ELLIPSE with semi-axes x_p (horizontal) and b_ap (vertical).  |P - (x_p, y_edge0)| <= x_p
    # for every th, so the sheet segment from the crease to the grabbed edge is never stretched; with
    # b_ap < x_p it is slack, and the sheet DRAPES over the fillings instead of sweeping them aside
    # (a taut half circle, b_ap = x_p, works for a bare sheet but flings a wide filling bundle).
    def Pg(th):
        return (x_p * (1.0 - math.cos(th)), y_edge0 + b_ap * math.sin(th))
    def dPg(th):
        return (x_p * math.sin(th), b_ap * math.cos(th))
    # tapered grab weight: 1 on the first half of the strip, fading to 0 at GRAB_W
    w_grab = np.clip((GRAB_W - xs[:, 0]) / (0.5 * GRAB_W), 0.0, 1.0)
    grab_np = np.where(cls == CLASS_NORI, w_grab, 0.0).astype(np.float32)
    n_grab = int((grab_np > 0).sum())
    # the "fingers": a rigid disk of radius R_FINGER around the centroid of the grabbed strip, carried
    # along the same path, so nothing inside the grab can be torn apart.
    g0 = (float(xs[grab_np == 1, 0].mean()), float(xs[grab_np == 1, 1].mean()))
    goff = (g0[0] - 0.0, g0[1] - y_edge0)
    def Gc(th):
        pp = Pg(th)
        return (pp[0] + goff[0], pp[1] + goff[1])

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
    S['init_particles'](xs.astype(np.float32), cls.astype(np.int32), vol.astype(np.float32), rho, grab_np.astype(np.float32))
    dt = CFL * dx / cmax
    v_c = V_PULL_REF * args.speed            # roll-centre speed, phase C
    v_g = V_GRAB_REF * args.speed            # grabbed-edge speed along the arc, phases A/B
    x_end = X_SHEET + L_SHEET + X_END_EXTRA

    # step budget (an upper bound; phase C can finish early, phase D is fixed)
    len_arc = 0.0
    for i in range(600):
        p0 = Pg(th_end * i / 600.0); p1 = Pg(th_end * (i + 1) / 600.0)
        len_arc += math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    t_fold = len_arc / v_g
    t_tuck = max(0.0, (Pg(th_end)[1] - Y_TUCK)) / (V_TUCK_FRAC * v_g)
    xc_C0 = 1.35 * x_p
    t_rollmax = (x_end - xc_C0) / v_c
    t_total_max = t_fold + t_tuck + T_HOLD + t_rollmax + T_CLOSE + T_PRESS_MAX
    n_steps_max = int(math.ceil(t_total_max / dt))
    R_init = 0.5 * (b_ap + h_top + 1.2) + 0.3

    print(f'grid {nx}x{ny} dx={dx:.4f} particles={n} grabbed={n_grab} hp={info["hp"]:.4f} nori rows={info["nori_rows"]} '
          f'dt={dt:.5f} cmax={cmax:.2f} v_c={v_c} v_g={v_g} s_fold={s_fold:.2f} x_p={x_p:.2f} b={b_ap:.2f} '
          f'R_init={R_init:.2f} t_fold={t_fold:.1f} t_rollmax={t_rollmax:.1f} steps<={n_steps_max}', flush=True)

    # ---------------- state ----------------------------------------------------------------------
    R = R_init; Rdot = 0.0; F_f = 0.0
    tau_f = 0.5
    shape = 0 if layout['press_shape'] == 'circle' else 1
    frames_dir = os.path.join(args.out, f'frames_{tag}')
    if args.frames:
        os.makedirs(frames_dir, exist_ok=True)
        for f in os.listdir(frames_dir):           # start from a clean set of snapshots
            if f.endswith('.png'):
                os.remove(os.path.join(frames_dir, f))
    snap_every = max(1, n_steps_max // max(args.frames, 1))
    t0 = time.time()
    log = []
    t = 0.0
    ctrl_every = 8
    phase = 'A'; last_phase = 'A'; t_phase = 0.0; th_g = 0.0
    t_engage = None                      # time the mat engaged (start of phase B)
    xc = xc_C0
    gp = Pg(0.0)                          # current grabbed-edge point (for the debug frames)
    gc = Gc(0.0)                          # current finger-disk centre
    gv_now = (0.0, 0.0)
    gom = 0.0
    ylift = 0.0; vly = 0.0
    err_last = 1.0
    R_floor = 0.0
    ylift_target = lift_f * Y_BED
    rice_idx = np.nonzero(cls == CLASS_RICE)[0]
    n_rice = len(rice_idx)
    phase_marks = {'A': 0.0}
    nori_idx = np.nonzero(cls == CLASS_NORI)[0]
    n_nori = len(nori_idx)
    step = 0
    frame_i = 0
    while True:
        # ---------------- kinematic schedule ------------------------------------------------------
        grabbing = 1
        engaged = phase not in ('A', 'B')
        if phase == 'A' or phase == 'B':
            sp = math.hypot(*dPg(th_g))
            th_g = min(th_end, th_g + v_g * dt / max(sp, 1e-6))
            d = dPg(th_g); sp = math.hypot(*d)
            gom = 0.0
            gp = Pg(th_g); gc = Gc(th_g)
            gv_now = (v_g * d[0] / sp, v_g * d[1] / sp) if th_g < th_end else (0.0, 0.0)
            if phase == 'A' and th_g >= 0.5 * math.pi:
                phase = 'B'; t_phase = 0.0; phase_marks['B'] = t
            elif phase == 'B' and th_g >= th_end - 1e-9:
                phase = 'Btuck'; t_phase = 0.0; t_engage = t; phase_marks['Btuck'] = t
        elif phase == 'Btuck':
            gom = 0.0
            gv_now = (0.0, -V_TUCK_FRAC * v_g)
            gp = (gp[0], gp[1] + gv_now[1] * dt)
            gc = (gc[0], gc[1] + gv_now[1] * dt)
            if gp[1] <= Y_TUCK:
                phase = 'Bhold'; t_phase = 0.0; phase_marks['Bhold'] = t
        elif phase == 'Bhold':
            gom = 0.0
            gv_now = (0.0, 0.0)
            if t_phase >= T_HOLD:
                phase = 'C'; t_phase = 0.0; phase_marks['C'] = t
                xnp = S['x'].to_numpy()
                hi = xnp[:, 1] > (W_NORI + T) * 1.15
                xc = float(xnp[hi, 0].mean()) if hi.sum() > 20 else xc_C0
                xc_C0 = xc
        elif phase == 'C':
            grabbing = 0
            xc += v_c * dt
        elif phase in ('D_close', 'D_press'):
            grabbing = 0

        # ---------------- mat lift + arc -----------------------------------------------------------
        ylift_prev = ylift
        if phase == 'C':
            tgt = ylift_target * min(1.0, t_phase / T_LIFT)
        elif phase == 'D_close':
            tgt = ylift_target * max(0.0, 1.0 - t_phase / T_CLOSE)
        else:
            tgt = 0.0
        ylift += max(-V_LIFT * dt, min(V_LIFT * dt, tgt - ylift))
        vly = (ylift - ylift_prev) / dt
        th_f_max = arc_front_max(R, max(0.0, y_front - ylift))
        if not engaged:
            th_lo, th_hi, vc_now, P_ref, shp = 1.0, 0.0, 0.0, P_ROLL_REF * args.press, 0
        elif phase in ('B', 'Btuck', 'Bhold'):
            frac = min(1.0, (t - t_engage) / T_WRAP)
            half = 0.5 + frac * (0.5 * PHI_ROLL - 0.5)
            th_lo = max(TH_BACK_MIN, math.pi - half)
            th_hi = min(th_f_max, math.pi + half)
            vc_now = 0.0
            P_ref = P_FOLD_FRAC * P_ROLL_REF * args.press
            shp = 0
        elif phase == 'C':
            th_hi = th_f_max
            th_lo = max(TH_BACK_MIN, th_hi - PHI_ROLL)
            vc_now = v_c
            P_ref = P_ROLL_REF * args.press
            shp = 0
        elif phase == 'D_close':
            f = min(1.0, t_phase / T_CLOSE)
            th_hi_c = th_f_max
            th_lo_c = max(TH_BACK_MIN, th_hi_c - PHI_ROLL)
            th_lo = (1 - f) * th_lo_c
            th_hi = (1 - f) * th_hi_c + f * 2.0 * math.pi
            vc_now = 0.0
            P_ref = (P_ROLL_REF + f * (P_PRESS_REF - P_ROLL_REF)) * args.press
            shp = 0
        else:  # D_press
            th_lo, th_hi = 0.0, 2.0 * math.pi
            vc_now = 0.0
            P_ref = P_PRESS_REF * args.press
            shp = shape

        # spin rate: rolling without slipping on the top of the incoming sheet (thickness Y_BED),
        # i.e. the instantaneous centre sits at y = Y_BED rather than on the table. This is what stops
        # the roll from bulldozing the rice bed in front of it.
        # The mat circle is tangent to the TOP OF THE INCOMING SHEET (y = ylift), not to the table, so
        # the bed can pass under the roll instead of being bulldozed. The instantaneous centre is then the
        # circle's own bottom point => plain rolling without slipping, vspin = vc.
        vspin = vc_now
        S['substep'](dt, xc, R, Rdot, ylift, vly, vc_now, vspin, th_lo, th_hi, shp, MU_MAT,
                     gc[0], gc[1], gv_now[0], gv_now[1], gom, R_FINGER, grabbing)

        # ---------------- radius controller --------------------------------------------------------
        fnow = S['fn'][None]
        F_f += (fnow - F_f) * min(1.0, dt / tau_f)
        if step % ctrl_every == 0:
            arc_len = R * max(th_hi - th_lo, 0.0) if shp == 0 else 8 * R
            F_t = P_ref * arc_len
            err = (F_f - F_t) / max(F_t, 1e-6)
            err_last = err
            vrad = V_RADIAL_PRESS if phase in ('D_close', 'D_press') else V_RADIAL
            Rdot = vrad * max(-1.0, min(1.0, err))
            if R <= R_MIN and Rdot < 0: Rdot = 0.0
            if R >= R_MAX and Rdot > 0: Rdot = 0.0
        R += Rdot * dt
        R = min(max(R, R_MIN), R_MAX)
        t += dt; t_phase += dt

        # ---------------- phase C -> D: the sheet is fully picked up --------------------------------
        if phase == 'C' and step % 200 == 0:
            xnp = S['x'].to_numpy()
            # nothing that is not yet part of the roll may stick out in front of it any more
            # (this is what winds the tail in instead of leaving it outside)
            # how thick is the sheet still coming in? (rice bed vs. bare nori flap)
            rf = int(np.sum((xnp[rice_idx, 0] > xc + 0.8 * R) & (xnp[rice_idx, 1] < 2.0)))
            ylift_target = lift_f * (Y_BED if rf > 0.01 * n_rice else (W_NORI + 0.15))
            d = np.hypot(xnp[:, 0] - xc, xnp[:, 1] - (R + ylift))
            outs = d > R + 0.5
            ahead = float((xnp[outs, 0] - xc).max()) if outs.any() else -1e9
            if ahead < 0.9 * R or xc >= x_end:
                phase = 'D_close'; t_phase = 0.0; phase_marks['D_close'] = t
                # close the mat AROUND everything, tail included: the smallest circle that is tangent to
                # the table at xc and contains every particle has
                #   R_enclose = max_p ((px-xc)^2 + py^2) / (2 py)
                xc = float(xnp[:, 0].mean())
                yy = np.maximum(xnp[:, 1], 0.05)
                need = (xnp[:, 0] - xc) ** 2 + yy ** 2
                need = need / (2.0 * yy)
                # 99.5th percentile, so a handful of stray crumbs cannot blow the mat wide open
                R = min(R_MAX, 1.8 * R, max(R, 1.03 * float(np.percentile(need, 99.5))))
                Rdot = 0.0
        if phase == 'D_close' and t_phase >= T_CLOSE:
            phase = 'D_press'; t_phase = 0.0; phase_marks['D_press'] = t
        if phase == 'D_press' and t_phase >= T_PRESS and (abs(err_last) < 0.08 or t_phase >= T_PRESS_MAX):
            phase_marks['end'] = t
            if args.frames:
                save_frame(S, cls, xc, R, th_lo, th_hi, shp, os.path.join(frames_dir, f'f{step:07d}_{phase}.png'), t, F_f, gp, grabbing, ylift=ylift)
            break

        if step % 400 == 0:
            log.append(dict(t=round(t, 2), ph=phase, xc=round(xc, 3), R=round(R, 3),
                            lo=round(th_lo, 3), hi=round(th_hi, 3), F=round(F_f, 4), Ft=round(P_ref * (R * max(th_hi - th_lo, 0.0) if shp == 0 else 8 * R), 4)))
        if phase != last_phase:
            _xp = S['x'].to_numpy(); _g = 0.0; _at = 0.0
            for _r in range(info['nori_rows']):
                _m = nori_row == _r; _o = np.argsort(nori_col[_m]); _p = _xp[_m][_o]
                _gg = np.linalg.norm(np.diff(_p, axis=0), axis=1)
                if _gg.max() > _g:
                    _g = float(_gg.max()); _at = float(nori_col[_m][_o][int(np.argmax(_gg))]) / info['nori_cols'] * L_SHEET
            print(f'  -> phase {phase} at t={t:.1f}  nori max gap={_g:.3f} T at s={_at:.1f} T', flush=True)
        if args.frames and phase != last_phase:
            save_frame(S, cls, xc, R, th_lo, th_hi, shp, os.path.join(frames_dir, f'f{step:07d}_{phase}.png'), t, F_f, gp, grabbing, ylift=ylift)
        last_phase = phase
        if args.frames and step % snap_every == 0:
            save_frame(S, cls, xc, R, th_lo, th_hi, shp, os.path.join(frames_dir, f'f{step:07d}_{phase}.png'), t, F_f, gp, grabbing, ylift=ylift)
            frame_i += 1
        if step % 2000 == 0:
            el = time.time() - t0
            print(f'  step {step} t={t:.1f} [{phase}] xc={xc:.2f} R={R:.3f} arc=[{th_lo:.2f},{th_hi:.2f}] '
                  f'F={F_f:.3f} esc={S["esc"][None]} {el:.0f}s', flush=True)
        step += 1
        if step > n_steps_max + int(60 / dt):
            print('  ! step budget exhausted', flush=True)
            phase_marks['end'] = t
            break

    S['ti'].sync()
    elapsed = time.time() - t0
    esc_total = int(S['esc'][None])
    xs_f = S['x'].to_numpy(); vs_f = S['v'].to_numpy(); Jp = S['J'].to_numpy()

    # ---- outputs
    center = (xs_f[:, 0].mean(), xs_f[:, 1].mean())
    img, px = rasterize(xs_f, cls, info['hp'], W_NORI / info['nori_rows'], center, args.window, 600)
    np.save(os.path.join(args.out, f'material_{tag}.npy'), img)
    np.savez_compressed(os.path.join(args.out, f'particles_{tag}.npz'), x=xs_f, cls=cls,
                        nori_row=nori_row, nori_col=nori_col, J=Jp, grab=grab_np)
    from PIL import Image
    rgb = np.zeros((600, 600, 3), np.uint8)
    for c, col in COLORS.items():
        rgb[img == c] = col
    Image.fromarray(rgb).save(os.path.join(args.out, f'material_{tag}.png'))
    global vol_of
    def vol_of(cl, c, inf):
        return float(np.sum(vol[cl == c]))
    ph = {k: round(v, 2) for k, v in phase_marks.items()}
    extra = dict(layout=args.layout, speed=args.speed, press=args.press, tuck=tuck, R=R, window_T=args.window,
                 mat=dict(v_pull=v_c, P_roll=P_ROLL_REF * args.press, P_press=P_PRESS_REF * args.press,
                          P_fold=P_FOLD_FRAC * P_ROLL_REF * args.press, mu_mat=MU_MAT, mu_table=MU_TABLE,
                          press_shape=layout['press_shape'], phi_roll=PHI_ROLL, y_front_min=y_front, t_lift=T_LIFT, lift_frac=lift_f,
                          th_back_min=TH_BACK_MIN, y_bed=Y_BED, R_init=round(R_init, 3), xc_C0=round(xc_C0, 3),
                          xc_final=round(xc, 3), x_end=x_end),
                 grab=dict(width_T=GRAB_W, finger_R=R_FINGER, apex_b=round(b_ap, 3), particles=n_grab, v_grab=v_g, s_fold=round(s_fold, 3),
                           s_fold_base=round(s_fold_base, 3), semi_axis_x=round(x_p, 3), y_edge0=round(y_edge0, 3),
                           th_end=round(th_end, 3), y_tuck=round(Y_TUCK, 3),
                           t_hold=T_HOLD, arc_len=round(len_arc, 3), h_top=round(h_top, 3)),
                 phases=ph,
                 timing=dict(seconds=round(elapsed, 1), steps=step, dt=round(dt, 6), grid=[nx, ny], dx=round(dx, 5),
                             particles=n, hp=round(info['hp'], 5), t_end=round(t, 2)))
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
    save_frame(S, cls, xc, R, 0.0, 2 * math.pi, shp, os.path.join(args.out, f'final_{tag}.png'), t, F_f, gp, 0,
               zoom=(center, args.window))
    print(json.dumps({k: v for k, v in met.items() if k not in ('controller_log', 'fillings')}, indent=1, default=_js))
    print(f'done in {elapsed:.1f}s  ({step} steps, t_end={t:.1f})')

def save_frame(S, cls, xc, R, th_lo, th_hi, shp, path, t, F, gp=None, grabbing=0, zoom=None, ylift=0.0):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    xs = S['x'].to_numpy()
    fig, ax = plt.subplots(figsize=(12, 3.6) if zoom is None else (6, 6), dpi=100)
    colors = np.array([COLORS[c] for c in range(N_CLASS)]) / 255.0
    colors[CLASS_NORI] = np.array([0.30, 0.85, 0.55])   # debug frames only: make the nori band visible
    ax.scatter(xs[:, 0], xs[:, 1], c=colors[cls], s=1.2 if zoom is None else 4, linewidths=0)
    if th_hi > th_lo:
        th = np.linspace(th_lo, th_hi, 240)
        if shp == 0:
            ax.plot(xc - R * np.sin(th), R + ylift - R * np.cos(th), 'r-', lw=1.2)
        else:
            ax.plot([xc - R, xc + R, xc + R, xc - R, xc - R],
                    [ylift, ylift, 2 * R + ylift, 2 * R + ylift, ylift], 'r-', lw=1.2)
    if gp is not None and grabbing:
        ax.plot([gp[0]], [gp[1]], marker='o', ms=5, mfc='none', mec='#ff4fd8', mew=1.5)
    ax.axhline(0, color='k', lw=0.5)
    if zoom is None:
        ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
    else:
        (cx, cy), wdt = zoom
        ax.set_xlim(cx - wdt / 2, cx + wdt / 2); ax.set_ylim(cy - wdt / 2, cy + wdt / 2)
    ax.set_aspect('equal'); ax.set_facecolor('#1c1c20')
    ax.set_title(f't={t:.1f} xc={xc:.2f} R={R:.3f} lift={ylift:.2f} arc=[{th_lo:.2f},{th_hi:.2f}] F={F:.3f}', fontsize=8)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)

if __name__ == '__main__':
    main()
