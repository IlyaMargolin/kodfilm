// Движок: детерминированный рендер кадра по номеру. Никакого реального времени —
// кадр N всегда выглядит одинаково, поэтому рендер можно резать на куски и параллелить.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { FilmGrade } from './grade.js';

const params = new URLSearchParams(location.search);
const W = +params.get('w') || 1280, H = +params.get('h') || 720;

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

// Финальный кадр собирается на 2D-холсте: 3D + титры + каше (letterbox).
const out = document.createElement('canvas');
out.width = W; out.height = H;
document.body.appendChild(out);
const g2d = out.getContext('2d');

await document.fonts.load("300 40px 'Inter Display Light'").catch(() => {});
const film = (await import(params.get('film') || '/films/tochka.js')).default;
function drawTitles(t) {
  for (const tt of film.titles ?? []) {
    const a = envelope(t, tt.in, tt.out, tt.fade ?? 1.2);
    if (a <= 0) continue;
    g2d.save();
    g2d.globalAlpha = a;
    g2d.fillStyle = tt.color ?? '#e9e4da';
    const size = Math.round(H * (tt.size ?? 0.034));
    g2d.font = `${tt.weight ?? 300} ${size}px ${tt.font ?? "'Inter Display Light','Inter','DejaVu Sans',sans-serif"}`;
    g2d.textAlign = 'center';
    g2d.textBaseline = 'middle';
    if (g2d.letterSpacing !== undefined) g2d.letterSpacing = `${tt.spacing ?? 0.12}em`;
    const y = H * (tt.y ?? 0.82) + (1 - a) * H * 0.006;
    g2d.shadowColor = 'rgba(0,0,0,0.8)'; g2d.shadowBlur = size * 0.6;
    g2d.fillText(tt.text, W / 2, y);
    g2d.restore();
  }
}

if (film.kind === '2d') {
  const draw = await film.build({ g: g2d, W, H });
  window.__meta = { fps: film.fps, duration: film.duration, frames: Math.round(film.fps * film.duration), W, H };
  window.__frame = (i) => { draw(i / film.fps, i); drawTitles(i / film.fps); return out.toDataURL('image/png'); };
  window.__ready = true;
}
if (film.kind !== '2d') {
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(35, W / H, 0.05, 500);
const ctx = { THREE, scene, camera, renderer, W, H, rand: mulberry32(film.seed ?? 1) };
const shot = await film.build(ctx);

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(W, H), film.bloom?.strength ?? 1.1, film.bloom?.radius ?? 0.6, film.bloom?.threshold ?? 0.15);
composer.addPass(bloom);
composer.addPass(new OutputPass());
const grade = new ShaderPass(FilmGrade);
composer.addPass(grade);

window.__meta = { fps: film.fps, duration: film.duration, frames: Math.round(film.fps * film.duration), W, H };
window.__frame = (i) => {
  const t = i / film.fps;
  shot.update(t);
  grade.uniforms.uTime.value = i;
  grade.uniforms.uFade.value = film.fade ? film.fade(t) : 1;
  composer.render();
  g2d.drawImage(renderer.domElement, 0, 0);
  drawTitles(t);
  const bar = Math.round(H * (film.letterbox ?? 0.11)); // ~2.39:1
  g2d.fillStyle = '#000';
  g2d.fillRect(0, 0, W, bar); g2d.fillRect(0, H - bar, W, bar);
  return out.toDataURL('image/png');
};
window.__ready = true;
}

function envelope(t, a, b, f) {
  if (t < a || t > b) return 0;
  return Math.min(1, (t - a) / f, (b - t) / f);
}
function mulberry32(a) {
  return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a);
    t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}
