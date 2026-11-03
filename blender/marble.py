# Фотореал-тест: мокрый мраморный покров с мхом, по складке катится капля. Ночь, вспышка.
# Запуск: python blender/marble.py --out out/marble --w 1920 --h 1080 --frames 1,40,80 [--samples 96]
import bpy, bmesh, math, sys, argparse, os
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ap = argparse.ArgumentParser()
ap.add_argument('--out', default='out/marble'); ap.add_argument('--w', type=int, default=1920); ap.add_argument('--h', type=int, default=1080)
ap.add_argument('--frames', default='1'); ap.add_argument('--samples', type=int, default=96); ap.add_argument('--fps', type=int, default=24)
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = 'CYCLES'
sc.cycles.device = 'CPU'
sc.cycles.samples = a.samples
sc.cycles.use_denoising = True
sc.cycles.denoiser = 'OPENIMAGEDENOISE'
sc.cycles.max_bounces = 10; sc.cycles.transmission_bounces = 12; sc.cycles.caustics_reflective = False
sc.render.resolution_x, sc.render.resolution_y = a.w, a.h
sc.render.fps = a.fps
sc.view_settings.view_transform = 'AgX'
sc.view_settings.look = 'AgX - Medium High Contrast'
sc.render.image_settings.file_format = 'PNG'

# ---------- форма статуи: ткань, упавшая на скрытое тело (симуляция ткани) ----------
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.55, location=(0, 0, 1.25), segments=48, ring_count=24)
head = bpy.context.object; head.scale = (1, 0.85, 1.12)
bpy.ops.mesh.primitive_cylinder_add(radius=0.42, depth=1.4, location=(0, 0, 0.45))
torso = bpy.context.object; torso.scale = (1.25, 0.8, 1)
for o in (head, torso):
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_add(type='COLLISION'); o.collision.thickness_outer = 0.012

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'out', 'cache_veil.npy')
import numpy as np
bpy.ops.mesh.primitive_grid_add(x_subdivisions=110, y_subdivisions=110, size=3.0, location=(0.05, 0.02, 2.05))
cloth = bpy.context.object
cloth.rotation_euler = (0.06, -0.04, 0.3)
if os.path.exists(CACHE):   # симуляция ткани долгая: считаем один раз и кэшируем форму
    co = np.load(CACHE); cloth.matrix_world.identity()
    cloth.data.vertices.foreach_set('co', co.ravel()); cloth.data.update()
else:
    m = cloth.modifiers.new('cloth', 'CLOTH'); s = m.settings
    s.quality = 6; s.mass = 0.35; s.tension_stiffness = 25; s.compression_stiffness = 25; s.bending_stiffness = 0.6
    s.air_damping = 1.5
    m.collision_settings.use_self_collision = True; m.collision_settings.self_distance_min = 0.006
    m.collision_settings.distance_min = 0.006
    m.point_cache.frame_start = 1; m.point_cache.frame_end = 90
    for f in range(1, 91): sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    em = cloth.evaluated_get(dg).to_mesh()
    co = np.array([cloth.matrix_world @ v.co for v in em.vertices], dtype=np.float32)
    os.makedirs(os.path.dirname(CACHE), exist_ok=True); np.save(CACHE, co)
    cloth.modifiers.clear(); cloth.matrix_world.identity()
    cloth.data.vertices.foreach_set('co', co.ravel()); cloth.data.update()
dg = bpy.context.evaluated_depsgraph_get()
me = bpy.data.meshes.new_from_object(cloth.evaluated_get(dg))
statue = bpy.data.objects.new('statue', me); statue.matrix_world = cloth.matrix_world.copy()
sc.collection.objects.link(statue)
bpy.data.objects.remove(cloth)
for o in (head, torso):
    o.modifiers.clear()
