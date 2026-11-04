# Композиция кадра: где в кадре стоит герой и как кадр «читается».
# Координаты экрана: sx, sy в долях ВИДИМОГО кадра 2.39:1, центр = (0, 0), +x вправо, +y вверх.
# Камера сама поворачивается так, чтобы точка интереса (глаза на портрете, центр тела на общем) легла в эту точку.
#
# Источники: правило третей и «воздух по взгляду» (lead room), сетка Φ и золотая спираль,
# центральная симметрия (Кубрик, Андерсон), круговая (свет/виньетка собирают взгляд в центр),
# треугольная (плечи — основание, глаза — вершина; низкая камера), масштаб (крошечная фигура в огромной архитектуре),
# негативное пространство (одиночество), одноточечная перспектива / ведущие линии (герой в точке схода).
import math

PHI = 0.618

# rule: (sx, sy, где применять по крупности, что делает с камерой, смысл)
RULES = {
    'thirds':     dict(sx=1 / 6, sy=1 / 6, sizes=('FS', 'MS', 'MCU', 'CU', 'WS'), look_room=True,
                       desc='правило третей: глаза на верхней линии, воздух по направлению взгляда'),
    'golden':     dict(sx=PHI - 0.5 + 0.07, sy=PHI - 0.5 + 0.05, sizes=('MS', 'MCU', 'CU', 'ECU'), look_room=True,
                       desc='золотая спираль: глаза в фокусе спирали, кадр «закручивается» к лицу'),
    'centered':   dict(sx=0.0, sy=0.12, sizes=('ECU', 'CU', 'MCU', 'MS', 'FS', 'WS', 'EWS'), snap_axis=True,
                       desc='центр и симметрия: камера на оси, герой в центре, давление и порядок'),
    'circular':   dict(sx=0.0, sy=-0.06, sizes=('FS', 'WS'), vignette=0.35,
                       desc='круговая: свет и виньетка собирают взгляд к фигуре в центре'),
    'triangular': dict(sx=0.07, sy=0.16, sizes=('MCU', 'CU', 'MS'), look_room=True, elev=-12,
                       desc='треугольник: плечи — основание, глаза — вершина; камера чуть снизу, сила и устойчивость'),
    'scale':      dict(sx=0.0, sy=-0.30, sizes=('EWS', 'WS'), size='EWS', elev=8, snap_axis=True,
                       desc='масштаб: крошечная фигура внизу огромного пространства'),
    'negative':   dict(sx=0.34, sy=-0.08, sizes=('WS', 'FS', 'EWS'), look_room=False, away=True,
                       desc='негативное пространство: герой у края, пустота давит — одиночество, сомнение'),
    'diagonal':   dict(sx=0.19, sy=0.10, sizes=('MS', 'FS', 'WS', 'MCU'), look_room=True, dutch_hint=0,
                       desc='диагональ: герой на главной диагонали, движение и динамика (барокко — слева-снизу вправо-вверх)'),
    'dynamic':    dict(sx=0.21, sy=0.14, sizes=('MS', 'MCU', 'CU', 'FS', 'WS'), look_room=True,
                       desc='динамическая симметрия Хэмбриджа: диагонали и перпендикуляры к ним, глаза на их пересечении'),
    'golden_tri': dict(sx=0.24, sy=0.12, sizes=('MS', 'FS', 'WS', 'MCU'), look_room=True,
                       desc='золотые треугольники: диагональ + перпендикуляры из углов, фигура в остром углу'),
    'frame_in':   dict(sx=0.0, sy=0.0, sizes=('FS', 'WS', 'EWS'), frame=True,
                       desc='рамка в рамке: арка, дверь, колонны обрамляют героя, взгляд зрителя «заперт» на нём'),
    'depth':      dict(sx=0.12, sy=0.02, sizes=('FS', 'WS', 'MS'), foreground=True, look_room=True,
                       desc='глубина по оси Z: передний план размыт, герой на среднем, фон читается — объём кадра'),
    'dirty':      dict(sx=0.2, sy=0.1, sizes=('MS', 'MCU', 'CU'), foreground=True, near=True, look_room=True,
                       desc='грязный передний план: край колонны/плеча вплотную к объективу, в расфокусе закрывает треть кадра — '
                            'зритель подглядывает, лицо резкое в глубине (кадры через плечо в студийном кино)'),
    'vanishing':  dict(sx=0.0, sy=0.0, sizes=('WS', 'EWS', 'FS'), snap_axis=True,
                       desc='одноточечная перспектива: ведущие линии архитектуры сходятся на герое'),
}

