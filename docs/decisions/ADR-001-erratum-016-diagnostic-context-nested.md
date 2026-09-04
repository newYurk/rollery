# ADR-001 — Erratum 016: `Diagnostic.context` допускает вложенный объект и `null`

- **Дата:** 2026-09-04
- **Статус:** proposed; точечная правка типа `Diagnostic` **не в скоупе PR1** (F04b вне
  первого PR), но тип — часть контракта сейчас.
- **Уточняет (поверх `ADR-001-erratum-012-diagnostic-type.md`):** поле `context` типа
  `Diagnostic` и прозу «значения — числа/строки/массивы».
- **Источник:** независимый ревьюер-человек, issue [#171](https://github.com/newYurk/rollery/issues/171),
  пункт 4 (major). Проверено независимо: `docs/handoff/core-v2-validation-findings.md`,
  Слой 6.
- **Связанные документы:** `ADR-001-erratum-012-diagnostic-type.md`,
  `ADR-001-erratum-004-placement-window.md`, `ADR-001-erratum-008-wind-direction.md`,
  `core-v2-fixtures.md`.

## Проблема

Erratum 012 впервые объявил тип `Diagnostic` и закрытый список `code`. Поле `context`
типизировано так (`ADR-001-erratum-012-diagnostic-type.md:53`):

```ts
context: Record<string, number | string | number[] | string[]>
```

Та же таблица «Обязательный `context` по `code`» требует значений, которые в это объединение
не входят:

- `closure_window` → `placementWindowMm: { nearEdgeMm: number; farEdgeMm: number }`
  (вложенный объект; erratum-004, F04b);
- `recipe_missing_wind_direction` → `observedValue: string | null`
  (`null` не в объединении; erratum-008).

**Минимальный контрпример.** Честный отчёт F04b кладёт в `context.placementWindowMm`
тот же объект, который таблица F04b называет обязательным. Значение не типизируется:
`tsc` на первой сборке `Diagnostic` для F04b красный. Сплющивание в два скаляра
(`placementWindowNearEdgeMm`, `placementWindowFarEdgeMm`) проходит тип и нарушает
таблицу. `null` в `observedValue` — то же самое для кода `recipe_missing_wind_direction`.

Слой 5 закрывал находку «тип не объявлен» и не типизировал TypeScript против собственной
таблицы. Не блокирует F01/F02 (F04b вне скоупа PR1), но разработчик, который заведёт
`Diagnostic` в первом PR «по 012 как написано», получит тип, с которым F04b собрать
нельзя.

## Патч 1 — `ADR-001-erratum-012-diagnostic-type.md`, поле `context`

Было (накопленное состояние — текст Erratum 012 как есть):

```ts
  // Структурированный контекст — какие именно поля здесь обязательны, зависит от code
  // (см. таблицу «Обязательный context по code» ниже). Ключи — camelCase, значения — числа/
  // строки/массивы, без вложенных Diagnostic и без ссылок на объекты RecipeV2/FixtureReport
  // целиком (только конкретные скалярные наблюдаемые значения).
  context: Record<string, number | string | number[] | string[]>
```

Стало:

```ts
  // Структурированный контекст — какие именно поля здесь обязательны, зависит от code
  // (см. таблицу «Обязательный context по code» ниже). Ключи — camelCase.
  // Значения — скаляры (number | string | null), массивы скаляров, либо один уровень
  // вложенного объекта со скалярными полями (нужно для placementWindowMm из erratum-004).
  // По-прежнему без вложенных Diagnostic и без ссылок на RecipeV2/FixtureReport целиком.
  context: Record<
    string,
    number | string | null | number[] | string[] | Record<string, number | string>
  >
```

Таблица «Обязательный `context` по `code`» **не сплющивается**: строка `closure_window`
оставляет `placementWindowMm: { nearEdgeMm: number; farEdgeMm: number }` — это
норматив erratum-004, не иллюстрация. Тип подтягивается под таблицу, не наоборот.

`null` разрешён только как значение ключа `context`, не как сам `context` и не как
замена отсутствующего обязательного ключа: если таблица требует ключ, его нет — это
неполный diagnostic, а не `null`.

## Почему не сплющивать таблицу

Erratum 004 ввёл `placementWindowMm` как именованный объект с двумя полями во «Вход»
и в diagnostic F04b одним идентификатором. Два скаляра в `context` — это уже другой
контракт: разработчик, читающий 004 и 012 вместе, не узнает, какое имя правильное.
Расширение объединения дешевле и не откатывает 004.

## Mutation tests

На уровне `tsc` / формы `Diagnostic` (до появления раннера F04b):

```markdown
| Честный F04b-diagnostic с `context.placementWindowMm = { nearEdgeMm, farEdgeMm }` (объект, как в таблице erratum-012 / erratum-004) | Тип `Diagnostic.context` обязан это принимать. Реализация, чей тип отвергает вложенный объект, не собирает F04b |
| Diagnostic `recipe_missing_wind_direction` с `context.observedValue = null` (поле отсутствует во входе) | Тип обязан принимать `null`. Реализация, чей union не содержит `null`, не выражает собственную таблицу |
```