statue.modifiers.new('thick', 'SOLIDIFY').thickness = 0.03
sub = statue.modifiers.new('sub', 'SUBSURF'); sub.levels = 2; sub.render_levels = 2
bpy.ops.object.select_all(action='DESELECT'); statue.select_set(True); bpy.context.view_layer.objects.active = statue
bpy.ops.object.shade_smooth()
sc.frame_set(1)

# ---------- мрамор: прожилки, подповерхностное рассеяние, мох и грязь в складках, влага ----------
def marble_material():
    mat = bpy.data.materials.new('marble'); mat.use_nodes = True
    nt = mat.node_tree; N = nt.nodes; L = nt.links; N.clear()
    out = N.new('ShaderNodeOutputMaterial'); bsdf = N.new('ShaderNodeBsdfPrincipled')
    L.new(bsdf.outputs[0], out.inputs['Surface'])
    tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (2.2, 2.2, 2.2); L.new(tc.outputs['Object'], mp.inputs[0])
    # прожилки
    wave = N.new('ShaderNodeTexWave'); wave.inputs['Scale'].default_value = 1.6; wave.inputs['Distortion'].default_value = 14
    wave.inputs['Detail'].default_value = 8; wave.inputs['Detail Roughness'].default_value = 0.6
    L.new(mp.outputs[0], wave.inputs['Vector'])
    vr = N.new('ShaderNodeValToRGB'); vr.color_ramp.elements[0].position = 0.0; vr.color_ramp.elements[0].color = (0.42, 0.41, 0.38, 1)
    vr.color_ramp.elements[1].position = 0.12; vr.color_ramp.elements[1].color = (0.70, 0.68, 0.64, 1)
    L.new(wave.outputs['Fac'], vr.inputs[0])
    # грязь и мох: в углублениях (AO) + крупный шум, стекает вниз
    ao = N.new('ShaderNodeAmbientOcclusion'); ao.inputs['Distance'].default_value = 0.12; ao.samples = 16
    noise = N.new('ShaderNodeTexNoise'); noise.inputs['Scale'].default_value = 3.5; noise.inputs['Detail'].default_value = 14; noise.inputs['Roughness'].default_value = 0.7
    mp2 = N.new('ShaderNodeMapping'); mp2.inputs['Scale'].default_value = (3, 3, 0.9); L.new(tc.outputs['Object'], mp2.inputs[0]); L.new(mp2.outputs[0], noise.inputs['Vector'])
    fine = N.new('ShaderNodeTexNoise'); fine.inputs['Scale'].default_value = 60; fine.inputs['Detail'].default_value = 10
    L.new(tc.outputs['Object'], fine.inputs['Vector'])
    inv = N.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1; L.new(ao.outputs['AO'], inv.inputs[1])
    mix1 = N.new('ShaderNodeMath'); mix1.operation = 'MULTIPLY_ADD'; mix1.inputs[2].default_value = -0.35
    L.new(noise.outputs['Fac'], mix1.inputs[0]); mix1.inputs[1].default_value = 1.3
    dirt = N.new('ShaderNodeMath'); dirt.operation = 'ADD'; L.new(inv.outputs[0], dirt.inputs[0]); L.new(mix1.outputs[0], dirt.inputs[1])
    dmask = N.new('ShaderNodeValToRGB'); dmask.color_ramp.elements[0].position = 0.22; dmask.color_ramp.elements[1].position = 0.62
    L.new(dirt.outputs[0], dmask.inputs[0])
    fm = N.new('ShaderNodeMath'); fm.operation = 'MULTIPLY'; L.new(dmask.outputs['Color'], fm.inputs[0]); L.new(fine.outputs['Fac'], fm.inputs[1])
    fm2 = N.new('ShaderNodeMath'); fm2.operation = 'MULTIPLY'; fm2.inputs[1].default_value = 1.6; fm2.use_clamp = True; L.new(fm.outputs[0], fm2.inputs[0])
    moss = N.new('ShaderNodeValToRGB')
    moss.color_ramp.elements[0].color = (0.012, 0.013, 0.008, 1); moss.color_ramp.elements[1].color = (0.075, 0.072, 0.04, 1)
    L.new(fine.outputs['Fac'], moss.inputs[0])
    col = N.new('ShaderNodeMix'); col.data_type = 'RGBA'
    L.new(fm2.outputs[0], col.inputs['Factor']); L.new(vr.outputs['Color'], col.inputs[6]); L.new(moss.outputs['Color'], col.inputs[7])
    L.new(col.outputs[2], bsdf.inputs['Base Color'])
    # мокрая поверхность: где чисто — блестит, где мох — матово
    rr = N.new('ShaderNodeMapRange'); rr.inputs[3].default_value = 0.32; rr.inputs[4].default_value = 0.8
    L.new(fm2.outputs[0], rr.inputs[0]); L.new(rr.outputs[0], bsdf.inputs['Roughness'])
    bsdf.inputs['Coat Weight'].default_value = 0.12; bsdf.inputs['Coat Roughness'].default_value = 0.18
    bsdf.inputs['Subsurface Weight'].default_value = 0.35
    bsdf.inputs['Subsurface Radius'].default_value = (0.9, 0.75, 0.6); bsdf.inputs['Subsurface Scale'].default_value = 0.02
    # микрорельеф: поры и выветривание
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.35; bump.inputs['Distance'].default_value = 0.004
    bn = N.new('ShaderNodeTexNoise'); bn.inputs['Scale'].default_value = 140; bn.inputs['Detail'].default_value = 6
    L.new(tc.outputs['Object'], bn.inputs['Vector'])
    bsum = N.new('ShaderNodeMath'); bsum.operation = 'ADD'; L.new(bn.outputs['Fac'], bsum.inputs[0]); L.new(fm2.outputs[0], bsum.inputs[1])
    L.new(bsum.outputs[0], bump.inputs['Height']); L.new(bump.outputs[0], bsdf.inputs['Normal'])
    return mat
