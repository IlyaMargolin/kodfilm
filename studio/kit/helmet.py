# Интегральный мотошлем по голове актёра: светлая угловатая оболочка, вставка цвета морской волны по темени,
# подбородочная дуга с прорезями, прозрачное забрало на двух шарнирах. Деталь привязана к кости головы.
#   h = build(body, arm, shell=(r,g,b), stripe=(r,g,b))  -> dict(root, visor_pivot, shell, visor)
#   visor(h, 0..1)   0 — закрыто, 1 — поднято (~55°)
import math
import bpy, bmesh
import numpy as np
from mathutils import Vector, Matrix
from wardrobe import _w
from kit.moto import _mat

def _head_box(body, arm):
    """Габариты головы в мире (по вершинам с весом головы) и базис: центр, вперёд, вверх, вбок."""
    off = [m for m in body.modifiers if m.type in ('SUBSURF', 'MASK', 'PARTICLE_SYSTEM') and m.show_viewport]
    for m in off: m.show_viewport = False
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get(); ev = body.evaluated_get(dg); me = ev.to_mesh()
    ps = body.get('proxy_start', 10 ** 9)
    idx = [v.index for v in body.data.vertices if v.index < ps and _w(body, v, ('Head', 'HeadTop')) > 0.5]
    mw = body.matrix_world
    assert len(me.vertices) == len(body.data.vertices), 'шлем: топология головы изменилась модификатором'
    P = np.array([(mw @ me.vertices[i].co)[:] for i in idx]); ev.to_mesh_clear()
    for m in off: m.show_viewport = True
    pb = arm.pose.bones['mixamorig:Head']; M = arm.matrix_world @ pb.matrix
    up = (M.to_3x3() @ Vector((0, 1, 0))).normalized()
    import human
    el, er = human.eyes_world(body, arm); em = (Vector(el) + Vector(er)) / 2
    fwd = em - M.translation; fwd = (fwd - up * fwd.dot(up)).normalized()
    side = fwd.cross(up).normalized()   # правый базис: side × fwd = up
    c = Vector(P.mean(0)); R = np.array([[*side], [*fwd], [*up]])
    L = (P - np.array(c)) @ R.T
    lo, hi = L.min(0), L.max(0)
    c = c + side * ((lo[0] + hi[0]) / 2) + fwd * ((lo[1] + hi[1]) / 2) + up * ((lo[2] + hi[2]) / 2)
    return c, fwd, up, side, (hi - lo) / 2

