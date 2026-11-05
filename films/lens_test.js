// Проверка затвора и объектива ядра (engine/lens.js, engine/accum.js). 3 секунды.
// 0–1.5 с: камера стоит у обочины в траве, мотоцикл с фарой едет на неё и пролетает мимо: фара — ровный штрих, а не копии.
// 1.5–3 с: камера едет низко за мотоциклом сквозь стебли: стебли у объектива — мягкие полосы, а не «гребёнка»,
// фон за мотоциклом размыт по правилу диафрагмы для среднего плана.
import { makeShutter } from '/engine/lens.js';
import { markMoving } from '/engine/accum.js';

const V = 22;                                                       // м/с, ~80 км/ч
export default {
  fps: 24, duration: 3, letterbox: 0, bloom: { strength: 0.25, radius: 0.6, threshold: 1.2 },
  async build({ THREE, scene, camera, W, H, rand }) {
    scene.background = new THREE.Color(0x8a6e8c); scene.fog = new THREE.Fog(0x8a6e8c, 30, 160);
    camera.fov = 40; camera.near = 0.05; camera.far = 400; camera.updateProjectionMatrix();
    const sun = new THREE.DirectionalLight(0xffc89a, 3); sun.position.set(-10, 8, 40); scene.add(sun);
    scene.add(new THREE.HemisphereLight(0x9a88b0, 0x302018, 0.6));
    scene.add(new THREE.Mesh(new THREE.PlaneGeometry(400, 400).rotateX(-Math.PI / 2), new THREE.MeshStandardMaterial({ color: 0x2a2018, roughness: 1 })));
    // дальние столбы и тонкие стебли у трассы
    const rock = new THREE.MeshStandardMaterial({ color: 0x4a3c36, roughness: 0.9 });
    for (let i = 0; i < 40; i++) { const m = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.9, 6 + rand() * 6, 8), rock); m.position.set((rand() < 0.5 ? -1 : 1) * (8 + rand() * 20), 4, 120 - i * 8); scene.add(m); }
    const stemMat = new THREE.MeshStandardMaterial({ color: 0xd8b060, roughness: 0.7 });
    const stemGeo = new THREE.CylinderGeometry(0.002, 0.003, 0.8, 5).translate(0, 0.4, 0);
    const stems = new THREE.InstancedMesh(stemGeo, stemMat, 3000), m4 = new THREE.Matrix4();
    for (let i = 0; i < 3000; i++) { const x = (rand() < 0.5 ? -1 : 1) * (0.25 + rand() * 4), z = 60 - rand() * 90, s = 0.6 + rand() * 0.6;
      stems.setMatrixAt(i, m4.makeScale(s, s, s).setPosition(x, 0, z)); }
    scene.add(stems);
    // «мотоцикл»: корпус и яркая фара; движется сам — помечен
    const bike = new THREE.Group();
    bike.add(new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.9, 1.8).translate(0, 0.75, 0), markMoving(new THREE.MeshStandardMaterial({ color: 0x401010, roughness: 0.5 }))));
    bike.add(new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 8).translate(0, 0.95, 0.92), markMoving(new THREE.MeshBasicMaterial({ color: new THREE.Color(9, 8, 6) }))));
    scene.add(bike);
    const head = new THREE.Vector3();
    // мир и камера в момент tt; возвращает дистанцию фокуса до мотоцикла
    const place = (tt, cam) => {
      bike.position.set(1.2, 0, -30 + V * tt);
      if (tt < 1.5) { cam.position.set(2.0, 0.35, 0); cam.lookAt(1.0, 0.8, -6); }
      else { cam.position.set(1.4, 0.6, bike.position.z - 5); cam.lookAt(bike.position.x, 0.9, bike.position.z + 6); }
      cam.updateMatrixWorld();
      return { focus: cam.position.distanceTo(bike.localToWorld(head.set(0, 0.9, 0))) };
    };
    const shutter = makeShutter(THREE, camera, { W, H, fps: 24 });
    const probe = () => [bike.localToWorld(new THREE.Vector3(0, 0.95, 0.92)), bike.localToWorld(new THREE.Vector3(0, 0.75, -0.9))];
    return {
      update(t) { place(t, camera); },
      subframes(t) {
        const { L, n } = shutter.plan(t, place, { fov: camera.fov, size: t < 1.5 ? 'FS' : 'MS', bg: 40 }, probe);
        console.log('N', t.toFixed(3), n, L.N.toFixed(1));
        return { n, pose: shutter.pose(t, n, place, L) };
      },
    };
  },
};
