# Съёмка: сценарий -> мир -> постановка героя -> раскадровка режиссёра -> камеры -> кадры.
# python studio/film.py -- --script films/hram.txt --out out/hram --w 1280 --h 720 [--frames all|1-100|10,20] [--board]
import sys, os, json, math, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector, Euler, Quaternion
import world, script, director

ap = argparse.ArgumentParser()
ap.add_argument('--script', required=True); ap.add_argument('--out', default='out/film')
ap.add_argument('--w', type=int, default=1280); ap.add_argument('--h', type=int, default=720); ap.add_argument('--fps', type=int, default=24)
ap.add_argument('--frames', default='all'); ap.add_argument('--chunk', type=int, default=0); ap.add_argument('--chunks', type=int, default=1)
ap.add_argument('--taa', type=int, default=6); ap.add_argument('--board', action='store_true', help='раскадровка: по кадру из середины каждого плана')
ap.add_argument('--director', default=None)
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
FPS = a.fps
scn = script.parse(open(a.script, encoding='utf-8').read())
if a.director: scn.director = a.director

# ---------- мир ----------
sc = world.new_scene(a.w, a.h, FPS, TAA=a.taa)
if scn.world == 'sponza': world.set_sponza()
world.hdri(scn.sky[0], scn.sky[1])
sun = world.sun(scn.sun[0], scn.sun[1], scn.sun[2] if len(scn.sun) > 2 else 6)
fogobj = world.fog(scn.fog, size=(40, 24, 16)) if scn.fog > 0 else None

