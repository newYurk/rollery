#!/usr/bin/env python
"""reference: 2D MLS-MPM reference of rolling a sushi sheet (cross-section, plane strain).

Merge of the two kinematics attempts (see ../kin-grab, ../kin-mat and README.md here):
  * from kin-grab (winner)  -- the four-phase fold driven by a kinematic GRAB of the near edge;
  * from kin-mat (grafted)  -- the mat as an ARCHIMEDEAN SPIRAL (pitch = thickness of the sheet
                               still lying ahead), the explicit fold-zone rule, the ring lift during
                               the press, and the conservation family of metrics.

  phase A  edge lift   -- the near-edge nori particles (x < GRAB_W) are a kinematic GRAB ("fingers"):
                          their velocity is prescribed along a half ELLIPSE with semi-axes
                          x_p = s_fold/2 and b_ap <= 0.8*x_p about the crease point (x_p, 0). The path
                          never stretches the sheet segment between crease and edge.
  phase B  tuck        -- the same arc continues past the apex down onto the sheet behind the fillings
                          (theta -> pi - TH_END_MARGIN), then the grab is driven straight down into the
                          rice bed to y_tuck and held; the mat engages from ABOVE (a cap around
                          theta = pi that widens with time) and its radius is force-controlled.
  phase C  rolling     -- the grab is released; the mat is a full-turn spiral touching the table at the
                          contact point and rising by one sheet thickness per turn, so its lower FRONT
                          branch rides ON TOP of the bed still lying ahead instead of ploughing it.
                          Rolling without slipping on the table: xc' = v_c, omega = v_c/R.
  phase D  close+press -- the spiral closes into a ring (pitch -> 0, flap pressed on), the ring is
                          opened once to enclose everything ("gather"), lifted LIFT_PRESS off the table
                          and pressed to force equilibrium at P_press (circle, or rounded square for
                          layout 5 -- the gather is then computed for the square).

Units: T = 1 rice thickness (~5 mm), rho_rice = 1, E_rice = 1, time unit = T / sqrt(E_rice/rho_rice).

CLI: python run.py --layout 1|2|3|4|5 --speed 1.0 --press 1.0 --tuck 1.0 --pitch 1.0 --seed 1
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
    # 6 is NOT one of the five control layouts of docs/simulation-research.md §5. It is a diagnostic for the
    # nori_turns target of KINEMATICS.md: a real futomaki carries ~15 cm2 of filling in cross-section, i.e.
    # ~60 T2 at T = 5 mm. With that much core the 38.7 T sheet closes in ~1.2 turns (see README §5.1).
    6: dict(name='futomaki-full-core', fillings=[fill('tamago', 1.5, 5.0, 4.4), fill('salmon', 7.0, 4.6, 4.0),
                                                 fill('avocado', 12.1, 4.4, 4.2, True)],
            press_shape='circle'),
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
B_SLACK = 0.80           # ... and never taut: b <= B_SLACK * x_p, or the arc tears the nori
V_TUCK_FRAC = 0.5        # downward tuck speed as a fraction of the grab speed
Y_TUCK = W_NORI + 0.55 * T   # target height of the tucked edge (pressed into the rice bed)
T_HOLD = 5.0             # hold the tucked edge before releasing the grab
S_FOLD_EMPTY = 5.0       # s_fold for a sheet with no fillings NEAR THE EDGE, T
S_FOLD_MARGIN = 1.0      # s_fold = (end of the fold zone) + this, T
# --- fold zone (grafted from kin-mat): only the fillings lying close to the near edge are folded
#     into the core. Without this rule layout 3 (one filling at mid-sheet) folds the sheet at its
#     middle, which is not what a cook does and not what the stand models.
FOLD_REACH = 5.0         # the first filling must start within this of the near edge to join the zone
FOLD_GAP = 2.5           # max gap between neighbouring fillings inside the zone, T
FOLD_CAP = 0.45          # s_fold never exceeds this fraction of the sheet

# --- mat
V_PULL_REF = 0.25        # roll-centre speed during phase C at --speed 1
P_ROLL_REF = 0.04        # mat pressure during rolling at --press 1 (units of E_rice)
                         # (halved vs ../mpm-shell after the sweep in README.md: at 0.08 the rice is
                         #  over-compacted, J drops to ~0.86 and the outer turn is shed)
P_PRESS_REF = 0.08       # mat pressure during final pressing at --press 1
P_FOLD_FRAC = 0.6        # phase-B pressure as a fraction of P_roll
V_RADIAL = 0.075         # max radial speed of the mat controller
R_MIN, R_MAX = 0.8, 8.0
PHI_ROLL = 5.50          # angular span of the mat's cap while the fold is being wrapped (phase B), rad
V_PITCH = 0.08           # max rate of change of the spiral pitch
V_RADIAL_PRESS = 0.12    # radial speed of the mat controller during the final pressing
TH_BACK_MIN = 0.15       # the mat's back end stays this far (in angle) off the table during phase B
Y_BED = W_NORI + T       # thickness of the incoming sheet = pitch of the mat spiral during rolling
LIFT_PRESS = 0.25        # phase D: the closed ring is held this high off the table while pressing, so
                         # the press cannot extrude rice sideways into the ring/table wedge (kin-mat)
T_WRAP = 12.0            # time for the phase-B cap to widen to the full rolling arc
T_CLOSE = 6.0            # phase-D closing of the arc to 360 deg
T_PRESS = 8.0            # minimum duration of the final pressing
T_PRESS_MAX = 46.0       # give up on force equilibrium after this (circle)
T_PRESS_MAX_SQ = 100.0   # ... and for the SQUARE press (layout 5). A rounded square of half-side R
                         # has area 4R^2 against the circle's pi R^2, so the mat must travel ~1.3 T
                         # further inwards, and it only starts loading once the corners fill: at 46
                         # the run stopped with F = 1.69 against a target of 3.01 and the flap still
                         # loose outside (67 nori particles, excess 1.17 T).
ANCHOR_MARGIN = 1.0     # '--anchor': the second hand holds the bed from x = s_fold + this ...
ANCHOR_Y = 0.6          # ... and only the layer lying on the table (this is a hold, not a wall)
FOLD_CLEAR = 0.8        # the rolling fold clears the tallest filling of the zone by this much, T
HOLD_RATE = 0.015       # 'second hand' (--hold): per-substep damping of the bed's horizontal velocity,
HOLD_MARGIN = 1.5       # ... downstream of x = s_fold + this, only while the near edge is grabbed.
                        # OFF by default: it keeps a heavy core from dragging the bed (layout 6) but it
                        # also stops the sheet feeding into the crease, and layout 4 then tears the nori.
GRAVITY = 0.01
MU_TABLE = 0.4
MU_MAT = 2.0             # effectively sticky while pressed against the mat
CFL = 0.3
CORNER_R = 0.6           # corner radius of the square press
PITCH_BAND0 = 1.05       # the pitch is measured over particles at x in [xc + BAND0*R, xc + BAND1*R]
PITCH_BAND1 = 2.20
PITCH_PROUD = 0.5        # ... and only if it stands this much proud of the bed
PITCH_MAX = 3.2          # ... and clamped here, T
C_EXIT_FRAC = 0.55       # phase C ends when nothing outside the mat is further ahead than this * R
TAIL_TOL = 0.3           # a particle further than this outside the fitted contour counts as "tail outside"
TAIL_FRAC = 0.002        # fraction of particles above which tail_outside becomes True
BG_HOLE_T = 0.35         # a background run shorter than this along a ray is a hole between particles,
                         # not the outside of the roll (rice_under_filling_T walk)

# ----------------------------------------------------------------------------- particle sampling (unchanged)
def sample_layout(layout, n_target, seed=1):
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
    rng = np.random.default_rng(seed)
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

# ----------------------------------------------------------------------------- fold zone (phases A/B)
def fold_zone(info):
    """Fillings lying close to the near edge form the core (grafted from kin-mat).

    Returns (s_fold_base, selected rects, area of the selected fillings). A filling joins the zone if
    it starts within FOLD_REACH of the near edge, or within FOLD_GAP of the previous member.
    """
    sel, reach = [], FOLD_REACH
    for r in sorted(info['rects'], key=lambda r: r[0]):
        if r[0] <= reach:
            sel.append(r)
            reach = r[0] + r[2] + FOLD_GAP
    if not sel:
        return S_FOLD_EMPTY, [], 0.0
    end = max(r[0] + r[2] for r in sel) + S_FOLD_MARGIN
    a = sum((math.pi / 4 if r[4] else 1.0) * r[2] * r[3] for r in sel)
    return min(end, FOLD_CAP * L_SHEET), sel, a

def predict_layers(info, s_fold, a_fold=0.0):
    """Wrapper-layer count implied by AREA CONSERVATION (KINEMATICS.md, correction of 26.08.2026).

    (a) the LITERAL formula of the correction -- the number the stand is compared against:

        area  = rice (L - flap)*T + nori L*w + fillings
        Rout  = sqrt(area/pi);   Rcore = sqrt(s_fold * (T + w) / pi)
        layers = (Rout - Rcore) / (T + w)

    (b) the same accounting with the two terms the literal version drops. Both are area
        bookkeeping, neither knows anything about the kinematics:

        * the fillings that lie IN THE FOLD ZONE end up inside the core, so their area belongs
          to Rcore and not to the wrapper annulus. The literal formula puts them in Rout only,
          which counts them twice in the annulus and over-predicts the layer count;
        * a sheet of thickness h cannot be creased to zero radius: the fold leaves a hollow of
          radius ~h at the crease, which adds h^2 to Rcore^2 and removes ~0.35 layers.

          Rcore_core   = sqrt( (s_fold*h + a_fold) / pi )
          Rcore_hollow = sqrt( Rcore_core^2 + h^2 )
          layers_core  = (Rout - Rcore_hollow) / h

    The ray metric `nori_turns` counts the tuck nori as well, hence crossings = layers + 1.
    """
    h = T + W_NORI
    area = info['area_rice'] + info['area_nori'] + info['area_fill']
    r_out = math.sqrt(area / math.pi)
    r_core = math.sqrt(max(s_fold, 0.0) * h / math.pi)
    layers = (r_out - r_core) / h
    r_core2 = math.sqrt((max(s_fold, 0.0) * h + max(a_fold, 0.0)) / math.pi)
    r_hollow = math.sqrt(r_core2 * r_core2 + h * h)
    layers2 = (r_out - r_hollow) / h
    return dict(area_T2=round(area, 3), Rout_pred_T=round(r_out, 3), Rcore_pred_T=round(r_core, 3),
                layers_predicted=round(layers, 3), crossings_predicted=round(layers + 1.0, 3),
                a_fold_T2=round(a_fold, 3),
                Rcore_core_T=round(r_core2, 3), Rcore_hollow_T=round(r_hollow, 3),
                layers_predicted_core=round(layers2, 3), crossings_predicted_core=round(layers2 + 1.0, 3))

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
                vc: float, vspin: float, th_lo: float, th_hi: float, pitch: float, unroll: float,
                shape: ti.i32, mu_mat: float, gx: float, gy: float, gvx: float, gvy: float,
                gom: float, grad: float, grabbing: ti.i32, hold_x0: float, hold_y1: float, hold_damp: float,
                anch_x0: float, anch: float):
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
                    th = ti.atan2(-ddx, -ddy)
                    if th < 0:
                        th += 2.0 * math.pi
                    # Archimedean spiral (kin-mat): one turn back from the contact point the mat is
                    # `pitch` thinner, so its lower-front branch rides at the height of the sheet still
                    # lying ahead (pitch = T + W_NORI) instead of cutting through it.
                    rb = R - pitch * th / (2.0 * math.pi)
                    dsd = r - rb
                    if dsd > -0.5 * dx and dsd < 3.0 * dx and th_hi > th_lo:
                        if th >= th_lo and th <= th_hi:
                            sn = ti.sin(th); cs = ti.cos(th)
                            n = ti.Vector([sn, cs])            # inward normal
                            # rigid-body field of the mat: centre translates at vc, the mat spins at
                            # omega = vspin/R; the rb/R factor keeps the spin rigid (tangential speed
                            # proportional to the local radius), so vb(th=0) = 0 -- no slip on the table.
                            vb = ti.Vector([vc, Rdot + vly]) + Rdot * ti.Vector([-sn, -cs]) \
                                 + (vspin * rb / R - unroll * th * Rdot) * ti.Vector([-cs, sn])
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
                        vb = ti.Vector([0.0, Rdot + vly]) + Rdot * nout
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
                # --- second hand: while the near edge is being folded (phases A/B) the chef's other hand
                #     holds the sheet down beyond the fold zone, so the bed is not dragged along. Soft
                #     anchor on the horizontal velocity of the bed nodes downstream of x = hold_x0.
                if grabbing == 1 and px > hold_x0 and py < hold_y1:
                    vv[0] *= hold_damp
                # --- one-sided anchor (--anchor): the sheet still lying flat ahead of the fold zone may
                #     not be pulled BACKWARDS into the crease. Forward motion is untouched, so the sheet
                #     still feeds into the roll -- this is what --hold got wrong (it damped both ways and
                #     starved the crease). Physically: the chef's other hand on the mat.
                if grabbing == 1 and anch > 0.0 and px > anch_x0 and py < ANCHOR_Y and vv[0] < 0.0:
                    vv[0] *= (1.0 - anch)
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

def raster_class_area(xs, cls, hp, nori_dy, px, which=CLASS_RICE):
    """Same disc rasterization as `rasterize`, but over a bounding box of the whole scene (kin-mat).
    Used once on the INITIAL state to calibrate the rasterization bias of rice_area_ratio."""
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

def turns_geom(info):
    """A-priori number of spiral turns: an Archimedean spiral of pitch h = T + W_NORI wound from a core of
    area info['area_fill'] until the whole sheet is used. pi*(R^2 - r0^2) = h * L_SHEET, N = (R - r0)/h.
    Depends only on sheet length, rice thickness and filling area - NOT on the kinematics."""
    h = T + W_NORI
    r0 = math.sqrt(max(info['area_fill'], 0.0) / math.pi)
    R = math.sqrt(r0 * r0 + h * L_SHEET / math.pi)
    return (R - r0) / h

# ----------------------------------------------------------------------------- wrinkle metric ("accordion")
# The defect the owner found on the phase-B frames: the wrapper band gathers into 2-3 folds instead of
# bending into one arc (../KINEMATICS.md, "gармошка"). Measured on the MIDLINE of the nori band:
#   wrinkles  = sign changes of the signed curvature along the band, outside the fold nose
#   amplitude = largest departure of the midline from a local quadratic fit, T
# The midline is smoothed over 3 particles (as specified) and then RESAMPLED at WR_DS along arc length:
# raw particle-to-particle curvature is pure noise (spacing 0.05 T, position noise ~0.005 T gives
# kappa noise ~2 1/T, above any sane threshold), the 0.25 T resampling brings it to ~0.08.
WR_DS = 0.25                        # arc-length step the midline is resampled at, T
WR_KAPPA_MIN = 1.0 / (T + W_NORI)   # 0.893 1/T -- a reversal counts only if it bends TIGHTER than the
                                    # sheet's own thickness; the roll's own core (R ~ 1.3 T) never trips it
WR_NOSE_T = math.pi * (T + W_NORI)  # arc length of the fold nose that is excluded (a half turn at r = h), T
WR_EDGE_T = 1.0                     # ... and this much at each end of the sheet
WR_FIT_T = 0.9                      # half-window of the local quadratic fit used for the amplitude, T
WR_EVERY = 400                      # steps between samples of the metric during the run


def _movavg(P, k):
    if k <= 1 or len(P) <= k:
        return P
    ker = np.ones(k) / k
    Q = np.column_stack([np.convolve(P[:, 0], ker, 'same'), np.convolve(P[:, 1], ker, 'same')])
    m = k // 2
    return Q[m: len(Q) - m]


def nori_midline(xs, nori_row, nori_col, nrows, smooth=3):
    """Mid-surface polyline of the nori band, ordered along the sheet and smoothed over `smooth` particles."""
    if nrows >= 2:
        a = nori_row == 0
        b = nori_row == (nrows - 1)
        pa = xs[a][np.argsort(nori_col[a])]
        pb = xs[b][np.argsort(nori_col[b])]
        m = min(len(pa), len(pb))
        P = 0.5 * (pa[:m] + pb[:m])
    else:
        a = nori_row == 0
        P = xs[a][np.argsort(nori_col[a])]
    return _movavg(np.asarray(P, np.float64), smooth)


def _sg_smooth_kernel(n, order=2):
    m = (n - 1) // 2
    xx = np.arange(-m, m + 1, dtype=float)
    A = np.vander(xx, order + 1, increasing=True)
    return np.linalg.pinv(A)[0][::-1]        # value of the fit at the centre, as a convolution kernel


def wrinkle_metric(xs, nori_row, nori_col, nrows, x0=None, s_fold=None):
    """Number of curvature reversals of the wrapper band outside the fold nose, and their amplitude.

    Two companion diagnostics of the same defect, because the count alone misses the L1 form of it
    (there the band makes ONE hairpin -- inside the nose window, so uncounted -- and it is the bed that
    is churned):
      fold_radius_T = 1/max|kappa| over the whole band: the tightest crease the sheet is bent to. A
                      sheet of thickness h cannot be creased tighter than ~h/2; anything below that is
                      the sheet folding on itself.
      bed_drag_T    = how far the sheet still lying flat AHEAD of the fold zone has been dragged
                      BACKWARDS (initial x minus current x). The crease acts as a pulley when the sheet
                      is not held: the top layer lengthens by feeding bed through the crease. > 0.5 T is
                      the pulley at work.
    """
    out = dict(wrinkles=0, wrinkle_amp_T=0.0, wrinkle_kappa_max=0.0, wrinkle_reversals=0,
               wrinkle_nose_s_T=0.0, wrinkle_len_T=0.0, fold_radius_T=0.0, bed_drag_T=0.0)
    if x0 is not None and s_fold is not None:
        flat = (x0 > s_fold + 2.0) & (xs[:, 1] < 0.6) & (nori_row == 0)
        if flat.sum() > 10:
            out['bed_drag_T'] = round(float(np.percentile(x0[flat] - xs[flat, 0], 90.0)), 3)
    P = nori_midline(xs, nori_row, nori_col, nrows)
    if len(P) < 8:
        return out
    seg0 = np.hypot(*np.diff(P, axis=0).T)
    s0 = np.concatenate([[0.0], np.cumsum(seg0)])
    if s0[-1] < 6.0 * WR_DS:
        return out
    sq = np.arange(0.0, s0[-1], WR_DS)
    Q = np.column_stack([np.interp(sq, s0, P[:, 0]), np.interp(sq, s0, P[:, 1])])
    out['wrinkle_len_T'] = round(float(s0[-1]), 3)
    if len(Q) < 8:
        return out
    d = np.diff(Q, axis=0)
    seg = np.hypot(d[:, 0], d[:, 1])
    tv = d / np.maximum(seg, 1e-12)[:, None]
    cr = tv[:-1, 0] * tv[1:, 1] - tv[:-1, 1] * tv[1:, 0]
    dp = (tv[:-1] * tv[1:]).sum(1)
    ang = np.arctan2(cr, dp)                                  # signed turn at each interior vertex, rad
    ds = 0.5 * (seg[:-1] + seg[1:])
    kap = ang / np.maximum(ds, 1e-12)                         # signed curvature, 1/T
    sv = sq[1:len(ang) + 1]
    kmax = float(np.max(np.abs(kap)))
    out['fold_radius_T'] = round(1.0 / kmax, 4) if kmax > 1e-6 else 99.0
    # --- fold nose: the WR_NOSE_T window of arc length that accumulates the most turning. That is the
    #     crease itself (or, once the roll is wound, its tightest turn); wrinkles are counted OUTSIDE it.
    cum = np.concatenate([[0.0], np.cumsum(np.abs(ang))])
    j = np.minimum(np.searchsorted(sv, sv + WR_NOSE_T), len(sv))
    i0 = int(np.argmax(cum[j] - cum[np.arange(len(sv))]))
    nose_lo, nose_hi = sv[i0], sv[i0] + WR_NOSE_T
    out['wrinkle_nose_s_T'] = round(float(nose_lo), 3)
    ok = ~((sv >= nose_lo) & (sv <= nose_hi)) & (sv >= WR_EDGE_T) & (sv <= s0[-1] - WR_EDGE_T)
    strong = ok & (np.abs(kap) >= WR_KAPPA_MIN)
    sgn = np.sign(kap[strong])
    if len(sgn) > 1:
        out['wrinkles'] = int(np.sum(sgn[1:] != sgn[:-1]))
    if len(sgn):
        dom = 1.0 if np.sum(sgn > 0) >= np.sum(sgn < 0) else -1.0
        rev = sgn != dom
        out['wrinkle_reversals'] = int(np.sum(rev[1:] & ~rev[:-1]) + (1 if len(rev) and rev[0] else 0))
        out['wrinkle_kappa_max'] = round(float(np.max(np.abs(kap[strong][rev]))) if rev.any() else 0.0, 3)
    # --- amplitude: departure from a LOCAL QUADRATIC fit (a quadratic follows a smooth roll almost
    #     exactly, so only short-wave corrugation is left in the residual)
    nfit = 2 * int(round(WR_FIT_T / WR_DS)) + 1
    if len(Q) > nfit + 4:
        ker = _sg_smooth_kernel(nfit)
        bx = np.convolve(Q[:, 0], ker, 'same')
        by = np.convolve(Q[:, 1], ker, 'same')
        dev = np.hypot(Q[:, 0] - bx, Q[:, 1] - by)
        m = nfit // 2
        okv = np.zeros(len(Q), bool)
        okv[m:len(Q) - m] = True
        okv &= (sq >= WR_EDGE_T) & (sq <= s0[-1] - WR_EDGE_T)
        okv &= ~((sq >= nose_lo - WR_FIT_T) & (sq <= nose_hi + WR_FIT_T))
        if okv.any():
            out['wrinkle_amp_T'] = round(float(dev[okv].max()), 4)
    return out


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
        # walk from the filling centroid outward: skip own class, count rice until nori.
        # A short BG run is a hole between particles, not the outside of the roll: only a run longer
        # than BG_HOLE_T ends the walk. (In kin-grab/kin-mat every walk died on the first pixel hole,
        # so rice_under_filling_T came out 0 for almost every filling.)
        bg_hole = int(BG_HOLE_T / (0.2 * px))
        start = min(int(np.searchsorted(d, r)), len(seq) - 1)
        k = start
        while k < len(seq) and seq[k] == c:
            k += 1
        under = 0.0; hit = 'none'; k2 = k; bg = 0
        while k2 < len(seq):
            if seq[k2] == CLASS_NORI:
                hit = 'nori'; break
            if seq[k2] == CLASS_RICE:
                under += 0.2 * px; bg = 0
            elif seq[k2] == CLASS_BG:
                bg += 1
                if bg > bg_hole:
                    hit = 'bg'; break
            elif seq[k2] != c:
                hit = MAT_OF_CLASS.get(int(seq[k2]), 'other'); break
            k2 += 1
        # inward: rice between filling and the previous turn's nori (or the center)
        k3 = start
        while k3 >= 0 and seq[k3] == c:
            k3 -= 1
        inner = 0.0; hit_in = 'center'; bg = 0
        while k3 >= 0:
            if seq[k3] == CLASS_NORI:
                hit_in = 'nori'; break
            if seq[k3] == CLASS_RICE:
                inner += 0.2 * px; bg = 0
            elif seq[k3] == CLASS_BG:
                bg += 1
                if bg > bg_hole:
                    hit_in = 'bg'; break
            elif seq[k3] != c:
                hit_in = MAT_OF_CLASS.get(int(seq[k3]), 'other'); break
            k3 -= 1
        # deformation: bounding extent of the filling (max/min along principal axes)
        pts = xs[m] - np.array([cx, cy])
        cov = np.cov(pts.T); ev = np.linalg.eigvalsh(cov)
        fills.append(dict(kind=f['kind'], r_T=round(r, 3), phi_deg=round(phi, 1), centroid_xy=[round(cx, 3), round(cy, 3)],
                          rice_under_filling_T=round(under, 3), outer_hit=hit, rice_inside_T=round(inner, 3), inner_hit=hit_in,
                          aspect=round(math.sqrt(ev[1] / max(ev[0], 1e-9)), 3), area_T2=round(float(vol_of(cls, c, info)), 3)))
    # ---- conservation: the honest measure of "nothing was lost".
    # Sum(vol_p * J_p) at the end vs Sum(vol_p) at the start. Everything else (the class map) is a
    # rasterization of a point cloud and undercounts a sheared material; this does not.
    volp = np.asarray(extra['vol'], np.float64)
    rice_m = cls == CLASS_RICE
    nori_m = cls == CLASS_NORI
    fill_m = cls > CLASS_NORI
    def _cons(m):
        return float(np.sum(volp[m] * Jp[m]) / np.sum(volp[m])) if m.any() else float('nan')
    conservation = float(np.sum(volp * Jp) / np.sum(volp))
    rice_area_map = float(np.sum(img == CLASS_RICE)) * px * px
    Jmean = float(np.mean(Jp[rice_m]))
    # rice outside the fitted contour: the physical form of "rice was ploughed off the sheet"
    rel_r = xs[rice_m] - np.array(cen_world, np.float64)
    rr_r = np.hypot(rel_r[:, 0], rel_r[:, 1])
    bi_r = np.mod(np.round(np.mod(np.arctan2(rel_r[:, 1], rel_r[:, 0]), 2 * math.pi) /
                           (2 * math.pi / len(angs))).astype(int), len(angs))
    rice_out = float(np.mean(rr_r > r_contour[bi_r] + TAIL_TOL))
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
        tuck=extra['tuck'], pitch=extra['pitch'], seed=extra['seed'],
        # --- conservation (correction 2 of KINEMATICS.md): Sum(vol*J) / Sum(vol), must be >= 0.97
        conservation=round(conservation, 4),
        conservation_rice=round(_cons(rice_m), 4),
        conservation_nori=round(_cons(nori_m), 4),
        conservation_fillings=round(_cons(fill_m), 4) if fill_m.any() else None,
        volume_end_T2=round(float(np.sum(volp * Jp)), 3), volume_start_T2=round(float(np.sum(volp)), 3),
        rice_outside_contour_frac=round(rice_out, 5),
        # --- layers implied by area conservation (correction 1): the target for nori_turns
        layers_predicted=extra['pred']['layers_predicted'],
        crossings_predicted=extra['pred']['crossings_predicted'],
        Rout_pred_T=extra['pred']['Rout_pred_T'], Rcore_pred_T=extra['pred']['Rcore_pred_T'],
        area_pred_T2=extra['pred']['area_T2'],
        # --- the same area bookkeeping with the fold-zone fillings put inside the core and a crease
        #     hollow of one sheet thickness (see predict_layers): this is the number the reference
        #     actually reproduces, the literal one above is what the stand is compared against.
        layers_predicted_core=extra['pred']['layers_predicted_core'],
        crossings_predicted_core=extra['pred']['crossings_predicted_core'],
        Rcore_core_T=extra['pred']['Rcore_core_T'], Rcore_hollow_T=extra['pred']['Rcore_hollow_T'],
        a_fold_pred_T2=extra['pred']['a_fold_T2'],
        Rout_T=round(float(rout.max()), 3), Rout_mean_T=round(float(rout.mean()), 3), Rout_min_T=round(float(rout.min()), 3),
        Rout_median_T=round(float(np.median(rout)), 3),
        R_mat_T=round(extra['R'], 3), R_nori_outer_mean_T=round(float(np.mean(r_nori_out)), 3),
        nori_turns=round(float(np.mean(turns)), 3), nori_turns_min=int(np.min(turns)), nori_turns_max=int(np.max(turns)),
        nori_turns_geom=round(turns_geom(info), 3),
        turns_minus_predicted=round(float(np.mean(turns)) - extra['pred']['crossings_predicted'], 3),
        turns_match_formula=bool(abs(float(np.mean(turns)) - extra['pred']['crossings_predicted']) <= 0.25),
        turns_minus_predicted_core=round(float(np.mean(turns)) - extra['pred']['crossings_predicted_core'], 3),
        turns_match_formula_core=bool(abs(float(np.mean(turns)) - extra['pred']['crossings_predicted_core']) <= 0.25),
        # --- the "accordion" defect (KINEMATICS.md, 26.08.2026): curvature reversals of the wrapper
        #     band outside the fold nose. Acceptance: wrinkles_max <= 1 and amplitude < 0.5 T.
        wrinkles=int(extra['wr']['final']['wrinkles']),
        wrinkles_max=int(extra['wr']['wrinkles_max']), wrinkles_max_phase=extra['wr']['wrinkles_max_phase'],
        wrinkle_amp_T=float(extra['wr']['final']['wrinkle_amp_T']),
        wrinkle_amp_max_T=float(extra['wr']['wrinkle_amp_max_T']),
        wrinkle_amp_max_phase=extra['wr']['wrinkle_amp_max_phase'],
        wrinkle_kappa_max=float(extra['wr']['final']['wrinkle_kappa_max']),
        fold_radius_min_T=float(extra['wr']['fold_radius_min_T']),
        bed_drag_max_T=float(extra['wr']['bed_drag_max_T']),
        wrinkles_by_phase=extra['wr']['by_phase'],
        wrinkle_ok=bool(extra['wr']['wrinkles_max'] <= 1 and extra['wr']['wrinkle_amp_max_T'] < 0.5),
        tail_outside=bool(tail_frac > TAIL_FRAC), tail_outside_particles=int(tail_n),
        tail_outside_frac=round(tail_frac, 5), tail_tol_T=TAIL_TOL,
        tail_outside_nori=int(np.sum(tail_mask & (cls == CLASS_NORI))),
        tail_outside_max_excess_T=round(tail_excess, 3),
        rice_under_filling_T={f['kind']: f['rice_under_filling_T'] for f in fills},
        core=core, fillings=fills, core_order_left_to_right=order_by_x, core_order_by_phi=order_by_phi,
        rice_area_initial_T2=round(info['area_rice'], 3), rice_area_map_T2=round(rice_area_map, 3),
        rice_area_ratio=round(rice_area_map / info['area_rice'], 3), rice_J_mean=round(Jmean, 4),
        rice_area_ratio_vs_J=round(rice_area_map / (info['area_rice'] * max(Jmean, 1e-6)), 3),
        rice_area_map_initial_T2=round(extra['rice_map0'], 3),
        rice_area_ratio_ref=round(rice_area_map / max(extra['rice_map0'], 1e-9), 3),
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

# ----------------------------------------------------------------------------- mat geometry
def gather_R(xnp, xc, R, shape, pct=99.5, grow=1.8, must=None):
    """Radius the closing mat needs so that everything -- the tail included -- ends up INSIDE it.

    shape 0 (circle tangent to the table at xc): the circle through a particle (px, py) has
        R_enclose = ((px - xc)^2 + py^2) / (2 py).
    shape 1 (rounded square of half-side R, tangent to the table): containment needs
        R_enclose = max(|px - xc|, py).
    The percentile keeps a handful of stray crumbs from blowing the mat wide open; `grow` caps how far
    a single gather may open the mat. `must` is a mask of particles that may NOT be left outside at
    any percentile -- the WRAPPER: a crumb of rice outside the mat is a crumb, a loose flap of nori is
    a defect (layout 5 left 101 nori particles and 1.07 T of flap hanging out at pct = 99.5).
    """
    yy = np.maximum(xnp[:, 1], 0.05)
    if shape == 0:
        need = ((xnp[:, 0] - xc) ** 2 + yy ** 2) / (2.0 * yy)
    else:
        need = np.maximum(np.abs(xnp[:, 0] - xc), yy)
    r_need = float(np.percentile(need, pct))
    if must is not None and must.any():
        r_need = max(r_need, float(np.percentile(need[must], 99.9)))
    return float(min(R_MAX, grow * R, max(R, 1.03 * r_need)))

# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--layout', type=int, default=1)
    ap.add_argument('--speed', type=float, default=1.0)
    ap.add_argument('--press', type=float, default=1.0)
    ap.add_argument('--hold', type=float, default=0.0,
                    help="'second hand': damp the bed's horizontal velocity downstream of the fold zone "
                         'while the edge is grabbed (0 = off, 1 = 1.5%% per substep)')
    ap.add_argument('--tuck', type=float, default=1.0, help='how far the grabbed edge is carried in phase B (0.6..1.3)')
    ap.add_argument('--pitch', type=float, default=1.0,
                    help='spiral pitch of the mat as a fraction of the incoming sheet thickness (1 = the mat '
                         'rides exactly on top of the bed lying ahead; 0 = plain circle, ploughs the rice)')
    ap.add_argument('--fold', type=str, default='roll', choices=['roll', 'ellipse'],
                    help="path of the grabbed edge in phases A/B: 'roll' (default) is the CYCLOID of a "
                         'cylinder of radius r_fold rolling from x=0 to x=s_fold -- the fold radius is '
                         "then fixed and the length budget is exact; 'ellipse' is the old half-ellipse "
                         'about the crease point (kept for comparison: it starts vertically, which the '
                         'sheet can only follow by hairpinning on itself)')
    ap.add_argument('--anchor', type=float, default=1.0,
                    help="'second hand', one-sided: while the edge is grabbed, the bed lying flat beyond "
                         'x = s_fold + 1 may not move BACKWARDS (0 = free, 1 = fully held). Unlike --hold '
                         'it does not stop the sheet feeding forward, only the crease-as-a-pulley')
    ap.add_argument('--bend', type=float, default=0.0,
                    help='bending stiffness of the nori band as a fraction of the physical E*w^3/12 '
                         '(0 = none, the MPM band is thinner than a cell and has no resolved bending)')
    ap.add_argument('--seed', type=int, default=1, help='RNG seed of the particle jitter')
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
    pitch_f = min(1.2, max(0.0, args.pitch))

    aspect = (X1 - X0) / (Y1 - Y0)
    ny = int(round(args.grid / math.sqrt(aspect)))
    nx = int(round(ny * aspect))
    xs, cls, vol, nori_row, nori_col, info = sample_layout(layout, args.particles, args.seed)
    n = len(cls)

    # ---------------- grab path (phases A and B) -------------------------------------------------
    # Only the fillings lying near the near edge are folded into the core (fold_zone, from kin-mat):
    # a filling at mid-sheet (layout 3) is wound in by the roll, not tucked.
    s_fold_base, fold_rects, a_fold = fold_zone(info)
    h_top = max((r[1] + r[3] for r in fold_rects), default=W_NORI + T)
    s_fold = tuck * s_fold_base
    pred = predict_layers(info, s_fold, a_fold)
    x_p = 0.5 * s_fold                      # half-span of the fold arc (the crease sits near here)
    hold_x0 = (s_fold + HOLD_MARGIN) if args.hold > 0 else 1e18   # 'second hand', off unless --hold
    anch = min(1.0, max(0.0, args.anchor))
    anch_x0 = (s_fold + ANCHOR_MARGIN) if anch > 0 else 1e18
    hold_damp = 1.0 - HOLD_RATE * max(args.hold, 0.0)
    # apex height of the fold arc. The second cap (0.8*x_p) keeps the arc slack even when the
    # fillings are tall: a taut half circle (b = x_p) tears the nori at --tuck 1.3 (README 5.4.2).
    b_ap = min(B_SLACK * x_p, h_top + B_CLEAR)
    y_edge0 = 0.5 * W_NORI
    th_end = math.pi - TH_END_MARGIN
    # ---- rolling fold (default). The old half-ellipse starts by lifting the edge STRAIGHT UP at x = 0:
    # at that instant the edge stands above the sheet, so the chord from the edge to any point of the
    # sheet still on the table is LONGER than the material between them. The sheet cannot reach, and the
    # only shape that satisfies the constraint is a hairpin at the very edge -- which then works as a
    # PULLEY, feeding the bed backwards through itself (measured: bed_drag 4-6 T, crease radius 0.3 T).
    # The rolling fold has no such deficit at any instant: it is the CYCLOID traced by a point on the rim
    # of a cylinder of radius r_fold rolling along the table, so at angle phi the sheet is wrapped on the
    # cylinder over exactly r_fold*phi of arc and lifts off at x = r_fold*phi -- material used = material
    # available, and the crease radius is r_fold everywhere.
    #   r_fold  >= s_fold/2pi   (or the edge cannot reach s_fold in one turn)
    #   r_fold  >= (h_top + FOLD_CLEAR)/2  (the loop must clear the stack it is folded over -- this is the
    #                                       "minimum bend radius from the height of the stack")
    r_fold = max(s_fold / (2.0 * math.pi), 0.5 * (h_top + FOLD_CLEAR))
    ph_end = 2.0 * math.pi
    for _ in range(60):                       # solve r_fold*(phi - sin phi) = s_fold, phi in (0, 2pi]
        f = r_fold * (ph_end - math.sin(ph_end)) - s_fold
        d = r_fold * (1.0 - math.cos(ph_end))
        if d < 1e-6:
            break
        ph_end = max(1e-3, min(2.0 * math.pi, ph_end - f / d))
    if args.fold == 'roll':
        th_end = ph_end
        b_ap = 2.0 * r_fold                   # apex of the fold (used for R_init and the JSON)
    # Fold arc of the grabbed edge (phases A and B):
    #     P(th) = ( x_p*(1 - cos th),  y_edge0 + b_ap*sin th ),  th: 0 -> th_end
    # a half ELLIPSE with semi-axes x_p (horizontal) and b_ap (vertical).  |P - (x_p, y_edge0)| <= x_p
    # for every th, so the sheet segment from the crease to the grabbed edge is never stretched; with
    # b_ap < x_p it is slack, and the sheet DRAPES over the fillings instead of sweeping them aside
    # (a taut half circle, b_ap = x_p, works for a bare sheet but flings a wide filling bundle).
    if args.fold == 'roll':
        def Pg(th):
            return (r_fold * (th - math.sin(th)), y_edge0 + r_fold * (1.0 - math.cos(th)))
        def dPg(th):
            return (r_fold * (1.0 - math.cos(th)), r_fold * math.sin(th))
        SP_MIN = 0.30 * r_fold                # |dP/dphi| -> 0 at the cusp phi = 0; clamp it, or the first
    else:                                     # step takes the edge anywhere
        def Pg(th):
            return (x_p * (1.0 - math.cos(th)), y_edge0 + b_ap * math.sin(th))
        def dPg(th):
            return (x_p * math.sin(th), b_ap * math.cos(th))
        SP_MIN = 1e-6
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
    t_press_max = T_PRESS_MAX_SQ if layout['press_shape'] == 'square' else T_PRESS_MAX
    t_total_max = t_fold + t_tuck + T_HOLD + t_rollmax + T_CLOSE + t_press_max
    n_steps_max = int(math.ceil(t_total_max / dt))
    R_init = 0.5 * (b_ap + h_top + 1.2) + 0.3

    print(f'grid {nx}x{ny} dx={dx:.4f} particles={n} grabbed={n_grab} hp={info["hp"]:.4f} nori rows={info["nori_rows"]} '
          f'dt={dt:.5f} cmax={cmax:.2f} v_c={v_c} v_g={v_g} s_fold={s_fold:.2f} x_p={x_p:.2f} b={b_ap:.2f} '
          f'R_init={R_init:.2f} t_fold={t_fold:.1f} t_rollmax={t_rollmax:.1f} steps<={n_steps_max}\n'
          f'fold zone: {[r[5] for r in fold_rects]} a_fold={a_fold:.2f} | predicted from area: '
          f'Rout={pred["Rout_pred_T"]} Rcore={pred["Rcore_pred_T"]} layers={pred["layers_predicted"]} '
          f'crossings={pred["crossings_predicted"]} | core+hollow: Rcore={pred["Rcore_hollow_T"]} '
          f'layers={pred["layers_predicted_core"]} crossings={pred["crossings_predicted_core"]}', flush=True)

    # rasterization calibration: the same disc rasterization applied to the INITIAL (undeformed) state.
    # rice_area_ratio is compared against this, not only against the true area (kin-mat).
    rice_map0 = raster_class_area(xs, cls, info['hp'], W_NORI / info['nori_rows'], args.window / 600.0, CLASS_RICE)

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
    ylift = 0.0; vly = 0.0                # height of the mat ring above the table (phase D only)
    pitch = 0.0                           # spiral pitch of the mat
    err_last = 1.0
    pitch_target = pitch_f * Y_BED
    rice_idx = np.nonzero(cls == CLASS_RICE)[0]
    n_rice = len(rice_idx)
    phase_marks = {'A': 0.0}
    nori_idx = np.nonzero(cls == CLASS_NORI)[0]
    n_nori = len(nori_idx)
    nori_mask = (cls == CLASS_NORI)
    fill_mask = (cls > CLASS_NORI)
    # --- wrinkle ("accordion") watch: sampled through the whole run, not just at the end, because the
    #     defect lives in phase B and is partly ironed out by the press.
    wr_hist = []
    wr_phase = {}
    nori_x0 = np.where(nori_col >= 0, (nori_col.astype(np.float64) + 0.5) * info['nori_dx'], -1.0)
    def wr_sample(ph, tt):
        w = wrinkle_metric(S['x'].to_numpy(), nori_row, nori_col, info['nori_rows'], nori_x0, s_fold)
        w['t'] = round(tt, 2); w['phase'] = ph
        wr_hist.append(w)
        cur = wr_phase.get(ph)
        if cur is None or (w['wrinkles'], w['wrinkle_amp_T']) > (cur['wrinkles'], cur['wrinkle_amp_T']):
            wr_phase[ph] = w
        return w
    step = 0
    while True:
        # ---------------- kinematic schedule ------------------------------------------------------
        grabbing = 1
        engaged = phase not in ('A', 'B')
        if phase == 'A' or phase == 'B':
            sp = math.hypot(*dPg(th_g))
            th_g = min(th_end, th_g + v_g * dt / max(sp, SP_MIN))
            d = dPg(th_g); sp = math.hypot(*d)
            sp = max(sp, SP_MIN)
            gom = 0.0
            gp = Pg(th_g); gc = Gc(th_g)
            gv_now = (v_g * d[0] / sp, v_g * d[1] / sp) if th_g < th_end else (0.0, 0.0)
            th_ab = math.pi if args.fold == 'roll' else 0.5 * math.pi
            if phase == 'A' and th_g >= th_ab:
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

        # ---------------- mat spiral pitch, ring lift and arc ---------------------------------------
        # The mat is a spiral: it touches the table at the contact point (th = 0) and, one turn back
        # (th -> 2pi, i.e. in FRONT of the roll), it is `pitch` higher -- exactly the thickness of the
        # sheet still lying ahead. That is what lets the bed pass UNDER the roll instead of being
        # bulldozed, and it replaces kin-grab's lifted circle (--lift) and its Y_FRONT_MIN clip.
        ylift_prev = ylift
        p_tgt = pitch_target if (engaged and phase not in ('D_close', 'D_press')) else 0.0
        y_tgt = LIFT_PRESS if phase == 'D_press' else 0.0
        pitch += max(-V_PITCH * dt, min(V_PITCH * dt, p_tgt - pitch))
        ylift += max(-V_PITCH * dt, min(V_PITCH * dt, y_tgt - ylift))
        vly = (ylift - ylift_prev) / dt
        unroll = 0.0
        if not engaged:
            th_lo, th_hi, vc_now, P_ref, shp = 1.0, 0.0, 0.0, P_ROLL_REF * args.press, 0
        elif phase in ('B', 'Btuck', 'Bhold'):
            frac = min(1.0, (t - t_engage) / T_WRAP)
            half = 0.5 + frac * (0.5 * PHI_ROLL - 0.5)
            th_lo = max(TH_BACK_MIN, math.pi - half)
            th_hi = min(2.0 * math.pi, math.pi + half)
            vc_now = 0.0
            P_ref = P_FOLD_FRAC * P_ROLL_REF * args.press
            shp = 0
            unroll = 1.0                       # the cap is still unrolling around the fold
        elif phase == 'C':
            th_lo, th_hi = 0.0, 2.0 * math.pi  # a full turn: the spiral itself clears the bed ahead
            vc_now = v_c
            P_ref = P_ROLL_REF * args.press
            shp = 0
        elif phase == 'D_close':
            f = min(1.0, t_phase / T_CLOSE)
            th_lo, th_hi = 0.0, 2.0 * math.pi
            vc_now = 0.0
            P_ref = (P_ROLL_REF + f * (P_PRESS_REF - P_ROLL_REF)) * args.press
            shp = 0
        else:  # D_press
            th_lo, th_hi = 0.0, 2.0 * math.pi
            vc_now = 0.0
            P_ref = P_PRESS_REF * args.press
            shp = shape

        # spin rate: the spiral touches the table at th = 0, so vb(0) = 0 with vspin = vc -- plain
        # rolling without slipping on the table, omega = vc / R, while the sheet ahead feeds in under
        # the spiral's lower-front branch.
        vspin = vc_now
        S['substep'](dt, xc, R, Rdot, ylift, vly, vc_now, vspin, th_lo, th_hi, pitch, unroll, shp, MU_MAT,
                     gc[0], gc[1], gv_now[0], gv_now[1], gom, R_FINGER, grabbing,
                     hold_x0, Y_BED + 0.35, hold_damp, anch_x0, anch)

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
            # The spiral pitch follows the ACTUAL height of what is still lying ahead, measured in a
            # band in front of the roll -- not a constant Y_BED switched by x (that was kin-mat's own
            # limitation, its README section 7). A filling standing at mid-sheet (layout 3) is taller
            # than the bed, and a spiral pitched for 1.12 ploughs into it and pushes a heap of rice
            # ahead of the roll all the way to the end of the sheet.
            rf = int(np.sum((xnp[rice_idx, 0] > xc + 0.8 * R) & (xnp[rice_idx, 1] < 2.0)))
            base = Y_BED if rf > 0.01 * n_rice else (W_NORI + 0.15)
            # the band starts OUTSIDE the roll's own footprint (1.05*R), or it measures the roll's
            # own flank and the pitch runs away (layout 1: turns 2.47 -> 3.44, conservation -0.034)
            # Only FILLING particles are measured, and only ahead of the roll's own footprint. Two
            # weaker versions of this rule were tried and rejected: measuring every particle in the
            # band (even starting at 1.05*R) picks up material the roll has already lifted and runs
            # the pitch up to PITCH_MAX on the BARE sheet -- layout 1 went turns 2.47 -> 3.5,
            # conservation 0.959 -> 0.933, Rout_max 3.66 -> 4.69. A filling is the only thing that
            # can actually stand proud of the bed in front of the roll.
            band = ((fill_mask) & (xnp[:, 0] > xc + PITCH_BAND0 * R) & (xnp[:, 0] < xc + PITCH_BAND1 * R)
                    & (xnp[:, 1] < PITCH_MAX + 1.0))
            h_ahead = float(np.percentile(xnp[band, 1], 98.0)) if band.sum() > 20 else 0.0
            tall = h_ahead + 0.3 if h_ahead > Y_BED + PITCH_PROUD else 0.0
            pitch_target = pitch_f * min(max(tall, base), PITCH_MAX)
            d = np.hypot(xnp[:, 0] - xc, xnp[:, 1] - (R + ylift))
            outs = d > R + 0.5
            ahead = float((xnp[outs, 0] - xc).max()) if outs.any() else -1e9
            # 0.9*R used to end phase C with ~3 T of bed still flat on the table: the gather then
            # closed the ring around that lobe and the press flattened it against the side of the roll
            # (layout 3: 2.7 % of particles outside the contour, a whole lobe in material_3.png).
            if ahead < C_EXIT_FRAC * R or xc >= x_end:
                phase = 'D_close'; t_phase = 0.0; phase_marks['D_close'] = t
                xc = float(xnp[:, 0].mean())
                R = gather_R(xnp, xc, R, 0, must=nori_mask)   # close the ring AROUND everything, flap included
                Rdot = 0.0
        if phase == 'D_close' and t_phase >= T_CLOSE:
            phase = 'D_press'; t_phase = 0.0; phase_marks['D_press'] = t
            if shape == 1:
                # the square press must be gathered for the SQUARE: a ring of radius R contains points
                # the square of half-side R does not (kin-grab layout 5 left a whole lobe outside).
                xnp = S['x'].to_numpy()
                xc = float(xnp[:, 0].mean())
                R = gather_R(xnp, xc, R, 1, must=nori_mask)
                Rdot = 0.0
        if phase == 'D_press' and t_phase >= T_PRESS and (abs(err_last) < 0.08 or t_phase >= t_press_max):
            phase_marks['end'] = t
            if args.frames:
                save_frame(S, cls, xc, R, th_lo, th_hi, shp, os.path.join(frames_dir, f'f{step:07d}_{phase}.png'), t, F_f, gp, grabbing, ylift=ylift)
            break

        if step % WR_EVERY == 0 or phase != last_phase:
            wr_sample(phase, t)
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
    wr_final = wrinkle_metric(xs_f, nori_row, nori_col, info['nori_rows'], nori_x0, s_fold)
    wr_final['t'] = round(t, 2); wr_final['phase'] = 'end'
    wr_hist.append(wr_final)
    wr_phase['end'] = wr_final
    wr_max = max(wr_hist, key=lambda w: (w['wrinkles'], w['wrinkle_amp_T']))
    wr_amp_max = max(wr_hist, key=lambda w: w['wrinkle_amp_T'])
    wr = dict(final=wr_final,
              wrinkles_max=int(wr_max['wrinkles']), wrinkles_max_phase=wr_max['phase'],
              wrinkles_max_t=wr_max['t'],
              wrinkle_amp_max_T=float(wr_amp_max['wrinkle_amp_T']), wrinkle_amp_max_phase=wr_amp_max['phase'],
              fold_radius_min_T=round(min(w['fold_radius_T'] for w in wr_hist if w['fold_radius_T'] > 0), 4),
              bed_drag_max_T=round(max(w['bed_drag_T'] for w in wr_hist), 3),
              by_phase={k: dict(wrinkles=v['wrinkles'], amp_T=v['wrinkle_amp_T'], kappa=v['wrinkle_kappa_max'],
                                r_fold_T=v['fold_radius_T'], drag_T=v['bed_drag_T'], t=v['t'])
                        for k, v in wr_phase.items()},
              samples=len(wr_hist), hist=[dict(t=w['t'], ph=w['phase'], w=w['wrinkles'],
                                               a=w['wrinkle_amp_T'], rf=w['fold_radius_T'],
                                               dg=w['bed_drag_T']) for w in wr_hist])
    print(f"wrinkles: max {wr['wrinkles_max']} at t={wr['wrinkles_max_t']} ({wr['wrinkles_max_phase']}), "
          f"amp max {wr['wrinkle_amp_max_T']:.3f} T ({wr['wrinkle_amp_max_phase']}), final {wr_final['wrinkles']}; "
          f"r_fold min {wr['fold_radius_min_T']:.3f} T, bed drag max {wr['bed_drag_max_T']:.2f} T",
          flush=True)

    # ---- outputs
    center = (xs_f[:, 0].mean(), xs_f[:, 1].mean())
    img, px = rasterize(xs_f, cls, info['hp'], W_NORI / info['nori_rows'], center, args.window, 600)
    np.save(os.path.join(args.out, f'material_{tag}.npy'), img)
    np.savez_compressed(os.path.join(args.out, f'particles_{tag}.npz'), x=xs_f, cls=cls,
                        nori_row=nori_row, nori_col=nori_col, J=Jp, grab=grab_np, vol=vol)
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
                 pitch=pitch_f, seed=args.seed, vol=vol, pred=pred, rice_map0=rice_map0, wr=wr,
                 mat=dict(v_pull=v_c, P_roll=P_ROLL_REF * args.press, P_press=P_PRESS_REF * args.press,
                          P_fold=P_FOLD_FRAC * P_ROLL_REF * args.press, mu_mat=MU_MAT, mu_table=MU_TABLE,
                          press_shape=layout['press_shape'], phi_roll=PHI_ROLL, pitch_frac=pitch_f,
                          pitch_final=round(pitch, 3), lift_press=LIFT_PRESS,
                          th_back_min=TH_BACK_MIN, y_bed=Y_BED, R_init=round(R_init, 3), xc_C0=round(xc_C0, 3),
                          xc_final=round(xc, 3), x_end=x_end),
                 grab=dict(width_T=GRAB_W, finger_R=R_FINGER, apex_b=round(b_ap, 3), particles=n_grab, v_grab=v_g, s_fold=round(s_fold, 3),
                           s_fold_base=round(s_fold_base, 3), semi_axis_x=round(x_p, 3), y_edge0=round(y_edge0, 3),
                           th_end=round(th_end, 3), y_tuck=round(Y_TUCK, 3), fold_zone=[r[5] for r in fold_rects],
                           a_fold_T2=round(a_fold, 3),
                           t_hold=T_HOLD, arc_len=round(len_arc, 3), h_top=round(h_top, 3), hold=args.hold,
                           path=args.fold, r_fold=round(r_fold, 3), phi_end=round(ph_end, 3),
                           anchor=anch, anchor_x0=round(anch_x0, 2) if anch > 0 else None, bend=args.bend),
                 phases=ph,
                 timing=dict(seconds=round(elapsed, 1), steps=step, dt=round(dt, 6), grid=[nx, ny], dx=round(dx, 5),
                             particles=n, hp=round(info['hp'], 5), t_end=round(t, 2)))
    met = compute_metrics(xs_f, vs_f, cls, Jp, nori_row, nori_col, info, layout, img, px, center, esc_total, extra)
    met['controller_log'] = log[-40:]
    met['wrinkle_hist'] = wr['hist']
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
    print(json.dumps({k: v for k, v in met.items() if k not in ('controller_log', 'fillings', 'wrinkle_hist')}, indent=1, default=_js))
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
