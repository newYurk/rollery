'use strict';
// СЛЕПОК LEGACY-ПОВЕДЕНИЯ: что геометрия считает на базовой ревизии 9e9ce2a.
//
// СНЯТ ПРОГОНОМ, А НЕ НАПИСАН РУКАМИ: captureLegacyBaseline() (play/test/legacy/baseline.js)
// на ветке refactor/geometry-facade-baseline, 31.08.2026. Это характеризационный эталон —
// он описывает поведение КАК ЕСТЬ, включая то, что мы считаем дефектами.
//
// ⚠ ПЕРЕСНИМАТЬ ТОЛЬКО ОСОЗНАННО. Правило то же, что у REF в начале play/checks.js: если
// проверка упала — сперва понять, что изменилось в модели, и лишь потом трогать числа,
// вместе с коммитом, где это сказано. Молча обновлённый слепок превращает регрессию в
// самоисполняющееся пророчество.
//
// Что стоит знать про отдельные записи:
//   F03 — обёртка «блин» (2 мм) против нори (0,1 мм): ⌀ 62,4 против 58,7 у F02-подобной
//         раскладки, то есть обёртка действительно входит в шаг витка. Отдельно: альбом
//         (albumSave) поле wrap НЕ сохраняет — запись с блином вернётся как нори.
//   F07 — ролл на грани: 1,0056 витка. Это известный случай урамаки (issue #3), и слепок
//         фиксирует его как есть, а не как хотелось бы.
//
// ПЕРЕСНЯТ 31.08.2026 (дважды). Второй раз — при переезде materialMap/similarity за facade:
// в инварианты добавлены `map` (счётчики классов на карте среза + выборка) и `selfSimilarity`.
// СНЯТ ДО ПЕРЕЕЗДА, на прежней реализации из render/slice.js — в этом весь смысл: после
// переезда проверка сверяет новое поведение с числами, добытыми у старого кода, а не у
// самой себя. Числа намотки не изменились ни в одном fixture.
//
// Первый раз 31.08.2026 — в инварианты добавлено поле shape. Причина названа честно: ревью
// PR #100 показало, что форма прессовки не входила ни в один инвариант, и F04 «квадратная
// прессовка» на деле её не проверял. Числа намотки при этом не изменились ни в одном
// fixture — сравни с предыдущей ревизией файла: добавилась ровно одна строка на запись.

const ROLL_BASELINE = {
  "F01-hosomaki-basic": {
    "turns": 1.2917,
    "outerDiameterMm": 31.1927,
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
      "patch:cucumber": 0.0486,
      "spread": 0.5868,
      "wrap": 0.0313
    },
    "probes": [
      "0.25|1|0=core",
      "0.25|1|6=core",
      "0.25|1|12=core",
      "0.25|1|18=core",
      "0.25|5|0=spread",
      "0.25|5|6=spread",
      "0.25|5|12=patch:cucumber",
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
      "0.5|5|12=patch:cucumber",
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
      "0.75|5|12=patch:cucumber",
      "0.75|5|18=spread",
      "0.75|9|0=spread",
      "0.75|9|6=spread",
      "0.75|9|12=patch:cucumber",
      "0.75|9|18=spread"
    ],
    "map": {
      "counts": {
        "0": 972,
        "1": 1946,
        "2": 36,
        "4": 182
      },
      "probe": "0002441100"
    },
    "selfSimilarity": 1
  },
  "F02-futomaki-basic": {
    "turns": 1.3743,
    "outerDiameterMm": 58.7456,
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
      "out": 0.0417,
      "patch:avocado": 0.0208,
      "patch:salmon": 0.0347,
      "patch:shrimp": 0.0104,
      "spread": 0.5486,
      "wrap": 0.0104
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
        "0": 1048,
        "1": 1960,
        "2": 14,
        "3": 76,
        "6": 38
      },
      "probe": "0000111100"
    },
    "selfSimilarity": 1
  },
  "F03-wrapper-roundtrip": {
    "turns": 1.3042,
    "outerDiameterMm": 62.4367,
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
        "1": 1706,
        "2": 324,
        "5": 96
      },
      "probe": "0000111200"
    },
    "selfSimilarity": 1
  },
  "F04-puzzle-recipe": {
    "turns": 2.1701,
    "outerDiameterMm": 73.8325,
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
        "0": 1025,
        "1": 1915,
        "2": 26,
        "3": 32,
        "11": 138
      },
      "probe": "0000111100"
    },
    "selfSimilarity": 1
  },
  "F05-hand-variation": {
    "turns": 1.2764,
    "outerDiameterMm": 66.6884,
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
      "patch:shrimp": 0.0058,
      "spread": 0.5428
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
        "0": 1214,
        "1": 1808,
        "2": 24,
        "3": 59,
        "6": 31
      },
      "probe": "0000111000"
    },
    "selfSimilarity": 1
  },
  "F06-rotated-patch": {
    "turns": 1.3896,
    "outerDiameterMm": 59.3707,
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
      "out": 0.0556,
      "patch:cucumber": 0.0278,
      "patch:tamago": 0.037,
      "spread": 0.5428,
      "wrap": 0.0035
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
      "0.25|9|0=patch:tamago",
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
      "0.5|9|0=patch:tamago",
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
      "0.75|9|0=patch:tamago",
      "0.75|9|6=spread",
      "0.75|9|12=spread",
      "0.75|9|18=spread"
    ],
    "map": {
      "counts": {
        "0": 1029,
        "1": 1902,
        "2": 13,
        "4": 114,
        "5": 78
      },
      "probe": "0000441100"
    },
    "selfSimilarity": 1
  },
  "F07-edge-overload": {
    "turns": 1.0056,
    "outerDiameterMm": 35.3177,
    "closePoint": -1,
    "sheetEnd": 21,
    "sheetLength": 21,
    "hasCore": true,
    "shape": "round",
    "coreRadius": 2.009,
    "coreFold": 4,
    "patchCount": 3,
    "materialFractions": {
      "core": 0.3299,
      "out": 0.0278,
      "patch:avocado": 0.0833,
      "patch:cucumber": 0.0868,
      "patch:salmon": 0.0833,
      "spread": 0.3889
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
        "0": 960,
        "1": 1812,
        "2": 23,
        "3": 151,
        "4": 97,
        "6": 93
      },
      "probe": "0001111100"
    },
    "selfSimilarity": 1
  }
};
