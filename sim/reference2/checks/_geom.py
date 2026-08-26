"""The ONE place the checks in this directory read the run's geometry from.

Until 26.08.2026 every script here kept its own copy of `T = 1.0, W_NORI = 0.12, L_SHEET = 38.7`
(and pitch H_NOM = 1.12). When run.py's thicknesses were corrected to the sourced ones -- rice bed
1.4 U = 7 mm, nori 0.02 U = 0.1 mm, sheet 42 U = 21 cm -- those copies would have gone on judging
the NEW particle dumps by the OLD spiral pitch. Nothing would have raised: the checkers would have
printed plausible, wrong numbers. So: no third copy of the numbers. Import them.

`assert_same_geometry(met)` is the second half of the guard: a metrics file carries a `geometry`
stamp since 26.08.2026, and pointing a checker at a dump made with different constants must be loud.
"""
import importlib.util, os, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_RUN = os.path.join(_HERE, '..', 'run.py')


def _load():
    spec = importlib.util.spec_from_file_location('reference2_run', _RUN)
    m = importlib.util.module_from_spec(spec)
    sys.modules['reference2_run'] = m
    spec.loader.exec_module(m)          # gstaichi is imported inside build(), not at module level
    return m


run = _load()

U_MM = run.U_MM
T_RICE = run.T_RICE
W_NORI = run.W_NORI
H_SHEET = run.H_SHEET          # spiral pitch, U -- what these scripts used to call H_NOM
L_SHEET = run.L_SHEET
L_FLAP = run.L_FLAP
R_MAT_MIN = run.R_MAT_MIN
BG_HOLE_T = run.BG_HOLE_T
WR_DS = run.WR_DS
WR_KAPPA_MIN = run.WR_KAPPA_MIN
WR_NOSE_T = run.WR_NOSE_T
WR_EDGE_T = run.WR_EDGE_T
WR_FIT_T = run.WR_FIT_T
PACK_AIR = run.PACK_AIR
CORNER_R = run.CORNER_R


def assert_same_geometry(met, strict=False):
    """Warn (or raise) if `met` was produced with constants other than the ones imported above.

    A metrics file written before 26.08.2026 has no `geometry` key at all -- that alone means it is
    the old geometry, because the stamp was added together with the correction.
    """
    g = met.get('geometry')
    if g is None:
        msg = ('WARNING: this metrics file has no `geometry` stamp, so it predates the thickness '
               'correction of 26.08.2026 (T = 1.0, w = 0.12, L = 38.7). The numbers below are '
               'computed with the CURRENT constants '
               f'(T_rice {T_RICE}, w {W_NORI}, L {L_SHEET}) and do not apply to it.')
    else:
        bad = [k for k, v in (('T_rice_U', T_RICE), ('w_nori_U', W_NORI), ('L_sheet_U', L_SHEET),
                              ('L_flap_U', L_FLAP)) if abs(g.get(k, float('nan')) - v) > 1e-9]
        if not bad:
            return True
        msg = (f'WARNING: geometry mismatch on {bad}: the dump was made with {g}, the checks are '
               f'using T_rice {T_RICE}, w {W_NORI}, L {L_SHEET}, flap {L_FLAP}.')
    if strict:
        raise SystemExit(msg)
    print(msg, file=sys.stderr)
    return False
