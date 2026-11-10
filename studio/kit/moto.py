# Мотоцикл-скрамблер: процедурная модель с настоящими осями (руль, колёса, подножка, маятник).
# Размеры — дорожный скрамблер: колёса 19/17 дюймов, база 1.45 м, длина около 2.15 м, седло 0.84 м.
# Оси: X — вперёд, Y — влево (с точки зрения седока), Z — вверх, земля z=0, задняя ось x=0.
# Борта не зеркалятся: слева цепь, звезда, коричневая сумка и подножка; справа один глушитель и оливковая канистра.
#   bk = build(name='bike')   -> dict: root, steer, wheel_f, wheel_r, stand, lamp_tail, lamp_head, parts
#   pose(bk, steer_deg=0, roll_f=0, roll_r=0, stand_deg=0, brake=False, lights=False)
import math
import bpy, bmesh
from mathutils import Vector, Matrix

WB = 1.45            # колёсная база
RF, RR = 0.345, 0.32  # внешние радиусы шин: 19" спереди, 17" сзади
HEAD = Vector((1.16, 0, 1.0))        # рулевая колонка (верх)
RAKE = math.radians(26)              # наклон вилки

def _mat(name, col, rough=0.5, metal=0.0, coat=0.0, emit=None, es=0.0, trans=0.0, ior=1.45, wear=None):
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; N, L = m.node_tree.nodes, m.node_tree.links
    p = N['Principled BSDF']
    p.inputs['Base Color'].default_value = (*col, 1); p.inputs['Roughness'].default_value = rough; p.inputs['Metallic'].default_value = metal
    if coat: p.inputs['Coat Weight'].default_value = coat; p.inputs['Coat Roughness'].default_value = 0.2
    if trans: p.inputs['Transmission Weight'].default_value = trans; p.inputs['IOR'].default_value = ior
    if emit: p.inputs['Emission Color'].default_value = (*emit, 1); p.inputs['Emission Strength'].default_value = es
    if wear:   # износ: шум в объекте открывает подложку (сколы краски, потёртость кожи), там же матовее
        under, scale, amount = wear
        tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = scale
        nz.inputs['Detail'].default_value = 8; nz.inputs['Roughness'].default_value = 0.65
        L.new(tc.outputs['Object'], nz.inputs['Vector'])
        r = N.new('ShaderNodeValToRGB'); r.color_ramp.elements[0].position = 1 - amount; r.color_ramp.elements[1].position = 1 - amount + 0.04
        L.new(nz.outputs['Fac'], r.inputs['Fac'])
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'
        L.new(r.outputs['Color'], mx.inputs[0]); mx.inputs[6].default_value = (*col, 1); mx.inputs[7].default_value = (*under, 1)
        L.new(mx.outputs[2], p.inputs['Base Color'])
        rr = N.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = rough; rr.inputs['To Max'].default_value = min(1, rough + 0.3)
        L.new(r.outputs['Color'], rr.inputs['Value']); L.new(rr.outputs['Result'], p.inputs['Roughness'])
        # мелкая неровность поверхности
        bm = N.new('ShaderNodeBump'); bm.inputs['Strength'].default_value = 0.08; nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = scale * 6
        L.new(tc.outputs['Object'], nz2.inputs['Vector']); L.new(nz2.outputs['Fac'], bm.inputs['Height']); L.new(bm.outputs['Normal'], p.inputs['Normal'])
    return m