mat = marble_material()
for o in (statue, head, torso):
    o.data.materials.clear(); o.data.materials.append(mat)

# ---------- капля: катится по складке (лучом ищем поверхность каждый кадр) ----------
water = bpy.data.materials.new('water'); water.use_nodes = True
wb = water.node_tree.nodes['Principled BSDF']
wb.inputs['Transmission Weight'].default_value = 1.0; wb.inputs['Roughness'].default_value = 0.0; wb.inputs['IOR'].default_value = 1.333
wb.inputs['Base Color'].default_value = (1, 1, 1, 1)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.018, segments=48, ring_count=24)
drop = bpy.context.object; drop.data.materials.append(water); bpy.ops.object.shade_smooth()
drop.modifiers.new('sub', 'SUBSURF').levels = 1

dg = bpy.context.evaluated_depsgraph_get()
ev = statue.evaluated_get(dg)
bm = bmesh.new(); bm.from_mesh(ev.to_mesh()); bm.transform(statue.matrix_world)
tree = BVHTree.FromBMesh(bm)

def surface_at(x, z):
    hit = tree.ray_cast(Vector((x, -3, z)), Vector((0, 1, 0)))
    return hit if hit[0] else None

X0, Z0, Z1 = 0.2, 1.3, 0.92
total = int(a.fps * 6)
trail = []
for f in range(1, total + 1):
    t = (f - 1) / (total - 1)
    hold = 0.18
    u = 0 if t < hold else ((t - hold) / (1 - hold)) ** 1.7
    z = Z0 - (Z0 - Z1) * u
    x = X0 + 0.02 * math.sin(u * 9)
    h = surface_at(x, z)
    if not h: continue
    p, n = h[0], h[1]
    stretch = 1 + 0.9 * min(1, u * 4)
    drop.location = p - n * -0.012
    drop.scale = (1, 0.55, stretch)
    drop.keyframe_insert('location', frame=f); drop.keyframe_insert('scale', frame=f)
    trail.append(p - n * -0.003)

