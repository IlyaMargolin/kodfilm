# Съёмка: сценарий -> мир -> постановка героя -> раскадровка режиссёра -> камеры -> кадры.
# python studio/film.py -- --script films/hram/script.txt --out out/hram --w 1280 --h 720 [--frames all|1-100|10,20] [--board]
import sys, os, json, math, argparse, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector, Euler, Quaternion
import world, script, director, composition

ap = argparse.ArgumentParser()
ap.add_argument('--script', required=True); ap.add_argument('--out', default='out/film')
ap.add_argument('--w', type=int, default=1280); ap.add_argument('--h', type=int, default=0); ap.add_argument('--fps', type=int, default=24)
ap.add_argument('--frames', default='all'); ap.add_argument('--chunk', type=int, default=0); ap.add_argument('--chunks', type=int, default=1)
ap.add_argument('--taa', type=int, default=10); ap.add_argument('--board', action='store_true', help='раскадровка: по кадру из середины каждого плана')
ap.add_argument('--director', default=None)
ap.add_argument('--engine', default='eevee', choices=['eevee', 'cycles'], help='cycles — трассировка путей (для GPU-фермы на Kaggle)')
ap.add_argument('--samples', type=int, default=96)
ap.add_argument('--fogk', type=float, default=0.5, help='множитель плотности тумана в Cycles: настоящий объём гуще, чем в EEVEE')
ap.add_argument('--ev', type=float, default=None, help='экспозиция; в Cycles по умолчанию +0.9: нет фальшивого фонового света EEVEE, честный свет темнее')
ap.add_argument('--passes', action='store_true', help='слои AOV: EXR (глубина, туман, нормали) + 16-бит PNG глубины')
ap.add_argument('--hero', default=None, help='заменить актёра главной роли (id из studio/cast/actors), например pilgrim')
ap.add_argument('--save', default=None, help='сохранить сцену .blend (проверка постановки)')
ap.add_argument('--lens', default='cinema', help='clean|cinema|anamorphic|dream|none — блум, анаморфные блики, аберрация')
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
FPS = a.fps
if not a.h: a.h = int(round(a.w / 2.39 / 2)) * 2   # кадр сразу 2.39:1 — никаких чёрных полос, плеер сам впишет
scn = script.parse(open(a.script, encoding='utf-8').read())
if a.director: scn.director = a.director

# ---------- мир ----------
sc = world.new_scene(a.w, a.h, FPS, engine='CYCLES' if a.engine == 'cycles' else 'BLENDER_EEVEE', TAA=a.samples if a.engine == 'cycles' else a.taa)
sc.view_settings.exposure = a.ev if a.ev is not None else (0.9 if a.engine == 'cycles' else sc.view_settings.exposure)
# --lens: имя стиля линзы (clean|cinema|anamorphic|dream) или путь к look.json стилевого репозитория:
#   {"lens": "cinema", "passes": true, "post": "../kodfilm-restyle/post.py"} — post вызывается после рендера
#   с аргументами <папка кадров> <meta.json> (стадия post из style.json: нужны beauty, depth, motion)
LOOK = {}
if scn.style and a.lens == 'cinema':   # СТИЛЬ: из сценария — look стадии post, если стилевой репозиторий рядом
    import styles; lf = styles.look_file(scn.style)
    if lf: a.lens = lf
    else: print(f'стиль {scn.style}: look-файла для ядра нет (стиль рисует в своём движке или репозиторий не скачан)', flush=True)
if a.lens.endswith('.json'):
    LOOK = json.load(open(a.lens, encoding='utf-8')); LOOK['_dir'] = os.path.dirname(os.path.abspath(a.lens))
    a.lens = LOOK.get('lens', 'cinema'); a.passes = a.passes or LOOK.get('passes', False)
if a.lens != 'none':
    import lens; lens.setup(sc, a.lens)
import palette
if a.lens != 'none': palette.setup(sc)      # грейд по палитре кадра (после линзы)
if a.passes:
    import lens; lens.passes(sc, a.out)
if scn.world == 'sponza': world.set_sponza()
world.hdri(scn.sky[0], scn.sky[1])
sun = world.sun(scn.sun[0], scn.sun[1], scn.sun[2] if len(scn.sun) > 2 else 6)
from crew import profile as _cp
HAZE = 0.6 + 0.5 * _cp(scn.director, getattr(scn, 'dp', None))['light'].get('haze', 0.8)   # дымка — инструмент оператора: контровой становится лучами
fogobj = world.fog(scn.fog * HAZE * (a.fogk if a.engine == 'cycles' else 1.0), size=(40, 24, 16)) if scn.fog > 0 else None

# ---------- постановка героя ----------
import cast
FILM_DIR = os.path.dirname(os.path.abspath(a.script)); HERO = a.hero or scn.hero
hero = world.Actor(cast.resolve(HERO, FILM_DIR))
SPEC = cast.spec(HERO, FILM_DIR) or {}
body = None; HOODED = False
if SPEC.get('human'):        # живой человек: своё тело (MakeHuman CC0) на скелете мокапа + костюм
    import human, wardrobe
    hs = dict(SPEC['human'])
    body = human.build_actor(hero.arm, hs)
    if hs.get('wardrobe') == 'robe': wardrobe.robe(body, hero.arm, color=tuple(hs.get('cloth', (0.09, 0.075, 0.06))), hood=hs.get('hood', True))
    HOODED = hs.get('wardrobe') == 'robe' and hs.get('hood', True)
    if hs.get('groom', True):   # волосы и борода прядями (Principled Hair)
        import groom
        groom.groom(body, color=tuple(hs.get('hair', (0.03, 0.022, 0.016))), grey=hs.get('grey', 0.25), beard_len=hs.get('beard', 0.03 if hs.get('gender', 1) > 0.5 else 0),
                    hooded=hs.get('wardrobe') == 'robe' and hs.get('hood', True))
