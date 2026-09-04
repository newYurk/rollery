# ADR-001, Erratum 012 — тип `Diagnostic` определён, а не только используется

- **Статус:** proposed; обязательное уточнение `core-v2-fixtures.md`.
- **Дата:** 2026-09-04.
- **Заменяет в контракте:** `core-v2-fixtures.md` — тип `FixtureReport`, поле `diagnostics: Diagnostic[]`.
- **Отвечает на находку третьего сводного ревью:** `diagnostic-type-never-declared` (major) —
  `Diagnostic` используется во всех документах контракта (базовый `core-v2-fixtures.md:26` и
  каждый erratum, добавляющий свой diagnostic code), но нигде не определён как тип.
- **Кому:** ревьюеру / разработчику Core V2.

## Проблема

`core-v2-fixtures.md:26` объявляет `diagnostics: Diagnostic[]` в типе `FixtureReport`. Ни один
из двенадцати документов контракта не содержит `type Diagnostic = {...}`. Разные fixture
описывают требуемое содержимое diagnostics прозой по-разному и не согласованно:

- F04a: «id патча, нарушенную границу (`sheet.lengthMm`), наблюдаемое значение следа»
  (`ADR-001-erratum-004-placement-window.md:262`)
- F04b: «id патча, `placementWindowMm`, наблюдаемый след патча»
  (`ADR-001-erratum-004-placement-window.md:277`)
- Прочие diagnostic code (`patch_rotated`, `recipe_missing_wind_direction`,
  `patch_material_overlap`, `closure_window`, `conical_roll`, `inside_wrap_topology`,
  `section_shape`, `non_neutral_hand_in_puzzle`) вообще не говорят, какой контекст несёт
  соответствующий объект `diagnostics[]`.

Без типа разработчик может честно выполнить каждую прозаическую строку по отдельности и всё
равно получить девять несовместимых форм одного и того же поля — а тест на «diagnostics
содержит id патча и наблюдаемое значение» невозможно написать программно без структуры.

## Решение

```ts
type Diagnostic = {
  // Один из кодов, встречающихся в контракте — см. полный список ниже. Разработчик не
  // изобретает новые коды без явного erratum: код — часть публичного интерфейса kernel,
  // на него ссылаются fixtures и, потенциально, UI-адаптер.
  code:
    | 'patch_out_of_sheet'            // ADR-001, инвариант 5 / erratum-004, F04a
    | 'closure_window'                // ADR-001, инвариант 5 / erratum-004, F04b (status: outsideModelScope)
    | 'patch_rotated'                 // erratum-002
    | 'patch_material_overlap'        // erratum-007, F07
    | 'recipe_missing_wind_direction' // erratum-008
    | 'conical_roll'                  // ADR-001, «Поведение вне модели» (unsupported)
    | 'inside_wrap_topology'          // ADR-001, «Поведение вне модели» (unsupported)
    | 'section_shape'                 // ADR-001, «Поведение вне модели» (unsupported)
    | 'non_neutral_hand_in_puzzle'    // ADR-001, «Поведение вне модели» (invalid)
  // Свободный текст для человека — не заменяет code, только поясняет контекст читающему отчёт.
  message: string
  // Структурированный контекст — какие именно поля здесь обязательны, зависит от code
  // (см. таблицу «Обязательный context по code» ниже). Ключи — camelCase, значения — числа/
  // строки/массивы, без вложенных Diagnostic и без ссылок на объекты RecipeV2/FixtureReport
  // целиком (только конкретные скалярные наблюдаемые значения).
  context: Record<string, number | string | number[] | string[]>
}
```

### Обязательный `context` по `code`

| `code` | Обязательные ключи `context` | Источник требования |
|---|---|---|
| `patch_out_of_sheet` | `patchId: string`, `sheetLengthMm: number`, `observedFootprintMm: [number, number]` | erratum-004, F04a |
| `closure_window` | `patchId: string`, `placementWindowMm: { nearEdgeMm: number; farEdgeMm: number }`, `observedFootprintMm: [number, number]` | erratum-004, F04b |
| `patch_rotated` | `patchId: string`, `observedRotationDeg: number` | erratum-002 |
| `patch_material_overlap` | `patchIds: [string, string]`, `materialId: string` | erratum-007, F07 |
| `recipe_missing_wind_direction` | `observedValue: string \| null` | erratum-008 |
| `conical_roll`, `inside_wrap_topology`, `section_shape` | `requestedFeature: string` (например `baseId` или `shape`, в зависимости от того, что именно запросил рецепт) | ADR-001, «Поведение вне модели» |
| `non_neutral_hand_in_puzzle` | `observedHandMode: string` | ADR-001, «Поведение вне модели» |

Список кодов и их `context` закрыт на дату этого erratum. Новый diagnostic code, введённый
будущим erratum, обязан добавить свою строку в эту таблицу тем же способом — правкой этого
файла или отдельным erratum, ссылающимся на него, а не молчаливым использованием кода,
которого здесь нет.

## Причина

`diagnostics: Diagnostic[]` — единственное поле `FixtureReport`, через которое kernel обязан
объяснять КАЖДЫЙ невалидный или неподдерживаемый результат (ADR-001: «Никакой из этих случаев
не должен silently fallback»). Без типа это требование непроверяемо: fixture может убедиться,
что `diagnostics` не пуст, но не может проверить, что он несёт нужный код и нужный контекст —
то есть «честный отказ» как принцип контракта не имеет машинно проверяемой формы.
