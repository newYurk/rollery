# Core V2 — техническое задание агенту-разработчику

## Цель

Реализовать минимальный, чистый, детерминированный forward-kernel для F01 и F02. Цель первого PR — не показать красивый ролл, а доказать корректную карту одного физического листа в цилиндрическом маки.

## Обязательное чтение

1. `docs/decisions/ADR-001-core-v2-scope.md`
2. `docs/decisions/ADR-001-erratum-001-neutral-hand-only.md`
3. `docs/decisions/ADR-001-erratum-002-no-diagonal-placement.md`
4. `docs/decisions/ADR-001-erratum-003-rice-color-field.md`
5. `docs/decisions/ADR-001-erratum-004-placement-window.md`
6. `docs/decisions/ADR-001-erratum-005-seam-overlap.md`
7. `docs/decisions/ADR-001-erratum-006-area-anchor.md`
8. `docs/decisions/ADR-001-erratum-007-ordinal-vs-coordinate.md`
9. `docs/decisions/ADR-001-erratum-008-wind-direction.md`
10. `docs/decisions/ADR-001-erratum-009-acceptance-gate.md`
11. `docs/decisions/ADR-001-erratum-010-report-completeness.md`
12. `docs/decisions/ADR-001-erratum-011-hash-domain.md`
13. `docs/decisions/ADR-001-erratum-012-diagnostic-type.md`
14. `docs/decisions/ADR-001-erratum-013-sheet-parameter-vs-layer-arc.md`
15. `docs/decisions/ADR-001-erratum-014-core-box-units.md`
16. `docs/decisions/ADR-001-erratum-015-f02-catalog-area-formula.md`
17. `docs/decisions/ADR-001-erratum-016-diagnostic-context-nested.md`
18. `docs/decisions/ADR-001-erratum-017-f07-wind-direction.md`
19. `docs/decisions/ADR-001-erratum-018-neutral-hand-everywhere.md`
20. `docs/decisions/ADR-001-erratum-019-invertibility-seam-cut.md`
21. `docs/decisions/ADR-001-erratum-020-cross-erratum-seams.md`
22. `docs/decisions/ADR-001-erratum-021-layer-arc-units.md`
23. `docs/decisions/ADR-001-erratum-022-source-forks.md`
24. `docs/decisions/core-v2-fixtures.md`
25. `docs/decisions/core-v2-legacy-boundary.md`

При конфликте между ТИПАМИ документов приоритет такой: erratum → ADR → fixtures →
этот brief → код `play/core-v2/**` → legacy/docs/archive.
Статус ADR (`proposed`/`accepted`) на эту лестницу не влияет — она про то,
какой источник истины выигрывает при противоречии формулировок, а не про то,
разрешено ли начинать реализацию (это отдельный критерий, `ADR-001-core-v2-scope.md`,
раздел «Критерий принятия», см. `ADR-001-erratum-009-acceptance-gate.md`).

При конфликте между ДВУМЯ ERRATUM, независимо правящими одну и ту же строку одной и
той же таблицы (или одно и то же поле типа) — как случилось между erratum-005 и
erratum-010 на приёмке F01: побеждает **более поздний номер**, но только для СТРОКИ/
ПОЛЯ, которое они оба трогают буквально. Патч более позднего erratum — это вставка в
НАКОПЛЕННОЕ состояние документа (все более ранние патчи уже применены), а не замена
всего раздела базовым текстом `core-v2-fixtures.md`/`ADR-001-core-v2-scope.md`. Если
патч erratum пишет «Было: <текст>», этот текст обязан быть текущим состоянием ПОСЛЕ
всех более ранних erratum, а не текстом из непатченного оригинала — иначе патч рискует
незаметно откатить более раннюю правку, ничего не сказав об этом в шапке «Заменяет».

## Scope первого PR

Реализовать только:

- F01: пустой хосомаки;
- F02: один огурец в центре `placementWindowMm` (erratum-004);
- `neutralHand` как единственный hand mode;
- валидацию рецепта;
- построение winding state;
- sample центрального среза;
- measurements и hashes;
- Node-compatible test runner;
- mutation tests из документа fixtures, относящиеся к F01/F02.

## Явные non-goals

Не реализовывать и не рефакторить:

- UI, canvas, анимацию, audio, URL, localStorage;
- puzzle mode, `turns` как вход, уровни и scoring;
- урамаки, тэмаки, формы квадрат/треугольник;
- реальную руку, pressure, случайность, физику разрушения;
- мазки, inverse design, мини-роллы и кадзари-маки;
- миграцию legacy recipes;
- исправление или рефакторинг `play/model/geometry.js`.

## Файлы первого PR

