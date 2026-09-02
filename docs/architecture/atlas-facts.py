#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сторож свежести атласа: разошлись ли числа на листах с кодом.

    python3 docs/architecture/atlas-facts.py             # сверить, показать дрейф
    python3 docs/architecture/atlas-facts.py --snapshot   # записать новый слепок

ЗАЧЕМ. Атлас цитирует полсотни чисел — счётчики grep, адреса file:line, длины
файлов, статусы issues. Все они верны на ОДИН коммит и стареют молча: документ
продолжает выглядеть уверенно, когда под ним всё уехало.

01.09 это случилось за час. Пока атлас собирался, в main пришло шесть коммитов
параллельной работы, и три из них закрыли ровно то, о чём атлас говорил в будущем
времени. Документ при этом не изменился ни на символ и выглядел свежим.

Лечится не аккуратностью, а сторожем — им и является этот файл. Числа меряются
заново, сверяются со слепком, и КАЖДОЕ расхождение говорит, на каком листе его
править. Тогда «атлас разошёлся» — строчка в прогоне, а не находка владельца
глазами.

ПОЧЕМУ ИЗ GIT, А НЕ ИЗ РАБОЧЕГО ДЕРЕВА. Над «Ролльней» работает вторая сессия,
и в дереве может лежать её незаконченная правка. Числа, снятые с наполовину
сохранённого файла, не соответствуют ни одному состоянию проекта и врут дважды —
и сейчас, и в слепке. Поэтому всё читается через `git show <ref>:<путь>`, и слепок
всегда привязан к коммиту, который можно назвать вслух.

ПОЧЕМУ ЯКОРЯ, А НЕ НОМЕРА СТРОК. Сверять запомненный номер строки бессмысленно:
он съезжает от любой правки выше, и сторож кричал бы каждый день. Определения
ищутся регуляркой; сверяется, что определение ЕСТЬ, а свежий номер строки
выдаётся как подсказка для правки листа.