def build(body, arm, shell=(0.5, 0.46, 0.4), stripe=(0.05, 0.16, 0.16), name='helmet'):
    bpy.context.view_layer.update()
    c, fwd, up, side, half = _head_box(body, arm)
    print('helmet: голова полуразмеры', [round(x, 3) for x in half], flush=True)
    # внутренние радиусы шлема: голова + подкладка 2.5 см; центр чуть выше центра головы (шлем закрывает темя, не подбородок)
    rx, ry, rz = half[0] + 0.03, half[1] + 0.03, half[2] * 0.88 + 0.03
    cc = c + up * (half[2] * 0.12)
    Mh = Matrix((side, fwd, up)).transposed().to_4x4(); Mh.translation = cc   # локально: X вбок, Y вперёд, Z вверх
    M_shell = _mat(name + '_shell', shell, 0.32, coat=0.5, wear=((0.2, 0.18, 0.15), 10, 0.08))
    M_stripe = _mat(name + '_stripe', stripe, 0.3, coat=0.5)
    M_pad = _mat(name + '_pad', (0.025, 0.025, 0.028), 0.85)
    M_trim = _mat(name + '_trim', (0.03, 0.03, 0.032), 0.4)
    M_visor = bpy.data.materials.get(name + '_visor') or _visor_mat(name + '_visor')
    root = bpy.data.objects.new(name, None); bpy.context.scene.collection.objects.link(root)
    # --- оболочка ---
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=40, radius=1.0)
    ey = (body.get('eyes') and True)
    for v in bm.verts:
        x, y, z = v.co
        # угловатость: слегка «граненый» силуэт (сплюснуть к плоскостям) и затылок ниже лба
        k = 1.0 + 0.06 * (abs(x) ** 3 + abs(y) ** 3) - 0.04 * abs(z) ** 3
        chin = max(0.0, -z) * max(0.0, y)                      # подбородочная дуга выдвинута вперёд
        flat = 1.0 - 0.07 * max(0.0, abs(x) - 0.55)            # боковины площе
        v.co = Vector((x * rx * k * flat, y * ry * k * (1 + 0.22 * chin), z * rz * (1.08 if z > 0 else 1.25)))
    # срезы: низ открыт (шея), окно для лица спереди
    kill = []
    for v in bm.verts:
        x, y, z = v.co.x / rx, v.co.y / ry, v.co.z / rz
        if z < -0.95 + 0.55 * max(0, y): kill.append(v); continue   # вырез под шею, спереди ниже (подбородочная дуга)
        if y > 0.3 and -0.5 < z < 0.2 and abs(x) < 0.68: kill.append(v)   # окно лица: от бровей до губ
    bmesh.ops.delete(bm, geom=list(set(kill)), context='VERTS')
    for f in bm.faces:
        cx = f.calc_center_median(); x, y, z = cx.x / rx, cx.y / ry, cx.z / rz
        f.material_index = 1 if (abs(x) < 0.16 and z > 0.15 and y > -0.55) else 0
        f.smooth = True
    me = bpy.data.meshes.new(name + '_shell'); bm.to_mesh(me); bm.free()
    for m in (M_shell, M_stripe, M_pad): me.materials.append(m)
    sh = bpy.data.objects.new(name + '_shell', me); bpy.context.scene.collection.objects.link(sh); sh.parent = root
    s = sh.modifiers.new('thick', 'SOLIDIFY'); s.thickness = 0.022; s.offset = 1; s.material_offset = 2; s.use_rim = True; s.material_offset_rim = 2
    sb = sh.modifiers.new('sub', 'SUBSURF'); sb.levels = 1; sb.render_levels = 2
    # кант окна и подбородка, прорези вентиляции
    # прорези на подбородочной дуге: тёмные вставки по месту (найдено по самой оболочке)
    pts = [Vector(v.co) for v in me.vertices]
    for i, zz in enumerate((-0.62, -0.72, -0.82)):
        band = [p for p in pts if abs(p.z / rz / 1.25 - zz) < 0.04 and abs(p.x) < rx * 0.15]
        if not band: continue
        yy = max(p.y for p in band)
        bpy.ops.mesh.primitive_cube_add(size=1); o = bpy.context.object; o.name = f'{name}_vent{i}'
        o.scale = (rx * 0.45 * (1 - 0.15 * i), 0.02, 0.01); o.location = (0, yy + 0.012, zz * rz * 1.25)
        o.data.materials.append(M_trim); o.parent = root
    for sx in (-1, 1):   # шарниры забрала
        bpy.ops.mesh.primitive_cylinder_add(radius=0.024, depth=0.012, vertices=24, location=(sx * (rx + 0.022), ry * 0.05, -rz * 0.1), rotation=(0, math.pi / 2, 0))
        o = bpy.context.object; o.name = f'{name}_hinge{sx}'; o.data.materials.append(M_trim); o.parent = root
    # --- забрало: часть сферы чуть больше оболочки, поворот вокруг оси шарниров ---
    piv = bpy.data.objects.new(name + '_visor_pivot', None); bpy.context.scene.collection.objects.link(piv)
    piv.parent = root; piv.location = (0, ry * 0.05, -rz * 0.1)
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=40, radius=1.0)
    kill = []
    for v in bm.verts:
        x, y, z = v.co
        if not (y > 0.12 and -0.72 < z < 0.34 and abs(x) < 0.97): kill.append(v)
        v.co = Vector((x * (rx + 0.03), y * (ry + 0.03), z * (rz + 0.02) * (1.08 if z > 0 else 1.2)))
    bmesh.ops.delete(bm, geom=kill, context='VERTS')
    for v in bm.verts: v.co -= Vector(piv.location)
    for f in bm.faces: f.smooth = True
    me = bpy.data.meshes.new(name + '_visor'); bm.to_mesh(me); bm.free(); me.materials.append(M_visor)
    vi = bpy.data.objects.new(name + '_visor', me); bpy.context.scene.collection.objects.link(vi); vi.parent = piv
    s = vi.modifiers.new('thick', 'SOLIDIFY'); s.thickness = 0.003
    sb = vi.modifiers.new('sub', 'SUBSURF'); sb.render_levels = 1
    # привязать к кости головы
    pb = arm.pose.bones['mixamorig:Head']
    P = arm.matrix_world @ pb.matrix @ Matrix.Translation((0, pb.bone.length, 0))
    root.parent = arm; root.parent_type = 'BONE'; root.parent_bone = 'mixamorig:Head'
    root.matrix_parent_inverse = Matrix.Identity(4); root.matrix_basis = P.inverted() @ Mh
    return dict(root=root, visor_pivot=piv, shell=sh, visor=vi)

def _visor_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True; p = m.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (0.42, 0.42, 0.4, 1); p.inputs['Roughness'].default_value = 0.02
    p.inputs['Transmission Weight'].default_value = 1.0; p.inputs['IOR'].default_value = 1.49
    return m

def visor(h, k):
    h['visor_pivot'].rotation_euler = (math.radians(78 * k), 0, 0)
