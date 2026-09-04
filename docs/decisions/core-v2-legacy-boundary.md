# Core V2 — граница с legacy и план безопасной миграции

- **Статус:** proposed
- **Связанные документы:** `ADR-001-core-v2-scope.md`, `ADR-001-erratum-001-neutral-hand-only.md`, `ADR-001-erratum-002-no-diagonal-placement.md`, `ADR-001-erratum-003-rice-color-field.md`, `ADR-001-erratum-004-placement-window.md`, `ADR-001-erratum-005-seam-overlap.md`, `ADR-001-erratum-006-area-anchor.md`, `ADR-001-erratum-007-ordinal-vs-coordinate.md`, `ADR-001-erratum-008-wind-direction.md`, `ADR-001-erratum-009-acceptance-gate.md`, `ADR-001-erratum-010-report-completeness.md`, `ADR-001-erratum-011-hash-domain.md`, `ADR-001-erratum-012-diagnostic-type.md`, `ADR-001-erratum-013-sheet-parameter-vs-layer-arc.md`, `ADR-001-erratum-014-core-box-units.md`, `ADR-001-erratum-015-f02-catalog-area-formula.md`, `ADR-001-erratum-016-diagnostic-context-nested.md`, `ADR-001-erratum-017-f07-wind-direction.md`, `ADR-001-erratum-018-neutral-hand-everywhere.md`, `ADR-001-erratum-019-invertibility-seam-cut.md`, `ADR-001-erratum-020-cross-erratum-seams.md`, `ADR-001-erratum-021-layer-arc-units.md`, `core-v2-fixtures.md`
- **Цель:** дать разработчику чёткую границу. Новый kernel не должен импортировать поведение legacy случайно.

## Решение о границе

`play/core-v2/` строится как независимый чистый слой. До прохождения F01–F08 (порог обновлён
`ADR-001-erratum-008-wind-direction.md`; исходно F01–F06) он не имеет production-потребителей
и не заменяет `play/model/geometry.js`.

```text
UI / URL / global S / modes
        ↓ adapter only
RecipeV2 (mm, immutable)
        ↓
play/core-v2/validate.js
        ↓
play/core-v2/winding.js
        ↓
play/core-v2/section.js
        ↓
FixtureReport / RenderSnapshot
        ↓ adapter only
renderer
```

## Область применимости legacy

На неё ссылается шаг 5 плана миграции — `ADR-001-core-v2-scope.md`, раздел «План миграции»
(план живёт там, не в этом файле). Legacy — валидный oracle для сравнения
только там, где известные дефекты сохранения материала не проявляются:

