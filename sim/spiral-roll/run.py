#!/usr/bin/env python
"""spiral-seed: 2D MLS-MPM reference of rolling a sheet (cross-section, plane strain).

Two families of base live here:

  * SUSHI (layouts 1-5) -- unchanged from ../kin-grab: nori + rice, a bare flap at the far end and a
    four-phase chef kinematics that starts with a kinematic GRAB of the near edge (phases A, B below).

  * SPIRAL (layouts 6 = roll cake, 7 = lavash roll) -- no grab and no curl phase at all.  The tight
    start is ASSUMED instead of simulated: at sampling time the first `seed_turns` turns of the sheet
    are laid out geometrically as a small spiral with the right material order (wrapper outside each
    turn, spread inside), sitting on the table exactly where the flat run of the sheet begins, and the
    state machine starts directly at the rolling phase C.  That is the whole experiment of this
    attempt: does the tight start have to be simulated, or can it be seeded?

  phase A  edge lift   -- (sushi only) the near-edge nori particles (x < GRAB_W) are a kinematic GRAB ("fingers"):
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

Units: T = 1 SPREAD thickness of the base being rolled (rice ~5 mm, cream ~5 mm, cream cheese ~5 mm),
rho_spread = 1, E_spread = 1, time unit = T / sqrt(E/rho).

CLI: python run.py --layout 1..7 [--speed ..] [--press ..] [--tuck ..] [--seedturns 1.5]
                   [--grid 240] [--particles 18000] [--frames 10] [--out DIR] [--tag ...]
"""
import argparse, json, math, os, sys, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import fold                                  # одно определение посадки края на всю лабораторию

# ----------------------------------------------------------------------------- bases and layouts
# T = 1 is the SPREAD thickness of whatever base is being rolled (rice / cream / cream cheese).
# Every geometric property of a base (sheet length, wrapper thickness, spread thickness, material
# names, colours, domain, target roll size) lives in its layout dict -- nothing about the sheet is a
# module-level constant any more.  bind_layout() copies the run's base into the few globals the
# taichi kernel and the metric helpers need to see.
T = 1.0
KIND_IDS = ['salmon', 'cucumber', 'tamago', 'avocado', 'shrimp',          # sushi (classes 3..7)
            'strawberry', 'kiwi', 'banana', 'jam',                        # roll cake (8..11)
            'cheese', 'tomato', 'dill']                                   # lavash    (12..14)
CLASS_BG, CLASS_SPREAD, CLASS_WRAP = 0, 1, 2
CLASS_RICE, CLASS_NORI = CLASS_SPREAD, CLASS_WRAP        # sushi-era aliases, kept so nothing breaks
CLASS_OF_KIND = {k: 3 + i for i, k in enumerate(KIND_IDS)}
N_CLASS = 3 + len(KIND_IDS)
COLORS = {0: (28, 28, 32), 1: (246, 240, 224), 2: (26, 62, 44), 3: (250, 118, 88), 4: (86, 178, 62),
          5: (250, 208, 66), 6: (152, 202, 92), 7: (250, 168, 150),
          8: (226, 58, 82), 9: (138, 196, 74), 10: (246, 226, 130), 11: (176, 44, 74),
          12: (250, 224, 146), 13: (230, 80, 62), 14: (66, 132, 78)}
SPREAD_COLOR = {'rice': (246, 240, 224), 'cream': (253, 248, 238), 'cream-cheese': (247, 244, 232)}
WRAP_COLOR = {'nori': (26, 62, 44), 'sponge': (222, 168, 96), 'lavash': (231, 210, 168)}

def fill(kind, u, w, h, round_=False, stack=False, y_off=0.0):
    """u = position along the sheet (T), w x h = footprint, round = ellipse, stack = sit on the
    previous filling, y_off = extra lift above the spread (used to put a piece on top of the dill)."""
    return dict(kind=kind, u=u, w=w, h=h, round=round_, stack=stack, y_off=y_off)

def base_sushi(**kw):
    """maki base: nori 0.12 T, rice 1 T, whole sheet 38.7 T with a 5 T bare flap, folded (tuck)."""
    d = dict(kind='sushi', spiral=False, L_sheet=38.7, L_flap=5.0, w_wrap=0.12, T_spread=1.0,
             wrap_mat='nori', spread_mat='rice', press_shape='circle', lift=1.0,
             window=12.0, y_top=12.6, x_pad=9.3, R_max=8.0, speed=1.0, press=1.0)
    d.update(kw)
    return d

def base_spiral(**kw):
    """roll-cake / lavash base: no tuck, no flap, both ends of the wrapper taper to nothing, the
    first turns are pre-curled at sampling time and the phase machine starts at C."""
    d = dict(kind='spiral', spiral=True, L_flap=0.0, press_shape='circle',
             taper_lead=3.0,      # wrapper ramps to full thickness over this length at the START tip
             taper_tail=3.0,      # ... and back to nothing over this length at the END
             taper_floor=0.30,    # thinnest the tapered wrapper gets (fraction of w_wrap); below ~1 grid
                                  # cell the tip is smeared by the solver, so it is not taken to zero
             spread_lead=1.6,     # spread starts this far from the start tip (the pressed tip is bare)
             spread_tail=2.6,     # ... and stops this far from the end (last turn: wrapper on wrapper)
             spread_ramp=2.6,     # length of the spread's ramp-in / ramp-out
             seed_turns=1.5,      # pre-curled turns placed geometrically at sampling time
             seed_r_core=0.30,    # mid-surface radius of the innermost pre-curled turn, T
             seed_relax=0.8,      # length over which the coil's curvature is ramped back to zero, so
                                  # the sheet leaves the junction straight (the peel front)
             mu_table=0.4,        # spiral bases may want a slippier board than a sushi mat
             lift=0.0,            # a seeded coil is wound FROM THE SHEET TIP, so it stands on the TABLE at
                                  # the peel front, not on top of the incoming sheet (that is the sushi
                                  # case, where the tuck puts the core on the sheet).  See README.
             grid=240, particles=18000,
             speed=1.0, press=1.0)
    d.update(kw)
    return d

