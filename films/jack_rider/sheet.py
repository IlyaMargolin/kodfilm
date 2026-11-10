# Листы моделей «Джека Райдера»: студийный серый фон, мягкий ключ, ракурсы как на листах из папки фильма.
# python films/jack_rider/sheet.py -- bike|jack|head out/sheets [samples] [w]
import sys, os, math
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'studio')); sys.path.insert(0, HERE)
import bpy
from mathutils import Vector
import world
args = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
what = args[0] if args else 'bike'; out = args[1] if len(args) > 1 else 'out/sheets'; S = int(args[2]) if len(args) > 2 else 24
W = int(args[3]) if len(args) > 3 else 900
os.makedirs(out, exist_ok=True)

def stage(w, h):
    sc = world.new_scene(w, h, 24, engine='CYCLES', TAA=S); sc.view_settings.exposure = 0.0
    sc.view_settings.look = 'AgX - Base Contrast'
    wd = bpy.data.worlds.new('w'); sc.world = wd; wd.use_nodes = True; wd.node_tree.nodes['Background'].inputs[0].default_value = (0.2, 0.2, 0.2, 1)
    wd.node_tree.nodes['Background'].inputs[1].default_value = 0.35
    # бесконечный серый фон-циклорама
    bpy.ops.mesh.primitive_plane_add(size=60); fl = bpy.context.object
    m = bpy.data.materials.new('cyc'); m.use_nodes = True; m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.22, 0.22, 0.22, 1)
    m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.9; fl.data.materials.append(m)
    fl.is_shadow_catcher = True; sc.render.film_transparent = True
    def area(name, loc, energy, size):
        ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.size = size
        o = bpy.data.objects.new(name, ld); sc.collection.objects.link(o); o.location = loc
        d = Vector((0, 0, 0.9)) - Vector(loc); o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler(); return o
    return sc, area

def cam(sc, loc, target, lens=50, ortho=None):
    cd = bpy.data.cameras.new('c'); cd.lens = lens
    if ortho: cd.type = 'ORTHO'; cd.ortho_scale = ortho
    c = bpy.data.objects.new('cam', cd); sc.collection.objects.link(c); c.location = loc
    c.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler(); sc.camera = c; return c

def shoot(sc, c, path):
    sc.camera = c; sc.render.filepath = path; bpy.ops.render.render(write_still=True)
    from PIL import Image   # прозрачный рендер с тенью на ровный серый лист
    im = Image.open(path).convert('RGBA'); bg = Image.new('RGBA', im.size, (118, 118, 118, 255)); Image.alpha_composite(bg, im).convert('RGB').save(path)
    print('кадр', path, flush=True)

if what == 'bike':
    sc, area = stage(W, int(W * 0.62))
    import kit.moto as moto
    bk = moto.build('bike'); moto.pose(bk, stand_deg=1.0)
    bk['root'].rotation_euler.x = math.radians(-6)   # на подножке — крен влево
    area('key', (2.5, -4, 4), 350, 4); area('fill', (-4, -3, 2.5), 120, 5); area('rim', (-1, 5, 3.5), 200, 3)
    C = Vector((0.6, 0, 0.62))
    views = dict(left=((0.6, 6.5, 0.7), 'ortho'), right=((0.6, -6.5, 0.7), 'ortho'), front=((6.5, 0, 0.75), 'ortho'),
                 rear=((-6.5, 0, 0.75), 'ortho'), top=((0.6, 0, 7), 'ortho'), threeq=((3.3, 2.6, 1.5), 'persp'))
    for k, (loc, kind) in views.items():
        if k == 'top':
            c = cam(sc, loc, C, ortho=2.6); c.rotation_euler = (0, 0, math.radians(-90))
        elif kind == 'ortho': c = cam(sc, loc, (loc[0] if k in ('left', 'right') else C.x, C.y if k in ('left','right') else 0, 0.62), ortho=2.7 if k in ('left', 'right') else 1.7)
        else: c = cam(sc, loc, C, lens=45)
        if k in ('front', 'rear'): c.data.ortho_scale = 2.0; c.location.z = 0.75; c.rotation_euler = (math.radians(90), 0, math.radians(90 if k == 'front' else -90))
        if k == 'top': c.data.ortho_scale = 2.9
        shoot(sc, c, os.path.join(out, f'bike_{k}.png'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(out, 'bike.blend')))

