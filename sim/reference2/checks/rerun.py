#!/usr/bin/env python3
"""Driver: run reference2/run.py unmodified, optionally with one material parameter overridden.

    ../.venv/bin/python checks/rerun.py --nu 0.45 --layout 4 --out checks/out --tag nu45_4

Everything after the driver's own flags is handed to run.py's own argv. run.py is imported, not
edited: MATERIALS is patched in the module namespace before main() reads it (run.py line 1126).
"""
import os, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'run.py')

nu = None
argv = []
it = iter(sys.argv[1:])
for a in it:
    if a == '--nu':
        nu = float(next(it))
    else:
        argv.append(a)

spec = importlib.util.spec_from_file_location('ref2run', RUN)
mod = importlib.util.module_from_spec(spec)
sys.modules['ref2run'] = mod
mod.__name__ = 'ref2run'          # keep the __main__ guard shut so we control the call
spec.loader.exec_module(mod)

if nu is not None:
    E, _nu, ty, rho = mod.MATERIALS['rice']
    mod.MATERIALS['rice'] = (E, nu, ty, rho)
    K_old = E / (3 * (1 - 2 * _nu))
    K_new = E / (3 * (1 - 2 * nu))
    print(f'[rerun] rice nu {_nu} -> {nu};  bulk modulus K {K_old:.3f} -> {K_new:.3f} E_rice '
          f'(x{K_new / K_old:.2f})', flush=True)

os.chdir(os.path.join(HERE, '..'))
sys.argv = ['run.py'] + argv
mod.main()
