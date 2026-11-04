# Режиссёр: превращает биты сценария в раскадровку (список кадров) по почерку конкретного режиссёра.
# Правила, которые соблюдаются всегда: 180°-линия, нет «прыжков» (соседние кадры отличаются
# крупностью или углом ≥30°), монтажная склейка по действию, первый кадр сцены — общий.
import math, random, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dataclasses import dataclass

PACE = 0.6   # общий темп монтажа: <1 — чаще склейки, чем «классический» ASL режиссёра
SIZES = ['EWS', 'WS', 'FS', 'MS', 'MCU', 'CU', 'ECU']   # от сверхобщего до деталь
FRAME_H = {'EWS': 11.0, 'WS': 4.6, 'FS': 2.15, 'MS': 0.98, 'MCU': 0.66, 'CU': 0.46, 'ECU': 0.18, 'INS': 1.6}  # видимая высота кадра 2.39:1, с запасом над головой  # высота кадра, м

# Диафрагма по крупности (Super 35, как на площадке): крупные планы T2–2.8 — фон мягкий, но читается;
# общие T5.6–8 — пространство резкое. Профиль режиссёра сдвигает таблицу (Финчер/Нолан мельче ГРИП, Кубрик/Андерсон глубже).
TSTOP = {'ECU': 2.0, 'CU': 2.2, 'MCU': 2.8, 'MS': 3.5, 'FS': 4.0, 'WS': 5.6, 'EWS': 8.0, 'INS': 2.8}

# Точки интереса локации для вставок «на архитектуру»: (цель, откуда смотреть, крупность в метрах кадра)
POIS = {'sponza': {
    'lion_w':   ((-11.1, 0.25, 1.45), (-7.6, 0.25, 1.5), 'рельеф льва у входа'),
    'lion_e':   ((10.2, 0.25, 1.45), (6.6, 0.25, 1.5), 'лев в конце зала, куда он бежит'),
    'arcade_n': ((0.0, 4.8, 6.5), (0.0, -1.2, 2.5), 'верхняя галерея: колонны и арки', 40),
    'arches_s': ((-3.0, -4.5, 3.5), (0.5, 0.8, 1.6), 'резьба арки'),
    'nave_up':  ((0.0, 0.3, 9.0), (-8.0, 0.3, 1.5), 'взгляд вверх вдоль нефа, к небу', 18),
}}

# Профили собираются из съёмочной группы (studio/crew): режиссёр + его оператор по умолчанию.
# В сценарии можно сменить оператора строкой «ОПЕРАТОР: deakins».
from crew import DIRECTORS, profile
from crew import emotions
import composition
PROFILES = {k: profile(k) for k in DIRECTORS}

@dataclass
class Shot:
    start: float; end: float
    size: str; azim: float; elev: float   # азимут относительно взгляда героя (0 — в лицо), высота камеры (°)
    lens: float; move: str; target: str   # target: head/chest/body/feet/sky
    dutch: float = 0.0; hand: float = 0.0; fstop: float = 2.8; thirds: float = 0.0; note: str = ''
    pov: bool = False
    poi: tuple = None
    comp: str = ''
    why: str = ''
    speed: float = 1.0     # <1 — слоумо (0.4 = в 2.5 раза медленнее), см. film.py «перерасчёт времени»

# Грамматика камеры: каждое движение — решение с причиной (как в режиссёрском сценарии оператора)
MOVE_WHY = {
    'static':    'штатив: камера не вмешивается — смотрим на поступок, а не на съёмку',
    'slow_push': 'медленный наезд: внимание сгущается, зритель придвигается к мысли героя',
    'push':      'наезд: момент решения — пространство сужается до лица',
    'dolly':     'долли: пространство раскрывается параллаксом, место становится объёмным',
    'slow_pull': 'отъезд: герой остаётся один, мир вокруг становится больше него',
    'track':     'боковой трэвеллинг на рельсах: идём рядом с героем, ритм шага — ритм кадра; микро-наезд 5% незаметно сближает',
    'follow':    'за спиной на Steadicam: видим то, к чему он идёт, мы — его тень',
    'lead':      'камера отступает перед ним: лицо и порыв, пространство открывается за спиной',
    'slow_tilt': 'панорама взгляда: ведём глаз зрителя туда, куда смотрит герой',
    'passby':    'камера стоит у земли, герой пролетает мимо объектива: скорость = быстрый параллакс и смаз',
    'pan':       'длинный объектив издалека ведёт панорамой: фон превращается в полосы, герой резкий',
    'orbit':     'низкий облёт: камера кружит вокруг героя — момент осознания становится монументальным',
}
SIZE_WHY = {'EWS': 'масштаб места', 'WS': 'герой в пространстве', 'FS': 'тело и жест целиком', 'MS': 'жест и лицо вместе',
            'MCU': 'эмоция с контекстом плеч', 'CU': 'мысль на лице', 'ECU': 'деталь, которую нельзя пропустить', 'INS': 'то, что важно миру'}