# клипы мокапа к одному курсу: стойка и бег развёрнуты так же, как ходьба (иначе тело «крутится на подставке»)
with world.bones_only():   # позовые циклы без пересчёта сеток и волос
    for _act in ('idle', 'run'):
        if _act in hero.actions and 'walk' in hero.actions:
            print('align', _act, round(math.degrees(hero.align_facing(_act, 'walk')), 1), 'deg', flush=True)
    speed = {k: hero.cycle_speed(k) for k in ('walk', 'run') if k in hero.actions}
ACT = {'walk': 'walk', 'run': 'run', 'stand': 'idle', 'look_up': 'idle', 'look_down': 'idle', 'look': 'idle', 'turn': 'idle'}
pos = Vector((0, 0, 0)); yaw = 0.0
t = 0.0
for i, bt in enumerate(scn.beats):
    if bt.a and bt.b:
        if i == 0: pos = Vector((*bt.a, 0))
        d = (Vector((*bt.b, 0)) - Vector((*bt.a, 0))).length
        bt.dur = d / (speed[bt.action] * bt.tempo)
    bt.start = t; t += bt.dur
TOTAL = int(round(t * FPS)) + 1

# траектория корня и поворот, покадрово
path = []; cur = Vector((*scn.beats[0].a, 0)) if scn.beats[0].a else Vector((0, 0, 0))
first_dir = next(((Vector((*b.b, 0)) - Vector((*b.a, 0))).normalized() for b in scn.beats if b.a), Vector((1, 0, 0)))
yaw = math.atan2(first_dir.y, first_dir.x) - math.pi / 2
for f in range(1, TOTAL + 1):
    tt = (f - 1) / FPS
    bt = next((b for b in scn.beats if b.start <= tt < b.start + b.dur), scn.beats[-1])
    if bt.a and bt.b:
        u = min(1, max(0, (tt - bt.start) / bt.dur))
        bi_ = scn.beats.index(bt)
        stop_after = bi_ + 1 < len(scn.beats) and not scn.beats[bi_ + 1].a
        start_from = bi_ > 0 and not scn.beats[bi_ - 1].a
        # тело не останавливается мгновенно: последние ~0.6 с замедление, первые ~0.4 с разгон
        eo = min(0.6 / bt.dur, 0.3) if stop_after else 0; ei = min(0.4 / bt.dur, 0.25) if start_from else 0
        def ease(x):
            if ei and x < ei: return x * x / (2 * ei) / (1 - ei / 2 - eo / 2)
            if eo and x > 1 - eo: y = 1 - x; return 1 - y * y / (2 * eo) / (1 - ei / 2 - eo / 2)
            return (x - ei / 2) / (1 - ei / 2 - eo / 2)
        u = min(1, max(0, ease(u)))
        A_, B_ = Vector((*bt.a, 0)), Vector((*bt.b, 0)); cur = A_.lerp(B_, u)
        dv = (B_ - A_).normalized(); target_yaw = math.atan2(dv.y, dv.x) - math.pi / 2
        yaw += (target_yaw - yaw) * 0.15
    path.append((cur.copy(), yaw))
for f, (p, y) in enumerate(path, start=1):
    hero.root.location = p; hero.root.rotation_euler = (0, 0, y)
    hero.root.keyframe_insert('location', frame=f); hero.root.keyframe_insert('rotation_euler', frame=f)
for fc in hero.root.animation_data.action.fcurves if hasattr(hero.root.animation_data.action, 'fcurves') else []:
    for k in fc.keyframe_points: k.interpolation = 'LINEAR'

