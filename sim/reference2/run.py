#!/usr/bin/env python
"""reference2: 2D MLS-MPM reference of rolling a sushi roll with a REAL bamboo mat (makisu).

The winner of the mat play-off of 26.08.2026 (see README.md): ../mat-sdf, plus three things taken
from the loser ../mat-chain and one metric asked for by the owner. Deltas against mat-sdf:
  * R_fold is capped by AREA CONSERVATION -- the first turn cannot enclose more than the material
    that goes into it (a_fold + s_close*h). Only layout 5 hits the cap; layouts 1-4 are unchanged.
  * when the cap bites, tuck_eff carries the near end further in proportion to the shrinkage.
  * wrinkles_mat: the wrinkle count with the threshold the BAMBOO sets (1/R_MAT_MIN = 2 1/U) rather
    than the bed (1/H_SHEET = 0.704 1/U; it was 0.89 before the thickness correction of 26.08.2026)
    -- from mat-chain.
  * mat_bend_violations (26.08.2026): every stretch of the band bent tighter than the mat itself can
    bend, over the WHOLE band. Reversal-based counters can be dodged; this one cannot.

Corrections of 26.08.2026 (evening), all from adversarial re-measurement -- see README sec.4:
  * the "fold nose" window is no longer excluded from any wrinkle count or from the amplitude fit.
    It was placed by argmax of accumulated turning, so it sat on the tightest bend by construction.
  * nori_turns bridges rasterisation holes (BG_HOLE_T), as the rice-under-filling walk already did.
  * crossings_predicted lost its "+1 for the tuck": with the bridged count the offset is zero.
  * nori_particle_gap_T / nori_mat_gap_*: the tear test and the contact test are now two metrics.
  * pressed_ok: a run whose mat never reached the roll is no longer reported as stable.
  * --threads: one thread makes the run bit-reproducible (atomic float adds are order-dependent).
  * crossings_predicted_actual / _best: the layer formula fed the fold length the run actually spent
    on the first turn -- from mat-chain.
  * rice_J_min_run: the smallest rice compaction reached at ANY moment (KINEMATICS.md 13:25 -- the
    wrinkle is the symptom, the crushed rice is the disease).
  * shape: half-side, fill fraction and corner radius of the square press (layout 5).

Rewritten kinematics (../KINEMATICS.md, "MAIN CORRECTION 26.08.2026, 12:50"). The mat is not an arc
pressing from above and the near edge of the nori is not grabbed through the air. The mat lies UNDER
the sheet from the first instant, its near end flush with the near edge of the nori, and the nori
rides ON it, held down by the rice.

The mat as an analytic moving boundary
--------------------------------------
At every instant the mat is
    * flat on the table ahead of the contact point (x > xc), where it coincides with the table, and
    * a circular arc of radius R tangent to the table at (xc, 0), spanning th in [0, Phi], where th is
      measured CLOCKWISE from the contact point: th = pi/2 behind the roll, pi on top, 3pi/2 in front.
      P(th) = (xc - R sin th, ylift + R (1 - cos th)).
Rolling without slipping ties the two together: d(xc)/dt = d(s_c)/dt = v, so the mat material of
arclength s sits at th = (s_c - s)/R and Phi = s_c/R. Two consequences, and they are the whole point:
    * the near end of the mat traces a CYCLOID, and the sheet's fold radius is R everywhere -- no
      crease tighter than R can exist, so an accordion is impossible by construction (the mat's own
      minimum bend radius, R_MAT_MIN = 0.5 U, is far below R and is never the binding constraint).
      CAVEAT, measured 26.08.2026: this holds for the mat, NOT yet for the sheet. The mat contact is
      one-sided ("stay inside", only when vn < 0) and nothing gives the nori a bending stiffness of
      its own, so in the CORE the sheet can and does fold tighter than the mat could -- 0.229 U on
      layout 4 and 0.164 U on layout 5, against a limit of 0.56 U. `mat_bend_violations` records it.
      MEASURED AT T = 1.0, w = 0.12, L = 38.7 -- needs re-measuring: the limit is now
      R_MAT_MIN + w/2 = 0.51 U, so the same bend is judged MORE leniently than it was.
      Until the sheet gets an explicit curvature limit, "impossible by construction" is a claim about
      the boundary, not a property of the model;
    * there is no free span of sheet at any moment: the nori is either flat on the table or bonded to
      the mat (MAT_BOND, high friction / next to no slip), which is what the old grab got wrong.

Phases
------
  1 lift   Phi grows from 0 to pi -- the near end of the mat goes up the back and over the top,
           carrying the nori with it. The fingers hold the stack of fillings the roll has not yet
           reached (a lid just above it plus a brake on its forward creep).
  2 close  Phi grows on to phi_meet = pi + tuck*(phi_meet0 - pi), where phi_meet0 puts the near end
           down exactly on the far rice line (rice meets rice over the fillings). --tuck moves it.
  3 hold   the roll stops, the mat presses harder, the fingers let go. --hold sets the pause.
  4 roll   the mat rolls forward WITH the roll: R grows as an Archimedean spiral (dR/ds = h/(2 pi R)),
           and the mat's leading end is led out from under the roll -- Phi is capped at the angle
           where the mat would otherwise scoop the bed still lying ahead. --speed sets the pace.
  5 ring   the mat closes into a full ring around everything, flap included.
  6 press  final squeeze to force equilibrium at P_press (circle, or rounded square for layout 5).

Units: U = 1 length unit = 5 mm (the rice bed is T_RICE = 1.4 U, NOT the unit -- see the block of
constants below), rho_rice = 1, E_rice = 1, time unit = U / sqrt(E_rice/rho_rice).
Materials, solver, rasterization and metrics are unchanged from ../reference/run.py.

CLI: python run.py --layout 1..6 --speed 1.0 --press 1.0 --tuck 1.0 --hold 1.0 --fingers 1
                   [--bond 0.85] [--grid 240] [--particles 16000] [--frames 12] [--out DIR] [--tag ..]
"""
import argparse, json, math, os, sys, time
import numpy as np

# ----------------------------------------------------------------------------- layouts
# UNITS (rewritten 26.08.2026). U is the LENGTH UNIT of this file and of the stand (index.html):
# U = 5 mm. Every bare length below -- the filling sizes in LAYOUTS, R_MAT_MIN, FOLD_CLEAR, WR_DS,
# TAIL_TOL, ... -- is in U, and NONE of them follows the thickness of the rice.
# Until 26.08.2026 the unit and the rice bed were one symbol `T`, because they happened to be
# numerically equal (a 5 mm bed = 1 U). They are not equal any more: the sourced bed is 7 mm = 1.4 U
# (docs/geometry-audit.md, "Thicknesses from sources"). The symbol `T` is therefore GONE rather than
# aliased -- a forgotten use has to raise NameError, not quietly read 1.0.
# The `_T` suffix on the metric keys is KEPT (../judge.py and ../reference/table.py read those keys
# across every variant) and from now on it reads "in U", not "in rice thicknesses".
U_MM    = 5.0     # one length unit, mm -- the same unit as index.html
T_RICE  = 1.4     # rice bed thickness, U = 7 mm   (SUZUMO SVS-FCA: small 7 / medium 8 / futomaki 12)
W_NORI  = 0.02    # nori thickness,     U = 0.1 mm (FAO: 21x19 cm sheet ~3.0 g -> 75 g/m2, rho 0.7-1.0)
H_SHEET = T_RICE + W_NORI      # loaded sheet thickness = spiral pitch, U (1.42)
L_SHEET = 42.0    # sheet length,       U = 21 cm  (long side of the FAO sheet; stand sheetCm 21)
L_FLAP  = 5.0     # bare nori at the far edge, U = 25 mm -- NOT from the stand, UNVERIFIED: the stand
                  # has flap 0 for sushi and its `flap` means something else (the tail after closing
                  # in the one-turn model). At L_FLAP = 0 the rice area would be 58.8 U2, not 51.8.
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
    # ~60 U2 at U = 5 mm. With that much core the sheet closes in ~1.2 turns (see README sec.5.1;
    # the turn count was measured on the 38.7 U / T = 1.0 geometry and needs re-measuring).
    6: dict(name='futomaki-full-core', fillings=[fill('tamago', 1.5, 5.0, 4.4), fill('salmon', 7.0, 4.6, 4.0),
                                                 fill('avocado', 12.1, 4.4, 4.2, True)],
            press_shape='circle'),
    # 7 is the realistic futomaki that layout 6 is NOT. Layout 6 packs 54.9 U2 of filling (the code
    # samples the avocado as an ELLIPSE; the 58.8 U2 this comment used to claim is the rectangle sum,
    # i.e. it was wrong before this rewrite too) against 51.8 U2 of rice -- 51 % of the cross-section
    # after the 26.08.2026 thickness correction, 59 % before it, never the 64 % once claimed. The nori
    # tears anyway: it has no rice cushion to lie on.
    # A real futomaki carries ~30 % filling with rice all around it. This is the layout the one-turn
    # model of the stand must be checked against -- see ../KINEMATICS.md, "Open discrepancy".
    7: dict(name='futomaki-real', fillings=[fill('tamago', 1.5, 2.4, 2.0), fill('salmon', 3.9, 2.0, 1.6),
                                            fill('cucumber', 5.5, 1.4, 1.4, True),
                                            fill('avocado', 6.8, 2.0, 1.1, True),
                                            fill('shrimp', 8.5, 2.0, 1.6)],
            press_shape='circle'),
}

