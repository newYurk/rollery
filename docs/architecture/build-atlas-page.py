#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Собрать docs/reports/architecture-atlas.html — самодостаточную страницу атласа.

Правится ШАБЛОН atlas.template.html, а не результат: результат перезаписывается.

Почему листы вшиваются как data-URI в <img>, а не вставляются разметкой.
D2 кладёт внутрь каждого SVG свой <style> со шрифтами и своими именами классов.
Четыре таких SVG, вставленные разметкой в одну страницу, делят пространство
имён: стиль одного листа начинает красить другой, и это ломается молча, без
единой ошибки в консоли. <img> с data-URI изолирован по построению — внутри
работают только собственные шрифты листа, наружу не течёт ничего.

Плата — 5 % на процентное кодирование и невозможность выделить текст на листе.
За это страница остаётся одним файлом, который можно переслать или открыть
с диска, и это ровно то правило, что записано в CLAUDE.md: один
самодостаточный HTML вместо сотни файлов рядом.
"""

import pathlib
import re
import urllib.parse

HERE = pathlib.Path(__file__).parent
TPL = HERE / "atlas.template.html"
SVG = HERE / "svg"
OUT = HERE.parent / "reports" / "architecture-atlas.html"

# Подпись под каждым листом: что на нём и чего на нём нарочно нет.
CAPTIONS = {
    "01-system-map": (
        "Карта системы",
        "Десять зон и право вызова между ними. Внутри зоны — опись файлов с числом "
        "строк; стрелок между файлами нет ни одной.",
    ),
    "02-danger-edges": (
        "Опасные зависимости",
        "Шесть узлов цепочкой сверху вниз, и порядок в цепочке — это порядок резки. "
        "Цифры считаны grep -c на 01.09.2026.",
    ),
    "03-one-life-path": (
        "Один жизненный путь",
        "Жест → состояние → модель → срез → отрисовка → сохранение. Красным — места, "
        "где путь меняет владельца через глобал, а не через аргумент.",
    ),
    "04-target-migration": (
        "Целевая миграция",
        "Пять шагов и предусловие. У каждого: что делаем, что умирает, чем доказываем, "
        "что открывает.",
    ),
}


def data_uri(path: pathlib.Path) -> str:
    """SVG → data-URI. Процентное кодирование, а не base64: base64 раздувает
    на треть, а здесь больше половины веса — вшитые шрифты, и они уже плотные."""
    raw = path.read_text(encoding="utf-8")
    raw = raw.replace("\n", " ")
    quoted = urllib.parse.quote(raw, safe="~!@$&*()_+-=:;,./?[]{}| ")
    return "data:image/svg+xml;charset=utf-8," + quoted


def size_of(path: pathlib.Path):
    head = path.read_text(encoding="utf-8")[:600]
    m = re.search(r'width="(\d+)" height="(\d+)"', head)
    if not m:
        raise SystemExit(f"не нашёл размер в {path.name}")
    return int(m.group(1)), int(m.group(2))


def figure(stem: str) -> str:
    path = SVG / f"{stem}.svg"
    w, h = size_of(path)
    name, cap = CAPTIONS[stem]
    # Длинный лист ограничиваем по высоте, широкий показываем во всю ширину:
    # иначе один лист занимает пять экранов прокрутки и теряет форму.
    cls = "tall" if h > w else "wide"
    return (
        f'  <figure class="sheet">\n'
        f'    <div class="frame {cls}">'
        f'<img src="{data_uri(path)}" alt="{name}" width="{w}" height="{h}" data-w="{w}">'
        f'</div>\n'
        f'    <figcaption>\n'
        f'      <span class="dim">{w} × {h}</span>\n'
        f'      <span class="txt">{cap}</span>\n'
        f'      <button type="button" class="zoom" data-zoom="{name}">открыть крупно</button>\n'
        f'    </figcaption>\n'
        f'  </figure>'
    )


def main():
    html = TPL.read_text(encoding="utf-8")
    for stem in CAPTIONS:
        token = "{{SVG:" + stem + "}}"
        if token not in html:
            raise SystemExit(f"в шаблоне нет {token}")
        html = html.replace(token, figure(stem))
    left = re.findall(r"\{\{[^}]+\}\}", html)
    if left:
        raise SystemExit(f"в шаблоне осталась неподставленная метка: {left}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"{OUT.relative_to(HERE.parent.parent)}: {OUT.stat().st_size // 1024} КБ")


if __name__ == "__main__":
    main()
