// Мел на чёрной доске: штрих с текстурой мела, «кипение» линий как в рисованной анимации,
// персонаж-человечек на скелете с позами и мимикой.
export function makeChalk(g, W, H, seed = 1) {
  // текстура мела: шум с «дырами», как мел по шероховатой доске
  const tex = document.createElement('canvas'); tex.width = tex.height = 256;
  const tg = tex.getContext('2d'), id = tg.createImageData(256, 256);
  let s = seed * 9301 + 49297;
  const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < 256 * 256; i++) {
    const v = rnd(); const a = v < 0.18 ? 0 : 150 + 105 * rnd();
    id.data.set([240, 238, 230, a], i * 4);
  }
  tg.putImageData(id, 0, 0);
  const pat = g.createPattern(tex, 'repeat');

  // детерминированный шум для «кипения»: зависит от номера рисунка и индекса точки
  const hash = (a, b) => { const x = Math.sin(a * 127.1 + b * 311.7) * 43758.5453; return x - Math.floor(x); };
  let drawing = 0; // номер «рисунка» (12 в секунду)
  const U = H / 1000; // единица: тысячная доля высоты кадра

  function jitter(pts, k, amt) {
    return pts.map(([x, y], i) => [x + (hash(drawing + k, i * 2) - 0.5) * amt * U, y + (hash(drawing + k, i * 2 + 1) - 0.5) * amt * U]);
  }
  function densify(pts, step = 14) {
    const out = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const [x0, y0] = pts[i], [x1, y1] = pts[i + 1];
      const n = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0) / (step * U)));
      for (let j = 0; j < n; j++) out.push([x0 + (x1 - x0) * j / n, y0 + (y1 - y0) * j / n]);
    }
    out.push(pts[pts.length - 1]);
    return out;
  }
  // stroke: несколько проходов с разным дрожанием — как живая линия мелом
  function stroke(pts, { w = 3.2, alpha = 1, k = 0, amt = 2.2, partial = 1 } = {}) {
    if (alpha <= 0.01 || pts.length < 2) return;
    let d = densify(pts);
    if (partial < 1) d = d.slice(0, Math.max(2, Math.floor(d.length * partial)));
    g.save(); g.strokeStyle = pat; g.lineCap = 'round'; g.lineJoin = 'round';
    for (let p = 0; p < 3; p++) {
      const j = jitter(d, k * 7 + p * 101, amt * (p === 0 ? 0.6 : 1.2));
      g.globalAlpha = alpha * (p === 0 ? 0.95 : 0.4);
      g.lineWidth = w * U * (p === 0 ? 1 : 0.6);
      g.beginPath(); g.moveTo(j[0][0], j[0][1]);
      for (let i = 1; i < j.length; i++) g.lineTo(j[i][0], j[i][1]);
      g.stroke();
    }
    g.restore();
  }
  function circle(cx, cy, r, opt = {}) {
    const pts = []; const n = Math.max(12, Math.round(r / U));
    const start = hash(opt.k ?? 0, 9) * Math.PI * 2;
    for (let i = 0; i <= n + 2; i++) { const a = start + i / n * Math.PI * 2; pts.push([cx + Math.cos(a) * r, cy + Math.sin(a) * r]); }
    stroke(pts, { amt: 1.4, ...opt });
  }
  function hatch(x0, y0, x1, y1, n, opt = {}) { // штриховка (тени, глубина)
    for (let i = 0; i < n; i++) {
      const t = i / n, x = x0 + (x1 - x0) * t + (hash(i, 3) - 0.5) * 6 * U;
      stroke([[x, y0 + hash(i, 5) * 20 * U], [x + (hash(i, 7) - 0.5) * 8 * U, y1 - hash(i, 8) * 40 * U]], { w: 1.4, alpha: 0.35, k: i + 50, ...opt });
    }
  }
  function text(str, x, y, size, alpha = 1) {
    g.save(); g.globalAlpha = alpha; g.fillStyle = pat;
    g.font = `300 ${size * U}px 'Inter Display Light','DejaVu Sans',sans-serif`; g.textAlign = 'center';
    if (g.letterSpacing !== undefined) g.letterSpacing = '0.06em';
    const ox = (hash(drawing, 77) - 0.5) * 1.2 * U, oy = (hash(drawing, 78) - 0.5) * 1.2 * U;
    g.fillText(str, x + ox, y + oy); g.globalAlpha = alpha * 0.35; g.fillText(str, x + ox + U, y + oy); g.restore();
  }

  // ---------- человечек ----------
  // поза: углы в радианах (0 = вниз), всё относительно бёдер
  function figure(x, yFeet, pose, { scale = 1, alpha = 1, k = 0, face = {} } = {}) {
    const S = U * scale;
    const L = { thigh: 62, shin: 60, torso: 92, neck: 10, upper: 50, fore: 46, head: 30 };
    const P = (o, ang, len) => [o[0] + Math.sin(ang) * len * S, o[1] + Math.cos(ang) * len * S];
    const legLen = (L.thigh + L.shin) * S * (pose.crouch ?? 1);
    const hip = [x, yFeet - legLen + (pose.bob ?? 0) * S];
    const chest = P(hip, Math.PI + (pose.lean ?? 0), L.torso);
    const neck = P(chest, Math.PI + (pose.lean ?? 0) * 1.2, L.neck);
    const head = P(neck, Math.PI + (pose.lean ?? 0) + (pose.headTilt ?? 0), L.head);
    const kneeL = P(hip, pose.hipL ?? 0.08, L.thigh), footL = P(kneeL, (pose.hipL ?? 0.08) - (pose.kneeL ?? 0), L.shin);
    const kneeR = P(hip, pose.hipR ?? -0.08, L.thigh), footR = P(kneeR, (pose.hipR ?? -0.08) - (pose.kneeR ?? 0), L.shin);
    const sh = P(chest, (pose.lean ?? 0), 8);
    const elL = P(sh, pose.armL ?? 0.25, L.upper), hdL = P(elL, (pose.armL ?? 0.25) + (pose.elbL ?? 0.1), L.fore);
    const elR = P(sh, pose.armR ?? -0.25, L.upper), hdR = P(elR, (pose.armR ?? -0.25) + (pose.elbR ?? -0.1), L.fore);
    const o = { alpha, w: 3.4 * scale };
    // тело — прямоугольная рубашка как у меловых человечков
    const bw = 22 * S, top = P(chest, 0, 6), bot = P(hip, Math.PI, 4);
    stroke([[top[0] - bw * 0.6, top[1]], [top[0] + bw * 0.6, top[1]], [bot[0] + bw * 0.5, bot[1]], [bot[0] - bw * 0.5, bot[1]], [top[0] - bw * 0.6, top[1]]], { ...o, k: k + 1 });
    stroke([hip, kneeL, footL, [footL[0] - 8 * S, footL[1]]], { ...o, k: k + 2 });
    stroke([hip, kneeR, footR, [footR[0] + 8 * S, footR[1]]], { ...o, k: k + 3 });
    stroke([sh, elL, hdL], { ...o, k: k + 4 }); stroke([sh, elR, hdR], { ...o, k: k + 5 });
    // голова и лицо
    const r = L.head * S;
    circle(head[0], head[1], r, { ...o, k: k + 6 });
    const look = (face.look ?? 0) * 6 * S, lookY = (face.lookY ?? 0) * 5 * S;
    for (const sx of [-1, 1]) {
      const ex = head[0] + sx * 11 * S + look * 0.5, ey = head[1] - 2 * S;
      circle(ex, ey, 8 * S, { ...o, w: 2.4 * scale, k: k + 7 + sx });
      const blink = face.blink ? 0.15 : 1;
      g.save(); g.globalAlpha = alpha; g.fillStyle = pat; g.beginPath();
      g.ellipse(ex + look, ey + lookY + 1 * S, 3.6 * S, 3.6 * S * blink, 0, 0, Math.PI * 2); g.fill(); g.restore();
      // брови: тревога = внутренние концы вверх
      const worry = face.worry ?? 0;
      stroke([[ex - sx * 9 * S, ey - 13 * S + worry * 1 * S], [ex + sx * 7 * S, ey - 13 * S - worry * 6 * S * -1 - worry * 2 * S]], { ...o, w: 2.2 * scale, k: k + 9 + sx });
    }
    const m = face.mouth ?? 0; // -1 грусть, +1 улыбка
    const mx = head[0] + look * 0.4, my = head[1] + 14 * S;
    stroke([[mx - 7 * S, my - m * 3 * S], [mx, my + m * 3 * S], [mx + 7 * S, my - m * 3 * S]], { ...o, w: 2.2 * scale, k: k + 12 });
    // волосы: растрёпанные штрихи
    for (let i = 0; i < 7; i++) {
      const a = -Math.PI / 2 + (i - 3) * 0.32, b = a + (hash(i, k) - 0.5) * 0.8;
      const p0 = [head[0] + Math.cos(a) * r * 0.95, head[1] + Math.sin(a) * r * 0.95];
      stroke([p0, [p0[0] + Math.cos(b) * 12 * S, p0[1] + Math.sin(b) * 12 * S]], { ...o, w: 1.8 * scale, k: k + 20 + i });
    }
    return { hip, head, hdL, hdR, footL, footR };
  }

  // процедурная ходьба: фаза 0..1
  function walkPose(ph, amp = 1) {
    const a = Math.sin(ph * Math.PI * 2), b = Math.cos(ph * Math.PI * 2);
    return { hipL: 0.38 * a * amp, hipR: -0.38 * a * amp, kneeL: Math.max(0, -b) * 0.7 * amp, kneeR: Math.max(0, b) * 0.7 * amp,
      armL: -0.35 * a * amp, armR: 0.35 * a * amp, elbL: -0.25, elbR: -0.25, bob: -Math.abs(b) * 4 * amp, lean: -0.05 * amp };
  }

  return {
    U, stroke, circle, hatch, text, figure, walkPose,
    begin(frame, fps) { drawing = Math.floor(frame / Math.max(1, Math.round(fps / 12))); g.fillStyle = '#0b0b0c'; g.fillRect(0, 0, W, H); },
  };
}
export const mixPose = (a, b, t) => { const o = {}; for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) o[k] = (a[k] ?? 0) * (1 - t) + (b[k] ?? 0) * t; return o; };
