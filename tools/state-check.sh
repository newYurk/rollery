#!/bin/bash
# Сверка «всё ли в порядке»: гит-сущности и документы против фактического состояния.
#
# ЗАЧЕМ. Держать issues, доску и доки в согласии — постоянная обязанность ассистента, но
# обещание не проверяется, а эта команда проверяется. Запускать в конце работы (и владельцу
# в любой момент): она НИЧЕГО НЕ ЧИНИТ, только называет расхождения.
#
#   ./tools/state-check.sh
set -uo pipefail
cd "$(dirname "$0")/.."
OWNER=newYurk; REPO=newYurk/rollery; PROJ=2
bad=0
say() { printf '%s\n' "$*"; }
warn() { bad=$((bad+1)); printf '  ✗ %s\n' "$*"; }

say "── рабочее дерево"
if [ -n "$(git status --porcelain)" ]; then
  warn "есть незакоммиченные изменения:"; git status --porcelain | sed 's/^/      /'
else say "  ✓ чисто"; fi

br=$(git branch --show-current)
ahead=$(git log "origin/$br..$br" --oneline 2>/dev/null | wc -l | tr -d ' ')
[ "$ahead" != "0" ] && warn "не запушено коммитов: $ahead (ветка $br)" || say "  ✓ запушено ($br)"

say "── ветки без PR"
for b in $(git branch --format='%(refname:short)' | grep -v '^main$'); do
  pr=$(gh pr list --head "$b" --json number -q '.[0].number' 2>/dev/null)
  [ -z "$pr" ] && warn "ветка $b без открытого PR — влита и забыта?" || say "  ✓ $b → PR #$pr"
done

say "── доска Projects"
have=$(gh project item-list $PROJ --owner $OWNER --limit 500 --format json -q '[.items[].content.number] | @tsv' 2>/dev/null | tr '\t' '\n' | sort -n)
miss=0
while read -r n; do
  echo "$have" | grep -qx "$n" || { warn "issue #$n не на доске"; miss=$((miss+1)); }
done < <(gh issue list -R $REPO --state all --limit 500 --json number -q '.[].number')
[ "$miss" = "0" ] && say "  ✓ все issues на доске"

say "── статусы карточек против состояния issues"
# ⚠ БЕЗ --limit gh отдаёт 30 штук и молчит об этом. Так я 30.08 сообщила владельцу «30
# открытых, 70 закрытых» вместо настоящих 82 и 18: обрезанный список приняла за полный.
# Здесь везде явный предел, и он же проверяется на упор — если элементов ровно столько,
# сколько запрошено, список мог быть обрезан.
gh project item-list $PROJ --owner $OWNER --limit 500 --format json \
  -q '.items[] | select(.content.number) | "\(.content.number)\t\(.status // "—")"' 2>/dev/null | sort -k1,1 > /tmp/sc-cards.tsv
gh issue list -R $REPO --state all --limit 500 --json number,state \
  -q '.[] | "\(.number)\t\(.state)"' 2>/dev/null | sort -k1,1 > /tmp/sc-issues.tsv
nc=$(wc -l < /tmp/sc-cards.tsv | tr -d ' '); ni=$(wc -l < /tmp/sc-issues.tsv | tr -d ' ')
[ "$nc" -ge 500 ] && warn "список карточек упёрся в предел 500 — поднять лимит"
[ "$ni" -ge 500 ] && warn "список issues упёрся в предел 500 — поднять лимит"
mism=$(join -t$'\t' /tmp/sc-cards.tsv /tmp/sc-issues.tsv | \
  awk -F'\t' '($3=="CLOSED" && $2!="Done") || ($3=="OPEN" && $2=="Done") {print "#"$1" — issue "$3", карточка «"$2"»"}')
if [ -n "$mism" ]; then
  while IFS= read -r line; do warn "$line"; done <<< "$mism"
else
  op=$(awk -F'\t' '$2=="OPEN"' /tmp/sc-issues.tsv | wc -l | tr -d ' ')
  cl=$(awk -F'\t' '$2=="CLOSED"' /tmp/sc-issues.tsv | wc -l | tr -d ' ')
  say "  ✓ статусы сходятся: открытых $op · закрытых $cl · карточек $nc"
fi
rm -f /tmp/sc-cards.tsv /tmp/sc-issues.tsv

say "── документы"
for f in STATE.md docs/journal.md; do
  d=$(git log -1 --format=%cd --date=short -- "$f")
  say "  · $f — последняя правка $d"
done
last_code=$(git log -1 --format=%cd --date=short -- play/ sim/)
last_state=$(git log -1 --format=%cd --date=short -- STATE.md)
[ "$last_code" \> "$last_state" ] && warn "код правился ($last_code) позже STATE.md ($last_state) — точка входа могла отстать"

# ГИД ПО ЯДРУ обязан идти вровень с математикой (issue #106). Он описывает то же самое,
# что считает geometry.js и хранит catalog.js, — и если те ушли вперёд, гид врёт молча,
# а врущая схема хуже отсутствующей: по ней принимают решения.
guide=docs/reports/piece-body.html
last_math=$(git log -1 --format=%cd --date=short -- play/model/geometry.js play/model/catalog.js)
last_guide=$(git log -1 --format=%cd --date=short -- "$guide")
if [ "$last_math" \> "$last_guide" ]; then
  warn "математика правилась ($last_math) позже гида ($last_guide) — $guide отстал от geometry/catalog"
else
  say "  ✓ гид по ядру вровень с математикой ($last_guide)"
fi

say ""
[ "$bad" = "0" ] && say "ВСЁ В СОГЛАСИИ" || say "РАСХОЖДЕНИЙ: $bad — см. ✗ выше"
exit 0
