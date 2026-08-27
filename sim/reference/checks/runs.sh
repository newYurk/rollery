#!/bin/bash
# Adversarial check: determinism + hand inputs on layout 4.
# Usage: bash runs.sh "tag:args" "tag:args" ...   (runs all in parallel, waits)
source /Users/newyurk/Desktop/Home/Projects/rollery/sim/.venv/bin/activate
REF=/Users/newyurk/Desktop/Home/Projects/rollery/sim/reference
OUT=$REF/checks/out
mkdir -p "$OUT"
for spec in "$@"; do
  tag="${spec%%:*}"; rest="${spec#*:}"
  ( cd "$REF" && /usr/bin/time -p python run.py --layout 4 --grid 240 --particles 16000 \
      --frames 0 --out "$OUT" --tag "_$tag" $rest > "$OUT/log_$tag.txt" 2>&1 ) &
done
wait
echo "done: $@"