def lens_for(p, size):
    return p['lens']['wide'] if size in ('EWS', 'WS') else p['lens']['mid'] if size in ('FS', 'MS') else p['lens']['close']

def candidates(beat, first, p, pois=None):
    # first=True только для самого первого кадра сцены
    """Варианты кадра для бита: (крупность, азимут, высота, цель, движение, пометка). Смысл бита решает выбор."""
    A, low = beat.action, p['low']
    side = 90
    pois = pois or {}
    if first:
        ins = [('INS', k, 0, 'poi', 'push', 'архитектура: ' + v[2]) for k, v in pois.items() if k == 'nave_up']
        return ins + [('EWS', 15, 10, 'body', 'slow_push', 'устанавливающий: место и масштаб'), ('WS', 180, 4, 'body', 'follow', 'входим в сцену вместе с героем')]
    if A == 'walk':
        return [('FS', side, 2, 'body', 'track', 'боковой трэвеллинг'), ('MS', 25, -8 * low, 'chest', 'lead', 'камера отступает перед героем'),
                ('ECU', 70, -5, 'feet', 'track', 'шаги, деталь'), ('WS', 160, 6, 'body', 'follow', 'со спины: куда он идёт'),
                ('EWS', 120, 12, 'body', 'static', 'одиночество в пространстве'), ('MCU', 35, -4, 'head', 'lead', 'лицо в движении')]
    if A == 'run':
        return [('MS', side, -6, 'chest', 'track', 'бег сбоку'), ('FS', 20, -18 * low - 6, 'body', 'lead', 'снизу спереди: порыв'),
                ('WS', 170, 4, 'body', 'follow', 'бег к цели'), ('ECU', 80, -4, 'feet', 'track', 'удары стоп'), ('CU', 30, -6, 'head', 'lead', 'лицо в беге'), ('EWS', 195, 14, 'body', 'static', 'финал: он уходит в свет'),
                # язык скорости (гонки, погони): камера медленнее героя — он пролетает мимо низкого объектива;
                # длинный объектив в панораме — фон смазан, скорость читается по смазу, а не по тряске
                ('FS', 70, -4, 'body', 'passby', 'мимо камеры: низко у земли, он пролетает у объектива'),
                ('MS', 90, 0, 'chest', 'pan', 'длинный объектив, панорама: фон смазан скоростью'),
                ('FS', 145, -8, 'body', 'follow', '3/4 сзади-сбоку, низко у ног: земля летит под объективом')]
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
    p = profile(p_name, getattr(scene, 'dp', None)); crnd = random.Random(seed + 1); rnd = random.Random(seed); pois = POIS.get(scene.world, {})
    shots = []; prev = None
    for bi, bt in enumerate(scene.beats):
        base_c = candidates(bt, False, p, pois)
        # бит режется на кадры: длина ~ ASL, эмоциональные биты — чуть длиннее, напряжённые — короче
        emo = emotions.get(bt.emotion)
        asl = p['asl'] * (0.75 if bt.tension else 1.15 if bt.epic and bt.action != 'run' else 0.85 if bt.action == 'run' else 1.0)
        if emo: asl = p['asl'] * emo['asl']      # грамматика эмоции задаёт темп монтажа бита
        # смысловой минимум: эмоциональный бит снимается хотя бы 2 планами (лицо + то, что он видит / пространство)
        need = 3 if (bt.action == 'run' and bt.epic and bt.dur > 2.5) else 2 if (bt.emotion or bi == 0 or bt.action == 'stand') and bt.dur > 2.4 else 1
        n = max(need, math.ceil(bt.dur / (asl * PACE) - 0.25))
        # экшен: планы 1–2.5 с (короче — каша, длиннее — провисает); установочный первый план сцены длиннее и шире
        if bt.action == 'run': n = max(1, min(max(n, math.ceil(bt.dur / 2.5)), int(bt.dur / 1.0)))
        cuts = [bt.start + bt.dur * i / n for i in range(n + 1)]
        for k in range(n):
            # сначала то, что смысл бита ставит первым; дальше — с весами профиля, без повторов и прыжков
            cands = candidates(bt, True, p, pois) if (bi == 0 and k == 0) else base_c
            pw = lambda c: p['prefer'].get('MS' if c[0] in ('POV', 'INS') else c[0], 1) * ((emo['sizes'].get(c[0], 0.6)) if emo else 1)
            order = cands if k == 0 else sorted(cands, key=lambda c: -pw(c) * (0.5 + rnd.random()))
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
                  'hand': mv, 'track': mv, 'float': mv,
                  # облёт (Бэй): на остановке/эмоции крупный и средний планы — низкий облёт вокруг героя
                  'orbit': 'orbit' if (size in ('FS', 'MS', 'MCU', 'CU') and bt.action not in ('walk', 'run') and (bt.epic or bt.emotion or bt.tension)) else
                           ('push' if size in ('MCU', 'CU') and mv not in ('track', 'follow', 'lead') else mv)}[p['move']]
            if mv == 'orbit' and prev and prev.move == 'orbit': mv = 'push' if size in ('MCU', 'CU') else 'slow_push'   # приём, а не манера: не подряд
            if mv == 'orbit': el = min(el, -12)      # облёт всегда снизу: герой монументален
            if bt.epic and size in ('CU', 'MCU') and p['move'] in ('push', 'slow') and mv not in ('track', 'follow', 'lead'): mv = 'push'
            if p['move'] == 'push' and mv == 'push' and bt.action in ('walk', 'run') and size != 'INS': mv = 'lead'   # на движущегося героя «наезд» = ведём спереди
            # движение через склейку: после движущейся камеры статичный план «подхватывает» движение медленным наездом
            if prev and (prev.move in ('push', 'track', 'follow', 'lead') or prev.poi) and mv == 'static' and size != 'INS': mv = 'slow_push'
            sh = Shot(cuts[k], cuts[k + 1], size, az, el, lens_for(p, size), mv, tgt,
                      dutch=(p['dutch'] * (1 if (len(shots) % 2) else -1)) if bt.tension else 0.0,
                      hand=p['hand'], fstop=p['fstop'], note=note, pov=pov,
                      thirds=0.0 if p['sym'] > 0.7 else (0.18 if size in ('MS', 'MCU', 'CU', 'FS') else 0.0))
            sh.fstop = TSTOP[size] * p['fstop'] / 2.8
            sh.poi = pois[poi] if poi else None
            if size == 'INS': sh.lens = sh.poi[3] if len(sh.poi) > 3 else p['lens']['close']
            elif mv == 'pan': sh.lens = max(sh.lens * 1.8, 85)       # панорама скорости — телевик
            elif mv == 'passby': sh.lens = min(sh.lens, 24)          # пролёт — широкий угол вплотную
            # погоня: стабилизированная камера (Russian Arm, гироголова) — без «качки»; скорость передают параллакс,
            # смаз фона и лёгкий андеркранк (+8%: больше — лица искажаются, как предупреждает К. Миранда на «F1»)
            if bt.action == 'run' and size != 'INS':
                sh.hand = 0.0
                if sh.speed == 1.0: sh.speed = 1.08
            elif not pov:
                # композиция кадра: вкус режиссёра и оператора × эмоция бита; соседние планы не повторяют одну схему
                sh.comp = composition.choose(size, bt.emotion, p['comp'], crnd, prev.comp if prev else None, [x.comp for x in shots])
                r = composition.RULES[sh.comp]
                if r.get('snap_axis') and mv not in ('track',): sh.azim = 180 if 90 < (sh.azim % 360) < 270 else 0
                if sh.comp == 'scale': sh.lens = min(sh.lens, round(p['lens']['wide'] * 0.75))   # шире, чтобы фигура стала крошечной
                if 'elev' in r and size not in ('EWS',): sh.elev = r['elev'] if r['elev'] < 0 else max(sh.elev, r['elev'])
                # быстрый монтаж действия: точка внимания в центре («Безумный Макс»), глаз не ищет героя после склейки
                if bt.action == 'run' and (sh.end - sh.start) < 1.5 and mv not in ('pan',): sh.comp = 'centered'
            # слоумо — приём момента осознания: облёт на эмоциональном бите (почерк Бэя), не чаще раза на сцену
            if mv == 'orbit' and not any(x.speed < 1 for x in shots): sh.speed = 0.4
            sh.why = f"{SIZE_WHY.get(size, '')}; {MOVE_WHY.get(mv, mv)}" + ('; слоумо ×0.4: время растягивается в точке осознания' if sh.speed < 1 else '')
            shots.append(sh); prev = sh
    # финал: последний общий план — симметрия по оси и штатив. Взгляд не ищет, куда смотреть:
    # фигура на линии схода, свет — цель. Ясный фокус важнее «интересной» асимметрии в последнем кадре фильма
    if shots and shots[-1].size in ('EWS', 'WS') and not shots[-1].pov and not shots[-1].poi:
        f_ = shots[-1]; f_.comp = 'centered'; f_.hand = 0.0
        f_.azim = 180 if 90 < (f_.azim % 360) < 270 else 0
        if f_.move in ('static', 'slow_push'): f_.move = 'static'
        f_.why = 'финал: симметрия по оси, штатив — фигура на линии схода, свет как цель'
    return shots

def describe(shots):
    return '\n'.join(f'{s.start:5.1f}–{s.end:5.1f}  {s.size:3s} {s.lens:>3.0f}мм  {s.move:10s} {s.comp:10s} {s.note}' for s in shots)
