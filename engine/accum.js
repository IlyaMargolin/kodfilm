// Накопление подкадров (accumulation buffer, Haeberli & Akeley 1990) и фильтры реконструкции размытия движения
// (McGuire, Hennessy, Bukowski, Osman 2012) и боке. Общая часть для всех 3D-стилей.
//
// Кадр собирается из n рендеров, у каждого свой момент внутри открытого затвора, свой сдвиг на долю пикселя и
// своя точка на зрачке объектива (их ставит pose(k), см. engine/lens.js makeShutter). Одним приёмом это даёт
// сглаживание тонкой травы и бликов без мерцания, честное размытие движения и глубину резкости, как у камеры.
//
// Внутри каждого подкадра промежутки между копиями соседних подкадров ещё и заполняются:
//   VEL   — экранный сдвиг каждого пикселя за подкадр (из глубины и камер начала и конца подкадра), его глубина
//           и шаг между копиями на зрачке (кружок нерезкости·0.886/√n). Глубина берётся ближайшая в 3×3: цвет
//           может быть сглажен, а глубина одна на пиксель, и край тонкого стебля иначе получает скорость фона;
//   TILE  — самый быстрый сдвиг и самый большой шаг на зрачке в плитке motion_tile_px × motion_tile_px;
//   NEIGH — то же среди соседних плиток (один раз на плитку, а не на каждый пиксель);
//   DOFG  — досглаживание копий на зрачке: подкадр размывается по кружку радиусом в шаг между копиями,
//           иначе стебель у объектива при n подкадрах — n тонких линий («шторка»), а не мягкое пятно;
//   ACC   — пиксель собирает отсчёты вдоль самого быстрого сдвига соседних плиток: берёт отсчёт, если тот по своей
//           скорости до него дотягивается (передний план размазывается на фон) или если сам пиксель движется и
//           открывает то, что за ним. Глубины сравниваются мягко.
// Веса в DOFG и ACC — плотность размазанной точки с площадью 1: яркость сохраняется (тонкий стебель, смазанный на
// 9 пикселей, даёт каждому 1/9, а не почти всю). Шаг размазки равен шагу между подкадрами, форма — B-сплайн:
// копии соседних подкадров складываются в ровную полосу, даже если настоящий шаг больше расчётного (трава сама
// качается, а скорости знают только камеру). Точка медленнее пикселя не размазывается.
// Объекты, которые движутся сами (герой, транспорт), помечаются markMoving: их сдвиг здесь нулевой, их размытие
// дают сами подкадры, и по фону они не мажутся.
import LENS from '/studio/crew/lens.json' with { type: 'json' };

const TILE = LENS.motion_tile_px, TAPS = 10, TAPS_MAX = 40, DTAPS = 24;
const VS = /* glsl */`varying vec2 vUv; void main(){ vUv = uv; gl_Position = vec4(position.xy, 0., 1.); }`;
const VEL = /* glsl */`
  uniform sampler2D tSrc, tDepth; uniform mat4 uInvVP, uPrevVP, uNextVP; uniform vec2 uRes; uniform float uNear, uFar; uniform vec3 uCoc; varying vec2 vUv;
  vec2 proj(mat4 m, vec3 w) { vec4 c = m * vec4(w, 1.); return c.xy / c.w * 0.5 + 0.5; }
  void main() {
    // ближайшая глубина в окрестности 3×3: цвет сглажен (MSAA), а глубина одна на пиксель, и край тонкого стебля
    // (наполовину стебель по цвету) иначе получал скорость фона и оставался несмазанной резкой линией
    float d = 1.; vec2 q = vUv;
    for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++) {
      vec2 u = vUv + vec2(float(i), float(j)) / uRes; float e = texture2D(tDepth, u).x;
      if (e < d) { d = e; q = u; }
    }
    vec4 w = uInvVP * vec4(q * 2. - 1., d * 2. - 1., 1.); w /= w.w;
    vec2 v = (proj(uNextVP, w.xyz) - proj(uPrevVP, w.xyz)) * uRes;            // пиксели за подкадр
    float l = length(v); if (l > ${TILE}.) v *= ${TILE}. / l;
    if (texture2D(tSrc, q).a < 0.5) v = vec2(0.);
    float z = uNear * uFar / (uFar - d * (uFar - uNear));                       // расстояние по оси камеры, м
    gl_FragColor = vec4(v, z, uCoc.x * abs(z - uCoc.y) / z * uCoc.z);           // w — шаг между копиями на зрачке, пиксели
  }`;