# действия тела: клипы мокапа с плавными переходами (две дорожки NLA, верхняя «вплывает»)
ad = hero.arm.animation_data
tracks = [hero.track, ad.nla_tracks.new()]
B = int(0.8 * FPS)   # переход между клипами 0.8 с: поза не «ломается» резко
for i, bt in enumerate(scn.beats):
    act = ACT[bt.action]; s = int(bt.start * FPS) + 1; e = int((bt.start + bt.dur) * FPS) + 1
    tr = tracks[i % 2]; ac = hero.actions[act]
    s0 = max(1, s - (B if i % 2 == 0 else B // 2)); e0 = min(TOTAL + B, e + (B if i % 2 == 0 else B // 2))
    # предвосхищение: герой «знает», что остановится — стойка вплывает во время торможения и полностью
    # собрана в момент остановки, а не доворачивается после (живой человек гасит шаг уже в позу)
    if i % 2 and i > 0 and scn.beats[i - 1].a and not bt.a: s0 = max(1, s - B)
    st = tr.strips.new(f'{act}{i}', s0, ac)
    L = ac.frame_range[1] - ac.frame_range[0]
    st.action_frame_start, st.action_frame_end = ac.frame_range
    st.scale = 1.0 / bt.tempo; st.repeat = max(1.0, (e0 - s0) / (L * st.scale)); st.frame_end = e0
    st.extrapolation = 'NOTHING' if i % 2 else ('HOLD' if i == 0 else 'NOTHING')
    st.use_auto_blend = False
    if i % 2: st.blend_in = st.blend_out = B
    if i == len(scn.beats) - 1: st.extrapolation = 'HOLD_FORWARD'
# взгляд: поворот головы/шеи поверх тела (аддитивно)
look_tr = ad.nla_tracks.new()
look = bpy.data.actions.new('look')
ad.action = look
pb = [hero.arm.pose.bones[n] for n in (hero.head, hero.head.replace('Head', 'Neck')) if n in hero.arm.pose.bones]
for b in pb: b.rotation_mode = 'QUATERNION'
def pitch(f):
    tt = (f - 1) / FPS; v = 0
    for bt in scn.beats:
        if bt.action in ('look_up', 'look_down'):
            k = min(1, max(0, (tt - bt.start) / 0.9)) * min(1, max(0, (bt.start + bt.dur - tt) / 0.7))
            k = k * k * (3 - 2 * k)
            v += k * (-0.55 if bt.action == 'look_up' else 0.45)
    return v
for f in range(1, TOTAL + 1, 2):
    pv = pitch(f)
    for j, b in enumerate(pb):
        b.rotation_quaternion = Quaternion((1, 0, 0), pv * (0.6 if j == 0 else 0.4)); b.keyframe_insert('rotation_quaternion', frame=f)
ad.action = None
ls = look_tr.strips.new('look', 1, look); ls.blend_type = 'COMBINE'; ls.extrapolation = 'HOLD'
# мимика: выражение бита, асимметрия, микродвижения, моргания (studio/face.py)
if body is not None:
    import face; print('мимика: морганий', face.act(body, scn.beats, FPS, TOTAL), flush=True)

# опора стоп: ступня в контакте с полом прибита (IK), не скользит и не проворачивается
if not os.environ.get('KF_NOPLANT'): print('plant', hero.plant_feet(1, TOTAL), flush=True)

# ---------- раскадровка ----------
shots = director.plan(scn, scn.director)
print(director.describe(shots), flush=True)

# покадровые данные героя: голова, грудь, стопы (для камер и для звука шагов)
track_pts = []
footL = hero.foot; footR = hero.foot.replace('Left', 'Right')
_bo = world.bones_only().__enter__()
for f in range(1, TOTAL + 1):
    sc.frame_set(f)
    M = hero.arm.matrix_world
    hd = M @ hero.arm.pose.bones[hero.head].head
    fl = M @ hero.arm.pose.bones[footL].head; fr = M @ hero.arm.pose.bones[footR].head
    ey = human.eyes_world(body, hero.arm) if body is not None else None
    ey = ey or [hd + Vector((0, 0, 0.04))] * 2
    track_pts.append(dict(head=hd.copy(), root=hero.root.location.copy(), yaw=hero.root.rotation_euler.z, fl=fl.copy(), fr=fr.copy(),
                          el=ey[0].copy(), er=ey[1].copy()))

_bo.__exit__()
# сглаженная траектория для камеры: оператор ведёт не голову (она качается на каждом шаге), а «центр» движения.
# Гаусс без задержки — камера как будто знает, куда герой пойдёт (опытный оператор Steadicam/долли так и работает)
def _gauss(vals, sig):
    r = max(1, int(sig * 3)); w = [math.exp(-0.5 * (k / sig) ** 2) for k in range(-r, r + 1)]; n = len(vals); out = []
    for i in range(n):
        acc = Vector((0, 0, 0)); ws = 0.0
        for k in range(-r, r + 1):
            acc += vals[min(n - 1, max(0, i + k))] * w[k + r]; ws += w[k + r]
        out.append(acc / ws)
    return out
for p_, r_, h_ in zip(track_pts, _gauss([p['root'] for p in track_pts], 0.3 * FPS), _gauss([p['head'] for p in track_pts], 0.2 * FPS)):
    p_['rootS'] = r_; p_['headS'] = h_
# глаза для фокуса: лёгкое сглаживание (0.08 с) — фокус-пуллер ведёт глаз, но не дрожит на каждом шаге
for p_, l_, r_ in zip(track_pts, _gauss([p['el'] for p in track_pts], 0.08 * FPS), _gauss([p['er'] for p in track_pts], 0.08 * FPS)):
    p_['elS'] = l_; p_['erS'] = r_

# шаги: стопа «прилипла» к полу — скорость упала после движения (ноги не скользят, так что это точный момент удара)
steps = []
for key in ('fl', 'fr'):
    moving = False
    for f in range(1, len(track_pts)):
        v = (track_pts[f][key] - track_pts[f - 1][key]).length * FPS
        if v > 0.9: moving = True
        vn = (track_pts[min(f + 1, len(track_pts) - 1)][key] - track_pts[f][key]).length * FPS
        if moving and (v < 0.35 or (v < 0.9 and vn >= v)) and track_pts[f][key].z < 0.25:
            tt = f / FPS; bt = next((b for b in scn.beats if b.start <= tt < b.start + b.dur), scn.beats[-1])
            steps.append(dict(t=tt, side=key, kind='run' if bt.action == 'run' else 'walk')); moving = False
steps.sort(key=lambda x: x['t'])

# ---------- камеры ----------
SENSOR_W = 24.89                      # Super 35, как ARRI Alexa: глубина резкости «киношная», не фотографическая
SENSOR_H = SENSOR_W * a.h / a.w
# моушн-блюр: затвор 180° (выдержка 1/48 при 24 к/с) — стандарт кино
sc.render.use_motion_blur = not a.passes;   # со слоями AOV блюр делает пост по векторам движения
sc.render.motion_blur_shutter = 0.5
if hasattr(sc.eevee, 'motion_blur_steps'): sc.eevee.motion_blur_steps = 1
dg = None
def ray_block(origin, target):
    global dg
    dg = dg or bpy.context.evaluated_depsgraph_get()
    d = target - origin; L = d.length
    if L < 0.5: return target
    o2 = origin + d.normalized() * 0.45
    hit, loc, *_ = sc.ray_cast(dg, o2, d.normalized(), distance=L - 0.45)
    return loc - d.normalized() * 0.3 if hit else target

_DIRS = [Vector(v).normalized() for v in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(1,1,0),(1,-1,0),(-1,1,0),(-1,-1,0),(1,0,1),(-1,0,1),(0,1,1),(0,-1,1))]
def path_ok(pos, P, clearance=0.5):
    """Камера не внутри и не вплотную к геометрии (цепи, занавесы, колонны) и видит героя целиком."""
    global dg
    dg = dg or bpy.context.evaluated_depsgraph_get()
    for d in _DIRS:
        if sc.ray_cast(dg, pos, d, distance=clearance)[0]: return False
    for dz, side in ((0.15, 0), (-0.35, 0), (-0.8, 0), (-0.2, 0.22), (-0.2, -0.22)):
        tgt = P + Vector((0, 0, dz)); v = tgt - pos; L = v.length
        if L < 0.9: continue
        perp = Vector((-v.y, v.x, 0)).normalized() * side; tgt = tgt + perp; v = tgt - pos; L = v.length
        if sc.ray_cast(dg, pos, v.normalized(), distance=L - 0.6)[0]: return False
    return True

def occlusion(pos, P, lens, scr=(0.0, 0.0)):
    """Доля кадра, закрытая передним планом: сетка 7×5 лучей, попадание ближе 0.6 расстояния до героя."""
    global dg
    dg = dg or bpy.context.evaluated_depsgraph_get()
    fw = (P - pos).normalized(); rt = fw.cross(Vector((0, 0, 1))).normalized(); up = rt.cross(fw)
    tw = SENSOR_W / 2 / lens; th = tw * a.h / a.w; L = (P - pos).length; near = 0; n = 0
    for i in (-0.92, -0.6, -0.3, 0, 0.3, 0.6, 0.92):
        for j in (-0.85, -0.42, 0, 0.42, 0.85):
            d = (fw + rt * ((i - 2 * scr[0]) * tw) + up * ((j - 2 * scr[1]) * th)).normalized(); n += 1   # учёт композиции: герой не в центре
            if sc.ray_cast(dg, pos, d, distance=0.6 * L)[0]: near += 1
    return near / n

def framing(pos, P, lens, scr=(0.0, 0.0)):
    """Передний план кадра: (закрыт ли герой, доля левого края, доля правого края) — лучи 9×5, «край» = препятствие
    ближе 0.45 расстояния до героя вне его зоны (в расфокусе), «герой» = что угодно ближе 0.9 в его зоне."""
    global dg
    dg = dg or bpy.context.evaluated_depsgraph_get()
    fw = (P - pos).normalized(); rt = fw.cross(Vector((0, 0, 1))).normalized(); up = rt.cross(fw)
    tw = SENSOR_W / 2 / lens; th = tw * a.h / a.w; L = (P - pos).length
    hx, hy = 2 * scr[0], 2 * scr[1]; hero = hn = 0; lft = rgt = nl = nr = 0
    for i in (-0.95, -0.72, -0.48, -0.24, 0, 0.24, 0.48, 0.72, 0.95):
        for j in (-0.9, -0.45, 0, 0.45, 0.9):
            d = (fw + rt * ((i - hx) * tw) + up * ((j - hy) * th)).normalized()
            r = sc.ray_cast(dg, pos, d, distance=0.9 * L)
            if abs(i) < 0.3 and abs(j) < 0.7:
                hn += 1; hero += 1 if r[0] else 0
            else:
                near = r[0] and (r[1] - pos).length < 0.45 * L
                if i + hx < 0: nl += 1; lft += 1 if near else 0
                else: nr += 1; rgt += 1 if near else 0
    return hero / max(1, hn), lft / max(1, nl), rgt / max(1, nr)

ALLOW_OCC = {'EWS': 0.3, 'WS': 0.22, 'FS': 0.15}     # на общих арки по краям — рамка кадра; на крупных — брак

BOUNDS = dict(sponza=((-10.8, 9.8), (-4.4, 4.8), (0.15, 9.0))).get(scn.world)
def clamp(v):
    if not BOUNDS: return v
    return Vector(tuple(min(hi, max(lo, c)) for c, (lo, hi) in zip(v, BOUNDS)))

def subject(f, target):
    p = track_pts[min(max(f, 1), TOTAL) - 1]
    base, head = p['rootS'], p['headS']      # без «качки» шага: в кадре не дёргается ни прицел, ни фокус
    if target == 'head': return head + Vector((0, 0, 0.04))
    if target == 'chest': return base.lerp(head, 0.75)
    if target == 'feet': return (p['fl'] + p['fr']) / 2 + Vector((0, 0, 0.1))
    if target == 'sky': return head + Vector((0, 0, 8))
    return base.lerp(head, 0.5)

import gaffer
from crew import profile as _crew_profile
LIGHT = _crew_profile(scn.director, getattr(scn, 'dp', None))['light']
SUN_DIR = sun.matrix_world.to_quaternion() @ Vector((0, 0, 1))
# свет плана ложится только на актёра: тело, одежда, волосы (всё, что ведёт скелет героя)
RECEIVERS = [o for o in sc.objects if o.type == 'MESH' and (o.parent == hero.arm or any(m.type == 'ARMATURE' and m.object == hero.arm for m in o.modifiers))]
if fogobj: fogobj.hide_viewport = True   # туман не должен мешать проверке «камера в стене»
cams = []
for si, sh in enumerate(shots):
    cd = bpy.data.cameras.new(f'shot{si:02d}'); cd.lens = sh.lens; cd.sensor_width = SENSOR_W; cd.sensor_fit = 'HORIZONTAL'
    cd.clip_start = 0.05; cd.clip_end = 400
    cd.dof.use_dof = True; cd.dof.aperture_fstop = sh.fstop; cd.dof.aperture_blades = 9; cd.dof.aperture_rotation = 0.3
    cam = bpy.data.objects.new(f'shot{si:02d}', cd); sc.collection.objects.link(cam)
    foc = bpy.data.objects.new(f'focus{si:02d}', None); sc.collection.objects.link(foc); cd.dof.focus_object = foc
    f0, f1 = int(sh.start * FPS) + 1, max(int(sh.start * FPS) + 2, int(sh.end * FPS) + 1)
    dist = director.FRAME_H[sh.size] * sh.lens / SENSOR_H
    p0 = track_pts[f0 - 1]; yaw0 = p0['yaw']
    fwd0 = Vector((math.cos(yaw0 + math.pi / 2), math.sin(yaw0 + math.pi / 2), 0))
    # свет плана (гаффер): ключ с дальней стороны лица, заливка по контрасту оператора, перекрёстный контровой
    _bt = next((b for b in scn.beats if b.start <= sh.start + 0.05 < b.start + b.dur), scn.beats[-1])
    sh.palette = palette.for_shot(scn, _bt.emotion)
    from crew import emotions as _emo; sh.detail = _emo.slowmo_detail(getattr(sh, 'speed', 1.0), _bt.action)
    # лицо под капюшоном читается только с уровня глаз или чуть снизу: сверху камера видит ткань, а не лицо
    if HOODED and sh.size in ('ECU', 'CU', 'MCU') and sh.elev > -4: sh.elev = -4.0
    gl = gaffer.ShotLights(sc, f'{si:02d}', LIGHT, RECEIVERS, sh.palette, hooded=HOODED)
    gl.window('' if (sh.poi or sh.pov) else sh.size, f0, f1)
    smooth_pos = None; smooth_aim = None; gaze = None; ox = oy = 0.0; sh.screen = None
    moving = sh.move in ('track', 'follow', 'lead')
    # ручная камера — только как приём (крупно, на напряжении, камера стоит). Сопровождение — долли/Steadicam,
    # общие — штатив/кран: тряска там читается как ошибка оператора, а не как эмоция
    # в слоумо облёт идёт по сцене медленнее — угол делим на скорость, чтобы на экране камера шла с прежней скоростью
    VIB = 1.0 if (sh.move in ('track', 'lead', 'follow', 'passby') and any(b.action == 'run' and b.start <= sh.start < b.start + b.dur for b in scn.beats)) else 0.0
    ORBIT = min(270.0, 40.0 * (f1 - f0) / FPS / getattr(sh, 'speed', 1.0)) * (1 if sh.azim >= 0 else -1)
    HAND = 1.0 if (not moving and not sh.poi and sh.size in ('MS', 'MCU', 'CU', 'ECU')) else 0.0
    def raw_pos(f, off=0.0, kd=1.0, de=0.0):
        """Где стоит камера в кадре f без сглаживания: азимут+off, дистанция×kd, высота+de."""
        u = (f - f0) / max(1, f1 - f0); P = subject(f, sh.target); p = track_pts[min(max(f, 1), TOTAL) - 1]
        fw = Vector((math.cos(p['yaw'] + math.pi / 2), math.sin(p['yaw'] + math.pi / 2), 0))
        ref = fw if moving else fwd0
        # облёт: азимут плавно (ease in-out) уходит на ORBIT° за план — 120° на 3 с, полный круг даёт склейка из нескольких
        orb = ORBIT * (3 * u * u - 2 * u * u * u) if sh.move == 'orbit' else 0.0
        az = math.radians(sh.azim + off + orb); el = math.radians(sh.elev + de)
        dv = Vector((ref.x * math.cos(az) - ref.y * math.sin(az), ref.x * math.sin(az) + ref.y * math.cos(az), 0))
        # сопровождение (track/follow/lead) с микро-наездом ~5% за план: глаз чувствует «подход» к герою, зритель — нет
        k = {'slow_push': 1.12 - 0.2 * u, 'push': 1.25 - 0.4 * u, 'dolly': 1.15 - 0.25 * u, 'slow_pull': 0.85 + 0.3 * u,
             'track': 1.0 - 0.05 * u, 'follow': 1.0 - 0.05 * u, 'lead': 1.0 - 0.05 * u}.get(sh.move, 1.0)
        anchor = P if moving else subject(f0, sh.target)
        q = anchor + (dv * math.cos(el) + Vector((0, 0, math.sin(el)))) * dist * k * kd
        if sh.move in ('passby', 'pan'):
            # камера стоит на пути героя: точка пролёта — 65% плана; passby — 1 м вбок, 45 см над землёй;
            # pan — далеко сбоку (длинный объектив), фон смазывается панорамой
            # пролёт в конце плана: герой выходит за край кадра — и склейка через 2–3 кадра, уезжающего не держим
            fp = int(f0 + (0.85 if sh.move == 'passby' else 0.65) * (f1 - f0)); pp = track_pts[min(max(fp, 1), TOTAL) - 1]
            fwp = Vector((math.cos(pp['yaw'] + math.pi / 2), math.sin(pp['yaw'] + math.pi / 2), 0))
            sidev = Vector((fwp.y, -fwp.x, 0)) * (1 if math.sin(az) >= 0 else -1)
            ground = min(pp['fl'].z, pp['fr'].z)
            if sh.move == 'passby':
                q = pp['rootS'] + sidev * 1.0 * kd + fwp * 0.3; q.z = ground + 0.45 + 0.1 * de
            else:
                q = pp['rootS'] + sidev * dist * 1.2 * kd; q.z = pp['headS'].z - 0.2 + 0.05 * de
            anchor = pp['rootS']
        q.z = max(0.15, q.z)
        return clamp(ray_block(anchor, clamp(q))), P     # реальная точка: в стенах здания, перед препятствием
    # «оператор ищет точку»: проверяем ВЕСЬ путь камеры — не внутри стены/цепи/колонны и ничего не перекрывает героя
    plan_ok = None
    if not sh.pov and not sh.poi:
        best = (-1, 0, 1.0, 0.0)
        _r = composition.RULES.get(sh.comp or '', {})
        FG = 'frame' if _r.get('frame') else 'fg' if _r.get('foreground') else None
        tries = [(o, kd, de) for kd in (1.0, 0.85, 0.7, 0.55) for de in (0, 8, -6, 18) for o in (0, 15, -15, 30, -30, 45, -45, 60, -60, 90, -90)]
        for o, kd, de in tries:
            fs = list(range(f0, f1 + 1, 3)) + [f1]
            allow = ALLOW_OCC.get(sh.size, 0.1); good = 0; pen = 0.0; bon = 0.0
            for fm in fs:
                q, Pq = raw_pos(fm, o, kd, de)
                if not path_ok(q, Pq, 0.3 if sh.move == 'passby' else 0.5): continue
                scr = (0.0, 0.0)
                if sh.comp:      # куда композиция поставит героя из этой точки (как в покадровом цикле ниже)
                    pp_ = track_pts[min(fm, TOTAL) - 1]; fw_ = Vector((math.cos(pp_['yaw'] + math.pi / 2), math.sin(pp_['yaw'] + math.pi / 2), 0))
                    dv_ = Pq - q; yd = math.atan2(dv_.y, dv_.x); g_ = 1 if (fw_.x * math.sin(yd) - fw_.y * math.cos(yd)) >= -0.15 else -1
                    sx_, sy_ = composition.screen_point(sh.comp, g_, a.w / a.h); scr = (sx_, sy_ / (composition.VISIBLE * a.w / a.h))
                if FG:   # передний план — приём: края закрыты вплотную к объективу, герой чист
                    hc, el_, er_ = framing(q, Pq, sh.lens, scr); good += 1; pen += hc * 6
                    edge = min(el_, er_) * 2 if FG == 'frame' else max(el_, er_)
                    bon += min(edge, 0.35) - max(0.0, max(el_, er_) - 0.55)
                else:
                    oc = occlusion(q, Pq, sh.lens, scr); good += 1; pen += max(0.0, oc - allow) * 3
            ok = good - pen + 1.5 * bon
            sc_ = ok / len(fs) - 0.002 * abs(o) - 0.05 * (1 - kd) - 0.004 * abs(de)
            if os.environ.get('CAMDBG') == str(si): print('try', o, kd, de, 'good', good, '/', len(fs), 'pen', round(pen, 2), 'score', round(sc_, 3))
            if sc_ > best[0]: best = (sc_, o, kd, de)
            if good == len(fs) and pen == 0 and (not FG or bon / len(fs) > 0.15): break
        _, az_fix, kd_fix, de_fix = best
    else:
        az_fix, kd_fix, de_fix = 0, 1.0, 0.0
    # разгон фильтров до склейки: камера входит в план уже в движении, без рывка «с места» в первых кадрах
    PRE = 0 if (sh.poi or sh.pov) else int(0.6 * FPS)
    for f in range(max(1, f0 - PRE), f1 + 1):
        u = max(0.0, (f - f0) / max(1, f1 - f0)); KEY = f >= f0
        P = subject(f, sh.target)
        p = track_pts[min(f, TOTAL) - 1]
        fwd = Vector((math.cos(p['yaw'] + math.pi / 2), math.sin(p['yaw'] + math.pi / 2), 0))
        if sh.poi:
            T, Fm = Vector(sh.poi[0]), Vector(sh.poi[1])
            # пролёт не тормозит к концу: склейка приходится на движение, следующий план его подхватывает
            sp = 0.5 * u + 0.5 * u * u
            pos = Fm + (Fm - T) * (0.12 - 0.27 * sp)
            aimv = T.copy(); P = T
        elif sh.pov:
            pos = p['head'] + fwd * 0.15
            aimv = pos + (fwd * math.cos(math.radians(35 + 30 * u)) + Vector((0, 0, math.sin(math.radians(35 + 30 * u))))) * 10
        else:
            pos, _ = raw_pos(f, az_fix, kd_fix, de_fix)
            aimv = P.copy()
            if sh.move == 'passby':
                # камера не панорамирует: смотрит в точку пролёта (чуть навстречу герою), он влетает и выходит из кадра
                fpp = int(f0 + 0.85 * (f1 - f0)); ppp = track_pts[min(max(fpp, 1), TOTAL) - 1]
                aimv = subject(fpp, sh.target) + Vector((math.cos(ppp['yaw'] + math.pi / 2), math.sin(ppp['yaw'] + math.pi / 2), 0)) * -0.6
        # вибрация подвеса на скорости: мелкая (≈2–4 мм) и частая, как у камеры на машине/кране — не «качка» ручной камеры
        if VIB:
            rv = random.Random(si * 100003 + f)
            hv = Vector((rv.uniform(-1, 1), rv.uniform(-1, 1), rv.uniform(-1, 1))) * 0.003 * VIB
        else: hv = Vector((0, 0, 0))
        hh = hv + HAND * Vector((math.sin(f * 0.11) + 0.4 * math.sin(f * 0.23 + 1), math.sin(f * 0.09 + 2) + 0.4 * math.sin(f * 0.19), 0.6 * math.sin(f * 0.13 + 4))) * 0.012 * sh.hand
        # движущаяся камера жёстко привязана к герою (сглаживается только смещение), статичная — плавно панорамирует
        off = pos - (P if moving else Vector((0, 0, 0)))
        smooth_pos = off if smooth_pos is None else smooth_pos.lerp(off, 0.12 if moving else 0.25)
        smooth_aim = aimv if smooth_aim is None else smooth_aim.lerp(aimv, 0.6 if moving else 0.8 if sh.move in ('passby', 'pan') else 0.35)
        pos_now = smooth_pos + (P if moving else Vector((0, 0, 0)))
        cam.location = pos_now + hh
        if not sh.poi and not sh.pov and not path_ok(cam.location, P, 0.3 if sh.move == 'passby' else 0.5):
            cam.location = clamp(ray_block(P, cam.location)); smooth_pos = cam.location - (P if moving else Vector((0, 0, 0)))
        dvec = smooth_aim - cam.location
        yaw_d = math.atan2(dvec.y, dvec.x); pit_d = math.atan2(dvec.z, math.hypot(dvec.x, dvec.y))
        if sh.comp and gaze is None:
            # куда герой смотрит по экрану: проекция его «вперёд» на правую ось камеры (воздух оставляем перед взглядом)
            dotr = fwd.x * math.sin(yaw_d) - fwd.y * math.cos(yaw_d)
            gaze = 1 if dotr >= -0.15 else -1
            sx, sy = composition.screen_point(sh.comp, gaze, a.w / a.h)
            ox, oy = composition.aim_offsets(sx, sy, sh.lens, SENSOR_W, a.w / a.h)
            sh.screen = (round(sx, 3), round(sy / (composition.VISIBLE * a.w / a.h), 3))
        if sh.comp:
            yaw_c, pit_c = yaw_d + ox, pit_d - oy
            # запас над головой: макушка не выходит за верх кадра (ECU режет сознательно)
            if sh.size in ('CU', 'MCU', 'MS', 'FS', 'WS'):
                crown = subject(f, 'head') + Vector((0, 0, 0.24)); dc = crown - cam.location
                ang = math.atan2(dc.z, math.hypot(dc.x, dc.y)) - pit_c
                half_v = math.atan(SENSOR_H / 2 / sh.lens); lim = half_v * 0.86
                if ang > lim: pit_c += ang - lim
            q = Vector((math.cos(pit_c) * math.cos(yaw_c), math.cos(pit_c) * math.sin(yaw_c), math.sin(pit_c))).to_track_quat('-Z', 'Y')
        else:
            q = dvec.to_track_quat('-Z', 'Y')
        cam.rotation_euler = (q @ Quaternion((0, 0, 1), math.radians(sh.dutch))).to_euler()
        if KEY: cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
        # фокус: на глаза для портретных планов, на грудь для общих, на объект во вставке
        # портрет: резкость на ближний к камере глаз (не центр черепа: на 85 мм f/2.8 9 см до глаз = «мыло» лица)
        if sh.poi: fpt = P
        elif sh.size in ('ECU', 'CU', 'MCU', 'MS'):
            pe = track_pts[min(max(f, 1), TOTAL) - 1]
            fpt = min((pe['elS'], pe['erS']), key=lambda e: (e - cam.location).length)
        else: fpt = subject(f, 'chest')
        foc.location = aimv if sh.pov else fpt
        if KEY: foc.keyframe_insert('location', frame=f)
        if f == (f0 + f1) // 2: mid_cf = (cam.location.copy(), foc.location.copy())
        if not sh.poi and not sh.pov and KEY:
            gl.place(f, subject(f, 'head'), cam.location, fwd, SUN_DIR)
    # диафрагма по фону (как у оператора с рулеткой): фон размыт на заданную долю кадра, лицо целиком в резкости
    if not sh.pov and sh.size in gaffer.BOKEH:
        cpos, fpos = mid_cf; dvn = (fpos - cpos); sdist = dvn.length; dvn.normalize()
        dg = dg or bpy.context.evaluated_depsgraph_get()
        hit = sc.ray_cast(dg, fpos + dvn * 0.6, dvn, distance=200)
        bg = (sdist + 0.6 + (hit[1] - (fpos + dvn * 0.6)).length) if hit[0] else 60.0
        nf = gaffer.fstop_for(sh.size, sh.lens, SENSOR_W, sdist, bg, sh.fstop)
        if nf != sh.fstop: print(f'  диафрагма {sh.fstop:.1f} → {nf:.1f} (фокус {sdist:.2f} м, фон {bg:.1f} м)', flush=True)
        sh.fstop = nf; cd.dof.aperture_fstop = nf
    print('shot', si, sh.size, sh.comp, sh.screen, sh.note, 'az_fix', az_fix, 'cam', tuple(round(c, 1) for c in cam.location), 'hero', tuple(round(c, 1) for c in track_pts[f1 - 1]['root']), flush=True)
    m = sc.timeline_markers.new(f'shot{si:02d}', frame=f0); m.camera = cam
    cams.append((f0, f1, cam))

if fogobj: fogobj.hide_viewport = False

# ---------- слоумо: перерасчёт времени ----------
# План со speed<1 снят «высокоскоростной камерой»: выходной кадр берёт сцену в дробный момент (subframe),
# скорость входит и выходит плавной рампой (~0.25 с), затвор укорачивается вместе со скоростью — каждая пылинка резкая.
RAMP = 0.25 * FPS
def _speed_at(sf):
    for (f0, f1, _), sh in zip(cams, shots):
        sp = getattr(sh, 'speed', 1.0)
        if sp != 1.0 and f0 <= sf <= f1:
            if sp < 1.0:   # слоумо до момента: замедление на подходе (30% плана), момент на минимуме, разгон после (25%)
                k = min(1.0, (sf - f0) / max(1.0, 0.3 * (f1 - f0)), (f1 - sf) / max(1.0, 0.25 * (f1 - f0)))
            else:          # андеркранк ровный, короткие рампы у склеек
                k = min(1.0, (sf - f0) / RAMP * 2.5, (f1 - sf) / RAMP)
            k = k * k * (3 - 2 * k)
            return 1.0 + (sp - 1.0) * max(0.0, k)
    return 1.0
OUT = []; sf = 1.0
while sf <= TOTAL + 1e-6:
    OUT.append(sf); sf += _speed_at(sf)
TOTAL_OUT = len(OUT)
def src2out(t):
    """время сцены (с) → время фильма (с)"""
    fs = t * FPS + 1
    for o in range(1, TOTAL_OUT):
        if OUT[o] >= fs: return (o - 1 + (fs - OUT[o - 1]) / max(1e-6, OUT[o] - OUT[o - 1])) / FPS
    return (TOTAL_OUT - 1 + (fs - OUT[-1])) / FPS
if TOTAL_OUT != TOTAL: print('слоумо: кадров сцены', TOTAL, '→ кадров фильма', TOTAL_OUT, flush=True)
for b in scn.beats:
    b_end = src2out(b.start + b.dur); b.start = src2out(b.start); b.dur = b_end - b.start
for st in steps: st['t'] = src2out(st['t'])
for sh in shots: sh.start, sh.end = src2out(sh.start), src2out(sh.end)

# метаданные для звука и монтажа
os.makedirs(a.out, exist_ok=True)
json.dump(dict(feet=[[tuple(round(c, 3) for c in p['fl']), tuple(round(c, 3) for c in p['fr'])] for p in track_pts], fps=FPS, frames=TOTAL_OUT, duration=TOTAL_OUT / FPS, steps=steps,
               beats=[dict(action=b.action, emotion=b.emotion, start=b.start, dur=b.dur, text=b.text) for b in scn.beats],
               shots=[dict(start=s.start, end=s.end, size=s.size, lens=s.lens, move=s.move, note=s.note, comp=s.comp, screen=s.screen, fstop=round(s.fstop, 1), why=s.why, speed=getattr(s, 'speed', 1.0), palette=dict(name=s.palette['name'], colors=palette.hexes(s.palette)) if getattr(s, 'palette', None) else None, detail=getattr(s, 'detail', None)) for s in shots],
               dp=getattr(scn, 'dp', None) or director.PROFILES[scn.director]['dp'],
               director=scn.director, title=scn.title), open(os.path.join(a.out, 'meta.json'), 'w'), ensure_ascii=False, indent=1)

if a.save: bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save))
# ---------- рендер ----------
# номера кадров дальше — кадры ФИЛЬМА (после слоумо); OUT[o-1] — какой момент сцены в нём снят
if a.board:
    frames = [int((s.start + s.end) / 2 * FPS) + 1 for s in shots]
