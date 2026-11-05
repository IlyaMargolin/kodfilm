# Раскадровка-разбор: кадр из середины каждого плана + разметка композиции + подпись (крупность, объектив, T-стоп, движение, смысл).
# python3 studio/board.py out/hram_board out/hram_board/board.png
import sys, os, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
import composition

RU = dict(thirds='правило третей', golden='золотая спираль', centered='центр, симметрия', circular='круговая',
          triangular='треугольник', scale='масштаб', negative='негативное пространство', vanishing='точка схода')
MOVE = dict(static='статика', push='наезд', slow_push='медленный наезд', slow_pull='отъезд', dolly='тележка', track='трэвеллинг',
            follow='за героем', lead='ведём спереди', slow_tilt='панорама вверх')

def font(sz):
    for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/dejavu/DejaVuSans.ttf'):
        if os.path.exists(f): return ImageFont.truetype(f, sz)
    return ImageFont.load_default()

COLORS = [(255, 196, 92), (110, 200, 255), (255, 110, 150), (140, 230, 140), (200, 160, 255), (255, 150, 80), (90, 230, 210),
          (240, 240, 120), (255, 120, 255), (170, 210, 120)]

def plan_view(m, w, h):
    """Вид сверху, как у оператора на планшете: путь героя (белый), путь камеры каждого плана (цвет, номер), куда смотрит."""
    im = Image.new('RGB', (w, h), (22, 22, 24)); dr = ImageDraw.Draw(im); F = font(14)
    feet = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in m.get('feet', [])]
    cams = [(i, s['cam']) for i, s in enumerate(m['shots']) if s.get('cam')]
    pts = feet + [(c[0], c[1]) for _, cp in cams for c in cp]
    if not pts: dr.text((10, 10), 'вид сверху: нет данных камер (старый meta.json)', fill='gray', font=F); return im
    x0, x1 = min(p[0] for p in pts) - 1, max(p[0] for p in pts) + 1; y0, y1 = min(p[1] for p in pts) - 1, max(p[1] for p in pts) + 1
    k = min((w - 40) / (x1 - x0), (h - 40) / (y1 - y0)); ox, oy = (w - k * (x1 - x0)) / 2, (h - k * (y1 - y0)) / 2
    P = lambda x, y: (ox + (x - x0) * k, h - (oy + (y - y0) * k))
    g = 1.0   # сетка через метр
    xs = int(x0); 
    while xs <= x1: dr.line([P(xs, y0), P(xs, y1)], fill=(36, 36, 40)); xs += g
    ys = int(y0)
    while ys <= y1: dr.line([P(x0, ys), P(x1, ys)], fill=(36, 36, 40)); ys += g
    if len(feet) > 1:
        dr.line([P(*p) for p in feet[::3]], fill=(235, 235, 235), width=3)
        sx, sy = P(*feet[0]); dr.ellipse([sx - 5, sy - 5, sx + 5, sy + 5], outline='white', width=2)
        ex, ey = P(*feet[-1]); dr.ellipse([ex - 5, ey - 5, ex + 5, ey + 5], fill='white')
    for i, cp in cams:
        col = COLORS[i % len(COLORS)]
        if len(cp) > 1: dr.line([P(c[0], c[1]) for c in cp], fill=col, width=2)
        mid = cp[len(cp) // 2]; mx, my = P(mid[0], mid[1])
        L = 0.9; ax, ay = P(mid[0] + mid[3] * L, mid[1] + mid[4] * L)
        dr.line([mx, my, ax, ay], fill=col, width=2); dr.ellipse([mx - 4, my - 4, mx + 4, my + 4], fill=col)
        fx, fy = P(cp[0][0], cp[0][1]); dr.text((fx + 6, fy - 16), f'{i + 1:02d}', fill=col, font=F)
    dr.text((8, 6), 'вид сверху: путь героя — белый, камеры — цвет и номер плана, штрих — куда смотрит; сетка 1 м', fill=(170, 170, 170), font=font(13))
    return im

def beat_table(m, w, h):
    """Таблица битов: время, действие, эмоция, текст режиссёру — сценарий рядом с раскадровкой."""
    im = Image.new('RGB', (w, h), (22, 22, 24)); dr = ImageDraw.Draw(im); F = font(15); y = 8
    dr.text((10, y), 'биты сцены', fill='white', font=font(17)); y += 28
    for b in m.get('beats', []):
        line = f"{b['start']:5.1f}–{b['start'] + b['dur']:5.1f} с  {b['action']:<9} {b.get('emotion') or '—':<12} {b['text']}"
        dr.text((10, y), line[:110], fill=(225, 215, 190), font=F); y += 22
        if y > h - 20: break
    return im

def main(d, out, cols=3, tw=640):
    m = json.load(open(os.path.join(d, 'meta.json'))); fps = m['fps']
    tiles = []
    for i, s in enumerate(m['shots']):
        f = int((s['start'] + s['end']) / 2 * fps) + 1
        p = os.path.join(d, f'f_{f:05d}.png')
        if not os.path.exists(p): continue
        im = Image.open(p).convert('RGB')
        W, H = im.size; vh = int(W / 2.39); y0 = (H - vh) // 2
        dr = ImageDraw.Draw(im); dr.rectangle([0, 0, W, y0], fill=0); dr.rectangle([0, y0 + vh, W, H], fill=0)
        if s.get('comp'):
            pole = (0.5 + s['screen'][0], 0.5 - s['screen'][1]) if s.get('screen') else None
            composition.draw_guides(im, s['comp'], pole=pole)
        im = im.resize((tw, int(tw * H / W)))
        dr = ImageDraw.Draw(im); F = font(max(12, tw // 40)); Fs = font(max(11, tw // 48))
        y_top = (im.height - int(tw / 2.39)) // 2
        dr.text((10, 6), f"{i + 1:02d}  {s['size']} · {s['lens']:.0f} мм · T{s.get('fstop', '')} · {MOVE.get(s['move'], s['move'])} · {s['end'] - s['start']:.1f} с", fill='white', font=F)
        dr.text((10, im.height - y_top + 6), (RU.get(s.get('comp'), 'вставка') + ' — ' + s['note'])[:80], fill=(230, 200, 140), font=Fs)
        tiles.append(im)
    rows = (len(tiles) + cols - 1) // cols; th = tiles[0].height; pad = 6
    head = 54; SW = cols * tw + (cols + 1) * pad
    plan = plan_view(m, SW // 2 - pad, int(SW * 0.28)); beats = beat_table(m, SW - plan.width - 3 * pad, plan.height)
    sheet = Image.new('RGB', (SW, head + rows * th + (rows + 1) * pad + plan.height + pad), (14, 14, 14))
    y_low = head + pad + rows * (th + pad)
    sheet.paste(plan, (pad, y_low)); sheet.paste(beats, (2 * pad + plan.width, y_low))
    ImageDraw.Draw(sheet).text((pad + 4, 12), f"{m.get('title', '')} — режиссёр: {m.get('director', '')}, оператор: {m.get('dp', '')}", fill='white', font=font(26))
    for k, t in enumerate(tiles):
        sheet.paste(t, (pad + (k % cols) * (tw + pad), head + pad + (k // cols) * (th + pad)))
    sheet.save(out); print(out)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
