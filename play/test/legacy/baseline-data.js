'use strict';
// СЛЕПОК LEGACY-ПОВЕДЕНИЯ: что геометрия считает на базовой ревизии 9e9ce2a.
//
// СНЯТ ПРОГОНОМ, А НЕ НАПИСАН РУКАМИ: captureLegacyBaseline() (play/test/legacy/baseline.js)
// на ветке refactor/geometry-facade-baseline, 30.08.2026. Это характеризационный эталон —
// он описывает поведение КАК ЕСТЬ, включая то, что мы считаем дефектами.
//
// ⚠ ЭТО ДЕТЕКТОР, А НЕ ТРЕБОВАНИЕ — и на нынешнем этапе это принципиально.
//
// Геометрия проекта НЕ является истиной в последней инстанции: половина её чисел помечена
// `inferred`, лаборатория начала давать прогоны на годном разрешении только 30.08 (#91), а
// разбор правил скрутки (#98) может переписать кинематику целиком. Модель здесь — рабочая
// гипотеза, и менять её можно и нужно.
//
// Слепок НЕ запрещает менять модель. Он запрещает менять её МОЛЧА. Поэтому:
//   • упала проверка — сперва понять, что изменилось, и только потом трогать числа;
//   • изменение осознанное — переснять слепок ТЕМ ЖЕ коммитом, где сказано, что именно
//     поехало и почему (`captureLegacyBaseline()` в консоли даёт готовое содержимое);
//   • «просто обновить, чтобы стало зелено» — единственный запрещённый ход: так регрессия
//     превращается в самоисполняющееся пророчество.
//
// Практический смысл для игрока (формулировка владельца): сохранённый ролл, ссылка-пазл и
// альбом должны через месяц выглядеть так же — а если мир игры изменился, это должно быть
// нашим решением, а не побочным эффектом чужой правки.
//
// То же правило и у REF в начале play/checks.js.
//
// Что стоит знать про отдельные записи:
//   F03 — обёртка «блин» (2 мм) против нори (0,1 мм): ⌀ 62,4 против 58,7 у F02-подобной
//         раскладки, то есть обёртка действительно входит в шаг витка. Отдельно: альбом
//         (albumSave) поле wrap НЕ сохраняет — запись с блином вернётся как нори.
//   F07 — ролл на грани: 1,0056 витка. Это известный случай урамаки (issue #3), и слепок
//         фиксирует его как есть, а не как хотелось бы.
//
// ПЕРЕСНЯТ 30.08.2026 (дважды). Второй раз — при переезде materialMap/similarity за facade:
// в инварианты добавлены `map` (счётчики классов на карте среза + выборка) и `selfSimilarity`.
// СНЯТ ДО ПЕРЕЕЗДА, на прежней реализации из render/slice.js — в этом весь смысл: после
// переезда проверка сверяет новое поведение с числами, добытыми у старого кода, а не у
// самой себя. Числа намотки не изменились ни в одном fixture.
//
// Третий раз (тот же вечер) — по ревью PR #102: исправлен шаг выборки проб (337 давало
// точки по диагонали, в углы карты за пределами ролла), добавлен разделитель между
// классами и — главное — МЕЖМОДЕЛЬНЫЕ ПАРЫ (__pairs). Похожесть модели с собой почти
// ничего не проверяла: пять мутаций внутри similarity при таком входе выживали.
// Снято на коде main через отдельный worktree, то есть опять ДО переезда.
//
// Первый раз 30.08.2026 — в инварианты добавлено поле shape. Причина названа честно: ревью
// PR #100 показало, что форма прессовки не входила ни в один инвариант, и F04 «квадратная
// прессовка» на деле её не проверял. Числа намотки при этом не изменились ни в одном
// fixture — сравни с предыдущей ревизией файла: добавилась ровно одна строка на запись.

