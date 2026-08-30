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
gh project item-list $PROJ --owner $OWNER --limit 500 --format json \
  -q '.items[] | select(.content.number) | "\(.content.number)\t\(.status // "—")"' 2>/dev/null | \
while IFS=$'\t' read -r n st; do
  state=$(gh issue view "$n" -R $REPO --json state -q .state 2>/dev/null)
  if [ "$state" = "CLOSED" ] && [ "$st" != "Done" ]; then warn "#$n закрыт, а на доске «$st»"; fi
  if [ "$state" = "OPEN" ] && [ "$st" = "Done" ]; then warn "#$n открыт, а на доске «Done»"; fi
done

say "── документы"
for f in STATE.md docs/journal.md; do
  d=$(git log -1 --format=%cd --date=short -- "$f")
  say "  · $f — последняя правка $d"
done
last_code=$(git log -1 --format=%cd --date=short -- play/ sim/)
last_state=$(git log -1 --format=%cd --date=short -- STATE.md)
[ "$last_code" \> "$last_state" ] && warn "код правился ($last_code) позже STATE.md ($last_state) — точка входа могла отстать"

say ""
[ "$bad" = "0" ] && say "ВСЁ В СОГЛАСИИ" || say "РАСХОЖДЕНИЙ: $bad — см. ✗ выше"
exit 0