- **≤ 1 витка рисовой постели.** Кольцо кладёт ровно один виток независимо от того,
  сколько нужно рису (#165). При потребности в 1,3–1,6 витка (STATE.md) legacy
  не сохраняет длину листа по построению — сравнение бессмысленно.
- **≤ 1 патч начинки в рецепте.** #134 действует по порядковому номеру укладки
  патча, а не по координате `uMm` (измерено 03.09,
  `docs/handoff/core-v2-validation-findings.md`): кусок «едет» без отклика на срезе,
  затем прыгает при смене соседа по порядку. При единственном патче порядка
  соседей нет — дефект не может проявиться.

Вне этих условий (футомаки, любой рецепт с 2+ патчами) расхождение V2 и legacy
ожидаемо и не является поводом чинить V2 «под legacy» — legacy сам неверен там.

## Карта компонентов

| Legacy-зона | Статус для V2 | Правило |
|---|---|---|
| `play/model/geometry.js` | Reference only | Не импортировать. Использовать только для чтения старых форматов и визуального сравнения в документированной области legacy |
| `play/model/catalog.js` | Adapt | Допустим только data-adapter: V2 получает нормализованные мм, не читает каталог напрямую |
| `play/model/canon.js` | Reference only | Канонические рецепты можно перенести вручную в V2 fixtures после проверки чисел; правила канона не импортировать |
| `play/model/util.js` | Copy selectively | Только маленькие чистые утилиты после локального копирования, теста и указания источника; никаких импортов legacy util по умолчанию |
| `play/domain/roll.js` | Adapt later | Может стать границей session/app, но не является входом kernel до определения адаптера RecipeV1 → RecipeV2 |
| `play/state.js` | Do not port | Глобальное состояние UI не может быть источником доменной геометрии |
| `play/index.html` | Do not port | DOM, URL, жесты и рендерные параметры запрещены в Core V2 |
| `play/modes/` | Do not port | Puzzle и другие режимы вызывают V2 только через adapter после V2 alpha |
| `play/render/` | Keep behind adapter | Рендер получает `RenderSnapshot`; он не вызывает `buildWinding` и не читает RecipeV2 напрямую |
| `play/checks.js` | Reference then replace | Старые проверки не являются oracle. Из него можно перенести только измерения, которые имеют ясный физический смысл и mutation test |
| `sim/` | Separate reference | Не импортировать и не переписывать. Общими могут быть только fixture-данные и будущие сравнимые измерения |
| `docs/` и GitHub issues | Evidence only | Документы и issue — доказательства, но не исполняемый контракт. При конфликте приоритет: erratum → ADR → fixtures → developer brief → код `play/core-v2/**` → архив (единая формулировка, см. `core-v2-developer-brief.md`) |

## Запрещённые зависимости

В файлах `play/core-v2/**` запрещены:

- доступ к `window`, `document`, canvas, URL и localStorage;
- импорт `play/state.js`, `play/index.html`, `play/modes/**`, `play/render/**`;
- чтение или изменение глобального `S`;
- `Date.now`, `performance.now`, `Math.random`, FPS и кадрозависимое состояние;
- импорт `play/model/geometry.js`;
- неявные единицы вида `* 5`, `÷ 5` или unitless координаты;
- silent fallback: исправление, обрезание, центрирование или замена невалидного рецепта.

## Разрешённые направления зависимости

```text
Legacy/UI adapter → Core V2
Fixture runner → Core V2
Core V2 → plain immutable data
Renderer adapter → Core V2 RenderSnapshot
```

Обратные направления запрещены. Core V2 не знает, вызвал его пазл, ручной режим или тест.

## Минимальный API V2

```ts
validateRecipe(recipe: RecipeV2): ValidationResult

buildWinding(recipe: RecipeV2): WindingResult
// WindingResult = valid winding | invalid/outsideModelScope diagnostic

sampleSection(winding: ValidWinding, options: SectionOptions): SectionResult

measure(winding: ValidWinding, section: SectionResult): Measurements

runFixture(fixture: Fixture): FixtureReport
```

`sampleSection` не строит намотку сам, не меняет рецепт и не делает fallback для invalid result.

## Нормализация данных

До входа в V2 существует единственный adapter `recipe-v1-adapter.js` в слое приложения. Его задача ограничена:

1. Прочитать legacy recipe/state.
2. Явно преобразовать единицы в мм.
3. Явно назначить `baseId`, профиль риса и `neutralHand`.
4. Выдать `RecipeV2` или список диагностик преобразования.
5. Отклонить или обнулить `rotationDeg` из legacy: в V2 поворота нет (`invalid: patch_rotated`).

Adapter не должен исправлять геометрию, угадывать пропущенные значения или интерпретировать puzzle `turns` как длину листа.

## Первый вертикальный срез

До UI делается только следующая цепочка:

```text
F01 RecipeV2
  → validateRecipe
  → buildWinding
  → sampleSection at central vSlice
  → FixtureReport
```

Это пустой хосомаки: лист 105 мм, одна нори, стандартная рисовая постель, нет ингредиентов, `neutralHand`. В нём должны появиться не пиксели, а отчёт о покрытии листа, шве, диапазоне координат и пересечениях обёртки.

## Критерий готовности границы

Разработчик может начать Core V2 только когда выполняет все условия:

- не импортирует legacy geometry;
- знает, какой exact input использует F01;
- может вернуть typed diagnostic вместо fallback;
- понимает, что legacy числа не задают expected output V2;
- готов начать с Node-compatible runner, а не с browser UI;
- не вводит поворот патча в плоскости листа.
