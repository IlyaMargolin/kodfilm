# Мимика: эмоция бита → единицы лица (шейпы из human._face_units), плюс жизнь лица между эмоциями.
# Правила игры крупного плана (то, что видно в кадрах-образцах студийного кино):
#   • лицо опережает тело: выражение начинает меняться за ~0.25 с до действия бита и набирается 0.5–0.8 с;
#   • асимметрия: одна бровь чуть выше, один угол рта — симметричное лицо читается как маска;
#   • моргание каждые 2.5–5 с (чаще в тревоге, реже в сосредоточенности и благоговении), 0.15–0.2 с, веко
#     закрывается быстрее, чем открывается; моргание на смене взгляда/повороте головы — «склейка» внимания;
#   • микродвижения: брови и веки едва дышат (2–4% амплитуды) — неподвижное лицо выглядит мёртвым;
#   • опущенный взгляд с приподнятыми внутренними краями бровей — горе/сомнение; прищур + сжатые губы — решимость.
import math, random

# эмоция → {единица: сила}; _L/_R в имени — одна сторона (для асимметрии), без суффикса — обе
EXPR = {
    'благоговение': {'eyebrows-inner-up': 0.45, 'eyebrows-up': 0.3, 'eye-opened-up': 0.35, 'mouth-open': 0.12, 'mouth-parling': 0.25},
    'сомнение':     {'eyebrows-inner-up': 0.55, 'mouth-depression': 0.3, 'eyebrows-left-down': 0.2, 'eye-slit': 0.1},
    'решимость':    {'eyebrows-down': 0.55, 'mouth-compression': 0.5, 'eye-slit': 0.3, 'nose-elevation': 0.08},
    'страх':        {'eye-opened-up': 0.75, 'eyebrows-up': 0.45, 'eyebrows-inner-up': 0.55, 'mouth-open': 0.25, 'mouth-parling': 0.4},
    'напряжение':   {'eyebrows-inner-up': 0.35, 'eyebrows-down': 0.25, 'eye-slit': 0.15, 'mouth-compression': 0.35},
    'горе':         {'eyebrows-inner-up': 0.75, 'mouth-depression': 0.5, 'eye-slit': 0.25},
    'одиночество':  {'eyebrows-inner-up': 0.4, 'mouth-depression': 0.2, 'eye-slit': 0.12},
    'радость':      {'mouth-corner-puller': 0.6, 'eye-slit': 0.3, 'eyebrows-up': 0.1},
    'гнев':         {'eyebrows-down': 0.85, 'eye-slit': 0.3, 'mouth-compression': 0.45, 'nose-elevation': 0.3},
    'откровение':   {'eyebrows-up': 0.5, 'eye-opened-up': 0.45, 'mouth-open': 0.2, 'mouth-parling': 0.3},
    'расслабление': {'mouth-corner-puller': 0.15, 'eye-slit': 0.15},
    'нокаут':       {'eye-slit': 0.6, 'mouth-open': 0.35, 'eyebrows-inner-up': 0.3},
}
from crew.emotions import canon     # синонимы — один словарь движка (crew/emotions.py)
# действие тела тоже окрашивает лицо: бег — усилие, взгляд вверх — брови вверх
ACTION = {'run': {'mouth-parling': 0.35, 'eyebrows-down': 0.2, 'eye-slit': 0.15}, 'look_up': {'eyebrows-up': 0.25, 'eye-opened-up': 0.15},
          'look_down': {'eye-slit': 0.25}}
BLINK_GAP = {'напряжение': 2.0, 'страх': 1.6, 'сомнение': 2.6, 'решимость': 4.5, 'благоговение': 5.5, 'горе': 3.2}

def _expand(d, asym):
    """«eyebrows-inner-up» → левая и правая единицы; asym — небольшой перекос сторон."""
    out = {}
    for k, v in d.items():
        if '-left-' in k or '-right-' in k or k.startswith('mouth'): out[k] = out.get(k, 0) + v; continue
        a, b = k.split('-', 1)
        out[f'{a}-left-{b}'] = out.get(f'{a}-left-{b}', 0) + v * (1 + asym)
        out[f'{a}-right-{b}'] = out.get(f'{a}-right-{b}', 0) + v * (1 - asym)
    return out

def act(body, beats, fps, total, seed=11):
    """Ключи шейпов на всю сцену (кадры исходного времени, как и тело)."""
    keys = getattr(body.data, 'shape_keys', None)
    if not keys: return 0
    kb = keys.key_blocks; rnd = random.Random(seed); asym = 0.12
    def target(t):
        acc = {}
        for bt in beats:
            emo = canon(bt.emotion)
            src = dict(EXPR.get(emo, {}))
            for k, v in ACTION.get(bt.action, {}).items(): src[k] = max(src.get(k, 0), v)
            if not src: continue
            # набор за 0.6 с, начиная за 0.25 с до бита; спад 0.5 с после
            u = min(1, max(0, (t - bt.start + 0.25) / 0.6)) * min(1, max(0, (bt.start + bt.dur + 0.3 - t) / 0.5))
            u = u * u * (3 - 2 * u)
            for k, v in _expand(src, asym).items(): acc[k] = acc.get(k, 0) + v * u
        return acc
    names = [k.name for k in kb if k.name != 'Basis']
    step = 2
    for f in range(1, total + 1, step):
        t = (f - 1) / fps; tg = target(t)
        for n in names:
            breath = 0.025 * math.sin(t * 1.3 + hash(n) % 7) if ('eyebrows' in n or 'slit' in n) else 0.0
            v = max(0.0, min(1.0, tg.get(n, 0.0) + breath))
            kb[n].value = v; kb[n].keyframe_insert('value', frame=f)
    # моргания: поверх выражения, своими ключами (быстро вниз, медленнее вверх)
    t = rnd.uniform(0.6, 1.8); n_bl = 0
    turn_t = [bt.start for bt in beats if bt.action in ('turn', 'look_up', 'look_down')]
    events = sorted(set([round(x, 2) for x in turn_t]))
    while t < total / fps:
        emo = next((canon(b.emotion) for b in beats if b.start <= t < b.start + b.dur), '')
        events.append(t); t += BLINK_GAP.get(emo, 3.4) * rnd.uniform(0.7, 1.35)
    for t0 in sorted(events):
        f0 = 1 + t0 * fps
        for side in ('left', 'right'):
            n = f'eye-{side}-closure'
            if n not in kb: continue
            base = kb[n].value
            for df, v in ((-1, None), (0.0, 0.0), (0.07 * fps, 1.0), (0.11 * fps, 1.0), (0.2 * fps, 0.0)):
                if v is None: continue
                kb[n].value = v; kb[n].keyframe_insert('value', frame=f0 + df + (0.3 if side == 'right' else 0))
        n_bl += 1
    return n_bl
