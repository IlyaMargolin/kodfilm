# Режиссёр: превращает биты сценария в раскадровку (список кадров) по почерку конкретного режиссёра.
# Правила, которые соблюдаются всегда: 180°-линия, нет «прыжков» (соседние кадры отличаются
# крупностью или углом ≥30°), монтажная склейка по действию, первый кадр сцены — общий.
import math, random
from dataclasses import dataclass

PACE = 0.6   # общий темп монтажа: <1 — чаще склейки, чем «классический» ASL режиссёра
SIZES = ['EWS', 'WS', 'FS', 'MS', 'MCU', 'CU', 'ECU']   # от сверхобщего до деталь
FRAME_H = {'EWS': 14.0, 'WS': 5.5, 'FS': 2.4, 'MS': 1.15, 'MCU': 0.7, 'CU': 0.42, 'ECU': 0.2, 'INS': 1.6}  # высота кадра, м

# Диафрагма по крупности (Super 35, как на площадке): крупные планы T2–2.8 — фон мягкий, но читается;
# общие T5.6–8 — пространство резкое. Профиль режиссёра сдвигает таблицу (Финчер/Нолан мельче ГРИП, Кубрик/Андерсон глубже).
TSTOP = {'ECU': 2.0, 'CU': 2.2, 'MCU': 2.8, 'MS': 3.5, 'FS': 4.0, 'WS': 5.6, 'EWS': 8.0, 'INS': 2.8}

# Точки интереса локации для вставок «на архитектуру»: (цель, откуда смотреть, крупность в метрах кадра)
POIS = {'sponza': {
    'lion_w':   ((-11.1, 0.25, 1.45), (-7.6, 0.25, 1.5), 'рельеф льва у входа'),
    'lion_e':   ((10.2, 0.25, 1.45), (6.6, 0.25, 1.5), 'лев в конце зала, куда он бежит'),
    'arcade_n': ((0.0, 4.8, 6.5), (0.0, -1.2, 2.5), 'верхняя галерея: колонны и арки'),
    'arches_s': ((-3.0, -4.5, 3.5), (0.5, 0.8, 1.6), 'резьба арки'),
}}

PROFILES = {
    # asl — средняя длина кадра (с), lens — любимые объективы по крупности, prefer — веса крупностей,
    # move — характер движения камеры, dutch — наклон горизонта при напряжении, sym — тяга к центральной симметрии,
    # low — склонность к нижнему ракурсу, hand — «ручная камера», fstop — глубина резкости
    'villeneuve': dict(asl=4.2, lens=dict(wide=24, mid=40, close=65), prefer=dict(EWS=3, WS=3, FS=2, MS=1.5, MCU=1, CU=1.5, ECU=0.5),
                       move='slow', dutch=0, sym=0.6, low=0.4, hand=0.0, fstop=2.8, desc='масштаб, тишина, силуэты, медленные наезды'),
    'kubrick':    dict(asl=5.0, lens=dict(wide=18, mid=28, close=50), prefer=dict(EWS=2, WS=3, FS=2, MS=1, MCU=0.7, CU=1, ECU=0.3),
                       move='dolly', dutch=0, sym=1.0, low=0.6, hand=0.0, fstop=5.6, desc='одноточечная перспектива, симметрия, неумолимый трэвеллинг'),
    'fincher':    dict(asl=3.0, lens=dict(wide=27, mid=40, close=65), prefer=dict(EWS=0.5, WS=1.5, FS=2, MS=3, MCU=2.5, CU=2, ECU=1),
                       move='locked', dutch=0, sym=0.3, low=0.2, hand=0.0, fstop=2.0, desc='точная камера, повторяет движение героя, холодный контраст'),
    'spielberg':  dict(asl=3.6, lens=dict(wide=21, mid=35, close=50), prefer=dict(EWS=1, WS=2, FS=2, MS=2, MCU=2, CU=2.5, ECU=1),
                       move='push', dutch=0, sym=0.2, low=0.7, hand=0.1, fstop=2.8, desc='наезд на лицо в момент откровения, герой снизу'),
    'nolan':      dict(asl=2.4, lens=dict(wide=28, mid=50, close=85), prefer=dict(EWS=1.5, WS=1.5, FS=1.5, MS=2, MCU=2.5, CU=3, ECU=1.5),
                       move='hand', dutch=0, sym=0.1, low=0.4, hand=0.6, fstop=2.0, desc='ручная камера, крупные планы, быстрый монтаж'),
    'anderson':   dict(asl=3.0, lens=dict(wide=27, mid=40, close=40), prefer=dict(EWS=1, WS=3, FS=3, MS=2, MCU=1, CU=1, ECU=0.5),
                       move='track', dutch=0, sym=1.0, low=0.0, hand=0.0, fstop=8.0, desc='строгая симметрия, фронтальность, боковой трэвеллинг'),
    'thriller':   dict(asl=2.2, lens=dict(wide=21, mid=35, close=85), prefer=dict(EWS=0.5, WS=1, FS=1.5, MS=2, MCU=2.5, CU=3, ECU=2),
                       move='hand', dutch=14, sym=0.0, low=0.5, hand=0.8, fstop=1.8, desc='голландский угол, нервная камера, детали'),
}

