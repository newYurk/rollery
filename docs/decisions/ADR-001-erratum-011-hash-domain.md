# ADR-001, Erratum 011 — домен и каноническая сериализация трёх hash в FixtureReport

- **Статус:** proposed; действует как обязательное уточнение для реализации до отдельного ADR о `play/core-v2/hash.js`.
- **Дата:** 2026-09-04
- **Заменяет в контракте:** `core-v2-fixtures.md` — тип `FixtureReport`, поле `hashes`; и формулировку `core-v2-developer-brief.md:80`.
- **Отвечает на находки ревью:** `hash-domain-undefined`, `canonical-serialization-undefined` (обе blocker, каждая 1/2 голоса скептиков).
- **Кому:** ревьюеру / разработчику Core V2.

## Исправление

### 1. Домен каждого hash

`hashes.recipe`, `hashes.winding`, `hashes.section` считаются НЕ над `FixtureReport` и не друг
над другом. Каждый — над собственным сырым объектом пайплайна (`RecipeV2 → buildWinding →
WindingResult → sampleSection → SectionResult → measure → FixtureReport`, core-v2-legacy-boundary.md:72-77):

```ts
hashes: {
  // canonicalize() входного RecipeV2 ровно в том виде, в котором он передан в runFixture —
  // до validateRecipe/buildWinding и без каких-либо derived-полей.
  recipe: string
  // canonicalize() полного WindingResult: все семплы uMm↔sMm↔angleRad по бинам намотки
  // и seam, на полной точности float64 — объект, который buildWinding вернул kernel'у, а не
  // производные от него поля sheet.*/seam в этом же отчёте.
  winding: string
  // canonicalize() полного SectionResult: позиции границ материалов на срезе (мм/рад) —
  // объект, который sampleSection вернул kernel'у, а не производные от него visiblePatches/
  // areaMm2/centerXmm/centerYmm в этом же отчёте.
  section: string
}
```

Правило одной фразой: **отчёт не является входом hash**. `hashWinding`/`hashSection` обязаны
получать на вход тот же объект, который `buildWinding`/`sampleSection` вернули kernel'у, а не
значения, которые затем попадут в `sheet`/`seam`/`roll`/`visiblePatches` полях `FixtureReport`.
Округление здесь ни при чём — ни один из шести документов контракта не упоминает округление
отчётных полей вообще (проверено: `grep -rn "округл\|toFixed\|precision" docs/decisions/
ADR-001*.md docs/decisions/core-v2-fixtures.md docs/decisions/core-v2-legacy-boundary.md
docs/handoff/core-v2-developer-brief.md` — ноль совпадений). Дыра не в точности чисел, а в
СТРУКТУРЕ: `sheet`/`seam`/`roll` — суммарные/крайние величины (агрегаты) над множеством
семплов, а не сами семплы, и уже поэтому не являются заменой полному
`WindingResult`/`SectionResult` как входу hash — вне зависимости от того, появится ли
когда-нибудь округление или нет.

### 2. Правило канонической сериализации

`core-v2-developer-brief.md:80`

Было: «Hash строится над канонической сериализацией, в которой порядок object keys стабилен.»

Стало:

> Hash строится над `canonicalize(value)`, определённой рекурсивно:
>
> ```
> canonicalize(value):
>   if value is number:
>     assert isFinite(value)              // NaN/Infinity уже запрещены инвариантом «Конечность»
>     return JSON.stringify(value)         // ECMA-262 Number::toString — одна строка на одно double
>   if value is string or boolean:
>     return JSON.stringify(value)
>   if value is null:
>     return "null"
>   if value is DataView:
>     throw new Error("canonicalize: DataView не поддерживается — сериализуйте поля явно")
>   if value is Array or ArrayBuffer.isView(value):
>     // ArrayBuffer.isView(value) ловит TypedArray (Float64Array/Int32Array/...) — естественный
>     // выбор хранения для 1000+ числовых семплов uMm/sMm/angleRad по бинам намотки.
>     // Array.isArray(typedArray) === false, поэтому эта ветка ОБЯЗАНА идти раньше ветки Object:
>     // иначе TypedArray попадёт в Object.keys(value).sort(), который сортирует числовые индексы
>     // ЛЕКСИКОГРАФИЧЕСКИ ('0','1','10','100',...,'2',...) и молча переставляет порядок семплов.
>     arr = Array.isArray(value) ? value : Array.from(value)
>     return "[" + arr.map(canonicalize).join(",") + "]"   // порядок массива не трогаем — это данные
>   if value is Object:
>     keys = Object.keys(value).sort()     // сортировка по code unit, без кастомного компаратора,
>                                           // без опоры на порядок вставки и без опоры на то, что
>                                           // движок сам выносит integer-like ключи вперёд
>     return "{" + keys.map(k => JSON.stringify(k) + ":" + canonicalize(value[k])).join(",") + "}"
> ```
>
> `digest(str)` — любая детерминированная функция строка→строка (например DJB2/FNV-1a или
> `crypto.createHash('sha1')`); контракт не навязывает алгоритм, только то, что её аргумент —
> всегда `canonicalize(...)`, никогда объект отчёта и никогда `JSON.stringify(value)` без
> сортировки ключей. Выбор алгоритма и его версия фиксируются в PR-заметке (developer-brief.md:108).

