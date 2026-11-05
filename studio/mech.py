# Робот-актёр: твёрдые оболочки на том же скелете мокапа, что и у людей. Вся анимация (ходьба, бег, взгляд) даром:
# каждая деталь привязана к своей кости и движется с ней, без скиннинга и без деформаций.
# Уроки референсов (дорогой CGI-робот): фаски на всех рёбрах ловят блик; два материала корпуса (светлый пластик и
# тёмный графит) + металл в суставах; износ во впадинах; глаза — свет в тёмном визоре: лица нет, а взгляд читается.
# Карточка актёра: {"model": null, "mech": {"skeleton": "Soldier.glb", "shell": [r,g,b], "frame": [r,g,b], "eyes": "#9FE8FF", "wear": 0.4}}
import math
import bpy
from mathutils import Vector, Matrix

def _mat(name, col, rough, metal=0.0, coat=0.0, emit=None, strength=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = next(n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = (*col, 1); p.inputs['Roughness'].default_value = rough
    p.inputs['Metallic'].default_value = metal
    if coat and 'Coat Weight' in p.inputs: p.inputs['Coat Weight'].default_value = coat; p.inputs['Coat Roughness'].default_value = 0.15
    if emit:
        p.inputs['Emission Color'].default_value = (*emit, 1); p.inputs['Emission Strength'].default_value = strength
    return m

def _lin(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)

def _round(ob, width, seg=4, sub=1):
    """Скруглённые рёбра (фаска + сглаживание): деталь выглядит отлитой, а не собранной из примитивов."""
    b = ob.modifiers.new('bevel', 'BEVEL'); b.width = width; b.segments = seg; b.limit_method = 'ANGLE'; b.harden_normals = False
    if sub: s = ob.modifiers.new('sub', 'SUBSURF'); s.levels = sub; s.render_levels = sub
    for p in ob.data.polygons: p.use_smooth = True

def _attach(ob, arm, bone, world_target):
    """Привязать деталь к кости так, чтобы в текущей позе она стояла в world_target (матрица в метрах сцены)."""
    pb = arm.pose.bones[bone]
    P = arm.matrix_world @ pb.matrix @ Matrix.Translation((0, pb.bone.length, 0))   # родитель-кость = её хвост
    ob.parent = arm; ob.parent_type = 'BONE'; ob.parent_bone = bone
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = P.inverted() @ world_target

def _frame(origin, z_axis, fwd):
    """Матрица: начало origin, ось Z детали вдоль z_axis, ось Y — к «вперёд» героя."""
    z = z_axis.normalized(); x = fwd.cross(z)
    if x.length < 1e-4: x = Vector((1, 0, 0)).cross(z)
    x.normalize(); y = z.cross(x)
    M = Matrix((x, y, z)).transposed().to_4x4(); M.translation = origin
    return M

def build(arm, spec, meshes=()):
    """Собрать робота на скелете arm. meshes — исходные сетки модели (прячутся). Возвращает список деталей."""
    sc = bpy.context.scene; bpy.context.view_layer.update()
    for o in meshes: o.hide_render = True; o.hide_viewport = True
    W = arm.matrix_world; pbs = arm.pose.bones
    def bn(n):
        for k in (f'mixamorig:{n}', f'mixamorig{n}', n):
            if k in pbs: return k
        return None
    def head(n): return W @ pbs[bn(n)].head
    def tail(n): return W @ pbs[bn(n)].tail
    fwd = (head('LeftToeBase') - head('LeftFoot')); fwd.z = 0; fwd.normalize()
    # светлый пластик: альбедо ≤ 0.45 — свет гаффера рассчитан на людей, белое 0.8 под ключом выгорает в блум (замер на Храме)
    sh_c = tuple(min(0.45, c) for c in spec.get('shell', (0.78, 0.76, 0.72)))
    shell = _mat('mech_shell', sh_c, 0.42, coat=0.25)
    frame = _mat('mech_frame', tuple(spec.get('frame', (0.035, 0.037, 0.04))), 0.35, coat=0.1)
    metal = _mat('mech_metal', (0.62, 0.62, 0.64), 0.28, metal=1.0)
    visor = _mat('mech_visor', (0.005, 0.005, 0.006), 0.06, coat=1.0)
    eyec = _lin(spec.get('eyes', '#9FE8FF'))
    eyes = _mat('mech_eyes', eyec, 0.3, emit=eyec, strength=9.0)
    parts = []
    def add(prim, bone, M, mat, rnd=0.0, **kw):
        getattr(bpy.ops.mesh, prim)(**kw); o = bpy.context.object; o.name = f'mech_{bone}_{len(parts)}'
        o.data.materials.append(mat)
        if rnd: _round(o, rnd)
        else:
            for p in o.data.polygons: p.use_smooth = True
        _attach(o, arm, bn(bone), M); parts.append(o); return o
    # конечности: «капсулы» вдоль кости (светлый корпус) + металлические сферы в суставах
    limbs = [('LeftArm', 'LeftForeArm', 0.055), ('LeftForeArm', 'LeftHand', 0.045), ('RightArm', 'RightForeArm', 0.055),
             ('RightForeArm', 'RightHand', 0.045), ('LeftUpLeg', 'LeftLeg', 0.078), ('LeftLeg', 'LeftFoot', 0.062),
             ('RightUpLeg', 'RightLeg', 0.078), ('RightLeg', 'RightFoot', 0.062)]
    for b0, b1, r in limbs:
        p0, p1 = head(b0), head(b1); L = (p1 - p0).length
        add('primitive_cylinder_add', b0, _frame((p0 + p1) / 2, p1 - p0, fwd), shell, rnd=r * 0.55, vertices=20, radius=r, depth=L * 0.78)
    for b, r in (('LeftArm', 0.068), ('RightArm', 0.068), ('LeftForeArm', 0.05), ('RightForeArm', 0.05), ('LeftHand', 0.036), ('RightHand', 0.036),
                 ('LeftUpLeg', 0.08), ('RightUpLeg', 0.08), ('LeftLeg', 0.066), ('RightLeg', 0.066), ('LeftFoot', 0.05), ('RightFoot', 0.05)):
        parent = b if b in ('LeftUpLeg', 'RightUpLeg', 'LeftArm', 'RightArm') else b
        add('primitive_uv_sphere_add', parent, _frame(head(b), Vector((0, 0, 1)), fwd), metal, segments=24, ring_count=12, radius=r)
    # кисти — «варежки», стопы — обтекаемые башмаки
    for side in ('Left', 'Right'):
        h0, h1 = head(f'{side}Hand'), head(f'{side}HandMiddle1') if bn(f'{side}HandMiddle1') else tail(f'{side}Hand')
        d = (h1 - h0); M = _frame(h0 + d * 0.9, d, fwd) @ Matrix.Diagonal((0.042, 0.022, max(0.05, d.length * 0.9), 1))
        add('primitive_cube_add', f'{side}Hand', M, frame, rnd=0.0, size=2)
        f0, f1 = head(f'{side}Foot'), head(f'{side}ToeBase'); fd = f1 - f0; fd.z = 0
        c = (f0 + f1) / 2 + fd * 0.25; c.z = 0.045
        M = _frame(c, fd, Vector((0, 0, 1))) @ Matrix.Diagonal((0.05, 0.04, fd.length * 0.95, 1))
        add('primitive_cube_add', f'{side}Foot', M, shell, size=2)
    for o in parts[-4:]:
        if o.data.materials[0] == shell or o.data.materials[0] == frame: _round(o, 0.18, seg=3)
    # корпус: грудь — светлая «скорлупа», живот — тёмный гофр, таз — тёмный блок
    up = head('Neck') - head('Hips'); upn = up.normalized()
    chest_c = head('Spine2') + upn * 0.10
    add('primitive_cube_add', 'Spine2', _frame(chest_c, upn, fwd) @ Matrix.Diagonal((0.16, 0.105, 0.15, 1)), shell, size=2)
    _round(parts[-1], 0.55, seg=5)
    tp = parts[-1].modifiers.new('taper', 'SIMPLE_DEFORM'); tp.deform_method = 'TAPER'; tp.factor = 0.35; tp.deform_axis = 'Z'   # грудь шире кверху: силуэт, а не «почтовый ящик»
    parts[-1].modifiers.move(len(parts[-1].modifiers) - 1, 0)
    for i, b in enumerate(('Spine', 'Spine1')):
        p = head(b) + upn * 0.05
        add('primitive_cylinder_add', b, _frame(p, upn, fwd) @ Matrix.Diagonal((1.0, 0.72, 1.0, 1)), frame, rnd=0.012, vertices=24, radius=0.12 - 0.01 * i, depth=0.075)
    add('primitive_cube_add', 'Hips', _frame(head('Hips') - upn * 0.03, upn, fwd) @ Matrix.Diagonal((0.15, 0.1, 0.075, 1)), frame, size=2)
    _round(parts[-1], 0.3, seg=3)
    # шея и голова: металлический стержень, «яйцо» шлема, тёмный визор, два светящихся глаза-штриха
    n0, n1 = head('Neck'), head('Head')
    add('primitive_cylinder_add', 'Neck', _frame((n0 + n1) / 2, n1 - n0, fwd), metal, vertices=16, radius=0.032, depth=(n1 - n0).length * 1.1)
    hc = n1 + upn * 0.1
    add('primitive_uv_sphere_add', 'Head', _frame(hc, upn, fwd) @ Matrix.Diagonal((0.105, 0.12, 0.135, 1)), shell, segments=32, ring_count=16, radius=1.0)
    add('primitive_uv_sphere_add', 'Head', _frame(hc + fwd * 0.062 + upn * 0.01, upn, fwd) @ Matrix.Diagonal((0.085, 0.07, 0.06, 1)), visor, segments=32, ring_count=16, radius=1.0)
    rt = fwd.cross(upn).normalized()
    for s in (-1, 1):
        add('primitive_cylinder_add', 'Head', _frame(hc + fwd * 0.128 + rt * (0.024 * s) + upn * 0.012, upn, fwd), eyes, vertices=12, radius=0.0065, depth=0.034)
    # акцент: тонкая светящаяся полоска на груди (цвет глаз) — одна деталь, которая «живёт»
    add('primitive_cube_add', 'Spine2', _frame(chest_c + fwd * 0.118 + upn * 0.07 + rt * 0.08, upn, fwd) @ Matrix.Diagonal((0.008, 0.003, 0.022, 1)), eyes, size=2)
    if spec.get('wear'):
        import materials
        materials.wear([shell, frame], spec['wear'], distance=0.03)
    print(f'робот: {len(parts)} деталей на скелете', flush=True)
    return parts