@dataclass
class Shot:
    start: float; end: float
    size: str; azim: float; elev: float   # азимут относительно взгляда героя (0 — в лицо), высота камеры (°)
    lens: float; move: str; target: str   # target: head/chest/body/feet/sky
    dutch: float = 0.0; hand: float = 0.0; fstop: float = 2.8; thirds: float = 0.0; note: str = ''
    pov: bool = False
    poi: tuple = None

def lens_for(p, size):
    return p['lens']['wide'] if size in ('EWS', 'WS') else p['lens']['mid'] if size in ('FS', 'MS') else p['lens']['close']

def candidates(beat, first, p, pois=None):
    # first=True только для самого первого кадра сцены
    """Варианты кадра для бита: (крупность, азимут, высота, цель, движение, пометка). Смысл бита решает выбор."""
    A, low = beat.action, p['low']
    side = 90
    pois = pois or {}
    if first:
        ins = [('INS', k, 0, 'poi', 'push', 'архитектура: ' + v[2]) for k, v in pois.items() if k == 'arches_s']
        return ins + [('EWS', 15, 10, 'body', 'slow_push', 'устанавливающий: место и масштаб'), ('WS', 180, 4, 'body', 'follow', 'входим в сцену вместе с героем')]
    if A == 'walk':
        return [('FS', side, 2, 'body', 'track', 'боковой трэвеллинг'), ('MS', 25, -8 * low, 'chest', 'lead', 'камера отступает перед героем'),
                ('ECU', 70, -5, 'feet', 'track', 'шаги, деталь'), ('WS', 160, 6, 'body', 'follow', 'со спины: куда он идёт'),
                ('EWS', 120, 12, 'body', 'static', 'одиночество в пространстве'), ('MCU', 35, -4, 'head', 'lead', 'лицо в движении')]
    if A == 'run':
        return [('MS', side, -6, 'chest', 'track', 'бег сбоку'), ('FS', 20, -18 * low - 6, 'body', 'lead', 'снизу спереди: порыв'),
                ('WS', 170, 4, 'body', 'follow', 'бег к цели'), ('ECU', 80, -4, 'feet', 'track', 'удары стоп'), ('CU', 30, -6, 'head', 'lead', 'лицо в беге'), ('EWS', 195, 14, 'body', 'static', 'финал: он уходит в свет')]
    if A == 'stand':
        return [('FS', 40, 0, 'body', 'static', 'остановка')] + [('INS', 'arcade_n', 0, 'poi', 'push', 'архитектура: верхняя галерея')] * ('arcade_n' in pois) + [('FS', 40, 0, 'body', 'static', 'остановка'), ('MS', 140, 3, 'chest', 'static', 'со спины: пауза'), ('WS', 100, 10, 'body', 'slow_push', 'герой и пространство')]
    if A == 'look_up':
        return [('CU', 20, -22, 'head', 'slow_push', 'лицо снизу: благоговение'), ('POV', 0, 70, 'sky', 'slow_tilt', 'что он видит: свет'),
                ('WS', 175, -25, 'body', 'static', 'снизу из-за спины: он и свод'), ('ECU', 15, -10, 'head', 'static', 'глаза')]
    if A == 'look_down':
        return [('WS', 200, 48, 'body', 'slow_pull', 'сверху: он маленький, сомнение'), ('MCU', 35, 8, 'head', 'static', 'лицо, тяжесть'),
                ('CU', 40, 15, 'head', 'slow_push', 'внутренний момент')]
    return [('MS', 30, 0, 'chest', 'static', '')]

