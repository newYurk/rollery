#!/usr/bin/env python
"""Лаборатория скрутки — локальный стенд: запускает симуляцию и показывает, как она крутится.

Запуск:  ./lab.sh        (из папки sim/lab)
Откроется http://127.0.0.1:8770 — выбираешь вариант кинематики, раскладку, ползунки, «Прогнать».
Питон знать не нужно: всё делается в браузере.
"""
import http.server, json, os, re, shutil, socketserver, subprocess, sys, threading, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(HERE)
RUNS = os.path.join(HERE, 'runs')
PORT = int(os.environ.get('LAB_PORT', '8770'))
HOST = os.environ.get('LAB_HOST', '127.0.0.1')   # 0.0.0.0 — открыть для телефона в той же сети
PY = sys.executable

# ----------------------------------------------------------------- варианты кинематики
# ★ — то, по чему сверяется ИГРА. Остальное — либо отвергнутые попытки, либо для рулета.
# Игра не считает физику: она мотает спираль переменной толщины и берёт числа отсюда.
TITLES = {
    'reference2':  ('★ ЭТАЛОН — по нему сверяется игра',
                    'Победитель очной ставки двух реализаций циновки (26.08): mat-sdf плюс то, что '
                    'удалось привить от mat-chain. Циновка лежит ПОД листом с первого мгновения и '
                    'заворачивается вместе с роллом, пальцы держат начинку. Именно отсюда берутся '
                    'числа для игры'),
    'reference':   ('Прежний эталон — заменён на reference2',
                    'Первая сборка. Оставлена для сверки; для новых прогонов брать reference2'),
    'mat-sdf':     ('Циновка как граница — ПОБЕДИЛ',
                    'Одна из двух реализаций циновки. Выиграла очную ставку и легла в основу reference2'),
    'mat-chain':   ('Циновка как цепочка — проиграл',
                    'Вторая реализация: циновка как лагранжева цепочка узлов. Проиграла, но три её '
                    'находки привиты победителю'),
    'kin-grab':    ('✗ Захват края — отвергнут',
                    'Циновка «пальцами» берёт кромку нори. Источники против: нори никто пальцами '
                    'не берёт, её несёт циновка, а пальцы лежат НА начинке'),
    'kin-mat':     ('Лопатка — без захвата',
                    'Подворот делает сама циновка. Захвата нет — и в этом он прав, но нет и второй '
                    'опоры, пальцев на начинке; для футомаки она главная'),
    'spiral-curl': ('Спираль · завивка — для РУЛЕТА',
                    'Сладкий рулет: край закручивают в тугой завиток руками. Что из двух спиральных '
                    'вариантов правда — вопрос к прогону, не к рассуждению'),
    'spiral-seed': ('Спираль · посев — для РУЛЕТА',
                    'Сладкий рулет: завиток задан сразу, дальше просто мотается'),
    'spiral':      ('Спираль — ранняя проба',
                    'Историческая. Развилась в spiral-curl и spiral-seed'),
    'spiral-roll': ('Спираль · качение — ранняя проба',
                    'Историческая, без README. Для рулета брать spiral-curl или spiral-seed'),
    'play':        ('Песочница', 'Твоя личная копия — можно ломать'),
    'mpm-shell':   ('✗ Первая версия — историческая',
                    'Циновка катится по столу и гребёт рис. Опровергнута: так не крутят'),
}
# Подписи раскладок берутся ИЗ САМОЙ СЦЕНЫ (поле name в LAYOUTS её run.py), а не из общей
# таблицы: 29.08 обнаружилось, что 6 и 7 подписаны «Рулет» и «Лаваш», хотя во ВСЕХ вариантах
# это futomaki-full-core и futomaki-real. Нажимаешь «Рулет» — считается футомаки.
LAYOUT_RU = {
    'empty': 'Пустой лист',
    'tamago-edge': 'Тамаго у края',
    'salmon-mid': 'Лосось в середине',
    'four-edge': 'Четыре начинки у края',
    'overflow-square': 'Переполнение + квадрат',
    'futomaki-full-core': 'Футомаки, набитое ядро',
    'futomaki-real': 'Футомаки как в жизни',
}
# Запасная таблица — только если сцена не объявила имён (спиральные варианты).
LAYOUT_NAMES = {
    1: 'Пустой лист', 2: 'Тамаго у края', 3: 'Лосось в середине',
    4: 'Четыре начинки у края', 5: 'Переполнение + квадрат', 6: 'Раскладка 6', 7: 'Раскладка 7',
}
KNOB_INFO = {
    'speed':  ('Скорость руки', 0.4, 2.0, 0.1, 1.0, 'быстрее — рыхлее и крупнее'),
    'press':  ('Прижим циновки', 0.4, 2.0, 0.1, 1.0, 'сильнее — плотнее и мельче'),
    'tuck':   ('Глубина подворота', 0.6, 1.3, 0.05, 1.0, 'дальше — начинка уходит из центра'),
    'hold':   ('Держать в конце', 0.0, 8.0, 0.5, 0.0, 'дольше — плотнее ядро'),
    'lift':   ('Подъём циновки', 0.0, 1.5, 0.1, 1.0, '0 — циновка едет по столу и гребёт рис'),
    'fronty': ('Передний край дуги', -1.0, 3.0, 0.1, -1.0, 'ниже — дуга сильнее задевает лист'),
}

