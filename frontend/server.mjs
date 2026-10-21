import http from 'node:http';
import https from 'node:https';
import { readFile, stat } from 'node:fs/promises';
import { resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';

const root = fileURLToPath(new URL('./dist/', import.meta.url));
const port = Number(process.env.PORT || 4173);
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.json': 'application/json' };
http.createServer(async (req, res) => {
  try {
    if (req.url.startsWith('/api/v1/')) {
      const target = new URL(req.url, process.env.API_UPSTREAM || 'http://127.0.0.1:8000');
      const transport = target.protocol === 'https:' ? https : http;
      const proxy = transport.request(target, { method: req.method, headers: { ...req.headers, host: target.host } }, upstream => { res.writeHead(upstream.statusCode, upstream.headers); upstream.pipe(res); });
      proxy.on('error', () => res.writeHead(502).end()); req.pipe(proxy); return;
    }
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    let file = resolve(root, '.' + pathname);
    if (file !== root.slice(0, -1) && !file.startsWith(root)) {
      res.writeHead(403).end(); return;
    }
    try { if ((await stat(file)).isDirectory()) file = resolve(file, 'index.html'); }
    catch { if (!extname(file)) file = resolve(root, 'index.html'); else throw new Error('missing'); }
    const data = await readFile(file);
    res.writeHead(200, { 'Content-Type': mime[extname(file)] || 'application/octet-stream', 'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store' });
    res.end(data);
  } catch { res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Не найдено'); }
}).on('error', error => {
  console.error(error.code === 'EADDRINUSE' ? `Порт ${port} занят. Откройте http://127.0.0.1:${port} или запустите на другом порту: PORT=4174 node server.mjs` : `Не удалось запустить сервер: ${error.message}`);
  process.exitCode = 1;
}).listen(port, '127.0.0.1', () => {
  const url = `http://127.0.0.1:${port}`;
  console.log(`Пульс бизнеса\nLocal: ${url}\nДля остановки нажмите Ctrl+C`);
  if (process.env.PULSE_OPEN_BROWSER === '1' && process.platform === 'darwin') execFile('open', [url], () => {});
});