# ----------------------------------------------------------------------------- materials
# The nori is a MEMBRANE, and what decides whether it survives being dragged is its stiffness per
# unit width, E*w -- not E alone. E = 25 was picked while the band was w = 0.12 thick, i.e. it was
# always shorthand for E*w = 3.0; it is not a sourced modulus (nothing in docs/ cites one).
#
# Writing down the sourced thickness (0.12 -> 0.02 U = 0.1 mm) without touching E therefore divided
# the band's membrane stiffness by six, and the bare far flap -- 5 U of nori with no rice on it --
# stopped being able to drag itself out from under the roll: it severed at s ~ 39 of 42 during the
# final press. Measured on layout 1, --threads 1, all else equal (26.08.2026):
#     T=1.0 w=0.12 L=38.7  E=25   grid 240   gap 0.054  torn False   <- the old reference
#     T=1.4 w=0.02 L=42    E=25   grid 240   gap 1.952  torn TRUE
#     T=1.4 w=0.02 L=38.7  E=25   grid 240   gap 2.093  torn TRUE    <- not the sheet length
#     T=1.4 w=0.02 L=42    E=25   grid 240   gap 2.060  torn TRUE    <- 22k particles, baseline hp:
#                                                                       not the particle spacing
#     T=1.4 w=0.02 L=42    E=25   grid 400   gap 1.088  torn TRUE    <- 1.66x finer grid: not the grid
#     T=1.4 w=0.12 L=42    E=25   grid 240   gap 0.069  torn False   <- thick nori alone is fine
#     T=1.0 w=0.02 L=42    E=25   grid 240   gap 0.072  torn False   <- thin nori alone is fine
#     T=1.4 w=0.02 L=42    E=150  grid 240   gap 0.069  torn False   <- E*w restored: fixed
# So E is tied to w here, and a future thickness edit cannot silently soften the band again.
# OPEN FORK for the owner: this asserts that the correction was bookkeeping -- the band is the same
# physical object, only drawn to its true thickness. The other reading, that real 0.1 mm nori IS six
# times floppier than the model has been assuming, is defensible too, and under it the flap tearing
# is a PREDICTION rather than an artefact. Deciding it needs a measured nori, which we do not have.
# Cost of the fix: dt ~ 1/sqrt(E), so a run is ~2.3x longer (37 s -> 85 s on layout 1).
E_NORI_W = 3.0           # membrane stiffness of the nori band, E*w, in units of E_rice * U
# name: (E, nu, tau_y (shear yield; 1e9 = elastic), rho)
MATERIALS = {
    'rice':     (1.0, 0.35, 0.03, 1.0),
    'nori':     (E_NORI_W / W_NORI, 0.30, 1e9, 2.0),
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

# ----------------------------------------------------------------------------- domain / mat constants
X0, X1 = -2.0, 48.0   # X1 is re-derived from the sheet length in main(); see --sheet
Y0, Y1 = -0.4, 12.6
X_SHEET = 0.0            # near edge of the sheet -- and of the mat: they coincide at t = 0
X_END_EXTRA = 2.0        # hard cap: the contact point never goes past sheet end + this

# --- the mat (makisu) ---------------------------------------------------------------------------
R_MAT_MIN = 0.5          # minimum bend radius of the mat itself (bamboo sticks ~2-3 mm at U = 5 mm).
                         # The working radius R is always far above it; reported as a check.
MAT_BOND = 0.0           # extra kinematic bond of the nori to the mat, ON TOP of the friction.
                         # Default OFF, and that is a result, not a shortcut: MU_MAT = 2 already makes
                         # the mat sticky, and the nori is pinned to it by the rice above, so the sheet
                         # follows the mat with no bond at all. With bond = 0.85 the band is driven at
                         # the mat's rigid rolling field while the roll under it is not quite rigid,
                         # and the mismatch tore holes of 0.36-0.72 U in it (layouts 2 and 4;
                         # measured at T = 1.0, w = 0.12, L = 38.7 -- not re-measured since).
MAT_BOND_D = 0.45        # ... within this distance of the mat surface, U
BOND_TAPER = 0.5         # ... faded in over this much angle at each end of the contact arc, rad
BOND_LAG = 0.15          # ... and only for sheet that has already passed the contact point, U
TAU_V = 1.5              # the hand's speed follows its target with this lag: an instant step from 0 to
                         # v_roll yanks the bonded nori while the rest of the roll stands still
V_LIFT_REF = 0.18        # speed of the contact point during the first turn at --speed 1
V_ROLL_REF = 0.26        # ... and once the roll is rolling forward
T_HOLD_REF = 6.0         # length of the pause after the rice meets the rice at --hold 1
FRONT_CLEAR = 0.35       # while rolling, the mat's leading end is led out to this height above what
                         # still lies ahead (the leading edge is fed out from under the roll). The height is
                         # MEASURED, not assumed: over the bed it is ~H_SHEET, over the bare far flap it
                         # is ~w, and the mat then closes almost the whole way round and presses the
                         # flap onto the roll instead of rolling over it.
V_YAHEAD = 0.5           # ... and it follows the measurement at this rate, U per time unit
FOLD_CLEAR = 0.8         # the first turn clears the tallest filling of the fold zone by this much, U
PACK_AIR = 0.04          # a wound layer is this much thicker than the flat sheet: real turns never
                         # pack perfectly. Without the allowance the geometric spiral is the radius of
                         # the UNDEFORMED area, and the mat then has to compress the rice by exactly the
                         # air between the turns to make it fit (conservation 0.945, measured at
                         # T = 1.0, w = 0.12, L = 38.7 -- needs re-measuring).
CORE_HOLLOW = 0.5        # the crease of the first turn leaves a hollow of about half a sheet thickness.
                         # Not free: with 1.0 the geometric spiral ends at R = 3.77 against the 3.49 that
                         # area conservation allows, and the roll keeps a 6 U2 void in its core for good.
                         # (measured at T = 1.0, w = 0.12, L = 38.7 -- needs re-measuring.)
Y_BED = H_SHEET          # thickness of the sheet lying flat ahead, U
S_FOLD_EMPTY = 5.0       # fold zone of a sheet with no fillings near the edge, U
S_FOLD_MARGIN = 1.0      # s_fold = (end of the fold zone) + this, U
FOLD_REACH = 5.0         # a filling joins the fold zone if it starts within this of the near edge ...
FOLD_GAP = 2.5           # ... or within this of the previous member, U
FOLD_CAP = 0.45          # s_fold never exceeds this fraction of the sheet

# --- fingers: the second kinematic support of the first turn -------------------------------------
# "The other fingers hold the filling from above so it does not slide apart on the first turn."
# A lid over the part of the stack the roll has not reached yet: nothing may rise through it and its
# forward creep is damped. Released the moment the rice meets the rice.
FING_GAP = 1.05          # the lid starts this many R ahead of the contact point (clear of the mat arc)
FING_LID = 0.12          # ... and sits this far above the top of the stack, U. NOTE: the 0.12 is a
                         # clearance in U and has nothing to do with the old W_NORI = 0.12 it happens
                         # to equal -- do not "fix" it to 0.02.
FING_RATE = 3.0          # e-folding rate of the forward creep under the fingers, 1/time

# --- pressure control ----------------------------------------------------------------------------
P_FOLD_FRAC = 0.6        # the first turn is folded gently: this fraction of P_roll
P_ROLL_REF = 0.04        # mat pressure while rolling at --press 1 (units of E_rice)
P_PRESS_REF = 0.04       # ... and during the final squeeze. Not comparable with ../reference's 0.08:
                         # there the pressure was charged over the mat's whole nominal span, here over
                         # the part of it that is really in contact.
P_HOLD_FRAC = 1.6        # the pause after the closing presses harder than plain rolling
L_FLOOR = 0.06           # the pressure is charged over at least this fraction of the span, so that
                         # "nothing is touching yet" reads as "press harder" and not as a 0/0
HUG_FRAC = 0.25          # the final press is not finished until the ring touches this much of its span.
                         # Was 0.40, which is unreachable: measured ceiling of L_contact/L_arc over 21
                         # runs is 0.274 (defaults) and 0.352 (--press 2) -- measured at T = 1.0,
                         # w = 0.12, L = 38.7 -- so `conv` never accumulated
                         # and the press ALWAYS left by t_press_max (duration 46.00-46.01 in all 21).
                         # The "force equilibrium" the README described never fired once.
BAND_W = 3.5             # width of the contact band of the circular mat, in grid cells (-0.5 .. 3)
BAND_W_SQ = 3.0          # ... and of the square press (-0.5 .. 2.5)
V_RADIAL = 0.075         # max radial speed of the mat controller
V_RADIAL_PRESS = 0.06    # ... during the final pressing
# The radius of the FIRST turn is set by the hands, not by a force balance: during phases 1-2 the
# controller is off (e_R = 0). It gets authority only from the pause onwards, and the baseline is
# rebased at every hand-over so R is CONTINUOUS -- a step in R of a few tenths of a U rips the sheet.
E_HOLD = 0.35            # the pause may only compact: e_R in [-E_HOLD, 0]
E_ROLL = 0.50            # while rolling the mat may lag this far inside the geometric spiral ...
E_ROLL_OUT = 0.05        # ... and only this far outside it
R_MIN, R_MAX = 0.8, 8.0
V_YLIFT = 0.08           # rate at which the closed ring is lifted off the table before the press
LIFT_PRESS_MAX = 1.2     # ... but never more than this, or the roll drops out of the bottom of the ring
T_CLOSE = 6.0            # phase 5: closing of the ring to 360 deg
T_PRESS = 8.0            # minimum duration of the final pressing
T_CONV = 3.0             # ... and force equilibrium has to hold this long before it counts
T_PRESS_MAX = 46.0       # give up on force equilibrium after this (circle)
T_PRESS_MAX_SQ = 100.0   # ... and for the SQUARE press (layout 5)
C_EXIT_FRAC = 0.55       # rolling ends when nothing outside the mat is further ahead than this * R
TAIL_TOL = 0.3           # a particle further than this outside the fitted contour counts as "tail outside"
TAIL_FRAC = 0.002        # fraction of particles above which tail_outside becomes True
BG_HOLE_T = 0.35         # a background run shorter than this along a ray is a hole between particles
MAT_GAP_BINS = 180       # angular sectors the nori-to-mat distance is measured in
PRESSED_GAP_MAX = 0.10   # the mat must finish within this of the roll, U (else the press never landed)
PRESSED_CONTACT_MIN = 0.20     # ... and touch this fraction of its span. Circle.
PRESSED_CONTACT_MIN_SQ = 0.08  # ... and this for the SQUARE press: a roundish roll inside a square
                               # touches only the four flats, so the ceiling is structurally lower
                               # (measured 0.115 on layout 5, the only square layout, at T = 1.0,
                               # w = 0.12, L = 38.7 -- needs re-measuring).
GRAVITY = 0.01
MU_TABLE = 0.4
MU_MAT = 2.0             # effectively sticky while pressed against the mat
CFL = 0.3
CORNER_R = 0.6           # corner radius of the square press

# ----------------------------------------------------------------------------- particle sampling (unchanged)
def sample_layout(layout, n_target, seed=1):
    fl = layout['fillings']
    area_rice = (L_SHEET - L_FLAP) * T_RICE
    area_nori = L_SHEET * W_NORI
    rects = []
    y_top = {}   # per filling index: top y (for stacking)
    for i, f in enumerate(fl):
        if f['stack'] and i > 0:
            base_y = y_top[i - 1]
        else:
            base_y = H_SHEET
        rects.append((f['u'], base_y, f['w'], f['h'], f['round'], CLASS_OF_KIND[f['kind']]))
        y_top[i] = base_y + f['h']
    area_fill = sum((math.pi / 4 if r[4] else 1.0) * r[2] * r[3] for r in rects)
    hp = math.sqrt((area_rice + area_nori + area_fill) / n_target)
    xs, cls, vol, nori_row, nori_col = [], [], [], [], []
    rng = np.random.default_rng(seed)
    jit = 0.15 * hp

    # rice: rows across thickness, columns along the sheet
    n_rows = max(2, int(round(T_RICE / hp)))
    dy = T_RICE / n_rows
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

        area  = rice (L - flap)*T_RICE + nori L*w + fillings
        Rout  = sqrt(area/pi);   Rcore = sqrt(s_fold * H_SHEET / pi)
        layers = (Rout - Rcore) / H_SHEET

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

    Crossings vs layers (corrected 26.08.2026). There used to be a "+1 for the tuck" here: the ray
    was assumed to cut the tucked-in near edge on top of every turn. It does not. Once `nori_turns`
    stops counting rasterisation holes as layer boundaries (see `runs_bridged`), the number of nori
    runs a ray meets equals the number of TURNS, with no offset: measured against the turn count read
    straight off the sheet (angle unwrapped by `nori_col`, a source the raster never touches) the
    bridged ray count lands within 0.009..0.102 on all five layouts, while the raw count overshot by
    0.269..0.713. The old +1 offset was cancelling that overshoot, so the two errors hid each other.
    """
    h = H_SHEET
    area = info['area_rice'] + info['area_nori'] + info['area_fill']
    r_out = math.sqrt(area / math.pi)
    r_core = math.sqrt(max(s_fold, 0.0) * h / math.pi)
    layers = (r_out - r_core) / h
    r_core2 = math.sqrt((max(s_fold, 0.0) * h + max(a_fold, 0.0)) / math.pi)
    r_hollow = math.sqrt(r_core2 * r_core2 + h * h)
    layers2 = (r_out - r_hollow) / h
    return dict(area_T2=round(area, 3), Rout_pred_T=round(r_out, 3), Rcore_pred_T=round(r_core, 3),
                layers_predicted=round(layers, 3), crossings_predicted=round(layers, 3),
                a_fold_T2=round(a_fold, 3),
                Rcore_core_T=round(r_core2, 3), Rcore_hollow_T=round(r_hollow, 3),
                layers_predicted_core=round(layers2, 3), crossings_predicted_core=round(layers2, 3))

# ----------------------------------------------------------------------------- simulation
def build(nx, ny, n_part, threads=0):
    import gstaichi as ti
    # --- determinism. P2G (scatter) and the two force accumulators fn/fl are ATOMIC float adds, so a
    #     multi-threaded run sums them in a different order every time and the run is not bit-exact.
    #     Measured (26.08.2026, layout 4 --press 2): two identical multi-threaded runs give roll-IoU
    #     0.878 and rice_under_filling differing by 30-45 %; with one thread the class maps are
    #     bit-identical (IoU 1.000000) at the cost of +51 % wall time. Default stays all cores so the
    #     lab keeps its speed; calibration runs should pass --threads 1.
    kw = dict(cpu_max_num_threads=threads) if threads and threads > 0 else {}
    ti.init(arch=ti.cpu, default_fp=ti.f32, random_seed=1, **kw)
    S = dict()
    S['x'] = ti.Vector.field(2, float, n_part)
    S['v'] = ti.Vector.field(2, float, n_part)
    S['C'] = ti.Matrix.field(2, 2, float, n_part)
    S['F'] = ti.Matrix.field(2, 2, float, n_part)
    S['cls'] = ti.field(ti.i32, n_part)
    S['sarc'] = ti.field(float, n_part)      # arclength of this particle along the sheet (nori only)
    S['vol'] = ti.field(float, n_part)
    S['mass'] = ti.field(float, n_part)
    S['J'] = ti.field(float, n_part)
    S['mu'] = ti.field(float, N_CLASS)
    S['la'] = ti.field(float, N_CLASS)
    S['tauy'] = ti.field(float, N_CLASS)
    S['gv'] = ti.Vector.field(2, float, (nx, ny))
    S['gm'] = ti.field(float, (nx, ny))
    S['fn'] = ti.field(float, ())       # normal force on the mat (this substep)
    S['fl'] = ti.field(float, ())       # ... and how many grid nodes carried it (-> contact length)
    S['esc'] = ti.field(ti.i32, ())     # escaped-particle counter
    x, v, C, F, cls, vol, mass, J = (S[k] for k in ['x', 'v', 'C', 'F', 'cls', 'vol', 'mass', 'J'])
    mu, la, tauy, gv, gm, fn, fl, esc, sarc = (S[k] for k in ['mu', 'la', 'tauy', 'gv', 'gm', 'fn', 'fl', 'esc', 'sarc'])
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
            sarc[p] = gr[p]
            vol[p] = vo[p]
            mass[p] = vo[p] * rho[cl[p]]
            J[p] = 1.0

    @ti.kernel
    def substep(dt: float, xc: float, R: float, Rdot: float, ylift: float, vly: float,
                vc: float, th_lo: float, th_hi: float, shape: ti.i32, mu_mat: float,
                s_c: float, bond: float, dbond: float, fx0: float, fx1: float, fy: float, fdamp: float,
                fon: ti.i32):
        for I in ti.grouped(gm):
            gv[I] = [0.0, 0.0]
            gm[I] = 0.0
        fn[None] = 0.0
        fl[None] = 0.0
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
                    # The mat is a plain circular arc of radius R tangent to the table at (xc, 0):
                    # the sheet lies on its CONCAVE side, so the constraint is one-sided "stay inside".
                    # No spiral pitch is needed here -- the bed still lying ahead passes under the roll
                    # through the front-lower wedge the arc deliberately leaves open (th > th_hi).
                    dsd = r - R
                    if dsd > -0.5 * dx and dsd < 3.0 * dx and th_hi > th_lo:
                        if th >= th_lo and th <= th_hi:
                            sn = ti.sin(th); cs = ti.cos(th)
                            n = ti.Vector([sn, cs])            # inward normal
                            # rolling without slipping: the centre translates at vc, the mat turns at
                            # omega = vc/R, so the material velocity of the mat point at angle th is
                            # vc*(1 - cos th, sin th) plus the radial term of a changing R.
                            vb = ti.Vector([vc, Rdot + vly]) + Rdot * ti.Vector([-sn, -cs]) \
                                 + vc * ti.Vector([-cs, sn])
                            vrel = vv - vb
                            vn = vrel.dot(n)
                            if vn < 0:
                                vt = vrel - vn * n
                                vtn = vt.norm()
                                if vtn > 1e-12:
                                    vt *= ti.max(0.0, 1.0 - mu_mat * (-vn) / vtn)
                                vv = vb + vt
                                fn[None] += gm[I] * (-vn) / dt
                                fl[None] += 1.0
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
                            fl[None] += 1.0
                # --- fingers: the cook's other hand holds the stack of fillings the roll has not
                #     reached yet -- a lid just above the stack (nothing may rise through it) plus a
                #     brake on its forward creep, so the filling is not squeezed out ahead of the roll.
                #     The lid starts FING_GAP*R ahead of the contact point, i.e. clear of the mat arc.
                if fon == 1 and px > fx0 and px < fx1 and py > fy:
                    if vv[1] > 0.0:
                        vv[1] = 0.0
                    vv[0] *= fdamp
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
            # --- the nori RIDES ON the mat. Wherever the band is within `dbond` of the mat surface
            #     it is carried by it (high friction, next to no slip -- KINEMATICS.md 26.08.2026).
            #     This is what removes the free span of sheet the old point grab left hanging in the
            #     air, and with it the accordion: the nori cannot bend tighter than the mat does.
            # ... and only for the nori that has already PASSED the contact point (sarc < s_c). Without
            #     that gate the bond also grabs the sheet still lying flat ahead -- it is within dbond
            #     of the big circle for several T in front of the roll -- and drives it downwards into
            #     the table while its neighbours stand still, which tears the band (0.33 U holes,
            #     measured on the pre-26.08.2026 geometry).
            if bond > 0.0 and cls[p] == CLASS_NORI and th_hi > th_lo and sarc[p] <= s_c - BOND_LAG:
                bdx = x[p][0] - xc
                bdy = x[p][1] - (R + ylift)
                br = ti.sqrt(bdx * bdx + bdy * bdy)
                bth = ti.atan2(-bdx, -bdy)
                if bth < 0:
                    bth += 2.0 * math.pi
                bd = ti.abs(br - R)
                if bth >= th_lo and bth <= th_hi and bd < dbond:
                    sn = ti.sin(bth); cs = ti.cos(bth)
                    # taper the bond at BOTH ends of the arc. A hard edge there is a jump in prescribed
                    # velocity between a bonded particle and its neighbour half a spacing away, and the
                    # band is pulled apart at exactly that point (a 1.2 U hole in the nori, measured
                    # on the pre-26.08.2026 geometry).
                    we = ti.min(1.0, ti.min((bth - th_lo) / BOND_TAPER, (th_hi - bth) / BOND_TAPER))
                    wb = bond * (1.0 - bd / dbond) * ti.max(we, 0.0)
                    vm = ti.Vector([vc * (1.0 - cs) - Rdot * sn, Rdot + vly - Rdot * cs + vc * sn])
                    nv = (1.0 - wb) * nv + wb * vm
                    nC = (1.0 - wb) * nC
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

def runs_bridged(d, seq, c, tol=None):
    """Runs of class c along a ray, with rasterisation holes bridged.

    The class map is a rasterised point cloud: a single physical ribbon of nori is regularly cut into
    two runs by one background pixel between particle stamps. run.py already knows this -- BG_HOLE_T,
    "a background run shorter than this along a ray is a hole between particles" -- and bridges such
    holes when it measures the rice under a filling; it did NOT bridge them when it counted nori runs,
    and the raw count therefore over-reported the turns by 0.27..0.71 (15-29 %) on all five layouts.
    Measured 26.08.2026 (on the PRE-correction geometry T = 1.0, w = 0.12, L = 38.7): 108 of 297
    inter-run gaps were shorter than 0.35 U, median 0.025 U = 1.2 px, while a real gap between turns
    was ~1.14 U; the map is one connected nori component in all five. The answer is flat for a
    bridging tolerance anywhere in 0.05..0.30 U -- the gaps are bimodal. The correction WIDENS the
    valley (a real gap is now ~H_SHEET = 1.42 U) so 0.35 keeps its margin; the median hole scales
    with the pixel size, not with the thickness. Left at 0.35; re-measure to be sure.
    """
    tol = BG_HOLE_T if tol is None else tol
    m = seq == c
    if not m.any():
        return 0
    idx = np.nonzero(m)[0]
    brk = np.nonzero(np.diff(idx) > 1)[0]
    grp = np.split(idx, brk + 1)
    n = 1
    for k in range(1, len(grp)):
        if float(d[grp[k][0]]) - float(d[grp[k - 1][-1]]) > tol:
            n += 1
    return n

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
    """A-priori number of spiral turns: an Archimedean spiral of pitch h = H_SHEET wound from a core of
    area info['area_fill'] until the whole sheet is used. pi*(R^2 - r0^2) = h * L_SHEET, N = (R - r0)/h.
    Depends only on sheet length, rice thickness and filling area - NOT on the kinematics."""
    h = H_SHEET
    r0 = math.sqrt(max(info['area_fill'], 0.0) / math.pi)
    R = math.sqrt(r0 * r0 + h * L_SHEET / math.pi)
    return (R - r0) / h

# ----------------------------------------------------------------------------- wrinkle metric ("accordion")
# The defect the owner found on the phase-B frames: the wrapper band gathers into 2-3 folds instead of
# bending into one arc (../KINEMATICS.md, "accordion"). Measured on the MIDLINE of the nori band:
#   wrinkles  = sign changes of the signed curvature along the band, outside the fold nose
#   amplitude = largest departure of the midline from a local quadratic fit, U
# The midline is smoothed over 3 particles (as specified) and then RESAMPLED at WR_DS along arc length:
# raw particle-to-particle curvature is pure noise (spacing 0.05 U, position noise ~0.005 U gives
# kappa noise ~2 1/U, above any sane threshold), the 0.25 U resampling brings it to ~0.08. The noise
# figures were measured at T = 1.0, w = 0.12, L = 38.7; the particle spacing grows with the sheet
# area, so re-measure before trusting them.
WR_DS = 0.25                        # arc-length step the midline is resampled at, U
WR_KAPPA_MIN = 1.0 / H_SHEET        # 0.704 1/U -- a reversal counts only if it bends TIGHTER than the
                                    # sheet's own thickness; the roll's own core (R ~ 1.3 U) never trips it.
                                    # It was 0.893 1/U while the sheet was 1.12 U thick: the bar is now
                                    # 21 % LOWER, so strictly MORE reversals qualify (see README).
WR_NOSE_T = math.pi * H_SHEET       # arc length of the fold nose that is excluded (a half turn at r = h), U
WR_EDGE_T = 1.0                     # ... and this much at each end of the sheet, U. OPEN QUESTION: if
                                    # this was meant as "one sheet thickness of free end" it should now
                                    # be H_SHEET = 1.42. Left in U pending the owner's call.
WR_FIT_T = 0.9                      # half-window of the local quadratic fit used for the amplitude, U
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
                      is not held: the top layer lengthens by feeding bed through the crease. > 0.5 U is
                      the pulley at work.
    """
    out = dict(wrinkles=0, wrinkles_nonose=0, wrinkles_mat=0, wrinkle_amp_T=0.0, wrinkle_kappa_max=0.0,
               wrinkle_reversals=0, wrinkle_nose_s_T=0.0, wrinkle_len_T=0.0, fold_radius_T=0.0,
               bed_drag_T=0.0, mat_bend_violations=0, mat_bend_violation_len_T=0.0,
               mat_bend_min_R_T=99.0, mat_bend_dist_to_end_T=0.0, mat_bend_limit_R_T=0.0,
               mat_bend_spots=[])
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
    kap = ang / np.maximum(ds, 1e-12)                         # signed curvature, 1/U
    sv = sq[1:len(ang) + 1]
    inner = (sv >= WR_EDGE_T) & (sv <= s0[-1] - WR_EDGE_T)
    kmax = float(np.max(np.abs(kap[inner]))) if inner.any() else float(np.max(np.abs(kap)))
    out['fold_radius_T'] = round(1.0 / kmax, 4) if kmax > 1e-6 else 99.0
    # --- fold nose: the WR_NOSE_T window of arc length that accumulates the most turning. Kept as a
    #     DIAGNOSTIC only (where the tightest turn of the band sits), no longer excluded from any
    #     count. It used to be cut out of `wrinkles`, `wrinkles_mat` and the amplitude fit, and that
    #     was wrong twice over: under the corrected kinematics the sheet is on the mat at every
    #     instant, so there is no hairpin to hide a wrinkle in; and the window is PLACED by argmax of
    #     accumulated |turning|, i.e. it lands by construction on the most bent stretch of the band.
    #     Measured 26.08.2026: opening the window turned the published "zero wrinkles in the final
    #     frame on all five layouts" into 3 / 2 / 1 reversals on layouts 2 / 4 / 5, two of them bent
    #     tighter than the mat's own minimum radius (0.229 U and 0.164 U against R_MAT_MIN = 0.5 U;
    #     measured on the pre-26.08.2026 geometry).
    cum = np.concatenate([[0.0], np.cumsum(np.abs(ang))])
    j = np.minimum(np.searchsorted(sv, sv + WR_NOSE_T), len(sv))
    i0 = int(np.argmax(cum[j] - cum[np.arange(len(sv))]))
    nose_lo, nose_hi = sv[i0], sv[i0] + WR_NOSE_T
    out['wrinkle_nose_s_T'] = round(float(nose_lo), 3)
    ok = (sv >= WR_EDGE_T) & (sv <= s0[-1] - WR_EDGE_T)
    # `wrinkles_nonose` is now the same quantity as `wrinkles`; kept so old comparisons still parse.
    ok_n = ok & (np.abs(kap) >= WR_KAPPA_MIN)
    sgn_n = np.sign(kap[ok_n])
    if len(sgn_n) > 1:
        out['wrinkles_nonose'] = int(np.sum(sgn_n[1:] != sgn_n[:-1]))
    # --- grafted from ../mat-chain: the same count with the threshold the MAT sets rather than the bed.
    #     A reversal is a FOLD of the wrapper only if the sheet is bent tighter than a bamboo stick can
    #     bend (1/R_MAT_MIN = 2.0 1/U).  Anything gentler is the roll's own curvature, which the bed
    #     threshold 1/H_SHEET = 0.704 also catches.  This is the "accordion is impossible by construction"
    #     test of KINEMATICS.md stated as a number: wrinkles_mat > 0 means the nori left the mat.
    sgm = np.sign(kap[ok & (np.abs(kap) >= 1.0 / R_MAT_MIN)])
    if len(sgm) > 1:
        out['wrinkles_mat'] = int(np.sum(sgm[1:] != sgm[:-1]))
    # --- the physics of the mat written down directly, and in a form no window can hide: ANY stretch
    #     of the band bent tighter than the bamboo can bend is a violation, reversal or not. The sheet
    #     rides on the mat, the mat is slats of radius R_MAT_MIN, and the sheet sits half its own
    #     thickness outside them, so the tightest legal midline radius is R_MAT_MIN + w/2 = 0.51 U
    #     (it was 0.56 U while the nori was 0.12 thick: the limit RELAXED by 9 %).
    #     Only the WR_EDGE_T ends are excused (the two free ends of the band are genuinely unsupported).
    r_lim = R_MAT_MIN + 0.5 * W_NORI
    viol = ok & (np.abs(kap) > 1.0 / r_lim)
    out['mat_bend_limit_R_T'] = round(r_lim, 4)
    if viol.any():
        idx = np.nonzero(viol)[0]
        grp = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
        L_band = float(s0[-1])
        out['mat_bend_violations'] = len(grp)
        out['mat_bend_violation_len_T'] = round(float(sum(sv[g[-1]] - sv[g[0]] + WR_DS for g in grp)), 3)
        out['mat_bend_min_R_T'] = round(float(1.0 / np.max(np.abs(kap[viol]))), 4)
        out['mat_bend_dist_to_end_T'] = round(float(min(min(sv[g[0]], L_band - sv[g[-1]]) for g in grp)), 2)
        out['mat_bend_spots'] = [[round(float(sv[g[0]]), 2), round(float(sv[g[-1]]), 2),
                                  round(float(1.0 / np.max(np.abs(kap[g]))), 3),
                                  round(float(min(sv[g[0]], L_band - sv[g[-1]])), 2)] for g in grp]
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
        # (the nose window is no longer cut out here either -- see the note above. Measured effect on
        #  the final frame: amplitude 0.0337 -> 0.1295 U on layout 4 and 0.0352 -> 0.1313 U on layout
        #  5, still under the 0.3 U bar, so the amplitude half of the claim survives the correction.
        #  Measured at T = 1.0, w = 0.12, L = 38.7 -- and note that the 0.3 bar is an absolute length
        #  in U, so against a sheet that is now 27 % thicker it is 21 % less strict in relative terms.)
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
    rout, turns, turns_raw, r_nori_out = [], [], [], []
    for a in angs:
        d, seq = ray_classes(img, c_row, c_col, a, px)
        nz = np.nonzero(seq != CLASS_BG)[0]
        rout.append(d[nz[-1]] if len(nz) else 0.0)
        turns.append(runs_bridged(d, seq, CLASS_NORI))
        turns_raw.append(runs(seq, CLASS_NORI))
        nn = np.nonzero(seq == CLASS_NORI)[0]
        r_nori_out.append(d[nn[-1]] if len(nn) else 0.0)
    rout = np.array(rout)
    # --- shape after the press. docs/simulation-research.md sec.5 asks layout 5 for two numbers the
    #     stand will be compared against: the corner rounding radius of the square and how much of the
    #     square the rice actually fills. Both are read off the class map, not off the mat.
    #       half-side  = half of the axis-aligned bounding box of the material
    #       fill_frac  = material area / (2*half-side)^2
    #       corner_r   = r from r_diag = sqrt2*(a - r) + r, r_diag measured along the four diagonals
    ys_px, xs_px = np.nonzero(fg)
    a_half = 0.5 * max((xs_px.max() - xs_px.min()), (ys_px.max() - ys_px.min())) * px
    r_diag = float(np.mean([rout[i] for i in (4, 13, 22, 31)]))          # 40, 130, 220, 310 deg
    corner_r = (math.sqrt(2.0) * a_half - r_diag) / (math.sqrt(2.0) - 1.0)
    shape_met = dict(square_half_side_T=round(float(a_half), 3),
                     square_fill_frac=round(float(fg.sum()) * px * px / max(4.0 * a_half * a_half, 1e-9), 3),
                     square_corner_radius_T=round(float(min(max(corner_r, 0.0), a_half)), 3),
                     press_shape=extra.get('mat', {}).get('press_shape', 'circle'))
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
    # --- does the nori actually stay ON the mat? The metric that was missing entirely: `nori_max_gap_T`
    #     above is the gap between CONSECUTIVE NORI PARTICLES (a tear test) and says nothing about the
    #     distance from the sheet to the mat, yet the README used to quote it as proof of contact.
    #     The mat here is analytic (a circle of radius R about (xc, y_cen), or a rounded square at the
    #     press), so the honest measure is its signed distance field: for each of MAT_GAP_BINS angular
    #     sectors, how far the nearest nori particle sits inside the mat surface, minus the half
    #     thickness of the outer nori row that contact geometrically requires.
    mat_i = extra.get('mat', {})
    nori_mat = dict(nori_mat_gap_median_T=None, nori_mat_gap_p90_T=None, nori_mat_gap_max_T=None,
                    nori_mat_off_frac=None, nori_mat_off_0p3T_frac=None, nori_mat_contact_ok=None,
                    nori_mat_tol_T=None)
    if mat_i and nori_m.any():
        _xc, _yc = float(mat_i['xc_final']), float(mat_i['y_cen_press'])
        _R, _shape = float(mat_i['R_final']), mat_i.get('press_shape', 'circle')
        dd = xs[nori_m] - np.array([_xc, _yc])
        if _shape == 'circle':
            sd = np.hypot(dd[:, 0], dd[:, 1]) - _R
        else:
            _hs = _R - CORNER_R
            q = np.abs(dd) - _hs
            mq = np.maximum(q, 0.0)
            sd = np.hypot(mq[:, 0], mq[:, 1]) + np.minimum(np.maximum(q[:, 0], q[:, 1]), 0.0) - CORNER_R
        depth = -sd                                            # how far inside the mat surface
        th_b = np.arctan2(dd[:, 1], dd[:, 0])
        bi = np.clip(((th_b + math.pi) / (2 * math.pi) * MAT_GAP_BINS).astype(int), 0, MAT_GAP_BINS - 1)
        per = np.full(MAT_GAP_BINS, np.nan)
        for b in range(MAT_GAP_BINS):
            mb = bi == b
            if mb.any():
                per[b] = depth[mb].min()                       # nearest nori to the mat in this sector
        okb = ~np.isnan(per)
        if okb.any():
            expect = 0.5 * (W_NORI / max(info['nori_rows'], 1))     # centre of the outer row when touching
            free = per[okb] - expect
            tol = 0.5 * info['nori_dx']
            nori_mat = dict(
                nori_mat_gap_median_T=round(float(np.median(free)), 4),
                nori_mat_gap_p90_T=round(float(np.percentile(free, 90.0)), 4),
                nori_mat_gap_max_T=round(float(free.max()), 4),
                nori_mat_off_frac=round(float((free > tol).mean()), 4),
                nori_mat_off_0p3T_frac=round(float((free > 0.3).mean()), 4),
                nori_mat_contact_ok=bool(float((free > 0.3).mean()) == 0.0),
                nori_mat_tol_T=round(float(tol), 4))
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
        Rout_median_T=round(float(np.median(rout)), 3), shape=shape_met,
        R_mat_T=round(extra['R'], 3), R_nori_outer_mean_T=round(float(np.mean(r_nori_out)), 3),
        nori_turns=round(float(np.mean(turns)), 3), nori_turns_min=int(np.min(turns)), nori_turns_max=int(np.max(turns)),
        nori_turns_raw=round(float(np.mean(turns_raw)), 3),   # unbridged, i.e. the old (hole-inflated) value
        nori_turns_geom=round(turns_geom(info), 3),
        turns_minus_predicted=round(float(np.mean(turns)) - extra['pred']['crossings_predicted'], 3),
        turns_match_formula=bool(abs(float(np.mean(turns)) - extra['pred']['crossings_predicted']) <= 0.25),
        turns_minus_predicted_core=round(float(np.mean(turns)) - extra['pred']['crossings_predicted_core'], 3),
        turns_match_formula_core=bool(abs(float(np.mean(turns)) - extra['pred']['crossings_predicted_core']) <= 0.25),
        # --- the "accordion" defect (KINEMATICS.md, 26.08.2026): curvature reversals of the wrapper
        #     band outside the fold nose. With a real mat the target is STRICT: zero wrinkles at every
        #     phase and amplitude below 0.3 U. A wrinkle now means the nori came off the mat.
        wrinkles=int(extra['wr']['final']['wrinkles']),
        wrinkles_max=int(extra['wr']['wrinkles_max']), wrinkles_max_phase=extra['wr']['wrinkles_max_phase'],
        wrinkles_mat=int(extra['wr']['final']['wrinkles_mat']),
        wrinkles_mat_max=int(extra['wr']['wrinkles_mat_max']),
        wrinkle_amp_T=float(extra['wr']['final']['wrinkle_amp_T']),
        wrinkle_amp_max_T=float(extra['wr']['wrinkle_amp_max_T']),
        wrinkle_amp_max_phase=extra['wr']['wrinkle_amp_max_phase'],
        wrinkle_kappa_max=float(extra['wr']['final']['wrinkle_kappa_max']),
        fold_radius_min_T=float(extra['wr']['fold_radius_min_T']),
        bed_drag_max_T=float(extra['wr']['bed_drag_max_T']),
        wrinkles_by_phase=extra['wr']['by_phase'],
        wrinkle_ok=bool(extra['wr']['wrinkles_max'] == 0 and extra['wr']['wrinkle_amp_max_T'] < 0.3),
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
        # `nori_particle_gap_T` is the largest gap between CONSECUTIVE NORI PARTICLES -- a tear test,
        # nothing to do with the mat. `nori_max_gap_T` is the same number under its old (misleading)
        # name, kept because ../judge.py and ../reference/table.py read it across every variant.
        nori_particle_gap_T=round(max_gap, 4),
        nori_max_gap_T=round(max_gap, 4), nori_particle_spacing_T=round(info['nori_dx'], 4), nori_torn=bool(torn),
        **nori_mat,
        nori_components_map=int(ncomp), nori_components_map_ge20px=big,
        v_max_final=round(vmax, 4), finite=finite, stable=bool(stable),
        window_T=extra['window_T'], px_T=round(px, 5), window_center_xy=[round(center[0], 3), round(center[1], 3)],
        centroid_xy=[round(cen_world[0], 3), round(cen_world[1], 3)],
        mat=extra['mat'], fingers=extra['fingers'], phases=extra['phases'], timing=extra['timing'],
    )
    return met

