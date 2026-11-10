# Мотоэкипировка поверх тела MakeHuman: короткая кожаная куртка со вставками, плотные брюки, высокие ботинки, перчатки.
# Каждая вещь — оболочка, снятая с тела по весам костей и раздутая по нормалям на толщину материала. Веса копируются
# с кожи, поэтому одежда идёт за скелетом мокапа без отдельного рига (тот же приём, что у рясы в wardrobe.py).
# Тело под одеждой не рендерится (маска 'covered'): кожа не протыкает куртку на сгибах.
#   gear = riderwear.dress(body, arm, jacket=(r,g,b), panel=(r,g,b), pants=..., boots=..., gloves=...)
import math
import bpy, bmesh
import numpy as np
from mathutils import Vector
from wardrobe import _w, _smooth_weights, _rig_like

def _leather(name, col, rough=0.55, panel=None, wear=0.2, emboss=0.0):
    """Кожа/ткань: тёмные вставки по атрибуту 'panel', потёртость по выступам (шум), мелкая фактура в бампе."""
    m = bpy.data.materials.new(name); m.use_nodes = True; N, L = m.node_tree.nodes, m.node_tree.links
    p = N['Principled BSDF']; p.inputs['Roughness'].default_value = rough
    p.inputs['Sheen Weight'].default_value = 0.15
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 18; nz.inputs['Detail'].default_value = 6
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    dirt = N.new('ShaderNodeMix'); dirt.data_type = 'RGBA'; dirt.blend_type = 'MULTIPLY'
    dirt.inputs[6].default_value = (*col, 1)
    k = N.new('ShaderNodeMapRange'); k.inputs['To Min'].default_value = (1, 1, 1) if False else 1.0 - wear; k.inputs['To Max'].default_value = 1.0
    L.new(nz.outputs['Fac'], k.inputs['Value'])
    cc = N.new('ShaderNodeCombineColor'); [L.new(k.outputs['Result'], cc.inputs[i]) for i in range(3)]
    dirt.inputs[0].default_value = 1.0; L.new(cc.outputs['Color'], dirt.inputs[7])
    out = dirt.outputs[2]
    if panel is not None:
        at = N.new('ShaderNodeAttribute'); at.attribute_name = 'panel'
        th = N.new('ShaderNodeMapRange'); th.inputs['From Min'].default_value = 0.42; th.inputs['From Max'].default_value = 0.5
        L.new(at.outputs['Fac'], th.inputs['Value'])
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; L.new(th.outputs['Result'], mx.inputs[0])
        L.new(out, mx.inputs[6]); mx.inputs[7].default_value = (*panel, 1); out = mx.outputs[2]
        rr = N.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = rough; rr.inputs['To Max'].default_value = 0.8
        L.new(th.outputs['Result'], rr.inputs['Value']); L.new(rr.outputs['Result'], p.inputs['Roughness'])
    L.new(out, p.inputs['Base Color'])
    bm = N.new('ShaderNodeBump'); bm.inputs['Strength'].default_value = 0.12 + 0.12 * emboss; bm.inputs['Distance'].default_value = 0.002
    nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 220; L.new(tc.outputs['Object'], nz2.inputs['Vector'])
    h = nz2.outputs['Fac']
    if emboss:   # тиснёная кожа: сетка мелких «плиток» (Вороной, расстояние до края) — как на карточке куртки
        vo = N.new('ShaderNodeTexVoronoi'); vo.feature = 'DISTANCE_TO_EDGE'; vo.inputs['Scale'].default_value = 210
        L.new(tc.outputs['Object'], vo.inputs['Vector'])
        cr = N.new('ShaderNodeMapRange'); cr.inputs['From Max'].default_value = 0.08; L.new(vo.outputs['Distance'], cr.inputs['Value'])
        ad = N.new('ShaderNodeMath'); ad.operation = 'MULTIPLY_ADD'; ad.inputs[1].default_value = 0.15
        L.new(nz2.outputs['Fac'], ad.inputs[0]); L.new(cr.outputs['Result'], ad.inputs[2]); h = ad.outputs[0]
    L.new(h, bm.inputs['Height']); L.new(bm.outputs['Normal'], p.inputs['Normal'])
    return m