def materials():
    return dict(
        tank=_mat('moto_tank', (0.045, 0.105, 0.13), 0.38, coat=0.35, wear=((0.42, 0.36, 0.28), 9, 0.10)),
        cream=_mat('moto_cream', (0.52, 0.47, 0.38), 0.42, coat=0.2, wear=((0.16, 0.12, 0.09), 11, 0.12)),
        frame=_mat('moto_frame', (0.018, 0.018, 0.02), 0.42, coat=0.1, wear=((0.12, 0.11, 0.1), 14, 0.06)),
        chrome=_mat('moto_chrome', (0.62, 0.6, 0.57), 0.22, metal=1.0),
        alu=_mat('moto_alu', (0.42, 0.41, 0.4), 0.38, metal=1.0),
        exhaust=_mat('moto_exhaust', (0.38, 0.3, 0.22), 0.4, metal=1.0, wear=((0.2, 0.12, 0.07), 7, 0.25)),
        rubber=_mat('moto_rubber', (0.02, 0.019, 0.018), 0.82),
        seat=_mat('moto_seat', (0.045, 0.03, 0.022), 0.62, wear=((0.09, 0.07, 0.05), 16, 0.1)),
        leather=_mat('moto_bag', (0.16, 0.075, 0.035), 0.58, wear=((0.3, 0.2, 0.12), 10, 0.18)),
        strap=_mat('moto_strap', (0.08, 0.045, 0.025), 0.65),
        olive=_mat('moto_olive', (0.12, 0.13, 0.05), 0.55, wear=((0.2, 0.18, 0.14), 12, 0.1)),
        tape=_mat('moto_bluetape', (0.08, 0.2, 0.42), 0.7),
        glass=_mat('moto_glass', (0.9, 0.92, 0.94), 0.03, trans=1.0, ior=1.5),
        lens=_mat('moto_headlens', (0.85, 0.83, 0.78), 0.06, coat=1.0, emit=(1.0, 0.92, 0.78), es=0.0),
        tail=_mat('moto_taillens', (0.35, 0.01, 0.008), 0.15, coat=1.0, emit=(1.0, 0.04, 0.02), es=0.0),
        mirror=_mat('moto_mirror', (0.9, 0.9, 0.9), 0.02, metal=1.0),
        disc=_mat('moto_disc', (0.5, 0.48, 0.46), 0.3, metal=1.0, wear=((0.3, 0.2, 0.12), 20, 0.3)),
        chain=_mat('moto_chain', (0.16, 0.12, 0.08), 0.5, metal=0.8),
    )

# ---------- примитивы ----------
_ROOT = [None]
def _link(o, parent=None):
    bpy.context.scene.collection.objects.link(o) if o.name not in bpy.context.scene.collection.objects else None
    parent = parent or _ROOT[0]
    if parent and parent is not o: o.parent = parent
    return o

def _mesh_obj(name, bm, mat, parent, smooth=True):
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = smooth
    o = bpy.data.objects.new(name, me); o.data.materials.append(mat); return _link(o, parent)

def _frame(z_axis, origin):
    z = Vector(z_axis).normalized(); x = Vector((0, 0, 1)).cross(z) if abs(z.z) < 0.99 else Vector((1, 0, 0))
    x.normalize(); y = z.cross(x)
    M = Matrix((x, y, z)).transposed().to_4x4(); M.translation = Vector(origin); return M

def tube(name, p0, p1, r, mat, parent=None, seg=16, caps=True):
    p0, p1 = Vector(p0), Vector(p1); d = p1 - p0
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=caps, segments=seg, radius1=r, radius2=r, depth=d.length)
    bmesh.ops.transform(bm, matrix=_frame(d, (p0 + p1) / 2), verts=bm.verts)
    return _mesh_obj(name, bm, mat, parent)

def path_tube(name, pts, r, mat, parent=None, res=6, closed=False):
    """Гнутая труба по точкам (сглаженный сплайн): рама, дуги багажника, выпуск."""
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = r; cu.bevel_resolution = 3
    cu.use_fill_caps = True
    sp = cu.splines.new('NURBS'); sp.points.add(len(pts) - 1); sp.use_endpoint_u = not closed; sp.use_cyclic_u = closed
    sp.order_u = 3; sp.resolution_u = res
    for p, q in zip(sp.points, pts): p.co = (*q, 1)
    o = bpy.data.objects.new(name, cu); o.data.materials.append(mat); return _link(o, parent)

