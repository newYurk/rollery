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

# ⚠ СНАЧАЛА СПРОСИТЬ, ЕСТЬ ЛИ ВЕТКА НА ORIGIN, и не глушить ошибку git. Диапазон
# origin/$br..$br на несуществующей ветке даёт пустой вывод, ahead становится нулём —
# и сторож печатает «запушено» ровно в том случае, который обязан ловить. Найдено вечерней сверкой 31.08.
br=$(git branch --show-current)
# В detached HEAD имя пустое, и проверка «есть ли ветка на origin» печатала
# «ветки  нет на origin» — жалобу на ветку, которой нет по определению.
# Отсоединённая голова — законное состояние (сверка на чужом коммите), и это
# не расхождение: сказать и не считать провалом.
if [ -z "$br" ]; then
  say "  ✓ отсоединённая голова на $(git rev-parse --short HEAD) — ветки нет, и не должно быть"
elif ! git rev-parse --verify --quiet "origin/$br" >/dev/null; then
  warn "ветки $br нет на origin — не отправлена ни разу"
else
  ahead=$(git log "origin/$br..$br" --oneline | wc -l | tr -d ' ')
  [ "$ahead" != "0" ] && warn "не запушено коммитов: $ahead (ветка $br)" || say "  ✓ запушено ($br)"
fi

say "── ветки без PR"
# Ветка без PR — не обязательно забытая. Она может быть незаконченной работой, у которой есть
# ЗАВЕДЁННАЯ ЗАДАЧА: тогда о ней помнят, и повторять предупреждение каждый прогон незачем —
# сторож, который каждый раз кричит одно и то же про известное, приучает пролистывать вывод.
# Ищем в открытых issues упоминание имени ветки; нашлось — печатаем спокойно, со ссылкой.
# grep убирает и main, и строку detached HEAD: без неё «(HEAD detached at X)»
# разваливается подстановкой на три слова и сторож ругается на несуществующие ветки.
for b in $(git branch --format='%(refname:short)' | grep -v '^main$' | grep -v '^(' ); do
  pr=$(gh pr list --head "$b" --state open --limit 1 --json number -q '.[0].number' 2>/dev/null)
  if [ -n "$pr" ]; then say "  ✓ $b → PR #$pr"; continue; fi
  # Влитый PR — единственный НАДЁЖНЫЙ ответ на вопрос «влита ли». Ни счётчик коммитов,
  # ни дифф его не заменяют: squash не оставляет коммитов ветки в main, а локальная
  # копия влитой ветки может просто отстать и выглядеть расходящейся.
  prm=$(gh pr list --head "$b" --state merged --limit 1 --json number -q '.[0].number' 2>/dev/null)
  if [ -n "$prm" ]; then warn "ветка $b влита (PR #$prm) и забыта — удалить"; continue; fi
  iss=$(gh issue list --state open --limit 100 --search "$b" --json number -q '.[0].number' 2>/dev/null)
  # «Влита и забыта» и «не влита и забыта» — разные беды, и лечатся по-разному:
  # первую удаляют, вторую доводят или осознанно бросают. Раньше сторож называл
  # влитой любую ветку без PR, и невлитая работа пряталась за успокаивающим словом.
  # PR не нашёлся вовсе — ветка жила только локально. Тогда содержимое: если она
  # ничего не добавляет к main, её можно удалить, каким бы способом это ни вышло.
  ahead=$(git rev-list --count origin/main.."$b" 2>/dev/null || echo 0)
  if git diff --quiet origin/main.."$b" 2>/dev/null; then same=1; else same=0; fi
  if [ -n "$iss" ]; then
    say "  ✓ $b без PR, но описана в #$iss"
  elif [ "$same" = "1" ]; then
    warn "ветка $b влита в main и забыта — удалить"
  else
    warn "ветка $b НЕ влита: $ahead коммит(ов) и своё содержимое мимо main, PR нет, задачи нет — работа потеряется"
  fi
done

say "── доска Projects"
have=$(gh project item-list $PROJ --owner $OWNER --limit 500 --format json -q '[.items[].content.number] | @tsv' 2>/dev/null | tr '\t' '\n' | sort -n)
miss=0
while read -r n; do
  echo "$have" | grep -qx "$n" || { warn "issue #$n не на доске"; miss=$((miss+1)); }
done < <(gh issue list -R $REPO --state all --limit 500 --json number -q '.[].number')
[ "$miss" = "0" ] && say "  ✓ все issues на доске"

say "── milestone у открытых задач"
# ⚠ ИМЯ ПЕРЕМЕННОЙ ЛАТИНИЦЕЙ. Кириллическое bash не принимает: «без=: command not found».
# Наступала на это дважды, поэтому напоминание стоит здесь, а не в памяти.
# ⚠ МЕТКА НЕ ЗАМЕНЯЕТ MILESTONE, и это не очевидно. 01.09 обе новые задачи получили метку
# «фундамент» и остались БЕЗ milestone — то есть не попали ни в один срез доски и не считались
# в прогрессе «Полноты модели». Владелец заметила это раньше сторожа; теперь сторож.
no_ms=$(gh issue list -R $REPO --state open --limit 200 --json number,milestone \
      -q '.[] | select(.milestone == null) | .number' 2>/dev/null)
if [ -n "$no_ms" ]; then
  cnt=$(printf '%s\n' "$no_ms" | grep -c .)
  warn "открытых задач без milestone: $cnt — они не попадают ни в один срез"
  printf '%s\n' "$no_ms" | sed 's/^/      #/'
else
  say "  ✓ у всех открытых задач есть milestone"
fi

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

# И третья: числа, которыми ЧЕРТЕЖИ кормят формулу. Сверялась формула, но не её вход —
# 01.09 нашлось, что TURNS в чертежах 1,29 при модельных 1,15, радиус 3,12 при 2,91,
# фоновый свет 0,34 при 0,62. Проза документа к тому времени уже признавала, что 1,29 старое.
say "── числа чертежей: документ ядра против кода"
python3 tools/guide-numbers-check.py || bad=$((bad+1))

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
