// Рендер: node render.mjs [--film films/tochka.js] [--w 1280 --h 720] [--from 0 --to N] [--out out/film.mp4]
import { chromium } from 'playwright';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';

const arg = (k, d) => { const i = process.argv.indexOf('--' + k); return i > 0 ? process.argv[i + 1] : d; };
const film = '/' + arg('film', 'films/tochka.js').replace(/^\//, '');
const W = +arg('w', 1280), H = +arg('h', 720);
const outFile = arg('out', 'out/film.mp4');
fs.mkdirSync(path.dirname(outFile), { recursive: true });

const root = process.cwd();
const types = { '.js': 'text/javascript', '.mjs': 'text/javascript', '.html': 'text/html', '.json': 'application/json', '.otf': 'font/otf' };
const server = http.createServer((req, res) => {
  const p = path.join(root, decodeURIComponent(req.url.split('?')[0]));
  if (!p.startsWith(root) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'content-type': types[path.extname(p)] || 'application/octet-stream' });
  fs.createReadStream(p).pipe(res);
}).listen(0);
const port = server.address().port;

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: W, height: H } });
page.on('console', m => console.log('[page]', m.text()));
page.on('pageerror', e => { console.error('[page error]', e); process.exit(1); });
await page.goto(`http://localhost:${port}/engine/index.html?film=${film}&w=${W}&h=${H}`);
await page.waitForFunction('window.__ready === true', null, { timeout: 120000 });
const meta = await page.evaluate('window.__meta');
let from = +arg('from', 0), to = +arg('to', meta.frames);
if (arg('chunks')) { // --chunk K --chunks N: K-й кусок из N (для параллельного рендера)
  const N = +arg('chunks'), K = +arg('chunk', 0), per = Math.ceil(meta.frames / N);
  from = K * per; to = Math.min(meta.frames, from + per);
}
console.log(`Рендер ${film}: кадры ${from}..${to - 1} из ${meta.frames}, ${W}x${H} @ ${meta.fps}fps`);

const stills = arg('stills');
if (stills) {
  for (const i of stills.split(',').map(Number)) {
    const url = await page.evaluate(i => window.__frame(i), i);
    fs.writeFileSync(path.join(path.dirname(outFile), `still_${String(i).padStart(5, '0')}.png`), Buffer.from(url.split(',')[1], 'base64'));
  }
  await browser.close(); server.close(); console.log('Стоп-кадры готовы'); process.exit(0);
}
const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(meta.fps), '-i', '-',
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', outFile], { stdio: ['pipe', 'inherit', 'inherit'] });
const t0 = Date.now();
for (let i = from; i < to; i++) {
  const url = await page.evaluate(i => window.__frame(i), i);
  if (!ff.stdin.write(Buffer.from(url.split(',')[1], 'base64'))) await new Promise(r => ff.stdin.once('drain', r));
  if (i % 24 === 0) console.log(`  кадр ${i}  (${((Date.now() - t0) / 1000 / (i - from + 1)).toFixed(2)} c/кадр)`);
}
ff.stdin.end();
await new Promise(r => ff.on('close', r));
await browser.close(); server.close();
console.log('Готово:', outFile);