def _shell(body, arm, name, keep, offset, mat, thick=0.004, panel=None, smooth_keep=(), smooth=0.0, hem=None):
    """Оболочка по маске вершин keep[i] (bool) с отступом offset[i] (м) по нормали покоя."""
    me = body.data.copy(); me.name = name
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = body.matrix_world.copy()
    if me.shape_keys: ob.shape_key_clear()   # мимика тела одежде не нужна
    # убрать модификаторы-наследство и частицы: только меш и группы
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table()
    nrm = np.array([v.normal[:] for v in bm.verts])
    for v in bm.verts:
        if keep[v.index]: v.co += Vector(nrm[v.index]) * offset[v.index]
    if panel is not None:
        lay = bm.verts.layers.float.new('panel'); bm.verts.ensure_lookup_table()
        for v in bm.verts: v[lay] = float(panel[v.index])
    kill = [v for v in bm.verts if not keep[v.index]]
    bmesh.ops.delete(bm, geom=kill, context='VERTS')
    if hem is not None:   # ровный подол: нижняя кромка торса — в одну плоскость
        for v in bm.verts:
            if v.is_boundary and v.co.z < hem + 0.05 and v.co.z > hem - 0.08: v.co.z = hem
    if smooth:   # ткань не повторяет рельеф мышц: сглаживаем форму в покое, кромки (подол, манжеты) держим на месте
        inner = [v for v in bm.verts if not v.is_boundary and all(not n.is_boundary for e in v.link_edges for n in e.verts)]
        for _ in range(int(smooth)):
            bmesh.ops.smooth_vert(bm, verts=inner, factor=0.6, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    # убрать мелкие острова (соски, пупок и т. п. в стыке масок)
    bm.to_mesh(me); bm.free()
    while me.materials: me.materials.pop()
    me.materials.append(mat)
    for p in me.polygons: p.material_index = 0; p.use_smooth = True
    if 'covered' in ob.vertex_groups: ob.vertex_groups.remove(ob.vertex_groups['covered'])
    _smooth_weights(ob, iters=6, k=0.5, keep=smooth_keep)
    am = ob.modifiers.new('body', 'ARMATURE'); am.object = arm
    ob.parent = arm; ob.matrix_parent_inverse = arm.matrix_world.inverted()
    s = ob.modifiers.new('thick', 'SOLIDIFY'); s.thickness = thick; s.offset = -1
    sb = ob.modifiers.new('sub', 'SUBSURF'); sb.levels = 1; sb.render_levels = 2
    return ob

def dress(body, arm, jacket=(0.5, 0.45, 0.37), panel=(0.07, 0.07, 0.075), pants=(0.075, 0.075, 0.08),
          boots=(0.38, 0.35, 0.3), gloves=(0.05, 0.05, 0.055)):
    me = body.data; ps = body.get('proxy_start', 10 ** 9); nv = len(me.vertices)
    co = np.array([v.co[:] for v in me.vertices]); nrm = np.array([v.normal[:] for v in me.vertices])
    def W(names): return np.array([_w(body, v, names) if v.index < ps else 0.0 for v in me.vertices])
    w_hand = W(('Hand',)); w_head = W(('Head', 'HeadTop')); w_neck = W(('Neck',)); w_foot = W(('Foot', 'Toe'))
    w_leg = W(('UpLeg', 'Leg')); w_hips = W(('Hips',)); w_arm = W(('Arm', 'ForeArm', 'Shoulder')); w_spine = W(('Spine',))
    w_low = W(('Leg',)) - W(('UpLeg',)) * 0   # голень
    w_low = np.array([_w(body, v, ('LeftLeg', 'RightLeg')) if v.index < ps else 0.0 for v in me.vertices])
    body_ok = np.arange(nv) < ps
    z = co[:, 2]
    # опорные высоты в позе покоя (+Z вверх у тела MakeHuman в нашем загрузчике)
    zs = z[body_ok]; zmin, zmax = zs.min(), zs.max(); H = zmax - zmin
    belt = zmin + H * 0.555        # пояс брюк / низ короткой куртки
    boot_top = zmin + H * 0.2      # верх высоких ботинок (середина голени)
    neck_cut = zmin + H * 0.872    # верх стойки воротника
    print(f'riderwear: рост {H:.2f} м, пояс {belt - zmin:.2f}, верх ботинок {boot_top - zmin:.2f}', flush=True)
    is_hand = body_ok & (w_hand > 0.5)
    is_head = body_ok & ((w_head > 0.3) | ((w_neck > 0.25) & (z > neck_cut)))
    is_boot = body_ok & ((w_foot > 0.3) | (z < boot_top)) & ~is_hand
    jk = body_ok & ~is_hand & ~is_head & ~is_boot & (z > belt - 0.04)
    lower = body_ok & ~is_hand & ~is_head & (z < belt + 0.04) & (z > boot_top - 0.07)
    # вставки: бока торса и низ рукава (по нормали покоя: тело стоит лицом к -Y, руки разведены по X)
    # торс: вставки — вертикальные полосы по бокам (азимут вокруг оси тела), от подмышки до низа куртки;
    # рукав: внутренняя сторона (нормаль к телу)
    torso = body_ok & (w_arm < 0.5)
    cx, cy = np.median(co[torso, 0]), np.median(co[torso, 1])
    fy = -1.0
    if 'eyes' in body: fy = 1.0 if (body['eyes'][0][1] + body['eyes'][1][1]) / 2 > cy else -1.0   # куда смотрит лицо в покое
    az = np.arctan2(co[:, 0] - cx, fy * (co[:, 1] - cy))       # 0 — грудь, ±pi/2 — бока
    side = (np.abs(np.sin(az)) > 0.86) & (z < neck_cut - 0.16)
    armpart = w_arm > 0.5
    under = armpart & (np.sign(co[:, 0] - cx) * nrm[:, 0] < -0.35)
    zip_ = torso & (np.abs(co[:, 0] - cx) < 0.0045) & (fy * (co[:, 1] - cy) > 0) & (z > belt - 0.04)
    band = torso & (z < belt + 0.012)          # тёмный пояс-манжета по низу куртки
    pan = ((side & ~armpart) | under | band).astype(float)
    # сгладить границы вставок по рёбрам сетки, в шейдере — резкий порог 0.5: ровный шов вместо пятен по вершинам
    E = np.array([e.vertices[:] for e in me.edges]); deg = np.bincount(E.ravel(), minlength=nv).astype(float); deg[deg == 0] = 1
    for _ in range(6):
        S = np.zeros(nv); np.add.at(S, E[:, 0], pan[E[:, 1]]); np.add.at(S, E[:, 1], pan[E[:, 0]]); pan = 0.5 * pan + 0.5 * S / deg
    off_j = np.where(w_arm > 0.5, 0.013, 0.017) + np.where(z > neck_cut - 0.07, 0.006, 0.0)
    J = _shell(body, arm, 'jacket', jk, off_j, _leather('jacket_leather', jacket, 0.5, panel=panel, wear=0.22, emboss=1.0), thick=0.004, panel=pan, smooth_keep=('Hand',), smooth=12, hem=belt - 0.045)
    pt = lower
    P = _shell(body, arm, 'pants', pt, np.full(nv, 0.009), _leather('pants_denim', pants, 0.8, wear=0.25), thick=0.003, smooth=6)
    bt = is_boot
    off_b = np.where(w_foot > 0.3, 0.013, 0.02)
    sole = (z < zmin + 0.028).astype(float)
    B = _shell(body, arm, 'boots', bt, off_b, _leather('boots_leather', boots, 0.62, panel=(0.04, 0.035, 0.03), wear=0.3), thick=0.004, panel=sole, smooth=4)
    G = _shell(body, arm, 'gloves', is_hand | (body_ok & (w_hand > 0.25)), np.full(nv, 0.003), _leather('gloves_leather', gloves, 0.5, wear=0.1), thick=0.002)
    # тело под одеждой скрыть
    hid = body.vertex_groups.get('covered') or body.vertex_groups.new(name='covered')
    cov = (jk | pt | bt | is_hand)
    for i in np.nonzero(cov)[0]:
        # кромка у шеи и запястья остаётся видимой — чтобы не было щели
        if z[i] > neck_cut - 0.03: continue
        hid.add([int(i)], 1.0, 'REPLACE')
    if 'under_clothes' not in body.modifiers:
        mk = body.modifiers.new('under_clothes', 'MASK'); mk.vertex_group = 'covered'; mk.invert_vertex_group = True
        want = max((k for k, m in enumerate(body.modifiers) if m.type in ('ARMATURE', 'CORRECTIVE_SMOOTH')), default=-1) + 1
        with bpy.context.temp_override(object=body):
            while body.modifiers.find('under_clothes') > want: bpy.ops.object.modifier_move_up(modifier='under_clothes')
    C, Z = _collar_zip(body, arm, J, co, nrm, jk, fy, cx, belt, neck_cut, jacket, panel)
    return dict(jacket=J, pants=P, boots=B, gloves=G, collar=C, zipper=Z)

def _collar_zip(body, arm, J, co, nrm, jk, fy, cx, belt, neck_cut, jacket, panel):
    """Воротник-стойка (кольцо по верхней кромке куртки, разрез спереди, кнопка) и молния по центру полочки."""
    mw = body.matrix_world
    ps = body.get('proxy_start', 10 ** 9)
    top = np.array([v.index for v in body.data.vertices if v.index < ps and neck_cut - 0.06 < v.co.z < neck_cut and _w(body, v, ('Neck',)) > 0.4])
    P = co[top]; c = P.mean(0)
    rx = np.abs(P[:, 0] - c[0]).max() + 0.018; ry = np.abs(P[:, 1] - c[1]).max() + 0.02
    z0 = neck_cut - 0.04; H = 0.055
    bm = bmesh.new(); rows = []; n = 48; gap = 0.16   # разрез спереди (радианы с каждой стороны)
    for k in range(3):
        row = []
        for i in range(n + 1):
            a = gap + (2 * math.pi - 2 * gap) * i / n     # 0 — перед (+fy по Y)
            sh = 1 - 0.1 * k                                   # стойка чуть сужается кверху
            x = c[0] + math.sin(a) * rx * sh; y = c[1] + fy * math.cos(a) * ry * sh
            row.append(bm.verts.new((x, y, z0 + H * k / 2 - 0.012 * math.cos(a) * (k == 0))))
        rows.append(row)
    for k in range(2):
        for i in range(n): bm.faces.new((rows[k][i], rows[k][i + 1], rows[k + 1][i + 1], rows[k + 1][i]))
    me = bpy.data.meshes.new('collar'); bm.to_mesh(me); bm.free()
    col = bpy.data.objects.new('collar', me); bpy.context.scene.collection.objects.link(col); col.matrix_world = mw.copy()
    col.data.materials.append(J.data.materials[0])
    for p in me.polygons: p.use_smooth = True
    _rig_like(col, body, arm, drop=('Arm', 'Hand', 'Head'))
    s = col.modifiers.new('thick', 'SOLIDIFY'); s.thickness = 0.006; s.offset = 0
    sb = col.modifiers.new('sub', 'SUBSURF'); sb.render_levels = 2
    # молния: центральная линия полочки от подола до стойки, поверх куртки
    front = np.nonzero(jk & (fy * (co[:, 1] - c[1]) > 0) & (np.abs(co[:, 0] - cx) < 0.03))[0]
    pts = []
    for zz in np.linspace(belt - 0.035, z0 + H * 0.95, 22):
        band = front[np.abs(co[front, 2] - zz) < 0.02]
        if len(band) == 0: continue
        yy = co[band, 1].max() if fy > 0 else co[band, 1].min()
        pts.append((cx, yy + fy * 0.024, zz))
    zm = bpy.data.materials.new('zipper'); zm.use_nodes = True; zb = zm.node_tree.nodes['Principled BSDF']
    zb.inputs['Base Color'].default_value = (0.35, 0.3, 0.22, 1); zb.inputs['Metallic'].default_value = 1.0; zb.inputs['Roughness'].default_value = 0.35
    cu = bpy.data.curves.new('zipper', 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.0035; cu.bevel_resolution = 2
    sp = cu.splines.new('POLY'); sp.points.add(len(pts) - 1)
    for q, p_ in zip(sp.points, pts): q.co = (*p_, 1)
    zo = bpy.data.objects.new('zipper_c', cu); bpy.context.scene.collection.objects.link(zo); zo.matrix_world = mw.copy()
    bpy.context.view_layer.objects.active = zo
    with bpy.context.temp_override(object=zo, active_object=zo, selected_objects=[zo], selected_editable_objects=[zo]):
        bpy.ops.object.convert(target='MESH')
    zo = bpy.context.view_layer.objects.active; zo.name = 'zipper'; zo.data.materials.clear(); zo.data.materials.append(zm)
    _rig_like(zo, body, arm, drop=('Arm', 'Hand', 'Head'))
    # кнопка стойки
    bpy.ops.mesh.primitive_cylinder_add(radius=0.008, depth=0.004, vertices=20)
    bt = bpy.context.object; bt.name = 'collar_snap'
    a = 0.55; bt.location = mw @ Vector((c[0] + math.sin(a) * rx, c[1] + fy * math.cos(a) * ry + fy * 0.004, z0 + H * 0.55))
    bt.rotation_euler = (math.radians(90), 0, 0); bt.data.materials.append(zm)
    bpy.ops.object.transform_apply(location=True, rotation=True)
    _rig_like(bt, body, arm, drop=('Arm', 'Hand', 'Head'))
    return col, zo
