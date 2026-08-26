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

# ----------------------------------------------------------------------------- bases and layouts
# T = 1 = the SPREAD thickness OF THAT BASE (rice for sushi, cream for the roll cake, cream cheese for
# the lavash roll).  Sheet length, wrapper thickness, spread thickness, material names and colours are
# per base and come from the layout dict -- nothing about the sheet is shared between the bases.
T = 1.0
KIND_IDS = ['salmon', 'cucumber', 'tamago', 'avocado', 'shrimp',
            'strawberry', 'kiwi', 'banana', 'jam', 'cheese', 'tomato', 'dill']
CLASS_BG, CLASS_SPREAD, CLASS_WRAP = 0, 1, 2
CLASS_RICE, CLASS_NORI = CLASS_SPREAD, CLASS_WRAP            # old sushi names, same class ids
CLASS_OF_KIND = {k: 3 + i for i, k in enumerate(KIND_IDS)}   # salmon 3 ... dill 14
N_CLASS = 3 + len(KIND_IDS)
KIND_COLORS = {'salmon': (250, 118, 88), 'cucumber': (86, 178, 62), 'tamago': (250, 208, 66),
               'avocado': (152, 202, 92), 'shrimp': (250, 168, 150),
               'strawberry': (226, 58, 74), 'kiwi': (124, 188, 72), 'banana': (246, 226, 120),
               'jam': (172, 40, 82), 'cheese': (246, 214, 128), 'tomato': (228, 82, 60),
               'dill': (70, 140, 76)}
# classes 1 and 2 are re-coloured per layout in main(); the defaults are the sushi ones
COLORS = {CLASS_BG: (28, 28, 32), CLASS_SPREAD: (246, 240, 224), CLASS_WRAP: (26, 62, 44)}
for _k, _c in CLASS_OF_KIND.items():
    COLORS[_c] = KIND_COLORS[_k]

def fill(kind, u, w, h, round_=False, stack=False):
    return dict(kind=kind, u=u, w=w, h=h, round=round_, stack=stack)

def base(**kw):
    """Geometry of one base.  The defaults ARE the sushi base, so layouts 1-5 are untouched."""
    d = dict(name='?', spiral=False, press_shape='circle',
             L=38.7,              # sheet length, T
             lead=0.0,            # near end left bare of spread, T
             flap=5.0,            # far end left bare of spread, T
             w_wrap=0.12,         # wrapper thickness, T
             t_spread=1.0,        # spread thickness, T (= 1 by definition of T)
             taper=0.0,           # wrapper fades to nothing over this length at BOTH ends, T
             taper_min=0.35,      # wrapper thickness left at the very tip (fraction of w_wrap)
             overlap_skip=False,  # a filling listed later yields to the ones listed before it
             wrap_mat='nori', spread_mat='rice',
             wrap_color=(26, 62, 44), spread_color=(246, 240, 224),
             window=12.0, domain=(-2.0, 48.0, -0.4, 12.6),
             grid=240, particles=16000, R_max=8.0, R_init=0.0,
             press_scale=1.0,     # per-base multiplier on the mat pressures (a cake is not squeezed)
             rho0=0.5,            # spiral: radius of the innermost tip of the curl, T
             fill_squash=1.0,     # spiral: area-preserving flattening of every filling piece
                                  # (h *= k, w /= k).  A 3.2 T kiwi slice laid round in a roll
                                  # whose radius is 5 T is two pitches tall: no winding can
                                  # close over it, and the roll comes out lobed with ~35 % air
                                  # between the turns.  A cook presses the fruit into the cream
                                  # as she lays it; k is that press.
             curl_turns=1.25,     # spiral: turns wound by the kinematic curl before phase C
             fillings=[])
    d.update(kw)
    return d

# roll cake (L = 40.2 T): one piece of each fruit plus a jam strip, distributed ALONG the sheet so
# that every spiral turn carries something.  The innermost ~2.5 T are bare sponge (lead), so the core
# can curl genuinely tight.
CAKE_FILL = [fill('jam', 5.0, 4.4, 0.44), fill('banana', 12.0, 3.0, 2.5, True),
             fill('strawberry', 21.0, 3.2, 3.0, True), fill('kiwi', 30.0, 3.7, 3.2, True)]
# lavash (L = 107.6 T): one piece of each, one per turn, plus a dill sprinkle running the whole length
# (listed last, so it yields wherever a real piece already lies -- overlap_skip)
LAVASH_FILL = ([fill('salmon', 22.0, 4.4, 3.6), fill('cheese', 52.0, 4.9, 2.7),
                fill('tomato', 80.0, 5.8, 2.2, True)]
               + [fill('dill', 3.0 + 7.0 * i, 4.5, 0.14) for i in range(14)])

LAYOUTS = {
    1: base(name='empty', fillings=[]),
    2: base(name='tamago-edge', fillings=[fill('tamago', 1.5, 2.4, 2.0)]),
    3: base(name='salmon-mid', fillings=[fill('salmon', 38.7 * 0.5 - 1.0, 2.0, 1.6)]),
    4: base(name='four-edge', fillings=[fill('cucumber', 1.5, 1.4, 1.4, True), fill('tamago', 3.2, 2.4, 2.0),
                                        fill('salmon', 5.9, 2.0, 1.6), fill('avocado', 8.2, 2.0, 1.1, True)]),
    5: base(name='overflow-square', press_shape='square',
            fillings=[fill('tamago', 1.5, 2.4, 2.0), fill('salmon', 1.7, 2.0, 1.6, stack=True),
                      fill('cucumber', 2.0, 1.4, 1.4, True, stack=True)]),
    # ---- spiral bases: no tuck, both ends tapered, the wrapper genuinely spirals
    6: base(name='roll-cake', spiral=True, L=40.2, lead=4.5, flap=0.6, w_wrap=0.52, taper=2.2,
            wrap_mat='sponge', spread_mat='cream',
            wrap_color=(214, 166, 104), spread_color=(252, 244, 226), overlap_skip=True,
            window=16.0, domain=(-3.0, 50.0, -0.4, 16.0), grid=300, particles=32000,
            R_max=9.0, R_init=0.0, press_scale=0.35, rho0=0.45, curl_turns=0.0, fill_squash=0.65,
            fillings=CAKE_FILL),
    7: base(name='lavash-roll', spiral=True, L=107.6, lead=3.0, flap=0.4, w_wrap=0.44, taper=1.4,
            wrap_mat='flatbread', spread_mat='creamcheese',
            wrap_color=(226, 198, 150), spread_color=(250, 248, 238), overlap_skip=True,
            window=22.0, domain=(-3.0, 118.0, -0.4, 22.6), grid=380, particles=40000,
            R_max=13.0, R_init=0.0, press_scale=0.35, rho0=0.30, curl_turns=0.0, fill_squash=0.60,
            fillings=LAVASH_FILL),
}

# ----------------------------------------------------------------------------- materials
# name: (E, nu, tau_y (shear yield; 1e9 = elastic), rho).  Classes 1 (spread) and 2 (wrapper) are
# bound to a material by the layout in main(); the fillings keep a fixed class each.
MATERIALS = {
    'rice':     (1.0, 0.35, 0.03, 1.0),
    'nori':     (25.0, 0.30, 1e9, 2.0),
    'salmon':   (3.0, 0.40, 0.15, 1.0),
    'cucumber': (15.0, 0.30, 1e9, 1.0),
    'tamago':   (10.0, 0.35, 1e9, 1.0),
    'avocado':  (4.0, 0.40, 0.15, 1.0),
    'shrimp':   (6.0, 0.35, 1e9, 1.0),
    # --- spiral bases
    # A spiral wrapper must TAKE A SET.  Nori is elastic (tau_y = 1e9) and that is fine for a maki:
    # one turn of radius ~3 T bends its 0.12 T band by ~2 % strain.  A sponge sheet 0.52 T thick wound
    # to radius 0.5 T is at ~37 % outer-fibre strain -- purely elastic, it stores that and springs the
    # coil open the moment the fingers let go (exactly what run 6c3 did).  Real sponge and real lavash
    # yield in bending, so both get a finite shear yield: tau_y ~ 2*mu*(w/2)/r_set, i.e. they hold any
    # bend tighter than r_set ~ 4 T.
    'sponge':      (4.0, 0.32, 0.20, 0.5),   # roll-cake wrapper: thicker and much softer than nori
    'cream':       (0.6, 0.40, 0.02, 1.0),   # whipped cream: yields early, spreads under the mat
    'flatbread':   (10.0, 0.30, 0.45, 1.2),  # lavash: stiff in tension, takes a set in bending
    'creamcheese': (0.8, 0.40, 0.03, 1.0),
    'strawberry':  (3.0, 0.40, 0.12, 1.0),
    'kiwi':        (2.5, 0.40, 0.10, 1.0),
    'banana':      (1.5, 0.40, 0.05, 1.0),
    'jam':         (0.3, 0.45, 0.008, 1.0),
    'cheese':      (8.0, 0.35, 0.40, 1.0),
    'tomato':      (2.0, 0.40, 0.08, 1.0),
    'dill':        (1.0, 0.35, 1e9, 0.6),
}
MAT_OF_CLASS = {CLASS_SPREAD: 'rice', CLASS_WRAP: 'nori'}    # rebound per layout in main()
for k, c in CLASS_OF_KIND.items():
    MAT_OF_CLASS[c] = k

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
Y_TUCK_FRAC = 0.55       # maki: tucked edge is pressed down to w_wrap + this * t_spread
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
R_MIN = 0.8              # R_max is per base (layout['R_max'])
PHI_ROLL = 5.50          # angular span of the mat during rolling, rad (~315 deg)
T_LIFT = 8.0             # time for the mat circle to rise onto the sheet at the start of phase C
V_LIFT = 0.08            # max rate of change of the mat lift
V_RADIAL_PRESS = 0.12    # radial speed of the mat controller during the final pressing
TH_BACK_MIN = 0.15       # the mat's back end stays this far (in angle) off the table
# the thickness of the incoming sheet (y_bed = w_wrap + t_spread) and the lowest the FRONT end of
# the arc may reach (y_front = max(0.30, y_bed + 0.15)) are per base and computed in main()
T_WRAP = 12.0            # time for the phase-B cap to widen to the full rolling arc
T_CLOSE = 6.0            # phase-D closing of the arc to 360 deg
T_PRESS = 8.0            # minimum duration of the final pressing
T_PRESS_MAX = 46.0       # give up on force equilibrium after this
T_SETTLE = 26.0          # spiral bases: how long the cupping hands hold the finished roll
GRAVITY = 0.01
MU_TABLE = 0.4
MU_MAT = 2.0             # effectively sticky while pressed against the mat
CFL = 0.3
CORNER_R = 0.6           # corner radius of the square press
TAIL_TOL = 0.3           # a particle further than this outside the fitted contour counts as "tail outside"
TAIL_FRAC = 0.002        # fraction of particles above which tail_outside becomes True

