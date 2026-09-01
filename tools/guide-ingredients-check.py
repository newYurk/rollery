"""Размеры и нарезка начинок в документе ядра против каталога.

⚠ ФОРМУЛУ СТОРОЖ СВЕРЯЛ, А ЧИСЛА, КОТОРЫМИ ЕЁ КОРМЯТ, — НЕТ. У документа ядра есть собственная
таблица ING (wU/hU/cut) ВНЕ помеченного блока формы, и именно она была прежним дефектом:
«креветка кружком 10×8» в документе ядра против полукруга 10×5 в игре. Сверять формулу и не сверять
её вход — половина сторожа. Найдено вечерней сверкой 31.08.2026.
"""
import re, sys

guide, catalog = sys.argv[1], sys.argv[2]
g = open(guide, encoding='utf-8').read()
c = open(catalog, encoding='utf-8').read()

m = re.search(r'const ING = \{(.*?)\n  \};', g, re.S)
if not m:
    print('  ✗ в документе ядра не нашлось таблицы ING — сверка не выполнена')
    sys.exit(3)

bad = 0
for kind, body in re.findall(r'(\w+):\s*\{([^}]*)\}', m.group(1)):
    src = re.search(r'\n\s*' + kind + r':\s*\{([^}]*)\}', c)
    if not src:
        print(f'  ✗ {kind}: есть в документе ядра, нет в каталоге'); bad += 1; continue
    sb = src.group(1)
    for f in ('wU', 'hU'):
        a = re.search(f + r':\s*([\d.]+)', body)
        b = re.search(f + r':\s*([\d.]+)', sb)
        if a and b and abs(float(a.group(1)) - float(b.group(1))) > 1e-9:
            print(f'  ✗ {kind}.{f}: документ ядра {a.group(1)} · каталог {b.group(1)}'); bad += 1
    a = re.search(r"cut:\s*'([^']+)'", body)
    b = re.search(r"cut:\s*'([^']+)'", sb)
    if a and b and a.group(1) != b.group(1):
        print(f'  ✗ {kind}.cut: документ ядра «{a.group(1)}» · каталог «{b.group(1)}»'); bad += 1

if not bad:
    print('  ✓ размеры и нарезка начинок в документе ядра совпадают с каталогом')
sys.exit(1 if bad else 0)
