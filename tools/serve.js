// Статический сервер для стенда: node tools/serve.js [порт] [корень]
//
// Зачем свой, а не python -m http.server: под песочницей агента python падает на
// PermissionError в os.getcwd() ещё до разбора аргументов, поэтому --directory не
// спасает. Корень здесь передаётся аргументом и никогда не берётся из cwd.
//
// Не путать с лабораторией скрутки: у неё свой запуск, sim/lab/lab.sh.

const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = Number(process.argv[2]) || 8137;
const ROOT = path.resolve(process.argv[3] || path.join(__dirname, '..'));

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.webp': 'image/webp',
  '.wav': 'audio/wav',
  '.mp3': 'audio/mpeg',
  '.woff2': 'font/woff2',
};

http
  .createServer((req, res) => {
    // Запрос отделяется от строки запроса: стенд открывают с ?check и ?puzzle,
    // и без этого путь искался бы вместе с ними.
    let rel = decodeURIComponent(req.url.split('?')[0].split('#')[0]);
    if (rel.endsWith('/')) rel += 'index.html';

    const full = path.join(ROOT, rel);
    // Выход за корень запрещён: путь после нормализации обязан остаться внутри.
    if (!full.startsWith(ROOT)) {
      res.writeHead(403).end('403');
      return;
    }

    fs.readFile(full, (err, data) => {
      if (err) {
        res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('404 ' + rel);
        return;
      }
      res.writeHead(200, {
        'Content-Type': MIME[path.extname(full).toLowerCase()] || 'application/octet-stream',
        // Стенд правится и перечитывается тут же: кэш браузера здесь только мешает.
        'Cache-Control': 'no-store',
      }).end(data);
    });
  })
  .listen(PORT, () => console.log('стенд: http://localhost:' + PORT + '/play/  корень ' + ROOT));
