# Кадр «Слеза»: мраморная голова (скан Lee Perry-Smith, Infinite Realities, CC BY 3.0),
# ночь, вспышка, из-под закрытого века набегает слеза и скатывается по щеке.
# python blender/shots/tear.py -- --out out/tear --w 1920 --h 1080 --frames 1,60,120 --samples 128
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import kf

a = kf.args([(['--shot'], dict(default='close'))])
sc = kf.setup(a)
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
S = 0.045  # единица скана -> метры (голова ~15 см шириной... для статуи берём 1:1 с человеком)
S = 0.07   # статуя чуть крупнее натуры

bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, 'assets/scans/LeePerrySmith.glb'))
for o in list(sc.objects):
    if o.type != 'MESH': bpy.data.objects.remove(o)
head = bpy.data.objects['LeePerrySmith']
# нормал-карта скана — даёт мелкий рельеф кожи, на камне читается как резьба резца
src = head.data.materials[0]
nimg = next((n.image for n in src.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image and 'Tangent' in n.image.name), None)
head.scale = (S, S, S)
bpy.context.view_layer.objects.active = head; head.select_set(True)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.object.shade_smooth()
sub = head.modifiers.new('sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 2

mat, bsdf, bump, nt = kf.weathered_marble(scale=0.3, dirt=0.8, wet=0.7)
if nimg:
    ti = nt.nodes.new('ShaderNodeTexImage'); ti.image = nimg; nimg.colorspace_settings.name = 'Non-Color'
    uv = nt.nodes.new('ShaderNodeUVMap'); nt.links.new(uv.outputs[0], ti.inputs[0])
    nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs['Strength'].default_value = 0.8
    nt.links.new(ti.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs[0], bump.inputs['Normal'])
nt.links.new(bump.outputs[0], bsdf.inputs['Normal'])
head.data.materials.clear(); head.data.materials.append(mat)

# ---------- поверхность для капли ----------
dg = bpy.context.evaluated_depsgraph_get()
bm = bmesh.new(); bm.from_mesh(head.evaluated_get(dg).to_mesh()); bm.transform(head.matrix_world)
tree = BVHTree.FromBMesh(bm)
def surf(x, z):
    h = tree.ray_cast(Vector((x, -1, z)), Vector((0, 1, 0)))
    return h if h[0] else None

EYE = Vector((0.50 * S, 0, 1.585 * S))   # нижнее веко правого (в кадре) глаза
total = a.fps * 7
drop_mat = kf.water()
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.0018, segments=64, ring_count=32)
drop = bpy.context.object; drop.data.materials.append(drop_mat); bpy.ops.object.shade_smooth()

trail = []
def drop_state(f):
    t = f / a.fps
    grow = min(1, max(0, (t - 0.5) / 2.0))              # 0.5–2.5 c: набухает на веке
    slide = max(0, t - 3.2)                              # с 3.2 c: срывается
    dz = 0.5 * 0.006 * slide ** 2 + 0.004 * slide       # ускорение, затем трение
    dz = min(dz, 0.75 * S)
    x = EYE.x + 0.08 * S * math.sin(dz / S * 2.2) + dz * 0.12
    return grow, x, EYE.z - dz, slide
for f in range(1, total + 1):
    grow, x, z, slide = drop_state(f)
    h = surf(x, z)
    if not h: continue
    p, n = h[0], h[1]
    r = 0.0018 * (0.25 + 0.75 * grow)
    drop.location = p + n * r * 0.35
    drop.scale = (0.25 + 0.75 * grow, (0.25 + 0.75 * grow) * 0.7, (0.25 + 0.75 * grow) * (1 + min(0.8, slide * 1.5)))
    drop.rotation_euler = (0, 0, 0)
    drop.keyframe_insert('location', frame=f); drop.keyframe_insert('scale', frame=f)
    if slide > 0: trail.append(p + n * 0.0003)

# мокрая дорожка: тонкая плёнка воды по следу
if len(trail) > 3:
    cu = bpy.data.curves.new('trail', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.00045; cu.bevel_resolution = 3
    sp = cu.splines.new('POLY'); sp.points.add(len(trail) - 1)
    for i, p in enumerate(trail): sp.points[i].co = (*p, 1)
    tr = bpy.data.objects.new('trail', cu); sc.collection.objects.link(tr); tr.data.materials.append(drop_mat)
    tr.scale = (1, 1, 1)
    first = next(f for f in range(1, total + 1) if drop_state(f)[3] > 0)
    for f in range(1, total + 1):
        cu.bevel_factor_end = max(0.0, min(1, (f - first) / max(1, total - first))) if f >= first else 0
        cu.keyframe_insert('bevel_factor_end', frame=f)

# ---------- свет: ночная вспышка у объектива + холодная луна ----------
kf.world((0.002, 0.0025, 0.004))
eye_empty = bpy.data.objects.new('eye', None); eye_empty.location = EYE + Vector((0, -0.02, 0)); sc.collection.objects.link(eye_empty)
if a.shot == 'close':
    cam, tgt = kf.camera(lens=100, fstop=5.6, focus=drop)
    base = EYE + Vector((0.11, -0.52, -0.005))
else:
    cam, tgt = kf.camera(lens=50, fstop=2.8, focus=eye_empty)
    base = Vector((0.55 * S * 10, -1.4, 1.1 * S * 10)) * 0.1 + Vector((0.12, -0.55, 0.08))
flash = kf.light('SPOT', base + Vector((-0.03, 0.0, 0.06)), 4.5 if a.shot == 'close' else 30, (1, 0.96, 0.9), 0.004, target=eye_empty, spot=(0.6, 0.5))
moon = kf.light('AREA', (-0.8, 0.6, 1.2), 1.2, (0.6, 0.7, 1.0), 0.6, target=head)
for f in range(1, total + 1, 2):
    t = f / total
    cam.location = base + Vector((0, 0.06 * t, 0)) + kf.handheld(f, 0.0012)
    cam.keyframe_insert('location', frame=f)
    sc.frame_set(f)
    tgt.location = drop.matrix_world.translation * 0.5 + EYE * 0.5 if a.shot == 'close' else EYE
    tgt.keyframe_insert('location', frame=f)

sc.frame_start, sc.frame_end = 1, total
kf.render(a, kf.frames_from(a, total))
