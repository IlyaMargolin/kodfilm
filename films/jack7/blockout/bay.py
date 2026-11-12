# Невидимая 3D-болванка для плана «Джек едет вдоль залива к закату».
# Даёт верную геометрию (перспектива, масштаб, посадка на байке) -> карта глубины + серый кадр.
# Рисунок поверх делает SDXL+ControlNet на ферме; сама 3D в фильм не попадает.
# blender -b -P bay.py -- --studio /home/user/kodfilm/studio --out OUT
import sys, os, math, argparse
ap = argparse.ArgumentParser(); ap.add_argument('--studio'); ap.add_argument('--out'); ap.add_argument('--w', type=int, default=1344); ap.add_argument('--h', type=int, default=768)
ap.add_argument('--cam', default='rear34')
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:])
sys.path.insert(0, a.studio)
import bpy, numpy as np
from mathutils import Vector
sys.path.insert(0, os.path.dirname(__file__)); import rig
import world, human, cast
sc = world.new_scene(a.w, a.h, 24, engine='BLENDER_WORKBENCH')
for o in list(bpy.data.objects): bpy.data.objects.remove(o)

# земля, дорога вдоль берега, море, дальние холмы
def box(name, loc, size, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(location=loc, rotation=rot); o = bpy.context.active_object; o.name = name; o.scale = [s / 2 for s in size]; return o
bpy.ops.mesh.primitive_plane_add(size=600, location=(-210, 0, -1.2)); sea = bpy.context.active_object
# дорога: полоса, слегка приподнятая, уходит вперёд и плавно влево к воде
pts = [(0.0 + 0.0003 * y * y, y) for y in range(-20, 200, 2)]
verts, faces = [], []
for i, (x, y) in enumerate(pts):
    verts += [(x - 2.2, y, 0.02), (x + 2.2, y, 0.02)]
    if i: faces.append((2 * i - 2, 2 * i - 1, 2 * i + 1, 2 * i))
gv = []
for i, (x, y) in enumerate(pts): gv += [(x - 7.0, y, 0.0), (x + 160, y, 0.0)]
gm = bpy.data.meshes.new('ground'); gm.from_pydata(gv, [], faces); sc.collection.objects.link(bpy.data.objects.new('ground', gm))  # суша справа от кромки
me = bpy.data.meshes.new('road'); me.from_pydata(verts, [], faces); road = bpy.data.objects.new('road', me); sc.collection.objects.link(road)
# береговая кромка: невысокий откос между травой и водой слева от дороги
for y in range(-20, 220, 6):
    box('bank', (-9 + 0.0003 * y * y, y, -0.3), (2.5, 6.2, 0.9), (0, 0.5, 0))
# дальние холмы за заливом и мыс справа
import random; R = random.Random(5)
for x, y, s, hz in ((-170, 260, 70, 0.32), (-70, 330, 90, 0.3), (60, 300, 60, 0.4), (-260, 210, 50, 0.3), (120, 180, 45, 0.45)):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=s, location=(x, y, -s * 0.6)); h = bpy.context.active_object; h.scale.z = hz * 2.2
    m = h.modifiers.new('d', 'DISPLACE'); t = bpy.data.textures.new('n', 'CLOUDS'); t.noise_scale = 0.6; m.texture = t; m.strength = s * 0.12
# вода: лёгкая рябь, ниже берега на метр
bpy.data.objects.remove(sea)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=300, y_subdivisions=300, size=600, location=(-300, 150, -1.0)); sea = bpy.context.active_object
m = sea.modifiers.new('w', 'DISPLACE'); t = bpy.data.textures.new('w', 'CLOUDS'); t.noise_scale = 0.8; m.texture = t; m.strength = 0.25
# сухая трава у дороги: кочки разной высоты справа и полосой между дорогой и водой
for i in range(2200):
    y = R.uniform(-4, 70); side = R.random() < 0.85
    x0 = 0.0003 * y * y
    x = x0 + (R.uniform(2.5, 25) if side else -R.uniform(2.5, 4.5))
    r = R.uniform(0.07, 0.22)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=r, location=(x, y, r * 0.3)); c = bpy.context.active_object
    c.scale = (R.uniform(0.8, 1.6), R.uniform(0.8, 1.6), R.uniform(0.9, 1.8))
# камни по кромке берега
for y in range(0, 120, 7):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=R.uniform(0.4, 1.1), location=(0.0003 * y * y - 7.2 + R.uniform(-0.5, 0.5), y + R.uniform(-2, 2), -0.6)); bpy.context.active_object.scale.z = 0.6

bike = rig.motorcycle(loc=(0.6, 6.0, 0), yaw=0)
hero = rig.rider(bike, cast, human, world)

cams = {'rear34': ((2.6, 0.6, 1.5), (-2.2, 12, 0.9), 35), 'side': ((6.5, 6.2, 1.0), (0.6, 6.2, 0.9), 40)}
loc, tgt, lens_mm = cams[a.cam]
bpy.ops.object.camera_add(location=loc); cam = bpy.context.active_object; sc.camera = cam; cam.data.lens = lens_mm
d = Vector(tgt) - Vector(loc); cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
os.makedirs(a.out, exist_ok=True)
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'SINGLE'; sh.single_color = (0.8, 0.8, 0.8); sh.show_cavity = True
sc.render.filepath = os.path.join(a.out, f'bay_{a.cam}_clay.png'); bpy.ops.render.render(write_still=True)
rig.depth(sc, cam, os.path.join(a.out, f'bay_{a.cam}_depth.png'), far=400)
print('BLOCKOUT DONE')