# эмоция бита подталкивает к композиции (умножает веса режиссёра/оператора)
EMOTION_BIAS = {
    'одиночество': dict(negative=3, scale=2), 'сомнение': dict(negative=2.5, centered=0.5), 'страх': dict(negative=2, triangular=0.5),
    'благоговение': dict(scale=2.5, vanishing=2, centered=1.5), 'решимость': dict(triangular=2.5, vanishing=1.5, thirds=1.2),
    'тоска': dict(negative=2, circular=1.5, frame_in=1.5, dirty=1.6), 'тревога': dict(diagonal=2.5, negative=1.5, frame_in=1.3, dirty=2.0),
    'напряжение': dict(dirty=2.2, frame_in=1.5), 'горе': dict(dirty=1.5),
    'движение': dict(diagonal=2.0, dynamic=1.5, depth=1.5), 'сила': dict(triangular=3, centered=1.5), 'откровение': dict(golden=2.5, centered=1.5),
}

def choose(size, emotion, weights, rnd, prev=None, used=()):
    """Выбор композиции под крупность, эмоцию и вкус постановщиков. Соседние кадры не повторяют одну и ту же."""
    bias = dict(EMOTION_BIAS.get(emotion or '', {}))
    try:
        from crew import emotions as _em
        e = _em.get(emotion)
        if e:
            for i, k in enumerate(e['comp']): bias[k] = max(bias.get(k, 1.0), 2.5 - 0.5 * i)
    except ImportError: pass
    opts = []
    for k, r in RULES.items():
        if size not in r['sizes']: continue
        w = weights.get(k, 0.5) * bias.get(k, 1.0) * (0.35 if k == prev else 1.0) * 0.75 ** list(used).count(k)
        opts.append((w * (0.4 + rnd.random()), k))
    return max(opts)[1] if opts else 'thirds'

VISIBLE = 1 / 2.39   # видимая высота кадра под каше 2.39:1, в долях ширины

def screen_point(rule, gaze_side, aspect):
    """Точка в долях полного кадра рендера (с учётом каше). gaze_side: +1 — герой смотрит вправо по экрану, −1 — влево."""
    r = RULES[rule]
    sx = r['sx']
    if r.get('look_room'): sx = -gaze_side * sx       # воздух перед взглядом: герой слева, если смотрит вправо
    if r.get('away'): sx = -gaze_side * sx            # негативное пространство за спиной/перед ним — пустота по взгляду
    sy = r['sy'] * (VISIBLE * aspect)                  # видимая часть кадра по высоте меньше полного кадра
    return sx, sy

def aim_offsets(sx, sy, lens, sensor_w, aspect):
    """Насколько повернуть камеру (рыскание, тангаж в радианах), чтобы точка интереса легла в (sx, sy)."""
    return math.atan(sx * sensor_w / lens), math.atan(sy * sensor_w / aspect / lens)