LAYOUTS = {
    1: base_sushi(name='empty', fillings=[]),
    2: base_sushi(name='tamago-edge', fillings=[fill('tamago', 1.5, 2.4, 2.0)]),
    3: base_sushi(name='salmon-mid', fillings=[fill('salmon', 38.7 * 0.5 - 1.0, 2.0, 1.6)]),
    4: base_sushi(name='four-edge', fillings=[fill('cucumber', 1.5, 1.4, 1.4, True), fill('tamago', 3.2, 2.4, 2.0),
                                              fill('salmon', 5.9, 2.0, 1.6), fill('avocado', 8.2, 2.0, 1.1, True)]),
    5: base_sushi(name='overflow-square', press_shape='square',
                  fillings=[fill('tamago', 1.5, 2.4, 2.0), fill('salmon', 1.7, 2.0, 1.6, stack=True),
                            fill('cucumber', 2.0, 1.4, 1.4, True, stack=True)]),
    # --- spiral bases -------------------------------------------------------------------------
    # Geometry is taken FROM THE STAND (docs: sim/KINEMATICS.md, "Геометрия баз"), in units of the
    # base's own spread thickness (T = 1):
    #   roll cake  w = 0.52, L = 40.2  -> stand turns 2.74, Rout 4.42 T  (fillings not modelled there)
    #   lavash     w = 0.44, L = 107.6 -> stand turns 4.71, Rout 7.03 T
    # The tapers are deliberately SHORT here.  A long taper removes area exactly where the radius is
    # small, and turns are the integral of ds/(2*pi*r): 3 T of taper on each end pushed the roll-cake
    # spiral from 2.7 to 3.3 turns.  With a short taper the area lost at the ends and the area added by
    # the fillings nearly cancel, so the reference lands on the stand's own turn count.
    6: base_spiral(name='roll-cake', L_sheet=40.2, w_wrap=0.52, T_spread=1.0,
                   wrap_mat='sponge', spread_mat='cream',
                   taper_lead=1.5, taper_tail=1.0, taper_floor=0.55,
                   spread_lead=0.6, spread_tail=1.0, spread_ramp=2.5,
                   seed_turns=1.5, seed_r_core=0.45,
                   window=13.0, y_top=13.0, x_pad=10.0, R_max=8.0, speed=1.0, press=0.60,
                   grid=240, particles=18000,
                   fillings=[fill('strawberry', 7.0, 3.2, 3.0, True), fill('jam', 13.5, 4.4, 0.44),
                             fill('kiwi', 19.0, 3.7, 3.2, True), fill('banana', 28.0, 3.0, 2.5, True)]),
    # 7 -- lavash roll: 107.6 T of flatbread, cream cheese 1 T, a dill line running almost the whole
    #      sheet (it doubles as a turn marker on the cut) and three pieces sitting on top of it.
    7: base_spiral(name='lavash-roll', L_sheet=107.6, w_wrap=0.44, T_spread=1.0,
                   wrap_mat='lavash', spread_mat='cream-cheese',
                   taper_lead=1.5, taper_tail=1.2, taper_floor=0.60,
                   spread_lead=0.6, spread_tail=1.2, spread_ramp=2.5,
                   seed_turns=1.5, seed_r_core=0.45,
                   window=19.0, y_top=19.0, x_pad=14.0, R_max=11.0, speed=1.0, press=0.50,
                   grid=360, particles=26000,
                   fillings=[fill('dill', 6.0, 95.0, 0.14),
                             fill('salmon', 12.0, 4.4, 3.6, False, False, 0.14),
                             fill('cheese', 38.0, 4.9, 2.7, False, False, 0.14),
                             fill('tomato', 68.0, 5.8, 2.2, True, False, 0.14)]),
    # --- 8, 9: the ROLL CAKE re-cut to the sourced thicknesses (26.08.2026 evening) ------------
    # Layouts 1-7 above are UNTOUCHED and still carry the pre-correction numbers (sushi w = 0.12,
    # L = 38.7; roll cake w = 0.52, L = 40.2).  The stand's own cake base (index.html, BASES.cake)
    # says T = 1.0, w = 1.7, turns = 2.5, from which the stand DERIVES L = 56.94 U.  Sources for the
    # wrapper: Bakels -- sponge batter spread 6-7 mm, baked sheet 8-10 mm; 1.7 U = 8.5 mm.
    #     pitch P = T + w = 2.70 U = 13.5 mm      (old base: 1.52 U)
    #     Rout   = sqrt(L*P/pi + r0^2) = 6.997 U = 35.0 mm at r0 = 0.25   (old base: 4.417 U)
    #     turns  = (Rout - r0)/P = 2.499                                   (old base: 2.742)
    #
    # 8 is the layout the CHECK FORMULA actually describes: a uniform sheet, no taper (taper_floor = 1),
    # spread from tip to tip, no fillings.  Anything it misses is kinematics, not modelling choice.
    # 9 is 8 plus the four fillings of layout 6, moved along the sheet by 56.9/40.2 = 1.415 so they sit
    # at the same fraction of the sheet, and with the base's own tapers back on.
    #
    # seed_r_core: 0.45 (layout 6) is GEOMETRICALLY IMPOSSIBLE at this thickness.  The seed map places
    # a point of the sheet at distance d from the mid-surface with area jacobian 1 + kappa*d, so the
    # inner face (d = -H/2) needs r_core > H/2 = 1.35 U just to stay on its own side of the axis; at
    # r_core = 0.45 the jacobian there is -2.0 and the inner half of the first turn is mapped through
    # the centre and out the far side.  1.8 U leaves jac_inner = 0.25.
    8: base_spiral(name='roll26-empty', L_sheet=56.9, w_wrap=1.70, T_spread=1.0,
                   wrap_mat='sponge', spread_mat='cream',
                   taper_lead=0.1, taper_tail=0.1, taper_floor=1.0,
                   spread_lead=0.0, spread_tail=0.0, spread_ramp=0.4,
                   seed_turns=0.75, seed_r_core=1.8,
                   window=20.0, y_top=20.0, x_pad=16.0, R_max=12.0, speed=1.0, press=0.60,
                   grid=300, particles=26000,
                   fillings=[]),
    9: base_spiral(name='roll26', L_sheet=56.9, w_wrap=1.70, T_spread=1.0,
                   wrap_mat='sponge', spread_mat='cream',
                   taper_lead=2.0, taper_tail=1.4, taper_floor=0.55,
                   spread_lead=0.6, spread_tail=1.4, spread_ramp=2.5,
                   seed_turns=0.75, seed_r_core=1.8,
                   window=20.0, y_top=20.0, x_pad=16.0, R_max=12.0, speed=1.0, press=0.60,
                   grid=300, particles=26000,
                   fillings=[fill('strawberry', 9.9, 3.2, 3.0, True), fill('jam', 19.1, 4.4, 0.44),
                             fill('kiwi', 26.9, 3.7, 3.2, True), fill('banana', 39.6, 3.0, 2.5, True)]),
    # 10 = the CONTROL for 8: identical knobs (uniform wrapper, spread tip to tip, no fillings,
    # seed_turns 0.75) on the OLD, pre-correction cake geometry.  Its seed core keeps the old 0.45,
    # which at H = 1.52 still leaves jac_inner = 1 - 0.76/0.45 < 0 -- so it gets 1.0, the smallest
    # core that is geometrically legal there (jac_inner = 0.24, the same margin layout 8 has at 1.8).
    # Anything 8 does that 10 does not is caused by the thickness, not by the seeded kinematics.
    10: base_spiral(name='roll-old-empty', L_sheet=40.2, w_wrap=0.52, T_spread=1.0,
                    wrap_mat='sponge', spread_mat='cream',
                    taper_lead=0.1, taper_tail=0.1, taper_floor=1.0,
                    spread_lead=0.0, spread_tail=0.0, spread_ramp=0.4,
                    seed_turns=0.75, seed_r_core=1.0,
                    window=13.0, y_top=13.0, x_pad=10.0, R_max=8.0, speed=1.0, press=0.60,
                    grid=300, particles=26000,
                    fillings=[]),
    # 11 = layout 9's geometry with the STAND'S OWN cake ingredients instead of the ones layout 6
    # invented.  index.html, ING: strawberry 5.0 x 1.0 ('ломтик'), kiwi 9.0 x 1.2 ('ломтик'),
    # banana 6.4 x 6.4 ('кружок', round), jam 3.5 x 0.35 ('паста').  They are SLICES, not the chunks
    # layout 6 carries -- except the banana, which at 6.4 U = 32 mm across is nearly the whole core of
    # a roll whose outer radius is 7 U.
    11: base_spiral(name='roll26-stand-fillings', L_sheet=56.9, w_wrap=1.70, T_spread=1.0,
                    wrap_mat='sponge', spread_mat='cream',
                    taper_lead=2.0, taper_tail=1.4, taper_floor=0.55,
                    spread_lead=0.6, spread_tail=1.4, spread_ramp=2.5,
                    seed_turns=0.75, seed_r_core=1.8,
                    window=20.0, y_top=20.0, x_pad=16.0, R_max=12.0, speed=1.0, press=0.60,
                    grid=300, particles=26000,
                    fillings=[fill('jam', 6.0, 3.5, 0.35), fill('strawberry', 14.0, 5.0, 1.0, True),
                              fill('kiwi', 24.0, 9.0, 1.2, True), fill('banana', 40.0, 6.4, 6.4, True)]),
}

# ----------------------------------------------------------------------------- materials
# name: (E, nu, tau_y (shear yield; 1e9 = elastic), rho)
MATERIALS = {
    'rice':         (1.0, 0.35, 0.03, 1.0),
    'nori':         (25.0, 0.30, 1e9, 2.0),
    'salmon':       (3.0, 0.40, 0.15, 1.0),
    'cucumber':     (15.0, 0.30, 1e9, 1.0),
    'tamago':       (10.0, 0.35, 1e9, 1.0),
    'avocado':      (4.0, 0.40, 0.15, 1.0),
    'shrimp':       (6.0, 0.35, 1e9, 1.0),
    # roll cake: sponge is thicker and much softer than nori, cream is softer than rice and yields early
    # Wrappers are ELASTIC membranes (tau_y = 1e9), exactly as nori already was.  "Softer than nori"
    # is a statement about stiffness (E 6 and 12 vs nori's 25), not about plastic flow: with a finite
    # shear yield the wrapper necks under the mat's tangential drag -- the soft spread cannot carry
    # any shear (tau_y ~ 0.02), so the whole drag goes through the band -- and it separates into arcs.
    # That was the "torn" verdict in runs 6e*/6f*; with tau_y = 1e9 the band survives and creases
    # instead (bending is free for a thin band in MPM regardless of the yield).
    'sponge':       (6.0, 0.35, 2.00, 0.90),
    'cream':        (0.6, 0.40, 0.012, 0.95),
    'strawberry':   (3.0, 0.40, 0.15, 1.0),
    'kiwi':         (2.4, 0.40, 0.12, 1.0),
    'banana':       (1.2, 0.40, 0.05, 0.95),
    'jam':          (0.4, 0.42, 0.008, 1.1),
    # lavash: thin flatbread, stiffer than sponge but far softer than nori; cream cheese is stiff paste
    'lavash':       (12.0, 0.32, 3.00, 1.30),
    'cream-cheese': (0.9, 0.40, 0.030, 1.0),
    'cheese':       (8.0, 0.35, 0.40, 1.05),
    'tomato':       (2.0, 0.42, 0.06, 1.0),
    'dill':         (1.5, 0.38, 0.05, 0.7),
}
MAT_OF_CLASS = {1: 'rice', 2: 'nori'}          # rebound per run by bind_layout()
for k, c in CLASS_OF_KIND.items():
    MAT_OF_CLASS[c] = k

