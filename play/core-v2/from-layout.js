// Раскладка игрока → RecipeV2. Чистая функция: каталог приходит АРГУМЕНТОМ.
//
// Правило ядра — не импортировать play/model/** — соблюдено буквально: здесь нет
// ни одного импорта из модели. Классическая сторона собирает данные (S, ING, BASES)
// и передаёт их сюда, а ядро остаётся не знающим про игру. Побочная выгода: функция
// накрывается node:test, чего с классическим глобальным скриптом не вышло бы.
//
// Отказ честный и поимённый. V2 умеет не всё, что умеет каталог, и молча
// приближать — запрещено (см. validate.js): огурец-сектор и брусок ядро считает,
// а пасту, присыпку и лист — нет, и прямоугольником их подменять нельзя.

import { FUTOMAKI, HOSOMAKI, U_MM, WINDING } from './units.js';

/** Классы нарезки, которые срез V2 действительно моделирует. */
export const SUPPORTED_CUTS = Object.freeze(['брусок', 'сектор']);

/** Базы, для которых у V2 есть снимок в миллиметрах. */
export const SUPPORTED_BASES = Object.freeze({ hoso: HOSOMAKI, futo: FUTOMAKI });

function diagnostic(code, message, context) {
  return { code, message, context };
}

function refuse(status, code, message, context) {
  return { status, diagnostics: [diagnostic(code, message, context)] };
}

/**
 * @param {object} input
 * @param {string} input.baseKey   ключ базы каталога: 'hoso' | 'futo' | …
 * @param {object} input.base      BASES[baseKey] — нужны sheetCm и Wv
 * @param {Array}  input.patches   S.lists[baseKey]: { kind, u, v, wU?, hU?, dv?, rot?, noriWrap? }
 * @param {object} input.ing       ING — паспорт каждого вида
 * @param {*}      [input.wrap]    S.wrap: null = обёртка базы по умолчанию
 * @param {object} [input.hand]    S.hand — семь чисел классической руки
 * @param {object} [input.handNeutral] HAND_NEUTRAL из util.js: эталон для сравнения
 * @param {string} [input.shape]   S.shape: round | square | triangle
 * @param {number} [input.turns]   S.turns: null = витки выводятся из длины листа
 * @returns {{status:'valid', recipe:object} | {status:'unsupported'|'invalid', diagnostics:Array}}
 */