# мокрый след за каплей
if len(trail) > 2:
    cu = bpy.data.curves.new('trail', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.006; cu.bevel_resolution = 4
    sp = cu.splines.new('POLY'); sp.points.add(len(trail) - 1)
    for i, p in enumerate(trail): sp.points[i].co = (*p, 1)
    tr = bpy.data.objects.new('trail', cu); sc.collection.objects.link(tr); tr.data.materials.append(water)
    cu.bevel_factor_mapping_end = 'SPLINE'
    for f in range(1, total + 1):
        t = (f - 1) / (total - 1); u = 0 if t < 0.18 else ((t - 0.18) / 0.82) ** 1.7
        cu.bevel_factor_end = max(0.001, u); cu.keyframe_insert('bevel_factor_end', frame=f)

# ---------- свет: ночь, вспышка у камеры, холодный контровой ----------
w = bpy.data.worlds.new('night'); sc.world = w; w.use_nodes = True
w.node_tree.nodes['Background'].inputs['Color'].default_value = (0.004, 0.005, 0.008, 1)
w.node_tree.nodes['Background'].inputs['Strength'].default_value = 1
def light(kind, loc, energy, color, size, rot=None):
    ld = bpy.data.lights.new(kind, kind); ld.energy = energy; ld.color = color
    if kind == 'AREA': ld.size = size
    else: ld.shadow_soft_size = size
    o = bpy.data.objects.new(kind, ld); o.location = loc; sc.collection.objects.link(o)
    if rot: o.rotation_euler = rot
    return o
flash = light('SPOT', (0.62, -2.15, 1.62), 90, (1.0, 0.95, 0.88), 0.04)
flash.data.spot_size = 0.9; flash.data.spot_blend = 0.6
rimL = light('AREA', (-1.4, 1.2, 2.2), 25, (0.55, 0.65, 1.0), 0.8)
for o in (flash, rimL):
    c = o.constraints.new('TRACK_TO'); c.target = head; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'

# земля: тёмные камни
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, -0.25))
ground = bpy.context.object
gm = bpy.data.materials.new('ground'); gm.use_nodes = True
gm.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (0.02, 0.02, 0.018, 1)
gm.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value = 0.85
ground.data.materials.append(gm)

# ---------- камера: 100 мм макро, малая ГРИП, медленный наезд + дыхание руки ----------
cd = bpy.data.cameras.new('cam'); cd.lens = 58; cd.sensor_width = 36
cd.dof.use_dof = True; cd.dof.aperture_fstop = 2.0; cd.dof.focus_object = drop
cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam); sc.camera = cam
tgt = bpy.data.objects.new('tgt', None); sc.collection.objects.link(tgt)
c = cam.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
for f in range(1, total + 1, 2):
    t = (f - 1) / (total - 1)
    cam.location = (0.95 + 0.004 * math.sin(f * 0.21), -2.35 + 0.3 * t, 1.32 + 0.003 * math.sin(f * 0.17 + 1))
    cam.keyframe_insert('location', frame=f)
    sc.frame_set(f)
    tgt.location = drop.matrix_world.translation * 0.35 + Vector((0.05, 0, 1.12)) * 0.65
    tgt.keyframe_insert('location', frame=f)

sc.frame_start, sc.frame_end = 1, total
os.makedirs(a.out, exist_ok=True)
frames = range(1, total + 1) if a.frames == 'all' else [int(x) for x in a.frames.split(',')]
if '-' in a.frames:
    s0, s1 = map(int, a.frames.split('-')); frames = range(s0, s1 + 1)
for f in frames:
    sc.frame_set(f)
    sc.render.filepath = os.path.join(os.path.abspath(a.out), f'f_{f:05d}.png')
    bpy.ops.render.render(write_still=True)
    print('frame', f, flush=True)