# --- per-run bindings of the current base (set by bind_layout, read by the kernel and the metrics)
L_SHEET = 38.7
L_FLAP = 5.0
W_NORI = 0.12

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
# ⚠ S_FOLD_EMPTY и S_FOLD_MARGIN сняты 31.08.2026 (#113). Здесь была ТРЕТЬЯ редакция правила
# сгиба — без потолка и без кластеризации, просто max по всем прямоугольникам, — и она уже
# расходилась и с mat-sdf, и с judge.py. Определение теперь одно: sim/fold.py.

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
T_SPINUP = 14.0          # spiral bases: the mat's speed (and grip) are ramped in over this time at the
                         # start of phase C.  The seeded coil starts AT REST while the mat's surface is
                         # driven at v_c from step one; without the ramp the whole shear of spinning the
                         # coil up is dumped on the junction between the pre-curled part and the flat
                         # sheet, and the wrapper ruptures exactly there (gaps 1.2-1.5 T at s = L_seed).
T_LIFT = 8.0             # time for the mat circle to rise onto the sheet at the start of phase C
V_LIFT = 0.08            # max rate of change of the mat lift
V_RADIAL_PRESS = 0.12    # radial speed of the mat controller during the final pressing
TH_BACK_MIN = 0.15       # the mat's back end stays this far (in angle) off the table
Y_BED = W_NORI + T       # thickness of the incoming sheet: the roll rolls without slip on ITS top
Y_FRONT_MIN = max(0.30, W_NORI + T + 0.15)   # lower FRONT end of the arc never goes below this (T)
                                             # KINEMATICS.md asks for >= 0.3 T; we also keep it above the
                                             # incoming rice bed (top = W_NORI + T) so the mat cannot scrape it.
T_WRAP = 12.0            # time for the phase-B cap to widen to the full rolling arc
T_CLOSE = 6.0            # phase-D closing of the arc to 360 deg
T_PRESS = 8.0            # minimum duration of the final pressing
T_PRESS_MAX = 46.0       # give up on force equilibrium after this
# A geometric CEILING on R during phase C (R <= k*sqrt(A_wound/pi), i.e. "the mat may not trail the
# growing roll") was tried TWICE and rejected both times -- see README, "Что пробовали и отбросили".
# Naive (k = 1.05..1.20) it crushes the seed on step one, because a pre-curled coil of 1-1.5 turns is a
# C and not a disc: its outer radius is legitimately wider than the dense radius of the sheet it holds.
# Held off the seed (k = 1.06, floor at R_seed_outer + 0.25) it still makes things worse -- the mat then
# forces the sheet into the roll faster than the peel front can take it, and the wrapper shreds
# (lavash: max gap 1.5 -> 4.5 T, 9 -> 11 map components, tail outside 0.00004 -> 0.018).
R_GEOM_FRAC = 0.99       # spiral bases: the mat radius during rolling may not go below this fraction of
                         # the radius that area conservation demands for the sheet wound so far.
                         # 0.99 in radius = 0.98 in area: the mat squeezes the AIR between turns out first and only then
                         # starts compressing the spread, which is what keeps conservation above 0.97.
GRAVITY = 0.01
MU_TABLE = 0.4           # rebound per run by bind_layout() from the base's 'mu_table'
MU_MAT = 2.0             # effectively sticky while pressed against the mat
CFL = 0.3
CORNER_R = 0.6           # corner radius of the square press
TAIL_TOL = 0.3           # a particle further than this outside the fitted contour counts as "tail outside"
TAIL_FRAC = 0.002        # fraction of particles above which tail_outside becomes True

# ----------------------------------------------------------------------------- per-run binding
def bind_layout(layout):
    """Copy the base's geometry into the globals the kernel / metrics read, and the base's materials
    into the spread and wrapper classes.  Nothing else in this file may assume sushi numbers."""
    global L_SHEET, L_FLAP, W_NORI, X0, X1, Y0, Y1, Y_BED, Y_FRONT_MIN, R_MAX, MU_TABLE
    L_SHEET = layout['L_sheet']
    L_FLAP = layout['L_flap']
    W_NORI = layout['w_wrap']
    Y_BED = W_NORI + layout['T_spread']
    Y_FRONT_MIN = max(0.30, Y_BED + 0.15)
    X0, X1 = -2.0, L_SHEET + layout['x_pad']
    Y0, Y1 = -0.4, layout['y_top']
    R_MAX = layout['R_max']
    MU_TABLE = layout.get('mu_table', 0.4)
    MAT_OF_CLASS[CLASS_SPREAD] = layout['spread_mat']
    MAT_OF_CLASS[CLASS_WRAP] = layout['wrap_mat']
    COLORS[CLASS_SPREAD] = SPREAD_COLOR[layout['spread_mat']]
    COLORS[CLASS_WRAP] = WRAP_COLOR[layout['wrap_mat']]


# ----------------------------------------------------------------------------- spiral seed geometry
def spiral_profile(layout):
    """Thickness profiles of a spiral base along the sheet parameter s in [0, L].

    Both ends of the WRAPPER taper to (almost) nothing -- the cook presses the start of the sheet into
    the core and presses the end onto the roll -- and the SPREAD is absent on the pressed tip and stops
    short of the end, so the last turn glues wrapper onto wrapper."""
    L = layout['L_sheet']; wmax = layout['w_wrap']; Ts = layout['T_spread']
    lead, tail, floor_ = layout['taper_lead'], layout['taper_tail'], layout['taper_floor']
    c0, c1, ramp = layout['spread_lead'], layout['spread_tail'], layout['spread_ramp']

    def w_of(s):
        a = min(1.0, max(0.0, s / lead)); b = min(1.0, max(0.0, (L - s) / tail))
        return wmax * (floor_ + (1.0 - floor_) * min(a, b))

    def sp_of(s):
        a = min(1.0, max(0.0, (s - c0) / ramp)); b = min(1.0, max(0.0, (L - c1 - s) / ramp))
        return Ts * min(a, b)

    return w_of, sp_of


def seed_curve(layout):
    """The pre-curled start of the sheet, as a CURVATURE-CONTINUOUS curve.

    A pure Archimedean spiral that stops dead at the junction (curvature 1/r on one side, 0 on the
    other) is what the first version of this attempt used, and it ruptured there every time: gaps of
    0.4..1.2 T at s = 2.6..4.9 on a sheet whose particle spacing is 0.067 (see README).  A cook's roll
    has no such corner -- the sheet PEELS off the table, its curvature growing from zero at the peel
    front to 1/r inside the coil.

    So the seed is marched as kappa(s):
      * s in [0, s1]        -- kappa = 1/r_mid, the dense spiral: r_mid grows by one local layer
                               thickness H(s) = wrapper + spread per turn;
      * s in [s1, s1+relax] -- kappa ramps linearly to 0, so the sheet leaves the coil straight.
    The tangent angle is theta(s) = -(psi_total - psi(s)), so theta = 0 (heading +x, flat on the table)
    exactly at the junction; the outward normal is n = (sin theta, -cos theta), which at the junction
    is (0, -1) -- i.e. the wrapper's outer face lies on the table, as it does on the flat run.

    Returns a dict with the sampled curve and the numbers the rest of the file needs."""
    w_of, sp_of = spiral_profile(layout)
    r = layout['seed_r_core']
    relax = layout.get('seed_relax', 2.0)
    psi_max = 2.0 * math.pi * layout['seed_turns']
    ds = 0.004
    S = [0.0]; PSI = [0.0]; KAP = [1.0 / r]; RMID = [r]
    s = 0.0; psi = 0.0
    for _ in range(400000):
        H = w_of(s) + sp_of(s)
        kap = 1.0 / max(r, 1e-6)
        psi += kap * ds
        r += H / (2.0 * math.pi) * kap * ds
        s += ds
        S.append(s); PSI.append(psi); KAP.append(1.0 / max(r, 1e-6)); RMID.append(r)
        if psi >= psi_max:
            break
    s1 = s; kap1 = KAP[-1]
    n_rel = int(round(relax / ds))
    for i in range(1, n_rel + 1):
        kap = kap1 * (1.0 - i / n_rel)
        psi += kap * ds
        s += ds
        S.append(s); PSI.append(psi); KAP.append(kap); RMID.append(RMID[-1])
    S = np.array(S); PSI = np.array(PSI); KAP = np.array(KAP); RMID = np.array(RMID)
    L_seed = float(S[-1])
    th = PSI - PSI[-1]                      # theta(L_seed) = 0, heading +x at the junction
    cx = np.concatenate([[0.0], np.cumsum(np.cos(0.5 * (th[1:] + th[:-1])) * np.diff(S))])
    cy = np.concatenate([[0.0], np.cumsum(np.sin(0.5 * (th[1:] + th[:-1])) * np.diff(S))])
    H_j = w_of(L_seed) + sp_of(L_seed)
    return dict(S=S, TH=th, KAP=KAP, CX=cx, CY=cy, L_seed=L_seed, H_j=H_j,
                r_mid_max=float(RMID[-1]), s1=float(s1), relax=relax, psi_total=float(PSI[-1]))


