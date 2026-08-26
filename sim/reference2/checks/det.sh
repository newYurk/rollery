#!/bin/zsh
cd /Users/newyurk/Desktop/Home/Projects/rollery/sim/reference2
PY=/Users/newyurk/Desktop/Home/Projects/rollery/sim/.venv/bin/python
for r in a b; do
  TI_CPU_MAX_NUM_THREADS=1 $PY run.py --layout 4 --press 2 --seed 1 --grid 240 --particles 16000 \
    --frames 0 --out checks/out_hand --tag _st20_$r >/dev/null 2>&1
  echo "st20_$r done"
done
