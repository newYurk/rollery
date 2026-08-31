# Аудит вызовов геометрии

Кто и как сегодня берёт данные у `play/model/geometry.js`. Документ read-only: по нему
принимаются решения о границе facade, сам код в этом заходе не менялся.

## Основание

- Репозиторий: `newYurk/rollery`
- Ветка: `refactor/geometry-facade-baseline`
- Базовая ревизия: `9e9ce2a442bfc1366253502c3bf87b154f5e52e6`
- Дата аудита: 30.08.2026
- Метод: чтение кода по группам файлов (пять параллельных проходов), 203 найденных места;
  всё, что ниже, — с файлом и строкой, без предположений.

## Как всё загружается

**Сборки нет, модулей нет.** Стенд — classic scripts: файлы делят одно лексическое окружение,
`import`/`export` в проекте не встречаются ни разу. Порядок подключения задан в
`play/index.html:21–33` и обязателен:

```
model/util.js → model/catalog.js → state.js → model/geometry.js → [domain/roll.js] →
audio.js → ui/layout.js → render/slice.js → render/sheet.js → ui/controls.js →
render/screens.js → ui/album.js → modes/puzzle.js → ui/actions.js
```

Проверочный путь догружается отдельно и последовательно при `?check`
(`play/index.html:156–159`): `inverse/primitives.js`, `inverse/materials.js`, `checks.js`.

Отсюда следствие для facade: **никаких `export`** — иначе стенд перестанет запускаться.
Границу задаёт не модульная система, а дисциплина вызовов и проверка на эквивалентность.

## Карта потребителей

| Потребитель | Что берёт у геометрии | Чтение/запись | Побочные эффекты | Метод facade | Очередь переезда |
|---|---|---|---|---|---|
| `play/render/slice.js` | `windFor`, `materialAt`, `topAt`, `spreadColor`, `wrapperColor`, `patchColor`, `NB`, `DPHI`, `GRAIN_C` | чтение + кеши | `shapeCache`, `faceCache`; **`touchModel` живёт здесь же** (`:338`) | `sliceAt()` | **кандидат первым** (только `materialMap`/`similarity`) |
| `play/render/sheet.js` | `spreadColor`, `sheetLen`, `dims`, `ING` | чтение + кеш `spreadTex` | текстура в offscreen canvas | `deriveSheetLayout()` | позже |
| `play/render/screens.js` | `getModel`, `windFor`, `windRout`, `RIM_W`, поля модели | чтение | рисование на canvas | — | позже |
| `play/ui/actions.js` | `bounds`, `dims` (оба **без `g`**) | чтение + **мутации патчей** | `p.u/p.v/p.rot`, `patches().splice/push` | команда приложения, не facade | позже |
| `play/ui/controls.js` | — (геометрию не зовёт вовсе) | — | — | — | не требуется |
| `play/ui/layout.js` | `sheetLen(B())` (`:42`) | чтение | пишет глобальный `L` | `deriveSheetLayout()` | позже |
| `play/ui/album.js` | `buildModel` (`:33`), `face` поверх модели | чтение + запись `S.album`, localStorage | подменяет `S` и восстанавливает | `serializeRecipe`/`deserializeRecipe` | позже |
| `play/modes/puzzle.js` | `sheetLen`, `buildModel`, `getModel`, поле `m.g.L` | чтение + запись `S.puzzle`, localStorage | `touchModel` | политика режима | позже |
| `play/inverse/*` | геометрию **не зовёт** (`ING`/`WRAPPERS` приходят аргументами) | — | — | — | не требуется |
| `play/checks.js` | `getModel`, `windFor`, `topAt`, `innerAt`, `materialAt`, `spreadAt`, `spreadColor`, `sheetLen`, `dims`, `NB`, `KMAX` | чтение | сохраняет/возвращает `S` и localStorage | тестовый адаптер | **первый (сделан)** |
| `play/index.html` (инлайн) | `dims` (`:108`), `sheetLen` (`:115`) | чтение | bootstrap | только загрузка | позже |

## Наблюдения по legacy-API

### Чистое и почти чистое

`boxHit`, `cutSpan`, `cutTop`, `sampleWind`, `innerAt`, `topAt` — зависят только от аргументов.
`riceField`, `thicknessProfile` требуют паспорт `g` (без него не работают) и при нём чисты.

### Завязанное на глобальное состояние

`sheetLen` читает `S.turns` (`geometry.js:22`). `gL`, `dims`, `bounds`, `patchBox`, `overlap`,
`spreadAt`, `betaEff` при `g === undefined` падают на `B()` — текущую базу, — и **UI пользуется
именно этим режимом** (`actions.js:19,25,138` зовут `dims`/`bounds` без `g`). Facade обязан его
сохранить. `buildModel` (`:668–678`) собирает ключ кеша и паспорт из `S.base`, `B().wrapKey`,
`S.shape`, `S.turns`, `S.hand` — то есть **рецепт передаётся геометрии через глобальное
состояние, а не аргументом**. Это главный шов миграции. `wind` (`:445`) читает `S.hand.press`
только при самодельном `g`; из `buildModel` прижим всегда приходит в паспорте.

