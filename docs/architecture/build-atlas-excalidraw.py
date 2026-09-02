#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Собрать rollery-atlas.excalidraw — ОДНУ редактируемую карту для обсуждения.

Почему генератор, а не файл руками. Excalidraw-файл — это JSON на несколько
тысяч строк с id, seed и привязками стрелок; править его текстом невозможно, а
перерисовывать мышью после каждой правки кода — значит гарантированно разойтись
с кодом. Здесь в git лежит ИСТОЧНИК (этот файл), а .excalidraw — результат,
который пересобирается одной командой:

    python3 docs/architecture/build-atlas-excalidraw.py

Что на карте и чем она отличается от четырёх листов D2. Листы отвечают каждый
на своё решение и потому нарочно неполны. Карта — наоборот, одна поверхность
для разговора: слева что есть, посередине что красное, справа куда едем, и
зелёные пунктиры показывают, какой шаг какой узел гасит. Её можно таскать
мышью, дописывать и черкать — для этого она и нужна.

Открывается: excalidraw.com → Open → выбрать файл. Или VS Code с расширением
«Excalidraw». Данные никуда не уходят, файл локальный.
"""

import json
import pathlib
import random

OUT = pathlib.Path(__file__).with_name("rollery-atlas.excalidraw")

rnd = random.Random(20260901)          # детерминированно: пересборка не даёт шумного диффа

# ── палитра ────────────────────────────────────────────────────────────────
# Та же, что в _style.d2, чтобы карта и листы читались как одно.
INK = "#2f2c25"
GREY = "#6f6959"
RED = "#c0392b"
RED_BG = "#fdecea"
GREEN = "#2e7d5b"
GREEN_BG = "#edf6f1"
GOLD = "#8a6d1f"
GOLD_BG = "#fbf4e0"
PAPER = "#ffffff"
SAND = "#faf9f5"
FAINT = "#a8a294"

elements = []
_n = [0]


def _id(prefix):
    _n[0] += 1
    return f"{prefix}{_n[0]:03d}"


def _base(el_id, kind, x, y, w, h, stroke, bg, **kw):
    el = {
        "id": el_id,
        "type": kind,
        "x": x, "y": y, "width": w, "height": h,
        "angle": 0,
        "strokeColor": stroke,
        "backgroundColor": bg,
        "fillStyle": "solid",
        "strokeWidth": 2,
        "strokeStyle": "solid",
        "roughness": 1,
        "opacity": 100,
        "groupIds": [],
        "frameId": None,
        "roundness": {"type": 3},
        "seed": rnd.randint(1, 2 ** 31),
        "version": 1,
        "versionNonce": rnd.randint(1, 2 ** 31),
        "isDeleted": False,
        "boundElements": [],
        "updated": 1,
        "link": None,
        "locked": False,
    }
    el.update(kw)
    return el


def box(x, y, w, h, text, stroke=GREY, bg=PAPER, size=14, dashed=False, bold_first=True):
    """Прямоугольник с текстом ВНУТРИ (containerId) — текст ездит вместе с боксом."""
    bid = _id("b")
    tid = _id("t")
    b = _base(bid, "rectangle", x, y, w, h, stroke, bg)
    if dashed:
        b["strokeStyle"] = "dashed"
    b["boundElements"] = [{"id": tid, "type": "text"}]
    t = _base(tid, "text", x + 10, y + 10, w - 20, h - 20, stroke, "transparent",
              roundness=None,
              text=text, originalText=text,
              fontSize=size, fontFamily=2,
              textAlign="left", verticalAlign="top",
              containerId=bid, lineHeight=1.3, autoResize=False)
    elements.append(b)
    elements.append(t)
    return bid


def label(x, y, text, size=20, color=INK, width=None, align="left"):
    tid = _id("t")
    w = width or max(220, int(len(max(text.split("\n"), key=len)) * size * 0.58))
    h = int(len(text.split("\n")) * size * 1.35) + 6
    elements.append(_base(tid, "text", x, y, w, h, color, "transparent",
                          roundness=None,
                          text=text, originalText=text,
                          fontSize=size, fontFamily=2,
                          textAlign=align, verticalAlign="top",
                          containerId=None, lineHeight=1.3, autoResize=True))
    return tid


def _bind(el_id, arrow_id):
    for e in elements:
        if e["id"] == el_id:
            e["boundElements"] = list(e.get("boundElements") or []) + [
                {"id": arrow_id, "type": "arrow"}]
            return
    raise KeyError(el_id)


def _rect(el_id):
    for e in elements:
        if e["id"] == el_id:
            return e
    raise KeyError(el_id)


def arrow(src, dst, color=GREY, dashed=False, text=None, width=2):
    """Стрелка, ПРИВЯЗАННАЯ к боксам: тянешь бокс — стрелка едет следом."""
    aid = _id("a")
    a_r, b_r = _rect(src), _rect(dst)
    x1 = a_r["x"] + a_r["width"] / 2
    y1 = a_r["y"] + a_r["height"] / 2
    x2 = b_r["x"] + b_r["width"] / 2
    y2 = b_r["y"] + b_r["height"] / 2
    a = _base(aid, "arrow", x1, y1, abs(x2 - x1), abs(y2 - y1), color, "transparent",
              roundness={"type": 2},
              points=[[0, 0], [x2 - x1, y2 - y1]],
              lastCommittedPoint=None,
              startBinding={"elementId": src, "focus": 0.0, "gap": 6},
              endBinding={"elementId": dst, "focus": 0.0, "gap": 6},
              startArrowhead=None, endArrowhead="arrow",
              elbowed=False)
    a["strokeWidth"] = width
    if dashed:
        a["strokeStyle"] = "dashed"
    elements.append(a)
    _bind(src, aid)
    _bind(dst, aid)
    if text:
        tid = _id("t")
        a["boundElements"] = [{"id": tid, "type": "text"}]
        elements.append(_base(tid, "text", x1, y1, 120, 20, color, "transparent",
                              roundness=None,
                              text=text, originalText=text,
                              fontSize=12, fontFamily=2,
                              textAlign="center", verticalAlign="middle",
                              containerId=aid, lineHeight=1.25, autoResize=True))
    return aid


# ═══════════════════════════════════════════════════════════════════════════
#  ШАПКА
# ═══════════════════════════════════════════════════════════════════════════
label(80, -170, "Ролльня · архитектурный атлас — карта для обсуждения", size=34)
label(80, -120,
      "Слева — что есть. Посередине — что мешает переезду. Справа — куда едем.\n"
      "Зелёный пунктир справа налево читается так: «этот шаг гасит этот узел».\n"
      "Точные цифры, файлы и строки — на четырёх листах D2 рядом (svg/01…04).",
      size=16, color=GREY)

# ═══════════════════════════════════════════════════════════════════════════
#  КОЛОНКА 1 — ЧТО ЕСТЬ
# ═══════════════════════════════════════════════════════════════════════════
C1, W1 = 80, 340
label(C1, -30, "① ЧТО ЕСТЬ", size=24)

zones = [
    ("catalog · что бывает на свете\nutil · catalog · canon · inverse\nBASES · ING · CANON · R0 · U_MM", SAND),
    ("state · что выбрал игрок\nstate.js — S · patches() · B()\nистория · load() · save()", SAND),
    ("geometry · что из этого выйдет\nbuildModel → g → restack →\ncomputeCore → wind → matAt\n2077 строк · ЯДРО ПРОДУКТА", SAND),
    ("domain/roll.js · шов наружу\nevaluateRoll · sliceAt · compareRolls\nбоевого потребителя нет (#72)", SAND),
    ("render · как выглядит\nslice · sheet · screens\nCanvas 2D + кеши картинок", SAND),
    ("ui · ввод и раскладка экрана\nlayout (L) · actions · controls · album\nmeasureHand — почерк из жеста", SAND),
    ("modes/puzzle · игровая оболочка\nLEVELS · genTarget · puzzleEvaluate", SAND),
    ("storage · переживает перезагрузку\nlocalStorage · адрес страницы (#p=…)", SAND),
    ("сторож · чем доказываем\nchecks.js ?check · practice · baseline\n22 известных · 0 провалов", GOLD_BG),
    ("sim · лаборатория Python\nв рантайме игры ЕЁ НЕТ\nчисла едут в каталог руками", "#f2f0e9"),
]
z_ids = []
y = 20
for txt, bg in zones:
    h = 104 if txt.count("\n") < 3 else 124
    stroke = GOLD if bg == GOLD_BG else GREY
    zid = box(C1, y, W1, h, txt, stroke=stroke, bg=bg,
              dashed=(bg == "#f2f0e9"))
    z_ids.append(zid)
    y += h + 26

Z_CATALOG, Z_STATE, Z_GEO, Z_ROLL, Z_RENDER, Z_UI, Z_MODES, Z_STORE, Z_CHECKS, Z_SIM = z_ids

# здоровые связи внутри колонки — тонкие и серые, они тут фон
for a, b in [(Z_CATALOG, Z_STATE), (Z_STATE, Z_GEO), (Z_GEO, Z_RENDER),
             (Z_UI, Z_RENDER), (Z_MODES, Z_STORE)]:
    arrow(a, b, color=FAINT, width=1)

# ① порядок скриптов — не стрелка, а плашка под всей колонкой:
#    он отравляет не одну связь, а само понятие «зависимость».
N1 = box(C1, y + 10, W1, 236,
         "① classic scripts: порядок вместо зависимостей\n\n"
         "15 тегов <script> без type=\"module\".\n"
         "Кто от кого зависит — нигде не записано:\n"
         "это сам ПОРЯДОК СТРОК в play/index.html.\n"
         "Плюс ручной ?v=165 у каждой строки.\n"
         "Трижды за вечер дал ошибку (STATE 01.09).",
         stroke=RED, bg=RED_BG)

# ═══════════════════════════════════════════════════════════════════════════
#  КОЛОНКА 2 — ЧТО КРАСНОЕ
# ═══════════════════════════════════════════════════════════════════════════
C2, W2 = 600, 380
label(C2, -30, "② ЧТО КРАСНОЕ", size=24, color=RED)

n2 = box(C2, 20, W2, 168,
         "② S — один объект сессии на всю игру\n\n"
         "state.js:11. Режим, база, обёртка, списки,\n"
         "почерк, пазл, альбом — в одном литерале.\n"
         "151 запись и 161 чтение из 18 файлов.\n"
         "Ни один файл не только пишет и не только\n"
         "читает: границы нет вообще никакой.",
         stroke=RED, bg=RED_BG)

n3 = box(C2, 198, W2, 152,
         "③ B() — база с кешем на два поля\n\n"
         "state.js:133. Ключ кеша — только\n"
         "S.base + '|' + wrapKey. 66 вызовов из 12 файлов.\n"
         "Та же болезнь этажом выше — #148.",
         stroke=RED, bg=RED_BG)

n4 = box(C2, 376, W2, 152,
         "④ L — раскладка экрана внутри домена\n\n"
         "domain/roll.js:259 deriveSheetLayout\n"
         "читает L.sheet, L.handle, L.mode, L.chips.\n"
         "ИНВЕРСИЯ: домен зависит от рендера.",
         stroke=RED, bg=RED_BG)

n5 = box(C2, 554, W2, 168,
         "⑤ touchModel() — рендер владеет всем\n\n"
         "Объявлена в render/slice.js:374 и одной\n"
         "строкой делает три чужих дела:\n"
         "ключ модели · save() · dirty.\n"
         "43 упоминания в 7 файлах, две трети — сторож.",
         stroke=RED, bg=RED_BG)

n6 = box(C2, 748, W2, 188,
         "⑥ временная подмена S — 6 редакций\n\n"
         "album.js withRecipe · roll.js\n"
         "withRollRecipeState · ~15 keep-блоков\n"
         "в стороже · targetModel() в пазле.\n"
         "Прямо запрещено контрактом §11 commit 4.\n"
         "Отсюда #86 и невозможность воркера.",
         stroke=RED, bg=RED_BG)

# красные стрелки: узел → зона, которую он отравляет
arrow(n2, Z_GEO, color=RED, text="12 — модель читает сессию", width=3)
arrow(n3, Z_GEO, color=RED, text="14 вызовов", width=3)
arrow(n4, Z_ROLL, color=RED, text="домен → рендер", width=3)
arrow(n5, Z_STORE, color=RED, text="рендер пишет сессию", width=3)
arrow(n6, Z_STATE, color=RED, text="мутируют живой S", width=3)
arrow(n2, Z_UI, color=RED, text="50 прямых записей", width=3)

# ═══════════════════════════════════════════════════════════════════════════
#  КОЛОНКА 3 — КУДА ЕДЕМ
# ═══════════════════════════════════════════════════════════════════════════
C3, W3 = 1120, 420
label(C3, -30, "③ КУДА ЕДЕМ", size=24, color=GREEN)

s0 = box(C3, 20, W3, 128,
         "0 · Сторож из терминала — СДЕЛАНО 01.09  #147\n\n"
         "node tools/check.js — весь checks.js headless.\n"
         "Правок игрового кода ноль.\n"
         "Сам ничего не чинил и разблокировал всё.",
         stroke=GOLD, bg=GOLD_BG)

s1 = box(C3, 174, W3, 128,
         "1 · ES-модули  #72\n\n"
         "import/export вместо порядка строк.\n"
         "Поведение не меняется вовсе.\n"
         "⚠ модули НЕ заменяют runtime-тест.",
         stroke=GREEN, bg=GREEN_BG)

s2 = box(C3, 328, W3, 166,
         "2 · ModelInput — вход модели назван\n\n"
         "g (паспорт, geometry.js:1730) уже собран\n"
         "внутри buildModel. Поднять его в АРГУМЕНТ:\n"
         "buildModel(input, list). Ключ кеша = хеш input,\n"
         "а не перечисление полей руками → #148 закрыт.\n"
         "Доказывается слепком baseline-data.js.",
         stroke=GREEN, bg=GREEN_BG)

s3 = box(C3, 520, W3, 166,
         "3 · Чистый домен — три удаления\n\n"
         "· deriveSheetLayout удалить (потребителя нет)\n"
         "· withRecipe / withRollRecipeState / keep-блоки\n"
         "  → обычный вызов с другим input\n"
         "· targetModel() перестаёт считать на живой сессии\n"
         "Открывает воркер и обратный поиск (#80).",
         stroke=GREEN, bg=GREEN_BG)

s4 = box(C3, 712, W3, 184,
         "4 · Команды сессии  (контракт §8)\n\n"
         "app/session.js. UI не пишет в S.lists, а создаёт\n"
         "команды: piece/add · piece/stroke · piece/remove\n"
         "history/undo · roll/build · slice/cut.\n"
         "Переносить ПО ОДНОЙ, после каждой — полный прогон.\n"
         "⚠ «command bus не нужен» из разбора ревью — это\n"
         "было про #150 (три строки истории), не про этот шаг.",
         stroke=GREEN, bg=GREEN_BG)

s5 = box(C3, 922, W3, 166,
         "5 · Снимки  (контракт §11 commit 7)\n\n"
         "Рендер получает snapshot и перестаёт читать S.\n"
         "touchModel распадается: ключ → в модель,\n"
         "save() → в сессию, dirty остаётся рендеру.\n\n"
         "РАДИ ЧЕГО ВСЁ: шкуру можно менять,\n"
         "не трогая математику.",
         stroke=GREEN, bg=GREEN_BG)

for a, b in [(s0, s1), (s1, s2), (s2, s3), (s3, s4), (s4, s5)]:
    arrow(a, b, color=GREEN, width=3)

# зелёный пунктир справа налево: какой шаг какой узел гасит
arrow(s1, N1, color=GREEN, dashed=True, text="гасит ①")
arrow(s2, n2, color=GREEN, dashed=True, text="гасит чтение модели")
arrow(s2, n3, color=GREEN, dashed=True, text="гасит ③ и #148")
arrow(s3, n4, color=GREEN, dashed=True, text="гасит ④")
arrow(s3, n6, color=GREEN, dashed=True, text="гасит ⑥")
arrow(s4, n2, color=GREEN, dashed=True, text="гасит запись из UI")
arrow(s5, n5, color=GREEN, dashed=True, text="гасит ⑤")

# ═══════════════════════════════════════════════════════════════════════════
#  ЧТО ИДЁТ РЯДОМ И НЕ ВХОДИТ В ПЯТЬ ШАГОВ
# ═══════════════════════════════════════════════════════════════════════════
box(C3, 1150, W3, 250,
    "РЯДОМ, но НЕ в этих пяти шагах\n\n"
    "Пять шагов слева не меняют ни одного числа.\n"
    "Эти — меняют модель, и путать их нельзя:\n\n"
    "#146 ЗАКРЫТ 01.09 — намотка отдаёт восемь\n"
    "        вопросов вместо массивов. Это и был\n"
    "        настоящий блокер, ревью его не назвало\n"
    "#142 уже строится: база узумаки, winding=spiral,\n"
    "        ядра нет, хвост с обжимом общий с кольцом\n"
    "#74  роль как свойство укладки → форма каталога\n"
    "#3, #124 урамаки — без него это не конструктор суши",
    stroke=GREY, bg=SAND)

# ═══════════════════════════════════════════════════════════════════════════
#  ЛЕГЕНДА И ПУСТОЕ МЕСТО ПОД РЕШЕНИЯ
# ═══════════════════════════════════════════════════════════════════════════
box(C1, y + 280, W1 + 240, 168,
    "КАК ЧИТАТЬ\n\n"
    "красный  — пока связь красная, шаг переезда сделать нельзя\n"
    "зелёный  — куда едем; сплошной — порядок, пунктир — что гасит\n"
    "золотой  — сторож: он и есть определение «не сломали»\n"
    "пунктир серым — этого в рантайме игры нет",
    stroke=GREY, bg=PAPER, size=13)

box(C1, y + 480, W1 + 240, 232,
    "МЕСТО ПОД РЕШЕНИЯ  ← сюда писать\n\n"
    "Первый вопрос снят сам: #146 и #147 закрыты 01.09,\n"
    "и предусловия у переезда больше нет — шаг 1 можно\n"
    "резать первым, не дожидаясь кольца.\n\n"
    "Остался один, и он не мой:\n\n"
    "#74 (роль как свойство укладки) — до шага 2 или после?\n"
    "Он меняет форму каталога, а шаг 2 фиксирует вход модели.\n"
    "Сделать наоборот — переписывать дважды.",
    stroke=GOLD, bg=GOLD_BG, size=13)

# ═══════════════════════════════════════════════════════════════════════════
doc = {
    "type": "excalidraw",
    "version": 2,
    "source": "https://github.com/newYurk/rollery — docs/architecture/build-atlas-excalidraw.py",
    "elements": elements,
    "appState": {
        "gridSize": None,
        "gridStep": 5,
        "gridModeEnabled": False,
        "viewBackgroundColor": "#fdfcf8",
    },
    "files": {},
}

OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{OUT.name}: {len(elements)} элементов, {OUT.stat().st_size // 1024} КБ")
