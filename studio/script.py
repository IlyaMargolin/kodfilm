# Разбор сценария. Формат — обычный текст: шапка с параметрами сцены и строки действий.
#
#   СЦЕНА: Храм на закате
#   МИР: sponza
#   НЕБО: venice_sunset_1k 0.6
#   СОЛНЦЕ: 38 172 7          (высота°, азимут°, сила)
#   ТУМАН: 0.012
#   ГЕРОЙ: Soldier
#   РЕЖИССЁР: villeneuve
#   СТИЛЬ: restyle/neon      (необязательно: стиль поверх ядра, см. studio/styles.py)
#   ОПЕРАТОР: fraser          (необязательно: по умолчанию «свой» оператор режиссёра)
#   КОМПОЗИТОР: zimmer        (необязательно)
#   ---
#   [идёт -12,0 -> 0,0] Он входит из тени и идёт по храму.
#   [стоит 2.5] Останавливается.
#   [смотрит вверх 3.5 | благоговение] Поднимает голову к свету.
#   [бежит 0,0 -> 11,0 | решимость] Бежит к свету.
#
# Каждая строка — «бит» сцены. В квадратных скобках действие и эмоция, дальше текст для режиссёра.
import re
from dataclasses import dataclass, field

ACTIONS = {'идёт': 'walk', 'идет': 'walk', 'бежит': 'run', 'стоит': 'stand', 'смотрит вверх': 'look_up',
           'смотрит вниз': 'look_down', 'оборачивается': 'turn', 'смотрит': 'look'}
TENSE = {'страх', 'тревога', 'сомнение', 'паника', 'угроза', 'смятение'}
EPIC = {'благоговение', 'решимость', 'триумф', 'надежда', 'восторг'}

@dataclass
class Beat:
    action: str
    text: str
    emotion: str = ''
    dur: float = 0.0
    a: tuple = None
    b: tuple = None
    start: float = 0.0
    tempo: float = 1.0   # «медленно» 0.75, «быстро» 1.2 — скорость движения и мокапа
    @property
    def tension(self): return self.emotion in TENSE
    @property
    def epic(self): return self.emotion in EPIC

@dataclass
class Scene:
    title: str = ''
    world: str = 'sponza'
    sky: tuple = ('venice_sunset_1k.hdr', 0.5)
    sun: tuple = (35, 170, 6)
    fog: float = 0.0
    hero: str = 'Soldier.glb'
    director: str = 'villeneuve'
    dp: str = None
    composer: str = None
    palette: str = ''   # ведущая палитра сцены (studio/palette.py), пусто — по небу
    style: str = ''     # «restyle/neon»: стиль из style.json стилевого репозитория (studio/styles.py)
    look: str = ''      # ВИД: пресет пульта стиля (studio/look.py: кино, pixar, нуар, неон, тун) или путь к look.json
    look_words: list = field(default_factory=list)
    place: tuple = None    # МЕСТО: x,y — где герой стоит в начале (если первый бит без пути)
    face: tuple = None     # ЛИЦОМ: dx,dy — куда он смотрит в начале
    practicals: list = field(default_factory=list)   # ПРАКТИК: кольцо x,y,z r #цвет — свет в кадре (studio/neon.py)   # СВЕТ/ДЫМКА/ОБЪЁМ/НЕОН/... — правки пульта на сцену
    beats: list = field(default_factory=list)

def _pt(s): x, y = s.split(','); return (float(x), float(y))

def parse(text):
    sc = Scene(); body = False
    for raw in text.splitlines():
        line = raw.split('#')[0].strip() if not raw.strip().startswith('[') else raw.strip()
        if not line: continue
        if line.startswith('---'): body = True; continue
        if not body:
            k, _, v = line.partition(':'); k = k.strip().upper(); v = v.strip()
            if k == 'СЦЕНА': sc.title = v
            elif k == 'МИР': sc.world = v
            elif k == 'НЕБО': p = v.split(); sc.sky = (p[0] + ('' if p[0].endswith('.hdr') else '.hdr'), float(p[1]) if len(p) > 1 else 0.5)
            elif k == 'СОЛНЦЕ': sc.sun = tuple(float(x) for x in v.split())
            elif k == 'ТУМАН': sc.fog = float(v)
            elif k == 'ГЕРОЙ': sc.hero = v   # роль из cast.json фильма, id актёра или файл модели — разрешается в film.py
            elif k == 'РЕЖИССЁР' or k == 'РЕЖИССЕР': sc.director = v.lower()
            elif k == 'ОПЕРАТОР': sc.dp = v.lower()
            elif k == 'КОМПОЗИТОР': sc.composer = v.lower()
            elif k == 'СТИЛЬ': sc.style = v.lower()
            elif k == 'ПАЛИТРА': sc.palette = v.lower()
            elif k == 'МЕСТО': sc.place = _pt(v)
            elif k == 'ЛИЦОМ': sc.face = _pt(v)
            elif k == 'ПРАКТИК':
                pp = v.split(); kind = pp[0].lower()
                xyz = tuple(float(x) for x in pp[1].split(',')); r = float(pp[2]) if len(pp) > 2 else 0.5
                col = next(('#' + x.lstrip('#') for x in pp[3:] if re.fullmatch(r'#?[0-9a-fA-F]{6}', x)), '#FFB060')   # цвет без «#»: «#» в шапке — комментарий
                sc.practicals.append(dict(kind=kind, at=xyz, r=r, color=col))
            elif k == 'ВИД': sc.look = v.lower() if not v.endswith('.json') else v
            elif k in ('СВЕТ', 'ДЫМКА', 'ОБЪЁМ', 'ОБЪЕМ', 'НЕОН', 'НАСЫЩЕННОСТЬ', 'ЗЕРНО', 'КОНТРАСТ', 'ВИНЬЕТКА', 'ОПТИКА'):
                sc.look_words.append(('ОБЪЁМ' if k == 'ОБЪЕМ' else k, v.lower() if k in ('СВЕТ', 'ОПТИКА') else v))
            continue
        m = re.match(r'\[(.+?)\]\s*(.*)', line)
        if not m: continue
        inner, txt = m.groups()
        act_s, _, emo = inner.partition('|')
        act_s = act_s.strip(); emo = emo.strip()
        name = next(k for k in sorted(ACTIONS, key=len, reverse=True) if act_s.startswith(k))
        rest = act_s[len(name):].strip()
        bt = Beat(ACTIONS[name], txt.strip(), emo)
        if '->' in rest:
            a_, b_ = rest.split('->'); bt.a, bt.b = _pt(a_.strip()), _pt(b_.strip())
        elif rest:
            bt.dur = float(rest)
        if 'медленно' in txt.lower(): bt.tempo = 0.78
        if 'быстро' in txt.lower() or 'срывается' in txt.lower(): bt.tempo = 1.1
        sc.beats.append(bt)
    return sc
