// Объектив и затвор по законам настоящей камеры. Общие правила для всех стилей; числа — в studio/crew/lens.json,
// их же читает Blender-ядро (studio/gaffer.py: диафрагма по крупности плана), поэтому превиз и чистовой рендер совпадают.
//
// Кадр Super 35. Фокусное считается из угла обзора, диафрагма — по крупности плана (фон за субъектом размыт на
// заданную долю кадра, но субъект целиком в резкости), фокус всегда на субъекте (фокус-пуллер ведёт героя).
// Отсюда физический кружок нерезкости в пикселях.
//
// Затвор: кадр собирается из n подкадров внутри открытого затвора (накопление, engine/accum.js), у каждого свой
// момент времени, свой сдвиг на долю пикселя (сглаживание тонкого без мерцания) и своя точка на зрачке объектива
// (честное боке). Подкадров столько, чтобы копии движущегося объекта шли не реже чем через gap_px пикселей:
// иначе быстрый яркий объект (фара на проезде) распадается на отдельные копии.
import LENS from '/studio/crew/lens.json' with { type: 'json' };
export { LENS };

const SH = LENS.sensor_h_mm, SW = LENS.sensor_w_mm;

// фокусное (мм) по вертикальному углу обзора three.js
export const focalMm = (fovDeg) => SH / 2 / Math.tan(fovDeg * Math.PI / 360);

// диафрагма по крупности плана, та же формула, что studio/gaffer.fstop_for
export function fstopFor(size, f, focusM, bgM, cur = LENS.fstop_default) {
  if (!(size in LENS.bokeh)) return cur;
  const s = Math.max(focusM * 1000, f * 1.5), d = Math.max(bgM * 1000, s + 1);
  const nB = f * f * (d - s) / (d * (s - f) * LENS.bokeh[size] * SW);          // размытие фона ∝ 1/N
  const c = SW * LENS.coc_frac;
  const nDof = LENS.dof_min[size] * 1000 * f * f / (2 * c * s * s);             // глубина ≈ 2·N·c·s²/f²
  return Math.round(Math.max(1.4, nDof, Math.min(nB, cur)) * 10) / 10;
}

// объектив плана: { fov, size?, fstop?, focus (м), bg (м) } → фокусное, диафрагма, радиус входного зрачка (м)
export function lensFor({ fov, size, fstop, focus = 5, bg = 60 }) {
  const f = focalMm(fov);
  const N = fstop ?? fstopFor(size, f, focus, bg);
  return { f, N, apertureR: f / (2 * N) / 1000 };
}

// диаметр кружка нерезкости в пикселях для точки на дистанции z (м) при фокусе zf (м); H — высота кадра в пикселях
export function cocPx(L, z, zf, H) {
  const zm = z * 1000, zfm = zf * 1000;
  return (L.f / L.N) * L.f * Math.abs(zm - zfm) / (zm * Math.max(1, zfm - L.f)) / SH * H;
}

// кружок нерезкости в пикселях как k·|z − zf|/z: множитель k (то же, что cocPx на бесконечности), для шейдера
export function cocK(L, zf, H) {
  const zfm = zf * 1000;
  return (L.f / L.N) * L.f / Math.max(1, zfm - L.f) / SH * H;
}

// подкадров на кадр: копии объекта не реже чем через gap пикселей
export function samplesFor(objectPx, { min = LENS.subframes.min, max = LENS.subframes.max, gap = LENS.subframes.gap_px } = {}) {
  return Math.max(min, Math.min(max, Math.ceil(objectPx / gap)));
}

export function halton(i, b) { let f = 1, r = 0; while (i > 0) { f /= b; r += f * (i % b); i = Math.floor(i / b); } return r; }