### Кеши

Три уровня: `modelCaches` (ключ включает базу, обёртку, форму, витки, руку и список),
`m.wds` (намотка по ломтику) и `p._sr` — кеш отрезков **на самом патче**, скрытый
`defineProperty(enumerable:false)`, чтобы не утекать в localStorage (`:47–51`). Инвалидация
модели идёт не через геометрию, а через `touchModel` — и он живёт в `render/slice.js:338`,
хотя к рисованию среза отношения не имеет.

### Мутации

`restack` пишет `p.z0/p.z1` в каждый элемент списка, `computeCore` ставит `p.inCore`,
`srReset` — скрытый `p._sr`. Поэтому **любой путь, отдающий геометрии чужой массив, обязан
его клонировать** — `buildModel` так и делает (`:675`), и facade делает то же.

### Скрытый канал `GRAIN_C`

`spreadColor` (`geometry.js:877`) пишет результат в глобальный `GRAIN_C`, а рендер читает его
сразу после вызова (`slice.js:146`, `:283`) — включая вызов-пустышку ради побочного эффекта.
Это самая хрупкая связь: протокол «позвал → немедленно прочитал» не выражен в сигнатуре.
Facade его не трогает; при переезде рендера канал придётся сделать явным возвратом.

### Мёртвые публичные символы

`geometry()` (`:144`) и `covers()` (`:164`) не вызываются нигде в `play/`. Первый к тому же
мутирует живой список патчей (`restack(patches())` без `g`). В facade не переносятся.

### Форма результата, на которую опирается регрессия

`checks.js` читает не только функции, но и структуру: `m = { g: { L, r0, spreadEnd, sweet },
core, Rmax, wds }`, `wd = { turns, top[], rin[], rout[], u0[] }`. Любая смена внутренностей
обязана сохранить эти поля либо менять `checks.js` тем же коммитом.

### Сериализация рецепта, которая уже существует

- **Альбом** (`album.js:14`): `{ id, base, turns, shape, hand{air,wobble,phase,press}, list, at, level, sim }`.
  **Поля `wrap` в записи нет** — обёртка при сохранении теряется, и запись с блином вернётся
  как нори. Зафиксировано fixture `F03`, заведено отдельно (см. ниже).
- **Ссылка-пазл** (`puzzle.js:117–130`): `{ b, t, s, h[4], l[[kind,u,v,wU,hU,dv,phase,rot]] }`,
  base64url в хэше `#p=`. Патчи — кортежи по позициям, порядок полей значим.

## Где проведена первая граница

`play/domain/roll.js` — тонкий переходник поверх нынешней геометрии:
`createRecipe` · `validateRecipe` · `evaluateRoll` · `sliceAt` · `deriveSheetLayout` ·
`serializeRecipe` · `deserializeRecipe`.

Формат рецепта — **тот, что уже есть в проекте** (запись альбома плюс `wrap`), новая модель
не вводится. Шов с глобальным `S` собран в одном месте (`withRollRecipeState`): пока геометрия
читает `S`, переходник вынужден его ставить и возвращать — но делает это один раз, а не в
каждом вызывающем.

Единственный потребитель facade сейчас — тестовый адаптер
(`play/test/domain/roll-facade-checks.js`). Ни один production-файл не переведён.

**Кандидат на первый настоящий переезд:** `materialMap`/`similarity` в `render/slice.js`
(`:306–327`) — по аудиту это чистый read-only участок: не мутирует состояние, не связан с
жестом. Оговорка: рядом в том же файле лежат `touchModel` и чтение `GRAIN_C`, поэтому переезд
брать узко и отдельным PR. **Не начинать** с `ui/actions.js`, `modes/puzzle.js`, `state.js`.

## Чего здесь намеренно нет

- Правок `play/model/geometry.js` — ни строки.
- Новой модели рецепта (`layers[]`, `Layer`, `InternalLayer`): радиальный порядок возникает из
  скрутки, а раскладка живёт на плоском листе — одним массивом «от центра к краю» это не
  выражается. Решается отдельным RFC `docs/architecture/recipe-model-rfc.md` — он ещё не написан, имя дано заранее.
- Переноса `catalog.js` в `domain/`, новой сериализации, переезда production-потребителей.
- Переписывания `checks.js`: добавлена только точка подключения новых проверок.
- Фреймворков и тест-раннеров: проверки идут тем же путём, что и вся регрессия, — `?check`.
