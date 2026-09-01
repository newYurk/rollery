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

# ⚠ СНАЧАЛА СПРОСИТЬ, ЕСТЬ ЛИ ВЕТКА НА ORIGIN. Прежняя редакция считала коммиты в диапазоне
# origin/$br..$br и глушила ошибку через 2>/dev/null: если ветки на origin НЕТ ВОВСЕ (новая,
# ни разу не отправленная), git падал, вывод пустел, ahead становился нулём — и сторож печатал
# «✓ запушено» ровно в том случае, который обязан ловить. Тот же класс, что мерка spreadEnd
# вместо кромки нори: величина взята не та, что названа. Найдено вечерней сверкой 31.08.
br=$(git branch --show-current)
if ! git rev-parse --verify --quiet "origin/$br" >/dev/null; then
  warn "ветки $br нет на origin — не отправлена ни разу"
else
  ahead=$(git log "origin/$br..$br" --oneline | wc -l | tr -d ' ')
  [ "$ahead" != "0" ] && warn "не запушено коммитов: $ahead (ветка $br)" || say "  ✓ запушено ($br)"
fi

say "── ветки без PR"
for b in $(git branch --format='%(refname:short)' | grep -v '^main$'); do
  pr=$(gh pr list --head "$b" --limit 1 --json number -q '.[0].number' 2>/dev/null)
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

# ДОКУМЕНТ ЯДРА ПО ЯДРУ обязан идти вровень с математикой (issue #106). Он описывает то же самое,
# что считает geometry.js и хранит catalog.js, — и если те ушли вперёд, документ ядра врёт молча,
# а врущая схема хуже отсутствующей: по ней принимают решения.
#
# ⚠ СВЕРЯЕМ СОДЕРЖИМОЕ, А НЕ ДАТЫ. Прежняя версия сравнивала даты последних коммитов
# geometry.js и документа ядра. Оба правились 31.08 — сторож печатал «вровень», а в документе ядра лежала
# формула ДВУХ ПОКОЛЕНИЙ НАЗАД: флаги round/lens вместо таблицы профилей, ни сектора,
# ни полукруга, креветка кружком 10×8 против полукруга 10×5 в игре. Все чертежи документа
# рисовались по снятой формуле, а подпись обещала «по формуле кода». Зелёный сторож на
# врущем документе хуже отсутствующего: по нему принимают решения.
guide=docs/reports/piece-body.html
блок() {   # вырезать помеченный блок и сжать пробелы: сравниваем смысл, а не отступы
  awk '/⟦ФОРМА · ЕДИНОЕ ОПРЕДЕЛЕНИЕ⟧/{f=1} f{print} /⟦\/ФОРМА · ЕДИНОЕ ОПРЕДЕЛЕНИЕ⟧/{f=0}' "$1" \
    | tr -s ' \t' ' ' | sed 's/^ //; s/ $//'
}
# Вторая половина той же обязанности: у документа ядра есть СВОЯ таблица размеров начинок, вне блока.
say "── размеры начинок: документ ядра против каталога"
python3 tools/guide-ingredients-check.py "$guide" play/model/catalog.js || bad=$((bad+1))

math_block=$(блок play/model/geometry.js)
guide_block=$(блок "$guide")
if [ -z "$math_block" ] || [ -z "$guide_block" ]; then
  warn "блок ⟦ФОРМА · ЕДИНОЕ ОПРЕДЕЛЕНИЕ⟧ не найден в geometry.js или в $guide — сверять нечего"
elif [ "$math_block" != "$guide_block" ]; then
  warn "документ ядра разошёлся с geometry.js по форме сечения: $(diff <(echo "$math_block") <(echo "$guide_block") | grep -c '^[<>]') строк — $guide"
else
  say "  ✓ документ ядра считает форму той же формулой, что игра ($(echo "$math_block" | wc -l | tr -d ' ') строк сверено)"
fi

say ""
[ "$bad" = "0" ] && say "ВСЁ В СОГЛАСИИ" || say "РАСХОЖДЕНИЙ: $bad — см. ✗ выше"
exit 0