const ROLL_BASELINE = {
  "F01-hosomaki-basic": {
    "turns": 1.2833,
    "outerDiameterMm": 31.5308,
    "closePoint": -1,
    "sheetEnd": 21,
    "sheetLength": 21,
    "hasCore": true,
    "shape": "round",
    "coreRadius": 1.1645,
    "coreFold": 3,
    "patchCount": 1,
    "materialFractions": {
      "core": 0.3333,
      "patch:cucumber": 0.0938,
      "spread": 0.5521,
      "wrap": 0.0208
    },
    "probes": [
      "0.25|1|0=core",
      "0.25|1|6=core",
      "0.25|1|12=core",
      "0.25|1|18=core",
      "0.25|5|0=spread",
      "0.25|5|6=spread",
      "0.25|5|12=spread",
      "0.25|5|18=spread",
      "0.25|9|0=spread",
      "0.25|9|6=spread",
      "0.25|9|12=patch:cucumber",
      "0.25|9|18=spread",
      "0.5|1|0=core",
      "0.5|1|6=core",
      "0.5|1|12=core",
      "0.5|1|18=core",
      "0.5|5|0=spread",
      "0.5|5|6=spread",
      "0.5|5|12=spread",
      "0.5|5|18=spread",
      "0.5|9|0=spread",
      "0.5|9|6=spread",
      "0.5|9|12=patch:cucumber",
      "0.5|9|18=spread",
      "0.75|1|0=core",
      "0.75|1|6=core",
      "0.75|1|12=core",
      "0.75|1|18=core",
      "0.75|5|0=spread",
      "0.75|5|6=spread",
      "0.75|5|12=spread",
      "0.75|5|18=spread",
      "0.75|9|0=spread",
      "0.75|9|6=spread",
      "0.75|9|12=patch:cucumber",
      "0.75|9|18=spread"
    ],
    "map": {
      "counts": {
        "0": 963,
        "1": 1852,
        "2": 27,
        "4": 294
      },
      "probe": "0,1,4,1,1,1,1,1,1,1,0"
    },
    "selfSimilarity": 1
  },
  "F02-futomaki-basic": {
    "turns": 1.375,
    "outerDiameterMm": 58.4079,
    "closePoint": -1,
    "sheetEnd": 42,
    "sheetLength": 42,
    "hasCore": true,
    "shape": "round",
    "coreRadius": 2.1499,
    "coreFold": 6,
    "patchCount": 3,
    "materialFractions": {
      "core": 0.3333,
      "out": 0.0463,
      "patch:avocado": 0.0208,
      "patch:salmon": 0.0313,
      "patch:shrimp": 0.0069,
      "spread": 0.5532,
      "wrap": 0.0081
    },
    "probes": [
      "0.25|1|0=core",
      "0.25|1|6=core",
      "0.25|1|12=core",
      "0.25|1|18=core",
      "0.25|5|0=spread",
      "0.25|5|6=spread",
      "0.25|5|12=spread",
      "0.25|5|18=spread",
      "0.25|9|0=spread",
      "0.25|9|6=spread",
      "0.25|9|12=spread",
      "0.25|9|18=spread",
      "0.5|1|0=core",
      "0.5|1|6=core",
      "0.5|1|12=core",
      "0.5|1|18=core",
      "0.5|5|0=spread",
      "0.5|5|6=spread",
      "0.5|5|12=spread",
      "0.5|5|18=spread",
      "0.5|9|0=spread",
      "0.5|9|6=spread",
      "0.5|9|12=spread",
      "0.5|9|18=spread",
      "0.75|1|0=core",
      "0.75|1|6=core",
      "0.75|1|12=core",
      "0.75|1|18=core",
      "0.75|5|0=spread",
      "0.75|5|6=spread",
      "0.75|5|12=spread",
      "0.75|5|18=spread",
      "0.75|9|0=spread",
      "0.75|9|6=spread",
      "0.75|9|12=spread",
      "0.75|9|18=spread"
    ],
    "map": {
      "counts": {
        "0": 1024,
        "1": 1981,
        "2": 19,
        "3": 73,
        "6": 39
      },
      "probe": "0,1,1,1,1,1,1,1,1,1,0"
    },
    "selfSimilarity": 1
  },
  "F03-wrapper-roundtrip": {
    "turns": 1.3042,
    "outerDiameterMm": 62.4147,
    "closePoint": -1,
    "sheetEnd": 42,
    "sheetLength": 42,
    "hasCore": true,
    "shape": "round",
    "coreRadius": 2.3125,
    "coreFold": 6,
    "patchCount": 1,
    "materialFractions": {
      "core": 0.3333,
      "out": 0.0417,
      "patch:tamago": 0.0347,
      "spread": 0.5278,
      "wrap": 0.0625
    },
    "probes": [
      "0.25|1|0=core",
      "0.25|1|6=core",
      "0.25|1|12=core",
      "0.25|1|18=core",
      "0.25|5|0=spread",
      "0.25|5|6=spread",
      "0.25|5|12=spread",
      "0.25|5|18=spread",
      "0.25|9|0=spread",
      "0.25|9|6=spread",
      "0.25|9|12=spread",
      "0.25|9|18=spread",
      "0.5|1|0=core",
      "0.5|1|6=core",
      "0.5|1|12=core",
      "0.5|1|18=core",
      "0.5|5|0=spread",
      "0.5|5|6=spread",
      "0.5|5|12=spread",
      "0.5|5|18=spread",
      "0.5|9|0=spread",
      "0.5|9|6=spread",
      "0.5|9|12=spread",
      "0.5|9|18=spread",
      "0.75|1|0=core",
      "0.75|1|6=core",
      "0.75|1|12=core",
      "0.75|1|18=core",
      "0.75|5|0=spread",
      "0.75|5|6=spread",
      "0.75|5|12=spread",
      "0.75|5|18=spread",
      "0.75|9|0=spread",
      "0.75|9|6=spread",
      "0.75|9|12=spread",
      "0.75|9|18=spread"
    ],
    "map": {
      "counts": {
        "0": 1010,
        "1": 1711,
        "2": 324,
        "5": 91
      },
      "probe": "0,1,2,1,1,2,1,1,1,2,0"
    },
    "selfSimilarity": 1
  },
  "F04-puzzle-recipe": {
    "turns": 2.1701,
    "outerDiameterMm": 73.8074,
    "closePoint": -1,
    "sheetEnd": 73.1363,
    "sheetLength": 73.1363,
    "hasCore": true,
    "shape": "square",
    "coreRadius": 2.1499,
    "coreFold": 6,
    "patchCount": 2,
    "materialFractions": {
      "core": 0.25,
      "patch:ricePink": 0.0799,
      "patch:salmon": 0.0104,
      "spread": 0.6597
    },
    "probes": [
      "0.25|1|0=core",
      "0.25|1|6=core",
      "0.25|1|12=core",
      "0.25|1|18=core",
      "0.25|5|0=spread",
      "0.25|5|6=spread",
      "0.25|5|12=spread",
      "0.25|5|18=spread",
      "0.25|9|0=patch:ricePink",
      "0.25|9|6=spread",
      "0.25|9|12=spread",
      "0.25|9|18=spread",
      "0.5|1|0=core",
      "0.5|1|6=core",
      "0.5|1|12=core",
      "0.5|1|18=core",
      "0.5|5|0=spread",
      "0.5|5|6=spread",
      "0.5|5|12=spread",
      "0.5|5|18=spread",
      "0.5|9|0=patch:ricePink",
      "0.5|9|6=spread",
      "0.5|9|12=spread",
      "0.5|9|18=spread",
      "0.75|1|0=core",
      "0.75|1|6=core",
      "0.75|1|12=core",
      "0.75|1|18=core",
      "0.75|5|0=spread",
      "0.75|5|6=spread",
      "0.75|5|12=spread",
      "0.75|5|18=spread",
      "0.75|9|0=patch:ricePink",
      "0.75|9|6=spread",
      "0.75|9|12=spread",
      "0.75|9|18=spread"
    ],
    "map": {
      "counts": {
        "0": 1024,
        "1": 1915,
        "2": 27,
        "3": 32,
        "11": 138
      },
      "probe": "0,1,1,1,1,0,1,1,1,1,0"
    },
    "selfSimilarity": 1
  },
  "F05-hand-variation": {
    "turns": 1.2771,
    "outerDiameterMm": 66.4653,
    "closePoint": -1,
    "sheetEnd": 42,
    "sheetLength": 42,
    "hasCore": true,
    "shape": "round",
    "coreRadius": 2.3618,
    "coreFold": 6,
    "patchCount": 3,
    "materialFractions": {
      "core": 0.3333,
      "out": 0.0729,
      "patch:avocado": 0.0174,
      "patch:salmon": 0.0278,
      "patch:shrimp": 0.0035,
      "spread": 0.5451
    },
    "probes": [
      "0.25|1|0=core",
      "0.25|1|6=core",
      "0.25|1|12=core",
      "0.25|1|18=core",
      "0.25|5|0=spread",
      "0.25|5|6=patch:salmon",
      "0.25|5|12=patch:avocado",
      "0.25|5|18=spread",
      "0.25|9|0=spread",
      "0.25|9|6=spread",
      "0.25|9|12=spread",
      "0.25|9|18=spread",
      "0.5|1|0=core",
      "0.5|1|6=core",
      "0.5|1|12=core",
      "0.5|1|18=core",
      "0.5|5|0=spread",
      "0.5|5|6=patch:salmon",
      "0.5|5|12=patch:avocado",
      "0.5|5|18=spread",
      "0.5|9|0=spread",
      "0.5|9|6=spread",
      "0.5|9|12=spread",
      "0.5|9|18=spread",
      "0.75|1|0=core",
      "0.75|1|6=core",
      "0.75|1|12=core",
      "0.75|1|18=core",
      "0.75|5|0=spread",
      "0.75|5|6=patch:salmon",
      "0.75|5|12=patch:avocado",
      "0.75|5|18=patch:shrimp",
      "0.75|9|0=spread",
      "0.75|9|6=spread",
      "0.75|9|12=spread",
      "0.75|9|18=spread"
    ],
    "map": {
      "counts": {
        "0": 1202,
        "1": 1833,
        "2": 15,
        "3": 56,
        "6": 30
      },
      "probe": "0,1,1,1,1,0,1,1,1,0,0"
    },
    "selfSimilarity": 1
  },
  "F06-rotated-patch": {
    "turns": 1.3868,
    "outerDiameterMm": 60.4685,
    "closePoint": -1,
    "sheetEnd": 42,
    "sheetLength": 42,
    "hasCore": true,
    "shape": "round",
    "coreRadius": 2.1499,
    "coreFold": 6,
    "patchCount": 2,
    "materialFractions": {
      "core": 0.3333,
      "out": 0.0613,
      "patch:cucumber": 0.0336,
      "patch:tamago": 0.0301,
      "spread": 0.5394,
      "wrap": 0.0023
    },
    "probes": [
      "0.25|1|0=core",
      "0.25|1|6=core",
      "0.25|1|12=core",
      "0.25|1|18=core",
      "0.25|5|0=spread",
      "0.25|5|6=spread",
      "0.25|5|12=spread",
      "0.25|5|18=spread",
      "0.25|9|0=spread",
      "0.25|9|6=spread",
      "0.25|9|12=spread",
      "0.25|9|18=spread",
      "0.5|1|0=core",
      "0.5|1|6=core",
      "0.5|1|12=core",
      "0.5|1|18=core",
      "0.5|5|0=spread",
      "0.5|5|6=spread",
      "0.5|5|12=spread",
      "0.5|5|18=spread",
      "0.5|9|0=spread",
      "0.5|9|6=spread",
      "0.5|9|12=patch:cucumber",
      "0.5|9|18=spread",
      "0.75|1|0=core",
      "0.75|1|6=core",
      "0.75|1|12=core",
      "0.75|1|18=core",
      "0.75|5|0=spread",
      "0.75|5|6=spread",
      "0.75|5|12=spread",
      "0.75|5|18=spread",
      "0.75|9|0=spread",
      "0.75|9|6=spread",
      "0.75|9|12=spread",
      "0.75|9|18=spread"
    ],
    "map": {
      "counts": {
        "0": 1086,
        "1": 1801,
        "2": 21,
        "4": 164,
        "5": 64
      },
      "probe": "0,1,1,1,1,1,1,1,1,1,0"
    },
    "selfSimilarity": 1
  },
  "F07-edge-overload": {
    "turns": 0.9889,
    "outerDiameterMm": 35.83,
    "closePoint": -1,
    "sheetEnd": 21,
    "sheetLength": 21,
    "hasCore": true,
    "shape": "round",
    "coreRadius": 2.0684,
    "coreFold": 4,
    "patchCount": 3,
    "materialFractions": {
      "core": 0.3403,
      "out": 0.0313,
      "patch:avocado": 0.0694,
      "patch:cucumber": 0.1076,
      "patch:salmon": 0.066,
      "spread": 0.3854
    },
    "probes": [
      "0.25|1|0=patch:cucumber",
      "0.25|1|6=core",
      "0.25|1|12=core",
      "0.25|1|18=patch:avocado",
      "0.25|5|0=patch:cucumber",
      "0.25|5|6=patch:salmon",
      "0.25|5|12=core",
      "0.25|5|18=core",
      "0.25|9|0=spread",
      "0.25|9|6=spread",
      "0.25|9|12=spread",
      "0.25|9|18=spread",
      "0.5|1|0=patch:cucumber",
      "0.5|1|6=core",
      "0.5|1|12=core",
      "0.5|1|18=patch:avocado",
      "0.5|5|0=patch:cucumber",
      "0.5|5|6=patch:salmon",
      "0.5|5|12=core",
      "0.5|5|18=core",
      "0.5|9|0=spread",
      "0.5|9|6=spread",
      "0.5|9|12=spread",
      "0.5|9|18=spread",
      "0.75|1|0=patch:cucumber",
      "0.75|1|6=core",
      "0.75|1|12=core",
      "0.75|1|18=patch:avocado",
      "0.75|5|0=patch:cucumber",
      "0.75|5|6=patch:salmon",
      "0.75|5|12=core",
      "0.75|5|18=core",
      "0.75|9|0=spread",
      "0.75|9|6=spread",
      "0.75|9|12=spread",
      "0.75|9|18=spread"
    ],
    "map": {
      "counts": {
        "0": 975,
        "1": 1821,
        "2": 25,
        "3": 137,
        "4": 88,
        "6": 90
      },
      "probe": "0,1,1,1,6,0,1,1,1,1,0"
    },
    "selfSimilarity": 1
  },
  "__pairs": {
    "F02~F05 рука": 0.4821,
    "F02~сдвиг": 0.4086,
    "F04~форма": 0.9916
  }
};