def box(name, c, s, mat, parent=None, bevel=0.01, seg=3, rot=None):
    bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(s), verts=bm.verts)
    if rot: bmesh.ops.rotate(bm, cent=(0, 0, 0), matrix=Matrix.Rotation(rot[1], 3, rot[0]), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    o = _mesh_obj(name, bm, mat, parent, smooth=False)
    if bevel:
        b = o.modifiers.new('bevel', 'BEVEL'); b.width = bevel; b.segments = seg; b.limit_method = 'ANGLE'
        o.data.polygons.foreach_set('use_smooth', [True] * len(o.data.polygons))
        try: o.data.set_sharp_from_angle(angle=math.radians(40))
        except Exception: pass
    return o

def blob(name, c, s, mat, parent=None, sub=2, seg=24):
    """Обтекаемая форма из сферы (бак, корпус фары, кожух)."""
    bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=seg // 2, radius=1.0)
    bmesh.ops.scale(bm, vec=Vector(s), verts=bm.verts); bmesh.ops.translate(bm, vec=Vector(c), verts=bm.verts)
    return _mesh_obj(name, bm, mat, parent)

def disc(name, c, axis, r, depth, mat, parent=None, seg=32, r2=None):
    bm = bmesh.new(); bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r if r2 is None else r2, depth=depth)
    bmesh.ops.transform(bm, matrix=_frame(axis, c), verts=bm.verts)
    return _mesh_obj(name, bm, mat, parent)

def torus(name, c, axis, R, r, mat, parent=None, seg=64, rseg=12):
    bm = bmesh.new()
    verts = []
    for i in range(seg):
        a = 2 * math.pi * i / seg; ring = []
        for j in range(rseg):
            b = 2 * math.pi * j / rseg
            ring.append(bm.verts.new(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a), r * math.sin(b))))
        verts.append(ring)
    for i in range(seg):
        for j in range(rseg):
            bm.faces.new((verts[i][j], verts[(i + 1) % seg][j], verts[(i + 1) % seg][(j + 1) % rseg], verts[i][(j + 1) % rseg]))
    bmesh.ops.transform(bm, matrix=_frame(axis, c), verts=bm.verts)
    return _mesh_obj(name, bm, mat, parent)

def empty(name, loc, parent):
    o = bpy.data.objects.new(name, None); o.empty_display_size = 0.1; o.location = loc; return _link(o, parent)

# ---------- узлы ----------
def wheel(name, R, M, parent, rim_inch, disc_side=0, sprocket=False):
    """Колесо со спицами и грунтовой шиной. Ось вращения — Y пустышки (крутить rotation_euler.y)."""
    hub = empty(name, (0, 0, 0), parent)
    tire_r = 0.062; RT = R - tire_r
    torus(name + '_tire', (0, 0, 0), (0, 1, 0), RT, tire_r, M['rubber'], hub, seg=72, rseg=14).scale = (1, 1, 1)
    # шашки протектора: блоки по кругу в два ряда, вразбежку
    n = 34
    for i in range(n):
        a = 2 * math.pi * i / n
        for row, dy in ((0, 0.032), (1, -0.032)):
            aa = a + (math.pi / n if row else 0)
            c = Vector((math.cos(aa) * (R - 0.004), dy, math.sin(aa) * (R - 0.004)))
            b = box(f'{name}_knob{i}_{row}', (0, 0, 0), (0.034, 0.04, 0.018), M['rubber'], hub, bevel=0.004, seg=2)
            b.matrix_basis = Matrix.Translation(c) @ Matrix.Rotation(-aa + math.pi / 2, 4, 'Y')
    rim_r = rim_inch * 0.0254 / 2
    torus(name + '_rim', (0, 0, 0), (0, 1, 0), rim_r, 0.012, M['alu'], hub, seg=64, rseg=8)
    disc(name + '_hub', (0, 0, 0), (0, 1, 0), 0.055, 0.12, M['alu'], hub, seg=24)
    for i in range(36):   # спицы: от фланцев ступицы к ободу, крест-накрест
        side = 1 if i % 2 else -1; a = 2 * math.pi * i / 36
        p0 = Vector((math.cos(a + 0.35 * side) * 0.045, side * 0.045, math.sin(a + 0.35 * side) * 0.045))
        p1 = Vector((math.cos(a) * (rim_r - 0.008), side * 0.01, math.sin(a) * (rim_r - 0.008)))
        tube(f'{name}_spoke{i}', p0, p1, 0.0022, M['chrome'], hub, seg=6, caps=False)
    if disc_side:
        d = disc(name + '_disc', (0, disc_side * 0.075, 0), (0, 1, 0), 0.14, 0.005, M['disc'], hub, seg=48)
    if sprocket:
        disc(name + '_sprocket', (0, 0.085, 0), (0, 1, 0), 0.105, 0.006, M['chain'], hub, seg=40)
    return hub