const TILEMAX = /* glsl */`
  uniform sampler2D tVel; uniform vec2 uRes;
  void main() {
    vec2 o = floor(gl_FragCoord.xy) * ${TILE}.; vec2 best = vec2(0.); float bl = 0., sm = 0.;
    for (int i = 0; i < ${TILE}; i++) for (int j = 0; j < ${TILE}; j++) {
      vec4 V = texture2D(tVel, (o + vec2(float(i), float(j)) + 0.5) / uRes); float l = dot(V.xy, V.xy);
      if (l > bl) { bl = l; best = V.xy; }
      sm = max(sm, V.w);
    }
    gl_FragColor = vec4(best, sm, 1.);
  }`;
const NEIGH = /* glsl */`
  uniform sampler2D tTile; uniform vec2 uTiles;
  void main() {
    vec2 tc = floor(gl_FragCoord.xy), best = vec2(0.); float bl = 0., sm = 0.;
    for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++) {
      vec3 v = texture2D(tTile, (tc + vec2(float(i), float(j)) + 0.5) / uTiles).xyz; float l = dot(v.xy, v.xy);
      if (l > bl) { bl = l; best = v.xy; }
      sm = max(sm, v.z);
    }
    gl_FragColor = vec4(best, sm, 1.);
  }`;
const DOFG = /* glsl */`
  uniform sampler2D tSrc, tVel, tNeigh; uniform float uSeed; uniform vec2 uRes, uTiles; varying vec2 vUv;
  float D(float d, float r) { return r > 1. ? (1. - smoothstep(r - 0.5, r + 0.5, d)) / (r * r) : 0.; }
  void main() {
    vec3 c = texture2D(tSrc, vUv).rgb;
    float R = texture2D(tNeigh, (floor(gl_FragCoord.xy / ${TILE}.) + 0.5) / uTiles).z;
    if (R > 0.75) {
      R = min(R, ${TILE}.);
      // точка размазывается по кружку радиуса s: плотность 1/(π s²) на пиксель; сам пиксель — площадь 1,
      // отсчёт — площадь π R²/n. Радиус не меньше 1/√π: точка не плотнее самого пикселя
      vec4 X = texture2D(tVel, vUv); float sX = X.w;
      float ws = 1. / (3.14159 * max(sX * sX, 0.3183)); vec3 acc = c * ws;
      vec3 p3 = fract(vec3(gl_FragCoord.xy, uSeed + 7.5) * 0.1031); p3 += dot(p3, p3.zyx + 31.32);
      float rot = fract((p3.x + p3.y) * p3.z) * 6.2831853;
      float n = clamp(ceil(R * R), 6., ${DTAPS}.), A = R * R / n;
      for (int i = 0; i < ${DTAPS}; i++) {
        if (float(i) >= n) break;
        float t = (float(i) + 0.5) / n, a = float(i) * 2.3999632 + rot;              // диск Фогеля: ровно по площади
        vec2 o = R * sqrt(t) * vec2(cos(a), sin(a)); float dist = length(o);
        vec2 uv = vUv + o / uRes;
        vec4 Y = texture2D(tVel, uv); float sY = Y.w;
        float ext = 0.02 + 0.05 * min(X.z, Y.z);
        float f = clamp(1. - (Y.z - X.z) / ext, 0., 1.), b = clamp(1. - (X.z - Y.z) / ext, 0., 1.);
        // ближний (f) ложится сюда, если его кружок дотянулся; дальний (b) виден сквозь размытый край самого пикселя
        float w = A * (f * D(dist, sY) + b * (1. - f) * D(dist, sX));
        if (w > 0.) { acc += texture2D(tSrc, uv).rgb * w; ws += w; }
      }
      c = acc / ws;
    }
    gl_FragColor = vec4(c, 1.);
  }`;
