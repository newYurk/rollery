# ADR-001 — Erratum 018: в `RecipeV2` только `NeutralHand`, код отказа общий

- **Дата:** 2026-09-04
- **Статус:** proposed; правка снимка `RecipeV2` и закрытого списка diagnostic-кодов.
  Не блокирует сборку F01/F02 с `NeutralHand`; блокирует честный отказ на другом входе.
- **Заменяет (поверх `ADR-001-erratum-008-wind-direction.md`, правка `RecipeV2`):** поле
  `hand` в накопленном снимке типа.
- **Заменяет (поверх `ADR-001-erratum-001-neutral-hand-only.md`):** формулировку отказа —
  не «поле не входит в тип и как-нибудь отклоняется», а один код на любой не-neutral.
- **Заменяет (поверх `ADR-001-erratum-012-diagnostic-type.md`):** код
  `non_neutral_hand_in_puzzle` в объединении `code` и в таблице обязательного `context`.
- **Заменяет в `ADR-001-core-v2-scope.md`:** строку «Нефиксированный hand в puzzle» таблицы
  «Поведение вне модели».
- **Источник:** независимый ревьюер-человек, issue [#171](https://github.com/newYurk/rollery/issues/171),
  пункт 6 (major). Проверено независимо: `docs/handoff/core-v2-validation-findings.md`,
  Слой 6.
- **Связанные документы:** `ADR-001-erratum-001-neutral-hand-only.md`,
  `ADR-001-erratum-008-wind-direction.md`, `ADR-001-erratum-012-diagnostic-type.md`,
  `ADR-001-core-v2-scope.md`, `core-v2-fixtures.md`.

## Проблема

Erratum 001 убрал `RecordedHand` из `RecipeV2`: поле не входит в тип, не передаётся в
kernel, V2 alpha принимает только `NeutralHand = { mode: 'neutral'; seed: 0 }`.

Erratum 008, пересказывая тип ради добавления `windDirection`, взял за базу «состояние
после Erratum 002» и в обоих блоках — «Было» и «Стало» — снова написал
`hand: NeutralHand | RecordedHand` (`ADR-001-erratum-008-wind-direction.md:51,66`).
001 к этому моменту уже должен быть применён. `core-v2-developer-brief.md` (правило
конфликта двух erratum): более поздний номер побеждает на том же поле. Поздний снимок
008 легализует `RecordedHand` обратно.

Закрытый список кодов (`ADR-001-erratum-012-diagnostic-type.md:37-46`) знает один код
руки — `non_neutral_hand_in_puzzle`. F01 не пазл. Таблица «Поведение вне модели»
ADR-001 (`:96`) формулирует отказ только для puzzle.

**Минимальный контрпример.** `RecipeV2` с
`hand: { mode: 'recorded', seed: 1, press: 1, speed: 1, wobble: 0 }` на входе F01.
По 001 — отказ. По 008 — поле легально. По 012 — кода нет. Разработчик либо принимает
руку на пустом хосомаки, либо ставит puzzle-код на не-пазл, либо изобретает код, чего
закрытый список прямо запрещает.

Слой 5 ловил коллизию номеров инвариантов, не grep поля `hand` в пересказанных типах.

## Патч 1 — накопленный снимок `RecipeV2` (поверх «Стало» Erratum 008)

Было (накопленное состояние после Erratum 008; `windDirection` уже обязателен):

```ts
type RecipeV2 = {
  version: 2
  baseId: string
  sheet: { lengthMm: number; widthMm: number }
  wrap: { materialId: string }
  rice: { profileId: string }
  windDirection: WindDirection
  patches: Patch[]
  hand: NeutralHand | RecordedHand
}
```

Стало:

```ts
type RecipeV2 = {
  version: 2
  baseId: string
  sheet: { lengthMm: number; widthMm: number }
  wrap: { materialId: string }
  rice: { profileId: string }
  windDirection: WindDirection
  patches: Patch[]
  hand: NeutralHand
}
```

`RecordedHand` не входит в `RecipeV2` (возвращает норму Erratum 001). Тип
`RecordedHand` может оставаться объявленным в ADR-001 как задел будущего ADR про руку —
но не как член объединения в `RecipeV2`. Пока этого ADR нет, любое значение `hand`,
которое не есть `{ mode: 'neutral'; seed: 0 }` (включая отсутствие поля, `mode: 'recorded'`
и `NeutralHand` с `seed ≠ 0`), — отказ ниже.

## Патч 2 — `ADR-001-core-v2-scope.md`, таблица «Поведение вне модели»

Было (строка, которую Erratum 007 не трогал):

```markdown
| Нефиксированный hand в puzzle | `invalid: non_neutral_hand_in_puzzle` |
```

Стало:

```markdown
| Любой `hand` кроме `NeutralHand` (`mode: 'neutral', seed: 0`) — в том числе на не-пазловом входе и на F01 | `invalid: non_neutral_hand` |
```

Код `non_neutral_hand_in_puzzle` больше не является допустимым diagnostic-кодом V2 alpha.
Реализация, которая эмитит старое имя, нарушает закрытый список Erratum 012 (в редакции
этого erratum). Отдельного puzzle-кода нет, потому что V2 alpha не принимает recorded
hand ни в каком режиме; будущий ADR про руку введёт свои коды сам.

Имя `non_neutral_hand_in_puzzle` остаётся в историческом diff Erratum 007
(`ADR-001-erratum-007-ordinal-vs-coordinate.md:31`) — это снимок строки ADR-001 на момент
007, не живой код. Живой код после этого erratum — `non_neutral_hand`. Grep по 007 без
чтения 018 поймает мёртвый токен; mutation test ниже это ловит.

## Патч 3 — `ADR-001-erratum-012-diagnostic-type.md`, объединение `code` и таблица `context`

В объединении `code` **Было:**

```ts
    | 'non_neutral_hand_in_puzzle'    // ADR-001, «Поведение вне модели» (invalid)
```

**Стало:**

```ts
    | 'non_neutral_hand'              // Erratum 018 (заменяет non_neutral_hand_in_puzzle); любой не-NeutralHand
```

В таблице «Обязательный `context` по `code`» **Было:**

```markdown
| `non_neutral_hand_in_puzzle` | `observedHandMode: string` | ADR-001, «Поведение вне модели» |
```

**Стало:**

```markdown
| `non_neutral_hand` | `observedHandMode: string` | Erratum 018 / ADR-001, «Поведение вне модели» |
```

`observedHandMode` — фактический `hand.mode`, если поле было объектом с `mode`, или
строка `"missing"`, если поля не было. Не `null`: для отсутствующего значения руки
достаточно этой строки; `null` в `context` нужен erratum-016 для другого кода
(`recipe_missing_wind_direction`), не для этого.

## Почему не расширять семантику старого кода

Имя `_in_puzzle` в коде, который обязан срабатывать на F01, — ловушка чтения. Закрытый
список как раз для того, чтобы коды были однозначны. Замена одним erratum дешевле, чем
«этот код значит не то, что написано». Реализации Core V2 ещё нет — миграции эмиттеров
не существует.

## Mutation tests

```markdown
| Подать на F01 `hand: { mode: 'recorded', seed: 1, press: 1, speed: 1, wobble: 0 }` | F01: `invalid: non_neutral_hand` (не `valid`, не `non_neutral_hand_in_puzzle`, не молчаливый fallback к `NeutralHand`) |
| Подать на F01 рецепт без поля `hand` | F01: `invalid: non_neutral_hand`, `context.observedHandMode = "missing"` |
```
