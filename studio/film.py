# Съёмка: сценарий -> мир -> постановка героя -> раскадровка режиссёра -> камеры -> кадры.
# python studio/film.py -- --script films/hram/script.txt --out out/hram --w 1280 --h 720 [--frames all|1-100|10,20] [--board]
import sys, os, json, math, argparse
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
ap.add_argument('--fogk', type=float, default=0.35, help='множитель плотности тумана в Cycles: настоящий объём гуще, чем в EEVEE')
ap.add_argument('--ev', type=float, default=None, help='экспозиция; в Cycles по умолчанию +0.9: нет фальшивого фонового света EEVEE, честный свет темнее')
ap.add_argument('--lens', default='cinema', help='clean|cinema|anamorphic|dream|none — блум, анаморфные блики, аберрация')
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
FPS = a.fps
if not a.h: a.h = int(round(a.w / 2.39 / 2)) * 2   # кадр сразу 2.39:1 — никаких чёрных полос, плеер сам впишет
scn = script.parse(open(a.script, encoding='utf-8').read())
if a.director: scn.director = a.director

# ---------- мир ----------
sc = world.new_scene(a.w, a.h, FPS, engine='CYCLES' if a.engine == 'cycles' else 'BLENDER_EEVEE', TAA=a.samples if a.engine == 'cycles' else a.taa)
sc.view_settings.exposure = a.ev if a.ev is not None else (0.9 if a.engine == 'cycles' else sc.view_settings.exposure)
if a.lens != 'none':
    import lens; lens.setup(sc, a.lens)
if scn.world == 'sponza': world.set_sponza()
world.hdri(scn.sky[0], scn.sky[1])
sun = world.sun(scn.sun[0], scn.sun[1], scn.sun[2] if len(scn.sun) > 2 else 6)
fogobj = world.fog(scn.fog * (a.fogk if a.engine == 'cycles' else 1.0), size=(40, 24, 16)) if scn.fog > 0 else None

# ---------- постановка героя ----------
import cast
hero = world.Actor(cast.resolve(scn.hero, os.path.dirname(os.path.abspath(a.script))))
ACT = {'walk': 'walk', 'run': 'run', 'stand': 'idle', 'look_up': 'idle', 'look_down': 'idle', 'look': 'idle', 'turn': 'idle'}
speed = {k: hero.cycle_speed(k) for k in ('walk', 'run') if k in hero.actions}
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

# ---------- раскадровка ----------
shots = director.plan(scn, scn.director)
print(director.describe(shots), flush=True)

# покадровые данные героя: голова, грудь, стопы (для камер и для звука шагов)
track_pts = []
footL = hero.foot; footR = hero.foot.replace('Left', 'Right')
for f in range(1, TOTAL + 1):
    sc.frame_set(f)
    M = hero.arm.matrix_world
    hd = M @ hero.arm.pose.bones[hero.head].head
    fl = M @ hero.arm.pose.bones[footL].head; fr = M @ hero.arm.pose.bones[footR].head
    track_pts.append(dict(head=hd.copy(), root=hero.root.location.copy(), yaw=hero.root.rotation_euler.z, fl=fl.copy(), fr=fr.copy()))

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
sc.render.use_motion_blur = True; sc.render.motion_blur_shutter = 0.5
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

def frame_clear(pos, P, lens):
    """Передний план не закрывает кадр: сетка 5×3 лучей по кадру, близкие препятствия (колонна в полкадра) — брак."""
    global dg
    dg = dg or bpy.context.evaluated_depsgraph_get()
    fw = (P - pos).normalized(); rt = fw.cross(Vector((0, 0, 1))).normalized(); up = rt.cross(fw)
    tw = SENSOR_W / 2 / lens; th = tw * a.h / a.w; near = 0; L = (P - pos).length
    for i in (-0.9, -0.45, 0, 0.45, 0.9):
        for j in (-0.8, 0, 0.8):
            d = (fw + rt * (i * tw) + up * (j * th)).normalized()
            if sc.ray_cast(dg, pos, d, distance=min(1.6, 0.35 * L))[0]: near += 1
    return near <= 2