# --- curl (spiral bases only: roll cake, lavash roll)
CURL_ENGAGE_TURNS = 0.55  # the mat cap comes down on the curl after this many turns
CURL_SQUEEZE = 1.00       # the curl's pitch at arc length s is  w_wrap(s) + this * (everything above
                          # the wrapper at s): the spread and the fillings are squeezed by 10 %, and
                          # the bare lead (no spread) curls at the wrapper's own thickness -- which is
                          # what lets the first turn be genuinely tight.
CURL_RAMP = 0.9           # length over which the kinematic grab fades in behind the wind point, T.
                          # Ahead of the wind point the sheet is FREE (not pinned), so it can be drawn
                          # into the coil instead of being torn off it.
CURL_RELEASE_TURNS = 0.2  # the grab fades out over the last turns of the curl -> seamless phase C
CURL_V_CAP = 12.0         # cap on a prescribed particle speed, in units of the feed speed
CURL_BAND_TURNS = 0.75     # the fingers hold only the OUTERMOST turns of the coil: a particle deeper
CURL_BAND_FADE = 0.5      # than this many turns behind the wind point is released over this many more
                          # turns and is free material from then on.  The already-wound interior is
                          # confined by the driven turns wrapped around it, so it cannot spring open --
                          # and it is free to compact, to let the fillings squash, and to let the
                          # spread thin out under them.  That is where the physics of this reference
                          # lives; the winding itself is guided, as a cook's hands guide it.
OMEGA_REF = 0.06          # THE CURL WINDS AT CONSTANT ANGULAR VELOCITY, not at constant feed speed.
                          # With a constant feed the coil's spin rate is v/rho, which is ~10x faster
                          # when the core is 0.45 T than when the roll is 4.6 T.  Material released
                          # from the driven band keeps the spin it had, the band around it is by then
                          # turning much slower, and the whipped cream (tau_y = 0.02) cannot carry the
                          # torque that would bring them back together: the interior grinds itself into
                          # a void ring, which is what runs 6c8/6c9 show at t = 92.  At constant omega
                          # every turn -- driven or free -- co-rotates, there is no torque to transmit,
                          # and the centrifugal term omega^2 r stays at ~2x gravity.  The feed speed
                          # omega*rho then grows as the roll grows, exactly as a cook's hands do.
CURL_LUMP_SPREAD = 0.06   # a filling's lump is spread over +-this many turns before the next turn
                          # rides over it (the spread squeezes sideways round the filling)
CURL_MAT_ON = False       # keep the mat OFF while the coil is being wound.  A circular mat cannot hug
                          # a snail whose outer radius jumps by a whole pitch at the seam, and a sticky
                          # mat that spins at the wrong rate shears the coil apart (runs 6c3-6c5).
V_RADIAL_CURL = 0.9       # max |dR/dt| while the mat is glued to the growing coil, T per time unit
LIFT_R_FRAC = 0.5         # spiral bases: the mat lift never exceeds this fraction of the mat radius
                          # (a small coil must not be lifted clean off the mat by the sheet thickness)

# ----------------------------------------------------------------------------- particle sampling
def wrap_thickness(layout, s):
    """Wrapper thickness at arc length s along the sheet.

    Spiral bases press BOTH ends flat: the very start of the sheet (the innermost tip of the spiral)
    and the very end fade to `taper_min` of the full thickness over `taper`, so the wrapper runs out
    instead of ending in a step -- no bare flap, no butt joint.  taper = 0 gives the sushi sheet back
    exactly."""
    w = layout['w_wrap']
    tp = layout['taper']
    arr = isinstance(s, np.ndarray)
    if tp <= 0:
        return w * np.ones_like(s) if arr else w
    L = layout['L']; tm = layout['taper_min']
    e = (np.minimum(s, L - s) if arr else min(s, L - s)) / tp
    e = np.clip(e, 0.0, 1.0) if arr else min(max(e, 0.0), 1.0)
    return w * (tm + (1.0 - tm) * e)

def stack_height(layout, info, s):
    """Total material height above the table at arc length s along the flat sheet, T."""
    top = wrap_thickness(layout, s).copy()
    inside = (s >= layout['lead']) & (s <= layout['L'] - layout['flap'])
    top = np.where(inside, np.maximum(top, layout['w_wrap'] + layout['t_spread']), top)
    for (u, by, w, h, rnd, _c) in info['rects']:
        m = (s >= u) & (s <= u + w)
        if not m.any():
            continue
        if rnd:
            e = np.clip((s[m] - (u + 0.5 * w)) / (0.5 * w), -1.0, 1.0)
            top[m] = np.maximum(top[m], by + h * np.sqrt(np.maximum(0.0, 1.0 - e * e)))
        else:
            top[m] = np.maximum(top[m], by + h)
    return top

