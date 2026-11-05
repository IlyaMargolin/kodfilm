# Пульт стиля: один словарь (look.json или пресет по имени) включает и настраивает каждый инструмент ядра.
# Так стиль — это данные, а не код: «кино», «Pixar», «нуар», «неон», «тун» отличаются только числами здесь,
# сценарий может переключить любой инструмент на сцену (ВИД: нуар, ДЫМКА: 0, СВЕТ: контровой, НЕОН: 1).
# Разделы и кто их исполняет:
#   light    — схема света (gaffer.py): поверх профиля оператора; scheme — готовая схема, поля — точная правка;
#   air      — воздух: depth — дымка по глубине рендера (depth.py), fog — объёмный туман (world.fog), множители;
#   optics   — lens: блум/анаморф/аберрация (lens.py), dof — множитель размытия фона (меньше f-число), 1 = как у оператора;
#   color    — palette: имя палитры (palette.py) или None = по сцене и эмоции, sat — множитель насыщенности грейда,
#              contrast: −3 (очень мягко) … 0 (база) … 3 (очень жёстко) — тональная кривая AgX, exposure: ± ступени;
#   neon     — неоновые трубки-практики в кадре (neon.py): on, strength, colors (hex), count;
#   post     — монтаж (assemble.sh): grain (зерно 0..1), vignette (угол, 0..1), halation (ореол бликов 0..1), twos («на двойках»);
#   material — bevel (фаски на твёрдых поверхностях, м), wear (износ 0..1), toon (заливка тона 0..1).
# Значение None — «не трогать, как решили профили команды». Неизвестные ключи игнорируются с предупреждением.
import json, os, copy

DEFAULT = dict(
    light=dict(scheme=None, key=None, fill=None, rim=None, side=None, temp=None, ambient=1.0),   # ambient — множитель света неба/окружения (тени светлее/темнее)
    air=dict(depth=1.0, fog=1.0),
    optics=dict(lens='cinema', dof=1.0),
    color=dict(palette=None, sat=1.0, contrast=1, exposure=0.0),   # contrast −3..3 → кривая AgX; exposure — ступени к экспозиции
    neon=dict(on=False, strength=1.0, colors=['#FF2E88', '#2EC8FF'], count=3),
    post=dict(grain=0.2, vignette=0.45, halation=0.35, twos=False),   # монтаж (assemble.sh): зерно, виньетка, ореол бликов
    material=dict(bevel=0.0, wear=0.0, toon=0.0),
)

# Схемы света: правка профиля оператора (key/fill/rim — множители и доли, side — угол ключа от камеры, temp — K)
SCHEMES = {
    'рембрандт': dict(side=65, fill=0.15, rim=0.6),           # классический портрет: треугольник света на щеке
    'контровой': dict(side=140, fill=0.18, rim=1.5),          # ключ из-за плеча, силуэт обведён: драма, тайна
    'high-key':  dict(side=35, fill=0.6, rim=0.4, key=0.9),   # светло и мягко: комедия, реклама, Pixar-день
    'нуар':      dict(side=95, fill=0.04, rim=1.1, key=1.2),  # жёсткий боковой, почти чёрная тень
    'неон':      dict(side=110, fill=0.1, rim=1.6, temp=7000),  # холодный ключ, цветной контур от вывесок
}

PRESETS = {
    'кино':  {},
    'pixar': dict(light=dict(scheme='high-key', ambient=2.2), air=dict(depth=1.3), optics=dict(lens='dream', dof=1.2),
                  color=dict(sat=1.15, contrast=0, exposure=0.35), post=dict(grain=0.05, vignette=0.25), material=dict(bevel=0.004)),
    'нуар':  dict(light=dict(scheme='нуар', ambient=0.45), air=dict(depth=0.35, fog=0.9), optics=dict(lens='clean'),
                  color=dict(sat=0.0, contrast=3, exposure=-0.2), post=dict(grain=0.4, vignette=0.7, halation=0.15)),
    'неон':  dict(light=dict(scheme='неон'), air=dict(depth=1.2, fog=1.8), optics=dict(lens='anamorphic'),
                  color=dict(sat=1.2), neon=dict(on=True, strength=1.0), post=dict(halation=0.6)),
    'тун':   dict(light=dict(scheme='high-key', ambient=2.0), air=dict(depth=0.6), optics=dict(lens='clean', dof=0.5),
                  color=dict(sat=1.25, contrast=0, exposure=0.25), post=dict(grain=0.0, vignette=0.15, halation=0.1, twos=True), material=dict(toon=1.0)),
}

