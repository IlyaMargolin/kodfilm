# Черновой аниматик Jack Rider: выбранный опорный кадр каждого плана -> 2.5D «живая картина» -> склейка.
# python3 animatic.py SHOTS.json PICKS.json FAILS.json SRC_DIRS(comma) OUTDIR
# Планы с браком (FAILS) идут тёмной паузой нужной длины, чтобы в черновик не попал ни один неверный кадр.
import sys, json, glob, re, os, subprocess, numpy as np, cv2
from concurrent.futures import ProcessPoolExecutor
SHOTS, PICKS, FAILS, SRC, OUT = sys.argv[1:6]
shots = json.load(open(SHOTS)); picks = json.load(open(PICKS)); fails = json.load(open(FAILS))
src = {}
for d in SRC.split(','):
    for f in glob.glob(f'{d}/out/j*_s*.png'):
        if 'depth' in f: continue
        k = re.search(r'(j\d+)_s(\d+)', f).group(1); src.setdefault(k, []).append(f)
for k in src: src[k].sort()
PAR = '/home/user/kodfilm/studio/parallax25d.py'
os.makedirs(f'{OUT}/shots', exist_ok=True); os.makedirs(f'{OUT}/graded', exist_ok=True)
W, H, FPS = 1280, 720, 24
MOVES = [dict(tz=0.07, tx=0.0), dict(tz=0.03, tx=0.03), dict(tz=0.05, tx=-0.025), dict(tz=-0.04, tx=0.01), dict(tz=0.02, ty=0.02, tx=0.0)]

def unbar(img):                            # срезать чёрные полосы, которые иногда рисует модель, и вернуть 16:9
    h, w = img.shape[:2]; r = img.mean(axis=(1, 2)); c = img.mean(axis=(0, 2))
    t = 0
    while t < h // 6 and r[t] < 12: t += 1
    b = h
    while b > h - h // 6 and r[b - 1] < 12: b -= 1
    l = 0
    while l < w // 6 and c[l] < 12: l += 1
    rr = w
    while rr > w - w // 6 and c[rr - 1] < 12: rr -= 1
    t, b, l, rr = t + 2 * (t > 0), b - 2 * (b < h), l + 2 * (l > 0), rr - 2 * (rr < w)
    ch, cw = b - t, rr - l
    if cw / ch > w / h: nw = int(ch * w / h); l += (cw - nw) // 2; cw = nw
    else: nh = int(cw * h / w); t += (ch - nh) // 2; ch = nh
    return cv2.resize(img[t:t + ch, l:l + cw], (w, h), interpolation=cv2.INTER_CUBIC), (t, l, ch, cw)

def grade(img, tod):                       # единый вид: ночь не кислотно-синяя, а сине-чёрная
    x = img.astype(np.float32) / 255
    hsv = cv2.cvtColor(x, cv2.COLOR_BGR2HSV)
    if tod == 'ночь':
        hsv[..., 1] *= 0.62; hsv[..., 2] = hsv[..., 2] ** 1.25 * 0.92
    elif tod in ('ливень',):
        hsv[..., 1] *= 0.75
    else:
        hsv[..., 1] *= 0.9
    return (np.clip(cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), 0, 1) * 255).astype(np.uint8)

def one(s):
    k = f"j{s['n']:03d}"; out = f"{OUT}/shots/{k}.mp4"; frames = s['sec'] * FPS
    if os.path.exists(out): return out
    if k in fails or k not in src or k not in picks:
        subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', f'color=c=0x0b0b0e:s={W}x{H}:r={FPS}', '-t', str(s['sec']),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', out], check=True)
        return out
    f = src[k][picks[k]]; dep = f.replace('.png', '_depth.png')
    g = f"{OUT}/graded/{k}.png"; im, (t, l, ch, cw) = unbar(cv2.imread(f)); cv2.imwrite(g, grade(im, s['tod']))
    dm = cv2.imread(dep, cv2.IMREAD_UNCHANGED); dh, dw = dm.shape[:2]; sy, sx = dh / im.shape[0], dw / im.shape[1]
    dm = cv2.resize(dm[int(t * sy):int((t + ch) * sy), int(l * sx):int((l + cw) * sx)], (dw, dh)); dep = f"{OUT}/graded/{k}_depth.png"; cv2.imwrite(dep, dm)
    p = dict(MOVES[s['n'] % len(MOVES)], frames=frames, out=[W, H], fps=FPS, seed=s['n'], dust=120,
             haze=0.12 if s['tod'] != 'ночь' else 0.06, drift=0.006)
    subprocess.run(['python3', PAR, g, dep, out, json.dumps(p)], check=True)
    return out

if __name__ == '__main__':
    with ProcessPoolExecutor(4) as ex: outs = list(ex.map(one, shots))
    with open(f'{OUT}/list.txt', 'w') as fh:
        for o in outs: fh.write(f"file '{os.path.abspath(o)}'\n")
    subprocess.run(['ffmpeg', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', f'{OUT}/list.txt', '-c:v', 'libx264', '-crf', '21',
                    '-pix_fmt', 'yuv420p', '-preset', 'medium', f'{OUT}/jack7_animatic.mp4'], check=True)
    print('DONE', f'{OUT}/jack7_animatic.mp4')
