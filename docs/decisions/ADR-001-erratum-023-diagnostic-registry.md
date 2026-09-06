# ADR-001, Erratum 023 — закрытый список диагностик был закрыт на девяти кодах, а ядро эмитит двадцать три

- **Статус:** proposed; правит `ADR-001-erratum-012-diagnostic-type.md` (таблица «Обязательный `context` по `code`»).
- **Дата:** 2026-09-06.
- **Кому:** ревьюеру / разработчику Core V2.
- **Повод:** #205, пункт 6.

## Что разошлось

`erratum-012` объявил список кодов **закрытым**: «Новый diagnostic code обязан добавить свою строку в эту таблицу, а не молчаливым использованием кода, которого здесь нет». Сверка 06.09 — обходом обоих эмитентов (`validate.js`, `from-layout.js`) регулярным выражением по `diagnostic(...)` и `refuse(...)`:

| | сколько |
|---|---|
| кодов эмитится ядром | **23** |
| из них есть в закрытом списке | **6** |
| эмитится, в списке нет | **17** |
| в списке есть, не эмитится никогда | **1** |

⚠ #205 называл четыре кода вне списка. Их семнадцать. Разница не в невнимательности: тринадцать из них живут в `from-layout.js`, который отдаёт диагностики **той же формы** (`{ code, message, context }`) и в то же поле отчёта, а grep в исходной сверке искал только `diagnostic('…')` и не видел `refuse('unsupported', '…')`.

⚠ И одно расхождение #205 пропустил вовсе: **список знает `non_neutral_hand_in_puzzle`, а код эмитит `non_neutral_hand`** — оба эмитента, три места. Это не отсутствующая строка, а разъехавшееся имя: хуже, потому что выглядит покрытым.

## Решение

Список **остаётся закрытым**; закрывать его на девяти кодах, когда эмитится двадцать три, — не дисциплина, а фикция. Ниже он приводится к тому, что ядро делает, с обязательным `context` по факту кода.

### Правка таблицы `erratum-012` — коды `validate.js`

| `code` | `status` | Обязательные ключи `context` | Требование |
|---|---|---|---|
| `patch_out_of_sheet` | `invalid` | `patchId`, `sheetLengthMm`, `observedFootprintMm` | erratum-004, F04a |
| `closure_window` | `outsideModelScope` | `patchId`, `placementWindowMm` | erratum-004, F04b |
| `patch_rotated` | `unsupported` | `patchId`, `observedRotationDeg` | erratum-002 |
| `patch_material_overlap` | `invalid` | `patchIds`, `materialId` | erratum-007, F07 |
| `recipe_missing_wind_direction` | `invalid` | `observedValue` | erratum-008 |
| `conical_roll` | `unsupported` | `requestedFeature` | ADR-001, «Поведение вне модели» |
| `inside_wrap_topology` | `unsupported` | `requestedFeature` | там же |
| `section_shape` | `unsupported` | `requestedFeature` | там же |
| **`non_neutral_hand`** | `invalid` | `observedHandMode` | **переименование, см. ниже** |
| **`sheet_too_short`** | `invalid` | `noriPerimeterMm`, `sheetLengthMm` | лист короче одного оборота |
| **`wraps_beyond_two`** | `outsideModelScope` | `noriPerimeterMm`, `sheetLengthMm` | больше двух витков обёртки |
| **`chef_corridor`** | `outsideModelScope` | `diameterMm`, `corridorMm` | диаметр вне коридора практики |
| **`core_overflow`** | `invalid` | `patchId`, `overflowMm` | начинка не помещается в ядро |

### Правка таблицы — коды `from-layout.js` (адаптер legacy → V2)

Отдельным разделом, потому что это **граница с legacy**, а не отказ ядра: сюда попадает то, что живая игра умеет, а V2 alpha ещё нет. Форма та же, и закрытость списка на них распространяется.

| `code` | `status` | Обязательные ключи `context` |
|---|---|---|
| `base_shape` | `invalid` | `baseKey` |
| `base_unsupported` | `unsupported` | `requestedFeature`, `supported` |
| `wrap_unsupported` | `unsupported` | `requestedFeature` |
| `shape_unsupported` | `unsupported` | `requestedFeature` |
| `turns_override` | `unsupported` | `observedTurns` |
| `patch_shape` | `invalid` | `index` |
| `patch_unknown_kind` | `invalid` | `index`, `observedKind` |
| `patch_is_paint` | `unsupported` | `requestedFeature` |
| `patch_cut_unsupported` | `unsupported` | `patchKind`, `observedCut`, `supported` |
| `patch_axial_profile` | `unsupported` | `patchKind`, `observedAxial` |
| `patch_wave` | `unsupported` | `patchKind` |
| `patch_nori_wrap` | `unsupported` | `patchKind` |
| `patch_rotated` | `unsupported` | `patchKind`, `observedRotationDeg` |
| `non_neutral_hand` | `invalid` | `observedHandMode` |

### Переименование `non_neutral_hand_in_puzzle` → `non_neutral_hand`

Побеждает код, и по существу, а не по факту. Имя из `erratum-012` привязывает отказ к **режиму** (puzzle), тогда как правило ADR-001 шире: V2 alpha принимает нейтральную руку **везде** — это прямо зафиксировано `erratum-018` («neutral hand everywhere»). Имя `non_neutral_hand_in_puzzle` осталось от более узкой формулировки, которую erratum-018 уже отменил, и держать в реестре имя, противоречащее более позднему erratum, нельзя.

`non_neutral_hand_in_puzzle` из списка **снимается**. Кода с таким именем ядро не эмитило никогда.

### `conical_roll` и `inside_wrap_topology` — были в списке и не эмитились

До 06.09 обе строки таблицы `erratum-012` были **мёртвыми**: `validateRecipe` не читал `baseId` вовсе, и тэмаки проходил как хосомаки с хешем бит в бит (#205, пункт 1). Исправлено в том же заходе; коды теперь эмитятся из `validate.js` по таблице соответствия.

⚠ Обе эмитятся **через переменную**, а не литералом (`BASE_REFUSALS[shown] || 'section_shape'`), поэтому grep по `diagnostic('conical_roll'` их не найдёт. Инвентаризацию кодов вести чтением таблицы соответствия, а не только регулярным выражением.

## Что это меняет в приёмке

Ничего в числах: ни один хеш, ни одна фикстура не двигаются. Меняется проверяемость — до этой правки утверждение «kernel объясняет каждый отказ кодом из реестра» было ложным для семнадцати кодов из двадцати трёх, и никакая fixture этого поймать не могла, потому что сверять было не с чем.