def build(name='bike'):
    M = materials(); _ROOT[0] = None; root = empty(name, (0, 0, 0), None); _ROOT[0] = root; parts = []
    yl, yr = 1, -1   # лево / право седока
    # --- колёса ---
    wr = wheel(name + '_wr', RR, M, root, 17, disc_side=0, sprocket=True); wr.location = (0, 0, RR)
    steer = empty(name + '_steer', HEAD, root)          # рулевая ось: вращение вокруг локальной Z наклонённой колонки
    steer.rotation_euler = (0, -RAKE, 0)
    # вилка в системе колонки: ось колеса ниже по наклонной оси + вынос
    axle_local = Matrix.Rotation(RAKE, 3, 'Y') @ (Vector((WB, 0, RF)) - HEAD)
    wf = wheel(name + '_wf', RF, M, steer, 19, disc_side=yl); wf.location = axle_local
    for s in (yl, yr):
        top = Vector((0.0, s * 0.105, 0.02)); bot = axle_local + Vector((0, s * 0.105, 0.04))
        mid = top.lerp(bot, 0.45)
        tube(f'{name}_stanchion{s}', top, mid, 0.022, M['chrome'], steer)
        tube(f'{name}_slider{s}', mid, bot, 0.03, M['frame'], steer)
        tube(f'{name}_gaiter{s}', mid + (bot - mid) * 0.02, mid + (bot - mid) * 0.3, 0.034, M['rubber'], steer, seg=20)
    box(name + '_ytop', (0, 0, 0.02), (0.07, 0.27, 0.03), M['alu'], steer, bevel=0.008)
    box(name + '_ybot', (0, 0, -0.17), (0.07, 0.27, 0.035), M['alu'], steer, bevel=0.008)
    if True:   # кронштейн суппорта слева
        box(name + '_caliper', axle_local + Vector((0.07, yl * 0.085, 0.08)), (0.06, 0.03, 0.09), M['alu'], steer, bevel=0.01)
    # передний крыло (кремовое, короткое, высоко над шиной) — в системе колонки, повторяет колесо
    _fender(name + '_ffender', axle_local, RF + 0.035, 0.13, (-30, 120), M['cream'], steer)
    # фара, стекло, руль, зеркала (в системе колонки, чтобы поворачивались с рулём)
    lamp_c = Vector((0.16, 0, -0.06))
    blob(name + '_lampbody', lamp_c, (0.085, 0.095, 0.095), M['chrome'], steer)
    lamp = disc(name + '_lamplens', lamp_c + Vector((0.075, 0, 0)), (1, 0, 0), 0.082, 0.012, M['lens'], steer, seg=40)
    torus(name + '_lampring', lamp_c + Vector((0.078, 0, 0)), (1, 0, 0), 0.084, 0.007, M['chrome'], steer, seg=40, rseg=8)
    ws = _screen(name + '_screen', Vector((0.2, 0, 0.03)), M['glass'], steer)
    for s in (yl, yr):   # уши фары: от траверс к корпусу
        tube(f'{name}_lampear{s}', Vector((0.0, s * 0.105, -0.12)), lamp_c + Vector((0, s * 0.09, 0)), 0.008, M['frame'], steer)
    bar = [Vector((-0.06, s * 0.36, 0.17)) for s in (yl,)] + [Vector((0.0, 0.18, 0.12)), Vector((0.0, -0.18, 0.12)), Vector((-0.06, -0.36, 0.17))]
    path_tube(name + '_bar', bar, 0.011, M['frame'], steer)
    for s in (yl, yr):
        g0 = Vector((-0.04, s * 0.27, 0.15)); g1 = Vector((-0.07, s * 0.40, 0.18))
        tube(f'{name}_grip{s}', g0, g1, 0.017, M['rubber'], steer, seg=16)
        tube(f'{name}_lever{s}', g0 + Vector((0.02, 0, 0.0)), g1 + Vector((0.07, 0, -0.01)), 0.005, M['alu'], steer, seg=6)
        m0 = Vector((-0.02, s * 0.25, 0.16)); m1 = Vector((-0.07, s * 0.33, 0.38))
        tube(f'{name}_mstem{s}', m0, m1, 0.005, M['frame'], steer, seg=8)
        disc(f'{name}_mirror{s}', m1 + Vector((0, s * 0.02, 0.025)), (1, 0, 0), 0.045, 0.012, M['frame'], steer)
        disc(f'{name}_mglass{s}', m1 + Vector((-0.008, s * 0.02, 0.025)), (1, 0, 0), 0.04, 0.004, M['mirror'], steer)
    # --- рама ---
    F = M['frame']
    head_bot = HEAD + Vector((math.sin(RAKE) * 0.2, 0, -math.cos(RAKE) * 0.2))
    tube(name + '_headtube', HEAD + Vector((0, 0, 0.02)), head_bot, 0.03, F)
    for s in (yl, yr):
        path_tube(f'{name}_top{s}', [HEAD + Vector((-0.04, s * 0.02, -0.03)), Vector((0.75, s * 0.05, 0.88)), Vector((0.42, s * 0.09, 0.84)), Vector((0.05, s * 0.1, 0.78)), Vector((-0.12, s * 0.1, 0.8))], 0.014, F, root)
        path_tube(f'{name}_down{s}', [head_bot, Vector((1.05, s * 0.07, 0.55)), Vector((0.98, s * 0.11, 0.24)), Vector((0.75, s * 0.12, 0.17)), Vector((0.5, s * 0.12, 0.22)), Vector((0.42, s * 0.12, 0.42)), Vector((0.42, s * 0.1, 0.84))], 0.015, F, root)
        path_tube(f'{name}_sub{s}', [Vector((0.44, s * 0.11, 0.5)), Vector((0.2, s * 0.13, 0.62)), Vector((0.02, s * 0.12, 0.78))], 0.012, F, root)
        # багажник за седлом
        path_tube(f'{name}_rack{s}', [Vector((0.08, s * 0.12, 0.86)), Vector((-0.1, s * 0.12, 0.88)), Vector((-0.2, s * 0.08, 0.88)), Vector((-0.22, 0, 0.88))], 0.009, F, root)
        # маятник и амортизатор
        tube(f'{name}_swing{s}', (0.44, s * 0.12, 0.42), (0, s * 0.12, RR), 0.02, F)
        sh0, sh1 = Vector((0.02, s * 0.14, RR + 0.04)), Vector((0.12, s * 0.135, 0.77))
        tube(f'{name}_shockbody{s}', sh0, sh0.lerp(sh1, 0.45), 0.018, M['alu'])
        tube(f'{name}_shockrod{s}', sh0.lerp(sh1, 0.4), sh1, 0.008, M['chrome'])
        for k in range(9):
            c = sh0.lerp(sh1, 0.45 + 0.055 * k)
            torus(f'{name}_spring{s}_{k}', c, sh1 - sh0, 0.026, 0.005, M['chrome'], root, seg=20, rseg=6)
        # подножки
        tube(f'{name}_peg{s}', (0.5, s * 0.14, 0.33), (0.5, s * 0.26, 0.33), 0.014, M['rubber'], root)
    # поперечины багажника
    for x in (-0.05, -0.16):
        tube(f'{name}_rackx{x}', (x, 0.12, 0.88), (x, -0.12, 0.88), 0.008, F)
    # --- двигатель: оппозитный? нет — рядный твин воздушного охлаждения, цилиндры чуть вперёд ---
    E = M['alu']
    box(name + '_crank', (0.7, 0, 0.37), (0.44, 0.27, 0.24), E, root, bevel=0.06, seg=4)
    box(name + '_gearbox', (0.47, 0, 0.4), (0.2, 0.21, 0.22), E, root, bevel=0.05, seg=4)
    for s in (yl, yr):
        disc(f'{name}_cover{s}', (0.7, s * 0.14, 0.36), (0, 1, 0), 0.1, 0.03, M['chrome'], root, seg=32)
        disc(f'{name}_cover2{s}', (0.5, s * 0.115, 0.42), (0, 1, 0), 0.07, 0.025, E, root, seg=32)
    base = Vector((0.73, 0, 0.49)); top = Vector((0.8, 0, 0.8))
    for k in range(11):   # общий блок цилиндров твина: квадратные рёбра охлаждения во всю ширину
        c = base.lerp(top, k / 10); w = 0.2 if k < 10 else 0.17
        box(f'{name}_fin{k}', c, (0.17 if k < 10 else 0.15, 0.25, 0.012), E, root, bevel=0.004, seg=2, rot=('Y', -0.22))
    box(name + '_barrel', base.lerp(top, 0.5), (0.12, 0.2, 0.32), M['frame'], root, bevel=0.01, rot=('Y', -0.22))
    box(name + '_headcap', top + Vector((0.012, 0, 0.04)), (0.15, 0.24, 0.07), E, root, bevel=0.025, seg=3, rot=('Y', -0.22))
    for c_y in (0.11, -0.11):
        disc(f'{name}_valvecover{c_y}', top + Vector((0.01, c_y * 1.12, 0.03)), (0, 1, 0), 0.04, 0.02, M['chrome'], root, seg=20)
    box(name + '_carb', (0.6, 0, 0.67), (0.1, 0.16, 0.08), E, root, bevel=0.02)
    # выпуск справа: коллекторы от головок вниз и назад, один глушитель
    for c_y in (0.055, -0.055):
        path_tube(f'{name}_header{c_y}', [Vector((0.84, c_y, 0.66)), Vector((0.97, c_y * 0.6 - 0.04, 0.48)), Vector((0.9, -0.12, 0.2)), Vector((0.6, -0.17, 0.2)), Vector((0.38, -0.2, 0.3))], 0.02, M['exhaust'], root)
    tube(name + '_muffler', (0.38, -0.2, 0.32), (-0.08, -0.2, 0.44), 0.05, M['exhaust'], root, seg=24)
    disc(name + '_mufcap', (-0.09, -0.2, 0.443), (-0.46, 0, 0.12), 0.048, 0.02, M['chrome'], root)
    tube(name + '_heatshield', (0.3, -0.255, 0.35), (0.02, -0.255, 0.42), 0.02, M['chrome'], root, seg=12)
    # цепь слева: верхняя и нижняя ветви
    tube(name + '_chain_up', (0.48, 0.09, 0.42), (0, 0.09, RR + 0.1), 0.007, M['chain'], root, seg=6)
    tube(name + '_chain_lo', (0.48, 0.09, 0.32), (0, 0.09, RR - 0.1), 0.007, M['chain'], root, seg=6)
    disc(name + '_frontsprocket', (0.5, 0.09, 0.37), (0, 1, 0), 0.045, 0.008, M['chain'], root)
    # под седлом: воздушный фильтр и боковые крышки (заполняют треугольник рамы)
    box(name + '_airbox', (0.3, 0, 0.66), (0.22, 0.2, 0.2), F, root, bevel=0.03, seg=3)
    for s in (yl, yr):
        box(f'{name}_sidecover{s}', (0.3, s * 0.11, 0.66), (0.2, 0.012, 0.15), M['frame'], root, bevel=0.02, seg=3)
    # бак, коленные панели, крышка горловины
    tank = blob(name + '_tank', (0.86, 0, 0.94), (0.29, 0.15, 0.11), M['tank'], root, seg=40)
    _shape_tank(tank)
    for s in (yl, yr):
        p = blob(f'{name}_knee{s}', (0.84, s * 0.128, 0.93), (0.13, 0.03, 0.065), M['cream'], root, seg=24)
    disc(name + '_fillcap', (0.95, 0, 1.045), (0, 0, 1), 0.035, 0.015, M['chrome'], root)
    # седло: ребристое
    seat = box(name + '_seat', (0.36, 0, 0.88), (0.6, 0.27, 0.07), M['seat'], root, bevel=0.03, seg=4)
    for k in range(9):
        tube(f'{name}_seatrib{k}', (0.12 + k * 0.058, 0.125, 0.912), (0.12 + k * 0.058, -0.125, 0.912), 0.006, M['seat'], root, seg=8)
    # заднее крыло и фонарь
    _fender(name + '_rfender', Vector((0, 0, RR)), RR + 0.04, 0.12, (60, 160), M['cream'], root)
    tl = box(name + '_taillamp', (-0.25, 0, 0.8), (0.03, 0.09, 0.045), M['tail'], root, bevel=0.006)
    box(name + '_tailhouse', (-0.235, 0, 0.8), (0.03, 0.1, 0.055), F, root, bevel=0.006)
    # левая сумка (коричневая кожа, два ремня) — только слева
    bag = box(name + '_bag', (0.05, 0.215, 0.7), (0.3, 0.11, 0.21), M['leather'], root, bevel=0.025, seg=4)
    box(name + '_bagflap', (0.05, 0.27, 0.77), (0.3, 0.012, 0.08), M['leather'], root, bevel=0.006)
    for dx in (-0.07, 0.11):
        box(f'{name}_bagstrap{dx}', (0.05 + dx, 0.276, 0.73), (0.03, 0.006, 0.17), M['strap'], root, bevel=0.002)
        box(f'{name}_buckle{dx}', (0.05 + dx, 0.282, 0.71), (0.038, 0.006, 0.03), M['chrome'], root, bevel=0.002)
    # правая канистра (оливковая, 5 л) с зазором над выпуском, синяя лента на крышке
    can = box(name + '_can', (-0.08, -0.205, 0.78), (0.2, 0.09, 0.25), M['olive'], root, bevel=0.015, seg=3)
    tube(name + '_canneck', (-0.01, -0.205, 0.905), (-0.01, -0.205, 0.94), 0.02, M['olive'], root)
    tube(name + '_cantape', (-0.01, -0.205, 0.925), (-0.01, -0.205, 0.945), 0.023, M['tape'], root)
    box(name + '_canstrap', (-0.08, -0.205, 0.8), (0.21, 0.1, 0.03), M['strap'], root, bevel=0.003)
    box(name + '_canbracket', (-0.08, -0.155, 0.66), (0.22, 0.03, 0.02), F, root, bevel=0.003)
    tube(name + '_canstay', (-0.18, -0.13, 0.88), (-0.18, -0.16, 0.66), 0.007, F, root)
    tube(name + '_canstay2', (0.02, -0.13, 0.82), (0.02, -0.16, 0.66), 0.007, F, root)
    # подножка слева: шарнир у маятника, вращать rotation_euler.x
    stand = empty(name + '_stand', (0.42, 0.13, 0.3), root)
    tube(name + '_standleg', (0, 0, 0), (-0.05, 0.0, -0.32), 0.012, F, stand)
    box(name + '_standfoot', (-0.05, 0, -0.32), (0.06, 0.03, 0.01), F, stand, bevel=0.003)
    # номерная рамка / кронштейн
    box(name + '_plate', (-0.29, 0, 0.68), (0.008, 0.12, 0.07), M['frame'], root, bevel=0.004, rot=('Y', -0.3))
    _ROOT[0] = None
    return dict(root=root, steer=steer, wheel_f=wf, wheel_r=wr, stand=stand, lamp_head=lamp, lamp_tail=tl, M=M)

