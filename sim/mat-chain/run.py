#!/usr/bin/env python
"""mat-chain: 2D MLS-MPM reference of rolling a sushi sheet with a REAL bamboo mat (makisu).

The kinematics is rebuilt around the correction of ../KINEMATICS.md (26.08.2026, 12:50): the mat is
not a rigid arc pressing from above, it is a LEAF that wraps together with the roll.

  * the mat is a LAGRANGIAN CHAIN of nodes (spacing MAT_DS) with rigid distance constraints and a
    minimum bend radius MAT_RBEND = 0.5 T (the bamboo sticks).  It lies UNDER the nori from the
    first frame, near edges flush, and the nori is dragged by it through a high-friction contact
    resolved on the same MPM grid (MU_MAT).  There is therefore NO free span of sheet at any
    instant -- the sheet is either on the table or on the mat -- and an accordion fold is
    impossible by construction: the sheet cannot bend tighter than the mat can.
  * only two things are prescribed: the path of the NEAR END of the chain (the thumbs) and, during
    the rolling phase, the tangential drive of the wrapped part (the palms).  The radial shape of
    the mat is NOT prescribed: every controlled node runs a pressure servo against the reaction it
    actually measures from the material, so the roll's radius is a result of contact.
  * the rest of the fingers are a second kinematic support on the first turn (--fingers): they hold
    the filling stack from above and stop it being extruded forward; released once the rice closes.

Phases
  lift     the thumbs carry the near end of the mat along an arch over the filling stack; the mat is
           paid out from the flat part as the chain goes taut (the lift-off point rolls forward)
  close    the near end is pressed down onto the far rice line -- rice meets rice
  hold     pause under pressure (--hold), the fingers let go
  roll     the wrap is driven tangentially at the rolling-without-slipping field of the roll, the
           lift-off point advances at --speed, and the mat's leading edge is progressively led out
           from under the roll (nodes retire at the near end, PHI_LEAD of wrap is kept)
  squeeze  no advance, the pressure ramps to P_press and the wrap is closed all the way round

Units: T = 1 rice thickness (~5 mm), rho_rice = 1, E_rice = 1, time unit = T / sqrt(E_rice/rho_rice).

CLI: python run.py --layout 1..6 --speed 1 --press 1 --tuck 1 --hold 0 --fingers 1
                   [--lift 1] [--fronty -1] [--grid 240] [--particles 16000] [--frames 12]
                   [--out DIR] [--tag ...] [--seed 1]
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
    # 6 is NOT one of the five control layouts of docs/simulation-research.md sec.5. It is a diagnostic for the
    # nori_turns target of KINEMATICS.md: a real futomaki carries ~15 cm2 of filling in cross-section, i.e.
    # ~60 T2 at T = 5 mm. With that much core the 38.7 T sheet closes in ~1.2 turns (see README sec.5.1).
    6: dict(name='futomaki-full-core', fillings=[fill('tamago', 1.5, 5.0, 4.4), fill('salmon', 7.0, 4.6, 4.0),
                                                 fill('avocado', 12.1, 4.4, 4.2, True)],
            press_shape='circle'),
    # 7 is the realistic futomaki that layout 6 is NOT. Layout 6 packs 58.8 T2 of filling against
    # 33.7 T2 of rice (64 % of the cross-section) and the nori tears: it has no rice cushion to lie on.
    # A real futomaki carries ~30 % filling with rice all around it. This is the layout the one-turn
    # model of the stand must be checked against -- see ../KINEMATICS.md, "Open discrepancy".
    7: dict(name='futomaki-real', fillings=[fill('tamago', 1.5, 2.4, 2.0), fill('salmon', 3.9, 2.0, 1.6),
                                            fill('cucumber', 5.5, 1.4, 1.4, True),
                                            fill('avocado', 6.8, 2.0, 1.1, True),
                                            fill('shrimp', 8.5, 2.0, 1.6)],
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

# ----------------------------------------------------------------------------- domain
X0 = -2.0
Y0, Y1 = -0.6, 12.6
X1 = 56.0                # overwritten in main() from the mat length, before the kernels compile
X_SHEET = 0.0            # near edge of the sheet (and of the mat)
X_END_EXTRA = 4.0
ROLL_OVERRUN = 2.6       # keep rolling this far past the end of the sheet, to wind the flap in

# ----------------------------------------------------------------------------- the mat (makisu)
# A real makisu is ~24 cm against a 19-21 cm nori sheet, and its sticks are 2-3 mm wide, i.e. ~0.5 T
# at T = 5 mm. Both numbers matter: the length decides how much flap has to be led out from under
# the roll, the stick width is the minimum bend radius that makes the accordion impossible.
MAT_LEN_FRAC = 1.25      # mat length as a multiple of the sheet length
MAT_DS = 0.25            # chain node spacing, T
MAT_RBEND = 0.5          # minimum bend radius of the mat, T
MAT_Y0 = -0.06           # the mat centreline lies just under the sheet (nori bottom is y = 0)
MAT_BAND_DX = 1.05       # contact half-thickness of the chain, in grid cells (it has to reach
                         # across the nori: the band is thinner than one cell otherwise and the mat
                         # simply slides out from under the sheet)
MU_MAT = 2.2             # mat/food friction: effectively no sliding while pressed
STICK_FRAC = 0.60        # fraction of the contact band inside which the sheet is STUCK to the mat
MAT_ITERS = 8            # Gauss-Seidel sweeps of the constraint projection per chain step
CHAIN_EVERY = 2          # substeps between chain updates
HAND_N = 1               # chain nodes held by the thumbs
K_FREE = 4               # nodes just behind the lift-off point left free of the pressure servo
HAND_OFF = 0.06          # the thumbs hold the mat this far outside the wrap radius, T
R_DEEP = 0.55            # a node closer than this fraction of the wrap radius may only move out
DRIVE_BAND = 0.45        # the palms only drive mat that is within this fraction of R of the wrap
CIRC_W = 0.9             # weight of the pull back onto the force-controlled circle
V_R_GLOBAL = 0.060       # rate the GLOBAL wrap radius follows the force error, T per time unit
R_TIGHT = 1.11           # the tightest a wound roll ever gets, as a multiple of the area radius
R_LOOSE = 1.35           # how much wider than the area radius the wrap may ever be (air in the roll)
VTAR = 0.55              # speed cap of the shape servo at --speed 1, T per time unit
X_C0 = 0.90              # where the contact point of the first turn starts, T
HAND_VMAX = 3.0          # speed cap of the thumb servo (it lags instead of tearing the mat)
HAND_YIELD = 0.02        # inverse mass of the held node relative to a free one
V_RADIAL = 0.075         # max radial (pressure-servo) speed of a controlled chain node
V_RADIAL_PRESS = 0.11    # ... during the final squeeze
TAU_F = 0.5              # time constant of the reaction filter, time units
F_SMOOTH = 2             # half-width of the along-chain smoothing of the measured reaction, nodes
PHI_LEAD = 6.10          # arc of the roll the mat is kept wrapped around during rolling, rad
                         # (contact -> back -> top -> front-top; beyond it the leading edge is led
                         #  out, which is what stops the mat rolling itself into the roll)
PHI_SQUEEZE = 6.10
FRONT_CLEAR = 0.35       # the leading end of the wrap clears the sheet lying ahead by this much, T       # ... and during the final squeeze (all the way round)
V_SQUEEZE = 0.30         # rate the extra wrap is paid out during the squeeze, T per time unit

# ----------------------------------------------------------------------------- hand / phases
V_GRAB_REF = 0.20        # speed of the thumbs along the arch at --speed 1
V_PULL_REF = 0.25        # speed of the lift-off point during rolling at --speed 1
V_TUCK_FRAC = 0.5        # downward speed in phase `close`, as a fraction of the thumb speed
P_FOLD_REF = 0.016       # mat pressure during the first turn at --press 1 (units of E_rice)
P_ROLL_REF = 0.028       # ... while rolling
P_PRESS_REF = 0.044      # ... during the final squeeze
T_HOLD_MIN = 6.0         # pause after the rice closes, time units, at --hold 0
T_HOLD_PER = 2.0         # ... plus this per unit of --hold
T_CLOSE_MAX = 26.0       # give up on the downward press of phase `close` after this
T_PRESS = 20.0           # minimum duration of the final squeeze
T_PRESS_MAX = 46.0       # ... and the cap (circle)
T_PRESS_MAX_SQ = 100.0   # ... and for the square press (layout 5)
Y_TUCK = 0.12 + 0.55     # target height of the near end at the end of phase `close`, T
FOLD_CLEAR = 0.8         # the arch clears the tallest filling of the fold zone by this much, T
S_FOLD_EMPTY = 5.0       # fold span for a sheet with no fillings near the edge, T
S_FOLD_MARGIN = 1.0      # fold span = (end of the fold zone) + this, T
FOLD_REACH = 5.0         # a filling joins the fold zone if it starts within this of the near edge
FOLD_GAP = 2.5           # ... or within this of the previous member
FOLD_CAP = 0.45          # the fold span never exceeds this fraction of the sheet
PAYOUT_TOL = 1.004       # the mat is paid out when the chain is stretched more than this
PAYOUT_MAX = 2.2         # ... and never past this multiple of the fold span, in phase `lift`
FING_CLEAR = 0.35        # the finger plate sits this far above the filling stack, T
FING_LEAD = 0.35         # ... and starts this far ahead of the nose of the fold, T

# ----------------------------------------------------------------------------- solver / world
GRAVITY = 0.01
MU_TABLE = 0.4
CFL = 0.3
CORNER_R = 0.6           # corner radius of the square press
TAIL_TOL = 0.3           # a particle further than this outside the fitted contour counts as outside
TAIL_FRAC = 0.002
BG_HOLE_T = 0.35
R_MIN, R_MAX = 0.8, 8.0
WRINKLE_MAX_OK = 0       # STRICT after the 12:50 correction: not one reversal is allowed
WRINKLE_AMP_OK = 0.3     # ... and the largest fold must stay under this, T
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
def build(nx, ny, n_part, n_mat):
    """MPM state + the Lagrangian mat chain, both on the same grid.

    One substep is seven kernels instead of one, because the chain has to see the grid and the grid
    has to see the chain:

        p2g  ->  grid_pre  ->  mat_gather  ->  mat_apply  ->  grid_post  ->  mat_react  ->  g2p

    `mat_gather` scatters, for every chain SEGMENT, the mat velocity and the mat normal onto the grid
    nodes lying inside its contact band (a segment only ever touches a 4x4 patch of cells, so this is
    cheap).  `mat_apply` resolves ONE separable Coulomb contact per grid node against the averaged
    mat frame.  `mat_react` walks the same segments again and gathers the impulse the mat had to
    spend back onto the chain nodes -- that reaction is what the pressure servo measures.
    """
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
    S['fn'] = ti.field(float, ())       # total normal force the mat spends on the food (this substep)
    S['esc'] = ti.field(ti.i32, ())
    # --- chain
    S['mp'] = ti.Vector.field(2, float, n_mat)     # node position
    S['mv'] = ti.Vector.field(2, float, n_mat)     # node velocity
    S['mq'] = ti.Vector.field(2, float, n_mat)     # predicted position (projection scratch)
    S['mn'] = ti.Vector.field(2, float, n_mat)     # node normal, pointing at the food
    S['mvk'] = ti.Vector.field(2, float, n_mat)    # prescribed part of the velocity (hand / drive)
    S['mwi'] = ti.field(float, n_mat)              # inverse mass (0 = held)
    S['mact'] = ti.field(ti.i32, n_mat)            # 1 = part of the live chain
    S['mctl'] = ti.field(ti.i32, n_mat)            # 1 = pressure-servo node (the wrap)
    S['mkin'] = ti.field(ti.i32, n_mat)            # 1 = velocity fully prescribed
    S['mfn'] = ti.field(float, n_mat)              # reaction accumulated since the last chain step
    S['mfF'] = ti.field(float, n_mat)              # ... time-filtered
    S['mfS'] = ti.field(float, n_mat)              # ... and smoothed along the chain
    S['mr'] = ti.field(float, n_mat)               # distance of the node from the wrap axis
    S['mstretch'] = ti.field(float, ())            # worst segment stretch of the last projection
    # --- grid scratch for the chain contact
    S['mw'] = ti.field(float, (nx, ny))
    S['mvg'] = ti.Vector.field(2, float, (nx, ny))
    S['mng'] = ti.Vector.field(2, float, (nx, ny))
    S['mimp'] = ti.Vector.field(2, float, (nx, ny))
    S['mdist'] = ti.field(float, (nx, ny))

    x, v, C, F, cls, vol, mass, J = (S[k] for k in ['x', 'v', 'C', 'F', 'cls', 'vol', 'mass', 'J'])
    mu, la, tauy, gv, gm, fn, esc = (S[k] for k in ['mu', 'la', 'tauy', 'gv', 'gm', 'fn', 'esc'])
    mp, mv, mq, mn, mvk, mwi = (S[k] for k in ['mp', 'mv', 'mq', 'mn', 'mvk', 'mwi'])
    mact, mctl, mkin, mfn, mfF, mfS = (S[k] for k in ['mact', 'mctl', 'mkin', 'mfn', 'mfF', 'mfS'])
    mr = S['mr']
    mw, mvg, mng, mimp, mstretch = (S[k] for k in ['mw', 'mvg', 'mng', 'mimp', 'mstretch'])
    mdist = S['mdist']
    dx = (Y1 - Y0) / ny
    inv_dx = 1.0 / dx

    @ti.kernel
    def init_particles(xs: ti.types.ndarray(), cl: ti.types.ndarray(), vo: ti.types.ndarray(),
                       rho: ti.types.ndarray()):
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
    def init_chain(ds: float, y0: float):
        for i in mp:
            mp[i] = [X_SHEET + i * ds, y0]
            mv[i] = [0.0, 0.0]
            mq[i] = mp[i]
            mn[i] = [0.0, 1.0]
            mvk[i] = [0.0, 0.0]
            mwi[i] = 1.0
            mact[i] = 1
            mctl[i] = 0
            mkin[i] = 0
            mfn[i] = 0.0
            mfF[i] = 0.0
            mfS[i] = 0.0
            mr[i] = 1.0

    # ------------------------------------------------------------------ P2G
    @ti.kernel
    def p2g(dt: float):
        for I in ti.grouped(gm):
            gv[I] = [0.0, 0.0]
            gm[I] = 0.0
            mw[I] = 0.0
            mvg[I] = [0.0, 0.0]
            mng[I] = [0.0, 0.0]
            mimp[I] = [0.0, 0.0]
            mdist[I] = 1e9
        fn[None] = 0.0
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
            tau = U @ ti.Matrix([[2.0 * mu_ * e0 + la_ * tr, 0.0],
                                 [0.0, 2.0 * mu_ * e1 + la_ * tr]]) @ U.transpose()
            affine = -dt * 4.0 * inv_dx * inv_dx * vol[p] * tau + mass[p] * C[p]
            mpp = mass[p]
            for i, j in ti.static(ti.ndrange(3, 3)):
                off = ti.Vector([i, j])
                dpos = (off.cast(float) - fx) * dx
                wt = w[i][0] * w[j][1]
                gv[base + off] += wt * (mpp * v[p] + affine @ dpos)
                gm[base + off] += wt * mpp

    @ti.kernel
    def grid_pre(dt: float):
        for I in ti.grouped(gm):
            if gm[I] > 0:
                vv = gv[I] / gm[I]
                vv[1] -= dt * GRAVITY
                gv[I] = vv

    # ------------------------------------------------------------------ chain -> grid
    @ti.kernel
    def mat_gather(band: float, i0: ti.i32, i1: ti.i32):
        for i in range(i0, i1 - 1):
            if mact[i] == 1 and mact[i + 1] == 1:
                a = mp[i]; b = mp[i + 1]
                e = b - a
                L = e.norm()
                if L > 1e-9:
                    tg = e / L
                    nn = ti.Vector([-tg[1], tg[0]])
                    gi0 = int((ti.min(a[0], b[0]) - band - X0) * inv_dx) - 1
                    gi1 = int((ti.max(a[0], b[0]) + band - X0) * inv_dx) + 2
                    gj0 = int((ti.min(a[1], b[1]) - band - Y0) * inv_dx) - 1
                    gj1 = int((ti.max(a[1], b[1]) + band - Y0) * inv_dx) + 2
                    for gi in range(ti.max(gi0, 0), ti.min(gi1, nx)):
                        for gj in range(ti.max(gj0, 0), ti.min(gj1, ny)):
                            if gm[gi, gj] > 0:
                                q = ti.Vector([X0 + gi * dx, Y0 + gj * dx])
                                sc = ti.max(0.0, ti.min(1.0, (q - a).dot(tg) / L))
                                dv = q - (a + sc * e)
                                dd = dv.norm()
                                if dd < band:
                                    wgt = 0.05 + 0.95 * (1.0 - dd / band)
                                    vseg = mv[i] * (1.0 - sc) + mv[i + 1] * sc
                                    ti.atomic_add(mw[gi, gj], wgt)
                                    ti.atomic_add(mvg[gi, gj][0], wgt * vseg[0])
                                    ti.atomic_add(mvg[gi, gj][1], wgt * vseg[1])
                                    ti.atomic_add(mng[gi, gj][0], wgt * nn[0])
                                    ti.atomic_add(mng[gi, gj][1], wgt * nn[1])
                                    ti.atomic_min(mdist[gi, gj], dd)

    @ti.kernel
    def mat_apply(dt: float, mu_mat: float, stick: float):
        for I in ti.grouped(gm):
            if gm[I] > 0 and mw[I] > 0:
                nn = mng[I]
                ln = nn.norm()
                if ln > 1e-9:
                    nn = nn / ln
                    vb = mvg[I] / mw[I]
                    v0 = gv[I]
                    vrel = v0 - vb
                    vn = vrel.dot(nn)
                    vnew = v0
                    hit = 0
                    # Two bands. Inside `stick` -- a layer just thick enough to cover the nori -- the
                    # sheet is GLUED to the mat tangentially (that is the wet rice sticking the nori to
                    # the makisu) but still free to lift off it normally. Without the glue a separable
                    # contact can only drag what is pressing on it, and at this gravity nothing is, so
                    # the mat slides out from under the sheet. Outside it, ordinary separable Coulomb.
                    if mdist[I] <= stick:
                        vnew = vb
                        hit = 1
                    elif vn < 0:
                        vt = vrel - vn * nn
                        vtn = vt.norm()
                        if vtn > 1e-12:
                            vt *= ti.max(0.0, 1.0 - mu_mat * (-vn) / vtn)
                        vnew = vb + vt
                        hit = 1
                    if hit == 1:
                        gv[I] = vnew
                        imp = gm[I] * (vnew - v0) / dt
                        mimp[I] = imp
                        fn[None] += imp.dot(nn)

    @ti.kernel
    def grid_post(fing: float, fx0: float, fx1: float, fy: float):
        for I in ti.grouped(gm):
            if gm[I] > 0:
                vv = gv[I]
                px = X0 + I[0] * dx
                py = Y0 + I[1] * dx
                # --- the chef's other fingers: they lie on top of the filling stack through the first
                #     turn so the stack is not extruded forward, and give way as the mat arrives.
                if fing > 0.0 and py > fy and px > fx0 and px < fx1:
                    if vv[1] > 0.0:
                        vv[1] *= (1.0 - fing)
                    vv[0] *= (1.0 - 0.5 * fing)
                if fing > 0.0 and py > fy and px >= fx1 and px < fx1 + 0.9 and vv[0] > 0.0:
                    vv[0] *= (1.0 - fing)
                # --- table
                if py <= 1e-6:
                    if vv[1] < 0:
                        vtn = ti.abs(vv[0])
                        if vtn > 1e-12:
                            vv[0] *= ti.max(0.0, 1.0 - MU_TABLE * (-vv[1]) / vtn)
                        vv[1] = 0.0
                # --- domain walls
                if I[0] < 3 and vv[0] < 0:
                    vv[0] = 0.0
                if I[0] > nx - 4 and vv[0] > 0:
                    vv[0] = 0.0
                if I[1] > ny - 4 and vv[1] > 0:
                    vv[1] = 0.0
                gv[I] = vv

    # ------------------------------------------------------------------ grid -> chain
    @ti.kernel
    def mat_react(band: float, i0: ti.i32, i1: ti.i32, dtsub: float):
        for i in range(i0, i1 - 1):
            if mact[i] == 1 and mact[i + 1] == 1:
                a = mp[i]; b = mp[i + 1]
                e = b - a
                L = e.norm()
                if L > 1e-9:
                    tg = e / L
                    nn = ti.Vector([-tg[1], tg[0]])
                    gi0 = int((ti.min(a[0], b[0]) - band - X0) * inv_dx) - 1
                    gi1 = int((ti.max(a[0], b[0]) + band - X0) * inv_dx) + 2
                    gj0 = int((ti.min(a[1], b[1]) - band - Y0) * inv_dx) - 1
                    gj1 = int((ti.max(a[1], b[1]) + band - Y0) * inv_dx) + 2
                    for gi in range(ti.max(gi0, 0), ti.min(gi1, nx)):
                        for gj in range(ti.max(gj0, 0), ti.min(gj1, ny)):
                            if mw[gi, gj] > 0:
                                q = ti.Vector([X0 + gi * dx, Y0 + gj * dx])
                                sc = ti.max(0.0, ti.min(1.0, (q - a).dot(tg) / L))
                                dv = q - (a + sc * e)
                                dd = dv.norm()
                                if dd < band:
                                    wgt = 0.05 + 0.95 * (1.0 - dd / band)
                                    share = wgt / mw[gi, gj]
                                    fnorm = mimp[gi, gj].dot(nn) * share * dtsub
                                    ti.atomic_add(mfn[i], fnorm * (1.0 - sc))
                                    ti.atomic_add(mfn[i + 1], fnorm * sc)


    # ------------------------------------------------------------------ who is who along the chain
    @ti.kernel
    def chain_control(i0: ti.i32, i1: ti.i32, ictl: ti.i32, ict: ti.i32, ds: float, dtc: float,
                      xL: float, xn: float, rn: float, xc: float, rr: float, w: float,
                      vtar: float, rmin: float):
        """Where the mat is asked to be, by ARC LENGTH from its lift-off point.

        Two shapes, blended by `w`:
        * the FOLD (w = 0) -- a flat-bottomed loop: the mat runs along the table back to the nose,
          turns through 180 deg at radius rn = (stack + bed)/2, and comes back forward over the top.
          rn is exactly the radius at which the rice of the returning branch meets the rice of the
          bottom branch, which is what a cook means by "bring the near rice line to the far one".
          Nothing here is a circle: a first turn drawn as a circle cannot hold a bed thicker than its
          own radius, and it ploughs the rice instead of folding it.
        * the ROLL (w = 1) -- the wrap of a cylinder of radius rr sitting on the table at xc, taken
          from the lift-off point backwards, i.e. the mat rolling up with the roll.

        The mat is only ASKED: it is servoed towards the target at a capped speed, the constraint
        projection then makes the result inextensible and no tighter than a bamboo stick can bend,
        and the pressure servo (chain_step) moves it radially off the target until the food pushes
        back with P. What comes out is not the target."""
        for i in range(i0, i1):
            mkin[i] = 0
            mwi[i] = 1.0
            mctl[i] = 0
            mvk[i] = ti.Vector([0.0, 0.0])
            if i >= i1 - 1:
                mkin[i] = 1
                mwi[i] = 0.0
            else:
                a = (ict - i) * ds
                # --- fold target
                b1 = ti.max(xL - xn, 0.0)
                nose = math.pi * rn
                fx = 0.0; fy = 0.0
                if a <= b1:
                    fx = xL - a; fy = 0.0
                elif a <= b1 + nose:
                    ps = (a - b1) / ti.max(rn, 1e-6)
                    fx = xn - rn * ti.sin(ps); fy = rn - rn * ti.cos(ps)
                else:
                    fx = xn + (a - b1 - nose); fy = 2.0 * rn
                # --- roll target
                ph = a / ti.max(rr, 1e-6)
                cx = xc - rr * ti.sin(ph)
                cy = rr - rr * ti.cos(ph)
                tgt = ti.Vector([(1.0 - w) * fx + w * cx, (1.0 - w) * fy + w * cy])
                dvv = (tgt - mp[i]) / ti.max(dtc, 1e-9)
                sp = dvv.norm()
                if sp > vtar:
                    dvv = dvv * (vtar / sp)
                mvk[i] = dvv
                if i < ictl:
                    rvec = ti.Vector([xc, rr]) - mp[i]
                    rl = rvec.norm()
                    mr[i] = rl
                    if rl > 1e-6:
                        mn[i] = rvec / rl
                        mctl[i] = 2 if rl < rmin else 1

    # ------------------------------------------------------------------ chain dynamics
    @ti.kernel
    def chain_step(dtc: float, vrad: float, pref: float, ds: float, chord: float,
                   yfloor: float, iters: ti.i32, i0: ti.i32, i1: ti.i32, alpha: float, rcirc: float):
        # 1. reaction: time filter + smoothing along the chain
        for i in range(i0, i1):
            f = mfn[i] / ti.max(dtc, 1e-9)
            mfF[i] += (f - mfF[i]) * alpha
            mfn[i] = 0.0
        for i in range(i0, i1):
            acc = 0.0
            cnt = 0.0
            for k in range(-F_SMOOTH, F_SMOOTH + 1):
                j = i + k
                if j >= i0 and j < i1:
                    acc += mfF[j]
                    cnt += 1.0
            mfS[i] = acc / ti.max(cnt, 1.0)
        # 2. velocities: prescribed part + the pressure servo along the node normal
        for i in range(i0, i1):
            vel = mvk[i]
            if mkin[i] == 0 and mctl[i] > 0:
                ft = pref * ds
                err = (mfS[i] - ft) / ti.max(ft, 1e-9)
                vn = -vrad * ti.max(-1.0, ti.min(1.0, err))     # mn points at the roll centre
                # ... plus a pull back onto the circle the GLOBAL force controller has settled at.
                # Without it a node that touches nothing (over a gap between fillings, or before the
                # bed has filled the first turn) walks inward for ever and the wrap collapses.
                dr = (rcirc - mr[i]) / (0.35 * ti.max(rcirc, 1e-6))
                vn += -vrad * CIRC_W * ti.max(-1.0, ti.min(1.0, dr))
                if mctl[i] == 2 and vn > 0.0:
                    vn = 0.0
                vel += vn * mn[i]
            mv[i] = vel
            mq[i] = mp[i] + dtc * vel
        # 3. constraint projection (serial: one forward sweep carries the hand all the way down)
        ti.loop_config(serialize=True)
        for _ in range(1):
            for _it in range(iters):
                for i in range(i0, i1 - 1):
                    dd = mq[i + 1] - mq[i]
                    L = dd.norm()
                    ws = mwi[i] + mwi[i + 1]
                    if L > 1e-9 and ws > 0.0:
                        corr = ((L - ds) / L) * dd
                        mq[i] += (mwi[i] / ws) * corr
                        mq[i + 1] -= (mwi[i + 1] / ws) * corr
                for k in range(i0, i1 - 1):
                    i = i0 + (i1 - 2 - k)
                    dd = mq[i + 1] - mq[i]
                    L = dd.norm()
                    ws = mwi[i] + mwi[i + 1]
                    if L > 1e-9 and ws > 0.0:
                        corr = ((L - ds) / L) * dd
                        mq[i] += (mwi[i] / ws) * corr
                        mq[i + 1] -= (mwi[i + 1] / ws) * corr
                # minimum bend radius: the chord over two segments may not fall below
                # 2*ds*cos(ds/(2*R_bend)) -- the mat cannot be creased tighter than a bamboo stick
                for i in range(i0 + 1, i1 - 1):
                    dd = mq[i + 1] - mq[i - 1]
                    L = dd.norm()
                    ws = mwi[i - 1] + mwi[i + 1]
                    if L < chord and L > 1e-9 and ws > 0.0:
                        corr = ((L - chord) / L) * dd
                        mq[i - 1] += (mwi[i - 1] / ws) * corr
                        mq[i + 1] -= (mwi[i + 1] / ws) * corr
                for i in range(i0, i1):
                    if mq[i][1] < yfloor and mwi[i] > 0.0:
                        mq[i][1] = yfloor
        # 4. commit + worst stretch + normals
        mstretch[None] = 1.0
        for i in range(i0, i1):
            mv[i] = (mq[i] - mp[i]) / dtc
            mp[i] = mq[i]
        for i in range(i0, i1 - 1):
            L = (mp[i + 1] - mp[i]).norm() / ds
            ti.atomic_max(mstretch[None], L)
        for i in range(i0, i1):
            a = mp[ti.max(i - 1, i0)]
            b = mp[ti.min(i + 1, i1 - 1)]
            e = b - a
            L = e.norm()
            if L > 1e-9:
                tg = e / L
                mn[i] = ti.Vector([-tg[1], tg[0]])

    # ------------------------------------------------------------------ G2P
    @ti.kernel
    def g2p(dt: float):
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
            lo0 = X0 + 2.0 * dx; hi0 = X1 - 3.0 * dx
            lo1 = Y0 + 2.0 * dx; hi1 = Y1 - 3.0 * dx
            if xn[0] < lo0 or xn[0] > hi0 or xn[1] < lo1 or xn[1] > hi1:
                esc[None] += 1
                xn[0] = ti.min(ti.max(xn[0], lo0), hi0)
                xn[1] = ti.min(ti.max(xn[1], lo1), hi1)
            x[p] = xn

    S.update(init_particles=init_particles, init_chain=init_chain, p2g=p2g, grid_pre=grid_pre,
             chain_control=chain_control,
             mat_gather=mat_gather, mat_apply=mat_apply, grid_post=grid_post, mat_react=mat_react,
             chain_step=chain_step, g2p=g2p, dx=dx, ti=ti, nx=nx, ny=ny)
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
# bending into one arc (../KINEMATICS.md, "accordion"). Measured on the MIDLINE of the nori band:
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
    out = dict(wrinkles=0, wrinkles_mat=0, wrinkle_amp_T=0.0, wrinkle_kappa_max=0.0, wrinkle_reversals=0,
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
    # The same count with the threshold the MAT sets rather than the bed: a reversal is a fold of the
    # wrapper only if the sheet has been bent tighter than a bamboo stick can bend (1/MAT_RBEND).
    # Anything gentler is the roll's own curvature, which the old threshold 1/(T+w) also caught.
    sgm = np.sign(kap[ok & (np.abs(kap) >= 1.0 / MAT_RBEND)])
    if len(sgm) > 1:
        out['wrinkles_mat'] = int(np.sum(sgm[1:] != sgm[:-1]))
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
        fingers=extra['grab']['fingers'], lift_arch=extra['grab']['lift'], hold=extra['grab']['hold'],
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
        wrinkles_mat=int(extra['wr']['final']['wrinkles_mat']),
        wrinkles_mat_max=int(extra['wr']['wrinkles_mat_max']),
        wrinkles_max=int(extra['wr']['wrinkles_max']), wrinkles_max_phase=extra['wr']['wrinkles_max_phase'],
        wrinkle_amp_T=float(extra['wr']['final']['wrinkle_amp_T']),
        wrinkle_amp_max_T=float(extra['wr']['wrinkle_amp_max_T']),
        wrinkle_amp_max_phase=extra['wr']['wrinkle_amp_max_phase'],
        wrinkle_kappa_max=float(extra['wr']['final']['wrinkle_kappa_max']),
        fold_radius_min_T=float(extra['wr']['fold_radius_min_T']),
        bed_drag_max_T=float(extra['wr']['bed_drag_max_T']),
        wrinkles_by_phase=extra['wr']['by_phase'],
        wrinkle_ok=bool(extra['wr']['wrinkles_max'] <= WRINKLE_MAX_OK and
                        extra['wr']['wrinkle_amp_max_T'] < WRINKLE_AMP_OK),
        wrinkle_thresholds=[WRINKLE_MAX_OK, WRINKLE_AMP_OK],
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
    global X1
    ap = argparse.ArgumentParser()
    ap.add_argument('--layout', type=int, default=1)
    ap.add_argument('--speed', type=float, default=1.0, help='hand speed: the arch in phase lift and the roll in phase roll')
    ap.add_argument('--press', type=float, default=1.0, help='pressure of the mat (all three phases scale together)')
    ap.add_argument('--tuck', type=float, default=1.0, help='how far the near end is carried over the stack (0.6..1.3)')
    ap.add_argument('--hold', type=float, default=0.0, help='extra pause after the rice closes, time units per unit')
    ap.add_argument('--fingers', type=float, default=1.0,
                    help='the chefs other fingers on the filling stack during the first turn (1 = hold, 0 = none)')
    ap.add_argument('--lift', type=float, default=1.0, help='height of the thumb arch (0 = the mat never leaves the table)')
    ap.add_argument('--fronty', type=float, default=-1.0,
                    help='wrap kept during rolling: phi_lead = 3 + fronty rad; < 0 uses the default %.2f' % PHI_LEAD)
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--grid', type=int, default=240)
    ap.add_argument('--particles', type=int, default=16000)
    ap.add_argument('--frames', type=int, default=12)
    ap.add_argument('--window', type=float, default=12.0)
    ap.add_argument('--out', type=str, default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out'))
    ap.add_argument('--tag', type=str, default='')
    # accepted for compatibility with the older command lines of ../lab and ../reference (no effect here)
    ap.add_argument('--pitch', type=float, default=1.0, help=argparse.SUPPRESS)
    ap.add_argument('--anchor', type=float, default=1.0, help=argparse.SUPPRESS)
    ap.add_argument('--bend', type=float, default=0.0, help=argparse.SUPPRESS)
    ap.add_argument('--fold', type=str, default='roll', help=argparse.SUPPRESS)
    args = ap.parse_args()

    layout = LAYOUTS[args.layout]
    os.makedirs(args.out, exist_ok=True)
    tag = f'{args.layout}{args.tag}'
    tuck = min(1.3, max(0.6, args.tuck))
    fing = min(1.0, max(0.0, args.fingers))
    liftf = min(1.5, max(0.0, args.lift))
    phi_lead = PHI_LEAD if args.fronty < 0 else min(6.2, max(2.0, 3.0 + args.fronty))

    # ---- the mat sets the domain: it is 25 % longer than the sheet and the flat part has to fit
    L_MAT = MAT_LEN_FRAC * L_SHEET
    ds = MAT_DS
    n_mat = int(round(L_MAT / ds)) + 1
    X1 = X_SHEET + L_MAT + 8.0

    aspect = (X1 - X0) / (Y1 - Y0)
    ny = int(round(args.grid / math.sqrt(aspect)))
    nx = int(round(ny * aspect))
    xs, cls, vol, nori_row, nori_col, info = sample_layout(layout, args.particles, args.seed)
    n = len(cls)
    x0p = xs[:, 0].copy()

    # ---- fold zone: the fillings that end up in the core, and the span of the first turn
    s_fold_base, fold_rects, a_fold = fold_zone(info)
    h_top = max((r[1] + r[3] for r in fold_rects), default=W_NORI + T)
    s_fold = tuck * s_fold_base
    pred = predict_layers(info, s_fold, a_fold)
    # The first turn is the mat rolling ITSELF up: a virtual cylinder whose contact point walks
    # forward along the table with the mat wrapped on it from the near edge, so the sheet lying on the
    # mat is picked up and wound in. The thumbs hold the near edge, so their path is the point of the
    # wrap at angle phi_h -- a cycloid whose RADIUS is not prescribed anywhere: R_ctl is read back off
    # the chain, and the chain sits where the food stops it.
    #   phi = 0 at the contact, pi/2 up the back, pi on top, 3pi/2 in front, 2pi back down at the table
    # `close` is reached when the near edge of the rice has come all the way round onto the far rice
    # line -- rice meets rice. --tuck moves that point (0.6 undertuck, 1.3 past it).
    # ---- the first turn is a FLAT-BOTTOMED LOOP, not a circle.
    # The mat lies flat under the sheet; the thumbs lift its near end, carry it back over the nose and
    # forward again over the filling stack until the near rice line lands on the far rice line. The
    # nose radius is fixed by that meeting: the returning branch carries its own bed of thickness h
    # under it, so 2*rn - h = h_top, i.e. rn = (h_top + h)/2. Anything tighter and the two beds
    # interpenetrate; anything looser and the rice does not meet.
    h_bed = T + W_NORI
    # rn is the radius at which the rice of the returning branch meets the rice of the bottom branch:
    # 2*rn - h = h_top. Opening it further (the "r >= 2h" no-compression bound) was tried and is worse,
    # not better: a wider nose makes the near end travel further before it closes, and the bed is left
    # behind on the table instead of being turned over (rice outside the contour 8 % -> 24 %).
    r_nose = max(MAT_RBEND, 0.5 * (h_top + h_bed) * (0.65 + 0.35 * liftf))
    # The near end travels in two stages, which is how a cook actually does it:
    #   1. LIFT   -- the nose opens from nothing to r_nose while the near end rides straight up over
    #                it (x_e = pi*r: a nose of radius r needs pi*r of mat folded over it, no less);
    #   2. CLOSE  -- the nose stays at r_nose and the near end is carried forward to the far rice line.
    x_e_end = max(s_fold, math.pi * r_nose + 0.6)
    s_lift = math.hypot(math.pi, 2.0) * r_nose   # path length of stage 1
    x_p = 0.5 * s_fold
    b_ap = 2.0 * r_nose
    arc_len = s_lift + max(0.0, x_e_end - math.pi * r_nose)
    R_FOLD = r_nose

    S = build(nx, ny, n, n_mat)
    dx = S['dx']
    band = MAT_BAND_DX * dx
    stick_d = STICK_FRAC * band
    chord = 2.0 * ds * math.cos(min(1.4, 0.5 * ds / MAT_RBEND))
    rho = np.zeros(N_CLASS, np.float32); mu = np.zeros(N_CLASS, np.float32)
    la = np.zeros(N_CLASS, np.float32); ty = np.zeros(N_CLASS, np.float32)
    cmax = 0.0
    present = set(int(c) for c in np.unique(cls))
    for c, name in MAT_OF_CLASS.items():
        E, nu, tau_y, r = MATERIALS[name]
        mu[c] = E / (2 * (1 + nu)); la[c] = E * nu / ((1 + nu) * (1 - 2 * nu)); ty[c] = tau_y; rho[c] = r
        if c in present:
            cmax = max(cmax, math.sqrt((la[c] + 2 * mu[c]) / r))
    S['mu'].from_numpy(mu); S['la'].from_numpy(la); S['tauy'].from_numpy(ty)
    S['init_particles'](xs.astype(np.float32), cls.astype(np.int32), vol.astype(np.float32), rho)
    S['init_chain'](ds, MAT_Y0)
    dt = CFL * dx / cmax
    dtc = CHAIN_EVERY * dt
    alpha = min(1.0, dtc / TAU_F)
    v_g = V_GRAB_REF * args.speed
    hvmax = max(0.5, 4.0 * v_g)
    v_c = V_PULL_REF * args.speed
    x_end = X_SHEET + L_SHEET + X_END_EXTRA

    t_lift = arc_len / v_g
    t_hold = T_HOLD_MIN + T_HOLD_PER * max(args.hold, 0.0)
    t_press_max = T_PRESS_MAX_SQ if layout['press_shape'] == 'square' else T_PRESS_MAX
    t_total_max = t_lift + T_CLOSE_MAX + t_hold + (L_SHEET + 2.0) / v_c + t_press_max + 40.0
    n_steps_max = int(math.ceil(t_total_max / dt))

    print(f'grid {nx}x{ny} dx={dx:.4f} particles={n} hp={info["hp"]:.4f} nori rows={info["nori_rows"]} '
          f'dt={dt:.5f} cmax={cmax:.2f} | mat: L={L_MAT:.1f} nodes={n_mat} ds={ds} band={band:.3f} '
          f'chord_min={chord:.4f} (R_bend={MAT_RBEND}) stick={stick_d:.3f} phi_lead={phi_lead:.2f}\n'
          f'fold: s_fold={s_fold:.2f} r_nose={r_nose:.2f} x_e_end={x_e_end:.2f} arc={arc_len:.2f} '
          f'h_top={h_top:.2f} zone={[r[5] for r in fold_rects]} a_fold={a_fold:.2f} | predicted: '
          f'Rout={pred["Rout_pred_T"]} layers={pred["layers_predicted"]} crossings={pred["crossings_predicted"]} '
          f'| core: layers={pred["layers_predicted_core"]} crossings={pred["crossings_predicted_core"]}\n'
          f'v_g={v_g} v_c={v_c} t_hold={t_hold} steps<={n_steps_max}', flush=True)

    rice_map0 = raster_class_area(xs, cls, info['hp'], W_NORI / info['nori_rows'], args.window / 600.0, CLASS_RICE)

    # ---------------- state ----------------------------------------------------------------------
    frames_dir = os.path.join(args.out, f'frames_{tag}')
    if args.frames:
        os.makedirs(frames_dir, exist_ok=True)
        for f in os.listdir(frames_dir):
            if f.endswith('.png'):
                os.remove(os.path.join(frames_dir, f))
    snap_every = max(1, n_steps_max // max(args.frames, 1))
    t0 = time.time()
    t = 0.0
    step = 0
    phase = 'lift'; last_phase = 'lift'; t_phase = 0.0
    x_e = 0.0                       # x of the near end of the mat (the thumbs)
    fold_s = 0.0                    # path length the thumbs have travelled
    r_n = MAT_RBEND                 # current nose radius of the fold
    x_n = 0.0                       # x of the nose
    w_roll = 0.0                    # 0 = fold shape, 1 = rolling wrap
    phi_h = 0.0                     # wrap angle actually subtended by the live chain
    i_ct = K_FREE + 3               # mat picked up so far, in nodes: x_lift = i_ct * ds
    x_c = i_ct * ds                 # the wrap is tangent to the table at the mat's lift-off point
    R_ctl = R_FOLD
    Rdot = 0.0
    y_c = R_ctl
    i_lo = 0
    hand = [x_c, MAT_Y0]
    F_f = 0.0
    err_last = 1.0
    log = []
    phase_marks = {'lift': 0.0}
    nori_x0 = np.where(nori_col >= 0, (nori_col.astype(np.float64) + 0.5) * info['nori_dx'], -1.0)
    volnp = np.asarray(vol, np.float64)
    wr_hist = []; wr_phase = {}
    s_fold_actual = s_fold
    mp_view = S['mp']

    def wr_sample(ph, tt):
        w = wrinkle_metric(S['x'].to_numpy(), nori_row, nori_col, info['nori_rows'], nori_x0, s_fold)
        w['t'] = round(tt, 2); w['phase'] = ph
        wr_hist.append(w)
        cur = wr_phase.get(ph)
        if cur is None or (w['wrinkles'], w['wrinkle_amp_T']) > (cur['wrinkles'], cur['wrinkle_amp_T']):
            wr_phase[ph] = w
        return w

    def snap(ph):
        if args.frames:
            save_frame(S, cls, i_lo, min(i_ct + 2, n_mat), os.path.join(frames_dir, f'f{step:07d}_{ph}.png'),
                       t, F_f, hand, phase in ('lift', 'close', 'hold'), (x_c, y_c), R_ctl)

    # ---- how big the roll must be once `x` of the sheet has been picked up. This is pure area
    #      bookkeeping (KINEMATICS.md: "the layer count follows from area conservation"), it knows
    #      nothing about the kinematics, and it is only used to place the AXIS of the wrap -- where
    #      each mat node actually sits on that axis is decided by the pressure servo.
    _ord = np.argsort(x0p)
    _xs_sorted = x0p[_ord]
    _cum = np.concatenate([[0.0], np.cumsum(volnp[_ord])])

    def radius_for(xc):
        a = float(_cum[int(np.searchsorted(_xs_sorted, xc))])
        return max(R_MIN, min(R_MAX, math.sqrt(max(a, 1e-6) / math.pi)))

    while True:
        # ---------------- phase schedule ---------------------------------------------------------
        vc_now = 0.0
        hand_on = 1
        if phase == 'lift':
            fold_s += v_g * dt
            pref = P_FOLD_REF * args.press
            if fold_s >= s_lift:
                phase = 'close'; t_phase = 0.0; phase_marks['close'] = t
        elif phase == 'close':
            fold_s += v_g * dt
            f = min(1.0, t_phase / 10.0)
            pref = (P_FOLD_REF + f * (P_ROLL_REF - P_FOLD_REF)) * args.press
            if x_e >= x_e_end - 1e-6:
                phase = 'hold'; t_phase = 0.0; phase_marks['hold'] = t
                s_fold_actual = i_ct * ds
        elif phase == 'hold':
            pref = P_ROLL_REF * args.press * 1.25
            w_roll = min(1.0, t_phase / max(t_hold * 0.8, 1e-6))
            if t_phase >= t_hold:
                phase = 'roll'; t_phase = 0.0; phase_marks['roll'] = t
                w_roll = 1.0
                x_c = i_ct * ds
        elif phase == 'roll':
            hand_on = 0
            x_c += v_c * dt
            vc_now = v_c
            pref = P_ROLL_REF * args.press
            # the wrap has to stay tangent under the roll: if the roll has run ahead of the nominal
            # contact, the contact is where the roll actually is, and the mat under it is consumed
            if step % 200 == 0:
                rolled = x0p < x_c - 0.5
                if rolled.sum() > 60:
                    x_c = max(x_c, float(S['x'].to_numpy()[rolled, 0].mean()))
            if x_c >= L_SHEET + ROLL_OVERRUN or x_c >= x_end:
                phase = 'squeeze'; t_phase = 0.0; phase_marks['squeeze'] = t
        else:  # squeeze
            hand_on = 0
            f = min(1.0, t_phase / 8.0)
            pref = (P_ROLL_REF + f * (P_PRESS_REF - P_ROLL_REF)) * args.press
            # "squeeze from every side": nothing moves any more, the wrap kept from the rolling phase
            # (PHI_LEAD rad of it) is simply pressed harder and evenly all the way round.

        # ---- fold geometry: the nose opens, then the near end is carried forward over the stack
        if phase in ('lift', 'close', 'hold'):
            if fold_s < s_lift:
                r_n = max(0.12, r_nose * fold_s / max(s_lift, 1e-6))
                x_e = math.pi * r_n
            else:
                r_n = r_nose
                x_e = min(x_e_end, math.pi * r_nose + (fold_s - s_lift))
            x_n = 0.5 * (x_e + math.pi * r_n)
            i_ct = max(i_ct, min(n_mat - 3, int((x_n + 0.45) / ds)))

        # ---------------- who is who along the chain ---------------------------------------------
        if phase == 'roll':
            i_ct = max(i_ct, min(n_mat - 3, int(x_c / ds)))
            # How far round the mat may be kept is not a constant: its leading end must stay CLEAR of
            # the sheet still lying ahead, or it comes down on the bed and shovels it along (that was
            # 11 % of the rice pushed off the end of the table). The wrap at angle phi sits at height
            # R(1 - cos phi), so phi <= 2 pi - acos(1 - (h_ahead + margin)/R). This is the chain's own
            # version of the Archimedean pitch ../reference used for the same purpose.
            h_ahead = (T + W_NORI) if x_c < L_SHEET - L_FLAP else W_NORI
            for _r in info['rects']:
                if _r[0] > x_c and _r[0] < x_c + 2.5 * R_ctl:
                    h_ahead = max(h_ahead, _r[1] + _r[3])
            if x_c > L_SHEET:
                h_ahead = 0.0
            cc = max(-1.0, min(1.0, 1.0 - (h_ahead + FRONT_CLEAR) / max(R_ctl, 1e-6)))
            phi_eff = min(phi_lead, 2.0 * math.pi - math.acos(cc))
            i_lo = max(i_lo, i_ct - int(phi_eff * R_ctl / ds))
        i_ct = min(i_ct, n_mat - 3)
        i_lo = max(0, min(i_lo, i_ct - K_FREE - 6))
        i1 = min(i_ct + 2, n_mat)
        ictl = max(i_lo + 2, i_ct - K_FREE)
        # the wrap angle is NOT integrated -- it is what the arc of mat between the near end and the
        # lift-off point subtends on the radius the servo has settled at. A fatter roll therefore
        # needs a longer first turn, which is exactly what a stuffed futomaki does.
        x_lift = i_ct * ds
        if phase in ('lift', 'close', 'hold'):
            x_c = x_lift
        y_c = R_ctl
        phi_h = min(2.0 * math.pi + 0.6, (i_ct - i_lo) * ds / max(R_ctl, 1e-6))
        vrad = V_RADIAL_PRESS if phase == 'squeeze' else V_RADIAL
        hand = [x_e, 2.0 * r_n] if hand_on else [x_c, R_ctl]

        if step % CHAIN_EVERY == 0:
            S['chain_control'](i_lo, i1, ictl, i_ct, ds, dtc, x_lift, x_n, r_n,
                               x_c, R_ctl, w_roll, VTAR * args.speed, R_DEEP * R_ctl)
            S['chain_step'](dtc, vrad, pref, ds, chord, MAT_Y0, MAT_ITERS, i_lo, i1, alpha, R_ctl)
        # ---------------- one MPM substep --------------------------------------------------------
        S['p2g'](dt)
        S['grid_pre'](dt)
        S['mat_gather'](band, i_lo, i1)
        S['mat_apply'](dt, MU_MAT, stick_d)
        # the chef's other fingers: they hold whatever stands proud of the bed (the filling stack, or
        # on a bare sheet the crest the fold pushes up) from being extruded forward, and they give way
        # as the near end of the mat arrives over them
        fing_on = fing if phase in ('lift', 'close') else 0.0
        # they sit AHEAD of the arriving mat (behind it the stack has already turned over and must be
        # free to rise -- holding it there leaves the near fillings lying on the table, which is what
        # layout 4 did: cucumber and tamago never made it into the roll)
        fx0 = max(0.25, x_n + FING_LEAD)
        fx1 = s_fold + 0.8 if fing_on > 0 else -1e9
        S['grid_post'](fing_on, fx0, fx1, max(h_top - 0.9, W_NORI + 0.85 * T) + FING_CLEAR)
        S['mat_react'](band, i_lo, i1, dt)
        S['g2p'](dt)

        fnow = S['fn'][None]
        F_f += (fnow - F_f) * min(1.0, dt / TAU_F)
        t += dt; t_phase += dt

        # ---------------- global radius of the wrap ----------------------------------------------
        # Exactly the reference's controller, but it now sets the circle the CHAIN is servoed onto
        # instead of a rigid arc: the force the mat actually spends against the food decides how
        # tight the roll ends up, and area conservation is the floor it can never go under.
        arc_ctl = max((i_ct - i_lo) * ds, 1e-6)
        F_t = pref * arc_ctl
        err_last = (F_f - F_t) / max(F_t, 1e-9)
        if step % 8 == 0:
            # the area radius assumes a roll with no air in it at all; a wound one always has
            # some, so it is the floor times R_TIGHT, not the floor itself
            r_floor = max(R_MIN, R_TIGHT * radius_for(max(x_c, i_ct * ds)))
            if phase in ('lift', 'close', 'hold'):
                # through the first turn the force is the crease, not the wrap: the radius follows
                # area conservation only, or the controller chases its own fold
                R_ctl = max(R_FOLD, r_floor)
            else:
                # ... and area conservation is also the CEILING, within the air a real roll carries:
                # a wrap wider than that is not a loose roll, it is a hollow one
                Rdot = V_R_GLOBAL * max(-1.0, min(1.0, err_last))
                R_ctl = min(min(R_MAX, (R_LOOSE / R_TIGHT) * r_floor), max(r_floor, R_ctl + Rdot * dt * 8.0))
        if phase == 'squeeze' and t_phase >= T_PRESS and (abs(err_last) < 0.10 or t_phase >= t_press_max):
            phase_marks['end'] = t
            snap('squeeze')
            break

        if step % 400 == 0:
            wr_sample(phase, t)
            log.append(dict(t=round(t, 2), ph=phase, ilo=i_lo, ict=i_ct, xc=round(x_c, 2),
                            phi=round(phi_h, 2), R=round(R_ctl, 3), F=round(F_f, 4), Ft=round(F_t, 4),
                            str=round(float(S['mstretch'][None]), 4)))
        if phase != last_phase:
            wr_sample(phase, t)
            _xp = S['x'].to_numpy(); _g = 0.0
            for _r in range(info['nori_rows']):
                _m = nori_row == _r; _o = np.argsort(nori_col[_m]); _p = _xp[_m][_o]
                _g = max(_g, float(np.linalg.norm(np.diff(_p, axis=0), axis=1).max()))
            print(f'  -> {phase} at t={t:.1f}  i_lo={i_lo} i_ct={i_ct} x_c={x_c:.1f} phi={phi_h:.2f} '
                  f'R={R_ctl:.2f} nori max gap={_g:.3f} T', flush=True)
            snap(phase)
        last_phase = phase
        if args.frames and step % snap_every == 0:
            snap(phase)
        if step % 2000 == 0:
            print(f'  step {step} t={t:.1f} [{phase}] i=[{i_lo},{i_ct}] xc={x_c:.2f} R={R_ctl:.3f} '
                  f'F={F_f:.3f}/{F_t:.3f} str={float(S["mstretch"][None]):.4f} esc={S["esc"][None]} '
                  f'{time.time() - t0:.0f}s', flush=True)
        step += 1
        if step > n_steps_max:
            print('  ! step budget exhausted', flush=True)
            phase_marks['end'] = t
            snap(phase)
            break

    S['ti'].sync()
    elapsed = time.time() - t0
    esc_total = int(S['esc'][None])
    xs_f = S['x'].to_numpy(); vs_f = S['v'].to_numpy(); Jp = S['J'].to_numpy()
    mat_np = S['mp'].to_numpy()
    wr_final = wrinkle_metric(xs_f, nori_row, nori_col, info['nori_rows'], nori_x0, s_fold)
    wr_final['t'] = round(t, 2); wr_final['phase'] = 'end'
    wr_hist.append(wr_final); wr_phase['end'] = wr_final
    wr_max = max(wr_hist, key=lambda w: (w['wrinkles'], w['wrinkle_amp_T']))
    wr_amp_max = max(wr_hist, key=lambda w: w['wrinkle_amp_T'])
    wr = dict(final=wr_final,
              wrinkles_max=int(wr_max['wrinkles']), wrinkles_max_phase=wr_max['phase'],
              wrinkles_mat_max=int(max(w['wrinkles_mat'] for w in wr_hist)),
              wrinkles_max_t=wr_max['t'],
              wrinkle_amp_max_T=float(wr_amp_max['wrinkle_amp_T']), wrinkle_amp_max_phase=wr_amp_max['phase'],
              fold_radius_min_T=round(min(w['fold_radius_T'] for w in wr_hist if w['fold_radius_T'] > 0), 4),
              bed_drag_max_T=round(max(w['bed_drag_T'] for w in wr_hist), 3),
              by_phase={k: dict(wrinkles=v['wrinkles'], amp_T=v['wrinkle_amp_T'], kappa=v['wrinkle_kappa_max'],
                                mat=v['wrinkles_mat'], r_fold_T=v['fold_radius_T'],
                                drag_T=v['bed_drag_T'], t=v['t'])
                        for k, v in wr_phase.items()},
              samples=len(wr_hist), hist=[dict(t=w['t'], ph=w['phase'], w=w['wrinkles'], a=w['wrinkle_amp_T'],
                                               rf=w['fold_radius_T'], dg=w['bed_drag_T']) for w in wr_hist])
    print(f"wrinkles: max {wr['wrinkles_max']} at t={wr['wrinkles_max_t']} ({wr['wrinkles_max_phase']}), "
          f"amp max {wr['wrinkle_amp_max_T']:.3f} T, final {wr_final['wrinkles']}; r_fold min "
          f"{wr['fold_radius_min_T']:.3f} T, bed drag max {wr['bed_drag_max_T']:.2f} T", flush=True)

    center = (xs_f[:, 0].mean(), xs_f[:, 1].mean())
    img, px = rasterize(xs_f, cls, info['hp'], W_NORI / info['nori_rows'], center, args.window, 600)
    np.save(os.path.join(args.out, f'material_{tag}.npy'), img)
    np.savez_compressed(os.path.join(args.out, f'particles_{tag}.npz'), x=xs_f, cls=cls,
                        nori_row=nori_row, nori_col=nori_col, J=Jp, vol=vol, mat=mat_np)
    from PIL import Image
    rgb = np.zeros((600, 600, 3), np.uint8)
    for c, col in COLORS.items():
        rgb[img == c] = col
    Image.fromarray(rgb).save(os.path.join(args.out, f'material_{tag}.png'))
    global vol_of
    def vol_of(cl, c, inf):
        return float(np.sum(vol[cl == c]))
    pred_act = predict_layers(info, s_fold_actual, a_fold)
    ph = {k: round(v, 2) for k, v in phase_marks.items()}
    seg = np.linalg.norm(np.diff(mat_np[i_lo:i1], axis=0), axis=1) if i1 - i_lo > 2 else np.array([ds])
    extra = dict(layout=args.layout, speed=args.speed, press=args.press, tuck=tuck, R=R_ctl,
                 window_T=args.window, pitch=args.pitch, seed=args.seed, vol=vol, pred=pred,
                 rice_map0=rice_map0, wr=wr,
                 mat=dict(kind='lagrangian-chain', length_T=round(L_MAT, 2), nodes=n_mat, ds=ds,
                          R_bend_T=MAT_RBEND, chord_min_T=round(chord, 4), band_T=round(band, 4), stick_T=round(stick_d, 4),
                          mu_mat=MU_MAT, mu_table=MU_TABLE, phi_lead=round(phi_lead, 3),
                          phi_squeeze=PHI_SQUEEZE, wrap_T=round(float((i_ct - i_lo) * ds), 2),
                          wrap_rad=round(float((i_ct - i_lo) * ds / max(R_ctl, 1e-6)), 3),
                          retired_nodes=int(i_lo), retired_T=round(i_lo * ds, 2),
                          pickup_T=round(i_ct * ds, 2), seg_max_T=round(float(seg.max()), 4),
                          seg_min_T=round(float(seg.min()), 4), stretch_max=round(float(seg.max() / ds), 4),
                          P_fold=P_FOLD_REF * args.press, P_roll=P_ROLL_REF * args.press,
                          P_press=P_PRESS_REF * args.press, press_shape=layout['press_shape'],
                          roll_centre=[round(x_c, 3), round(y_c, 3)], R_wrap_T=round(R_ctl, 3),
                          phi_hand_end=round(phi_h, 3), r_nose=round(r_nose, 3)),
                 grab=dict(hand='thumbs on the near end of the MAT', nodes=HAND_N, v_grab=v_g,
                           r_nose=round(r_nose, 3), loop_h=round(b_ap, 3), x_e_end=round(x_e_end, 3),
                           arc_len=round(arc_len, 3), s_fold=round(s_fold, 3), R_fold=round(R_FOLD, 3),
                           s_fold_base=round(s_fold_base, 3), s_fold_actual=round(s_fold_actual, 3),
                           y_tuck=Y_TUCK, h_top=round(h_top, 3),
                           fold_zone=[r[5] for r in fold_rects], a_fold_T2=round(a_fold, 3),
                           fingers=fing, lift=liftf, hold=args.hold, t_hold=t_hold),
                 phases=ph,
                 timing=dict(seconds=round(elapsed, 1), steps=step, dt=round(dt, 6), grid=[nx, ny],
                             dx=round(dx, 5), particles=n, hp=round(info['hp'], 5), t_end=round(t, 2)))
    met = compute_metrics(xs_f, vs_f, cls, Jp, nori_row, nori_col, info, layout, img, px, center, esc_total, extra)
    met['layers_predicted_actual'] = pred_act['layers_predicted']
    met['crossings_predicted_actual'] = pred_act['crossings_predicted']
    met['Rout_pred_actual_T'] = pred_act['Rout_pred_T']
    met['turns_match_formula_actual'] = bool(abs(met['nori_turns'] - pred_act['crossings_predicted']) <= 0.25)
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
    save_frame(S, cls, i_lo, i1, os.path.join(args.out, f'final_{tag}.png'), t, F_f, hand, False,
               (x_c, y_c), R_ctl, zoom=(center, args.window))
    print(json.dumps({k: v for k, v in met.items() if k not in ('controller_log', 'fillings', 'wrinkle_hist')},
                     indent=1, default=_js))
    print(f'done in {elapsed:.1f}s  ({step} steps, t_end={t:.1f})')


def save_frame(S, cls, i_lo, i1, path, t, F, hand=None, show_hand=False, c=None, R=0.0, zoom=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    xs = S['x'].to_numpy()
    mp = S['mp'].to_numpy()
    fig, ax = plt.subplots(figsize=(12, 3.6) if zoom is None else (6, 6), dpi=100)
    colors = np.array([COLORS[cc] for cc in range(N_CLASS)]) / 255.0
    colors[CLASS_NORI] = np.array([0.30, 0.85, 0.55])
    ax.scatter(xs[:, 0], xs[:, 1], c=colors[cls], s=1.2 if zoom is None else 4, linewidths=0)
    # the mat: the live chain in red, the part still lying flat ahead in dim grey, the leading edge
    # that has been led out from under the roll as a short stub
    ax.plot(mp[i1 - 1:, 0], mp[i1 - 1:, 1], '-', color='#6a6a72', lw=0.8)
    ax.plot(mp[i_lo:i1, 0], mp[i_lo:i1, 1], '-', color='#ff5a3c', lw=1.4)
    if i_lo > 0:
        k = min(i_lo, 24)
        d = np.array([0.30, 0.95])
        stub = mp[i_lo] + np.outer(np.arange(1, k + 1)[::-1] * MAT_DS, d)
        ax.plot(stub[:, 0], stub[:, 1], '-', color='#ff5a3c', lw=1.0, alpha=0.45)
    if hand is not None and show_hand:
        ax.plot([hand[0]], [hand[1]], marker='o', ms=5, mfc='none', mec='#ff4fd8', mew=1.5)
    if c is not None and R > 0 and zoom is None:
        th = np.linspace(0, 2 * math.pi, 120)
        ax.plot(c[0] + R * np.cos(th), c[1] + R * np.sin(th), ':', color='#7fb0ff', lw=0.8)
    ax.axhline(0, color='k', lw=0.5)
    if zoom is None:
        ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
    else:
        (cx, cy), wdt = zoom
        ax.set_xlim(cx - wdt / 2, cx + wdt / 2); ax.set_ylim(cy - wdt / 2, cy + wdt / 2)
    ax.set_aspect('equal'); ax.set_facecolor('#1c1c20')
    ax.set_title(f't={t:.1f} mat=[{i_lo},{i1}] F={F:.3f}', fontsize=8)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)


if __name__ == '__main__':
    main()