def draw_guides(img, rule, color=(255, 255, 255), pole=None):
    """Разметка композиции поверх кадра (как в разборах операторов). img — PIL.Image полного кадра."""
    from PIL import ImageDraw
    W, H = img.size; vh = W / 2.39; y0 = (H - vh) / 2
    d = ImageDraw.Draw(img, 'RGBA'); c = color + (190,)
    X = lambda u: u * W; Y = lambda v: y0 + v * vh
    d.rectangle([0, y0, W - 1, y0 + vh], outline=c, width=2)
    if rule == 'thirds':
        for u in (1 / 3, 2 / 3): d.line([X(u), Y(0), X(u), Y(1)], fill=c, width=2); d.line([X(0), Y(u), X(1), Y(u)], fill=c, width=2)
    elif rule == 'golden':
        for u in (1 - PHI, PHI): d.line([X(u), Y(0), X(u), Y(1)], fill=color + (90,), width=1); d.line([X(0), Y(u), X(1), Y(u)], fill=color + (90,), width=1)
        # логарифмическая золотая спираль r = a·φ^(2θ/π), полюс — в точке, где стоят глаза героя
        pu, pv = pole or (PHI, 1 - PHI); cx, cy = X(pu), Y(pv)
        b = math.log(1 / PHI) / (math.pi / 2); R = max(cx, W - cx); pts = []
        mirror = -1 if pu < 0.5 else 1
        for i in range(0, 721):
            th = -i / 720 * 4 * math.pi; r = R * math.exp(b * th)
            pts.append((cx + mirror * r * math.cos(th + math.pi), cy + r * math.sin(th + math.pi)))
        seg = []
        for x, y in pts + [(-1e9, 0)]:
            if 0 <= x < W and y0 <= y <= y0 + vh: seg.append((x, y))
            else:
                if len(seg) > 1: d.line(seg, fill=c, width=2)
                seg = []
    elif rule in ('centered', 'vanishing'):
        d.line([X(0.5), Y(0), X(0.5), Y(1)], fill=c, width=2)
        if rule == 'vanishing':
            for u, v in ((0, 0), (1, 0), (0, 1), (1, 1)): d.line([X(u), Y(v), X(0.5), Y(0.5)], fill=c, width=2)
        else:
            d.line([X(0.5 - 0.25 * vh / W), Y(0), X(0.5 - 0.25 * vh / W), Y(1)], fill=color + (90,), width=1)
            d.line([X(0.5 + 0.25 * vh / W), Y(0), X(0.5 + 0.25 * vh / W), Y(1)], fill=color + (90,), width=1)
    elif rule == 'circular':
        r = vh * 0.5; d.ellipse([W / 2 - r, y0, W / 2 + r, y0 + vh], outline=c, width=2)
    elif rule == 'triangular':
        d.polygon([(X(0.12), Y(1)), (X(0.53), Y(0.04)), (X(0.94), Y(1))], outline=c, width=2)
    elif rule == 'scale':
        d.rectangle([X(0.44), Y(0.62), X(0.56), Y(0.98)], outline=c, width=2)
        d.rectangle([X(0.16), Y(0.05), X(0.84), Y(0.98)], outline=color + (110,), width=1)
    elif rule == 'negative':
        d.line([X(0.2), Y(0), X(0.2), Y(1)], fill=c, width=2); d.line([X(0.8), Y(0), X(0.8), Y(1)], fill=c, width=2)
    elif rule == 'diagonal':
        d.line([X(0), Y(1), X(1), Y(0)], fill=c, width=2); d.line([X(0), Y(0), X(1), Y(1)], fill=color + (90,), width=1)
    elif rule in ('dynamic', 'golden_tri'):
        d.line([X(0), Y(1), X(1), Y(0)], fill=c, width=2)
        if rule == 'dynamic': d.line([X(0), Y(0), X(1), Y(1)], fill=c, width=2)
        # перпендикуляры к диагоналям из углов (reciprocals)
        Wr, Hr = W, vh
        for (ax, ay), sgn in (((0, 0), 1), ((W, vh), 1)) + ((((W, 0), -1), ((0, vh), -1)) if rule == 'dynamic' else ()):
            # диагональ (0,vh)-(W,0) для sgn=1, (0,0)-(W,vh) для sgn=-1; перпендикуляр из угла
            dx, dy = (W, -vh) if sgn == 1 else (W, vh)
            nx, ny = dy, -dx  # нормаль
            t = ((0 if sgn == 1 else 0) - ax) * 0
            # точка пересечения перпендикуляра с диагональю
            px0, py0 = (0, vh) if sgn == 1 else (0, 0)
            L2 = dx * dx + dy * dy; k = ((ax - px0) * dx + (ay - py0) * dy) / L2
            ix, iy = px0 + k * dx, py0 + k * dy
            ex, ey = ix + (ix - ax) * 0.0, iy + (iy - ay) * 0.0
            d.line([ax, y0 + ay, ix, y0 + iy], fill=c, width=2)
    elif rule == 'frame_in':
        d.rectangle([X(0.30), Y(0.10), X(0.70), Y(0.98)], outline=c, width=3)
        d.arc([X(0.30), Y(0.10) - (X(0.70) - X(0.30)) * 0.0, X(0.70), Y(0.10) + (X(0.70) - X(0.30))], 180, 360, fill=c, width=2)
    elif rule == 'depth':
        for u, lab in ((0.12, 'передний'), (0.5, 'средний'), (0.85, 'дальний')):
            d.line([X(0), Y(0.95 - u * 0.5), X(1), Y(0.95 - u * 0.5)], fill=color + (130,), width=1)
        d.rectangle([X(0.0), Y(0.0), X(0.18), Y(1)], outline=c, width=2)
    return img