def _fender(name, center, R, width, deg, mat, parent):
    """Крыло: тонкая изогнутая полоса над колесом (дуга в плоскости XZ)."""
    bm = bmesh.new(); a0, a1 = deg; n = 24; rows = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        row = []
        for t in (-1, -0.7, 0, 0.7, 1):
            drop = 0.025 * abs(t) ** 2
            rr = R - drop
            row.append(bm.verts.new((center.x + math.cos(a) * rr, t * width / 2, center.z + math.sin(a) * rr)))
        rows.append(row)
    for i in range(n):
        for j in range(4):
            bm.faces.new((rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]))
    o = _mesh_obj(name, bm, mat, parent)
    s = o.modifiers.new('thick', 'SOLIDIFY'); s.thickness = 0.006
    sb = o.modifiers.new('sub', 'SUBSURF'); sb.levels = 1; sb.render_levels = 2
    return o

def _screen(name, c, mat, parent):
    bm = bmesh.new(); rows = []
    for i in range(7):
        z = i / 6 * 0.2; row = []
        for j in range(7):
            y = (j / 6 - 0.5) * 0.24 * (1 - 0.25 * i / 6)
            row.append(bm.verts.new((c.x - 0.45 * z - 0.6 * y * y, c.y + y, c.z + z * 0.9)))
        rows.append(row)
    for i in range(6):
        for j in range(6): bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
    o = _mesh_obj(name, bm, mat, parent); s = o.modifiers.new('thick', 'SOLIDIFY'); s.thickness = 0.004
    return o