```text
play/core-v2/units.js
play/core-v2/recipe.js
play/core-v2/validate.js
play/core-v2/winding.js
play/core-v2/section.js
play/core-v2/measure.js
play/core-v2/hash.js
play/core-v2/fixtures.js
play/core-v2/run-fixtures.mjs
play/core-v2/core-v2.test.mjs
play/core-v2/package.json
```

`play/core-v2/package.json` (`{"type": "module"}`) относится только к файлам
внутри `play/core-v2/`. Легаси `play/*.js` как грузились через `<script>` в
браузере, так и продолжают — этот файл их не касается, корень репозитория
он тоже не трогает (там package.json как не было, так и нет). Без него
`.js`-файлы этого списка (`units.js`…`hash.js`) Node по умолчанию считает
CommonJS, и `import`/`export` в них упадёт с `SyntaxError` в момент, когда
`run-fixtures.mjs` попробует их импортировать.

Можно изменить этот список только с письменным обоснованием в PR. Не изменять production legacy-файлы.

## Требования к реализации

### Данные и единицы

- Внутри V2 все расстояния — мм, углы — радианы, площади — мм².
- Не использовать global state.
- Рецепт входа immutable: freeze в test mode или эквивалентная проверка отсутствия мутаций.
- Все численные допуски именованы и выведены в report.

### Намотка

- Карта листа должна задавать соответствие `uMm ↔ sMm ↔ angleRad`.
- Нельзя задавать угол только пропорцией номера бина, если это нарушает длину дуги.
- Полная длина листа должна быть учтена: нет lost или phantom segment выше `EPS_LENGTH_MM`.
- Шов является явной частью `WindingResult`.
- Если след патча физически за краем листа — `invalid: patch_out_of_sheet`. Если след патча
  на листе, но вне `placementWindowMm` — `outsideModelScope: closure_window`. Два разных
  входа, два разных кода, ни разу не fallback на лучший возможный ролл (erratum-004).

### Детерминизм

- Не использовать `Math.random`, время, FPS или порядок кеша.
- Одинаковый RecipeV2 даёт одинаковые hashes после повторного запуска и после создания нового kernel instance.
- Hash строится над `canonicalize(value)` — рекурсивной сортировкой ключей объекта по code unit
  (без кастомного компаратора, без опоры на порядок вставки); массивы и TypedArray-семплы — в
  исходном порядке (TypedArray обязан идти через ту же ветку, что и Array, иначе индексы
  сортируются лексикографически); точное определение и запрещённые упрощения см.
  `ADR-001-erratum-011-hash-domain.md`. `hashes.recipe` берётся над входным `RecipeV2` до
  вычислений; `hashes.winding`/`hashes.section` — над полным `WindingResult`/`SectionResult`,
  который `buildWinding`/`sampleSection` вернули kernel'у, а не над агрегатными полями
  `FixtureReport` и не над самим `FixtureReport`. Это последнее правило (домен) обязательно к
  соблюдению по сигнатуре хэш-функций и проверяется на code review — см. ограничение чёрного
  ящика в `ADR-001-erratum-011-hash-domain.md`.

### Патчи

- Для F02 достаточно одного осевого прямоугольного патча огурца.
- Порядок массива патчей не должен иметь эффекта без явного `placementOrder`.
- В F01/F02 не вводить эвристику auto-centering.

## Обязательные команды/вывод

Добавить одну команду, которую можно выполнить без браузера. Например:

```sh
node play/core-v2/run-fixtures.mjs
```

Она должна вернуть компактную таблицу: fixture id, status, `uMinMm`, `uMaxMm`, covered/uncovered/phantom length, seam, hashes и число diagnostics. При провале process должен завершаться с ненулевым кодом.

## Definition of done

PR готов к review только если:

- F01 и F02 зелёные автоматически;
- F06-подмножество для F01/F02 подтверждает повторяемость;
- все применимые mutation tests становятся красными при намеренной поломке;
- test output показывает measurements, а не только `pass`;
- нет импортов legacy geometry, UI и global state;
- нет изменения legacy production-кода;
- есть короткая PR-заметка: модель, дискретизация, `EPS_LENGTH_MM`, `PLACEMENT_EDGE_MARGIN_MM`
  (предварительное значение из A5/#57, erratum-004, если владелец ещё не подтвердила) и
  известные ограничения;
- в PR приложен machine-readable JSON FixtureReport для F01 и F02.

## Что reviewer отклонит

- «Срез выглядит правильно» без сохранения длины листа.
- Сравнение с legacy как с ожидаемым численным oracle.
- Появление `turns` в Core V2 input.
- Молчаливое исправление невалидной раскладки.
- Кеш, меняющий результат.
- Начало F03/F05 или UI до зелёных F01/F02.