def make_seed_map(layout):
    """(s, y) on the flat sheet  ->  (x, y) in the world, with the first turns already wound.

    A point at sheet coordinate (s, y) sits at offset d = H(s)/2 - y along the curve's OUTWARD normal
    (y = 0 is the wrapper's outer face, so d = +H/2 there), and the local area stretch of the map is
    jac = 1 + kappa*d -- the same 1 + d/r the circular version had, written for a general curve."""
    cur = seed_curve(layout)
    w_of, sp_of = spiral_profile(layout)
    S, TH, KAP, CX, CY = cur['S'], cur['TH'], cur['KAP'], cur['CX'], cur['CY']
    L_seed = cur['L_seed']; H_j = cur['H_j']
    # world placement: the junction sits at (x_j, H_j/2) with the sheet flat and heading +x
    x_j = float(1.6 + max(CX[-1] - CX.min(), 0.0))
    dx_off = x_j - CX[-1]; dy_off = 0.5 * H_j - CY[-1]

    def m(s, y):
        if s >= L_seed:
            return x_j + (s - L_seed), y, 1.0
        i = int(np.searchsorted(S, s))
        i = min(max(i, 0), len(S) - 1)
        th = float(TH[i]); kap = float(KAP[i])
        H = w_of(s) + sp_of(s)
        d = 0.5 * H - y
        nx, ny = math.sin(th), -math.cos(th)
        return (CX[i] + dx_off + nx * d, CY[i] + dy_off + ny * d, max(1.0 + kap * d, 0.05))

    # outer envelope of the seeded coil, for the mat's initial radius / the frame
    ss = np.linspace(0.0, L_seed, 900)
    pts = []
    ymin = 1e9
    for v in ss:
        for yy in (0.0, w_of(v) + sp_of(v)):
            X, Y, _ = m(v, yy)
            pts.append((X, Y)); ymin = min(ymin, Y)
    pts = np.array(pts)
    # The mat is a circle tangent to the table, so the seed's starting mat is the SMALLEST such circle
    # that holds the coil: minimise over the tangency point xc.  (Fixing the tangency at the coil's
    # lowest point instead -- the junction -- inflates R by 2-3x, because the last, straightened part of
    # the coil lies almost along the table and a circle tangent there cannot hug it.)  The 98th
    # percentile keeps a couple of near-table points from sending R to infinity.
    hi = pts[pts[:, 1] > 0.20]
    if len(hi) < 10:
        hi = pts
    cand = np.linspace(pts[:, 0].min(), pts[:, 0].max(), 120)
    need = [(float(np.percentile(((hi[:, 0] - c) ** 2 + hi[:, 1] ** 2) / (2.0 * hi[:, 1]), 98.0)), c) for c in cand]
    R_need, xc0 = min(need)
    inner_min = float(np.min([0.5 * (w_of(v) + sp_of(v)) for v in ss] - np.array([1.0 / max(k, 1e-9) for k in np.interp(ss, S, KAP)]) * 0 + 0))
    # tightest point of the map: where 1 + kappa*d first approaches zero (d = -H/2, the inner face)
    kap_i = np.interp(ss, S, KAP)
    H_i = np.array([w_of(v) + sp_of(v) for v in ss])
    inner_min = float(np.min(1.0 - kap_i * 0.5 * H_i))
    info = dict(L_seed=L_seed, r_core=layout['seed_r_core'], r_mid_max=cur['r_mid_max'],
                H_junction=H_j, seed_turns=layout['seed_turns'], seed_relax=cur['relax'],
                psi_total_turns=round(cur['psi_total'] / (2 * math.pi), 3),
                jac_inner_min=round(inner_min, 4), x_junction=x_j,
                curl_center=[xc0, R_need], R_seed_outer=R_need, y_min=round(ymin, 4),
                x_lo=float(pts[:, 0].min()), x_hi=float(pts[:, 0].max()))
    return m, info


def sample_spiral(layout, n_target):
    """Sample a spiral base: variable-thickness wrapper + spread, fillings spread along the sheet,
    then the whole thing pushed through the seed map."""
    L = layout['L_sheet']; wmax = layout['w_wrap']; Ts = layout['T_spread']
    w_of, sp_of = spiral_profile(layout)
    smap, sinfo = make_seed_map(layout)
    ss = np.linspace(0.0, L, 4000)
    area_wrap = float(np.trapezoid([w_of(s) for s in ss], ss)) if hasattr(np, 'trapezoid') else float(np.trapz([w_of(s) for s in ss], ss))
    area_spread = float(np.trapezoid([sp_of(s) for s in ss], ss)) if hasattr(np, 'trapezoid') else float(np.trapz([sp_of(s) for s in ss], ss))
    # fillings sit on top of the spread; keep them clear of the pre-curled seed
    fl = layout['fillings']
    # `fill_squash` (from ../spiral-curl): area-preserving pre-flattening of each piece, (h*k, w/k).
    # There it was mandatory -- its kinematic coil does not close over a 3.2 T kiwi at all.  Here it
    # is OFF by default (k = 1) because the seeded roll DOES close over the pieces at their stated
    # sizes; it is kept as a knob because the cook does press the fruit into the cream as she lays it,
    # and because it is the only handle on the pitch CV that the base itself does not fix.
    # Squash is for LUMPS only.  A piece already thinner than the spread (the jam line, the dill line)
    # has nothing left to press: flattening it just makes it longer, and a full-length line like the
    # dill (95 T on a 107.6 T sheet) becomes longer than the sheet, gets clamped to a negative start and
    # piles up in the core.  So the knob applies only where h > T_spread.
    k = float(layout.get('fill_squash', 1.0) or 1.0)
    rects = []
    for i, f in enumerate(fl):
        fw, fh = f['w'], f['h']
        if k != 1.0 and fh > layout['T_spread']:
            fw, fh = fw / k, fh * k
        u = max(f['u'], sinfo['L_seed'] + 1.2)
        u = max(0.0, min(u, L - layout['spread_tail'] - 0.6 - fw))   # never onto the glued tail
        sc = u + 0.5 * fw
        base_y = w_of(sc) + sp_of(sc) + f.get('y_off', 0.0)
        if f['stack'] and i > 0:
            base_y = rects[i - 1][1] + rects[i - 1][3]
        rects.append((u, base_y, fw, fh, f['round'], CLASS_OF_KIND[f['kind']]))
    area_fill = sum((math.pi / 4 if r[4] else 1.0) * r[2] * r[3] for r in rects)
    hp = math.sqrt((area_wrap + area_spread + area_fill) / n_target)
    xs, cls, vol, wrow, wcol = [], [], [], [], []
    rng = np.random.default_rng(1)
    jit = 0.12 * hp

    nr = max(2, int(round(wmax / hp)))                 # wrapper rows: fixed count, thickness varies
    ncn = int(round(L / hp))
    dxn = L / ncn
    ns_ref = max(2, int(round(Ts / hp)))
    for c in range(ncn):
        s = (c + 0.5) * dxn
        w = w_of(s); sp = sp_of(s)
        dyn = w / nr
        for r in range(nr):
            X, Y, jac = smap(s, (r + 0.5) * dyn)
            xs.append((X, Y)); cls.append(CLASS_WRAP); vol.append(dxn * dyn * jac)
            wrow.append(r); wcol.append(c)
        if sp > 0.02 * Ts:
            nsr = max(1, int(round(sp / hp)))
            dys = sp / nsr
            for r in range(nsr):
                X, Y, jac = smap(s + rng.uniform(-jit, jit), w + (r + 0.5) * dys + rng.uniform(-jit, jit))
                xs.append((X, Y)); cls.append(CLASS_SPREAD); vol.append(dxn * dys * jac)
                wrow.append(-1); wcol.append(-1)
    for (u, by, w, h, rnd, cl) in rects:
        ncx = max(2, int(round(w / hp))); ncy = max(2, int(round(h / hp)))
        ddx = w / ncx; ddy = h / ncy
        for i in range(ncx):
            for j in range(ncy):
                ps = u + (i + 0.5) * ddx; py = by + (j + 0.5) * ddy
                if rnd:
                    ex = (ps - (u + w / 2)) / (w / 2); ey = (py - (by + h / 2)) / (h / 2)
                    if ex * ex + ey * ey > 1.0:
                        continue
                X, Y, jac = smap(ps + rng.uniform(-jit, jit) * 0.5, py + rng.uniform(-jit, jit) * 0.5)
                xs.append((X, Y)); cls.append(cl); vol.append(ddx * ddy * jac)
                wrow.append(-1); wcol.append(-1)
    info = dict(hp=hp, nori_rows=nr, nori_cols=ncn, nori_dx=dxn, area_rice=area_spread, area_nori=area_wrap,
                area_fill=area_fill, rects=rects, seed=sinfo, spiral=True,
                x_flat0=sinfo['x_junction'], x_flat1=sinfo['x_junction'] + (L - sinfo['L_seed']))
    return (np.array(xs, np.float32), np.array(cls, np.int32), np.array(vol, np.float32),
            np.array(wrow, np.int32), np.array(wcol, np.int32), info)