const ACC = /* glsl */`
  uniform sampler2D tSrc, tVel, tNeigh; uniform float uW, uVel, uSeed; uniform vec2 uRes, uTiles; varying vec2 vUv;
  // Вес — плотность размазанной точки с площадью 1: тонкий стебель, смазанный на 9 пикселей, даёт каждому 1/9 своей
  // яркости, а не почти всю. Форма — квадратичный B-сплайн с шагом r = сдвиг за подкадр: копии соседних подкадров
  // складываются в ровную полку даже когда настоящий шаг на 20–30% больше расчётного (трава ещё и сама качается,
  // а скорости знают только камеру); треугольник при таком расхождении давал «шторку» из отдельных линий.
  // Точка медленнее пикселя не размазывается: её вклад уже дал сам пиксель (иначе близкий отсчёт перевешивал и шумел).
  float T(float d, float r) {
    if (r <= 1.) return 0.;
    float x = d / r;
    return (x < 0.5 ? 0.75 - x * x : x < 1.5 ? 0.5 * (1.5 - x) * (1.5 - x) : 0.) / r;
  }
  void main() {
    vec4 c0 = texture2D(tSrc, vUv); vec3 c = c0.rgb;
    if (uVel > 0.) {
      vec2 vN = texture2D(tNeigh, (floor(gl_FragCoord.xy / ${TILE}.) + 0.5) / uTiles).xy; float lN = length(vN);
      if (lN > 0.5) {
        vec4 X = texture2D(tVel, vUv); float rX = length(X.xy);
        float ws = 1. / max(rX, 1.); vec3 acc = c * ws;
        float n = clamp(ceil(1.5 * lN), ${TAPS}., ${TAPS_MAX}.), dl = 3. * lN / n;    // dl — длина участка на отсчёт, пиксели
        // смещение отсчётов своё у каждого пикселя и подкадра, белый шум без узора: решётчатый градиентный шум
        // при сдвиге копий на одинаковый шаг складывался с ними в «кирпичную кладку» на стеблях у объектива
        vec3 p3 = fract(vec3(gl_FragCoord.xy, uSeed + 0.5) * 0.1031); p3 += dot(p3, p3.zyx + 31.32);
        float j = fract((p3.x + p3.y) * p3.z);
        for (int i = 0; i < ${TAPS_MAX}; i++) {
          if (float(i) >= n) break;
          vec2 o = vN * ((float(i) + j) / n * 2. - 1.) * 1.5; float dist = length(o);
          vec2 uv = vUv + o / uRes;
          vec4 Y = texture2D(tVel, uv); float rY = length(Y.xy);
          float ext = 0.02 + 0.05 * min(X.z, Y.z);
          float f = clamp(1. - (Y.z - X.z) / ext, 0., 1.), b = clamp(1. - (X.z - Y.z) / ext, 0., 1.);
          // f — отсчёт ближе или там же: он размазан сюда по своей скорости; b·(1−f) — отсчёт дальше: виден сквозь
          // смазанный край самого пикселя
          float a = dl * (f * T(dist, rY) + b * (1. - f) * T(dist, rX));
          if (a > 0.) { acc += texture2D(tSrc, uv).rgb * a; ws += a; }
        }
        c = acc / ws;
      }
    }
    gl_FragColor = vec4(c * uW, 1.);
  }`;

// объект движется сам: его альфа 0 в кадре мира, размытие по фону его не трогает (только для непрозрачных материалов)
export function markMoving(material) {
  const prev = material.onBeforeCompile, key = material.customProgramCacheKey?.bind(material);
  material.onBeforeCompile = (sh, r) => {
    prev?.call(material, sh, r);
    sh.fragmentShader = sh.fragmentShader.replace('#include <dithering_fragment>', '#include <dithering_fragment>\n gl_FragColor.a = 0.0;');
  };
  material.customProgramCacheKey = () => (key ? key() : '') + '|moving';
  material.needsUpdate = true;
  return material;
}