_variants_cache = {}


def variants():
    out = []
    for name in sorted(os.listdir(SIM)):
        d = os.path.join(SIM, name)
        rp = os.path.join(d, 'run.py')
        if not os.path.isfile(rp):
            continue
        if name in _variants_cache and _variants_cache[name]['mtime'] == os.path.getmtime(rp):
            out.append(_variants_cache[name]['data'])
            continue
        src = open(rp, encoding='utf-8', errors='ignore').read()
        knobs = [k for k in KNOB_INFO if "'--%s'" % k in src]
        layouts = sorted({int(m) for m in re.findall(r'^\s*(\d)\s*:\s*dict\(', src, re.M)})
        if not layouts:
            layouts = [1, 2, 3, 4, 5]
        # имя каждой раскладки — из самой сцены; техническое переводим, незнакомое показываем как есть
        names = {}
        for num, tech in re.findall(r"^\s*(\d)\s*:\s*dict\(name='([^']+)'", src, re.M):
            names[int(num)] = LAYOUT_RU.get(tech, tech)
        title, note = TITLES.get(name, (name, ''))
        data = dict(id=name, title=title, note=note, knobs=knobs, layouts=layouts, names=names,
                    mtime=time.strftime('%H:%M %d.%m', time.localtime(os.path.getmtime(rp))))
        _variants_cache[name] = dict(mtime=os.path.getmtime(rp), data=data)
        out.append(data)
    # Эталон первым. Раньше reference2 в списке не было вовсе — он получал 99 и уезжал в конец,
    # а первым и предвыбранным оказывался устаревший reference (найдено 29.08).
    order = ['reference2', 'reference', 'mat-sdf', 'mat-chain', 'kin-grab', 'kin-mat',
             'spiral-curl', 'spiral-seed', 'spiral-roll', 'play', 'mpm-shell']
    out.sort(key=lambda v: (order.index(v['id']) if v['id'] in order else 99, v['id']))
    return out


# ----------------------------------------------------------------- запуск прогона
JOBS = {}