# ----------------------------------------------------------------------------- particle sampling (sushi: unchanged)
def sample_layout(layout, n_target):
    if layout.get('spiral'):
        return sample_spiral(layout, n_target)
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
        # 0.78 (not 0.6) of the particle spacing: at 0.6 a square lattice of discs leaves gaps
        # between them, which speckles the map, inflates the ray turn count and deflates the
        # class-area ratio.  0.78 * h > h/sqrt(2) covers the lattice without visibly fattening the
        # outer contour (~0.4 px).
        rad = 0.78 * (max(hp, nori_dy) if c == CLASS_NORI else hp) / px
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

def turn_gaps(img, c_row, c_col, px, angs):
    """Radial pitch of the spiral: distance between the centres of successive WRAPPER bands along each
    ray.  A real roll has an even pitch, so the mean and the CV of this population are the honest
    'is it a spiral' measure; sd_within_ray is the same thing measured ray by ray (immune to the roll
    being off-centre)."""
    all_g, per_ray_sd = [], []
    for a in angs:
        d, seq = ray_classes(img, c_row, c_col, a, px, step=0.25)
        m = seq == CLASS_WRAP
        centres = []
        i = 0
        while i < len(m):
            if m[i]:
                j = i
                while j < len(m) and m[j]:
                    j += 1
                centres.append(0.5 * (d[i] + d[j - 1])); i = j
            else:
                i += 1
        if len(centres) >= 2:
            g = np.diff(np.array(centres))
            all_g += [float(v) for v in g]
            if len(g) >= 2:
                per_ray_sd.append(float(np.std(g)))
    if not all_g:
        return dict(turn_gap_mean_T=0.0, turn_gap_sd_T=0.0, turn_gap_cv=0.0,
                    turn_gap_sd_within_ray_T=0.0, turn_gap_n=0)
    g = np.array(all_g)
    return dict(turn_gap_mean_T=round(float(g.mean()), 3), turn_gap_sd_T=round(float(g.std()), 3),
                turn_gap_cv=round(float(g.std() / max(g.mean(), 1e-9)), 3),
                turn_gap_sd_within_ray_T=round(float(np.mean(per_ray_sd)) if per_ray_sd else 0.0, 3),
                turn_gap_n=int(len(g)))


def hole_radius(img, c_row, c_col, px, angs):
    """Radius of the empty core: along every ray, how far you walk from the centroid before hitting
    ANY material.  Reported as the mean over rays and the max; a tight roll has mean < 0.6 T."""
    hs = []
    for a in angs:
        d, seq = ray_classes(img, c_row, c_col, a, px, step=0.2)
        nz = np.nonzero(seq != CLASS_BG)[0]
        hs.append(float(d[nz[0]]) if len(nz) else 0.0)
    hs = np.array(hs)
    return dict(hole_r_mean_T=round(float(hs.mean()), 3), hole_r_max_T=round(float(hs.max()), 3),
                hole_area_T2=round(float(math.pi * hs.mean() ** 2), 3))


def coil_axis(chain, cen_fallback):
    """The axis of the coil: the point the wrapper actually goes round.

    Grafted from `../spiral-curl` (its `wrapper_spiral`), and it is the single most valuable thing
    that attempt produced.  Measuring the swept angle about the CENTROID of the whole roll is wrong
    as soon as the fillings are heavy: a 3 T strawberry in a 5 T roll pulls the centroid off the
    coil's axis, the chain stops going round that point, and turns can only be LOST (roll cake read
    2.09 about the centroid against 2.74 expected from its own areas).

    Two steps, both from spiral-curl:
      1. least-squares circle (Kasa) through the innermost 10 % of the wrapper chain -- that piece is
         the tight seeded core, and its circle centre is the axis.  The plain mean of those points
         sits ON the coil, not at its centre, whenever the piece is under a full turn.
      2. refine by hill-climbing the SWEPT ANGLE: a spiral's swept angle is maximal about its own
         axis, so any move off the axis loses angle.  Centres closer than 0.20 T to the band itself
         are rejected -- a centre sitting on the band fakes a whole extra turn.
    """
    n0 = min(len(chain) - 1, max(8, int(0.10 * len(chain))))
    h = chain[:n0].astype(np.float64)
    A = np.stack([h[:, 0], h[:, 1], np.ones(n0)], 1)
    b = h[:, 0] ** 2 + h[:, 1] ** 2
    try:
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        cen = np.array([0.5 * sol[0], 0.5 * sol[1]])
    except Exception:
        cen = h.mean(axis=0)
    if not np.all(np.isfinite(cen)):
        cen = h.mean(axis=0)

    def sweep_about(c):
        d = chain - c
        rr = np.hypot(d[:, 0], d[:, 1])
        if rr.min() < 0.20:          # a centre sitting ON the band fakes a whole extra turn
            return -1.0
        return float(np.ptp(np.unwrap(np.arctan2(d[:, 1], d[:, 0]))))

    best = sweep_about(cen)
    if best < 0:
        cen = np.array(cen_fallback, np.float64); best = sweep_about(cen)
    for rad in (0.6, 0.25, 0.1):
        improved = True
        while improved:
            improved = False
            for dxc in (-rad, 0.0, rad):
                for dyc in (-rad, 0.0, rad):
                    if dxc == 0.0 and dyc == 0.0:
                        continue
                    c2 = cen + np.array([dxc, dyc])
                    v = sweep_about(c2)
                    if v > best + 1e-6:
                        best, cen, improved = v, c2, True
    return cen


def spiral_from_particles(xs, cen, nori_row, nori_col, info):
    """Turn count and radial pitch measured on the WRAPPER PARTICLES, not on the raster map.

    The wrapper's middle row is an ordered curve along the sheet parameter s.  Its polar angle about
    the coil axis, unwrapped, is the winding angle: turns = |theta_end - theta_start| / 2pi -- an
    exact statement of how many times the sheet goes round, immune to a ragged skin, to a flap that a
    ray crosses twice, and to the map's pixel size.  The pitch is r(theta + 2pi) - r(theta) sampled
    along the same curve: for a true spiral it is the constant T + w, so its CV is the honest
    'are the turns evenly spaced' number.

    The centre is the COIL AXIS (`coil_axis`, grafted from spiral-curl) on spiral bases and the
    centroid on sushi, which is round and where the two coincide.  Both numbers are reported."""
    nr = info['nori_rows']
    rowi = nr // 2
    m = nori_row == rowi
    if int(m.sum()) < 20:
        return dict(turns_particles=0.0, pitch_mean_T=0.0, pitch_sd_T=0.0, pitch_cv=0.0, pitch_n=0)
    o = np.argsort(nori_col[m])
    p = xs[m][o].astype(np.float64)
    cen_centroid = np.array(cen, np.float64)
    out_extra = {}
    if info.get('spiral'):
        cen = coil_axis(p, cen_centroid)
        d0 = p - cen_centroid
        th0 = np.unwrap(np.arctan2(d0[:, 1], d0[:, 0]))
        out_extra['turns_particles_centroid'] = round(float(abs(th0[-1] - th0[0]) / (2 * math.pi)), 3)
        out_extra['coil_axis_xy'] = [round(float(cen[0]), 3), round(float(cen[1]), 3)]
    rel = p - np.array(cen, np.float64)
    r = np.hypot(rel[:, 0], rel[:, 1])
    th = np.unwrap(np.arctan2(rel[:, 1], rel[:, 0]))
    turns_p = abs(th[-1] - th[0]) / (2 * math.pi)
    r_tip = float(r[0])                       # where the SEEDED tip of the sheet ended up
    # pitch: resample r on a monotone angle axis (flip if the roll was wound the other way)
    sgn = 1.0 if th[-1] >= th[0] else -1.0
    tt = sgn * th
    keep = np.concatenate([[True], np.diff(tt) > 0])          # drop the non-monotone wobble
    tt = tt[keep]; rr = r[keep]
    pit = []
    if len(tt) > 10 and tt[-1] - tt[0] > 2 * math.pi:
        grid = np.linspace(tt[0], tt[-1] - 2 * math.pi, 240)
        r0 = np.interp(grid, tt, rr); r1 = np.interp(grid + 2 * math.pi, tt, rr)
        pit = r1 - r0
    # arc-length bracket (grafted from spiral-curl): turns = sum(ds / (2*pi*r)) along the same chain.
    # It never sees the angle, so a chain point passing near the assumed centre cannot cost it a whole
    # turn the way unwrap can.  Where a lobe throws the sheet out radially, the swept angle UNDER-counts
    # and this over-counts, so the true winding is bracketed between them.
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    rmid = 0.5 * (r[1:] + r[:-1])
    r_floor = max(0.15, 0.25 * float(np.median(np.abs(np.diff(np.sort(r))))))
    turns_arc = float(np.sum(seg / (2.0 * math.pi * np.maximum(rmid, r_floor))))
    base = dict(turns_particles=round(float(turns_p), 3), turns_arclen=round(turns_arc, 3),
                tip_r_T=round(r_tip, 3),
                tip_r_frac=round(r_tip / max(float(r.max()), 1e-9), 3),
                turns_range=round(float(th.max() - th.min()) / (2 * math.pi), 3))
    base.update(out_extra)
    if len(pit) == 0:
        base.update(pitch_mean_T=0.0, pitch_sd_T=0.0, pitch_cv=0.0, pitch_n=0)
        return base
    pit = np.asarray(pit)
    base.update(pitch_mean_T=round(float(pit.mean()), 3), pitch_sd_T=round(float(pit.std()), 3),
                pitch_cv=round(float(pit.std() / max(abs(pit.mean()), 1e-9)), 3), pitch_n=int(len(pit)))
    # --- per-TURN pitch: the radial advance of one whole revolution, one number per turn.
    # `pitch_cv` above is the pitch AT AN ANGLE, and on a base whose fillings are 2-3x thicker than the
    # sheet it can never be even: where a strawberry lies between two turns the gap is legitimately
    # twice what it is a quarter-turn later (see `pitch_intrinsic_cv`).  What "even turns" means on the
    # cut is coarser -- turn k is spaced like turn k+1 -- so the same population is averaged over each
    # 2pi block before the CV is taken.  Both numbers are reported; neither replaces the other.
    if len(pit) > 3:
        ang = np.linspace(tt[0], tt[-1] - 2 * math.pi, len(pit))
        blk = np.floor((ang - ang[0]) / (2 * math.pi)).astype(int)
        vals = [float(pit[blk == b].mean()) for b in range(blk.max() + 1) if int((blk == b).sum()) >= 3]
        if len(vals) >= 2:
            v = np.asarray(vals)
            base.update(pitch_turn_mean_T=round(float(v.mean()), 3),
                        pitch_turn_cv=round(float(v.std() / max(abs(v.mean()), 1e-9)), 3),
                        pitch_turn_n=int(len(v)),
                        pitch_turn_values_T=[round(float(x), 3) for x in v])
    return base