export function makeAccum(THREE, { W, H }) {
  const nearest = { minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter, type: THREE.HalfFloatType };
  const rtWorld = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType, depthTexture: new THREE.DepthTexture(W, H, THREE.FloatType) });
  const rtAcc = new THREE.WebGLRenderTarget(W, H, { type: THREE.FloatType }), rtDof = new THREE.WebGLRenderTarget(W, H, { type: THREE.HalfFloatType });
  const rtVel = new THREE.WebGLRenderTarget(W, H, nearest), TW = Math.ceil(W / TILE), TH = Math.ceil(H / TILE);
  const rtTile = new THREE.WebGLRenderTarget(TW, TH, nearest), rtNeigh = new THREE.WebGLRenderTarget(TW, TH, nearest);
  const res = new THREE.Vector2(W, H), tiles = new THREE.Vector2(TW, TH), cam = new THREE.Camera();
  const quad = (fs, uniforms) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(2, 2), new THREE.ShaderMaterial({ vertexShader: VS, fragmentShader: fs, uniforms, depthTest: false, depthWrite: false }));
    m.frustumCulled = false; const s = new THREE.Scene(); s.add(m); return s;
  };
  const velU = { tSrc: { value: rtWorld.texture }, tDepth: { value: rtWorld.depthTexture }, uRes: { value: res }, uNear: { value: 0.1 }, uFar: { value: 1000 },
    uCoc: { value: new THREE.Vector3() }, uInvVP: { value: new THREE.Matrix4() }, uPrevVP: { value: new THREE.Matrix4() }, uNextVP: { value: new THREE.Matrix4() } };
  const dofU = { tSrc: { value: rtWorld.texture }, tVel: { value: rtVel.texture }, tNeigh: { value: rtNeigh.texture }, uSeed: { value: 0 }, uRes: { value: res }, uTiles: { value: tiles } };
  const accU = { tSrc: { value: rtWorld.texture }, tVel: { value: rtVel.texture }, tNeigh: { value: rtNeigh.texture }, uW: { value: 1 }, uVel: { value: 0 }, uSeed: { value: 0 },
    uRes: { value: res }, uTiles: { value: tiles } };
  const velScene = quad(VEL, velU), tileScene = quad(TILEMAX, { tVel: { value: rtVel.texture }, uRes: { value: res } });
  const neighScene = quad(NEIGH, { tTile: { value: rtTile.texture }, uTiles: { value: tiles } }), dofScene = quad(DOFG, dofU), accScene = quad(ACC, accU);
  const accMat = accScene.children[0].material; accMat.blending = THREE.AdditiveBlending; accMat.transparent = true;
  const vp = (c, out) => out.multiplyMatrices(c.projectionMatrix, c.matrixWorldInverse);
  return {
    texture: rtAcc.texture,
    // pose(k) ставит мир и камеру подкадра k и возвращает [камера начала, камера конца подкадра, { k, focus }?] или null;
    // { k, focus } — кружок нерезкости подкадра k·|z − focus|/z пикселей (engine/lens.js cocK), без него боке не досглаживается
    render(renderer, scene, camera, { n = 1, pose } = {}) {
      const target = renderer.getRenderTarget(), clear = renderer.autoClear, cc = renderer.getClearColor(new THREE.Color()), ca = renderer.getClearAlpha();
      accU.uW.value = 1 / n;
      renderer.setRenderTarget(rtAcc); renderer.setClearColor(0x000000, 1); renderer.clear(); renderer.setClearColor(cc, ca);
      for (let k = 0; k < n; k++) {
        const nb = pose?.(k);
        renderer.autoClear = true; renderer.setRenderTarget(rtWorld); renderer.render(scene, camera);
        accU.uVel.value = nb ? 1 : 0; accU.uSeed.value = k;
        if (nb) {
          camera.updateMatrixWorld(); vp(camera, velU.uInvVP.value).invert(); vp(nb[0], velU.uPrevVP.value); vp(nb[1], velU.uNextVP.value);
          velU.uNear.value = camera.near; velU.uFar.value = camera.far;
          const d = nb[2]; velU.uCoc.value.set(d ? d.k : 0, d ? d.focus : 1, 0.886 / Math.sqrt(n));
          renderer.setRenderTarget(rtVel); renderer.render(velScene, cam);
          renderer.setRenderTarget(rtTile); renderer.render(tileScene, cam);
          renderer.setRenderTarget(rtNeigh); renderer.render(neighScene, cam);
          dofU.uSeed.value = k; renderer.setRenderTarget(rtDof); renderer.render(dofScene, cam);
        }
        accU.tSrc.value = nb ? rtDof.texture : rtWorld.texture;
        renderer.setRenderTarget(rtAcc); renderer.autoClear = false; renderer.render(accScene, cam);
      }
      renderer.autoClear = clear; renderer.setRenderTarget(target);
      return rtAcc.texture;
    },
  };
}