def plan(scene, p_name, seed=7):
    p = PROFILES[p_name]; rnd = random.Random(seed); pois = POIS.get(scene.world, {})
    shots = []; prev = None
    for bi, bt in enumerate(scene.beats):
        base_c = candidates(bt, False, p, pois)
        # бит режется на кадры: длина ~ ASL, эмоциональные биты — чуть длиннее, напряжённые — короче
        asl = p['asl'] * (0.75 if bt.tension else 1.15 if bt.epic and bt.action != 'run' else 0.85 if bt.action == 'run' else 1.0)
        # смысловой минимум: эмоциональный бит снимается хотя бы 2 планами (лицо + то, что он видит / пространство)
        need = 3 if (bt.action == 'run' and bt.epic and bt.dur > 2.5) else 2 if (bt.emotion or bi == 0 or bt.action == 'stand') and bt.dur > 2.4 else 1
        n = max(need, math.ceil(bt.dur / (asl * PACE) - 0.25))
        cuts = [bt.start + bt.dur * i / n for i in range(n + 1)]
        for k in range(n):
            # сначала то, что смысл бита ставит первым; дальше — с весами профиля, без повторов и прыжков
            cands = candidates(bt, True, p, pois) if (bi == 0 and k == 0) else base_c
            order = cands if k == 0 else sorted(cands, key=lambda c: -p['prefer'].get('MS' if c[0] in ('POV', 'INS') else c[0], 1) * (0.5 + rnd.random()))
            pick = None
            for c in order:
                size = c[0]
                if prev and size == prev.size and size != 'INS' and abs(c[1] - prev.azim) < 30: continue        # прыжок
                if size == 'INS' and any(x.poi and x.note == c[5] for x in shots): continue                  # одну вставку один раз
                if prev and c[5] == prev.note: continue                                          # одно и то же дважды
                pick = c; break
            pick = pick or cands[0]
            size, az, el, tgt, mv, note = pick
            pov = size == 'POV'; poi = None
            if pov: size = 'WS'
            if size == 'INS': poi = az; az = 0
            if p['sym'] > 0.7 and size in ('EWS', 'WS') and not pov: az = 180 if az > 90 else 0   # симметрия по оси
            mv = {'slow': mv, 'dolly': 'dolly' if mv in ('static', 'slow_push') else mv, 'locked': mv, 'push': 'push' if size in ('MCU', 'CU') and mv not in ('track', 'follow', 'lead') else mv,
                  'hand': mv, 'track': mv}[p['move']]
            if bt.epic and size in ('CU', 'MCU') and p['move'] in ('push', 'slow') and mv not in ('track', 'follow', 'lead'): mv = 'push'
            if p['move'] == 'push' and mv == 'push' and bt.action in ('walk', 'run'): mv = 'lead'   # на движущегося героя «наезд» = ведём спереди
            sh = Shot(cuts[k], cuts[k + 1], size, az, el, lens_for(p, size), mv, tgt,
                      dutch=(p['dutch'] * (1 if (len(shots) % 2) else -1)) if bt.tension else 0.0,
                      hand=p['hand'] + (0.25 if bt.action == 'run' else 0), fstop=p['fstop'], note=note, pov=pov,
                      thirds=0.0 if p['sym'] > 0.7 else (0.18 if size in ('MS', 'MCU', 'CU', 'FS') else 0.0))
            sh.fstop = TSTOP[size] * p['fstop'] / 2.8
            sh.poi = pois[poi] if poi else None
            if size == 'INS': sh.lens = p['lens']['close']
            shots.append(sh); prev = sh
    return shots

def describe(shots):
    return '\n'.join(f'{s.start:5.1f}–{s.end:5.1f}  {s.size:3s} {s.lens:>3.0f}мм  {s.move:10s} {s.note}' for s in shots)
