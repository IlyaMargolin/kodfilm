# «Живая живопись» 2.5D: один нарисованный опорный кадр + карта глубины -> план с движением камеры.
# Без видеомодели: кадр режется на слои по глубине, дыры за ближними слоями достраиваются, каждый слой двигается
# по своей глубине (параллакс), поверх идут мазки-дымка, пылинки, дыхание света и зерно. Детерминированно, на CPU.
# python3 studio/parallax25d.py KEY.png DEPTH.png OUT.mp4 '{"frames":48,"tz":0.06,"tx":0.02,"ty":0,"drift":0.012,"haze":0.18,"dust":250}'
import sys, json, subprocess, numpy as np, cv2
KEY, DEP, OUT = sys.argv[1:4]; P = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
N = P.get('frames', 48); L = P.get('layers', 12); OW, OH = P.get('out', [1280, 720])
img = cv2.imread(KEY, cv2.IMREAD_COLOR).astype(np.float32) / 255
H, W = img.shape[:2]
d = cv2.imread(DEP, cv2.IMREAD_UNCHANGED).astype(np.float32); d = cv2.resize(d, (W, H)); d = (d - d.min()) / max(1e-6, d.max() - d.min())
d = cv2.bilateralFilter(d, 9, 0.08, 7)                      # глубина без ступенек внутри объекта, края держит
rng = np.random.default_rng(P.get('seed', 3))

def fill(rgb, valid):                                      # push-pull: достроить цвет в дырах по пирамиде
    pyr = [(rgb * valid[..., None], valid.astype(np.float32))]
    while min(pyr[-1][1].shape) > 4:
        c, w = pyr[-1]; pyr.append((cv2.pyrDown(c), cv2.pyrDown(w)))
    c, w = pyr[-1]; est = c / np.maximum(w, 1e-6)[..., None]
    for c, w in reversed(pyr[:-1]):
        up = cv2.resize(est, (w.shape[1], w.shape[0]), interpolation=cv2.INTER_LINEAR)
        a = np.clip(w * 4, 0, 1)[..., None]; est = c / np.maximum(w, 1e-6)[..., None] * a + up * (1 - a)
    return np.where(valid[..., None] > 0.5, rgb, est)

qs = np.quantile(d, np.linspace(0, 1, L + 1)); qs[-1] += 1e-3
layers = []
for i in range(L):
    behind = (d < qs[i + 1]).astype(np.float32)
    m = ((d >= qs[i]) & (d < qs[i + 1])).astype(np.float32)
    m = cv2.dilate(m, np.ones((5, 5), np.uint8)) if i > 0 else np.ones_like(m)
    m = cv2.GaussianBlur(m, (0, 0), 1.2) * (1 if i > 0 else 1)
    rgb = fill(img, cv2.erode(behind, np.ones((3, 3), np.uint8)) if i > 0 else np.ones_like(behind))
    z = float(np.median(d[(d >= qs[i]) & (d < qs[i + 1])])) if i > 0 else float(qs[1] * 0.5)
    layers.append((rgb, m, z))

# мазки-дымка: шум, размазанный вдоль ветра, цвет из светлой дали кадра
def strokes(w, h, seed):
    r = np.random.default_rng(seed); t = np.zeros((h, w), np.float32)
    for _ in range(900):
        x, y = r.integers(0, w), r.integers(0, h); ln, th = r.integers(40, 260), r.integers(3, 16)
        cv2.rectangle(t, (int(x), int(y)), (int(x + ln), int(y + th)), float(r.uniform(0.2, 1)), -1)
    t = cv2.GaussianBlur(t, (0, 0), 3); k = np.zeros((1, 61), np.float32); k[0] = 1 / 61
    t = cv2.filter2D(t, -1, k); t = cv2.GaussianBlur(t, (0, 0), 1.0)
    return (t - t.min()) / max(1e-6, t.max() - t.min())
HZ = strokes(W * 2, H, P.get('seed', 3)); hz_col = np.array(P.get('haze_color') or np.percentile(img.reshape(-1, 3), 85, axis=0), np.float32)
hz_mask = np.clip(1 - d * 1.4, 0, 1) ** 1.2                 # дымка гуще вдали, у переднего плана тает
dust = rng.uniform(0, 1, (P.get('dust', 200), 4))           # x, y, глубина, фаза
ff = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgr24', '-s', f'{OW}x{OH}', '-r', str(P.get('fps', 24)), '-i', '-',
                       '-c:v', 'libx264', '-preset', 'slow', '-crf', '14', '-pix_fmt', 'yuv420p', OUT], stdin=subprocess.PIPE)
ss = lambda x: x * x * (3 - 2 * x)
for f in range(N):
    u = f / max(1, N - 1); e = ss(u) * 0.6 + u * 0.4      # мягкий старт, без остановки в конце
    tz, tx, ty = P.get('tz', 0.05) * e, P.get('tx', 0.02) * e, P.get('ty', 0.0) * e
    acc = np.zeros_like(img)
    cx, cy = W * P.get('focus', [0.5, 0.5])[0], H * P.get('focus', [0.5, 0.5])[1]
    for i, (rgb, m, z) in enumerate(layers):
        zz = 0.15 + 0.85 * z                              # обратная глубина: небо почти не двигается
        s = 1 / (1 - tz * zz); dx = -tx * zz * W + (P.get('drift', 0) * u * W if i == 0 else 0); dy = -ty * zz * H
        M = np.float32([[s, 0, (1 - s) * cx + dx], [0, s, (1 - s) * cy + dy]])
        r = cv2.warpAffine(rgb, M, (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
        a = cv2.warpAffine(m, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)[..., None]
        acc = r if i == 0 else acc * (1 - a) + r * a
        if i == L // 3 and P.get('haze', 0) > 0:          # дымка между дальним и средним планом
            off = int((P.get('haze_speed', 0.06) * u) * W) % W
            hz = HZ[:, off:off + W] * hz_mask * P['haze'] * (0.85 + 0.15 * np.sin(6.28 * (u + 0.2)))
            acc = acc * (1 - hz[..., None]) + hz_col * hz[..., None]
    for x, y, z, ph in dust:                              # пылинки: ближние крупнее, быстрее, размытее
        px = ((x + P.get('wind', 0.05) * u * (0.3 + z) + 0.003 * np.sin(6.28 * (u * 2 + ph))) % 1) * W
        py = ((y - 0.02 * u + 0.004 * np.cos(6.28 * (u * 1.5 + ph))) % 1) * H
        rr = 0.6 + 2.2 * z ** 2; c = hz_col * (0.9 + 0.3 * ph)
        cv2.circle(acc, (int(px), int(py)), max(1, int(rr)), tuple(float(v) for v in c), -1, cv2.LINE_AA)
    acc *= 1 + P.get('breath', 0.03) * np.sin(6.28 * (u * 0.7 + 0.1))
    y0, x0 = (H - int(W * OH / OW)) // 2, 0
    fr = cv2.resize(acc[max(0, y0):max(0, y0) + int(W * OH / OW)], (OW, OH), interpolation=cv2.INTER_AREA)
    yy, xx = np.mgrid[0:OH, 0:OW]; vig = 1 - 0.28 * (((xx - OW / 2) / OW) ** 2 + ((yy - OH / 2) / OH) ** 2) * 2.2
    fr = fr * vig[..., None] + np.random.default_rng(1000 + f).normal(0, 0.012, (OH, OW, 1)).astype(np.float32)
    ff.stdin.write((np.clip(fr, 0, 1) * 255).astype(np.uint8).tobytes())
ff.stdin.close(); ff.wait(); print('ok', OUT, N, 'frames')
