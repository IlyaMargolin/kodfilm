// «Мост» — тест стиля «мел на чёрном». 18 секунд.
// Человечек подходит к обрыву. Чтобы построить мост, он отдаёт ему свои линии.
import { makeChalk, mixPose } from '/engine/chalk.js';
const cl = (x) => Math.min(1, Math.max(0, x));
const sm = (a, b, x) => { const t = cl((x - a) / (b - a)); return t * t * (3 - 2 * t); };

export default {
  kind: '2d', fps: 60, duration: 18,
  titles: [{ text: 'Чтобы перейти, приходится отдать часть себя.', in: 14.6, out: 18, y: 0.86, size: 0.032, color: '#ecebe4' }],
  async build({ g, W, H }) {
    const C = makeChalk(g, W, H, 3);
    const U = C.U, cx = W / 2, ground = H * 0.68;
    const gapL = cx - 150 * U, gapR = cx + 150 * U;
    return (t, frame) => {
      C.begin(frame, 60);
      // земля рисуется слева направо
      const gd = sm(0.2, 2.2, t);
      C.stroke([[0, ground], [gapL, ground]], { partial: cl(gd * 2), k: 1 });
      C.stroke([[gapR, ground], [W, ground]], { partial: cl(gd * 2 - 1), k: 2 });
      // пропасть: стенки и штриховка в глубину
      const dp = sm(1.2, 3.0, t);
      C.stroke([[gapL, ground], [gapL - 6 * U, ground + 400 * U * dp]], { k: 3, w: 2.6 });
      C.stroke([[gapR, ground], [gapR + 8 * U, ground + 400 * U * dp]], { k: 4, w: 2.6 });
      if (dp > 0.3) { g.save(); g.globalAlpha = dp; C.hatch(gapL - 2 * U, ground + 4 * U, gapL + 26 * U, ground + 380 * U * dp, 9); C.hatch(gapR - 26 * U, ground + 4 * U, gapR + 2 * U, ground + 380 * U * dp, 9); g.restore(); }
      // травинки
      for (const [x, k] of [[cx - 600 * U, 11], [cx - 340 * U, 12], [cx + 420 * U, 13], [cx + 700 * U, 14]]) {
        if (gd < 0.5 + (x - cx) / W) continue;
        C.stroke([[x, ground], [x - 5 * U, ground - 14 * U]], { k, w: 1.8 }); C.stroke([[x + 4 * U, ground], [x + 7 * U, ground - 12 * U]], { k: k + 1, w: 1.8 });
      }
      C.text('Здесь', cx - 520 * U, H * 0.14, 64, sm(2.0, 3.0, t));
      C.text('Там', cx + 520 * U, H * 0.14, 64, sm(2.4, 3.4, t));

      // ---------- человечек ----------
      const stand = { hipL: 0.08, hipR: -0.08, armL: 0.18, armR: -0.18, elbL: 0.05, elbR: -0.05 };
      let x, pose, face = {}, fig = { alpha: sm(2.6, 3.2, t), k: 30, scale: 1.9 };
      const edge = gapL - 120 * U;
      // 1) идёт к краю (3.2 – 6.5)
      const walkT = sm(3.2, 6.5, t);
      x = (cx - 760 * U) + (edge - (cx - 760 * U)) * walkT;
      pose = walkT > 0 && walkT < 1 ? C.walkPose((t - 3.2) * 0.9, Math.min(1, (1 - walkT) * 6, walkT * 8)) : stand;
      // 2) смотрит вниз, тревога (6.5 – 8.5)
      const down = sm(6.6, 7.4, t) * (1 - sm(8.4, 9.0, t));
      if (t > 6.5) { pose = mixPose(stand, { ...stand, lean: 0.12, headTilt: 0.25 }, down); face = { lookY: down, look: 0.6 * down, worry: down, mouth: -down }; }
      // 3) смотрит на руку, решается (9 – 10.2)
      const hand = sm(9.0, 9.6, t) * (1 - sm(10.2, 10.6, t));
      if (t > 9) { pose = mixPose(pose, { ...stand, armL: 1.6, elbL: 0.9, headTilt: -0.1 }, hand); face = { look: 1 * hand, lookY: 0.4 * hand, worry: 0.5, mouth: -0.3 }; }
      // 4) мост растёт из его руки, сам он бледнеет (10.6 – 13)
      const build = sm(10.6, 13.0, t);
      const reach = { ...stand, armL: 1.45, elbL: 0.15, lean: 0.06 };
      if (t > 10.4 && t < 13.2) { pose = mixPose(pose, reach, sm(10.4, 10.8, t)); face = { look: 1, worry: 0.3, mouth: 0 }; }
      fig.alpha *= 1 - 0.65 * build;
      // 5) переходит по мосту (13 – 15.5), на той стороне линии возвращаются
      const cross = sm(13.2, 15.6, t);
      if (t > 13.2) {
        x = edge + (gapR + 170 * U - edge) * cross;
        pose = cross < 1 ? C.walkPose((t - 13.2) * 1.1, Math.min(1, (1 - cross) * 6, cross * 8)) : stand;
        fig.alpha = sm(2.6, 3.2, t) * (0.35 + 0.65 * sm(15.4, 16.6, t));
        face = { look: cross < 1 ? 1 : 0, mouth: sm(15.8, 16.6, t), worry: 0 };
      }
      face.blink = (frame % 260) > 252;
      // мост: доска с верёвкой, её линии «вытягиваются» из руки
      if (build > 0) {
        const y = ground - 2 * U, sag = 18 * U;
        const pts = []; for (let i = 0; i <= 20; i++) { const u = i / 20; pts.push([gapL - 10 * U + (gapR - gapL + 20 * U) * u, y + Math.sin(u * Math.PI) * sag]); }
        C.stroke(pts, { partial: build, k: 60, w: 3 });
        for (let i = 1; i < 12; i++) { const u = i / 12; if (u > build) break; const px = gapL + (gapR - gapL) * u, py = y + Math.sin(u * Math.PI) * sag;
          C.stroke([[px, py - 6 * U], [px, py + 6 * U]], { k: 70 + i, w: 2.2 }); }
      }
      const yF = (t > 13.2 && cross > 0 && cross < 1) ? ground + Math.sin(cl((x - gapL) / (gapR - gapL)) * Math.PI) * 18 * U : ground;
      const parts = C.figure(x, yF, pose, { ...fig, face });
      // линия от руки к краю моста, пока строит
      if (build > 0 && build < 1) C.stroke([parts.hdL, [gapL - 10 * U + (gapR - gapL) * build, ground]], { k: 90, w: 1.6, alpha: 0.5 });
      // на той стороне вырастает цветок
      const fl = sm(16.0, 17.2, t);
      if (fl > 0) { const fx = gapR + 330 * U; C.stroke([[fx, ground], [fx + 3 * U, ground - 46 * U]], { partial: fl, k: 95 });
        if (fl > 0.7) for (let i = 0; i < 5; i++) { const a = i / 5 * Math.PI * 2; C.circle(fx + 3 * U + Math.cos(a) * 9 * U, ground - 52 * U + Math.sin(a) * 9 * U, 6 * U, { k: 96 + i, w: 1.8, alpha: sm(0.7, 1, fl) }); } }
    };
  },
};
