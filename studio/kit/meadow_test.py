"""Тест рассева: луг с травой и цветами в контровом свете на тёмном фоне (по мотивам референса с существом).
python studio/kit/meadow_test.py --out out/meadow --w 1280 --samples 64"""
import sys, os, math, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy
import world, lens
from kit import scatter, nature

ap = argparse.ArgumentParser(); ap.add_argument('--out', default='out/meadow'); ap.add_argument('--w', type=int, default=1280)
ap.add_argument('--samples', type=int, default=64); ap.add_argument('--density', type=float, default=350)
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
sc = world.new_scene(a.w, int(round(a.w / 2.39 / 2)) * 2, 24, engine='CYCLES', TAA=a.samples)
sc.view_settings.look = 'AgX - High Contrast'; lens.setup(sc, 'cinema')
w = bpy.data.worlds.new('w'); sc.world = w; w.use_nodes = True; w.node_tree.nodes['Background'].inputs[0].default_value = (0.002, 0.002, 0.003, 1)

bpy.ops.mesh.primitive_grid_add(x_subdivisions=120, y_subdivisions=120, size=8); g = bpy.context.object
t = bpy.data.textures.new('gr', 'CLOUDS'); t.noise_scale = 1.6
d = g.modifiers.new('d', 'DISPLACE'); d.texture = t; d.strength = 0.35; d.texture_coords = 'GLOBAL'
bpy.ops.object.modifier_apply(modifier='d')
g.data.materials.append(nature.rock_material((0.02, 0.018, 0.014)))
col = scatter.grass_collection(blades=14, tufts=8)
scatter.scatter(g, col, density=a.density, seed=4, scale=(0.6, 1.4))
# ключ: тёплый контровой прожектор + холодная мягкая заливка
for name, loc, energy, col_, size in (('back', (0.5, 5, 1.6), 2500, (1.0, 0.85, 0.65), 0.6), ('fill', (-4, -3, 3), 300, (0.6, 0.7, 1.0), 3)):
    ld = bpy.data.lights.new(name, 'AREA'); ld.energy = energy; ld.color = col_; ld.size = size
    o = bpy.data.objects.new(name, ld); sc.collection.objects.link(o); o.location = loc
    o.rotation_euler = (o.location * -1).to_track_quat('-Z', 'Y').to_euler()
cd = bpy.data.cameras.new('c'); cd.lens = 50; cd.dof.use_dof = True; cd.dof.aperture_fstop = 2.2; cd.dof.focus_distance = 3.6
cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
cam.location = (0, -3.4, 1.1); cam.rotation_euler = (math.radians(74), 0, 0)
os.makedirs(a.out, exist_ok=True); sc.render.filepath = os.path.abspath(f'{a.out}/f_00001.png')
bpy.ops.render.render(write_still=True); print('done', flush=True)