def _merge(dst, src, path=''):
    for k, v in (src or {}).items():
        if k.startswith('_') or k == 'preset' or k in ('lens', 'passes', 'post') and not isinstance(v, dict) and path == '':
            continue      # ключи старого формата look.json (стилевые репо) читает film.py
        if k not in dst: print(f'look: неизвестный ключ {path}{k} — пропускаю', flush=True); continue
        if isinstance(dst[k], dict) and isinstance(v, dict): _merge(dst[k], v, f'{path}{k}.')
        else: dst[k] = v
    return dst

def load(spec=None, overrides=None):
    """spec: имя пресета, путь к look.json или словарь. overrides — правки сценария поверх (тот же формат)."""
    lk = copy.deepcopy(DEFAULT)
    if isinstance(spec, str) and spec.endswith('.json') and os.path.exists(spec):
        d = json.load(open(spec, encoding='utf-8'))
        _merge(lk, PRESETS.get(d.get('preset', ''), {})); _merge(lk, d.get('look', d))
        if isinstance(d.get('lens'), str): lk['optics']['lens'] = d['lens']
    elif isinstance(spec, str) and spec:
        if spec not in PRESETS: print(f'look: пресета «{spec}» нет, есть {sorted(PRESETS)} — беру «кино»', flush=True)
        _merge(lk, PRESETS.get(spec, {}))
    elif isinstance(spec, dict): _merge(lk, spec)
    _merge(lk, overrides)
    return lk

def light(L, lk):
    """Профиль света оператора → с поправками стиля: сначала схема, потом точные поля."""
    out = dict(L); s = SCHEMES.get(lk['light'].get('scheme') or '', {})
    out.update(s)
    for k in ('key', 'fill', 'rim', 'side', 'temp'):
        if lk['light'].get(k) is not None: out[k] = lk['light'][k]
    return out

CONTRAST = {-3: 'AgX - Very Low Contrast', -2: 'AgX - Low Contrast', -1: 'AgX - Medium Low Contrast', 0: 'AgX - Base Contrast',
            1: 'AgX - Medium High Contrast', 2: 'AgX - High Contrast', 3: 'AgX - Very High Contrast'}

def tone(scene, lk):
    """Тональная кривая и экспозиция кадра из раздела color (вызывать после создания сцены и выбора экспозиции)."""
    c = int(max(-3, min(3, round(lk['color'].get('contrast', 1)))))
    try: scene.view_settings.look = CONTRAST[c]
    except TypeError: print(f'look: кривой {CONTRAST[c]} нет в этой сборке Blender', flush=True)
    scene.view_settings.exposure += lk['color'].get('exposure', 0.0)

# слова сценария → правки пульта (СВЕТ/ДЫМКА/ТУМАН_ВИД/НЕОН/НАСЫЩЕННОСТЬ/ЗЕРНО)
WORDS = {'СВЕТ': ('light', 'scheme', str), 'ДЫМКА': ('air', 'depth', float), 'ОБЪЁМ': ('air', 'fog', float),
         'НЕОН': ('neon', 'on', lambda v: v.strip().lower() not in ('0', 'нет', 'off', '')), 'НАСЫЩЕННОСТЬ': ('color', 'sat', float),
         'ЗЕРНО': ('post', 'grain', float), 'КОНТРАСТ': ('color', 'contrast', int), 'ВИНЬЕТКА': ('post', 'vignette', float), 'ОПТИКА': ('optics', 'lens', str)}

def from_words(pairs):
    """[(КЛЮЧ, значение)] из шапки сценария → overrides для load()."""
    ov = {}
    for k, v in pairs:
        if k in WORDS:
            sec, key, conv = WORDS[k]; ov.setdefault(sec, {})[key] = conv(v)
    return ov
