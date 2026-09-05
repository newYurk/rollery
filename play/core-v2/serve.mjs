#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT || 8080);
const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
};

http.createServer((req, res) => {
  let rel = decodeURIComponent((req.url || '/').split('?')[0].split('#')[0]);
  if (rel === '/') rel = '/index.html';
  const full = path.normalize(path.join(ROOT, rel));
  if (!full.startsWith(ROOT)) {
    res.writeHead(403).end('403');
    return;
  }
  fs.readFile(full, (err, data) => {
    if (err) {
      res.writeHead(err.code === 'ENOENT' ? 404 : 500).end(err.code === 'ENOENT' ? '404' : '500');
      return;
    }
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(full)] || 'application/octet-stream',
      'Cache-Control': 'no-store',
    });
    res.end(data);
  });
}).listen(PORT, '0.0.0.0', () => {
  console.log('core-v2 debug on 0.0.0.0:' + PORT);
});