TIP_WIN = 0.5      # what counts as "the tip": the outermost 0.5 T of sheet at each end


def tip_thickness(xs, nori_row, nori_col, info, layout):
    """How thin the wrapper actually is at its two tips IN THE FINISHED ROLL.

    The brief asks for both ends to run out to nothing (< 40 % of the nominal thickness).  `taper_floor`
    is only the sampling intent; what has to be checked is the band in the final state, because the
    solver smears a tip thinner than a grid cell and the press squeezes the whole band.  The wrapper is
    sampled as `nori_rows` rows at fixed count and varying spacing, so the band thickness at a column is
    the distance between its outermost rows, scaled by nr/(nr-1) (the rows sit at cell centres).

    Reported against BOTH references: `w_wrap` (the base's nominal) and the median band thickness over
    the middle of the sheet (the same band as the solver actually left it)."""
    nr = info['nori_rows']
    if nr < 2:
        return {}
    m0 = nori_row == 0; m1 = nori_row == nr - 1
    p0 = xs[m0][np.argsort(nori_col[m0])]
    p1 = xs[m1][np.argsort(nori_col[m1])]
    n = min(len(p0), len(p1))
    if n < 20:
        return {}
    d = np.hypot(p0[:n, 0] - p1[:n, 0], p0[:n, 1] - p1[:n, 1]) * nr / (nr - 1.0)
    k = max(2, int(round(TIP_WIN / max(info['nori_dx'], 1e-6))))      # average over TIP_WIN of sheet
    lead = float(np.mean(d[:k])); tail = float(np.mean(d[-k:]))
    mid = d[int(0.2 * n):int(0.8 * n)]
    nom = float(np.median(mid)) if len(mid) else float(np.median(d))
    w0 = float(layout['w_wrap'])
    return dict(tip_w_lead_T=round(lead, 4), tip_w_tail_T=round(tail, 4),
                tip_w_nominal_T=round(w0, 4), tip_w_mid_median_T=round(nom, 4),
                tip_w_lead_frac=round(lead / max(w0, 1e-9), 3),
                tip_w_tail_frac=round(tail / max(w0, 1e-9), 3),
                tip_w_lead_frac_mid=round(lead / max(nom, 1e-9), 3),
                tip_w_tail_frac_mid=round(tail / max(nom, 1e-9), 3),
                tips_taper_ok=bool(lead < 0.40 * w0 and tail < 0.40 * w0))


