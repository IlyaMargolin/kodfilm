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
macro = {k: hs[k] for k in ('gender', 'age', 'muscle', 'weight', 'height', 'proportions') if k in hs}
body = human.build(hero.arm, subdiv=2, skin=human.skin_material(tuple(hs.get('skin', (0.62, 0.43, 0.33))), tuple(hs.get('hair', (0.03, 0.022, 0.016))), 0.6), **macro)
if hs.get('wardrobe') == 'robe': wardrobe.robe(body, hero.arm, color=tuple(hs.get('cloth', (0.09, 0.075, 0.06))), hood=hs.get('hood', True))
groom.groom(body, color=tuple(hs.get('hair', (0.03, 0.022, 0.016))), grey=hs.get('grey', 0.25), hooded=hs.get('wardrobe') == 'robe' and hs.get('hood', True))
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
head = hero.arm.matrix_world @ hero.arm.pose.bones[hero.head].head + Vector((0, 0, 0.06))
os.makedirs(out, exist_ok=True)
if os.environ.get('PSTAT'):
    dg = bpy.context.evaluated_depsgraph_get(); oe = body.evaluated_get(dg)
    for pe in oe.particle_systems:
        st = pe.settings; n = len(pe.particles); ls = []
        for i in (0, 1, n + 5):
            a = pe.co_hair(oe, particle_no=i, step=0); b = pe.co_hair(oe, particle_no=i, step=2 ** st.render_step); ls.append((tuple(round(c, 3) for c in a), tuple(round(c, 3) for c in b), tuple(round(c, 3) for c in pe.co_hair(oe, particle_no=i, step=1))))
        print('PSTAT', pe.name, n, st.hair_length, ls)
    sys.exit(0)
for i, (az, el, d, lens) in enumerate(((20, 0, 0.9, 85), (70, 5, 0.9, 85), (0, -5, 3.2, 50))):
    cd = bpy.data.cameras.new('c'); cd.lens = lens; cd.sensor_width = 24.89
    cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam)
    a = math.radians(az + 90); e = math.radians(el)
    tgt = head if d < 2 else head - Vector((0, 0, 0.7))
    cam.location = tgt + Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e))) * d
    cam.rotation_euler = (tgt - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cd.dof.use_dof = True; cd.dof.focus_distance = d; cd.dof.aperture_fstop = 2.8
    sc.camera = cam; sc.render.filepath = os.path.abspath(f'{out}/p{i}.png'); bpy.ops.render.render(write_still=True)