class Job:
    def __init__(self, rid, variant, layout, args, frames, grid, particles):
        self.id, self.variant, self.layout = rid, variant, layout
        self.dir = os.path.join(RUNS, rid)
        os.makedirs(self.dir, exist_ok=True)
        self.log, self.done, self.error, self.proc = [], False, None, None
        self.started = time.time()
        cmd = [PY, 'run.py', '--layout', str(layout), '--out', self.dir, '--tag', 'lab',
               '--frames', str(frames), '--grid', str(grid), '--particles', str(particles)]
        for k, v in args.items():
            cmd += ['--%s' % k, str(v)]
        self.cmd = ' '.join(cmd[1:])
        threading.Thread(target=self._run, args=(cmd,), daemon=True).start()

    def _run(self, cmd):
        try:
            self.proc = subprocess.Popen(cmd, cwd=os.path.join(SIM, self.variant), stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True, bufsize=1,
                                         env=dict(os.environ, PYTHONUNBUFFERED='1'))
            for line in self.proc.stdout:
                line = line.rstrip()
                if line.startswith('[GsTaichi]') or not line:
                    continue
                self.log.append(line)
                if len(self.log) > 400:
                    del self.log[:200]
            self.proc.wait()
            if self.proc.returncode:
                self.error = 'прогон завершился с ошибкой (код %s)' % self.proc.returncode
        except Exception as e:                                   # noqa: BLE001
            self.error = str(e)
        finally:
            self.done = True

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()

    def artefacts(self):
        frames, cut, metrics, roll = [], None, None, None
        for root, _dirs, files in os.walk(self.dir):
            for f in sorted(files):
                rel = os.path.relpath(os.path.join(root, f), self.dir)
                if f.endswith('.png') and 'frames_' in root:
                    m = re.match(r'f(\d+)_?(.*)\.png$', f)
                    phase = (m.group(2) if m else '') or ''
                    frames.append(dict(src=rel, phase=phase, step=int(m.group(1)) if m else 0))
                elif f.startswith('material_') and f.endswith('.png'):
                    cut = rel
                elif f.startswith('final_') and f.endswith('.png'):
                    roll = rel
                elif f.startswith('metrics_') and f.endswith('.json'):
                    metrics = rel
        frames.sort(key=lambda x: x['step'])
        data = None
        if metrics:
            try:
                data = json.load(open(os.path.join(self.dir, metrics), encoding='utf-8'))
            except Exception:                                    # noqa: BLE001
                data = None
        return dict(frames=frames, cut=cut, roll=roll, metrics=data)


PHASE_RU = {'A': 'подъём края', 'B': 'заведение', 'Btuck': 'подворот', 'Bhold': 'удержание',
            'C': 'прокатка', 'D_close': 'замыкание', 'D_press': 'прижим', 'curl': 'завивка'}