def build_jack(sc):
    import cast, human, groom, riderwear
    from kit import helmet
    hero = world.Actor(cast.resolve('jack')); hs = dict(cast.spec('jack')['human'])
    body = human.build_actor(hero.arm, hs)
    gear = riderwear.dress(body, hero.arm, **{k: tuple(hs[k]) for k in ('jacket', 'panel', 'pants', 'boots', 'gloves')})
    groom.groom(body, color=tuple(hs['hair']), grey=hs.get('grey', 0), scalp_len=hs.get('scalp_len', 0.03), beard_len=hs.get('beard', 0.0), density=1.0, edge=0.3, brow_density=0.45)
    ad = hero.arm.animation_data; ad.action = None; sc.frame_set(1)
    import os as _o
    for pb in hero.arm.pose.bones: pb.location = (0, 0, 0); pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = (1, 0, 0, 0); pb.scale = (1, 1, 1)
    for side, sg in (('Left', 1), ('Right', float(_o.environ.get('RSIGN', '1')))):   # «А-поза» листа: руки вниз под 45° от T-позы
        pb = hero.arm.pose.bones[f'mixamorig:{side}Arm']; pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, sg * math.radians(float(_o.environ.get('ARMDOWN', '62'))))
    bpy.context.view_layer.update()
    h = helmet.build(body, hero.arm, **{k: tuple(v) for k, v in hs['helmet'].items()})
    return hero, body, gear, h

def hair(body, on):
    for m in body.modifiers:
        if m.type == 'PARTICLE_SYSTEM' and m.name in ('scalp', 'hairline'): m.show_render = on

def helm(h, on):
    for o in [h['root']] + list(h['root'].children_recursive): o.hide_render = not on

if what in ('jack', 'head'):
    sc, area = stage(W, int(W * (1.25 if what == 'jack' else 1.0)))
    hero, body, gear, h = build_jack(sc)
    import human
    el, er = human.eyes_world(body, hero.arm); em = (Vector(el) + Vector(er)) / 2
    fw = em - hero.arm.matrix_world.translation; fw.z = 0; fw.normalize()
    rt = fw.cross(Vector((0, 0, 1))).normalized()     # правая рука героя
    print('лицо смотрит', tuple(round(x, 2) for x in fw), 'глаза на', round(em.z, 3), flush=True)
    K = lambda d: tuple(Vector((0, 0, 0)) + d)
    key = area('key', K(fw * 3 - rt * 2.5 + Vector((0, 0, 3.5))), 110, 3); area('fill', K(fw * 3 + rt * 3 + Vector((0, 0, 1.6))), 40, 4)
    area('rim', K(-fw * 3 + rt * 1 + Vector((0, 0, 3))), 90, 2.5)
    if what == 'jack':
        helm(h, True); hair(body, False); helmet.visor(h, 0) if False else None
        from kit import helmet as hm; hm.visor(h, 0)
        C = Vector((0, 0, 0.92))
        for k, d in dict(front=fw, left=-rt, back=-fw, right=rt).items():
            c = cam(sc, C + d * 8, C, ortho=2.15); shoot(sc, c, os.path.join(out, f'jack_{k}.png'))
    else:
        from kit import helmet as hm
        C = em + Vector((0, 0, -0.02))
        views = [('bare_front', fw, False, 0), ('bare_left', -rt, False, 0), ('bare_back', -fw, False, 0),
                 ('bare_threeq', (fw + rt * 0.75).normalized(), False, 0), ('visor_front', fw, True, 1), ('visor_left', -rt, True, 1),
                 ('closed_threeq', (fw - rt * 0.8).normalized(), True, 0)]
        for k, d, on, vk in views:
            helm(h, on); hair(body, not on); hm.visor(h, vk)
            c = cam(sc, C + d * 1.25 + Vector((0, 0, 0.02)), C + Vector((0, 0, -0.04)), lens=85); shoot(sc, c, os.path.join(out, f'head_{k}.png'))
    bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(os.path.join(out, f'{what}.blend')))