def curl_profile(layout, info, rho0, squeeze=CURL_SQUEEZE, n=6001, smooth_T=0.5):
    """The curl as a map from arc length s along the sheet to (rho, phi) plus the heights it needs.

    Two heights, and they behave differently:

      solid(s)  wrapper + spread.  The spread is a fluid trapped between two turns of wrapper, so the
                gap it fills is just its own flat thickness: the pitch of the WRAPPER is solid, and a
                thick-layer (area-preserving) treatment would be wrong here -- the cream redistributes
                along the turn instead of thickening it.
      hf(s)     whatever lies ON the spread (a strawberry, a slice of tomato, a dill sprinkle).  That
                does not flow: it needs a slot of its own, opened by the pitch ONE TURN EARLIER.

    Turn on turn, not the area integral d(rho^2)/ds = pitch/pi (which is only its slowly-varying limit
    and leaves a ring of air wherever the pitch steps up -- the black core of runs 6c8-6c10):

        rho(phi) = Rout(phi - 2*pi) + hf(s),   Rout(phi) = rho(phi) + solid(s),   ds = (Rout - w/2) dphi

    with Rout = rho0 for the first turn.  Arc length is measured on the WRAPPER, which is the outer
    skin of the column (it lies under the spread on the table, so it winds up outside), not on the
    laying surface: measuring on the laying surface makes the sheet ~15 % too long.

    A filling's lump is smeared over +-CURL_LUMP_SPREAD turns before the next turn rides over it (the
    spread squeezes sideways round it).  Without that the lump is carried outward undiminished by every
    later turn and the roll ends ~40 % out of round.

    `ccy` is how high the coil's centre has to be for no part of the coil to be driven through the
    table -- normally Rout(s_w), higher for the moment a lump comes round to the contact.

    Returns (s, rho, phi, solid, hf, top_raw, ccy)."""
    L = layout['L']
    ss = np.linspace(0.0, L, n)
    ds = ss[1] - ss[0]
    w = wrap_thickness(layout, ss)
    top_raw = stack_height(layout, info, ss)
    inside = (ss >= layout['lead']) & (ss <= L - layout['flap'])
    solid_raw = np.where(inside, w + layout['t_spread'], w)
    hf_raw = np.maximum(0.0, top_raw - solid_raw)

    def sm(a, ln):
        k = max(3, int(round(ln / ds)) | 1)
        ker = np.ones(k) / k
        return np.convolve(np.concatenate([np.full(k, a[0]), a, np.full(k, a[-1])]), ker, 'same')[k:k + n]

    solid = np.maximum(sm(solid_raw, 0.6), w)
    hf = squeeze * sm(hf_raw, smooth_T)
    nth = 2000
    dth = 2.0 * math.pi / nth
    kk = max(1, int(round(CURL_LUMP_SPREAD * nth)))
    TH = [0.0]; SS = [0.0]; RHO = [rho0]; RO = [rho0 + float(solid[0])]
    th = 0.0; sc = 0.0; i = 0
    while sc < L and i < 400000:
        th += dth; i += 1
        if i < nth:
            prev = rho0
        else:
            a = max(0, i - nth - kk); b = min(i, i - nth + kk + 1)
            prev = float(np.mean(RO[a:b]))
        sol = float(np.interp(sc, ss, solid)); hfv = float(np.interp(sc, ss, hf))
        wv = float(np.interp(sc, ss, w))
        r = prev + hfv
        sc += (r + sol - 0.5 * wv) * dth
        TH.append(th); SS.append(sc); RHO.append(r); RO.append(r + sol)
    TH = np.array(TH); SS = np.array(SS); RHO = np.array(RHO); RO = np.array(RO)
    cyq = RO.copy()
    for k in range(1, len(RO) // nth + 1):
        cyq[k * nth:] = np.maximum(cyq[k * nth:], RO[:-k * nth])
    rho = np.interp(ss, SS, RHO, right=RHO[-1])
    phi = np.interp(ss, SS, TH, right=TH[-1])
    ccy = np.interp(ss, SS, cyq, right=cyq[-1])
    return ss, rho, phi, solid, hf, top_raw, ccy

def sample_layout(layout, n_target):
    L = layout['L']; w_wrap = layout['w_wrap']; t_sp = layout['t_spread']
    s0 = layout['lead']; s1 = L - layout['flap']
    fl = layout['fillings']
    area_spread = (s1 - s0) * t_sp
    if layout['taper'] <= 0:
        area_wrap = L * w_wrap
    else:
        ss = np.linspace(0.0, L, 4001)
        area_wrap = float(np.trapezoid(wrap_thickness(layout, ss), ss))
    rects = []
    y_top = {}   # per filling index: top y (for stacking)
    ksq = layout.get('fill_squash', 1.0)
    for i, f in enumerate(fl):
        if f['stack'] and i > 0:
            base_y = y_top[i - 1]
        else:
            base_y = w_wrap + t_sp
        fw = f['w'] / ksq; fh = f['h'] * ksq          # area-preserving press (see base(fill_squash=...))
        rects.append((f['u'] - 0.5 * (fw - f['w']), base_y, fw, fh, f['round'], CLASS_OF_KIND[f['kind']]))
        y_top[i] = base_y + fh
    area_fill = sum((math.pi / 4 if r[4] else 1.0) * r[2] * r[3] for r in rects)
    hp = math.sqrt((area_spread + area_wrap + area_fill) / n_target)
    xs, cls, vol, nori_row, nori_col, piece = [], [], [], [], [], []
    rng = np.random.default_rng(1)
    jit = 0.15 * hp

    # spread: rows across thickness, columns along the sheet
    n_rows = max(2, int(round(t_sp / hp)))
    dy = t_sp / n_rows
    n_cols = int(round((s1 - s0) / hp))
    dxp = (s1 - s0) / n_cols
    for r in range(n_rows):
        for c in range(n_cols):
            xs.append((X_SHEET + s0 + (c + 0.5) * dxp + rng.uniform(-jit, jit), w_wrap + (r + 0.5) * dy + rng.uniform(-jit, jit)))
            cls.append(CLASS_SPREAD); vol.append(dxp * dy); nori_row.append(-1); nori_col.append(-1); piece.append(-1)
    # wrapper: at least 2 rows, no jitter (clean band), thickness tapering at both ends
    nr = max(2, int(round(w_wrap / hp)))
    ncn = int(round(L / hp))
    dxn = L / ncn
    for r in range(nr):
        for c in range(ncn):
            sc = (c + 0.5) * dxn
            wl = wrap_thickness(layout, sc)
            xs.append((X_SHEET + sc, (r + 0.5) * wl / nr))
            cls.append(CLASS_WRAP); vol.append(dxn * wl / nr); nori_row.append(r); nori_col.append(c); piece.append(-1)
    # fillings
    skip_over = layout['overlap_skip']
    for idx, (u, by, w, h, rnd, cl) in enumerate(rects):
        ncx = max(2, int(round(w / hp))); ncy = max(2, int(round(h / hp)))
        ddx = w / ncx; ddy = h / ncy
        for i in range(ncx):
            for j in range(ncy):
                px = u + (i + 0.5) * ddx; py = by + (j + 0.5) * ddy
                if rnd:
                    ex = (px - (u + w / 2)) / (w / 2); ey = (py - (by + h / 2)) / (h / 2)
                    if ex * ex + ey * ey > 1.0:
                        continue
                if skip_over and _inside_any(rects[:idx], px, py):
                    continue
                xs.append((px + rng.uniform(-jit, jit) * 0.5, py + rng.uniform(-jit, jit) * 0.5))
                cls.append(cl); vol.append(ddx * ddy); nori_row.append(-1); nori_col.append(-1); piece.append(idx)
    info = dict(hp=hp, nori_rows=nr, nori_cols=ncn, nori_dx=dxn, wrap_dy=w_wrap / nr,
                area_rice=area_spread, area_spread=area_spread, area_nori=area_wrap, area_wrap=area_wrap,
                area_fill=area_fill, rects=rects, L=L, w_wrap=w_wrap, t_spread=t_sp)
    return (np.array(xs, np.float32), np.array(cls, np.int32), np.array(vol, np.float32),
            np.array(nori_row, np.int32), np.array(nori_col, np.int32), np.array(piece, np.int32), info)

def _inside_any(rects, px, py, m=0.04):
    """Is (px, py) inside one of these filling rects (ellipse for round ones)?"""
    for (u, by, w, h, rnd, _c) in rects:
        if not (u - m < px < u + w + m and by - m < py < by + h + m):
            continue
        if rnd:
            ex = (px - (u + w / 2)) / (w / 2 + m); ey = (py - (by + h / 2)) / (h / 2 + m)
            if ex * ex + ey * ey > 1.0:
                continue
        return True
    return False

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
    S['pv'] = ti.Vector.field(2, float, n_part)     # per-particle prescribed velocity (curl phase)
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
    pv = S['pv']
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
                gom: float, grad: float, grabbing: ti.i32, curl: ti.i32):
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
                # maki: the grabbed strip rides a rigid finger disk.  spiral: every grabbed particle
                # gets its own velocity from the winding map (a rigid disk could not curl the strip).
                tv = ti.Vector([gvx - gom * (x[p][1] - gy), gvy + gom * (x[p][0] - gx)])
                if curl == 1:
                    tv = pv[p]
                nv = (1.0 - wp) * nv + wp * tv
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

def turn_gaps(img, c_row, c_col, px, angs):
    """Radial distance between successive wrapper turns along each ray.

    A real roll cake has near-even turn spacing, so this is the honest measure of a spiral: mean gap
    (= the pitch of the spiral), its spread over all ray/turn pairs, and the spread WITHIN a ray
    (a ray crossing an even spiral sees equal gaps even if the roll is off-centre)."""
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

