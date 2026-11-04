# Автопроверка кадра (ОТК): раскадровка проверяется машиной ДО фермы, чтобы часы GPU не уходили на брак.
# Каждое правило — ошибка, которую мы уже ловили глазами:
#   focus   — диафрагма посчитана не для того расстояния (фокус «уезжал» на 13 м вместо 2: лицо мягкое, фон резкий);
#   face    — лицо в тени (поля капюшона, ключ «из-за плеча»): на крупном плане лицо должно быть светлее кадра;
#   cast    — тени перекрашены грейдом (бирюзовые тени: красный канал в тенях обнулён);
#   palette — пятен цвета больше, чем 3–4 цвета палитры: кадр «пёстрый», смысл цвета теряется.
# python studio/qc.py out/<раскадровка>   → таблица по кадрам, qc.json рядом, код выхода 1 при ошибках
import sys, os, json, glob, subprocess
import numpy as np

def load(path, w=320):
    """Кадр → массив RGB 0..1 (через ffmpeg: без PIL в окружении)."""
    h = int(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', path],
                           capture_output=True, text=True).stdout.strip().split(',')[1])
    W0 = int(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width', '-of', 'csv=p=0', path],
                            capture_output=True, text=True).stdout.strip())
    hh = max(2, int(round(h * w / W0 / 2)) * 2)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-vf', f'scale={w}:{hh}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(hh, w, 3).astype(np.float32) / 255.0

def luma(img): return img @ np.array([0.2126, 0.7152, 0.0722], np.float32)

def color_spots(img, k=8, it=12, min_area=0.04, chroma_min=0.06, seed=3):
    """Сколько различимых цветовых пятен в кадре: k-средних по цветности (без яркости), пятно — кластер ≥4% кадра
    с заметной цветностью; близкие по оттенку (<25°) кластеры сливаются — это один цвет в разных тонах."""
    X = img.reshape(-1, 3); Y = luma(img).reshape(-1, 1)
    C = X - Y                                         # цветность: отклонение от серого той же яркости
    rng = np.random.default_rng(seed); cent = C[rng.choice(len(C), k, replace=False)]
    for _ in range(it):
        lab = np.argmin(((C[:, None, :] - cent[None]) ** 2).sum(-1), 1)
        for j in range(k):
            m = lab == j
            if m.any(): cent[j] = C[m].mean(0)
    area = np.bincount(lab, minlength=k) / len(C)
    # оттенок в плоскости, перпендикулярной серой оси
    u = np.array([1, -1, 0]) / np.sqrt(2); v = np.array([1, 1, -2]) / np.sqrt(6)
    hues = []
    for j in np.argsort(-area):
        c = cent[j]; chroma = np.linalg.norm(c)
        if area[j] < min_area or chroma < chroma_min: continue
        hdeg = np.degrees(np.arctan2(c @ v, c @ u)) % 360
        if all(min(abs(hdeg - h0), 360 - abs(hdeg - h0)) > 25 for h0 in hues): hues.append(hdeg)
    return len(hues), [round(float(h)) for h in hues]

def check(img, shot, fps=24):
    out = []; L = luma(img); H, W = L.shape
    q = (shot or {}).get('qc') or {}
    if q.get('focus_m') and q.get('eye_m'):
        r = q['focus_m'] / q['eye_m']
        if not 0.7 < r < 1.4: out.append(('focus', f"диафрагма считалась на {q['focus_m']} м, а глаз в {q['eye_m']} м"))
    if q.get('face'):
        x, y = q['face']; rr = max(0.02, q.get('face_r', 0.05)) * 0.7
        if 0 <= x <= 1 and 0 <= y <= 1:
            cx, cy = int(x * W), int(y * H); r = max(2, int(rr * W))
            patch = L[max(0, cy - r):cy + r, max(0, cx - r):cx + r]
            fl, med = float(np.percentile(patch, 75)), float(np.median(L))
            # освещённая часть лица (верхняя четверть яркостей пятна) светлее медианы кадра и не тонет в черноте
            if fl < max(0.16, 0.9 * med): out.append(('face', f'лицо тёмное: {fl:.2f} при медиане кадра {med:.2f}'))
        else: out.append(('face', 'лицо вне кадра'))
    dark = img[L < np.percentile(L, 25)]
    if len(dark):
        m = dark.mean(0); spread = float(m.max() - m.min()); base = float(m.mean())
        if base > 0.01 and spread / max(base, 0.02) > 1.6 and spread > 0.06:
            out.append(('cast', f'тени окрашены: RGB теней {np.round(m, 2).tolist()}'))
    n, hues = color_spots(img)
    if n > 4: out.append(('palette', f'{n} цветовых пятен (оттенки {hues}), а палитра держит 3–4'))
    return out, dict(spots=n, hues=hues)

def main(d):
    meta = json.load(open(os.path.join(d, 'meta.json'))); fps = meta.get('fps', 24)
    shots = meta.get('shots', []); rows = []; bad = 0
    for p in sorted(glob.glob(os.path.join(d, 'f_*.png'))):
        f = int(os.path.basename(p)[2:7]); t = (f - 1) / fps
        si = next((i for i, s in enumerate(shots) if s['start'] <= t < s['end']), len(shots) - 1)
        sh = shots[si] if shots else None
        errs, info = check(load(p), sh, fps); bad += bool(errs)
        rows.append(dict(frame=f, shot=si, size=sh and sh.get('size'), note=sh and sh.get('note'), errors=errs, **info))
        print(f"{f:5d} план {si:2d} {(sh or {}).get('size', ''):4s} {'OK ' if not errs else 'ПЛОХО'}", '; '.join(f'{k}: {m}' for k, m in errs), flush=True)
    json.dump(rows, open(os.path.join(d, 'qc.json'), 'w'), ensure_ascii=False, indent=1)
    print(f'итог: {len(rows) - bad} из {len(rows)} кадров без замечаний')
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1]))