def wrinkle_metric(xs, nori_row, nori_col, info, step=0.5, ang_min=0.05):
    """Folds ("гармошка") along the wrapper, per KINEMATICS.md, "Дефект «гармошка»" (26.08.2026, 11:35).

    The wrapper's middle row is an ordered polyline along the sheet.  It is resampled at a fixed arc
    step (0.5 T -- three particles at this attempt's spacing is 0.2 T, far below the grid cell, so the
    raw turning angle is pure noise), and the signed turning angle at each vertex is smoothed over three
    vertices.  A roll wound one way turns one way: every sign change of that angle above `ang_min` is a
    fold.  A spiral base has no fold nose (no phase B), so nothing is excluded from the count.

    `wrinkle_amp_T` is the largest sagitta over a minority-sign vertex -- how deep the fold is.
    Criterion from the spec: wrinkles <= 1 and amplitude < 0.5 T."""
    rowi = info['nori_rows'] // 2
    m = nori_row == rowi
    if int(m.sum()) < 20:
        return dict(wrinkles=0, wrinkle_amp_T=0.0, wrinkle_vertices=0)
    p = xs[m][np.argsort(nori_col[m])].astype(np.float64)
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])
    n = max(4, int(arc[-1] / step))
    grid = np.linspace(0.0, arc[-1], n)
    q = np.stack([np.interp(grid, arc, p[:, 0]), np.interp(grid, arc, p[:, 1])], 1)
    d = np.diff(q, axis=0)
    cr = d[:-1, 0] * d[1:, 1] - d[:-1, 1] * d[1:, 0]
    dot = (d[:-1] * d[1:]).sum(1)
    ang = np.arctan2(cr, dot)
    k = np.convolve(ang, np.ones(3) / 3.0, mode='same')
    big = np.abs(k) > ang_min
    sg = np.sign(k[big])
    wr = int(np.sum(sg[1:] != sg[:-1])) if len(sg) > 1 else 0
    # amplitude: sagitta of the three-vertex window at each minority-sign vertex
    amp = 0.0
    if len(sg) > 1:
        maj = 1.0 if np.sum(sg > 0) >= np.sum(sg < 0) else -1.0
        idx = np.nonzero(big)[0][sg != maj]
        for i in idx:
            a, b, c = q[i], q[i + 1], q[i + 2]
            L = np.linalg.norm(c - a)
            if L > 1e-9:
                amp = max(amp, abs((c[0] - a[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (c[1] - a[1])) / L)
    return dict(wrinkles=wr, wrinkle_amp_T=round(float(amp), 3), wrinkle_vertices=int(np.sum(big)))


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
    gapm = turn_gaps(img, c_row, c_col, px, angs)
    holem = hole_radius(img, c_row, c_col, px, angs)
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
    # --- spread "loss": the map ratio is a RASTERISATION artefact (the wrapper band is drawn over the
    #     spread and the spread genuinely compresses), so the real measure is CONSERVATION:
    #     sum(vol_p * J_p) at the end / sum(vol_p) at the start.  It must be >= 0.97.
    rice_m = cls == CLASS_RICE
    wrap_m = cls == CLASS_NORI
    rice_area_map = float(np.sum(img == CLASS_RICE)) * px * px
    Jmean = float(np.mean(Jp[rice_m])) if rice_m.any() else 1.0
    volp = np.asarray(info['vol_np'], np.float64)
    Jd = np.asarray(Jp, np.float64)
    def _cons(mask):
        s0 = float(volp[mask].sum())
        return round(float((volp[mask] * Jd[mask]).sum() / s0), 4) if s0 > 0 else 1.0
    cons_all = _cons(np.ones(len(cls), bool))
    cons_spread = _cons(rice_m)
    cons_wrap = _cons(wrap_m)
    # per-filling conservation (grafted from spiral-curl): a piece that is only 2-3 particles thick on
    # this grid cannot be trusted, and the only way to see that is to break the number out per piece.
    cons_fill = {}
    for f in layout['fillings']:
        c = CLASS_OF_KIND[f['kind']]
        mf = cls == c
        if mf.any():
            cons_fill[f['kind']] = _cons(mf)
    area0 = float(volp.sum()); area1 = float((volp * Jd).sum())
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
        conservation=cons_all, conservation_spread=cons_spread, conservation_wrapper=cons_wrap,
        conservation_fillings=cons_fill,
        area_initial_T2=round(area0, 3), area_final_T2=round(area1, 3),
        mat=extra['mat'], grab=extra['grab'], phases=extra['phases'], timing=extra['timing'],
    )
    met.update(gapm); met.update(holem)
    met.update(spiral_from_particles(xs, cen_world, nori_row, nori_col, info))
    met.update(wrinkle_metric(xs, nori_row, nori_col, info))
    if info.get('spiral'):
        met.update(tip_thickness(xs, nori_row, nori_col, info, layout))
    # --- base-neutral aliases (a spiral base has no rice and no nori)
    met['turns'] = met['nori_turns']
    met['turns_min'] = met['nori_turns_min']
    met['turns_max'] = met['nori_turns_max']
    met['spread_area_ratio_map'] = met['rice_area_ratio']
    met['spread_J_mean'] = met['rice_J_mean']
    met['spread_under_filling_T'] = met['rice_under_filling_T']
    met['wrapper_max_gap_T'] = met['nori_max_gap_T']
    met['wrapper_components_map'] = met['nori_components_map']
    met['torn'] = met['nori_torn']
    met['wrap_material'] = MAT_OF_CLASS[CLASS_WRAP]
    met['spread_material'] = MAT_OF_CLASS[CLASS_SPREAD]
    met['sheet_L_T'] = layout['L_sheet']
    met['w_wrap_T'] = layout['w_wrap']
    met['T_spread_T'] = layout['T_spread']
    if info.get('spiral'):
        met['seed'] = info['seed']
        met['fill_squash'] = round(float(layout.get('fill_squash', 1.0) or 1.0), 3)
        met['taper_floor'] = round(float(layout['taper_floor']), 3)
        r_hole_ref = max(met['hole_r_mean_T'], layout['seed_r_core'])
        met['turns_expected_area'] = round(expected_turns(layout, info, r_hole_ref), 3)
        met['Rout_expected_area_T'] = round(math.sqrt(area0 / math.pi + r_hole_ref ** 2), 3)
        met['r_hole_ref_T'] = round(r_hole_ref, 3)
        st_t, st_R = stand_turns(layout)
        met.update(intrinsic_pitch(layout, info))
        met['turns_stand_formula'] = round(st_t, 3)
        met['Rout_stand_formula_T'] = round(st_R, 3)
    return met


def area_along_sheet(layout, info, n=4000):
    """(s, A(s)) -- cross-section area of everything (wrapper + spread + fillings) lying on the first
    s of the sheet.  This is the only thing needed to know how big the roll must be after s has been
    wound: R(s) = sqrt(A(s)/pi + r_hole^2)."""
    L = layout['L_sheet']
    w_of, sp_of = spiral_profile(layout)
    ss = np.linspace(0.0, L, n)
    h = np.array([w_of(s) + sp_of(s) for s in ss])
    for (u, by, wd, ht, rnd, cl) in info['rects']:
        m = (ss >= u) & (ss <= u + wd)
        if not m.any():
            continue
        if rnd:
            e = (ss[m] - (u + wd / 2)) / (wd / 2)
            h[m] += ht * np.sqrt(np.clip(1 - e * e, 0, 1))
        else:
            h[m] += ht
    A = np.concatenate([[0.0], np.cumsum(0.5 * (h[1:] + h[:-1]) * np.diff(ss))])
    return ss, A


def intrinsic_pitch(layout, info):
    """How uneven the radial pitch of this base is BOUND to be, before any kinematics.

    The gap between two neighbouring turns at a given angle is the local thickness of the sheet at the
    point that lies there: wrapper + spread + whatever filling sits on it.  So the honest floor for the
    pitch CV is the CV of that thickness along the sheet.  For the roll cake the fillings cover 36 % of
    the sheet and stand 2.4x taller than the sheet itself, which puts the floor near 0.45 -- a run that
    measures 0.4 is not "uneven", it is as even as this base can be."""
    ss, A = area_along_sheet(layout, info)
    h = np.gradient(A, ss)
    m = float(np.mean(h)); sd = float(np.std(h))
    return dict(pitch_intrinsic_mean_T=round(m, 3), pitch_intrinsic_cv=round(sd / max(m, 1e-9), 3))


def expected_turns(layout, info, r_hole=0.0):
    """How many turns the spiral MUST have, from area conservation alone (criterion 1 of the brief).

    Marching along the sheet: everything already wound (wrapper + spread + fillings) plus the hole
    fills the disc of radius r(s), so dphi = ds / r(s) and turns = (1/2pi) * integral ds / r(s)."""
    ss, A = area_along_sheet(layout, info)
    r = np.sqrt(A / math.pi + max(r_hole, 0.05) ** 2)
    return float(np.trapezoid(1.0 / (2 * math.pi * r), ss) if hasattr(np, 'trapezoid')
                 else np.trapz(1.0 / (2 * math.pi * r), ss))

def stand_turns(layout, r0=0.25):
    """The stand's own numbers for this base: a uniform sheet of pitch P = T + w wound from r0, with
    NO fillings.  L = r0*th + P*th^2/(4pi); turns = th/2pi; Rout = sqrt(L*P/pi + r0^2).
    Reported for comparison only -- the reference carries fillings, so its own honest target is
    `turns_expected_area`."""
    P = layout['T_spread'] + layout['w_wrap']; L = layout['L_sheet']
    a = P / (4.0 * math.pi)
    th = (-r0 + math.sqrt(r0 * r0 + 4.0 * a * L)) / (2.0 * a)
    return th / (2.0 * math.pi), math.sqrt(L * P / math.pi + r0 * r0)


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
    ap.add_argument('--speed', type=float, default=None, help='default: the base\'s own speed')
    ap.add_argument('--press', type=float, default=None, help='default: the base\'s own press')
    ap.add_argument('--tuck', type=float, default=1.0, help='how far the grabbed edge is carried in phase B (0.6..1.3)')
    ap.add_argument('--fronty', type=float, default=-1.0,
                    help='height of the lower FRONT end of the mat arc, T (default: sheet top + 0.15)')
    ap.add_argument('--lift', type=float, default=-1.0,
                    help='raise the mat circle by this fraction of the incoming sheet thickness, so the roll '
                         'rides ON the sheet instead of on the table (KINEMATICS.md phase C); 0 = on the table')
    ap.add_argument('--grid', type=int, default=0, help='total grid nodes ~ grid^2 (0 = the base\'s own)')
    ap.add_argument('--particles', type=int, default=0, help='0 = the base\'s own')
    ap.add_argument('--mutable', type=float, default=-1.0, help='table friction (default: the base\'s own)')
    ap.add_argument('--fillshift', type=float, default=0.0, help='shift every filling this far along the sheet, T')
    ap.add_argument('--wrapyield', type=float, default=-1.0, help='override the wrapper shear yield (material sweep)')
    ap.add_argument('--spreadyield', type=float, default=-1.0, help='override the spread shear yield (material sweep)')
    ap.add_argument('--seedturns', type=float, default=-1.0, help='spiral bases: pre-curled turns (default 1.5)')
    ap.add_argument('--seedcore', type=float, default=-1.0,
                    help='spiral bases: mid-surface radius of the innermost pre-curled turn, T. '
                         'Must exceed (w_wrap + T_spread)/2 or the seed map folds through its own axis.')
    ap.add_argument('--fillsquash', type=float, default=1.0,
                    help='area-preserving pre-flattening of every filling, (h*k, w/k); 1 = off (default). '
                         'From ../spiral-curl, where it was mandatory; here it is a modelling knob.')
    ap.add_argument('--taperlead', type=float, default=-1.0,
                    help='spiral bases: length over which the wrapper ramps up from the START tip, T')
    ap.add_argument('--tapertail', type=float, default=-1.0,
                    help='spiral bases: length over which the wrapper ramps down to the END tip, T')
    ap.add_argument('--taperfloor', type=float, default=-1.0,
                    help='spiral bases: thinnest the tapered wrapper gets at both tips, as a fraction of '
                         'w_wrap (default: the base\'s own; the brief asks for < 0.40)')
    ap.add_argument('--out', type=str, default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out'))
    ap.add_argument('--frames', type=int, default=10, help='number of debug snapshots (0 = none)')
    ap.add_argument('--window', type=float, default=0.0, help='material map window side, T (0 = the base\'s own)')
    ap.add_argument('--tag', type=str, default='')
    args = ap.parse_args()
    layout = dict(LAYOUTS[args.layout])
    spiral = bool(layout.get('spiral'))
    if args.speed is None: args.speed = layout['speed']
    if args.press is None: args.press = layout['press']
    if not args.grid: args.grid = layout.get('grid', 240)
    if not args.particles: args.particles = layout.get('particles', 16000)
    if not args.window: args.window = layout['window']
    if spiral and args.seedturns > 0: layout['seed_turns'] = args.seedturns
    if spiral and args.seedcore > 0: layout['seed_r_core'] = args.seedcore
    if spiral and args.fillsquash != 1.0: layout['fill_squash'] = args.fillsquash
    if spiral and args.taperfloor >= 0: layout['taper_floor'] = args.taperfloor
    if spiral and args.taperlead > 0: layout['taper_lead'] = args.taperlead
    if spiral and args.tapertail > 0: layout['taper_tail'] = args.tapertail
    if args.lift < 0: args.lift = layout.get('lift', 1.0)
    if args.mutable >= 0: layout['mu_table'] = args.mutable
    if args.fillshift:
        layout['fillings'] = [dict(f, u=f['u'] + args.fillshift) for f in layout['fillings']]
    bind_layout(layout)
    if args.wrapyield > 0:
        E, nu, _, r = MATERIALS[layout['wrap_mat']]; MATERIALS[layout['wrap_mat']] = (E, nu, args.wrapyield, r)
    if args.spreadyield > 0:
        E, nu, _, r = MATERIALS[layout['spread_mat']]; MATERIALS[layout['spread_mat']] = (E, nu, args.spreadyield, r)
    os.makedirs(args.out, exist_ok=True)
    tag = f'{args.layout}{args.tag}'
    tuck = min(1.3, max(0.6, args.tuck))
    lift_f = min(1.2, max(0.0, args.lift))
    y_front = Y_FRONT_MIN if args.fronty < 0 else max(0.30, args.fronty)

    aspect = (X1 - X0) / (Y1 - Y0)
    ny = int(round(args.grid / math.sqrt(aspect)))
    nx = int(round(ny * aspect))
    xs, cls, vol, nori_row, nori_col, info = sample_layout(layout, args.particles)
    info['vol_np'] = vol                     # conservation metric needs the reference volumes
    n = len(cls)

    # ---------------- grab path (phases A and B) -------------------------------------------------
    # Посадка ближнего края одна на все раскладки: дальняя кромка риса (sim/fold.py, #113).
    # Прежде она считалась от начинок и потому у пустого листа была другой; в источниках такой
    # зависимости нет. Начинки остались только там, где они и правда важны, — в высоте дуги.
    s_fold_base = fold.fold_landing(L_SHEET, L_FLAP)
    if spiral:
        # no grab and no tuck at all: the coil is seeded geometrically and the machine starts at C.
        h_top = layout['T_spread'] + W_NORI
    elif info['rects']:
        h_top = max(r[1] + r[3] for r in info['rects'])
    else:
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
    if spiral:
        grab_np = np.zeros(len(cls), np.float32)          # spiral bases are never grabbed
        goff = (0.0, 0.0)
    else:
        w_grab = np.clip((GRAB_W - xs[:, 0]) / (0.5 * GRAB_W), 0.0, 1.0)
        grab_np = np.where(cls == CLASS_NORI, w_grab, 0.0).astype(np.float32)
        # the "fingers": a rigid disk of radius R_FINGER around the centroid of the grabbed strip,
        # carried along the same path, so nothing inside the grab can be torn apart.
        g0 = (float(xs[grab_np == 1, 0].mean()), float(xs[grab_np == 1, 1].mean()))
        goff = (g0[0] - 0.0, g0[1] - y_edge0)
    n_grab = int((grab_np > 0).sum())
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
    if spiral:
        sd = info['seed']
        # the machine starts at C: the mat sits on the seeded coil, tangent to the table, at the point
        # where the flat run of the sheet begins.
        xc_C0 = sd['curl_center'][0]
        x_end = info['x_flat1'] + X_END_EXTRA
        R_init = sd['R_seed_outer'] + 0.12
        t_fold = t_tuck = 0.0
        t_rollmax = (x_end - xc_C0) / v_c + 0.5 * T_SPINUP
        t_total_max = t_rollmax + T_CLOSE + T_PRESS_MAX
    else:
        xc_C0 = 1.35 * x_p
        t_rollmax = (x_end - xc_C0) / v_c
        t_total_max = t_fold + t_tuck + T_HOLD + t_rollmax + T_CLOSE + T_PRESS_MAX
        R_init = 0.5 * (b_ap + h_top + 1.2) + 0.3
    n_steps_max = int(math.ceil(t_total_max / dt))

    print(f'grid {nx}x{ny} dx={dx:.4f} particles={n} grabbed={n_grab} hp={info["hp"]:.4f} wrap rows={info["nori_rows"]} '
          f'dt={dt:.5f} cmax={cmax:.2f} v_c={v_c} v_g={v_g} '
          f'R_init={R_init:.2f} t_fold={t_fold:.1f} t_rollmax={t_rollmax:.1f} steps<={n_steps_max}', flush=True)
    if spiral:
        sd = info['seed']
        print(f'  seed: {sd["seed_turns"]} turns, sheet used L_seed={sd["L_seed"]:.2f} T, r_core={sd["r_core"]:.2f}, '
              f'R_seed_outer={sd["R_seed_outer"]:.2f} T, junction x={sd["x_junction"]:.2f}, flat run '
              f'{info["x_flat0"]:.1f}..{info["x_flat1"]:.1f}, area total={float(vol.sum()):.1f} T2, '
              f'turns_expected={expected_turns(layout, info, 0.3):.2f}', flush=True)

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
    phase = 'C' if spiral else 'A'
    last_phase = phase; t_phase = 0.0; th_g = 0.0
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
    phase_marks = {phase: 0.0}
    nori_idx = np.nonzero(cls == CLASS_NORI)[0]
    n_nori = len(nori_idx)
    wrap_idx = nori_idx
    wrap_s = (nori_col[wrap_idx].astype(np.float64) + 0.5) * info['nori_dx']
    if spiral:
        s_tab_A, A_tab = area_along_sheet(layout, info)
        r_hole_seed = float(info['seed']['r_core'])
    else:
        s_tab_A = A_tab = None; r_hole_seed = 0.0
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
            spin = min(1.0, t_phase / T_SPINUP) if spiral else 1.0
            xc += v_c * spin * dt
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
            spin = min(1.0, t_phase / T_SPINUP) if spiral else 1.0
            vc_now = v_c * spin
            P_ref = P_ROLL_REF * args.press * (0.35 + 0.65 * spin)
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
        # GEOMETRIC FLOOR (spiral bases, phase C).  A pressure-only controller is a proportional
        # controller: near equilibrium its Rdot goes to zero, so on a long sheet the mat falls behind
        # the growing roll and starts extruding material through the feed gap at the bottom front.
        # The floor is measured, not assumed: the smallest circle (tangent to the top of the incoming
        # sheet) that still contains 99 % of the material already lifted off the table.
        R = min(max(R, R_MIN, R_floor), R_MAX)
        t += dt; t_phase += dt

        # ---------------- phase C -> D: the sheet is fully picked up --------------------------------
        if phase == 'C' and step % 100 == 0:
            xnp = S['x'].to_numpy()
            if spiral:
                # how much of the sheet is already wound?  the wrapper particles that have left the
                # flat bed (the bed's wrapper sits below w_wrap, the roll's above ~Y_BED)
                yw = xnp[wrap_idx, 1]
                up = wrap_s[yw > 0.5 * (W_NORI + Y_BED)]
                s_front = float(np.percentile(up, 99.5)) if len(up) > 20 else 0.0
                A_wound = float(np.interp(s_front, s_tab_A, A_tab)) + math.pi * r_hole_seed ** 2
                R_floor = min(R_MAX, R_GEOM_FRAC * math.sqrt(A_wound / math.pi))
            # nothing that is not yet part of the roll may stick out in front of it any more
            # (this is what winds the tail in instead of leaving it outside)
            # how thick is the sheet still coming in? (rice bed vs. bare nori flap)
            rf = int(np.sum((xnp[rice_idx, 0] > xc + 0.8 * R) & (xnp[rice_idx, 1] < 2.0)))
            ylift_target = lift_f * (Y_BED if rf > 0.01 * n_rice else (W_NORI + 0.15))
            d = np.hypot(xnp[:, 0] - xc, xnp[:, 1] - (R + ylift))
            outs = d > R + 0.5
            ahead = float((xnp[outs, 0] - xc).max()) if outs.any() else -1e9
            if ahead < (0.35 if spiral else 0.9) * R or xc >= x_end:
                phase = 'D_close'; t_phase = 0.0; phase_marks['D_close'] = t
                # close the mat AROUND everything, tail included: the smallest circle that is tangent to
                # the table at xc and contains every particle has
                #   R_enclose = max_p ((px-xc)^2 + py^2) / (2 py)
                xc = float(xnp[:, 0].mean())
                yy = np.maximum(xnp[:, 1], 0.05)
                need = (xnp[:, 0] - xc) ** 2 + yy ** 2
                need = need / (2.0 * yy)
                if spiral:
                    # only what is already part of the roll may size the mat; a strip of tail still on
                    # the table would otherwise blow it wide open (that strip is swept in by the arc).
                    near = np.hypot(xnp[:, 0] - xc, xnp[:, 1] - (R + ylift)) < 1.5 * R
                    need = need[near] if int(near.sum()) > 200 else need
                    R = min(R_MAX, 1.12 * R, max(R, 1.02 * float(np.percentile(need, 99.0))))
                    R_floor = R_GEOM_FRAC * math.sqrt((A_tab[-1] + math.pi * r_hole_seed ** 2) / math.pi)
                else:
                    R_floor = 0.0
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
    if zoom is None:
        wfig = 13.0
        hfig = max(2.6, min(7.0, wfig * (Y1 - Y0) / (X1 - X0)))
        fig, ax = plt.subplots(figsize=(wfig, hfig), dpi=100)
    else:
        fig, ax = plt.subplots(figsize=(6, 6), dpi=100)
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