СТАТУСЫ ISSUES требуют gh и сети. Без них сверка не падает: раздел помечается
«не проверено», а не выдумывается.
"""

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SNAP = pathlib.Path(__file__).with_name("atlas-facts.json")

# Где на листах живёт каждый факт. Не для красоты: сторож, который говорит
# «число разошлось», но не говорит где, заставляет искать руками по шести файлам.
SHEETS = {
    "lines": "лист 1 (опись зон) · страница, шапка «код на …»",
    "числа": "лист 1 · страница, шапка · README",
    "S_reads": "лист 2 узел ②, лист 3 · страница, таблица s2",
    "S_writes": "лист 2 узел ② · страница, таблица s2",
    "B_calls": "лист 2 узел ③ · страница, таблица s2",
    "L_calls": "лист 2 узел ④",
    "touchModel": "лист 2 узел ⑤, лист 3 фаза 2 · страница, таблица s2",
    "anchors": "лист 2 и лист 3 — адреса file:line · страница, таблица s2",
    "scripts": "лист 2 узел ①, лист 4 шаг 1 · страница",
    "markers": "лист 2 «Чего здесь нет», лист 3 заметка n6, лист 4 «Работа рядом»",
    "issues": "листы 2 и 4 · страница, секции s2 и s4",
    "guard": "лист 1 (зона «сторож»), лист 4 (зона proof и шаг 0) · страница, шаг 0",
}

# Номера задач, на которые ссылается атлас. Закрылся такой, а лист говорит о нём
# в будущем времени — это и есть протухание, ради которого сторож написан.
ISSUES = [3, 57, 72, 74, 80, 86, 94, 109, 115, 121, 124, 130, 140, 142,
          146, 147, 148, 150]

# Что атлас называет по адресу file:line.
ANCHORS = [
    ("S",                   "play/state.js",          r"^const S = \{"),
    ("B",                   "play/state.js",          r"^const B = \(\) =>"),
    ("L",                   "play/ui/layout.js",      r"^const L\b"),
    ("touchModel",          "play/render/slice.js",   r"^function touchModel\("),
    ("deriveSheetLayout",   "play/domain/roll.js",    r"^function deriveSheetLayout\("),
    ("withRollRecipeState", "play/domain/roll.js",    r"^function withRollRecipeState\("),
    ("withRecipe",          "play/ui/album.js",       r"^function withRecipe\("),
    ("targetModel",         "play/modes/puzzle.js",   r"^function targetModel\("),
    ("buildModel",          "play/model/geometry.js", r"^function buildModel\("),
    ("g_passport",          "play/model/geometry.js", r"const b = B\(\), g = \{"),
]

# Утверждения атласа про устройство кода — не числа, а «это ещё так».
# Третий элемент — что именно на листах держится на этом факте.
MARKERS = [
    ("ring_leak", "play/render/slice.js", r"wd\.rin\[",
     "листы 2/3/4: топология кольца вытекла в отрисовку (#146)"),
    ("geometry_reads_S", "play/model/geometry.js", r"S\.(base|shape|turns|hand)\b",
     "ГЛАВНЫЙ ТЕЗИС: вход модели не назван"),
    ("classic_scripts", "play/index.html", r'<script src="[^"]+\.js\?v=',
     "лист 2 узел ①: classic scripts вместо модулей"),
    ("es_modules", "play/index.html", r'type="module"',
     "лист 4 шаг 1: ES-модули (появились — шаг сделан)"),
    ("state_swaps", "play/ui/album.js", r"function withRecipe\(",
     "лист 2 узел ⑥: временные подмены S"),
]


def sh(args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True)


def blob(ref, path):
    r = sh(["git", "show", f"{ref}:{path}"])
    return r.stdout if r.returncode == 0 else None


def js_files(ref):
    r = sh(["git", "ls-tree", "-r", ref, "--name-only", "--", "play"])
    return sorted(p for p in r.stdout.splitlines() if p.endswith(".js"))


def measure(ref):
    files = js_files(ref)
    texts = {p: (blob(ref, p) or "") for p in files}
    lines = {p: len(t.splitlines()) for p, t in texts.items()}

    def count(pattern):
        rx = re.compile(pattern)
        out = {}
        for p in files:
            n = sum(1 for ln in texts[p].splitlines() if rx.search(ln))
            if n:
                out[p] = n
        return out

    # Те же выражения, что записаны в шапке листа 2. Поменять здесь и не поменять
    # там — значит мерить не то, что обещает документ.
    s_hits = count(r"\bS\.")
    b_calls = count(r"\bB\(\)")
    l_calls = count(r"\bL\.")
    touch = count(r"\btouchModel\b")

    # Кто ПИШЕТ в S, а кто только читает — разница, на которой стоит весь порядок
    # резки листа 2. Присваивание опознаётся грубо, но одинаково в обе стороны.
    write_rx = re.compile(r"\bS\.\w+(?:\.\w+|\[[^\]]*\])*\s*(?:=[^=]|\+\+|--|\+=|-=)")
    s_writes, s_reads = {}, {}
    for p in files:
        w = sum(1 for ln in texts[p].splitlines() if write_rx.search(ln))
        if w:
            s_writes[p] = w
        r = s_hits.get(p, 0) - w
        if r > 0:
            s_reads[p] = r

    index = blob(ref, "play/index.html") or ""
    anchors = {}
    for name, path, pattern in ANCHORS:
        rx = re.compile(pattern)
        src = texts.get(path) if path in texts else blob(ref, path)
        hit = None
        for i, ln in enumerate((src or "").splitlines(), 1):
            if rx.search(ln):
                hit = i
                break
        anchors[name] = f"{path}:{hit}" if hit else f"{path}: НЕ НАЙДЕНО"

    markers = {}
    for name, path, pattern, _ in MARKERS:
        src = texts.get(path) if path in texts else blob(ref, path)
        markers[name] = len(re.findall(pattern, src or ""))

    geo = texts.get("play/model/geometry.js", "")
    geo_code = sum(1 for ln in geo.splitlines()
                   if (t := ln.strip()) and not t.startswith(("//", "/*", "*")))

    return {
        "ref": sh(["git", "rev-parse", "--short", ref]).stdout.strip(),
        "subject": sh(["git", "log", "-1", "--format=%s", ref]).stdout.strip(),
        "date": sh(["git", "log", "-1", "--format=%cs", ref]).stdout.strip(),
        "lines": lines,
        "total_lines": sum(lines.values()),
        "geometry_total": lines.get("play/model/geometry.js", 0),
        "geometry_code": geo_code,
        "S_reads": s_reads,
        "S_writes": s_writes,
        "B_calls": b_calls,
        "L_calls": l_calls,
        "touchModel": touch,
        "anchors": anchors,
        "scripts": {
            "count": len(re.findall(r'<script src="', index)),
            "versions": sorted(set(re.findall(r"\?v=(\d+)", index))),
        },
        "markers": markers,
    }


def guard_counters():
    """Счётчики самого сторожа игры: ВСЁ ЦЕЛО / известно N / практика сошлось M.

    Их атлас цитирует на листах 1 и 4, и ровно они протухли первыми: в первой
    редакции стояло «22 известных» и «22 сошлось», а через сутки было 31 и 25.
    Число известных расхождений растёт от каждого нового вопроса к владельцу —
    то есть меняется чаще всего остального в этом файле.

    Гоняется настоящий прогон, а не парсится исходник: контракт сторожа —
    «ни одним известным больше», и проверять его надо тем же способом,
    каким он даётся. Нет node или файла — раздел помечается «не снято».
    """
    r = sh(["node", "tools/check.js"])
    if r.returncode not in (0, 1) or not r.stdout:
        return None
    out = r.stdout
    def num(marker):
        m = re.search(marker + r"\s*·\s*(\d+)", out)
        return int(m.group(1)) if m else None
    m = re.search(r"сошлось\s+(\d+),\s*не проверяется\s+(\d+)", out)
    return {
        "целостность": "ВСЁ ЦЕЛО" if "ВСЁ ЦЕЛО" in out else "НЕ ЦЕЛО",
        "известно": num("ИЗВЕСТНО"),
        "сдвиг_диаметра": num("СДВИГ ⌀"),
        "практика_сошлось": int(m.group(1)) if m else None,
        "практика_не_проверяется": int(m.group(2)) if m else None,
    }


def issue_states():
    r = sh(["gh", "issue", "list", "--repo", "newYurk/rollery", "--state", "all",
            "--limit", "300", "--json", "number,state,title"])
    if r.returncode != 0:
        return None
    by = {i["number"]: i for i in json.loads(r.stdout)}
    return {str(n): {"state": by[n]["state"], "title": by[n]["title"]}
            for n in ISSUES if n in by}


def main():
    now = measure("HEAD")
    now["issues"] = issue_states()
    now["guard"] = guard_counters()

    if "--snapshot" in sys.argv:
        SNAP.write_text(json.dumps(now, ensure_ascii=False, indent=1, sort_keys=True),
                        encoding="utf-8")
        print(f"слепок записан на {now['ref']} ({now['date']}) — {now['subject']}")
        print(f"  файлов play/**/*.js: {len(now['lines'])}, строк всего: {now['total_lines']}")
        if now["issues"] is None:
            print("  ⚠ статусы issues не сняты: нет gh или сети")
        if now["guard"] is None:
            print("  ⚠ счётчики сторожа не сняты: нет node или tools/check.js")
        else:
            g = now["guard"]
            print(f"  сторож: {g['целостность']} · известно {g['известно']} · "
                  f"практика сошлось {g['практика_сошлось']}")
        return 0

    if not SNAP.exists():
        print(f"нет слепка {SNAP.name}. Снять: python3 docs/architecture/atlas-facts.py --snapshot")
        return 2
    was = json.loads(SNAP.read_text(encoding="utf-8"))

    # ⚠ ТОТ ЖЕ КОММИТ — НЕ ЗНАЧИТ «СВЕРЯТЬ НЕЧЕГО». Первая редакция здесь
    # выходила с нулём, и это была дыра ровно того сорта, ради которого весь
    # файл написан: статусы issues и счётчики сторожа меняются БЕЗ КОММИТА.
    # Задачу закрывают в браузере, «известных расхождений» становится больше от
    # нового вопроса владельцу — код при этом не двинулся ни на строку.
    # Поэтому на том же коммите пропускается только то, что выведено ИЗ КОДА.
    same = was["ref"] == now["ref"]
    if same:
        print(f"коммит тот же ({now['ref']}) — сверяю только то, что меняется без коммита:\n"
              f"статусы задач и счётчики сторожа\n")
    else:
        behind = sh(["git", "rev-list", "--count", f"{was['ref']}..HEAD"]).stdout.strip()
        print(f"слепок на {was['ref']} ({was['date']}) «{was['subject']}»")
        print(f"сейчас   {now['ref']} ({now['date']}) «{now['subject']}»")
        print(f"коммитов сверху: {behind}\n")

    drift = []
    for key in ([] if same else ("lines", "S_reads", "S_writes", "B_calls", "L_calls",
                                 "touchModel", "anchors", "markers")):
        a, b = was.get(key) or {}, now.get(key) or {}
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                drift.append((key, k, a.get(k), b.get(k)))
    for key in ([] if same else ("total_lines", "geometry_total", "geometry_code")):
        if was.get(key) != now.get(key):
            drift.append(("числа", key, was.get(key), now.get(key)))
    if not same and was.get("scripts") != now.get("scripts"):
        drift.append(("scripts", "теги и версия", was.get("scripts"), now.get("scripts")))
    if now.get("guard") is None:
        print("⚠ счётчики сторожа не сняты: нет node или tools/check.js\n")
    elif was.get("guard"):
        for k in sorted(set(was["guard"]) | set(now["guard"])):
            if was["guard"].get(k) != now["guard"].get(k):
                drift.append(("guard", k, was["guard"].get(k), now["guard"].get(k)))

    issue_drift = []
    if was.get("issues") and now.get("issues"):
        for n, cur in sorted(now["issues"].items(), key=lambda kv: int(kv[0])):
            old = was["issues"].get(n)
            if old and old["state"] != cur["state"]:
                issue_drift.append((n, old["state"], cur["state"], cur["title"]))
    elif now.get("issues") is None:
        print("⚠ статусы issues не проверены: нет gh или сети\n")

    if issue_drift:
        print("ЗАДАЧИ СМЕНИЛИ СОСТОЯНИЕ — а листы говорят о них в будущем времени:")
        for n, a, b, title in issue_drift:
            print(f"  #{n:<4} {a} → {b}   {title[:76]}")
        print(f"  править: {SHEETS['issues']}\n")

    if drift:
        print(f"ЧИСЛА И ЯКОРЯ РАЗОШЛИСЬ — {len(drift)}:")
        group = None
        for label, k, a, b in drift:
            if label != group:
                group = label
                print(f"\n  [{label}]  править: {SHEETS.get(label, '—')}")
            print(f"    {k}: {a} → {b}")
        print()

    if not drift and not issue_drift:
        print("ВСЁ СОШЛОСЬ: числа и якоря атласа держатся.")
        return 0

    print("Поправить листы, пересобрать (./build.sh) и снять новый слепок:")
    print("  python3 docs/architecture/atlas-facts.py --snapshot")
    return 1


if __name__ == "__main__":
    sys.exit(main())