Явно запрещено:
- вызывать `JSON.stringify(recipe | windingResult | sectionResult)` напрямую — это insertion
  order, не каноническая сериализация;
- опираться на порядок объявления полей в TS-типе — он не существует в рантайме;
- сортировать ключи только на верхнем уровне — сортировка обязана быть рекурсивной, иначе любой
  вложенный объект (например будущая карта долей материалов по id) снова становится источником
  недетерминизма того же типа, который уже закрыт для карты материалов в `play/domain/roll.js:237`
  (`rollMapDigest` явно вызывает `.sort()` на ключах `counts`) — этот же паттерн распространяется
  на все три hash, а не только на карту материалов;
- передавать TypedArray в реализацию `canonicalize`, у которой нет отдельной ветки
  `ArrayBuffer.isView(value)` перед веткой `Object` — см. пример выше с лексикографической
  сортировкой числовых индексов.

## Причина

`FixtureReport` кладёт `hashes` рядом с полями `sheet`/`seam`/`roll`, которые по построению —
агрегаты (например `sheet.coveredLengthMm`, `sheet.uMinMm`/`uMaxMm`, `roll.diameterMinMm`/
`diameterMaxMm`, `roll.wrapIntersectionsByRay` — суммы, крайние значения, один массив по
лучам), а не полный набор семплов `WindingResult`/`SectionResult` (core-v2-fixtures.md:23-39).
Ничто в типе `FixtureReport` не запрещает реализации посчитать hash от этих агрегатов вместо
полного `WindingResult`/`SectionResult`. Отдельно, «порядок object keys стабилен»
(developer-brief.md:80) одинаково верно для insertion order, лексикографической сортировки и
порядка объявления схемы — три разные строки hash для одного и того же физического рецепта, если
два патча в нём записаны в разном литеральном порядке полей (`{id,materialId,uMm,vMm}` vs
`{materialId,id,vMm,uMm}`).

## Ограничение: что из этого правила проверяется fixture-ами автоматически, а что — только на code review

Правило домена («hash над полным pipeline-объектом, не над отчётом») проверено адверсарной
проверкой на предмет самодостаточности fixture-теста и требует честной оговорки:

- Реализация, которая считает `hashes.winding`/`hashes.section` от **агрегатов** `sheet`/`seam`/
  `roll` вместо полного `WindingResult`/`SectionResult`, но при этом полностью детерминирована
  (без багов, без `Math.random()`), пройдёт F01-F06 целиком: hash воспроизводится между запусками
  той же сборки, recipe hash проходит round-trip, измерения совпадают в пределах допуска — F06
  (fixtures.md:173-190) проверяет именно это, и ни одна из этих проверок не требует, чтобы hash
  различал структуру, которой нет в отчётных полях.
- Мутация «джиттер `1e-12` к семплам» (см. таблицу ниже) ловит implementation-от-агрегата ровно
  потому, что джиттер физически меняет значения агрегатов (сумма длины сдвигается на величину
  порядка `N × 1e-12`) — это тест на чувствительность к **точности**, а не на выбор домена как
  такового.
- Отдельного fixture-а, различающего домен структурно (два входа с идентичными агрегатами
  `sheet`/`seam`/`roll`, но разным порядком/составом семплов внутри бинов намотки — например,
  переставленные бины с одинаковой суммарной длиной и одинаковым `seam.angleRad`), этот erratum
  не поставляет: построение такой пары требует знания конкретной раскладки бинов намотки, которого
  в контракте пока нет. Это **открытая задача** для реализации, а не закрытая правкой: пометка
  `TODO(core-v2): black-box fixture, различающая winding/section hash по структуре при идентичных
  агрегатах — требует конкретной пары входов` остаётся в `core-v2-fixtures.md` до тех пор, пока
  такая пара не будет сконструирована и добавлена как отдельная строка F06.