def vol_of(cls, c, info):
    return 0.0  # placeholder, replaced below via closure in main (area from particle volumes)

# ----------------------------------------------------------------------------- mat geometry
def gather_R(xnp, xc, ycen, shape, pct=99.5, must=None):
    """Radius the closing mat needs so that everything -- the tail included -- ends up INSIDE it.

    The centre is given (xc, ycen) and is the roll's own centroid, NOT the point where a circle would
    touch the table. That matters: ../reference gathered a circle tangent to the table, for which a
    particle lying ON the table a distance d off the tangency needs R = d^2/(2y) -- unbounded as
    y -> 0. A roll resting on the table always has such particles, so the gather ran into R_MAX (8 U)
    around a roll of Rout = 4, and the press then had 4 U of empty travel to make.

    shape 0: circle, R = |P - C|.   shape 1: rounded square of half-side R, R = max(|dx|, |dy|).
    `must` is a mask of particles that may NOT be left outside at any percentile -- the WRAPPER: a
    crumb of rice outside the mat is a crumb, a loose flap of nori is a defect.
    """
    ddx = xnp[:, 0] - xc
    ddy = xnp[:, 1] - ycen
    need = np.hypot(ddx, ddy) if shape == 0 else np.maximum(np.abs(ddx), np.abs(ddy))
    r_need = float(np.percentile(need, pct))
    if must is not None and must.any():
        r_need = max(r_need, float(np.percentile(need[must], 99.9)))
    return float(min(R_MAX, max(R_MIN, 1.03 * r_need)))