export function recipeFromLayout(input) {
  const { baseKey, base, patches, ing } = input || {};

  const snapshot = SUPPORTED_BASES[baseKey];
  if (!snapshot) {
    return refuse('unsupported', 'base_unsupported', 'V2 alpha знает только хосомаки и футомаки', {
      requestedFeature: String(baseKey),
      supported: Object.keys(SUPPORTED_BASES),
    });
  }
  if (!base || typeof base.sheetCm !== 'number' || typeof base.Wv !== 'number') {
    return refuse('invalid', 'base_shape', 'у базы нет sheetCm или Wv', { baseKey: String(baseKey) });
  }

  // Обёртка: null означает «по умолчанию для базы», то есть нори. Любой явный
  // выбор — это ещё не смоделированный материал, а не синоним нори.
  if (input.wrap != null) {
    return refuse('unsupported', 'wrap_unsupported', 'V2 alpha заворачивает только в нори', {
      requestedFeature: String(input.wrap),
    });
  }

  // Форма прессовки: кольцо V2 круглое. square и triangle — не приближение, а другая модель.
  if (input.shape != null && input.shape !== 'round') {
    return refuse('unsupported', 'shape_unsupported', 'V2 alpha прессует только круглый ролл', {
      requestedFeature: String(input.shape),
    });
  }

  // Число витков V2 выводит из длины листа само (#141). Заданное вручную — чужое условие.
  if (input.turns != null) {
    return refuse('unsupported', 'turns_override', 'V2 выводит витки из длины листа, а не принимает', {
      observedTurns: Number(input.turns),
    });
  }

  // Рука у классической стороны — это семь чисел (air, wobble, phase, press, v, cv, hold),
  // а не {mode, seed} из V2. Мост между ними один: NeutralHand у V2 = рука, точно равная
  // эталону каталога. Эталон приходит аргументом, чтобы ядро не знало про util.js.
  const hand = input.hand;
  const neutral = input.handNeutral;
  if (hand && neutral) {
    const off = Object.keys(neutral).filter((k) => hand[k] !== neutral[k]);
    if (off.length) {
      return refuse('invalid', 'non_neutral_hand', 'V2 alpha принимает только нейтральную руку', {
        observedHandMode: 'recorded',
        deviatingFields: off.map((k) => ({ field: k, observed: hand[k], neutral: neutral[k] })),
      });
    }
  } else if (hand && (hand.mode !== 'neutral' || hand.seed !== 0)) {
    return refuse('invalid', 'non_neutral_hand', 'V2 alpha принимает только NeutralHand', {
      observedHandMode: String(hand.mode),
    });
  }

  const sheet = {
    lengthMm: base.sheetCm * 10,
    widthMm: base.Wv * U_MM,
  };

  const list = Array.isArray(patches) ? patches : [];
  const out = [];
  for (let i = 0; i < list.length; i++) {
    const p = list[i];
    if (!p || typeof p !== 'object') {
      return refuse('invalid', 'patch_shape', 'элемент раскладки не объект', { index: i });
    }
    const d = ing && ing[p.kind];
    if (!d) {
      return refuse('invalid', 'patch_unknown_kind', 'вида нет в каталоге', {
        index: i,
        observedKind: String(p.kind),
      });
    }
    if (d.paint) {
      return refuse('unsupported', 'patch_is_paint', 'краска риса — не начинка ядра', {
        requestedFeature: String(p.kind),
      });
    }
    if (!SUPPORTED_CUTS.includes(d.cut)) {
      return refuse('unsupported', 'patch_cut_unsupported', 'срез V2 не моделирует этот класс нарезки', {
        patchKind: String(p.kind),
        observedCut: String(d.cut),
        supported: SUPPORTED_CUTS.slice(),
      });
    }
    // Профиль вдоль оси (#10) у V2 не описан: срез один, центральный, и конус
    // от него неотличим. Приближать молча нельзя — отказываем поимённо.
    if (d.axial) {
      return refuse('unsupported', 'patch_axial_profile', 'профиль вдоль оси в V2 не описан', {
        patchKind: String(p.kind),
        observedAxial: String(d.axial),
      });
    }
    if (d.wave) {
      return refuse('unsupported', 'patch_wave', 'волна вдоль оси в V2 не описана', {
        patchKind: String(p.kind),
      });
    }
    if (p.rot) {
      return refuse('unsupported', 'patch_rotated', 'поворот к оси ролла в V2 не описан', {
        patchKind: String(p.kind),
        observedRotationDeg: Number(p.rot),
      });
    }
    if (p.noriWrap) {
      return refuse('unsupported', 'patch_nori_wrap', 'начинка в нори внутри ядра в V2 не описана', {
        patchKind: String(p.kind),
      });
    }

    const wU = p.wU ?? d.wU;
    const hU = p.hU ?? d.hU;
    const dv = p.dv ?? d.dv;
    if (![p.u, p.v, wU, hU, dv].every((n) => typeof n === 'number' && Number.isFinite(n))) {
      return refuse('invalid', 'patch_shape', 'нечисловое поле в раскладке', {
        index: i,
        patchKind: String(p.kind),
        observed: { u: p.u, v: p.v, wU, hU, dv },
      });
    }

    out.push({
      // Индекс делает одинаковые виды различимыми — без этого проверка
      // same-material overlap не смогла бы назвать, какие два куска столкнулись.
      id: `${p.kind}-${i}`,
      materialId: p.kind,
      cut: d.cut,
      uMm: p.u * sheet.lengthMm,
      vMm: p.v * sheet.widthMm,
      widthMm: wU * U_MM,
      heightMm: hU * U_MM,
      lengthMm: dv * sheet.widthMm,
      placement: 'embedded',
    });
  }

  return {
    status: 'valid',
    recipe: {
      version: 2,
      baseId: snapshot.baseId,
      sheet,
      wrap: { materialId: snapshot.wrapMaterialId },
      rice: { profileId: snapshot.riceProfileId },
      windDirection: 'fromUZero',
      winding: WINDING.ring,
      patches: out,
      hand: { mode: 'neutral', seed: 0 },
    },
  };
}
