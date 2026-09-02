#!/bin/sh
# Пересобрать весь атлас: четыре листа → SVG, карта для обсуждения, страница.
#
# Запускать из любого места: скрипт сам переходит в свою папку.
#   ./docs/architecture/build.sh
#
# d2 ставится один раз: brew install d2
set -eu
cd "$(dirname "$0")"

command -v d2 >/dev/null 2>&1 || {
  echo "нет d2. Поставить: brew install d2" >&2
  exit 1
}

mkdir -p svg
for f in 0*.d2; do
  d2 "$f" "svg/${f%.d2}.svg"
done

python3 build-atlas-excalidraw.py
python3 build-atlas-page.py

echo "готово: svg/ · rollery-atlas.excalidraw · ../reports/architecture-atlas.html"
