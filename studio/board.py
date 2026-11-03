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
    head = 54
    sheet = Image.new('RGB', (cols * tw + (cols + 1) * pad, head + rows * th + (rows + 1) * pad), (14, 14, 14))
    ImageDraw.Draw(sheet).text((pad + 4, 12), f"{m.get('title', '')} — режиссёр: {m.get('director', '')}, оператор: {m.get('dp', '')}", fill='white', font=font(26))
    for k, t in enumerate(tiles):
        sheet.paste(t, (pad + (k % cols) * (tw + pad), head + pad + (k // cols) * (th + pad)))
    sheet.save(out); print(out)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