BOUNDS = dict(sponza=((-10.8, 9.8), (-4.4, 4.8), (0.15, 9.0))).get(scn.world)
def clamp(v):
    if not BOUNDS: return v
    return Vector(tuple(min(hi, max(lo, c)) for c, (lo, hi) in zip(v, BOUNDS)))

def subject(f, target):
    p = track_pts[min(f, TOTAL) - 1]
    base = p['root']
    if target == 'head': return p['head'] + Vector((0, 0, 0.04))
    if target == 'chest': return base.lerp(p['head'], 0.75)
    if target == 'feet': return (p['fl'] + p['fr']) / 2 + Vector((0, 0, 0.1))
    if target == 'sky': return p['head'] + Vector((0, 0, 8))
    return base.lerp(p['head'], 0.5)

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
    rd = bpy.data.lights.new(f'rim{si:02d}', 'SPOT'); rd.spot_size = math.radians(28); rd.spot_blend = 0.6; rd.shadow_soft_size = 0.4; rd.color = (1.0, 0.86, 0.7)
    rim = bpy.data.objects.new(f'rim{si:02d}', rd); sc.collection.objects.link(rim)
    rt = rim.constraints.new('TRACK_TO'); rt.target = foc; rt.track_axis = 'TRACK_NEGATIVE_Z'; rt.up_axis = 'UP_Y'
    RIM = 0 if (sh.poi or sh.pov or sh.size not in ('MS', 'MCU', 'CU', 'ECU')) else 90   # контровой только там, где его мотивирует солнце за героем и не видно пятна
    for ff, e in ((f0 - 1, 0), (f0, RIM), (f1, RIM), (f1 + 1, 0)):
        rd.energy = e; rd.keyframe_insert('energy', frame=max(1, ff))
    smooth_pos = None; smooth_aim = None; gaze = None; ox = oy = 0.0; sh.screen = None
    moving = sh.move in ('track', 'follow', 'lead')
    def raw_pos(f, off=0.0, kd=1.0, de=0.0):
        """Где стоит камера в кадре f без сглаживания: азимут+off, дистанция×kd, высота+de."""
        u = (f - f0) / max(1, f1 - f0); P = subject(f, sh.target); p = track_pts[min(f, TOTAL) - 1]
        fw = Vector((math.cos(p['yaw'] + math.pi / 2), math.sin(p['yaw'] + math.pi / 2), 0))
        ref = fw if moving else fwd0
        az = math.radians(sh.azim + off); el = math.radians(sh.elev + de)
        dv = Vector((ref.x * math.cos(az) - ref.y * math.sin(az), ref.x * math.sin(az) + ref.y * math.cos(az), 0))
        k = {'slow_push': 1.12 - 0.2 * u, 'push': 1.25 - 0.4 * u, 'dolly': 1.15 - 0.25 * u, 'slow_pull': 0.85 + 0.3 * u}.get(sh.move, 1.0)
        anchor = P if moving else subject(f0, sh.target)
        q = anchor + (dv * math.cos(el) + Vector((0, 0, math.sin(el)))) * dist * k * kd
        q.z = max(0.15, q.z)
        return clamp(ray_block(anchor, clamp(q))), P     # реальная точка: в стенах здания, перед препятствием
    # «оператор ищет точку»: проверяем ВЕСЬ путь камеры — не внутри стены/цепи/колонны и ничего не перекрывает героя
    plan_ok = None
    if not sh.pov and not sh.poi:
        best = (-1, 0, 1.0, 0.0)
        tries = [(o, kd, de) for kd in (1.0, 0.85, 0.7) for de in (0, 8, -6) for o in (0, 15, -15, 30, -30, 45, -45, 60, -60, 90, -90)]
        for o, kd, de in tries:
            fs = list(range(f0, f1 + 1, 3)) + [f1]
            ok = sum(1 for fm in fs if path_ok(*raw_pos(fm, o, kd, de)) and frame_clear(*raw_pos(fm, o, kd, de), sh.lens))
            sc_ = ok / len(fs) - 0.002 * abs(o) - 0.05 * (1 - kd) - 0.004 * abs(de)
            if sc_ > best[0]: best = (sc_, o, kd, de)
            if ok == len(fs): break
        _, az_fix, kd_fix, de_fix = best
    else:
        az_fix, kd_fix, de_fix = 0, 1.0, 0.0
    for f in range(f0, f1 + 1):
        u = (f - f0) / max(1, f1 - f0)
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
        hh = Vector((math.sin(f * 0.11) + 0.4 * math.sin(f * 0.23 + 1), math.sin(f * 0.09 + 2) + 0.4 * math.sin(f * 0.19), 0.6 * math.sin(f * 0.13 + 4))) * 0.012 * sh.hand
        # движущаяся камера жёстко привязана к герою (сглаживается только смещение), статичная — плавно панорамирует
        off = pos - (P if moving else Vector((0, 0, 0)))
        smooth_pos = off if smooth_pos is None else smooth_pos.lerp(off, 0.12 if moving else 0.25)
        smooth_aim = aimv if smooth_aim is None else smooth_aim.lerp(aimv, 0.6 if moving else 0.35)
        pos_now = smooth_pos + (P if moving else Vector((0, 0, 0)))
        cam.location = pos_now + hh
        if not sh.poi and not sh.pov and not path_ok(cam.location, P):
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
        cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
        # фокус: на глаза для портретных планов, на грудь для общих, на объект во вставке
        fpt = P if sh.poi else (subject(f, 'head') if sh.size in ('ECU', 'CU', 'MCU', 'MS') else subject(f, 'chest'))
        foc.location = aimv if sh.pov else fpt; foc.keyframe_insert('location', frame=f)
        # контровой свет плана: как у оператора на площадке, за героем напротив камеры — отделяет от фона
        if not sh.poi and not sh.pov:
            back = (subject(f, 'head') - cam.location); back.z = 0; back = back.normalized() if back.length > 0.01 else Vector((1, 0, 0))
            rim.location = subject(f, 'head') + back * 2.2 + Vector((0, 0, 0.9)); rim.keyframe_insert('location', frame=f)
    print('shot', si, sh.size, sh.comp, sh.screen, sh.note, 'az_fix', az_fix, 'cam', tuple(round(c, 1) for c in cam.location), 'hero', tuple(round(c, 1) for c in track_pts[f1 - 1]['root']), flush=True)
    m = sc.timeline_markers.new(f'shot{si:02d}', frame=f0); m.camera = cam
    cams.append((f0, f1, cam))