# ----------------------------------------------------------------------------- main
def main():
    global L_SHEET, X1
    ap = argparse.ArgumentParser()
    ap.add_argument('--layout', type=int, default=1)
    ap.add_argument('--sheet', type=float, default=42.0,
                    help='sheet length, U (default %(default)s = 21 cm nori). Note: layout 3 pins its filling '
                         'position at import time and is not rescaled by this flag.')
    ap.add_argument('--speed', type=float, default=1.0, help='speed of the rolling hand (phases 1-4)')
    ap.add_argument('--press', type=float, default=1.0, help='pressure of the mat')
    ap.add_argument('--tuck', type=float, default=1.0,
                    help='how far the near end of the mat is carried on the first turn: 0.6 stops short '
                         'of the far rice line, 1.0 lands exactly on it, 1.3 presses into it')
    ap.add_argument('--hold', type=float, default=1.0,
                    help='pause after the rice meets the rice (1 = %.0f time units, 0 = no pause)' % T_HOLD_REF)
    ap.add_argument('--fingers', type=float, default=1.0,
                    help='the other hand: 1 = the fingers hold the stack of fillings from above until the '
                         'rice meets the rice, 0 = no fingers')
    ap.add_argument('--bond', type=float, default=MAT_BOND,
                    help='how tightly the nori is carried by the mat (1 = no slip at all)')
    ap.add_argument('--seed', type=int, default=1, help='RNG seed of the particle jitter')
    ap.add_argument('--threads', type=int, default=0,
                    help='CPU threads for the solver (0 = all cores; 1 = bit-reproducible, ~+50%% time)')
    ap.add_argument('--grid', type=int, default=240, help='total grid nodes ~ grid^2 (aspect follows the domain)')
    ap.add_argument('--particles', type=int, default=16000)
    ap.add_argument('--out', type=str, default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out'))
    ap.add_argument('--frames', type=int, default=10, help='number of debug snapshots (0 = none)')
    ap.add_argument('--window', type=float, default=12.0, help='material map window side, U')
    ap.add_argument('--tag', type=str, default='')
    # accepted so the older command lines keep working; the real mat has no such knobs
    ap.add_argument('--pitch', type=float, default=1.0, help=argparse.SUPPRESS)
    ap.add_argument('--fold', type=str, default='mat', help=argparse.SUPPRESS)
    ap.add_argument('--anchor', type=float, default=0.0, help=argparse.SUPPRESS)
    ap.add_argument('--bend', type=float, default=0.0, help=argparse.SUPPRESS)
    args = ap.parse_args()
    L_SHEET = args.sheet
    X1 = X_SHEET + L_SHEET + 9.3     # the roll must stay inside the box: 51.3 for the default 42 U sheet
    layout = LAYOUTS[args.layout]
    os.makedirs(args.out, exist_ok=True)
    tag = f'{args.layout}{args.tag}'
    tuck = min(1.3, max(0.6, args.tuck))
    fingers = min(1.0, max(0.0, args.fingers))
    bond = min(1.0, max(0.0, args.bond))

    aspect = (X1 - X0) / (Y1 - Y0)
    ny = int(round(args.grid / math.sqrt(aspect)))
    nx = int(round(ny * aspect))
    xs, cls, vol, nori_row, nori_col, info = sample_layout(layout, args.particles, args.seed)
    n = len(cls)

    # ---------------- geometry of the mat --------------------------------------------------------
    # Only the fillings lying close to the near edge end up inside the first turn (fold_zone).
    s_fold, fold_rects, a_fold = fold_zone(info)
    h_top = max((r[1] + r[3] for r in fold_rects), default=H_SHEET)
    h_sheet = H_SHEET
    # Radius of the FIRST TURN. The mat has to go around the stack of fillings, so the circle it
    # closes on must hold them (plus the hollow the crease leaves) inside a wall one sheet thick.
    # It is a hand-set radius, not a force-controlled one: this is what the cook's fingers do.
    R_fold = max(R_MAT_MIN + h_sheet,
                 h_sheet + math.sqrt(max(a_fold, 0.0) / math.pi + (CORE_HOLLOW * h_sheet) ** 2),
                 0.5 * h_top + FOLD_CLEAR)

    def phi_land(Rr, y):
        """Angle at which the DESCENDING (front) branch of the mat arc is at height y."""
        c = 1.0 - min(max(y / max(Rr, 1e-6), 0.0), 2.0)
        return 2.0 * math.pi - math.acos(min(1.0, max(-1.0, c)))

    # ... and the first turn cannot enclose more area than the material that goes INTO it. This is
    # the one lesson of ../mat-chain worth keeping (there the loop radius was likewise clamped by area
    # conservation). Without the cap a tall stack at the near edge -- layout 5, h_top = 6.1 U -- makes
    # the clearance term 0.5*h_top + FOLD_CLEAR ask for a circle the sheet cannot fill: the core comes
    # out hollow by ~16 U2, the wrapper bridges the void, and the press then crumples it inwards. That
    # is where every wrinkle of layout 5 came from.
    #     material entering the first turn = a_fold + s_close*h_sheet,   s_close = R*phi_meet
    #     closed first turn encloses       = pi*R^2
    # phi_meet itself depends on R, so iterate; PACK_AIR is the same inter-turn air the spiral allows.
    R_cap = R_fold
    for _ in range(4):
        phi_c = min(2.0 * math.pi - 0.05, math.pi + tuck * (phi_land(R_cap, Y_BED) - math.pi))
        b_cap = phi_c * h_sheet * (1.0 + PACK_AIR)
        R_cap = (b_cap + math.sqrt(b_cap * b_cap + 4.0 * math.pi * max(a_fold, 0.0) * (1.0 + PACK_AIR))) \
            / (2.0 * math.pi)
    R_fold_want = R_fold
    R_fold = max(R_MAT_MIN + h_sheet, min(R_fold, R_cap))
    # When the cap bites, the loop closes BELOW the top of the stack: the stack is being squashed as
    # the turn shuts, and the near end has to be carried correspondingly further to still land on the
    # far rice line instead of hooking back into the core. Carry it in proportion to how much the loop
    # was shrunk. Where the cap does not bite (layouts 1-4) this is exactly 1 and changes nothing.
    tuck_eff = min(1.3, max(0.6, tuck * min(1.3, R_fold_want / max(R_fold, 1e-6))))

    phi_meet0 = phi_land(R_fold, Y_BED)          # near rice line lands exactly on the far rice line
    phi_meet = min(2.0 * math.pi - 0.05, math.pi + tuck_eff * (phi_meet0 - math.pi))
    s_close_pred = R_fold * phi_meet
    # sheet left over after the first turn -> the radius the spiral should end at
    a_rest = (max(0.0, (L_SHEET - L_FLAP) - s_close_pred) * h_sheet + L_FLAP * W_NORI) * (1.0 + PACK_AIR)
    R_end_pred = math.sqrt(R_fold * R_fold + a_rest / math.pi)
    pred = predict_layers(info, s_fold, a_fold)
    layers_close = (pred['Rout_pred_T'] - R_fold) / h_sheet

    S = build(nx, ny, n, threads=getattr(args, 'threads', 0))
    dx = S['dx']
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
    # per-particle arclength along the sheet: for the nori band it is simply its initial x, because
    # the mat, the nori and the table all coincide at t = 0 (near edges flush).
    s0_np = np.where(nori_col >= 0, (nori_col.astype(np.float64) + 0.5) * info['nori_dx'], 1e9).astype(np.float32)
    S['init_particles'](xs.astype(np.float32), cls.astype(np.int32), vol.astype(np.float32), rho, s0_np)
    dt = CFL * dx / cmax
    v_lift = V_LIFT_REF * args.speed
    v_roll = V_ROLL_REF * args.speed
    t_hold = T_HOLD_REF * max(args.hold, 0.0)
    x_end = X_SHEET + L_SHEET + X_END_EXTRA
    fdamp = math.exp(-FING_RATE * fingers * dt)
    W_roll = GRAVITY * float(np.sum(vol * rho[cls]))     # weight of everything, carried by the lifted ring

    t_lift = s_close_pred / max(v_lift, 1e-6)
    t_rollmax = max(0.0, L_SHEET + 2.0 - s_close_pred) / max(v_roll, 1e-6)
    t_press_max = T_PRESS_MAX_SQ if layout['press_shape'] == 'square' else T_PRESS_MAX
    t_total_max = t_lift + t_hold + t_rollmax + T_CLOSE + t_press_max
    n_steps_max = int(math.ceil(t_total_max / dt))

    # w/dx and T_RICE/dx are printed on every run: since 26.08.2026 the nori is 0.1 mm = 0.02 U,
    # i.e. a FIFTH of a grid cell, and both its particle rows sit inside one cell. Anything measured
    # on the nori band (wrinkles, mat_bend_*, nori_mat_gap_*) is measured on a sub-cell object.
    print(f'resolution: w_nori/dx={W_NORI / dx:.3f} cells, T_rice/dx={T_RICE / dx:.2f} cells, '
          f'w_nori/hp={W_NORI / info["hp"]:.3f}', flush=True)
    print(f'grid {nx}x{ny} dx={dx:.4f} particles={n} hp={info["hp"]:.4f} nori rows={info["nori_rows"]} '
          f'dt={dt:.5f} cmax={cmax:.2f} v_lift={v_lift:.3f} v_roll={v_roll:.3f}\n'
          f'mat: R_fold={R_fold:.3f} (want {R_fold_want:.3f}, area cap {R_cap:.3f}, '
          f'>= R_mat_min {R_MAT_MIN}) tuck_eff={tuck_eff:.3f} phi_meet={phi_meet:.3f} rad '
          f'({math.degrees(phi_meet):.0f} deg) s_close~{s_close_pred:.2f} U  R_end_pred={R_end_pred:.3f} '
          f'bond={bond} fingers={fingers} hold={t_hold:.1f}\n'
          f'fold zone: {[r[5] for r in fold_rects]} s_fold={s_fold:.2f} a_fold={a_fold:.2f} h_top={h_top:.2f} | '
          f'predicted from area: Rout={pred["Rout_pred_T"]} layers={pred["layers_predicted"]} '
          f'crossings={pred["crossings_predicted"]} | first-turn core: layers={layers_close:.2f} '
          f'crossings={layers_close + 1:.2f} | steps<={n_steps_max}', flush=True)

    rice_map0 = raster_class_area(xs, cls, info['hp'], W_NORI / info['nori_rows'], args.window / 600.0, CLASS_RICE)

    # ---------------- state ----------------------------------------------------------------------
    shape = 0 if layout['press_shape'] == 'circle' else 1
    frames_dir = os.path.join(args.out, f'frames_{tag}')
    if args.frames:
        os.makedirs(frames_dir, exist_ok=True)
        for f in os.listdir(frames_dir):
            if f.endswith('.png'):
                os.remove(os.path.join(frames_dir, f))
    snap_every = max(1, n_steps_max // max(args.frames, 1))
    t0 = time.time()
    log = []
    t = 0.0
    ctrl_every = 8
    phase = 'lift'; last_phase = 'lift'; t_phase = 0.0
    s_c = 0.0                     # arclength of the mat that has passed the contact point
    v_now = 0.0
    xc = X_SHEET                  # contact point of the mat with the table
    R = R_fold; e_R = 0.0; Rdot = 0.0; Rdot_eff = 0.0; F_f = 0.0; L_f = 0.0; conv = 0.0
    R_b = R_fold                  # geometric baseline radius
    tau_f = 0.5
    ylift = 0.0; vly = 0.0
    th_lo, th_hi = 0.0, 0.0
    shp = 0
    err_last = 1.0
    s_close_act = None; R_close_act = None
    y_ahead = Y_BED; y_ahead_tgt = Y_BED     # height of what still lies flat ahead of the roll
    y_cen_press = 0.0                        # centre height of the closed ring (set at the gather)
    rice_idx = np.nonzero(cls == CLASS_RICE)[0]
    nori_mask = (cls == CLASS_NORI)
    phase_marks = {'lift': 0.0}
    wr_hist = []
    wr_phase = {}
    nori_x0 = np.where(nori_col >= 0, (nori_col.astype(np.float64) + 0.5) * info['nori_dx'], -1.0)

    def wr_sample(ph, tt):
        w = wrinkle_metric(S['x'].to_numpy(), nori_row, nori_col, info['nori_rows'], nori_x0, s_fold)
        # --- how hard is the rice being squashed, RIGHT NOW? (KINEMATICS.md, owner's finding of
        #     26.08.2026 13:25: wrinkles are the symptom, crushed rice is the disease. Boiled rice is
        #     ~70 % water and gives up only the air between the grains, 5-15 %, so J below ~0.88 at ANY
        #     moment means the model let the roll collapse and the nori had to fold the slack away.)
        Jr = S['J'].to_numpy()[rice_idx]
        w['rice_J_mean'] = round(float(Jr.mean()), 4)
        w['rice_J_p05'] = round(float(np.percentile(Jr, 5.0)), 4)
        w['t'] = round(tt, 2); w['phase'] = ph
        wr_hist.append(w)
        cur = wr_phase.get(ph)
        if cur is None or (w['wrinkles'], w['wrinkle_amp_T']) > (cur['wrinkles'], cur['wrinkle_amp_T']):
            wr_phase[ph] = w
        return w

    step = 0
    while True:
        # ---------------- 1. schedule: how fast the contact point travels -------------------------
        v_cmd = 0.0
        if phase in ('lift', 'close'):
            v_cmd = v_lift
        elif phase == 'roll':
            v_cmd = v_roll
        v_now += (v_cmd - v_now) * min(1.0, dt / TAU_V)
        s_c += v_now * dt
        if phase not in ('ring', 'press'):
            xc += v_now * dt                  # rolling without slipping: ds_c/dt = dxc/dt


        # ---------------- 2. radius --------------------------------------------------------------
        R_prev = R
        if phase in ('lift', 'close', 'hold'):
            R = min(max(R_b + e_R, max(R_MIN, R_MAT_MIN)), R_MAX)
        elif phase == 'roll':
            # Archimedean spiral: one more turn adds one sheet thickness. dR/ds = h(s)/(2 pi R),
            # integrated exactly as R^2 += h ds / pi. h is the bed ahead, or bare nori over the flap.
            hh = (h_sheet if s_c < (L_SHEET - L_FLAP) else W_NORI) * (1.0 + PACK_AIR)
            if s_c <= L_SHEET:
                R_b = math.sqrt(max(R_b * R_b + hh * v_now * dt / math.pi, 1e-6))
            R = min(max(R_b + e_R, max(R_MIN, R_MAT_MIN)), R_MAX)
        else:                                  # ring / press: the controller owns R outright
            R = min(max(R + Rdot * dt, R_MIN), R_MAX)
        Rdot_eff = (R - R_prev) / dt

        ylift_prev = ylift
        if phase in ('ring', 'press'):
            # the ring stays centred on the roll: centre = (xc, y_cen). As R shrinks the ring lifts off
            # the table on its own, which is what LIFT_PRESS used to do by hand.
            ylift = min(max(y_cen_press - R, 0.0), LIFT_PRESS_MAX)
        else:
            ylift += max(-V_YLIFT * dt, min(V_YLIFT * dt, 0.0 - ylift))
        vly = (ylift - ylift_prev) / dt

        # ---------------- 3. wrapped arc ---------------------------------------------------------
        # Phi = s_c / R while the first turn is being made; afterwards the leading end of the mat is
        # led out from under the roll, so the arc stops where it would otherwise scoop the bed ahead.
        th_lo = 0.0
        if phase in ('lift', 'close'):
            th_hi = min(phi_meet, s_c / max(R, 1e-6))
            shp = 0
        elif phase == 'hold':
            th_hi = min(phi_meet, s_c / max(R, 1e-6))
            shp = 0
        elif phase == 'roll':
            y_ahead += max(-V_YAHEAD * dt, min(V_YAHEAD * dt, y_ahead_tgt - y_ahead))
            th_hi = min(s_c / max(R, 1e-6), phi_land(R, y_ahead + FRONT_CLEAR))
            shp = 0
        elif phase == 'ring':
            th_hi = 2.0 * math.pi
            shp = 0
        else:
            th_hi = 2.0 * math.pi
            shp = shape

        # ---------------- 4. fingers -------------------------------------------------------------
        fx0 = xc + FING_GAP * R
        fx1 = s_fold + 0.5
        fy = h_top + FING_LID
        fon = 1 if (fingers > 0.0 and phase in ('lift', 'close') and fx1 > fx0) else 0

        # ---------------- 5. one MPM step --------------------------------------------------------
        S['substep'](dt, xc, R, Rdot_eff, ylift, vly, v_now, th_lo, th_hi, shp, MU_MAT,
                     s_c, bond, MAT_BOND_D, fx0, fx1, fy, fdamp, fon)

        # ---------------- 6. pressure controller -------------------------------------------------
        if phase in ('lift', 'close'):
            P_ref = P_FOLD_FRAC * P_ROLL_REF * args.press
        elif phase == 'hold':
            P_ref = P_HOLD_FRAC * P_ROLL_REF * args.press
        elif phase == 'roll':
            P_ref = P_ROLL_REF * args.press
        elif phase == 'ring':
            f = min(1.0, t_phase / T_CLOSE)
            P_ref = (P_ROLL_REF + f * (P_PRESS_REF - P_ROLL_REF)) * args.press
        else:
            P_ref = P_PRESS_REF * args.press
        tau_f = 1.5 if phase in ('ring', 'press') else 0.5
        fnow = S['fn'][None]
        F_f += (fnow - F_f) * min(1.0, dt / tau_f)
        # Contact LENGTH, measured, not assumed: each contacting node stands for dx^2 of a band that is
        # BAND_W*dx wide. A rigid arc laid on a roll that is never perfectly round touches over a
        # fraction of its span; charging the hand's pressure over the WHOLE span (../reference's
        # convention) makes the controller squeeze until the local pressure is several times the
        # nominal one -- measured J = 0.91 at the rolling stage alone. P_ref is a real pressure here.
        L_c = S['fl'][None] * dx / (BAND_W if shp == 0 else BAND_W_SQ)
        L_f += (L_c - L_f) * min(1.0, dt / tau_f)
        if step % ctrl_every == 0:
            arc_len = R * max(th_hi - th_lo, 0.0) if shp == 0 else 8 * R
            F_t = P_ref * max(L_f, L_FLOOR * arc_len)
            # Once the ring is closed and lifted off the table it carries the roll's own WEIGHT, and
            # that alone balances a small target: the controller then stalls with the mat 0.6 U off
            # the roll and calls it equilibrium. The press is a squeeze, so weigh it net.
            F_net = F_f - (W_roll if phase in ('ring', 'press') else 0.0)
            err = (max(F_net, 0.0) - F_t) / max(F_t, 1e-6)
            err_last = err
            # the force reading is noisy, so "equilibrium" has to HOLD, not just happen once: a single
            # spike used to stop the press with the mat still 1.3 U off the roll (Rout 4.38 vs 3.49)
            # ... and, during the final press, the ring must actually HUG the roll: with a contact of
            # 8 % of the span the target P*L_contact is met by the roll's own weight resting in the
            # ring, and the press would stop with the mat 0.6 U off the roll.
            hug = (phase != 'press') or (L_f >= HUG_FRAC * arc_len)
            conv = conv + ctrl_every * dt if (abs(err) < 0.08 and hug) else 0.0
            vrad = V_RADIAL_PRESS if phase in ('ring', 'press') else V_RADIAL
            Rdot = vrad * max(-1.0, min(1.0, err))
            # The closing ring and the press are MONOTONE: a hand that presses never lets go. Without
            # this the controller reads the roll's own weight resting in an oversized ring as
            # over-pressure and opens out for ever (measured: R ran away from 5.7 to 7.2).
            if phase in ('ring', 'press'):
                Rdot = min(Rdot, 0.0)
            if R <= R_MIN and Rdot < 0: Rdot = 0.0
            if R >= R_MAX and Rdot > 0: Rdot = 0.0
        if phase == 'hold':
            e_R = min(max(e_R + Rdot * dt, -E_HOLD), 0.0)
        elif phase == 'roll':
            # the mat may lag INSIDE the geometric spiral but not run outside it: R_b already is the
            # area-conserving radius, and any slack left here has to be squeezed out by the final
            # press, which an inextensible wrapper can only follow by buckling (that is where every
            # wrinkle of the run came from -- see README).
            e_R = min(max(e_R + Rdot * dt, -E_ROLL), E_ROLL_OUT)
        t += dt; t_phase += dt

        # ---------------- 7. phase transitions ---------------------------------------------------
        if phase == 'lift' and th_hi >= math.pi:
            phase = 'close'; t_phase = 0.0; phase_marks['close'] = t
        elif phase == 'close' and th_hi >= phi_meet - 1e-9:
            phase = 'hold'; t_phase = 0.0; phase_marks['hold'] = t
            R_b = R; e_R = 0.0; Rdot = 0.0
        elif phase == 'hold' and t_phase >= t_hold:
            phase = 'roll'; t_phase = 0.0; phase_marks['roll'] = t
            s_close_act = s_c; R_close_act = R
            R_b = R; e_R = 0.0; Rdot = 0.0
        elif phase == 'roll' and step % 200 == 0:
            xnp = S['x'].to_numpy()
            # how tall is what still lies flat AHEAD of the roll's own footprint? (bed, flap, or nothing)
            band = (xnp[:, 0] > xc + 1.05 * R) & (xnp[:, 0] < xc + 2.6 * R)
            y_ahead_tgt = float(np.percentile(xnp[band, 1], 98.0)) if band.sum() > 20 else W_NORI
            y_ahead_tgt = min(max(y_ahead_tgt, W_NORI), 4.0)
            d = np.hypot(xnp[:, 0] - xc, xnp[:, 1] - (R + ylift))
            outs = d > R + 0.5
            ahead = float((xnp[outs, 0] - xc).max()) if outs.any() else -1e9
            if (ahead < C_EXIT_FRAC * R and s_c > L_SHEET - 0.5) or xc >= x_end:
                phase = 'ring'; t_phase = 0.0; phase_marks['ring'] = t
                xc = float(xnp[:, 0].mean())
                y_cen_press = float(xnp[:, 1].mean())
                R = gather_R(xnp, xc, y_cen_press, 0, must=nori_mask)
                Rdot = 0.0; e_R = 0.0
        elif phase == 'ring' and t_phase >= T_CLOSE:
            phase = 'press'; t_phase = 0.0; phase_marks['press'] = t
            if shape == 1:
                xnp = S['x'].to_numpy()
                xc = float(xnp[:, 0].mean())
                y_cen_press = float(xnp[:, 1].mean())
                R = gather_R(xnp, xc, y_cen_press, 1, must=nori_mask)
                Rdot = 0.0
        gp = (xc - R * math.sin(th_hi), ylift + R * (1.0 - math.cos(th_hi)))
        if phase == 'press' and t_phase >= T_PRESS and (conv >= T_CONV or t_phase >= t_press_max):
            phase_marks['end'] = t
            if args.frames:
                save_frame(S, cls, xc, R, th_lo, th_hi, shp,
                           os.path.join(frames_dir, f'f{step:07d}_{phase}.png'), t, F_f, gp, 1, ylift=ylift)
            break

        if step % WR_EVERY == 0 or phase != last_phase:
            wr_sample(phase, t)
        if step % 400 == 0:
            log.append(dict(t=round(t, 2), ph=phase, xc=round(xc, 3), sc=round(s_c, 3), R=round(R, 3),
                            hi=round(th_hi, 3), F=round(F_f, 4), Fn=round(F_f - (W_roll if phase in ('ring', 'press') else 0.0), 4),
                            Lc=round(L_f, 3),
                            Larc=round(R * max(th_hi - th_lo, 0.0), 3),
                            Ft=round(P_ref * max(L_f, L_FLOOR * (R * max(th_hi - th_lo, 0.0) if shp == 0 else 8 * R)), 4)))
        if phase != last_phase:
            _xp = S['x'].to_numpy(); _g = 0.0; _at = 0.0
            for _r in range(info['nori_rows']):
                _m = nori_row == _r; _o = np.argsort(nori_col[_m]); _p = _xp[_m][_o]
                _gg = np.linalg.norm(np.diff(_p, axis=0), axis=1)
                if _gg.max() > _g:
                    _g = float(_gg.max()); _at = float(nori_col[_m][_o][int(np.argmax(_gg))]) / info['nori_cols'] * L_SHEET
            print(f'  -> phase {phase} at t={t:.1f}  s_c={s_c:.2f} Phi={th_hi:.2f} R={R:.3f}  '
                  f'nori max gap={_g:.3f} U at s={_at:.1f} U', flush=True)
        if args.frames and (phase != last_phase or step % snap_every == 0):
            save_frame(S, cls, xc, R, th_lo, th_hi, shp,
                       os.path.join(frames_dir, f'f{step:07d}_{phase}.png'), t, F_f, gp, 1, ylift=ylift,
                       fbox=(fx0, fx1, fy) if fon else None)
        last_phase = phase
        if step % 2000 == 0:
            el = time.time() - t0
            print(f'  step {step} t={t:.1f} [{phase}] xc={xc:.2f} s_c={s_c:.2f} R={R:.3f} Phi={th_hi:.2f} '
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
              wrinkles_nonose_max=int(max(w['wrinkles_nonose'] for w in wr_hist)),
              wrinkles_mat_max=int(max(w['wrinkles_mat'] for w in wr_hist)),
              mat_bend_violations_max=int(max(w['mat_bend_violations'] for w in wr_hist)),
              mat_bend_violations_max_phase=max(wr_hist, key=lambda w: w['mat_bend_violations'])['phase'],
              mat_bend_min_R_run_T=round(float(min(w['mat_bend_min_R_T'] for w in wr_hist)), 4),
              mat_bend_violation_len_max_T=round(float(max(w['mat_bend_violation_len_T'] for w in wr_hist)), 3),
              mat_bend_samples_with_violation=int(sum(1 for w in wr_hist if w['mat_bend_violations'])),
              wrinkle_amp_max_T=float(wr_amp_max['wrinkle_amp_T']), wrinkle_amp_max_phase=wr_amp_max['phase'],
              fold_radius_min_T=round(min(w['fold_radius_T'] for w in wr_hist if w['fold_radius_T'] > 0), 4),
              bed_drag_max_T=round(max(w['bed_drag_T'] for w in wr_hist), 3),
              rice_J_min_run=round(min(w['rice_J_mean'] for w in wr_hist if 'rice_J_mean' in w), 4),
              rice_J_min_run_phase=min((w for w in wr_hist if 'rice_J_mean' in w),
                                       key=lambda w: w['rice_J_mean'])['phase'],
              rice_J_p05_min_run=round(min(w['rice_J_p05'] for w in wr_hist if 'rice_J_p05' in w), 4),
              by_phase={k: dict(wrinkles=v['wrinkles'], nonose=v['wrinkles_nonose'], mat=v['wrinkles_mat'],
                                amp_T=v['wrinkle_amp_T'],
                                kappa=v['wrinkle_kappa_max'], r_fold_T=v['fold_radius_T'],
                                drag_T=v['bed_drag_T'], t=v['t'])
                        for k, v in wr_phase.items()},
              samples=len(wr_hist), hist=[dict(t=w['t'], ph=w['phase'], w=w['wrinkles'],
                                               wn=w['wrinkles_nonose'], wm=w['wrinkles_mat'],
                                               a=w['wrinkle_amp_T'],
                                               rf=w['fold_radius_T'], dg=w['bed_drag_T']) for w in wr_hist])
    print(f"wrinkles: max {wr['wrinkles_max']} at t={wr['wrinkles_max_t']} ({wr['wrinkles_max_phase']}), "
          f"no-nose max {wr['wrinkles_nonose_max']}, mat-threshold max {wr['wrinkles_mat_max']}, "
          f"amp max {wr['wrinkle_amp_max_T']:.3f} U "
          f"({wr['wrinkle_amp_max_phase']}), final {wr_final['wrinkles']}; "
          f"r_fold min {wr['fold_radius_min_T']:.3f} U, bed drag max {wr['bed_drag_max_T']:.2f} U; "
          f"rice J min {wr['rice_J_min_run']:.3f} ({wr['rice_J_min_run_phase']}); "
          f"mat-bend violations max {wr['mat_bend_violations_max']} "
          f"({wr['mat_bend_violations_max_phase']}, {wr['mat_bend_samples_with_violation']}/{len(wr_hist)} samples), "
          f"tightest R {wr['mat_bend_min_R_run_T']:.3f} U", flush=True)

    # ---- outputs
    center = (xs_f[:, 0].mean(), xs_f[:, 1].mean())
    img, px = rasterize(xs_f, cls, info['hp'], W_NORI / info['nori_rows'], center, args.window, 600)
    # rasterize() drops whatever falls outside the window WITHOUT a word, and every map-derived metric
    # (Rout_T, nori_turns, rice_area_map_T2, shape.*) then measures a clipped roll. Count it.
    _half = args.window / 2.0
    _rout_win = int(np.sum((np.abs(xs_f[:, 0] - center[0]) > _half) | (np.abs(xs_f[:, 1] - center[1]) > _half)))
    np.save(os.path.join(args.out, f'material_{tag}.npy'), img)
    np.savez_compressed(os.path.join(args.out, f'particles_{tag}.npz'), x=xs_f, cls=cls,
                        nori_row=nori_row, nori_col=nori_col, J=Jp, vol=vol)
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
                 pitch=args.pitch, seed=args.seed, vol=vol, pred=pred, rice_map0=rice_map0, wr=wr,
                 mat=dict(model='analytic arc: circle of radius R tangent to the table at (xc,0), '
                                'th in [0,Phi] clockwise from the contact; mat under the sheet from t=0',
                          R_mat_min=R_MAT_MIN, R_fold=round(R_fold, 3), R_final=round(R, 3),
                          R_end_pred=round(R_end_pred, 3), phi_meet=round(phi_meet, 3),
                          phi_meet_deg=round(math.degrees(phi_meet), 1),
                          phi_meet0=round(phi_meet0, 3), s_close_pred=round(s_close_pred, 3),
                          s_close=round(s_close_act, 3) if s_close_act else None,
                          R_close=round(R_close_act, 3) if R_close_act else None,
                          s_c_final=round(s_c, 3), xc_final=round(xc, 3), x_end=x_end,
                          v_lift=v_lift, v_roll=v_roll, t_hold=round(t_hold, 2),
                          bond=bond, bond_d=MAT_BOND_D, front_clear=FRONT_CLEAR,
                          y_ahead_final=round(y_ahead, 3), phi_final=round(th_hi, 3),
                          P_fold=P_FOLD_FRAC * P_ROLL_REF * args.press,
                          P_roll=P_ROLL_REF * args.press, P_press=P_PRESS_REF * args.press,
                          mu_mat=MU_MAT, mu_table=MU_TABLE, press_shape=layout['press_shape'],
                          lift_press_max=LIFT_PRESS_MAX, y_cen_press=round(y_cen_press, 3),
                          y_bed=Y_BED),
                 fingers=dict(on=fingers, x1=round(s_fold + 0.5, 2), lid_y=round(h_top + FING_LID, 3),
                              gap_R=FING_GAP, rate=FING_RATE, released_at=ph.get('hold'),
                              fold_zone=[r[5] for r in fold_rects], s_fold=round(s_fold, 3),
                              a_fold_T2=round(a_fold, 3), h_top=round(h_top, 3), hold=args.hold),
                 phases=ph,
                 timing=dict(seconds=round(elapsed, 1), steps=step, dt=round(dt, 6), grid=[nx, ny], dx=round(dx, 5),
                             particles=n, hp=round(info['hp'], 5), t_end=round(t, 2)))
    met = compute_metrics(xs_f, vs_f, cls, Jp, nori_row, nori_col, info, layout, img, px, center, esc_total, extra)
    # --- the first turn is a hand-set radius, so the layer count implied by area conservation has a
    #     third form: everything outside R_fold is wrapper. crossings = layers (no tuck offset).
    met['R_fold_T'] = round(R_fold, 3)
    met['R_fold_want_T'] = round(R_fold_want, 3)
    met['R_fold_area_cap_T'] = round(R_cap, 3)
    met['R_fold_capped'] = bool(R_fold_want > R_cap + 1e-6)
    met['tuck_effective'] = round(tuck_eff, 3)
    met['layers_predicted_close'] = round(layers_close, 3)
    met['crossings_predicted_close'] = round(layers_close, 3)      # no "+1 for the tuck" -- see predict_layers
    met['turns_minus_predicted_close'] = round(met['nori_turns'] - layers_close, 3)
    met['turns_match_formula_close'] = bool(abs(met['turns_minus_predicted_close']) <= 0.25)
    # --- grafted from ../mat-chain: the area formula is fed the fold length the run ACTUALLY spent on
    #     the first turn (arc consumed when rice met rice), not the nominal s_fold read off the flat
    #     sheet. The two differ whenever the loop decides for itself how much sheet to eat -- which is
    #     every layout with a filling, and the whole reason `turns_match_formula` kept failing.
    if s_close_act:
        pred_act = predict_layers(info, s_close_act, a_fold)
        met['s_fold_T'] = round(s_fold, 3)
        met['s_fold_actual_T'] = round(s_close_act, 3)
        met['layers_predicted_actual'] = pred_act['layers_predicted']
        met['crossings_predicted_actual'] = pred_act['crossings_predicted']
        met['turns_minus_predicted_actual'] = round(met['nori_turns'] - pred_act['crossings_predicted'], 3)
        met['turns_match_formula_actual'] = bool(abs(met['turns_minus_predicted_actual']) <= 0.25)
        # --- which of the two to believe, decided by the geometry and not by the answer: the length of
        #     the first turn is set by the FILLINGS when there are any inside it (a_fold > 0) -- the loop
        #     has to go round them and eats as much sheet as that takes -- and by the flat sheet when
        #     there are none. So: measured arc if the fold zone is loaded, nominal s_fold if it is empty.
        use_act = a_fold > 1e-6
        cr_best = pred_act['crossings_predicted'] if use_act else met['crossings_predicted']
        met['crossings_predicted_best'] = cr_best
        met['crossings_best_source'] = 'actual' if use_act else 'nominal'
        met['turns_minus_predicted_best'] = round(met['nori_turns'] - cr_best, 3)
        met['turns_match_formula_best'] = bool(abs(met['turns_minus_predicted_best']) <= 0.25)
    met['wrinkles_nonose'] = int(wr_final['wrinkles_nonose'])
    met['wrinkles_nonose_max'] = int(wr['wrinkles_nonose_max'])
    # --- did the press actually reach the roll? A trap for the silently invalid run: at --speed 2 the
    #     ring opens out to R_MAX and the press cannot close it inside t_press_max, so the mat finishes
    #     0.93 U (4.7 mm) away from the roll with ZERO contact -- and every existing flag passes it
    #     (stable, wrinkles 0, nori_torn false, core order preserved, 0 escaped). These two numbers,
    #     both already in the controller log, catch it.
    #     Both quantities are shape-aware: for the circle the mat radius R is compared with Rout, for
    #     the square R is a HALF-SIDE and belongs against the half-side of the roll's bounding box.
    _arc_end = R * max(th_hi - th_lo, 0.0) if shp == 0 else 8 * R
    _roll_ref = met['Rout_T'] if shp == 0 else met['shape']['square_half_side_T']
    met['mat_gap_end_T'] = round(float(R - _roll_ref), 3)
    met['press_contact_frac_end'] = round(float(L_f / max(_arc_end, 1e-9)), 3)
    _c_min = PRESSED_CONTACT_MIN if shp == 0 else PRESSED_CONTACT_MIN_SQ
    met['pressed_contact_min'] = _c_min
    met['pressed_ok'] = bool(met['mat_gap_end_T'] <= PRESSED_GAP_MAX and
                             met['press_contact_frac_end'] >= _c_min)
    met['stable'] = bool(met['stable'] and met['pressed_ok'])
    met['mat_min_radius_T'] = R_MAT_MIN
    met['mat_radius_min_run_T'] = round(min(l['R'] for l in log), 3) if log else round(R, 3)
    met['wrinkle_ok'] = bool(wr['wrinkles_max'] == 0 and wr['wrinkle_amp_max_T'] < 0.3)
    met['wrinkle_ok_final'] = bool(wr_final['wrinkles'] == 0 and wr_final['wrinkle_amp_T'] < 0.3)
    # --- "the accordion is impossible by construction" as a test that cannot be dodged by a window:
    #     no stretch of the band, at any phase, bent tighter than the mat itself can bend.
    met['mat_bend_limit_R_T'] = round(R_MAT_MIN + 0.5 * W_NORI, 4)
    met['mat_bend_violations'] = int(wr_final['mat_bend_violations'])
    met['mat_bend_violation_len_T'] = float(wr_final['mat_bend_violation_len_T'])
    met['mat_bend_min_R_T'] = float(wr_final['mat_bend_min_R_T'])
    met['mat_bend_dist_to_end_T'] = float(wr_final['mat_bend_dist_to_end_T'])
    met['mat_bend_spots'] = wr_final['mat_bend_spots']
    met['mat_bend_violations_max'] = int(wr['mat_bend_violations_max'])
    met['mat_bend_violations_max_phase'] = wr['mat_bend_violations_max_phase']
    met['mat_bend_min_R_run_T'] = wr['mat_bend_min_R_run_T']
    met['mat_bend_violation_len_max_T'] = wr['mat_bend_violation_len_max_T']
    met['mat_bend_samples_with_violation'] = int(wr['mat_bend_samples_with_violation'])
    met['wrinkle_ok_mat'] = bool(wr['mat_bend_violations_max'] == 0)
    met['wrinkle_ok_mat_final'] = bool(wr_final['mat_bend_violations'] == 0)
    met['rice_J_min_run'] = wr['rice_J_min_run']
    met['rice_J_min_run_phase'] = wr['rice_J_min_run_phase']
    met['rice_J_p05_min_run'] = wr['rice_J_p05_min_run']
    met['rice_squash_ok'] = bool(wr['rice_J_min_run'] >= 0.88)
    # --- order of the fillings in the core. After the roll they sit AROUND the core, so the honest
    #     test is that their angular order is a ROTATION of their order along the flat sheet.
    init_order = [f['kind'] for f in sorted(layout['fillings'], key=lambda f: f['u'])]
    got = list(met['core_order_by_phi'])
    def _rot(a, b):
        return len(a) == len(b) and (not a or any(b[k:] + b[:k] == a for k in range(len(b))))
    met['core_order_initial'] = init_order
    # The angular test "correct up to a cyclic shift" is weak: a random permutation of four fillings
    # passes it with probability 1/6, and the radial order is not monotone either. The strong test is
    # the MATERIAL coordinate of the sheet: take the nori particle nearest each filling and read its
    # arclength s (= nori_col * nori_dx). The sheet is one strictly monotone ribbon, so the order of s
    # must equal the order of the fillings' initial u along the flat sheet -- no shift allowed.
    nori_all = cls == CLASS_NORI
    if nori_all.any() and met['fillings']:
        _P = xs_f[nori_all]
        _s = nori_col[nori_all].astype(np.float64) * info['nori_dx']
        arcs = []
        for f in met['fillings']:
            cxy = np.array(f['centroid_xy'], np.float64)
            k = int(np.argmin(np.sum((_P - cxy) ** 2, axis=1)))
            arcs.append((float(_s[k]), f['kind']))
        met['core_arc_s_T'] = {k: round(s, 2) for s, k in arcs}
        met['core_order_by_arc'] = [k for s, k in sorted(arcs)]
    else:
        met['core_arc_s_T'] = {}
        met['core_order_by_arc'] = []
    met['core_order_preserved_by_phi'] = bool(_rot(init_order, got))       # the old, weak test
    met['core_order_preserved'] = bool(met['core_order_by_arc'] == init_order)
    met['core_order_preserved_mirrored'] = bool(_rot(init_order, list(reversed(got))))
    met['conservation_ok'] = bool(met['conservation'] >= 0.95)
    met['raster_outside_particles'] = _rout_win
    met['raster_window_ok'] = bool(_rout_win == 0)

    # ── ВЕРДИКТ ПРОГОНА ───────────────────────────────────────────────────────────────────────
    # ЗАЧЕМ. `stable` отвечает на вопрос «счёт не развалился»: конечные числа, никто не улетел,
    # скорости в пределах, лента не порвана, циновка дошла до ролла. Это ДЕТЕКТОР СЧЁТА, и он
    # честен в своей роли. Но 30.08 обнаружилось, что его читают как «прогон годен»: на всех пяти
    # раскладках стоял `stable: true`, пока пять физических проверок из этого же дампа были
    # красными — рис пережат ниже физического предела, складки, лист отстаёт от циновки, витки
    # мимо формулы, циновка гнётся острее бамбука. Прибор рапортовал «здоров», и по его числам
    # калибровали модель игры.
    #
    # Это ровно та ошибка, которую проект уже разбирал на диаметре ролла: ОТДЕЛЯТЬ ДЕТЕКТОР ОТ
    # ТРЕБОВАНИЯ. Поэтому `stable` не расширяем — рядом появляется отдельный вердикт о физической
    # годности, и он перечисляет ИМЕНА проваленных проверок, а не прячет их за одним словом.
    #
    # Правило чтения: `physics_ok = false` не значит «прогон испорчен» — значит «этими числами
    # калибровать нельзя, пока не объяснено, почему провал допустим».
    _phys = [
        ('рис не пережат',            'rice_squash_ok'),
        ('нет складок листа',         'wrinkle_ok'),
        ('циновка гнётся не острее',  'wrinkle_ok_mat'),
        ('объём сохранён',            'conservation_ok'),
        ('порядок начинок сохранён',  'core_order_preserved'),
        ('витки сходятся с формулой', 'turns_match_formula_best'),
        ('лист прижат к циновке',     'nori_mat_contact_ok'),
        ('растр не обрезал ролл',     'raster_window_ok'),
    ]
    _failed = [name for name, key in _phys if key in met and met[key] is not None and not met[key]]
    _absent = [name for name, key in _phys if key not in met or met[key] is None]
    # Разрешение: приёмка, снятая при 1,9 частицы на клетку, недостоверна — минимум метода два
    # (поправка 11, KINEMATICS.md; разрыв ленты там исчезает между ppc 2,6 и 3,2 — пресет «точно»
    # в пульте целится в 3,2, но это выбор пресета, а не минимум метода).
    # Вторая половина критерия — ЛЕНТА НЕ ДЫРЯВИТСЯ ЧИСЛЕННО: в каждой клетке, которую пересекает
    # нори, должно лежать несколько её частиц, иначе перенос на сетку рвёт мембрану сам по себе.
    # Это dx / nori_dx (шаг ЧАСТИЦ ленты) ≥ 3 — ровно то, что просит поправка 11, п. 1.
    # ⚠ Первая редакция (30.08, ночь) сравнивала dx с ТОЛЩИНОЙ ленты (W_NORI / dx ≥ 0,5) — это
    # требовало сетку ~660 и не проходило никогда; толщина решается рядами частиц (nr ≥ 2),
    # а не клеткой сетки. Замер: сетки 150/200/260 дают W_NORI/dx 0,11/0,15/0,20 — планка была
    # недостижима по построению, вердикт «НЕ ГОДЕН» стоял бы вечно (issue #91).
    _ppc = float(n) / max(1, nx * ny)          # частиц на клетку; минимум метода — две
    met['ppc'] = round(_ppc, 3)
    _nori_per_cell = dx / max(1e-9, info['nori_dx'])
    met['nori_particles_per_cell'] = round(_nori_per_cell, 2)
    _res_ok = bool(_ppc >= 2.0 and _nori_per_cell >= 3.0)
    if not _res_ok:
        _failed.append('разрешение сетки (ppc %.2f, частиц нори на клетку %.1f)' % (_ppc, _nori_per_cell))
    met['physics_checks_failed'] = _failed
    met['physics_checks_absent'] = _absent
    met['physics_ok'] = bool(not _failed)
    met['verdict'] = ('ГОДЕН для калибровки' if met['physics_ok'] and met.get('stable')
                      else 'НЕ ГОДЕН: ' + '; '.join(_failed or ['счёт неустойчив']))
    # --- the geometry this run was made with, stamped into the file so that an old metrics_N.json and
    #     a new one cannot be confused: the keys are identical and only the numbers moved.
    met['geometry'] = dict(unit_mm=U_MM, T_rice_U=T_RICE, w_nori_U=W_NORI, h_sheet_U=round(H_SHEET, 4),
                           L_sheet_U=L_SHEET, L_flap_U=L_FLAP, w_nori_over_dx=round(W_NORI / dx, 4),
                           T_rice_over_dx=round(T_RICE / dx, 3),
                           E_nori_w=E_NORI_W, E_nori=round(MATERIALS['nori'][0], 3),
                           source='stand BASES.sushi 26.08.2026 (docs/geometry-audit.md)')
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
    save_frame(S, cls, xc, R, 0.0, 2 * math.pi, shp, os.path.join(args.out, f'final_{tag}.png'), t, F_f,
               None, 0, zoom=(center, args.window))
    print(json.dumps({k: v for k, v in met.items() if k not in ('controller_log', 'fillings', 'wrinkle_hist')},
                     indent=1, default=_js))
    # Вердикт печатается ПОСЛЕДНИМ и отдельной строкой: до 30.08 итог прогона тонул в дампе из
    # полутора сотен ключей, и «stable: true» читалось как «всё хорошо» (см. блок ВЕРДИКТ выше).
    print(f'done in {elapsed:.1f}s  ({step} steps, t_end={t:.1f})')
    print('─' * 72)
    print('ВЕРДИКТ: ' + met['verdict'])
    if met['physics_checks_absent']:
        print('  не проверялось: ' + '; '.join(met['physics_checks_absent']))
    print('─' * 72, flush=True)

def save_frame(S, cls, xc, R, th_lo, th_hi, shp, path, t, F, gp=None, grabbing=0, zoom=None, ylift=0.0,
               fbox=None):
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
            # the mat: the wrapped arc (thick) and, ahead of the contact point, the part still flat
            ax.plot(xc - R * np.sin(th), ylift + R - R * np.cos(th), '-', color='#ff5555', lw=2.0)
            ax.plot([xc, X1], [0.0, 0.0], '-', color='#ff5555', lw=1.0, alpha=0.6)
        else:
            ax.plot([xc - R, xc + R, xc + R, xc - R, xc - R],
                    [ylift, ylift, 2 * R + ylift, 2 * R + ylift, ylift], 'r-', lw=1.2)
    if gp is not None and grabbing:
        ax.plot([gp[0]], [gp[1]], marker='o', ms=6, mfc='none', mec='#ff4fd8', mew=1.8)   # near end of the mat
    if fbox is not None:
        ax.plot([fbox[0], fbox[1]], [fbox[2], fbox[2]], '-', color='#7fd0ff', lw=2.0)     # the fingers
    ax.axhline(0, color='k', lw=0.5)
    if zoom is None:
        ax.set_xlim(X0, X1); ax.set_ylim(Y0, Y1)
    else:
        (cx, cy), wdt = zoom
        ax.set_xlim(cx - wdt / 2, cx + wdt / 2); ax.set_ylim(cy - wdt / 2, cy + wdt / 2)
    ax.set_aspect('equal'); ax.set_facecolor('#1c1c20')
    ax.set_title(f't={t:.1f} xc={xc:.2f} R={R:.3f} lift={ylift:.2f} Phi={th_hi:.2f} F={F:.3f}', fontsize=8)
    fig.tight_layout(); fig.savefig(path); plt.close(fig)

if __name__ == '__main__':
    main()