- До появления такого fixture-а правило домена в разделе 1 обязательно к соблюдению как
  **требование к коду** (проверяется по сигнатуре `hashWinding(windingResult: WindingResult)` /
  `hashSection(sectionResult: SectionResult)` и по code review — они обязаны получать на вход
  объект, который вернули `buildWinding`/`sampleSection`, а не поля `FixtureReport`), а не как
  факт, который F06 сегодня гарантированно ловит black-box.

## Ownership / что этой правкой НЕ решается

Домены и `canonicalize()` не задевают резервированную развилку про кусок/лист (тянется ли начинка
вместе с изгибающимся листом, или лист несёт длину дуги отдельно, а кусок хранит форму и
проскальзывает) — правило работает одинаково независимо от её будущего решения. Когда тот ADR
добавит новые поля в `WindingResult`/`SectionResult` (например `stretchFactor` на кусок), они
автоматически попадают в домен `winding`/`section` hash по этому же правилу, без изменения этой
правки.

## Правка `docs/decisions/core-v2-fixtures.md`

### F06 — добавить строку приёмки (после «Все три запуска имеют идентичные `winding` и `section` hashes.»)

```markdown
- Два рецепта, физически идентичные, но с разным литеральным порядком ключей в исходном JS-объекте
  одного и того же патча (например `{ id, materialId, uMm, vMm }` и `{ materialId, id, vMm, uMm }`),
  дают один и тот же `recipe` hash.
```

### TODO — добавить сразу после таблицы Mutation tests (новый пункт, не закрывать молча)

```markdown
> **TODO(core-v2):** правило домена hash (ADR-001, Erratum 011, раздел 1) требует, чтобы
> `hashes.winding`/`hashes.section` считались над полным `WindingResult`/`SectionResult`, а не
> над агрегатами `sheet`/`seam`/`roll`. Ни одна текущая F0x-строка или мутация не ловит нарушение
> этого правила black-box, если нарушение не сопровождается физическим изменением значений (как в
> мутации с джиттером ниже) — детерминированная реализация «hash от агрегатов» проходит весь набор
> F01-F06. До появления пары входов с идентичными `sheet`/`seam`/`roll`, но разным составом/порядком
> семплов внутри бинов намотки, домен проверяется на code review по сигнатуре
> `hashWinding(windingResult: WindingResult)`/`hashSection(sectionResult: SectionResult)`, а не
> фикстурой.
```

### Таблица Mutation tests — заменить строку про `Math.random()` и добавить две новые

Было:

```markdown
| Добавить `Math.random()` при построении wind-state | F06: hashes |
```

Стало:

```markdown
| Добавить `Math.random() * 1e-12` к каждому семплу `sMm`/`angleRad` при построении wind-state (на каждый из бинов намотки) — тест на чувствительность hash к точности семплов, а не на выбор домена как такового | F06: `winding`/`section` hash |
| Посчитать `hashes.winding`/`hashes.section` от уже посчитанных полей `sheet`/`seam`/`roll` вместо полного `WindingResult`/`SectionResult`, оставив саму намотку/срез детерминированными (без джиттера) | Не гарантированно ловится ни одной существующей F0x-строкой black-box — см. TODO выше и «Ограничение» в ADR-001, Erratum 011; обязательна к соблюдению как code-review требование по сигнатуре хэш-функций |
| Сериализовать `recipe` hash через `JSON.stringify(recipe)` (insertion order) вместо `canonicalize(recipe)` | F06: новая строка про перестановку ключей патча |
```

### Тип `FixtureReport` — комментарии к полю `hashes`

Было:

```ts
hashes: { recipe: string; winding: string; section: string }
```

Стало:

```ts
hashes: {
  // canonicalize() входного RecipeV2 как он передан в runFixture, до любых вычислений.
  recipe: string
  // canonicalize() полного WindingResult (все семплы uMm↔sMm↔angleRad, seam) — объект, который
  // buildWinding вернул kernel'у, а НЕ производные от него агрегаты sheet.*/seam в этом же отчёте.
  // См. ADR-001, Erratum 011 (включая ограничение: домен проверяется на code review, не только
  // фикстурой).
  winding: string
  // canonicalize() полного SectionResult — объект, который sampleSection вернул kernel'у, а НЕ
  // производные от него visiblePatches/areaMm2/centerXmm/centerYmm в этом же отчёте.
  // См. ADR-001, Erratum 011.
  section: string
}
```

