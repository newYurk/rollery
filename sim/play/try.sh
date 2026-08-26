#!/bin/bash
# Ролльня — песочница симуляции. Запуск:  ./try.sh [аргументы run.py]
# Примеры:
#   ./try.sh                                   — раскладка 1 (пустой лист), быстрый прогон
#   ./try.sh --layout 4                        — четыре начинки у края
#   ./try.sh --layout 2 --press 2 --tag press2 — сильный прижим, результат с меткой
cd "$(dirname "$0")"
source ../.venv/bin/activate
ARGS="$@"
[[ "$ARGS" != *"--layout"* ]] && ARGS="--layout 1 $ARGS"
[[ "$ARGS" != *"--grid"* ]] && ARGS="$ARGS --grid 240"
[[ "$ARGS" != *"--particles"* ]] && ARGS="$ARGS --particles 16000"
[[ "$ARGS" != *"--frames"* ]] && ARGS="$ARGS --frames 10"
[[ "$ARGS" != *"--out"* ]] && ARGS="$ARGS --out out"
mkdir -p out
echo "run.py $ARGS"
python run.py $ARGS 2>&1 | grep -v "^\[GsTaichi\]"
echo
echo "Смотреть: sim/play/out/material_*.png (срез)  ·  final_*.png (ролл целиком)  ·  frames_*/ (как крутилось)"
open out 2>/dev/null || true
