# Портретный стенд: актёр без локации — проверка лица, волос, ткани. Cycles, 3 ракурса.
# python studio/portrait_test.py -- pilgrim out/portrait [samples] [hood0|hood1]
import sys, os, math, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector
import world, cast, human, wardrobe, groom
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
name = args[0] if args else 'pilgrim'; out = args[1] if len(args) > 1 else 'out/portrait'; S = int(args[2]) if len(args) > 2 else 32
hood_override = args[3] if len(args) > 3 else None
sc = world.new_scene(900, 900, 24, engine='CYCLES', TAA=S); sc.view_settings.exposure = 0.6
world.hdri('venice_sunset_1k.hdr', 0.6)
world.sun(25, 120, 4)
hero = world.Actor(cast.resolve(name)); hs = dict(cast.spec(name)['human'])
if hood_override: hs['hood'] = hood_override == 'hood1'
body = human.build_actor(hero.arm, hs)
if hs.get('wardrobe') == 'robe': wardrobe.robe(body, hero.arm, color=tuple(hs.get('cloth', (0.09, 0.075, 0.06))), hood=hs.get('hood', True))
groom.groom(body, color=tuple(hs.get('hair', (0.03, 0.022, 0.016))), grey=hs.get('grey', 0.25), beard_len=hs.get('beard', 0.03), hooded=hs.get('wardrobe') == 'robe' and hs.get('hood', True))
ad = hero.arm.animation_data; ad.action = hero.actions['idle']; sc.frame_set(10)
for _n in os.environ.get('HIDE', '').split(','):
    if _n in bpy.data.objects: bpy.data.objects[_n].hide_render = True
for _o in bpy.data.objects:
    for _m in _o.modifiers:
        if _m.type in os.environ.get('OFFMOD', '').split(','): _m.show_render = False
if os.environ.get('REST'): hero.arm.data.pose_position = 'REST'
if os.environ.get('SMOOTHIT'): bpy.data.objects['robe_top'].modifiers['drape'].iterations = int(os.environ['SMOOTHIT'])
print('OBJS', [(o.name, o.type) for o in bpy.data.objects])
print('BODYMODS', [(m.type, m.name, getattr(m, 'vertex_group', '')) for m in body.modifiers], len(body.vertex_groups['covered'].name) if 'covered' in body.vertex_groups else None)
EY = human.eyes_world(body, hero.arm); bpy.context.view_layer.update(); EY = human.eyes_world(body, hero.arm)
eyes_c = (EY[0] + EY[1]) / 2
head = eyes_c
# студийный свет как на референсах: большой мягкий ключ сбоку-сверху, заполняющий щит, контровой — объём без «пластика»
def area(name, loc, energy, size, color=(1, 0.96, 0.9)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.size = size; ld.color = color
    o = bpy.data.objects.new(name, ld); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (head - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); return o
if os.environ.get('STUDIO', '1') == '1':
    area('key', head + Vector((-1.2, 1.4, 0.9)), 160, 1.6); area('fill', head + Vector((1.5, 1.0, 0.1)), 30, 2.0, (0.9, 0.95, 1.0))
    area('rim', head + Vector((0.6, -1.3, 0.8)), 120, 0.8, (1.0, 0.9, 0.8))
os.makedirs(out, exist_ok=True)
if os.environ.get('DENOISE') == 'off': sc.cycles.use_denoising = False
elif os.environ.get('DENOISE') == 'albedo': sc.cycles.denoising_input_passes = 'RGB_ALBEDO'
W = int(os.environ.get('RES', '1200')); sc.render.resolution_x = sc.render.resolution_y = W
CAMS = [int(c) for c in os.environ.get('CAMS', '0,1,2').split(',')]
for i, (az, el, d, lens) in enumerate(((20, 0, 0.75, 85), (70, 5, 0.75, 85), (0, -5, 3.2, 50))):
    if i not in CAMS: continue
    cd = bpy.data.cameras.new('c'); cd.lens = lens; cd.sensor_width = 24.89
    cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam)
    a = math.radians(az + 90); e = math.radians(el)
    tgt = head if d < 2 else head - Vector((0, 0, 0.7))
    cam.location = tgt + Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * d
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    near = min(EY, key=lambda p: (p - cam.location).length)     # фокус на ближний глаз
    cd.dof.use_dof = True; cd.dof.focus_distance = (near - cam.location).length; cd.dof.aperture_fstop = 4.0 if d < 2 else 5.6
    sc.camera = cam; sc.render.filepath = os.path.abspath(f'{out}/p{i}.png'); bpy.ops.render.render(write_still=True)
