// «Точка» — прототип, 32 секунды.
// Точка → рой → мир-сетка → монолит и человек → снова точка.
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

export default {
  fps: 60,
  duration: 32,
  seed: 7,
  letterbox: 0.115,
  bloom: { strength: 1.25, radius: 0.7, threshold: 0.12 },
  fade: (t) => smooth(0, 1.5, t) * (1 - smooth(30.5, 32, t)),
  titles: [
    { text: 'В начале была точка.', in: 1.2, out: 5.0 },
    { text: 'Точка захотела увидеть себя', in: 7.5, out: 11.5 },
    { text: 'и стала миром.', in: 13.0, out: 16.5 },
    { text: 'Мир — это код, который читает сам себя.', in: 21.0, out: 25.5 },
    { text: 'Т О Ч К А', in: 28.6, out: 32, y: 0.66, size: 0.05, weight: 200, spacing: 0.3, fade: 1.0 },
  ],

  async build({ THREE, scene, camera, rand }) {
    scene.background = new THREE.Color(0x020306);
    scene.fog = new THREE.FogExp2(0x020306, 0.022);

    // ---------- частицы: одна геометрия, несколько «состояний» в атрибутах ----------
    const N = 24000;
    const pos = new Float32Array(N * 3), sph = new Float32Array(N * 3), pla = new Float32Array(N * 3), rnd = new Float32Array(N * 4);
    for (let i = 0; i < N; i++) {
      // сфера-рой (по Фибоначчи, с толщиной)
      const k = i + 0.5, phi = Math.acos(1 - 2 * k / N), th = Math.PI * (1 + Math.sqrt(5)) * k;
      const r = 2.2 + (rand() - 0.5) * 0.5;
      sph.set([r * Math.sin(phi) * Math.cos(th), 2.2 + r * Math.cos(phi), r * Math.sin(phi) * Math.sin(th)], i * 3);
      // плоскость-сетка: точки на линиях решётки
      const line = Math.floor(rand() * 41), along = (rand() - 0.5) * 40, across = (line - 20) * 1.0;
      const onX = rand() < 0.5;
      pla.set(onX ? [along, 0, across] : [across, 0, along], i * 3);
      rnd.set([rand(), rand(), rand(), rand()], i * 4);
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
    geo.setAttribute('aSphere', new THREE.BufferAttribute(sph, 3));
    geo.setAttribute('aPlane', new THREE.BufferAttribute(pla, 3));
    geo.setAttribute('aRand', new THREE.BufferAttribute(rnd, 4));
    const pu = { uT: { value: 0 }, uBurst: { value: 0 }, uWorld: { value: 0 }, uCollapse: { value: 0 }, uSize: { value: 1 } };
    const pmat = new THREE.ShaderMaterial({
      uniforms: pu, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: `
        uniform float uT, uBurst, uWorld, uCollapse, uSize;
        attribute vec3 aSphere, aPlane; attribute vec4 aRand;
        varying float vA; varying vec3 vC;
        float st(float e0, float e1, float x){ return smoothstep(e0, e1, x); }
        void main(){
          vec3 seed = vec3(0., 2.2, 0.) + (aRand.xyz-0.5)*0.02;
          float b = st(aRand.w*0.35, 0.65+aRand.w*0.35, uBurst);
          vec3 swirl = vec3(sin(uT*0.7+aRand.x*40.), cos(uT*0.5+aRand.y*40.), sin(uT*0.6+aRand.z*40.)) * 0.18 * b;
          vec3 p = mix(seed, aSphere + swirl, b);
          float w = st(aRand.x*0.5, 0.5+aRand.x*0.5, uWorld);
          vec3 arc = vec3(0., sin(w*3.14159)*1.5*(aRand.y+0.3), 0.);
          p = mix(p, aPlane, w) + arc;
          // «код» бежит по сетке
          p += vec3(0., 0., 0.) ; 
          float c = st(aRand.z*0.4, 0.6+aRand.z*0.4, uCollapse);
          p = mix(p, seed, c);
          vec4 mv = modelViewMatrix * vec4(p, 1.);
          gl_Position = projectionMatrix * mv;
          float pulse = 0.5 + 0.5*sin(uT*2.0 + aPlane.x*0.7 + aPlane.z*0.3 - uT*3.0);
          gl_PointSize = uSize * (1.2 + aRand.y*1.6) * (18.0 / -mv.z);
          vA = mix(0.55, 0.35 + 1.4*pow(pulse, 6.0), w*(1.-c)) * (0.6 + 0.4*aRand.w);
          vA *= mix(0.01, 1.0, b) * mix(1.0, 0.01, c);   // в точке частицы почти прозрачны: иначе пересвет
          vC = mix(vec3(1.0,0.86,0.66), vec3(0.55,0.75,1.0), w*(1.-c)*aRand.x);
        }`,
      fragmentShader: `
        varying float vA; varying vec3 vC;
        void main(){ vec2 q = gl_PointCoord-0.5; float d = length(q); if(d>0.5) discard;
          float a = smoothstep(0.5, 0.0, d); gl_FragColor = vec4(vC * a * vA, a*vA); }`,
    });
    const points = new THREE.Points(geo, pmat);
    points.frustumCulled = false;
    scene.add(points);

    // мягкое свечение: спрайт с радиальным градиентом (круглее и стабильнее, чем пересвеченный bloom)
    const glowTex = (() => { const c = document.createElement('canvas'); c.width = c.height = 256;
      const g = c.getContext('2d'), gr = g.createRadialGradient(128, 128, 0, 128, 128, 128);
      gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(0.15, 'rgba(255,255,255,0.45)');
      gr.addColorStop(0.45, 'rgba(255,255,255,0.08)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
      g.fillStyle = gr; g.fillRect(0, 0, 256, 256); return new THREE.CanvasTexture(c); })();
    const glow = (color, s) => { const m = new THREE.Sprite(new THREE.SpriteMaterial({ map: glowTex, color, transparent: true,
      blending: THREE.AdditiveBlending, depthWrite: false, fog: false })); m.scale.setScalar(s); return m; };

    // ---------- точка-ядро ----------
    const core = new THREE.Mesh(new THREE.SphereGeometry(0.06, 32, 16), new THREE.MeshBasicMaterial({ color: new THREE.Color(1.3, 1.15, 0.95) }));
    core.position.set(0, 2.2, 0);
    scene.add(core);
    const coreGlow = glow(0xffd9b0, 1.6); coreGlow.position.copy(core.position); scene.add(coreGlow);
    // свет за монолитом: даёт силуэт
    const backGlow = glow(0xffcf9a, 26); backGlow.position.set(0, 2.6, -9); scene.add(backGlow);

    // ---------- пол-зеркало ----------
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(200, 200),
      new THREE.MeshStandardMaterial({ color: 0x05070b, roughness: 0.35, metalness: 0.8 }));
    floor.rotation.x = -Math.PI / 2; floor.position.y = -0.01; floor.receiveShadow = true;
    scene.add(floor);

    // ---------- монолит ----------
    const mono = new THREE.Mesh(new THREE.BoxGeometry(1.1, 4.4, 0.28),
      new THREE.MeshStandardMaterial({ color: 0x020203, roughness: 0.18, metalness: 0.9 }));
    mono.castShadow = true;
    scene.add(mono);
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(mono.geometry),
      new THREE.LineBasicMaterial({ color: new THREE.Color(1.6, 1.3, 0.9), transparent: true, opacity: 0 }));
    mono.add(edge);

    // ---------- человек (силуэт) ----------
    const human = new THREE.Group();
    const dark = new THREE.MeshStandardMaterial({ color: 0x0a0a0c, roughness: 0.9 });
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.13, 0.62, 6, 16), dark);
    body.position.y = 0.5; body.castShadow = true;
    const head = new THREE.Mesh(new THREE.SphereGeometry(0.1, 24, 16), dark);
    head.position.y = 1.02; head.castShadow = true;
    human.add(body, head);
    human.position.set(1.15, 0, 3.0); human.rotation.y = -0.25;
    scene.add(human);

    // ---------- свет ----------
    scene.add(new THREE.AmbientLight(0x223044, 0.25));
    const key = new THREE.SpotLight(0xffd9a8, 0, 40, 0.5, 0.6, 1.2);
    key.position.set(0, 9, -4); key.target = mono; key.castShadow = true; key.shadow.mapSize.set(1024, 1024);
    scene.add(key);
    const rim = new THREE.PointLight(0x7fa6ff, 0, 20, 1.5);
    rim.position.set(0, 5.5, -3);
    scene.add(rim);
    const coreLight = new THREE.PointLight(0xffd8a8, 6, 12, 2);
    coreLight.position.copy(core.position);
    scene.add(coreLight);

    // ---------- камера: ключи [время, позиция, цель] с плавной интерполяцией ----------
    const V = (x, y, z) => new THREE.Vector3(x, y, z);
    const keys = [
      [0,   V(0, 2.25, 3.2),   V(0, 2.2, 0)],
      [5,   V(0.4, 2.3, 2.6),  V(0, 2.2, 0)],
      [9,   V(6.5, 3.4, 6.5),  V(0, 2.2, 0)],
      [13,  V(-7, 5.5, 8),     V(0, 1.6, 0)],
      [18,  V(-3.5, 1.4, 10),  V(0, 1.8, 0)],
      [22,  V(1.6, 1.2, 13.5), V(0.4, 1.9, 0)],
      [26.5,V(1.3, 1.05, 10.5), V(0.5, 2.1, 0)],
      [29,  V(0, 2.3, 4.5),    V(0, 2.2, 0)],
      [32,  V(0, 2.25, 3.0),   V(0, 2.2, 0)],
    ];
    const pc = new THREE.CatmullRomCurve3(keys.map(k => k[1]), false, 'centripetal');
    const tc = new THREE.CatmullRomCurve3(keys.map(k => k[2]), false, 'centripetal');
    const camAt = (t) => {
      let i = 0; while (i < keys.length - 2 && t > keys[i + 1][0]) i++;
      const a = keys[i][0], b = keys[i + 1][0];
      const local = smooth(0, 1, (t - a) / (b - a)) * 0.5 + ((t - a) / (b - a)) * 0.5;
      const u = (i + Math.min(1, Math.max(0, local))) / (keys.length - 1);
      camera.position.copy(pc.getPoint(u));
      // ручная камера: лёгкое дыхание
      camera.position.x += Math.sin(t * 0.9) * 0.015; camera.position.y += Math.sin(t * 1.3 + 1) * 0.01;
      camera.lookAt(tc.getPoint(u));
    };

    return {
      update(t) {
        pu.uT.value = t;
        pu.uBurst.value = smooth(5, 10, t);
        pu.uWorld.value = smooth(11.5, 17, t);
        pu.uCollapse.value = smooth(26.5, 30, t);
        pu.uSize.value = 1;

        const breathe = 1 + 0.25 * Math.sin(t * 2.2);
        const coreA = (1 - smooth(5, 6.5, t)) + smooth(29, 30.5, t);
        core.scale.setScalar(Math.max(0.001, coreA * breathe));
        coreLight.intensity = 6 * coreA * breathe;
        coreGlow.material.opacity = Math.min(1, coreA) * (0.75 + 0.25 * Math.sin(t * 2.2));
        coreGlow.scale.setScalar(1.4 * breathe);
        backGlow.material.opacity = 0.55 * smooth(16, 21, t) * (1 - smooth(26, 28.5, t));

        const rise = smooth(14, 20, t) * (1 - smooth(26.5, 29.5, t));
        mono.position.set(0, -2.3 + rise * 4.5, 0);
        edge.material.opacity = 0.6 * smooth(19, 21, t) * (1 - smooth(26, 27.5, t)) * (0.85 + 0.15 * Math.sin(t * 5));
        key.intensity = 40 * smooth(15, 20, t) * (1 - smooth(26.5, 29, t));
        rim.intensity = 5 * smooth(18, 21, t) * (1 - smooth(26.5, 29, t));

        const hv = smooth(16.5, 19, t) * (1 - smooth(27, 28.5, t));
        human.visible = hv > 0.01;
        human.scale.set(1, Math.max(0.001, hv), 1);
        floor.material.opacity = 1;
        floor.visible = t > 10 && t < 30.5;
        camAt(t);
      },
    };
  },
};