def _shape_tank(o):
    """Бак скрамблера: выше и шире спереди, к седлу опускается и сужается; снизу вогнут под раму."""
    for v in o.data.vertices:
        x, y, z = v.co.x - 0.86, v.co.y, v.co.z - 0.94
        u = x / 0.29                      # -1 сзади .. 1 спереди
        k = 0.78 + 0.22 * (u + 1) / 2     # ширина и высота растут вперёд
        v.co.y = y * k
        v.co.z = 0.94 + z * (0.75 + 0.3 * (u + 1) / 2) + 0.03 * (u + 1) / 2 - (0.03 if z < 0 else 0)
        if z < -0.04: v.co.z = max(v.co.z, 0.86)

def pose(bk, steer_deg=0.0, dist_f=0.0, dist_r=None, stand_deg=0.0, brake=False, lights=False):
    """Руль, вращение колёс по пройденному пути (м), подножка (0 — убрана, 1 — опущена), стоп и фара."""
    bk['steer'].rotation_euler = (0, -RAKE, 0)
    bk['steer'].matrix_basis = Matrix.Translation(HEAD) @ Matrix.Rotation(-RAKE, 4, 'Y') @ Matrix.Rotation(math.radians(steer_deg), 4, 'Z')
    dist_r = dist_f if dist_r is None else dist_r
    bk['wheel_f'].rotation_euler.y = dist_f / RF
    bk['wheel_r'].rotation_euler.y = dist_r / RR
    # подножка: убрана — вдоль маятника назад и вверх; опущена — в землю
    bk['stand'].rotation_euler = (math.radians(-12 * stand_deg), math.radians(-90 * (1 - stand_deg)), 0)
    tail = bk['M']['tail'].node_tree.nodes['Principled BSDF']; tail.inputs['Emission Strength'].default_value = (25.0 if brake else (6.0 if lights else 0.0))
    head = bk['M']['lens'].node_tree.nodes['Principled BSDF']; head.inputs['Emission Strength'].default_value = 12.0 if lights else 0.0