def wrapper_spiral(xs, cls, nori_row, nori_col, cen_world, info, core_hint=None):
    """Turns and turn-to-turn gap read off the WRAPPER ITSELF, not off rays.

    A ray from the centroid is the right instrument for a maki, which is round.  A roll cake with a
    3 T strawberry in a 5 T roll is not round: it has lobes, and a ray through a lobe crosses the
    wrapper twice more than the winding actually turns.  So walk the wrapper along its own material
    order instead, unwrap the angle it sweeps about the centroid, and read

        turns          = total swept angle / 2*pi
        gap(psi)       = r(psi + 2*pi) - r(psi)      -- the radial distance to the next turn
        gap mean, cv   over every psi where a next turn exists

    which is exactly the pitch of the spiral and its evenness, lobes and all."""
    m = (cls == CLASS_WRAP) & (nori_row == info['nori_rows'] // 2)
    if int(m.sum()) < 20:
        m = cls == CLASS_WRAP
    order = np.argsort(nori_col[m])
    chain = xs[m][order]
    # measure about the CORE of the coil, not the centroid of the whole roll.  Big fillings pull the
    # centroid off the coil's axis and an angle swept about an off-axis point loses most of a turn
    # (2.70 -> 1.95 on the map of the roll cake, checked against the profile's own 2.61).
    # least-squares circle (Kasa) through the innermost turn of the wrapper: the coil's axis.  The
    # plain mean of the first few per cent sits ON the coil instead of at its centre when that piece
    # is less than a full turn, and then the head of the chain passes within ~0.05 T of the "centre",
    # where the swept angle is meaningless and unwrap loses most of a turn.
    n0 = min(len(chain) - 1, max(8, int(0.10 * len(chain))))
    h = chain[:n0].astype(np.float64)
    if core_hint is not None:
        cen = np.array(core_hint, np.float64)
    else:
        A = np.stack([h[:, 0], h[:, 1], np.ones(n0)], 1)
        b = h[:, 0] ** 2 + h[:, 1] ** 2
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        cen = np.array([0.5 * sol[0], 0.5 * sol[1]])
    if not np.all(np.isfinite(cen)):
        cen = h.mean(axis=0)
    # Refine the centre: a spiral's swept angle is MAXIMAL about its own axis -- move the centre off
    # the axis and the chain stops going round it, so turns can only be lost.  Take the best of a small
    # grid.  (The same roll read 2.85 / 1.98 / 1.04 turns in runs 6c19-6c22 purely from where the
    # centre landed; this pins it.)
    def sweep_about(c):
        d = chain - c
        rr = np.hypot(d[:, 0], d[:, 1])
        if rr.min() < 0.20:        # a centre sitting ON the band fakes a whole extra turn
            return -1.0
        return float(np.ptp(np.unwrap(np.arctan2(d[:, 1], d[:, 0]))))
    best = sweep_about(cen)
    for _rad in (0.6, 0.25, 0.1):
        improved = True
        while improved:
            improved = False
            for dxc in (-_rad, 0.0, _rad):
                for dyc in (-_rad, 0.0, _rad):
                    if dxc == 0.0 and dyc == 0.0:
                        continue
                    c2 = cen + np.array([dxc, dyc])
                    v = sweep_about(c2)
                    if v > best + 1e-6:
                        best, cen, improved = v, c2, True
    pts = chain - cen
    r = np.hypot(pts[:, 0], pts[:, 1])
    th = np.arctan2(pts[:, 1], pts[:, 0])
    psi = np.unwrap(th)
    if psi[-1] < psi[0]:                       # walk it in the direction of increasing angle
        psi = psi[::-1]; r = r[::-1]
    # Turn count from the arc-length relation ds = r*dpsi, summed along the chain:
    #     turns = sum(ds_i / (2*pi*r_i)).
    # This is the same swept angle, but it never sees the angle itself, so it cannot be wrecked by a
    # chain point passing close to the assumed centre (unwrap loses or gains a whole turn there, which
    # is how the same roll measured 2.85, 1.98, 1.82 and 1.04 turns in runs 6c19-6c22 depending only
    # on where the centre landed).  r is floored at a quarter of the pitch for the same reason.
    seg = np.linalg.norm(np.diff(chain, axis=0), axis=1)
    rmid = 0.5 * (r[1:] + r[:-1])
    r_floor = max(0.15, 0.25 * float(np.median(np.abs(np.diff(np.sort(r))))) )
    turns_sweep = float((psi.max() - psi.min()) / (2.0 * math.pi))
    turns_arc = float(np.sum(seg / (2.0 * math.pi * np.maximum(rmid, r_floor))))
    turns = turns_sweep            # validated against the analytic profile: 2.52 vs 2.61
                                   # (cake) and 4.35 vs 4.31 (lavash) on the exact map
    # r as a function of psi on a monotone grid (the walk can wobble; sort and average duplicates)
    o = np.argsort(psi)
    ps, rs = psi[o], r[o]
    grid = np.arange(ps[0], ps[-1], 0.05)
    if len(grid) < 4:
        return dict(turns_wrap=round(turns, 3), turn_gap_mean_wrap_T=0.0, turn_gap_cv_wrap=0.0,
                    turn_gap_n_wrap=0, wrap_r_min_T=0.0, wrap_r_max_T=0.0)
    rg = np.interp(grid, ps, rs)
    k = int(round(2.0 * math.pi / 0.05))
    if len(grid) <= k:
        gaps = np.zeros(0)
    else:
        gaps = rg[k:] - rg[:-k]
    gaps = gaps[gaps > 0]
    if len(gaps) < 4:
        return dict(turns_wrap=round(turns, 3), turn_gap_mean_wrap_T=0.0, turn_gap_cv_wrap=0.0,
                    turn_gap_n_wrap=int(len(gaps)), wrap_r_min_T=round(float(rs.min()), 3),
                    wrap_r_max_T=round(float(rs.max()), 3))
    return dict(turns_wrap=round(turns, 3), turns_wrap_arclen=round(turns_arc, 3),
                turn_gap_mean_wrap_T=round(float(gaps.mean()), 3),
                turn_gap_cv_wrap=round(float(gaps.std() / max(gaps.mean(), 1e-9)), 3),
                turn_gap_n_wrap=int(len(gaps)), wrap_r_min_T=round(float(rs.min()), 3),
                wrap_r_max_T=round(float(rs.max()), 3),
                wrap_core_xy=[round(float(cen[0]), 3), round(float(cen[1]), 3)])

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

def hole_radius(img, px, c_row, c_col, search_T=1.4, max_T=6.0):
    """Radius of the empty core of the cross-section, T.

    The inscribed empty radius around a candidate centre is the smallest distance to material along 72
    rays; the hole is the largest such radius over candidate centres within `search_T` of the raster
    centroid (a spiral's hole is not always on the centroid).  0 when material sits on the centre."""
    npx = img.shape[0]
    ang = np.arange(72) * (2.0 * math.pi / 72.0)
    ca, sa = np.cos(ang), np.sin(ang)
    dd = np.arange(0.0, max_T / px, 0.5)                       # px along a ray
    best, bc = 0.0, (c_row, c_col)
    span = search_T / px
    for dr in np.linspace(-span, span, 11):
        for dc in np.linspace(-span, span, 11):
            r0, c0 = c_row + dr, c_col + dc
            ir, ic = int(round(r0)), int(round(c0))
            if not (0 <= ir < npx and 0 <= ic < npx) or img[ir, ic] != CLASS_BG:
                continue
            rr = np.rint(r0 - np.outer(sa, dd)).astype(int)
            cc = np.rint(c0 + np.outer(ca, dd)).astype(int)
            ok = (rr >= 0) & (rr < npx) & (cc >= 0) & (cc < npx)
            samp = np.where(ok, img[np.clip(rr, 0, npx - 1), np.clip(cc, 0, npx - 1)], CLASS_WRAP)
            hit = samp != CLASS_BG
            first = np.where(hit.any(axis=1), hit.argmax(axis=1), len(dd) - 1)
            rad = float(dd[first].min())
            if rad > best:
                best, bc = rad, (r0, c0)
    return round(best * px, 3), bc

def compute_metrics(xs, vs, cls, vol, Jp, nori_row, nori_col, info, layout, img, px, center, esc, extra):
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
    gaps = turn_gaps(img, c_row, c_col, px, angs)
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
    # --- conservation: sum(vol_p * J_p) / sum(vol_p).  This is the honest measure -- the class map
    # under-counts because the spread genuinely compresses and the wrapper band is rasterised over it.
    def cons(mask):
        v = vol[mask]
        return round(float(np.sum(v * Jp[mask]) / max(np.sum(v), 1e-12)), 4) if mask.any() else 0.0
    rice_m = cls == CLASS_RICE
    wrap_m = cls == CLASS_WRAP
    rice_area_map = float(np.sum(img == CLASS_RICE)) * px * px
    Jmean = float(np.mean(Jp[rice_m])) if rice_m.any() else 1.0
    conservation = cons(np.ones(len(cls), bool))
    cons_spread = cons(rice_m)
    cons_wrap = cons(wrap_m)
    cons_fill = {k: cons(cls == c) for k, c in CLASS_OF_KIND.items() if (cls == c).any()}
    # --- empty core
    hole_T, hole_rc = hole_radius(img, px, c_row, c_col)
    # nori connectivity from particles: max gap between consecutive particles of the same initial row
    max_gap = 0.0
    for r in range(info['nori_rows']):
        m = nori_row == r
        order = np.argsort(nori_col[m])
        pts_r = xs[m][order]
        rowgap = np.linalg.norm(np.diff(pts_r, axis=0), axis=1)
        max_gap = max(max_gap, float(rowgap.max()))
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
        conservation=conservation, conservation_spread=cons_spread, conservation_wrap=cons_wrap,
        conservation_fillings=cons_fill,
        hole_r_T=hole_T, hole_center_rc=[round(hole_rc[0], 1), round(hole_rc[1], 1)],
        rice_particles=int(rice_m.sum()), particles=int(len(cls)), escaped=int(esc),
        nori_max_gap_T=round(max_gap, 4), nori_particle_spacing_T=round(info['nori_dx'], 4), nori_torn=bool(torn),
        nori_components_map=int(ncomp), nori_components_map_ge20px=big,
        v_max_final=round(vmax, 4), finite=finite, stable=bool(stable),
        window_T=extra['window_T'], px_T=round(px, 5), window_center_xy=[round(center[0], 3), round(center[1], 3)],
        centroid_xy=[round(cen_world[0], 3), round(cen_world[1], 3)],
        mat=extra['mat'], grab=extra['grab'], phases=extra['phases'], timing=extra['timing'],
    )
    met.update(gaps)
    hole_world = (center[0] + (hole_rc[1] - npx / 2) * px, center[1] + (npx / 2 - hole_rc[0]) * px)
    met.update(wrapper_spiral(xs, cls, nori_row, nori_col, cen_world, info,
                              core_hint=hole_world if hole_T > 0.0 else None))
    # --- base-neutral names (the spiral bases have no rice and no nori)
    met['turns_rays'] = met['nori_turns']
    met['turns'] = met['turns_wrap'] if layout['spiral'] else met['nori_turns']
    if layout['spiral']:
        met['turn_gap_cv_rays'] = met['turn_gap_cv']
        met['turn_gap_mean_rays_T'] = met['turn_gap_mean_T']
        met['turn_gap_cv'] = met['turn_gap_cv_wrap']
        met['turn_gap_mean_T'] = met['turn_gap_mean_wrap_T']
    met['turns_min'] = met['nori_turns_min']
    met['turns_max'] = met['nori_turns_max']
    met['spread_area_ratio'] = met['rice_area_ratio']
    met['spread_area_initial_T2'] = met['rice_area_initial_T2']
    met['spread_area_map_T2'] = met['rice_area_map_T2']
    met['spread_J_mean'] = met['rice_J_mean']
    met['spread_under_filling_T'] = met['rice_under_filling_T']
    met['wrapper_max_gap_T'] = met['nori_max_gap_T']
    met['wrapper_components_map'] = met['nori_components_map']
    met['torn'] = met['nori_torn']
    met['wrap_material'] = MAT_OF_CLASS[CLASS_WRAP]
    met['spread_material'] = MAT_OF_CLASS[CLASS_SPREAD]
    met['sheet_L_T'] = layout['L']
    met['w_wrap_T'] = layout['w_wrap']
    return met