// Затвор для фильма: place(tt, cam) ставит мир на момент tt и камеру cam (без сдвигов) и возвращает
// { focus } — расстояние до субъекта в метрах. pose(t, n, lens) отдаёт функцию подкадра k для engine/accum.js:
// она ставит мир и камеру на свой момент внутри затвора, со сдвигом на долю пикселя и точкой на зрачке,
// и возвращает камеры начала и конца подкадра (по ним размывается движение камеры относительно мира)
// и кружок нерезкости подкадра { k, focus } (по нему досглаживаются копии на зрачке).
export function makeShutter(THREE, camera, { W, H, fps, shutter = LENS.shutter_deg / 360 }) {
  const A = camera.clone(), B = camera.clone();
  const fwd = new THREE.Vector3(), rgt = new THREE.Vector3(), up = new THREE.Vector3(), F = new THREE.Vector3(), q = new THREE.Quaternion();
  const open = shutter / fps;
  // сдвиг камеры для подкадра k: доля пикселя и точка на зрачке; фокус-плоскость остаётся на месте
  const offset = (cam, k, n, L, focus) => {
    cam.clearViewOffset();
    if (n <= 1) { cam.updateMatrixWorld(); return; }
    cam.setViewOffset(W, H, halton(k + 1, 2) - 0.5, halton(k + 1, 3) - 0.5, W, H);
    if (L) {
      const r = Math.sqrt(halton(k + 1, 5)) * L.apertureR, a = halton(k + 1, 7) * Math.PI * 2;
      cam.updateMatrixWorld(); cam.getWorldDirection(fwd);
      rgt.setFromMatrixColumn(cam.matrixWorld, 0); up.setFromMatrixColumn(cam.matrixWorld, 1);
      F.copy(cam.position).addScaledVector(fwd, focus);
      cam.position.addScaledVector(rgt, Math.cos(a) * r).addScaledVector(up, Math.sin(a) * r);
      // довернуть ось на точку фокуса, сохранив крен
      q.setFromUnitVectors(fwd, F.sub(cam.position).normalize()); cam.quaternion.premultiply(q);
    }
    cam.updateMatrixWorld();
  };
  // place пользователя + обновление матриц; камера без сдвигов прошлого подкадра
  const at = (place, tt, cam) => { cam.clearViewOffset(); const r = place(tt, cam) ?? {}; cam.updateMatrixWorld(); return r; };
  return {
    open,
    // объектив и число подкадров для кадра t. probe() → [Vector3]: точки субъекта в мире (шлем, фара, колесо);
    // мерится, сколько пикселей они пролетают за затвор относительно камеры, и сколько даёт боке у объектива
    plan(t, place, lensOpts, probe) {
      const focus = at(place, t, A).focus ?? lensOpts?.focus ?? 5;
      const L = lensOpts ? lensFor({ ...lensOpts, focus }) : null;
      let move = 0;
      if (probe) {
        at(place, t - open / 2, A); const P0 = probe().map((p) => p.clone().project(A));
        at(place, t + open / 2, B); const P1 = probe().map((p) => p.clone().project(B));
        P0.forEach((p, i) => { const p1 = P1[i]; if (p.z < 1 && p1.z < 1 && Math.abs(p.x) < 2 && Math.abs(p1.x) < 2) move = Math.max(move, Math.hypot((p.x - p1.x) * W / 2, (p.y - p1.y) * H / 2)); });
      }
      return { L, n: samplesFor(Math.max(move, L ? cocPx(L, 1.0, focus, H) * 1.6 : 0)) };
    },
    pose(t, n, place, L) {
      return (k) => {
        const tt = t + ((k + 0.5) / n - 0.5) * open, h = open / n / 2;
        let focus = 5;
        if (n > 1) { focus = at(place, tt - h, A).focus ?? focus; offset(A, k, n, L, focus); at(place, tt + h, B); offset(B, k, n, L, focus); }
        focus = at(place, tt, camera).focus ?? focus; offset(camera, k, n, L, focus);
        return n > 1 ? [A, B, L ? { k: cocK(L, focus, H), focus } : null] : null;
      };
    },
  };
}
