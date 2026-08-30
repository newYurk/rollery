#!/bin/bash
# Синхронизация issues → доска Projects «Ролльня» (user project 2 @newYurk).
#
# ЗАЧЕМ. Штатное автодобавление Projects включается только в веб-интерфейсе и через
# API не управляется (в projectV2.workflows его просто нет — проверено 30.08.2026);
# GitHub Action потребовал бы класть PAT в секреты. Поэтому — идемпотентный скрипт:
# добавляет отставшие issues на доску, новым ставит Вес=Обычная и Status по состоянию.
# Запускать после заведения issues (правило в памяти ассистента) или просто иногда.
set -euo pipefail
OWNER=newYurk; PROJ=2; REPO=newYurk/rollery
FLD_W=PVTSSF_lAHOAIozFM4Bhr_Hzhgm0fc; OPT_USUAL=53610f09          # поле «Вес»
PID=$(gh project view $PROJ --owner $OWNER --format json -q .id)
FLD_S=$(gh project field-list $PROJ --owner $OWNER --format json -q '.fields[] | select(.name=="Status") | .id')
OPT_TODO=$(gh project field-list $PROJ --owner $OWNER --format json -q '.fields[] | select(.name=="Status") | .options[] | select(.name=="Todo") | .id')
OPT_DONE=$(gh project field-list $PROJ --owner $OWNER --format json -q '.fields[] | select(.name=="Status") | .options[] | select(.name=="Done") | .id')

have=$(gh project item-list $PROJ --owner $OWNER --limit 500 --format json -q '[.items[].content.number] | @tsv' | tr '\t' '\n' | sort -n)
added=0
while IFS=$'\t' read -r num state; do
  echo "$have" | grep -qx "$num" && continue
  url="https://github.com/$REPO/issues/$num"
  # id берём из ответа item-add: свежая карточка попадает в item-list с задержкой
  id=$(gh project item-add $PROJ --owner $OWNER --url "$url" --format json -q .id)
  gh project item-edit --id "$id" --project-id "$PID" --field-id "$FLD_W" --single-select-option-id "$OPT_USUAL" >/dev/null
  opt=$([ "$state" = "CLOSED" ] && echo "$OPT_DONE" || echo "$OPT_TODO")
  gh project item-edit --id "$id" --project-id "$PID" --field-id "$FLD_S" --single-select-option-id "$opt" >/dev/null
  echo "#$num → доска (Вес=Обычная, $([ "$state" = "CLOSED" ] && echo Done || echo Todo))"
  added=$((added+1))
done < <(gh issue list -R $REPO --state all --limit 500 --json number,state -q '.[] | [.number, .state] | @tsv')
echo "готово: добавлено $added"
