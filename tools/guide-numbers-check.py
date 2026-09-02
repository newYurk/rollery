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

# ⚑ ВТОРАЯ ЧАСТЬ: ДИАМЕТРЫ И ВИТКИ ШЕСТИ КАДРОВ (заведено 02.09).
#
# Первая часть сверяет три числа из блока ⟦ЧИСЛА МОДЕЛИ⟧ — они про формулу формы. А ПОДПИСИ
# под кадрами не стерёг никто, и они уехали молча: в документе стояло ⌀ 57,8 мм у канона при
# нынешних 51,6, и рядом рукописная пометка «⚠ кадр до правок 01.09, сейчас 67,7» — сама уже
# неверная. За сутки диаметры двинули #151 (ролл был на 28 % больше материала), #154
# (сердечник заполнился рисом) и #156 (долг ядра снимается вместе с ядром); каждая правка
# обоснована, и каждая двигала подписи, о которых сторож не знал.
#
# Теперь блок ⟦ЧИСЛА СРЕЗА⟧ привязывает каждый кадр к раскладке, а числа снимаются ЖИВОЙ
# моделью через tools/check.js --eval. Правишь модель — либо подписи съезжают вместе с ней,
# либо сторож краснеет.
блок2 = re.search(r'⟦ЧИСЛА СРЕЗА⟧(.*?)⟦/ЧИСЛА СРЕЗА⟧', док, re.S)
if not блок2:
    print('  ✗ блок ⟦ЧИСЛА СРЕЗА⟧ не найден — подписи кадров не сверяются')
    плохо += 1
else:
    import subprocess, json, tempfile, os
    строки = []
    for л in блок2.group(1).split('\n'):
        m2 = re.match(r'\s*(\S+)\s+(hoso|futo|ura|fruit|uzumaki)\s+(.+?)\s+([\d.]+)\s+([\d.]+)\s*$', л)
        if m2: строки.append(m2.groups())
    if not строки:
        print('  ✗ в блоке ⟦ЧИСЛА СРЕЗА⟧ не разобралась ни одна строка')
        плохо += 1
    else:
        # раскладки описаны в блоке словами; здесь их машинное соответствие — одно место
        РАСКЛАДКИ = {
            'тэкка':      "[{kind:'tuna',u:0.42,v:0.5,z0:0,z1:0,phase:1}]",
            'каппа':      "[{kind:'cucumber',u:0.42,v:0.5,z0:0,z1:0,phase:1}]",
            'футо-канон': "canonLayout()",
            'урамаки':    "[{kind:'salmon',u:0.40,v:0.5,z0:0,z1:0,phase:1},{kind:'avocado',u:0.50,v:0.5,z0:0,z1:0,phase:1}]",
            'наруто':     "[{kind:'naruto',u:0.45,v:0.5,z0:0,z1:0,phase:1}]",
            'гюхи':       "canonLayout()",
        }
        ОБЁРТКИ = {'гюхи': "'gyuhi'"}
        куски = []
        for имя, база, _оп, _d, _t in строки:
            сп = РАСКЛАДКИ.get(имя)
            if not сп: continue
            об = ОБЁРТКИ.get(имя, 'null')
            куски.append(f"""{{ S.base='{база}'; S.shape='kamaboko'; S.wrap={об}; S.turns=null; S.hand=handOf();
  S.lists['{база}']={сп}; modelCaches.clear(); touchModel(); layout();
  const m=getModel(), wd=windFor(m,0.5);
  O['{имя}']=[+(2*m.Rmax*5).toFixed(1), +wd.turns.toFixed(2)]; }}""")
        код = 'const O={};\n' + '\n'.join(куски) + '\nglobalThis.ВЫХОД=JSON.stringify(O);'
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(код); путь = f.name
        try:
            r = subprocess.run(['node', 'tools/check.js', '--eval', путь],
                               capture_output=True, text=True, timeout=180)
            факт = json.loads(r.stdout.strip().split('\n')[-1])
        except Exception as e:
            print(f'  ✗ не удалось снять числа моделью: {e}')
            факт = {}; плохо += 1
        finally:
            os.unlink(путь)
        сверено = 0
        for имя, база, _оп, d, t in строки:
            если = факт.get(имя)
            if не_надо := (если is None):
                print(f'  ✗ {имя}: модель не дала числа'); плохо += 1; continue
            if abs(если[0] - float(d)) > 0.15 or abs(если[1] - float(t)) > 0.015:
                print(f'  ✗ подпись «{имя}»: документ ⌀ {d} · {t} об · модель ⌀ {если[0]} · {если[1]} об')
                плохо += 1
            else: сверено += 1
        if сверено: print(f'  ✓ подписи кадров совпадают с моделью ({сверено} сверено)')

if not плохо:
    print(f'  ✓ числа чертежей совпадают с кодом ({len(ожидаем)} сверено)')
sys.exit(1 if плохо else 0)
