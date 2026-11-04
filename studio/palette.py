# Палитра кадра: 3–4 цвета, которые что-то значат. Так работают художник-постановщик, оператор и колорист:
# у сцены есть ведущая палитра (холодная бирюза и сталь — тревога, янтарь и тёмное дерево — тепло дома),
# у бита — сдвиг к своей эмоции. Цвета держат все слои сразу:
#   • свет: ключ и контровой окрашены цветами палитры (гаффер), дымка — цветом воздуха;
#   • грейд: тени тонируются цветом теней, света — цветом светов (lift/gamma/gain), насыщенность по настроению;
#   • meta.json: палитра каждого плана — для стилей, монтажа и обложки.
# Цвета — sRGB hex; роли: key (свет), shadow (тени и воздух в тени), accent (одна деталь/практик), skin/hi (света).
import colorsys

def _rgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

def _lin(c):   # sRGB → линейный (свет в Blender задаётся линейно)
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)

PALETTES = {
    # имя: цвета (key, shadow, accent, hi), насыщенность грейда, смысл
    'янтарь_бирюза': dict(key='#E6A24E', shadow='#173B45', accent='#C8643C', hi='#F3E3C3', sat=1.0,
                          why='классика студийного кино: тёплый свет против холодных теней — объём и драма без лишних цветов'),
    'холодный_рассвет': dict(key='#AFC6D4', shadow='#1B2836', accent='#D9A066', hi='#E6EEF2', sat=0.75,
                             why='сталь и сизый воздух, одна тёплая точка (лицо, огонь) — одиночество и тишина'),
    'тревога':       dict(key='#8FB8B0', shadow='#0E1F24', accent='#B23A2E', hi='#D9E4DA', sat=0.7,
                          why='больничная бирюза, почти чёрные тени, красный акцент — опасность'),
    'священный':     dict(key='#F2C46B', shadow='#2A2233', accent='#7FA6C9', hi='#FFF4DC', sat=0.95,
                          why='золото света сквозь своды, фиолетово-тёмный камень, небесный акцент — благоговение'),
    'горе':          dict(key='#9AA7B1', shadow='#1C2127', accent='#8C6A55', hi='#D5D9DC', sat=0.55,
                          why='выцветший сине-серый мир, тёплым остаётся только кожа — утрата'),
    'решимость':     dict(key='#E8913A', shadow='#121212', accent='#5D7FA3', hi='#F5D9B0', sat=1.1,
                          why='огненный ключ, глубокие тени, стальной контровой — воля и движение'),
    'дом':           dict(key='#E9B26A', shadow='#3A2414', accent='#4F6F52', hi='#F7E2BE', sat=1.0,
                          why='лампы, дерево, тёплая темнота, зелёный акцент обоев — уют, прошлое'),
    'день':          dict(key='#F4E7C9', shadow='#3E5566', accent='#5E8C4A', hi='#FFFFFF', sat=1.05,
                          why='ясный день: тёплое солнце, голубые тени, зелень — нейтральная жизнь'),
}
# эмоция (каноническая, из единого словаря crew/emotions.py) → палитра
EMOTION = {'благоговение': 'священный', 'откровение': 'священный', 'одиночество': 'холодный_рассвет', 'сомнение': 'холодный_рассвет',
           'страх': 'тревога', 'напряжение': 'тревога', 'горе': 'горе', 'решимость': 'решимость', 'гнев': 'решимость',
           'нокаут': 'решимость', 'радость': 'день', 'расслабление': 'дом'}
# ведущая палитра сцены по времени суток (небо сценария), если сценарий не назвал свою
SKY = {'sunset': 'янтарь_бирюза', 'sunrise': 'холодный_рассвет', 'moonless': 'тревога', 'night': 'тревога', 'esplanade': 'день'}

def scene_palette(scene):
    name = getattr(scene, 'palette', '') or ''
    if name in PALETTES: return name
    sky = (scene.sky[0] if getattr(scene, 'sky', None) else '').lower()
    return next((p for k, p in SKY.items() if k in sky), 'янтарь_бирюза')

