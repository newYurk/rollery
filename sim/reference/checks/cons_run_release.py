"""run.py + a release phase E, WITHOUT touching run.py.  (conservation/leakage attack)

The reference stops integrating at the instant phase D_press reaches force equilibrium: it measures
the roll WHILE the mat is still squeezing it, so Sum(vol*J)/Sum(vol) reads the elastic compression
under the press. This wrapper loads run.py's source, patches in a phase `E_relax` (mat arc emptied
-> no contact, P_ref = 0, ring lift released) lasting --relax time units, and only then measures.
Solver, layouts and metric code are the unmodified reference.

  python cons_run_release.py --layout 1 --relax 30 --frames 0 --out ./out_cons_relax --tag r30
"""
import os, sys, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'run.py')

RELAX = 30.0
if '--relax' in sys.argv:
    i = sys.argv.index('--relax')
    RELAX = float(sys.argv[i + 1])
    del sys.argv[i:i + 2]

s = open(SRC).read()


def sub(old, new):
    global s
    assert s.count(old) == 1, f'patch anchor not unique/missing:\n{old[:120]}'
    s = s.replace(old, new)


# 1. phase targets: D_press stops being the last branch; E_relax disengages the mat completely
sub("""        else:  # D_press
            th_lo, th_hi = 0.0, 2.0 * math.pi
            vc_now = 0.0
            P_ref = P_PRESS_REF * args.press
            shp = shape
""",
    """        elif phase == 'D_press':
            th_lo, th_hi = 0.0, 2.0 * math.pi
            vc_now = 0.0
            P_ref = P_PRESS_REF * args.press
            shp = shape
        else:  # E_relax: mat lifted away, roll left on the table to spring back
            th_lo, th_hi = 1.0, 0.0          # empty arc -> the contact test th_hi > th_lo fails
            vc_now = 0.0
            P_ref = 0.0
            shp = 0
""")

# 2. no pitch drive, no grab, no radius drive during the release
sub("if (engaged and phase not in ('D_close', 'D_press'))",
    "if (engaged and phase not in ('D_close', 'D_press', 'E_relax'))")
sub("        elif phase in ('D_close', 'D_press'):\n            grabbing = 0",
    "        elif phase in ('D_close', 'D_press', 'E_relax'):\n            grabbing = 0")
sub("        R += Rdot * dt\n", "        R += (0.0 if phase == 'E_relax' else Rdot) * dt\n")

# 3. D_press no longer ends the run: it hands over to E_relax, which ends it
sub("""        if phase == 'D_press' and t_phase >= T_PRESS and (abs(err_last) < 0.08 or t_phase >= t_press_max):
            phase_marks['end'] = t
            if args.frames:
                save_frame(S, cls, xc, R, th_lo, th_hi, shp, os.path.join(frames_dir, f'f{step:07d}_{phase}.png'), t, F_f, gp, grabbing, ylift=ylift)
            break
""",
    """        if phase == 'D_press' and t_phase >= T_PRESS and (abs(err_last) < 0.08 or t_phase >= t_press_max):
            phase_marks['press_end'] = t
            if args.frames:
                save_frame(S, cls, xc, R, th_lo, th_hi, shp, os.path.join(frames_dir, f'f{step:07d}_{phase}.png'), t, F_f, gp, grabbing, ylift=ylift)
            phase = 'E_relax'; t_phase = 0.0; phase_marks['E_relax'] = t
        if phase == 'E_relax' and t_phase >= T_RELAX_PATCH:
            phase_marks['end'] = t
            if args.frames:
                save_frame(S, cls, xc, R, th_lo, th_hi, shp, os.path.join(frames_dir, f'f{step:07d}_{phase}.png'), t, F_f, gp, grabbing, ylift=ylift)
            break
""")

# 4. step budget must cover the release
sub("    n_steps_max = int(math.ceil(t_total_max / dt))",
    "    n_steps_max = int(math.ceil((t_total_max + T_RELAX_PATCH) / dt))")

s = s.replace("GRAVITY = 0.01", f"GRAVITY = 0.01\nT_RELAX_PATCH = {RELAX}", 1)

# gstaichi inspects kernel source on disk, so the patched reference is written out and run as a script
gen = os.path.join(HERE, '_cons_run_with_release.py')
open(gen, 'w').write(s)
sys.exit(subprocess.call([sys.executable, gen] + sys.argv[1:]))
