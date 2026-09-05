#!/usr/bin/env bash
# Мутационный стенд для шлюза Core V2 (ревью PR core-v2/f01-f02).
#
# Мутирует ОДНУ строку ядра (не отчёта!) и смотрит, краснеет ли шлюз.
# Тесты вида `mutation:` в core-v2.test.mjs портят отчёт ПОСЛЕ того, как ядро
# его вернуло, — это проверка функции приёмки, а не ядра. Здесь наоборот:
# мутируем производителя, проверяем потребителем.
#
#   bash tools/core-v2-mutation-gate.sh
#
# Выжившая мутация = дыра: ядро считает неверно, а CI зелёный.
# Столбец «кто поймал» различает приёмку (run-fixtures) и рукописные тесты:
# они ловят разное, и знать где именно живёт защита — полезнее, чем да/нет.
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
# Копируем ВЕСЬ play/, а не одно ядро: core-v2.test.mjs читает живой каталог через
# load-catalog.cjs → ../../model/catalog.js. При копии одной папки тесты не грузились
# вовсе, и колонка pass/fail молча показывала 0/1 на каждой строке.
mkdir -p "$WORK/base"
cp -R "$ROOT/play" "$WORK/base/play"

# Колонки: всё до свободного текста — ASCII фиксированной ширины, поэтому
# выравнивание не зависит от локали (printf и ${#} тут считают байты, а не символы).
# Паттерны привязаны к точным строкам ядра. Если ядро переписали и sed не
# применился, мутация «выживет» фиктивно — поэтому проверяем, что файл изменился.
APPLIED=1
s() {
  local before after
  before=$(cat "$WORK/try/play/core-v2/$2")
  sed -i '' "$1" "$WORK/try/play/core-v2/$2" 2>/dev/null || sed -i "$1" "$WORK/try/play/core-v2/$2"
  after=$(cat "$WORK/try/play/core-v2/$2")
  [ "$before" = "$after" ] && APPLIED=0
}

run_mut() {
  local name="$1"; shift
  rm -rf "$WORK/try" && cp -R "$WORK/base" "$WORK/try"
  K="$WORK/try/play/core-v2"
  APPLIED=1
  "$@"
  if [ "$APPLIED" -eq 0 ]; then
    printf '%s  %5s/%-5s  %s\n' 'н/п — паттерн   ' '-' '-' "$name"
    return
  fi
  local out pass fail fixtures
  out=$(cd "$WORK/try/play/core-v2" && node --test core-v2.test.mjs 2>&1)
  pass=$(printf '%s\n' "$out" | sed -n 's/^# pass \([0-9]*\)$/\1/p')
  fail=$(printf '%s\n' "$out" | sed -n 's/^# fail \([0-9]*\)$/\1/p')
  if (cd "$WORK/try/play/core-v2" && node run-fixtures.mjs >/dev/null 2>&1); then fx=0; else fx=1; fi
  # ⚠ CI требует ОБА шага — fixtures и unit. Значит и «выжила» считается по обоим:
  # verdict по одному шлюзу врал бы ровно так же, как всё, что этот стенд ищет.
  # Заодно видно, ГДЕ живёт защита: приёмка и рукописные тесты ловят разное.
  # printf '%-Ns' считает БАЙТЫ, а кириллица в UTF-8 занимает два — колонка
  # разъезжается. Набор вердиктов конечный, поэтому дополняем строки вручную.
  if [ "$fx" = "1" ] && [ "${fail:-0}" != "0" ]; then verdict='умерла: обе     '
  elif [ "$fx" = "1" ];                            then verdict='умерла: fixtures'
  elif [ "${fail:-0}" != "0" ];                    then verdict='умерла: unit    '
  else                                                  verdict='◆ ВЫЖИЛА — ДЫРА '
  fi
  printf '%s  %5s/%-5s  %s\n' "$verdict" "$pass" "$fail" "$name"
}