KEY_METRICS = [
    ('Rout_T', 'Радиус ролла, T'), ('Rout_median_T', 'Радиус (медиана), T'),
    ('nori_turns', 'Оборотов обёртки'), ('layers_predicted', 'Оборотов по формуле'),
    ('nori_turns_geom', 'Оборотов по формуле'),
    ('rice_J_mean', 'Сжатие риса (J)'), ('conservation', 'Объём (1 = не сжат)'),
    ('rice_area_ratio', 'Риса на карте'), ('spread_area_ratio', 'Намазки на карте'),
    ('gap_cv', 'Неравномерность витков'), ('hole_T', 'Дырка в центре, T'),
    ('nori_torn', 'Нори порвана'), ('escaped', 'Вылетело частиц'),
    # «Устойчиво» переименовано: оно отвечает только за то, что СЧЁТ не развалился, и читалось
    # как «прогон удался». Физическую годность показывает вердикт первой строкой (см. index.html).
    ('stable', 'Счёт устойчив'),
    ('rice_squash_ok', 'Рис не пережат'), ('wrinkle_ok', 'Без складок'),
    ('core_order_preserved', 'Порядок начинок'), ('ppc', 'Частиц на клетку'),
]


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):                                    # тише
        pass

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(p.query)
        if p.path == '/':
            return self._file(os.path.join(HERE, 'index.html'), 'text/html; charset=utf-8')
        if p.path == '/api/variants':
            return self._json(dict(variants=variants(), layoutNames=LAYOUT_NAMES,
                                   knobs={k: dict(zip(('label', 'min', 'max', 'step', 'def', 'hint'), v))
                                          for k, v in KNOB_INFO.items()},
                                   phases=PHASE_RU, keyMetrics=KEY_METRICS))
        if p.path == '/api/status':
            j = JOBS.get(q.get('id', [''])[0])
            if not j:
                return self._json(dict(error='нет такого прогона'), 404)
            r = dict(id=j.id, done=j.done, error=j.error, log=j.log[-30:],
                     seconds=round(time.time() - j.started, 1), cmd=j.cmd)
            if j.done:
                r.update(j.artefacts())
            return self._json(r)
        if p.path == '/api/history':
            hist = []
            for rid in sorted(os.listdir(RUNS), reverse=True)[:24] if os.path.isdir(RUNS) else []:
                meta = os.path.join(RUNS, rid, 'lab.json')
                if os.path.exists(meta):
                    try:
                        hist.append(json.load(open(meta, encoding='utf-8')))
                    except Exception:                             # noqa: BLE001
                        pass
            return self._json(dict(runs=hist))
        if p.path.startswith('/runs/'):
            f = os.path.join(RUNS, urllib.parse.unquote(p.path[len('/runs/'):]))
            if os.path.isfile(f) and os.path.abspath(f).startswith(RUNS):
                return self._file(f, 'image/png' if f.endswith('.png') else 'application/json')
            self.send_error(404)
            return None
        self.send_error(404)
        return None

    def do_POST(self):
        p = urllib.parse.urlparse(self.path)
        n = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n) or b'{}')
        if p.path == '/api/run':
            variant = body.get('variant', 'reference')
            if not os.path.isfile(os.path.join(SIM, variant, 'run.py')):
                return self._json(dict(error='нет такого варианта'), 400)
            layout = int(body.get('layout', 1))
            args = {k: v for k, v in (body.get('args') or {}).items() if k in KNOB_INFO}
            frames = max(6, min(60, int(body.get('frames', 30))))
            grid = max(120, min(320, int(body.get('grid', 200))))
            particles = max(4000, min(250000, int(body.get('particles', 12000))))   # потолок поднят под пресет «точно» (ppc 3,2 на сетке 240), issue #91
            rid = time.strftime('%H%M%S') + '-' + variant + '-l' + str(layout)
            job = Job(rid, variant, layout, args, frames, grid, particles)
            JOBS[rid] = job
            meta = dict(id=rid, variant=variant, layout=layout, args=args, frames=frames,
                        grid=grid, particles=particles, at=time.strftime('%H:%M'))
            json.dump(meta, open(os.path.join(job.dir, 'lab.json'), 'w', encoding='utf-8'), ensure_ascii=False)
            return self._json(dict(id=rid))
        if p.path == '/api/stop':
            j = JOBS.get(body.get('id'))
            if j:
                j.stop()
            return self._json(dict(ok=True))
        if p.path == '/api/clear':
            for rid in list(JOBS):
                JOBS[rid].stop()
            JOBS.clear()
            shutil.rmtree(RUNS, ignore_errors=True)
            os.makedirs(RUNS, exist_ok=True)
            return self._json(dict(ok=True))
        self.send_error(404)
        return None

    def _file(self, path, ctype):
        try:
            data = open(path, 'rb').read()
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    os.makedirs(RUNS, exist_ok=True)
    print('Лаборатория скрутки')
    print('  на этом маке:  http://127.0.0.1:%d' % PORT)
    if HOST != '127.0.0.1':
        import socket, subprocess
        # Имя .local (mDNS) печатаем ПЕРВЫМ и как основной адрес: оно не меняется при смене сети,
        # а числовой адрес меняется. 29.08 на корневой странице был записан 10.0.0.46, к 30.08 мак
        # уже получил 10.0.0.148 — записанный однажды IP протухает молча.
        try:
            name = subprocess.run(['scutil', '--get', 'LocalHostName'], capture_output=True,
                                  text=True, timeout=2).stdout.strip()
        except Exception:
            name = ''
        if name:
            print('  с телефона:    http://%s.local:%d   ← адрес не меняется' % (name, PORT))
        try:
            sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sk.connect(('10.255.255.255', 1))
            lan = sk.getsockname()[0]; sk.close()
            print('  если имя не нашлось: http://%s:%d   (адрес на сегодня)' % (lan, PORT))
        except Exception:
            print('  если имя не нашлось: http://<адрес-этого-мака>:%d' % PORT)
        print('  телефон и мак должны быть в одной сети Wi-Fi')
    print('Остановить — Ctrl+C в этом окне.')
    try:
        Server((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        print('\nостановлено')
