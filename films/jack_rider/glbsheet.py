# Лист-превью модели GLB (из studio/gen3d.py): четыре ракурса на сером фоне, мягкий студийный свет.
#   python films/jack_rider/glbsheet.py -- model.glb out.jpg [samples] [cell_px]
import sys, os, math
import bpy
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:]; src, out = a[0], a[1]; S = int(a[2]) if len(a) > 2 else 48; W = int(a[3]) if len(a) > 3 else 640
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = S; sc.cycles.use_denoising = True
sc.render.resolution_x = sc.render.resolution_y = W; sc.render.film_transparent = True
bpy.ops.import_scene.gltf(filepath=src)
obs = [o for o in sc.objects if o.type == 'MESH']
for o in obs:
    for p in o.data.polygons: p.use_smooth = True
pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
lo = Vector([min(p[i] for p in pts) for i in range(3)]); hi = Vector([max(p[i] for p in pts) for i in range(3)])
C = (lo + hi) / 2; R = (hi - lo).length / 2
sc.world = bpy.data.worlds.new('w'); sc.world.use_nodes = True; sc.world.node_tree.nodes['Background'].inputs[0].default_value = (0.5, 0.5, 0.52, 1)
sc.world.node_tree.nodes['Background'].inputs[1].default_value = 0.6
def area(loc, e, size):
    L = bpy.data.lights.new('a', 'AREA'); L.energy = e * R * R; L.size = size * R; o = bpy.data.objects.new('a', L); sc.collection.objects.link(o)
    o.location = C + Vector(loc) * R; o.rotation_euler = (C - o.location).to_track_quat('-Z', 'Y').to_euler()
cd = bpy.data.cameras.new('c'); cd.lens = 85; cam = bpy.data.objects.new('c', cd); sc.collection.objects.link(cam); sc.camera = cam
from PIL import Image
tiles = []
for k, ang in enumerate((25, 90, 180, 300)):   # 3/4 спереди, сбоку, сзади, 3/4 с другой стороны (GLB: +Z вперёд => в Blender -Y)
    r = math.radians(ang); d = Vector((math.sin(r), -math.cos(r), 0.12)).normalized()
    cam.location = C + d * R * 2.9; cam.rotation_euler = (C - cam.location).to_track_quat('-Z', 'Y').to_euler()
    for o in [o for o in sc.objects if o.type == 'LIGHT']: bpy.data.objects.remove(o)
    side = d.cross(Vector((0, 0, 1))).normalized()
    area(d * 3 + side * 2.5 + Vector((0, 0, 2.5)), 420, 3); area(d * 2 - side * 3 + Vector((0, 0, 0.5)), 140, 4); area(-d * 3 + Vector((0, 0, 2)), 260, 2)
    p = out + f'.{k}.png'; sc.render.filepath = p; bpy.ops.render.render(write_still=True)
    im = Image.open(p).convert('RGBA'); bg = Image.new('RGBA', im.size, (118, 118, 118, 255)); tiles.append(Image.alpha_composite(bg, im).convert('RGB')); os.remove(p)
sheet = Image.new('RGB', (W * 4, W)); [sheet.paste(t, (i * W, 0)) for i, t in enumerate(tiles)]; sheet.save(out, quality=92)
print('faces', sum(len(o.data.polygons) for o in obs), 'size', [round(x, 3) for x in (hi - lo)])