m_arc()     { s 's|    pathMm += mid \* dtheta;|    pathMm += mid * dtheta * 1.5;|' winding.js; }
m_nori()    { s 's|    acc += Math.sqrt(r \* r + dr \* dr) \* DPHI;|    acc += Math.sqrt(r * r + dr * dr) * DPHI * 1.5;|' winding.js; }
m_rp()      { s 's|  return Math.sqrt((Math.max(0, coreAreaMm2) + T \* Lrice) / Math.PI);|  return Math.sqrt((T * Lrice) / Math.PI);|' winding.js; }
m_corebox() { s 's|hw: p.widthMm / 2, hh:|hw: p.widthMm / 4, hh:|' winding.js; }
m_meanr()   { s 's|  const meanR = Math.max(1e-6, (r0m + rpCircle) / 2);|  const meanR = Math.max(1e-6, (r0m + rpCircle) / 2) * 1.3;|' winding.js; }
m_umm()     { s 's|export const U_MM = 5;|export const U_MM = 1;|' units.js; }
m_rowh()    { s 's|    const rowH = Math.max(...items.map((p) => p.heightMm));|    const rowH = Math.max(...items.map((p) => p.heightMm)) * 1.4;|' units.js; }
m_gap()     { s 's|export const CORE_PACK_GAP_MM = 1;|export const CORE_PACK_GAP_MM = 6;|' units.js; }
m_thick()   { s 's|  riceThicknessMm: 7,|  riceThicknessMm: 9,|' units.js; }
m_turns()   { s 's|  const turns = Lrice / (TAU \* meanR);|  const turns = Lrice / (TAU * meanR) * 2;|' winding.js; }
# ── входные константы: снимок каталога (#174). Раньше все шесть проходили насквозь.
m_spread_e(){ s 's|  spreadEnd: 0.88,|  spreadEnd: 0.85,|' units.js; }
m_spread_s(){ s 's|export const SPREAD_START = 0.048;|export const SPREAD_START = 0.02;|' units.js; }
m_emptyh()  { s 's|  emptyCoreHeightMm: 7.2,|  emptyCoreHeightMm: 5,|' units.js; }
m_rowmm()   { s 's|export const CORE_PACK_ROW_MM = 24;|export const CORE_PACK_ROW_MM = 60;|' units.js; }
# ← регрессия #165: нахлёст от голых полей вместо остатка листа
m_bare()    { s 's|  const overlapMm = L - noriPerimeter;|  const overlapMm = Lbare;|' winding.js; }
m_norih()   { s 's|hh: p.heightMm / 2 + base.noriThicknessMm|hh: p.heightMm / 2|' winding.js; }
m_pieces()  { s 's|  pieces: 6,|  pieces: 7,|' units.js; }
m_uramp()   { s 's|    const s = sRice0 + Lrice \* (b / NB);|    const s = sRice0 + Lrice * (b / NB) * 0.5;|' winding.js; }
m_overlap() { s 's|  const phiOverlap = enough \&\& Ravg > 1e-9 ? Math.min(TAU, overlapMm / Ravg) : 0;|  const phiOverlap = enough \&\& Ravg > 1e-9 ? Math.min(TAU, overlapMm / Ravg) * 0.7 : 0;|' winding.js; }

printf '%s  %5s/%-5s  %s\n' 'кто поймал      ' 'pass' 'fail' 'мутация ядра'
printf '%s\n' '----------------  -----------  -----------------------------------------'

run_mut 'winding.js  дуга риса pathMm x1,5'   m_arc
run_mut 'winding.js  midArc (нори) x1,5'      m_nori
run_mut 'winding.js  riceOuterMm без Wc·Hc'   m_rp
run_mut 'winding.js  полуширина патча /2'     m_corebox
run_mut 'winding.js  meanR x1,3'              m_meanr
run_mut 'winding.js  число витков x2'         m_turns
run_mut 'winding.js  phiOverlap x0,7'         m_overlap
run_mut 'winding.js  линейка uInnerMm вдвое'  m_uramp
run_mut 'units.js    U_MM 5 -> 1'             m_umm
run_mut 'units.js    высота ряда x1,4'        m_rowh
run_mut 'units.js    CORE_PACK_GAP_MM 1 -> 6' m_gap
run_mut 'units.js    riceThicknessMm 7 -> 9'  m_thick
run_mut 'units.js    spreadEnd 0,88 -> 0,85'     m_spread_e
run_mut 'units.js    SPREAD_START 0,048 -> 0,02' m_spread_s
run_mut 'units.js    emptyCoreHeightMm 7,2 -> 5' m_emptyh
run_mut 'units.js    CORE_PACK_ROW_MM 24 -> 60'  m_rowmm
run_mut 'units.js    pieces 6 -> 7'              m_pieces
run_mut 'winding.js  halfH без noriThickness'    m_norih
run_mut 'winding.js  нахлёст от голых полей'     m_bare