if fogobj: fogobj.hide_viewport = False
# метаданные для звука и монтажа
os.makedirs(a.out, exist_ok=True)
json.dump(dict(feet=[[tuple(round(c, 3) for c in p['fl']), tuple(round(c, 3) for c in p['fr'])] for p in track_pts], fps=FPS, frames=TOTAL, duration=TOTAL / FPS, steps=steps,
               beats=[dict(action=b.action, emotion=b.emotion, start=b.start, dur=b.dur, text=b.text) for b in scn.beats],
               shots=[dict(start=s.start, end=s.end, size=s.size, lens=s.lens, move=s.move, note=s.note, comp=s.comp, screen=s.screen, fstop=round(s.fstop, 1)) for s in shots],
               dp=getattr(scn, 'dp', None) or director.PROFILES[scn.director]['dp'],
               director=scn.director, title=scn.title), open(os.path.join(a.out, 'meta.json'), 'w'), ensure_ascii=False, indent=1)

# ---------- рендер ----------
if a.board:
    frames = [int((s.start + s.end) / 2 * FPS) + 1 for s in shots]
elif a.frames == 'all': frames = list(range(1, TOTAL + 1))
elif '-' in a.frames: s0, s1 = map(int, a.frames.split('-')); frames = list(range(s0, min(TOTAL, s1) + 1))
else: frames = [int(x) for x in a.frames.split(',')]
per = math.ceil(len(frames) / a.chunks); frames = frames[a.chunk * per:(a.chunk + 1) * per]
for f in frames:
    cam = next((c for f0, f1, c in cams if f0 <= f <= f1), cams[-1][2])
    sc.camera = cam; sc.frame_set(f)
    sc.render.filepath = os.path.join(os.path.abspath(a.out), f'f_{f:05d}.png')
    bpy.ops.render.render(write_still=True); print('frame', f, cam.name, flush=True)