# ---------- постановка героя ----------
hero = world.Actor(scn.hero)
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
B = int(0.45 * FPS)
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
    rd = bpy.data.lights.new(f'rim{si:02d}', 'AREA'); rd.size = 1.4; rd.color = (1.0, 0.86, 0.7)
    rim = bpy.data.objects.new(f'rim{si:02d}', rd); sc.collection.objects.link(rim)
    rt = rim.constraints.new('TRACK_TO'); rt.target = foc; rt.track_axis = 'TRACK_NEGATIVE_Z'; rt.up_axis = 'UP_Y'
    for ff, e in ((f0 - 1, 0), (f0, 0 if (sh.poi or sh.pov) else 160), (f1, 0 if (sh.poi or sh.pov) else 160), (f1 + 1, 0)):
        rd.energy = e; rd.keyframe_insert('energy', frame=max(1, ff))
    smooth_pos = None; smooth_aim = None
    # «оператор ищет точку»: если линия до героя перекрыта (колонна, занавес), сдвигаем ракурс по кругу
    def clear_ratio(off):
        tot = 0
        for fm in (f0, (f0 + f1) // 2, f1):
            Pm = subject(fm, sh.target); pm = track_pts[min(fm, TOTAL) - 1]
            fw = Vector((math.cos(pm['yaw'] + math.pi / 2), math.sin(pm['yaw'] + math.pi / 2), 0))
            az_ = math.radians(sh.azim + off); dv = Vector((fw.x * math.cos(az_) - fw.y * math.sin(az_), fw.x * math.sin(az_) + fw.y * math.cos(az_), 0))
            el_ = math.radians(sh.elev); want = clamp(Pm + (dv * math.cos(el_) + Vector((0, 0, math.sin(el_)))) * dist)
            got = clamp(ray_block(Pm, want)); tot += (got - Pm).length / max(0.01, dist)
        return tot / 3
    az_fix = 0
    if not sh.pov and not sh.poi:
        best = (clear_ratio(0), 0)
        if best[0] < 0.95:
            for off in (20, -20, 40, -40, 60, -60, 90, -90):
                if abs(((sh.azim + off) % 360) - 180) > 178 and sh.azim not in (160, 170, 175, 180, 200): pass
                r = clear_ratio(off)
                if r > best[0] + 0.05: best = (r, off)
                if r > 0.95: break
        az_fix = best[1]
    for f in range(f0, f1 + 1):
        u = (f - f0) / max(1, f1 - f0)
        P = subject(f, sh.target)
        p = track_pts[min(f, TOTAL) - 1]
        fwd = Vector((math.cos(p['yaw'] + math.pi / 2), math.sin(p['yaw'] + math.pi / 2), 0))
        moving = sh.move in ('track', 'follow', 'lead')
        ref = fwd if moving else fwd0
        az = math.radians(sh.azim + az_fix)
        dirv = Vector((ref.x * math.cos(az) - ref.y * math.sin(az), ref.x * math.sin(az) + ref.y * math.cos(az), 0))
        el = math.radians(sh.elev)
        k = {'slow_push': 1.12 - 0.2 * u, 'push': 1.25 - 0.4 * u, 'dolly': 1.15 - 0.25 * u, 'slow_pull': 0.85 + 0.3 * u}.get(sh.move, 1.0)
        anchor = P if moving else subject(f0, sh.target)
        if sh.poi:
            T, Fm = Vector(sh.poi[0]), Vector(sh.poi[1])
            pos = Fm + (Fm - T) * (0.12 - 0.27 * (u * u * (3 - 2 * u)))      # медленный наезд с мягким стартом и остановкой
            aimv = T.copy(); P = T
        elif sh.pov:
            pos = p['head'] + fwd * 0.15
            aimv = pos + (fwd * math.cos(math.radians(35 + 30 * u)) + Vector((0, 0, math.sin(math.radians(35 + 30 * u))))) * 10
        else:
            pos = anchor + (dirv * math.cos(el) + Vector((0, 0, math.sin(el)))) * dist * k
            pos.z = max(0.12, pos.z)
            pos = clamp(ray_block(anchor, clamp(pos)))
            side = Vector((-dirv.y, dirv.x, 0))
            aimv = P + side * sh.thirds * director.FRAME_H[sh.size] * a.w / a.h
        hh = Vector((math.sin(f * 0.37) + 0.5 * math.sin(f * 0.91 + 1), math.sin(f * 0.29 + 2) + 0.5 * math.sin(f * 0.83), math.sin(f * 0.33 + 4))) * 0.012 * sh.hand
        # движущаяся камера жёстко привязана к герою (сглаживается только смещение), статичная — плавно панорамирует
        off = pos - (P if moving else Vector((0, 0, 0)))
        smooth_pos = off if smooth_pos is None else smooth_pos.lerp(off, 0.12 if moving else 0.25)
        smooth_aim = aimv if smooth_aim is None else smooth_aim.lerp(aimv, 0.6 if moving else 0.35)
        pos_now = smooth_pos + (P if moving else Vector((0, 0, 0)))
        cam.location = pos_now + hh
        q = (smooth_aim - cam.location).to_track_quat('-Z', 'Y')
        cam.rotation_euler = (q @ Quaternion((0, 0, 1), math.radians(sh.dutch))).to_euler()
        cam.keyframe_insert('location', frame=f); cam.keyframe_insert('rotation_euler', frame=f)
        # фокус: на глаза для портретных планов, на грудь для общих, на объект во вставке
        fpt = P if sh.poi else (subject(f, 'head') if sh.size in ('ECU', 'CU', 'MCU', 'MS') else subject(f, 'chest'))
        foc.location = aimv if sh.pov else fpt; foc.keyframe_insert('location', frame=f)
        # контровой свет плана: как у оператора на площадке, за героем напротив камеры — отделяет от фона
        if not sh.poi and not sh.pov:
            back = (subject(f, 'head') - cam.location); back.z = 0; back = back.normalized() if back.length > 0.01 else Vector((1, 0, 0))
            rim.location = subject(f, 'head') + back * 2.2 + Vector((0, 0, 0.9)); rim.keyframe_insert('location', frame=f)
    print('shot', si, sh.size, sh.note, 'az_fix', az_fix, 'cam', tuple(round(c, 1) for c in cam.location), 'hero', tuple(round(c, 1) for c in track_pts[f1 - 1]['root']), flush=True)
    m = sc.timeline_markers.new(f'shot{si:02d}', frame=f0); m.camera = cam
    cams.append((f0, f1, cam))

if fogobj: fogobj.hide_viewport = False
# метаданные для звука и монтажа
os.makedirs(a.out, exist_ok=True)
json.dump(dict(feet=[[tuple(round(c, 3) for c in p['fl']), tuple(round(c, 3) for c in p['fr'])] for p in track_pts], fps=FPS, frames=TOTAL, duration=TOTAL / FPS, steps=steps,
               beats=[dict(action=b.action, emotion=b.emotion, start=b.start, dur=b.dur, text=b.text) for b in scn.beats],
               shots=[dict(start=s.start, end=s.end, size=s.size, lens=s.lens, move=s.move, note=s.note) for s in shots],
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
