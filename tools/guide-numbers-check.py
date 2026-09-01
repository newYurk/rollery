"""ЧИСЛА, КОТОРЫМИ ЧЕРТЕЖИ ПОЛЬЗУЮТСЯ, ПРОТИВ КОДА.

⚠ ЗАЧЕМ ОТДЕЛЬНАЯ ПРОВЕРКА. Блок формы сверяется дословно с 31.08 — это ловит ФОРМУЛУ.
Таблица начинок сверяется с каталогом — это ловит РАЗМЕРЫ. А числа, которыми чертежи
кормят формулу, лежали россыпью в скрипте документа и тихо отстали на два поколения:
TURNS был 1,29 при модельных 1,15, радиус ролла 3,12 при 2,91, фоновый свет 0,34 при 0,62.

Проза документа к тому времени уже признавала, что 1,29 — старое число. То есть текст
поправили, а картинку нет: сверялась формула, но не её вход.

Сверяется помеченный блок ⟦ЧИСЛА МОДЕЛИ⟧ в docs/reports/piece-body.html:
    TURNS   ← play/checks.js, REF.hoso.turns
    R_ROLL  ← play/checks.js, REF.hoso.d / 2 / U_MM
    AMBIENT ← play/model/geometry.js

Звать: python3 tools/guide-numbers-check.py
"""
import re, sys

ДОК   = 'docs/reports/piece-body.html'
CHECKS = 'play/checks.js'
GEOM   = 'play/model/geometry.js'
CATALOG = 'play/model/catalog.js'

def читать(p):
    return open(p, encoding='utf-8').read()

док = читать(ДОК)
m = re.search(r'⟦ЧИСЛА МОДЕЛИ⟧(.*?)⟦/ЧИСЛА МОДЕЛИ⟧', док, re.S)
if not m:
    print('  ✗ в документе ядра нет блока ⟦ЧИСЛА МОДЕЛИ⟧ — сверка не выполнена')
    sys.exit(3)
блок = m.group(1)

def из_блока(имя):
    mm = re.search(r'\b' + имя + r'\s*=\s*([\d.]+)', блок)
    return float(mm.group(1)) if mm else None

# ── источники истины
чекс = читать(CHECKS)
mm = re.search(r"hoso:\s*\{[^}]*?d:\s*([\d.]+)[^}]*?turns:\s*([\d.]+)", чекс)
if not mm:
    print('  ✗ в play/checks.js не нашлось эталона hoso — сверка не выполнена')
    sys.exit(3)
d_mm, turns = float(mm.group(1)), float(mm.group(2))

u_mm = float(re.search(r'U_MM\s*=\s*([\d.]+)', читать(CATALOG)).group(1))
ambient = float(re.search(r'AMBIENT\s*=\s*([\d.]+)', читать(GEOM)).group(1))

ожидаем = {
    'TURNS':   (turns,            f'play/checks.js REF.hoso.turns'),
    'R_ROLL':  (d_mm / 2 / u_mm,  f'play/checks.js REF.hoso.d {d_mm} / 2 / U_MM {u_mm}'),
    'AMBIENT': (ambient,          'play/model/geometry.js AMBIENT'),
}

плохо = 0
for имя, (надо, откуда) in ожидаем.items():
    есть = из_блока(имя)
    if есть is None:
        print(f'  ✗ {имя}: нет в блоке ⟦ЧИСЛА МОДЕЛИ⟧'); плохо += 1; continue
    if abs(есть - надо) > 0.005:
        print(f'  ✗ {имя}: документ {есть} · код {надо:.4g}  ({откуда})'); плохо += 1

if not плохо:
    print(f'  ✓ числа чертежей совпадают с кодом ({len(ожидаем)} сверено)')
sys.exit(1 if плохо else 0)