elif a.frames == 'none': frames = []
elif a.frames == 'all': frames = list(range(1, TOTAL_OUT + 1))
elif '-' in a.frames: s0, s1 = map(int, a.frames.split('-')); frames = list(range(s0, min(TOTAL_OUT, s1) + 1))
else: frames = [int(x) for x in a.frames.split(',')]
per = math.ceil(len(frames) / a.chunks); frames = frames[a.chunk * per:(a.chunk + 1) * per]
# бюджет сэмплов по крупности: лицо на крупном — никогда не «мыло» (больше лучей, строже адаптивный порог);
# общий план — фигура мелкая, шум прячет денойзер, время экономим (правило «где можно мягко»)
QS = {'ECU': (1.6, 0.006), 'CU': (1.5, 0.006), 'MCU': (1.3, 0.008), 'MS': (1.1, 0.01), 'FS': (1.0, 0.012), 'WS': (0.8, 0.015), 'EWS': (0.7, 0.02)}
base_s = sc.cycles.samples if a.engine == 'cycles' else 0
# LOD по крупности (как у ILM: 2 000 деталей на общем, 20 000 на крупном): дети прядей и подразделение тела.
# Корни прядей не меняются — меняется только густота интерполяции, поэтому между планами волосы не «прыгают»
HAIR_K = {'ECU': 1.0, 'CU': 1.0, 'MCU': 0.85, 'MS': 0.6, 'FS': 0.35, 'WS': 0.2, 'EWS': 0.1}
SUBD = {'ECU': 2, 'CU': 2, 'MCU': 2, 'MS': 2, 'FS': 1, 'WS': 1, 'EWS': 1}
psets = {ps.settings: (ps.settings.rendered_child_count, ps.settings.radius_scale) for o in sc.objects if o.type == 'MESH' for ps in o.particle_systems}
subs = [(m, m.render_levels) for o in sc.objects if o.type == 'MESH' and o.particle_systems for m in o.modifiers if m.type == 'SUBSURF']
for f in frames:
    sf = OUT[min(f, TOTAL_OUT) - 1]; fi = int(sf); fr = sf - fi
    ci = next((i for i, (f0, f1, c) in enumerate(cams) if f0 <= sf <= f1), len(cams) - 1); cam = cams[ci][2]
    sc.render.motion_blur_shutter = 0.5 * _speed_at(sf)      # 180° при любой скорости: в слоумо выдержка короче
    size_ = 'CU' if shots[ci].poi else shots[ci].size
    for st_, (n_, w_) in psets.items():   # меньше прядей — каждая толще: покрытие и цвет шевелюры не меняются
        k_ = HAIR_K.get(size_, 1.0); st_.rendered_child_count = max(2, int(round(n_ * k_))); st_.radius_scale = w_ * min(3.0, 1.0 / k_)
        if a.engine != 'cycles': groom.eevee_hair(st_)
    for m_, lv in subs: m_.render_levels = min(lv, SUBD.get(size_, lv))
    if base_s:
        ks, th = QS.get(shots[ci].size, (1.0, 0.01)) if not shots[ci].poi else (1.2, 0.008)
        sc.cycles.samples = max(16, int(base_s * ks)); sc.cycles.adaptive_threshold = th
    palette.apply(sc, shots[ci].palette)
    sc.camera = cam; sc.frame_set(fi, subframe=fr)
    sc.render.filepath = os.path.join(os.path.abspath(a.out), f'f_{f:05d}.png')
    bpy.ops.render.render(write_still=True); print('frame', f, cam.name, flush=True)
if LOOK.get('post') and frames:
    import subprocess
    post = os.path.join(LOOK['_dir'], LOOK['post'])
    print('post', post, flush=True)
    subprocess.run([sys.executable if post.endswith('.py') else post] + ([post] if post.endswith('.py') else []) + [os.path.abspath(a.out), os.path.join(os.path.abspath(a.out), 'meta.json')], check=False)