def mix(a, b, t):
    A, B = PALETTES[a], PALETTES[b]; out = {}
    for k in ('key', 'shadow', 'accent', 'hi'):
        ca, cb = _rgb(A[k]), _rgb(B[k]); out[k] = tuple(x * (1 - t) + y * t for x, y in zip(ca, cb))
    out['sat'] = A['sat'] * (1 - t) + B['sat'] * t
    return out

def for_shot(scene, emotion):
    """Палитра плана: ведущая палитра сцены, сдвинутая на 45% к палитре эмоции бита."""
    from crew.emotions import canon
    base = scene_palette(scene); emo = EMOTION.get(canon(emotion), None)
    p = mix(base, emo, 0.45) if emo and emo != base else mix(base, base, 0)
    p['name'] = base + (f'→{emo}' if emo and emo != base else '')
    return p

def hexes(p):
    return ['#%02X%02X%02X' % tuple(int(round(min(1, max(0, x)) * 255)) for x in p[k]) for k in ('key', 'shadow', 'accent', 'hi')]

def light_color(c, keep=0.55):
    """Цвет источника из цвета палитры: тон оставляем, яркость выравниваем (сила света — отдельно)."""
    h, l, s = colorsys.rgb_to_hls(*c); r, g, b = colorsys.hls_to_rgb(h, 0.6, s * keep)
    return _lin((r, g, b))

def _tint(c, k):
    """Тонировка вокруг 1.0 для lift/gamma/gain: цвет без яркости, сила k."""
    m = sum(c) / 3 or 1e-3; return tuple(1 + (x / m - 1) * k for x in c)

def grade_values(p):
    # композитор работает в линейном свете: lift сдвигает значения на (lift−1)·(1−x), а тени в линейном ≈ 0.02–0.05,
    # поэтому тонировка теней — доли процента (замер: 0.10 обнулял красный канал в тенях и красил кадр в бирюзу)
    return dict(lift=_tint(p['shadow'], 0.015), gamma=_tint(p['key'], 0.04), gain=_tint(p['hi'], 0.06), sat=p['sat'])

def setup(scene):
    """Узлы грейда в композиторе (после линзы): баланс цвета + насыщенность. Значения ставит apply() перед кадром."""
    ng = scene.compositing_node_group
    if ng is None: return None
    N, L = ng.nodes, ng.links
    out = next(n for n in N if n.bl_idname == 'NodeGroupOutput')
    src = out.inputs[0].links[0].from_socket if out.inputs[0].links else None
    if src is None: return None
    cb = N.new('CompositorNodeColorBalance'); cb.name = 'grade'
    try: cb.correction_method = 'LIFT_GAMMA_GAIN'
    except Exception: pass
    hs = N.new('CompositorNodeHueSat'); hs.name = 'grade_sat'
    img_in = cb.inputs.get('Image') or cb.inputs[-1]
    L.new(src, img_in); L.new(cb.outputs[0], hs.inputs.get('Image') or hs.inputs[0]); L.new(hs.outputs[0], out.inputs[0])
    return ng

def _put(node, name, val):
    """Blender 4: свойство узла (cb.lift); Blender 5: входной сокет. В 5.x у Color Balance два сокета с одним
    именем — число (общая сила) и цвет; тон кладём в цветовой (RGBA), иначе грейд молча не применяется."""
    if hasattr(node, name):
        try: setattr(node, name, val); return
        except Exception: pass
    socks = [s for s in node.inputs if s.name.lower() == name.lower()]
    s = next((x for x in socks if x.type == 'RGBA'), socks[0] if socks else None)
    if s is not None:
        try: s.default_value = (*val, 1.0) if isinstance(val, tuple) and len(s.default_value) == 4 else val
        except Exception: pass

def apply(scene, p):
    ng = scene.compositing_node_group
    if ng is None or 'grade' not in ng.nodes: return
    g = grade_values(p); cb = ng.nodes['grade']; hs = ng.nodes['grade_sat']
    for k in ('lift', 'gamma', 'gain'): _put(cb, k, g[k])
    s = hs.inputs.get('Saturation')
    if s is not None: s.default_value = g['sat']