def vol_of(cls, c, info):
    return 0.0  # placeholder, replaced below via closure in main (area from particle volumes)

# ----------------------------------------------------------------------------- mat arc geometry
def enclosing_R(xnp, xc, ylift, R, q=99.5, y_bed=1.12):
    """Smallest radius whose circle centred at (xc, R + ylift) wraps the material of the ROLL.
    For a point (px, py):  (px-xc)^2 + (py-ylift-R)^2 <= R^2  <=>  R >= (u^2+w^2)/(2w), u = px-xc,
    w = py-ylift.  Only material that is already lifted off the flat sheet (py > y_bed + 0.35) and
    within a window around the roll counts, so the sheet still lying on the table cannot inflate it."""
    u = xnp[:, 0] - xc
    w = xnp[:, 1] - ylift
    m = (xnp[:, 1] > y_bed + 0.35) & (w > 0.25) & (np.abs(u) < 1.4 * R + 1.2)
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
    ap.add_argument('--tuck', type=float, default=1.0, help='maki only: how far the grabbed edge is carried in phase B (0.6..1.3)')
    ap.add_argument('--fronty', type=float, default=-1.0,
                    help='height of the lower FRONT end of the mat arc, T (default: sheet top + 0.15)')
    ap.add_argument('--lift', type=float, default=1.0,
                    help='raise the mat circle by this fraction of the incoming sheet thickness, so the roll '
                         'rides ON the sheet instead of on the table (KINEMATICS.md phase C); 0 = on the table')
    ap.add_argument('--grid', type=int, default=0, help='total grid nodes ~ grid^2 (0 = the layout default)')
    ap.add_argument('--particles', type=int, default=0, help='0 = the layout default')
    ap.add_argument('--out', type=str, default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out'))
    ap.add_argument('--frames', type=int, default=10, help='number of debug snapshots (0 = none)')
    ap.add_argument('--window', type=float, default=0.0, help='material map window side, T (0 = the layout default)')
    ap.add_argument('--curlturns', type=float, default=0.0, help='spiral bases: turns wound by the curl (0 = layout default)')
    ap.add_argument('--grabl', type=float, default=0.0,
                    help='spiral bases: length of sheet held by the fingers, T (0 = the whole coil)')
    ap.add_argument('--curlsq', type=float, default=0.0,
                    help='spiral bases: pitch squeeze of the curl (0 = CURL_SQUEEZE)')
    ap.add_argument('--rho0', type=float, default=0.0, help='spiral bases: radius of the innermost tip of the curl, T')
    ap.add_argument('--zoom', type=float, default=0.0,
                    help='also save a close-up of every debug frame, window side in T (0 = off)')
    ap.add_argument('--wrapy', type=float, default=0.0, help='override the wrapper shear yield (0 = material default)')
    ap.add_argument('--tag', type=str, default='')
    args = ap.parse_args()
    layout = LAYOUTS[args.layout]
    spiral = bool(layout['spiral'])
    global X0, X1, Y0, Y1
    X0, X1, Y0, Y1 = layout['domain']
    os.makedirs(args.out, exist_ok=True)
    tag = f'{args.layout}{args.tag}'
    tuck = min(1.3, max(0.6, args.tuck))
    lift_f = min(1.2, max(0.0, args.lift))
    # ---- per-base geometry (nothing below reads a sushi constant)
    Lsh = layout['L']; w_wrap = layout['w_wrap']; t_sp = layout['t_spread']
    y_bed = w_wrap + t_sp                       # thickness of the incoming sheet
    y_tuck = w_wrap + Y_TUCK_FRAC * t_sp
    y_front = max(0.30, y_bed + 0.15) if args.fronty < 0 else max(0.30, args.fronty)
    R_max = layout['R_max']
    window = args.window if args.window > 0 else layout['window']
    n_grid = args.grid if args.grid > 0 else layout['grid']
    n_part_t = args.particles if args.particles > 0 else layout['particles']
    MAT_OF_CLASS[CLASS_SPREAD] = layout['spread_mat']
    MAT_OF_CLASS[CLASS_WRAP] = layout['wrap_mat']
    if args.wrapy > 0:
        _e, _n, _y, _r = MATERIALS[layout['wrap_mat']]
        MATERIALS[layout['wrap_mat']] = (_e, _n, args.wrapy, _r)
    COLORS[CLASS_SPREAD] = layout['spread_color']
    COLORS[CLASS_WRAP] = layout['wrap_color']
    p_scale = MATERIALS[layout['spread_mat']][0] * layout['press_scale']
    # mat pressures are quoted in units of E_rice; scaling them by E_spread keeps the SAME relative
    # compression on a softer spread, and press_scale is the per-base hand: a roll cake is rolled, not
    # squeezed in a mat, so its pressures are a third of the sushi ones.

    aspect = (X1 - X0) / (Y1 - Y0)
    ny = int(round(n_grid / math.sqrt(aspect)))
    nx = int(round(ny * aspect))
    xs, cls, vol, nori_row, nori_col, piece, info = sample_layout(layout, n_part_t)
    n = len(cls)

    # ---------------- grab path ------------------------------------------------------------------
    rho0 = curl_turns = grab_len = psi_max = s_curl_end = rho_end = 0.0
    gi = np.zeros(0, np.int64)
    s_p = phi_p = rad_p = pv_buf = gw_buf = None
    cs = crho = cphi = csol = chf = ctopr = ccy = None
    if spiral:
        # ---- CURL (replaces the maki phases A / B / Btuck / Bhold).
        #
        # The fingers take the near end of the sheet and wind it into a coil.  The sheet is
        # inextensible, so arc length s IS the material coordinate and the only freedom is the pitch:
        # how much radius one turn adds.  The pitch at s is the thickness of what is being wound
        # there (see curl_profile), which is why the bare lead -- no spread on it -- can curl into a
        # genuinely tight first turn while the later turns open up to make room for the spread and
        # the fillings.
        #
        #   rho(s), phi(s) from curl_profile;  the wind point s_w advances at the feed speed v_c, so
        #   the coil centre xc = X_SHEET + s_w travels at v_c, and the spin rate is
        #   dphi_w/dt = v_c / rho_w -- exactly rolling without slipping.  Releasing into phase C is
        #   therefore seamless: same centre, same speed, same spin.
        #
        # A grabbed particle of the wrapper at arc length s sits at radius rad = rho(s) - (y - w/2)
        # (so the spread, which lies ABOVE the wrapper on the table, ends up INSIDE the turn, as it
        # must) and at spiral angle phi(s) measured back from the wind point.  The grab weight fades
        # in over CURL_RAMP behind the wind point and out over the last CURL_RELEASE_TURNS; ahead of
        # the wind point the sheet is FREE -- never pinned -- so it is drawn into the coil by the
        # coil itself instead of being torn off it.
        rho0 = args.rho0 if args.rho0 > 0 else layout['rho0']
        curl_turns = args.curlturns if args.curlturns != 0 else layout['curl_turns']
        squeeze = args.curlsq if args.curlsq > 0 else CURL_SQUEEZE
        cs, crho, cphi, csol, chf, ctopr, ccy = curl_profile(layout, info, rho0, squeeze)
        psi_max = float(cphi[-1]) if curl_turns <= 0 else min(2.0 * math.pi * curl_turns, float(cphi[-1]))
        s_curl_end = float(np.interp(psi_max, cphi, cs))
        rho_end = float(np.interp(psi_max, cphi, crho))
        grab_len = args.grabl if args.grabl > 0 else s_curl_end     # the fingers guide the whole coil
        # EVERY particle of the wound part is driven, not just the wrapper: the spread and the
        # fillings lie ON the wrapper, so if only the wrapper were prescribed it would slide out from
        # under them and the coil would come out hollow (that is exactly what run 6c1 did).  The map
        # below is area-preserving by construction (d(rho^2)/ds = pitch/pi), so driving the whole
        # column neither compresses nor inflates it.
        # EVERY particle is driven, fillings included.  The map is the identity at the wind point
        # (rad = rho + solid - y  <=>  world y = y), so a filling lying ON the spread goes to a radius
        # just INSIDE the laying surface -- into the gap that the pitch opened one turn earlier.  Only
        # the wrapper+spread were driven in run 6c8 and the free fillings were left behind at the wind
        # point and smeared into long arcs.
        sel = (((xs[:, 0] - X_SHEET) <= grab_len) & ((xs[:, 0] - X_SHEET) >= 0.0))
        gi = np.nonzero(sel)[0]
        n_grab = int(len(gi))
        grab_np = np.where(sel, 1.0, 0.0).astype(np.float32)   # initial weight; recomputed each step
        s_p = np.clip(xs[gi, 0].astype(np.float64) - X_SHEET, 0.0, grab_len)
        y_p = xs[gi, 1].astype(np.float64)
        phi_p = np.interp(s_p, cs, cphi)
        rho_p = np.interp(s_p, cs, crho)
        pc_p = piece[gi]
        lay_p = np.interp(s_p, cs, csol)
        # wrapper + spread: an isometry outward from the laying surface, rad = rho + (solid - y).  The
        # spread is a fluid trapped between two turns of wrapper, so the gap a turn opens for it is
        # exactly its flat thickness -- no thick-layer correction.
        rad_p = rho_p + (lay_p - y_p)
        # a filling PIECE is placed RIGIDLY in the slot the pitch opened for it one turn earlier: its
        # underside on the laying surface of its own arc position, its width laid along that surface.
        # Mapping filling particles by arc length like the sheet squeezes them tangentially by r/rho
        # and stretches them radially -- a 3 T strawberry comes out as a spike through the middle of
        # the coil (run 6c12), which is not what a strawberry does.
        # A driven particle's target is  (xc, cy) + A * r_hat(Th) + B * t_hat(Th),  Th = -pi/2 - phi_w
        # + phi_p, r_hat = (cos Th, sin Th), t_hat = (-sin Th, cos Th).  A sheet particle has B = 0 and
        # its own phi(s): the sheet bends.  A filling piece shares ONE phi (its centre's) and carries
        # B = the offset along the piece, so the whole piece is placed as a rigid body -- a strawberry
        # neither bends nor fans out.
        tan_p = np.zeros_like(rad_p)
        for j in range(len(info['rects'])):
            mj = pc_p == j
            if not mj.any():
                continue
            u, by, wj, hj, _rnd, _c = info['rects'][j]
            s_c = u + 0.5 * wj
            rho_c = float(np.interp(s_c, cs, crho)); phi_c = float(np.interp(s_c, cs, cphi))
            lay_c = float(np.interp(s_c, cs, csol))
            phi_p[mj] = phi_c
            rad_p[mj] = rho_c - (y_p[mj] - lay_c)
            tan_p[mj] = s_p[mj] - s_c
        srt = np.argsort(s_p)
        gi = gi[srt]; s_p = s_p[srt]; phi_p = phi_p[srt]; rad_p = rad_p[srt]; tan_p = tan_p[srt]
        s_sorted = s_p
        pv_buf = np.zeros((n, 2), np.float32)
        gw_buf = np.zeros(n, np.float32)
        h_top = max([r[1] + r[3] for r in info['rects']] + [y_bed])
        y_edge0 = 0.5 * w_wrap
        s_fold = s_fold_base = x_p = b_ap = th_end = len_arc = 0.0
        R_init = layout['R_init'] if layout['R_init'] > 0 else rho0
        def Pg(th):
            return (0.0, 0.0)
        def dPg(th):
            return (1.0, 0.0)
        def Gc(th):
            return (0.0, 0.0)
    else:
        if info['rects']:
            s_fold_base = max(r[0] + r[2] for r in info['rects']) + S_FOLD_MARGIN
            h_top = max(r[1] + r[3] for r in info['rects'])
        else:
            s_fold_base = S_FOLD_EMPTY
            h_top = y_bed
        s_fold = tuck * s_fold_base
        x_p = 0.5 * s_fold                      # half-span of the fold arc (the crease sits near here)
        b_ap = min(x_p, h_top + B_CLEAR)        # apex height of the fold arc
        y_edge0 = 0.5 * w_wrap
        th_end = math.pi - TH_END_MARGIN
        # Fold arc of the grabbed edge (phases A and B):
        #     P(th) = ( x_p*(1 - cos th),  y_edge0 + b_ap*sin th ),  th: 0 -> th_end
        # a half ELLIPSE with semi-axes x_p (horizontal) and b_ap (vertical).  |P - (x_p, y_edge0)| <= x_p
        # for every th, so the sheet segment from the crease to the grabbed edge is never stretched.
        def Pg(th):
            return (x_p * (1.0 - math.cos(th)), y_edge0 + b_ap * math.sin(th))
        def dPg(th):
            return (x_p * math.sin(th), b_ap * math.cos(th))
        # tapered grab weight: 1 on the first half of the strip, fading to 0 at GRAB_W
        w_grab = np.clip((GRAB_W - xs[:, 0]) / (0.5 * GRAB_W), 0.0, 1.0)
        grab_np = np.where(cls == CLASS_WRAP, w_grab, 0.0).astype(np.float32)
        n_grab = int((grab_np > 0).sum())
        # the "fingers": a rigid disk of radius R_FINGER around the centroid of the grabbed strip
        g0 = (float(xs[grab_np == 1, 0].mean()), float(xs[grab_np == 1, 1].mean()))
        goff = (g0[0] - 0.0, g0[1] - y_edge0)
        def Gc(th):
            pp = Pg(th)
            return (pp[0] + goff[0], pp[1] + goff[1])
        R_init = 0.5 * (b_ap + h_top + 1.2) + 0.3

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
    if spiral:
        S['pv'].from_numpy(pv_buf)
    dt = CFL * dx / cmax
    omega = OMEGA_REF * args.speed           # spiral bases: constant spin of the curl
    v_c = (omega * rho_end) if spiral else (V_PULL_REF * args.speed)   # feed speed (phase C uses it)
    v_g = V_GRAB_REF * args.speed            # grabbed-edge speed along its arc, maki phases A/B
    x_end = X_SHEET + Lsh + X_END_EXTRA

    # step budget (an upper bound; phase C can finish early, phase D is fixed)
    if spiral:
        t_fold = psi_max / omega             # duration of the curl
        t_tuck = 0.0
        xc_C0 = X_SHEET + s_curl_end
        t_rollmax = 0.0
        t_total_max = t_fold + T_SETTLE + 20.0
    else:
        len_arc = 0.0
        for i in range(600):
            p0 = Pg(th_end * i / 600.0); p1 = Pg(th_end * (i + 1) / 600.0)
            len_arc += math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        t_fold = len_arc / v_g
        t_tuck = max(0.0, (Pg(th_end)[1] - y_tuck)) / (V_TUCK_FRAC * v_g)
        xc_C0 = 1.35 * x_p
        t_rollmax = (x_end - xc_C0) / v_c
        t_total_max = t_fold + t_tuck + T_HOLD + t_rollmax + T_CLOSE + T_PRESS_MAX
    n_steps_max = int(math.ceil(t_total_max / dt))

    print(f'[{layout["name"]}] grid {nx}x{ny} dx={dx:.4f} particles={n} grabbed={n_grab} hp={info["hp"]:.4f} '
          f'wrap rows={info["nori_rows"]} dt={dt:.5f} cmax={cmax:.2f} v_c={v_c} L={Lsh} w_wrap={w_wrap} '
          f'area(spread/wrap/fill)={info["area_spread"]:.1f}/{info["area_wrap"]:.1f}/{info["area_fill"]:.1f} '
          f'R_init={R_init:.2f} t_start={t_fold:.1f} t_rollmax={t_rollmax:.1f} steps<={n_steps_max}', flush=True)
    if spiral:
        A_tot = info['area_spread'] + info['area_wrap'] + info['area_fill']
        Rpred = math.sqrt(A_tot / math.pi)
        print(f'  curl: rho0={rho0} turns={curl_turns} squeeze={squeeze} -> rho_end={rho_end:.2f}, '
              f'{s_curl_end:.1f} T of sheet wound (grab {grab_len:.1f} T, {n_grab} particles), '
              f'ccy {ccy[0]:.2f}..{ccy.max():.2f}', flush=True)
        print(f'  predicted from area {A_tot:.1f} T^2: Rout={Rpred:.2f}  turns=L/sqrt(pi*A)='
              f'{Lsh / math.sqrt(math.pi * A_tot):.2f}  hole~{rho0 - 0.5 * layout["taper_min"] * w_wrap:.2f}', flush=True)

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
    phase = 'CURL' if spiral else 'A'
    last_phase = phase
    t_phase = 0.0; th_g = 0.0
    t_engage = None                      # time the mat engaged
    xc = X_SHEET if spiral else xc_C0
    s_w = 0.0; rho_w = rho0; phi_w = 0.0  # curl state: wound length, wind radius, wound angle
    lay_w = float(csol[0]) if spiral else 0.0
    v_cap = CURL_V_CAP * omega * max(rho_end, 1.0)
    gp = Pg(0.0)                          # current grabbed-edge point (for the debug frames)
    gc = Gc(0.0)                          # current finger-disk centre
    gv_now = (0.0, 0.0)
    gom = 0.0
    ylift = 0.0; vly = 0.0
    err_last = 1.0
    R_curl = R_init
    ylift_target = lift_f * y_bed
    spread_idx = np.nonzero(cls == CLASS_SPREAD)[0]
    n_spread = len(spread_idx)
    phase_marks = {phase: 0.0}
    step = 0
    frame_i = 0

    def snap(pth):
        save_frame(S, cls, xc, R, th_lo, th_hi, shp, pth, t, F_f, gp, grabbing, ylift=ylift)
        if args.zoom > 0:
            save_frame(S, cls, xc, R, th_lo, th_hi, shp, pth[:-4] + '_z.png', t, F_f, gp, grabbing,
                       zoom=((xc, min(R, 0.45 * args.zoom) + ylift), args.zoom), ylift=ylift)

    while True:
        # ---------------- kinematic schedule ------------------------------------------------------
        grabbing = 1
        engaged = ((phase != 'CURL') or (t_engage is not None)) if spiral else (phase not in ('A', 'B'))
        if phase == 'CURL':
            phi_w = min(phi_w + omega * dt, psi_max)   # constant angular velocity (see OMEGA_REF)
            s_w = float(np.interp(phi_w, cphi, cs))
            rho_w = float(np.interp(s_w, cs, crho))
            xc = X_SHEET + s_w                         # the wind point (= the coil's contact)
            lay_w = float(np.interp(s_w, cs, csol))
            cy = float(np.interp(s_w, cs, ccy))        # centre height: rho + solid, higher over a lump
            R_curl = rho_w                             # the mat IS the coil's laying circle
            Th = (-0.5 * math.pi - phi_w) + phi_p
            rel = min(1.0, max(0.0, (psi_max - phi_w) / (2.0 * math.pi * CURL_RELEASE_TURNS)))
            # only the band [s_lo, s_w] is driven: fade in over CURL_RAMP behind the wind point, hold
            # for CURL_BAND_TURNS turns, fade out over CURL_BAND_FADE turns, free after that.
            phi_lo = phi_w - 2.0 * math.pi * (CURL_BAND_TURNS + CURL_BAND_FADE)
            s_lo = float(np.interp(phi_lo, cphi, cs)) if phi_lo > 0 else 0.0
            i0 = int(np.searchsorted(s_sorted, s_lo, 'left'))
            i1 = int(np.searchsorted(s_sorted, s_w, 'right'))
            gw_buf[gi] = 0.0
            if i1 > i0:
                sl = slice(i0, i1)
                idx = gi[sl]
                dphi = (phi_w - phi_p[sl]) / (2.0 * math.pi)
                w_out = np.clip((CURL_BAND_TURNS + CURL_BAND_FADE - dphi) / CURL_BAND_FADE, 0.0, 1.0)
                wp = np.clip((s_w - s_p[sl]) / CURL_RAMP, 0.0, 1.0) * w_out * rel
                gw_buf[idx] = wp
                Thb = Th[sl]
                cb = np.cos(Thb); sb = np.sin(Thb)
                txb = xc + rad_p[sl] * cb - tan_p[sl] * sb
                tyb = cy + rad_p[sl] * sb + tan_p[sl] * cb
                dfc = float(tyb.min())
                if dfc < 0.0:                       # never drive the coil through the table
                    cy -= dfc; tyb -= dfc
                xcur = S['x'].to_numpy()[idx]
                vx = (txb - xcur[:, 0]) / dt
                vy = (tyb - xcur[:, 1]) / dt
                sp_ = np.hypot(vx, vy)
                k = np.where(sp_ > v_cap, v_cap / np.maximum(sp_, 1e-9), 1.0)
                pv_buf[idx, 0] = vx * k
                pv_buf[idx, 1] = vy * k
                S['pv'].from_numpy(pv_buf)
                jj = int(np.argmax(s_p[sl]))
                gp = (float(txb[jj]), float(tyb[jj]))
            S['grab'].from_numpy(gw_buf)
            gc = gp
            gv_now = (0.0, 0.0); gom = 0.0
            if CURL_MAT_ON and t_engage is None and phi_w >= 2.0 * math.pi * CURL_ENGAGE_TURNS:
                t_engage = t; phase_marks['CURLmat'] = t
            if phi_w >= psi_max - 1e-9 or s_w >= s_curl_end - 1e-9:
                gw_buf[:] = 0.0; S['grab'].from_numpy(gw_buf)
                xc_C0 = xc
                # A spiral roll is finished when the sheet runs out: there is no flap to press on and
                # no tuck to close.  What follows is the cook's hands CUPPING it -- a static circle
                # just around the roll that stops it spinning and keeps the tail down while the
                # interior settles.  Rolling it on under the mat (phase C) and then squeezing it
                # (D_close/D_press) is a maki move, and on a roll cake it tore the turns apart:
                # max gap 0.63 T at the end of the curl, 2.7 T after the press (run 6c14).
                xnp = S['x'].to_numpy()
                xc = float(xnp[:, 0].mean()); cym = float(xnp[:, 1].mean())
                rr = np.hypot(xnp[:, 0] - xc, xnp[:, 1] - cym)
                R = float(np.percentile(rr, 99.7)) * 1.02
                ylift = cym - R; ylift_target = ylift; Rdot = 0.0
                phase = 'SETTLE'; t_phase = 0.0; phase_marks['SETTLE'] = t
        elif phase == 'A' or phase == 'B':
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
            if gp[1] <= y_tuck:
                phase = 'Bhold'; t_phase = 0.0; phase_marks['Bhold'] = t
        elif phase == 'Bhold':
            gom = 0.0
            gv_now = (0.0, 0.0)
            if t_phase >= T_HOLD:
                phase = 'C'; t_phase = 0.0; phase_marks['C'] = t
                xnp = S['x'].to_numpy()
                hi = xnp[:, 1] > y_bed * 1.15
                xc = float(xnp[hi, 0].mean()) if hi.sum() > 20 else xc_C0
                xc_C0 = xc
        elif phase == 'C':
            grabbing = 0
            xc += v_c * dt
        elif phase in ('D_close', 'D_press', 'SETTLE'):
            grabbing = 0

        # ---------------- mat lift + arc -----------------------------------------------------------
        ylift_prev = ylift
        if phase == 'CURL':
            # The mat is the coil's LAYING circle: radius rho_w, centre (xc, rho_w + lay_w), i.e. lifted
            # to the top of the incoming sheet.  Two things must both hold, and getting either wrong
            # destroys the coil (runs 6c1-6c4):
            #   * centre = coil centre, radius = rho_w  -> the mat hugs every earlier turn, because one
            #     full turn adds exactly `pitch` to rho, so the outer boundary of the coil IS rho_w at
            #     every angle except inside the newest partial turn;
            #   * no slip at the LAYING surface, not at the table: the coil spins at v_c/rho_w, and the
            #     mat tangent to y = lay_w with vspin = v_c spins at exactly the same rate.  A mat sized
            #     to the coil's outer radius (rho_w + lay_w) spins ~2x too slow and, being sticky
            #     (mu_mat = 2), shears the coil open -- which is what run 6c3/6c4 showed.
            ylift_prev2 = ylift
            ylift = lay_w
            vly = (ylift - ylift_prev2) / dt
            th_f_max = arc_front_max(R, max(0.0, y_front - ylift))
        elif phase == 'C':
            tgt = ylift_target * min(1.0, t_phase / T_LIFT)
        elif phase == 'D_close':
            tgt = ylift_target if spiral else ylift_target * max(0.0, 1.0 - t_phase / T_CLOSE)
        else:
            tgt = ylift_target if spiral else 0.0
        if phase == 'SETTLE':
            tgt = ylift_target
        if phase != 'CURL':
            ylift += max(-V_LIFT * dt, min(V_LIFT * dt, tgt - ylift))
            vly = (ylift - ylift_prev) / dt
            th_f_max = arc_front_max(R, max(0.0, y_front - ylift))
        if not engaged:
            th_lo, th_hi, vc_now, P_ref, shp = 1.0, 0.0, 0.0, P_ROLL_REF * args.press * p_scale, 0
        elif phase == 'CURL':
            # a cap around theta = pi that widens, exactly as the maki fold cap -- but it travels
            # forward with the curl and spins with it, so it never scrubs the spread
            frac = min(1.0, (t - t_engage) / T_WRAP)
            half = 0.5 + frac * (0.5 * PHI_ROLL - 0.5)
            th_lo = max(TH_BACK_MIN, math.pi - half)
            th_hi = min(th_f_max, math.pi + half)
            vc_now = v_c
            P_ref = P_ROLL_REF * args.press * p_scale * (P_FOLD_FRAC + (1.0 - P_FOLD_FRAC) * frac)
            shp = 0
        elif phase in ('B', 'Btuck', 'Bhold'):
            frac = min(1.0, (t - t_engage) / T_WRAP)
            half = 0.5 + frac * (0.5 * PHI_ROLL - 0.5)
            th_lo = max(TH_BACK_MIN, math.pi - half)
            th_hi = min(th_f_max, math.pi + half)
            vc_now = 0.0
            P_ref = P_FOLD_FRAC * P_ROLL_REF * args.press * p_scale
            shp = 0
        elif phase == 'C':
            th_hi = th_f_max
            th_lo = max(TH_BACK_MIN, th_hi - PHI_ROLL)
            vc_now = v_c
            P_ref = P_ROLL_REF * args.press * p_scale
            shp = 0
        elif phase == 'D_close':
            f = min(1.0, t_phase / T_CLOSE)
            th_hi_c = th_f_max
            th_lo_c = max(TH_BACK_MIN, th_hi_c - PHI_ROLL)
            th_lo = (1 - f) * th_lo_c
            th_hi = (1 - f) * th_hi_c + f * 2.0 * math.pi
            vc_now = 0.0
            P_ref = (P_ROLL_REF + f * (P_PRESS_REF - P_ROLL_REF)) * args.press * p_scale
            shp = 0
        elif phase == 'SETTLE':
            # the cup travels and turns WITH the roll: a static cup would brake a roll that is still
            # translating at omega*rho and spinning at omega, and a sticky one (mu_mat = 2) then
            # kneads the outer turns into waves (run 6c15).
            th_lo, th_hi = 0.0, 2.0 * math.pi
            vc_now = v_c * max(0.0, 1.0 - t_phase / (0.7 * T_SETTLE))
            P_ref = P_PRESS_REF * args.press * p_scale
            shp = 0
        else:  # D_press
            th_lo, th_hi = 0.0, 2.0 * math.pi
            vc_now = 0.0
            P_ref = P_PRESS_REF * args.press * p_scale
            shp = shape

        # The mat circle is tangent to the TOP OF THE INCOMING SHEET (y = ylift), not to the table, so
        # the bed can pass under the roll instead of being bulldozed. The instantaneous centre is then
        # the circle's own bottom point => plain rolling without slipping, vspin = vc.
        vspin = vc_now
        if phase == 'SETTLE':
            vspin = omega * R * (vc_now / max(v_c, 1e-9))
            xc += vc_now * dt
        S['substep'](dt, xc, R, Rdot, ylift, vly, vc_now, vspin, th_lo, th_hi, shp, MU_MAT,
                     gc[0], gc[1], gv_now[0], gv_now[1], gom, 0.0 if phase == 'CURL' else R_FINGER,
                     grabbing, 1 if phase == 'CURL' else 0)

        # ---------------- radius controller --------------------------------------------------------
        fnow = S['fn'][None]
        F_f += (fnow - F_f) * min(1.0, dt / tau_f)
        if phase == 'CURL':
            # kinematic: the mat IS the coil's outer circle (see above).  R_MIN does not apply -- the
            # coil legitimately starts smaller than any maki.
            Rdot = max(-V_RADIAL_CURL, min(V_RADIAL_CURL, (R_curl - R) / dt))
            R += Rdot * dt
        elif phase == 'SETTLE':
            Rdot = 0.0                       # the cupping hands neither squeeze nor let go
        else:
            if step % ctrl_every == 0:
                arc_len = R * max(th_hi - th_lo, 0.0) if shp == 0 else 8 * R
                F_t = P_ref * arc_len
                err = (F_f - F_t) / max(F_t, 1e-6)
                err_last = err
                vrad = V_RADIAL_PRESS if phase in ('D_close', 'D_press') else V_RADIAL
                Rdot = vrad * max(-1.0, min(1.0, err))
                if R <= R_MIN and Rdot < 0: Rdot = 0.0
                if R >= R_max and Rdot > 0: Rdot = 0.0
            R += Rdot * dt
            R = min(max(R, R_MIN), R_max)
        t += dt; t_phase += dt

        # ---------------- phase C -> D: the sheet is fully picked up --------------------------------
        if phase == 'C' and step % 200 == 0:
            xnp = S['x'].to_numpy()
            # how thick is the sheet still coming in? (spread bed vs. bare wrapper end)
            rf = int(np.sum((xnp[spread_idx, 0] > xc + 0.8 * R) & (xnp[spread_idx, 1] < 2.0 * y_bed)))
            ylift_target = lift_f * (y_bed if rf > 0.01 * n_spread else (w_wrap + 0.15))
            d = np.hypot(xnp[:, 0] - xc, xnp[:, 1] - (R + ylift))
            outs = d > R + 0.5
            ahead = float((xnp[outs, 0] - xc).max()) if outs.any() else -1e9
            if ahead < 0.9 * R or xc >= x_end:
                phase = 'D_close'; t_phase = 0.0; phase_marks['D_close'] = t
                # close the mat AROUND everything, tail included
                xc = float(xnp[:, 0].mean())
                if spiral:
                    # a spiral roll is already round and sits well off the table: put the mat circle
                    # concentric with the material instead of tangent to the table (the maki formula
                    # below divides by the height above the table and blows up on a tail lying flat)
                    cym = float(xnp[:, 1].mean())
                    rr = np.hypot(xnp[:, 0] - xc, xnp[:, 1] - cym)
                    R = min(R_max, 1.03 * float(np.percentile(rr, 99.5)))
                    ylift = cym - R          # CONCENTRIC with the material; may be negative.  Clamping
                    ylift_target = ylift     # it at 0 put the mat centre 2 T above the roll centre and
                                             # drove its lower half straight through the roll (6c13).
                else:
                    yy = np.maximum(xnp[:, 1], 0.05)
                    need = (xnp[:, 0] - xc) ** 2 + yy ** 2
                    need = need / (2.0 * yy)
                    R = min(R_max, 1.8 * R, max(R, 1.03 * float(np.percentile(need, 99.5))))
                Rdot = 0.0
        if phase == 'D_close' and t_phase >= T_CLOSE:
            phase = 'D_press'; t_phase = 0.0; phase_marks['D_press'] = t
        if phase == 'SETTLE' and t_phase >= T_SETTLE:
            phase_marks['end'] = t
            if args.frames:
                snap(os.path.join(frames_dir, f'f{step:07d}_{phase}.png'))
            break
        if phase == 'D_press' and t_phase >= T_PRESS and (abs(err_last) < 0.08 or t_phase >= T_PRESS_MAX):
            phase_marks['end'] = t
            if args.frames:
                snap(os.path.join(frames_dir, f'f{step:07d}_{phase}.png'))
            break

        if step % 400 == 0:
            log.append(dict(t=round(t, 2), ph=phase, xc=round(xc, 3), R=round(R, 3),
                            lo=round(th_lo, 3), hi=round(th_hi, 3), F=round(F_f, 4), Ft=round(P_ref * (R * max(th_hi - th_lo, 0.0) if shp == 0 else 8 * R), 4)))
        if phase != last_phase:
            _xp = S['x'].to_numpy(); _g = 0.0; _at = 0.0
            for _r in range(info['nori_rows']):
                _m = nori_row == _r; _o = np.argsort(nori_col[_m]); _pp = _xp[_m][_o]
                _gg = np.linalg.norm(np.diff(_pp, axis=0), axis=1)
                if _gg.max() > _g:
                    _g = float(_gg.max()); _at = float(nori_col[_m][_o][int(np.argmax(_gg))]) / info['nori_cols'] * Lsh
            print(f'  -> phase {phase} at t={t:.1f}  wrapper max gap={_g:.3f} T at s={_at:.1f} T  R={R:.2f}', flush=True)
        if args.frames and phase != last_phase:
            snap(os.path.join(frames_dir, f'f{step:07d}_{phase}.png'))
        last_phase = phase
        if args.frames and step % snap_every == 0:
            snap(os.path.join(frames_dir, f'f{step:07d}_{phase}.png'))
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
    img, px = rasterize(xs_f, cls, info['hp'], info['wrap_dy'], center, window, 600)
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
    extra = dict(layout=args.layout, speed=args.speed, press=args.press, tuck=tuck, R=R, window_T=window,
                 mat=dict(v_pull=v_c, P_roll=P_ROLL_REF * args.press * p_scale, P_press=P_PRESS_REF * args.press * p_scale,
                          P_fold=P_FOLD_FRAC * P_ROLL_REF * args.press * p_scale, p_scale=p_scale, mu_mat=MU_MAT,
                          mu_table=MU_TABLE, press_shape=layout['press_shape'], phi_roll=PHI_ROLL, y_front_min=y_front,
                          t_lift=T_LIFT, lift_frac=lift_f, th_back_min=TH_BACK_MIN, y_bed=y_bed,
                          press_scale=layout['press_scale'],
                          R_init=round(R_init, 3), R_max=R_max, xc_C0=round(xc_C0, 3),
                          xc_final=round(xc, 3), x_end=x_end),
                 grab=(dict(kind='curl', grab_len_T=round(grab_len, 2), particles=n_grab, rho0_T=rho0,
                            squeeze=squeeze if spiral else 0.0,
                            cy_max_T=round(float(ccy.max()), 3) if spiral else 0.0,
                            lump_spread_turns=CURL_LUMP_SPREAD,
                            curl_turns=curl_turns, rho_end_T=round(rho_end, 3), sheet_wound_T=round(s_curl_end, 2),
                            v_feed=v_c, omega=omega, band_turns=CURL_BAND_TURNS,
                            band_fade=CURL_BAND_FADE, ramp_T=CURL_RAMP,
                            release_turns=CURL_RELEASE_TURNS)
                       if spiral else
                       dict(kind='fold', width_T=GRAB_W, finger_R=R_FINGER, apex_b=round(b_ap, 3), particles=n_grab,
                            v_grab=v_g, s_fold=round(s_fold, 3), s_fold_base=round(s_fold_base, 3),
                            semi_axis_x=round(x_p, 3), y_edge0=round(y_edge0, 3), th_end=round(th_end, 3),
                            y_tuck=round(y_tuck, 3), t_hold=T_HOLD, arc_len=round(len_arc, 3), h_top=round(h_top, 3))),
                 phases=ph,
                 timing=dict(seconds=round(elapsed, 1), steps=step, dt=round(dt, 6), grid=[nx, ny], dx=round(dx, 5),
                             particles=n, hp=round(info['hp'], 5), t_end=round(t, 2)))
    met = compute_metrics(xs_f, vs_f, cls, vol, Jp, nori_row, nori_col, info, layout, img, px, center,
                          esc_total, extra)
    met['base'] = layout['name']
    met['spiral'] = spiral
    # --- analytic targets for the SAME geometry (no air between the turns, no compaction)
    #   turns_profile : the honest one -- integrate d(phi) = ds / rho(s) over the whole sheet with the
    #                   pitch profile that the fillings actually produce (curl_profile).
    #   turns_stand   : what the stand's own formula gives, which knows only T + w and ignores the
    #                   fillings:  Rout = sqrt(L*(T+w)/pi + r0^2),  turns = (Rout - r0)/(T + w).
    if spiral:
        _t_prof = float(cphi[-1] / (2.0 * math.pi))
        _P = w_wrap + t_sp
        _R_stand = math.sqrt(Lsh * _P / math.pi + 0.25 ** 2)
        _A = info['area_spread'] + info['area_wrap'] + info['area_fill']
        met['target'] = dict(turns_profile=round(_t_prof, 3),
                             turns_stand=round((_R_stand - 0.25) / _P, 3),
                             Rout_stand_T=round(_R_stand, 3),
                             Rout_area_T=round(math.sqrt(_A / math.pi), 3),
                             area_T2=round(_A, 2), hole_target_T=round(rho0, 3))
        met['turns_vs_profile'] = round(met['turns'] - _t_prof, 3)
        met['turns_vs_stand'] = round(met['turns'] - (_R_stand - 0.25) / _P, 3)
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
               zoom=(center, window))
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
