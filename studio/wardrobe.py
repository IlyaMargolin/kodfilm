"""Костюмерная: одежда строится по телу из studio/human.py и садится на тот же скелет.
robe(body)  — балахон/ряса: оболочка торса и рукавов (расширяются к запястью) + юбка-конус до щиколоток + капюшон.
cloak(body) — плащ с капюшоном поверх любой одежды.
Веса юбки и капюшона переносятся с тела (Data Transfer) и смешиваются с тазом/головой, чтобы ткань не зажимало между ног."""
import bpy, bmesh, math
from mathutils import Vector

def fabric(name='wool', color=(0.09, 0.075, 0.06), rough=0.92, sheen=0.3, scale=380):
    m = bpy.data.materials.new(name); m.use_nodes = True; N = m.node_tree.nodes; L = m.node_tree.links
    b = N['Principled BSDF']; b.inputs['Base Color'].default_value = (*color, 1); b.inputs['Roughness'].default_value = rough
    if 'Sheen Weight' in b.inputs: b.inputs['Sheen Weight'].default_value = sheen; b.inputs['Sheen Roughness'].default_value = 0.4
    tc = N.new('ShaderNodeTexCoord')
    wv = N.new('ShaderNodeTexWave'); wv.inputs['Scale'].default_value = scale; wv.inputs['Distortion'].default_value = 2; wv.inputs['Detail'].default_value = 3
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 7; nz.inputs['Detail'].default_value = 6
    L.new(tc.outputs['Object'], wv.inputs['Vector']); L.new(tc.outputs['Object'], nz.inputs['Vector'])
    mx = N.new('ShaderNodeMath'); mx.operation = 'MULTIPLY_ADD'; mx.inputs[1].default_value = 0.3
    L.new(wv.outputs['Fac'], mx.inputs[0]); L.new(nz.outputs['Fac'], mx.inputs[2])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.6; bp.inputs['Distance'].default_value = 0.003
    L.new(mx.outputs[0], bp.inputs['Height']); L.new(bp.outputs['Normal'], b.inputs['Normal'])
    # потёртость: светлее на выступах
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (color[0] * 0.55, color[1] * 0.55, color[2] * 0.55, 1)
    cr.color_ramp.elements[1].color = (color[0] * 1.8, color[1] * 1.6, color[2] * 1.4, 1)
    L.new(nz.outputs['Fac'], cr.inputs['Fac']); L.new(cr.outputs['Color'], b.inputs['Base Color'])
    return m

def _w(body, v, names):
    s = 0.0
    for g in v.groups:
        n = body.vertex_groups[g.group].name
        if any(k in n for k in names): s += g.weight
    return s

def _rig_like(o, body, arm, mix=None, drop=('Arm', 'Hand', 'Shoulder')):
    """веса с тела: Data Transfer -> применить; mix={'mixamorig:Hips': 0.5} подмешивает жёсткую кость.
    drop: кости, которые не должны тянуть эту вещь (у юбки рядом висят кисти — их веса отбрасываем и нормируем)."""
    for g in body.vertex_groups:
        if g.name != 'covered': o.vertex_groups.new(name=g.name)
    dt = o.modifiers.new('wt', 'DATA_TRANSFER'); dt.object = body; dt.use_vert_data = True
    dt.data_types_verts = {'VGROUP_WEIGHTS'}; dt.vert_mapping = 'POLYINTERP_NEAREST'
    bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier='wt')
    bad = {g.index for g in o.vertex_groups if any(k in g.name for k in drop)}
    for v in o.data.vertices:
        keep = [(g.group, g.weight) for g in v.groups if g.group not in bad]
        tot = sum(w for _, w in keep)
        for gi in bad: o.vertex_groups[gi].remove([v.index])
        if tot > 1e-6:
            for gi, w in keep: o.vertex_groups[gi].add([v.index], w / tot, 'REPLACE')
    if mix:
        for vg_name, k in mix.items():
            vg = o.vertex_groups.get(vg_name) or o.vertex_groups.new(name=vg_name)
            for v in o.data.vertices:
                f = k(v.co) if callable(k) else k
                for g in v.groups: g.weight *= (1 - f)
                vg.add([v.index], f, 'ADD')
    am = o.modifiers.new('body', 'ARMATURE'); am.object = arm
    o.parent = arm; o.matrix_parent_inverse = arm.matrix_world.inverted()

def robe(body, arm, **kw):
    pp = arm.data.pose_position; arm.data.pose_position = 'REST'; bpy.context.view_layer.update()
    try: return _robe(body, arm, **kw)
    finally: arm.data.pose_position = pp; bpy.context.view_layer.update()

def _robe(body, arm, color=(0.09, 0.075, 0.06), hood=True, sleeve=0.035, length=0.08):
    J = {k: Vector(v) for k, v in body['joints'].items()}
    mat = fabric('robe', color)
    # 1) верх: копия тела без кистей, головы, ног ниже бедра; выдавливание по нормали, рукава шире к запястью
    me = body.data.copy(); top = bpy.data.objects.new('robe_top', me); bpy.context.scene.collection.objects.link(top)
    top.matrix_world = body.matrix_world
    bm = bmesh.new(); bm.from_mesh(me); bm.verts.ensure_lookup_table(); bm.normal_update()
    kill = []
    for v in bm.verts:
        bv = body.data.vertices[v.index]
        if _w(body, bv, ('Hand', 'Head', 'Neck')) > 0.5 or _w(body, bv, ('Leg', 'Foot', 'Toe')) > 0.5: kill.append(v); continue
        fore = _w(body, bv, ('ForeArm',)); armw = _w(body, bv, ('Arm',))
        off = 0.036 + sleeve * fore
        v.co += v.normal * off
    # ткань натягивается поверх рельефа, а не облегает его: сглаживание «только наружу» заполняет впадины
    # (под грудными мышцами, подмышки, позвоночник), выпуклости остаются опорами — как шерсть, лежащая на теле
    killset = set(kill); live = [v for v in bm.verts if v not in killset]
    bm.normal_update(); N0 = {v: v.normal.copy() for v in live}
    for _ in range(45):
        upd = []
        for v in live:
            nb = [e.other_vert(v) for e in v.link_edges]
            if not nb: continue
            avg = sum((o.co for o in nb), Vector()) / len(nb); d = avg - v.co
            if d.dot(N0[v]) > 0: upd.append((v, d * 0.7))
        for v, d in upd: v.co += d
    bmesh.ops.delete(bm, geom=kill, context='VERTS')
    # швы и обрезки: сшиваем совпадающие вершины, выкидываем мелкие острова (иначе сглаживание их не трогает — «соски» на ткани)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002)
    bm.verts.ensure_lookup_table(); seen = set(); small = []
    for v in bm.verts:
        if v in seen: continue
        isl = [v]; seen.add(v); st = [v]
        while st:
            x = st.pop()
            for e in x.link_edges:
                o = e.other_vert(x)
                if o not in seen: seen.add(o); isl.append(o); st.append(o)
        if len(isl) < 200: small += isl
    bmesh.ops.delete(bm, geom=small, context='VERTS')
    # полюса сетки (соски, пупок: вершина с 7+ рёбрами) после сабдива дают «точку-вмятину» — растворяем их в ткани
    poles = [v for v in bm.verts if len(v.link_edges) >= 7 and not v.is_boundary]
    if poles: bmesh.ops.dissolve_verts(bm, verts=poles); bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    print('robe top: merged/cleaned, removed', len(small), 'island verts,', len(poles), 'poles')
    bm.to_mesh(me); bm.free()
    me.materials.clear(); me.materials.append(mat)
    for g in list(top.vertex_groups): pass
    # грудь рясы ведёт позвоночник, а не плечо: иначе опущенные руки сминают ткань в «грудь» и складку под ней
    gi = {g.index: g.name for g in top.vertex_groups}
    for v in me.vertices:
        ws = {gi[g.group]: g.weight for g in v.groups}
        sp = sum(w for n, w in ws.items() if 'Spine' in n)
        if sp < 0.25: continue
        k = max(0.0, 1.0 - sp * 1.4)          # чем больше вес позвоночника, тем меньше власть плеча
        for g in v.groups:
            if any(t in gi[g.group] for t in ('Shoulder', 'Arm')) and 'ForeArm' not in gi[g.group]: g.weight *= k
        tot = sum(g.weight for g in v.groups)
        if tot > 1e-6:
            for g in v.groups: g.weight /= tot
    am = top.modifiers.new('body', 'ARMATURE'); am.object = arm
    top.parent = arm; top.matrix_parent_inverse = arm.matrix_world.inverted()
    # корректирующее сглаживание после скелета (аналог корректирующих шейпов в играх): плечо и подмышка не мнутся
    # «грудью», когда руки опущены из Т-позы — ткань сохраняет длины рёбер исходной формы
    cs = top.modifiers.new('corrective', 'CORRECTIVE_SMOOTH'); cs.rest_source = 'ORCO'; cs.smooth_type = 'LENGTH_WEIGHTED'; cs.iterations = 8; cs.factor = 0.6
    sm = top.modifiers.new('drape', 'SMOOTH'); sm.factor = 1.0; sm.iterations = 60   # ткань не повторяет анатомию (нет «груди» у рясы)
    # складки под собственным весом: вертикально вытянутый шум (как висит тяжёлая шерсть от плеч к поясу)
    tx = bpy.data.textures.new('robe_folds', 'CLOUDS'); tx.noise_scale = 0.09; tx.noise_depth = 1
    em = bpy.data.objects.new('robe_folds_space', None); bpy.context.scene.collection.objects.link(em); em.scale = (1, 1, 5); em.parent = arm; em.matrix_parent_inverse = arm.matrix_world.inverted()
    dp = top.modifiers.new('folds', 'DISPLACE'); dp.texture = tx; dp.strength = 0.007; dp.mid_level = 0.5; dp.texture_coords = 'OBJECT'; dp.texture_coords_object = em
    sol = top.modifiers.new('thick', 'SOLIDIFY'); sol.thickness = 0.008; sol.offset = 1
    sub = top.modifiers.new('sub', 'SUBSURF'); sub.levels = 1; sub.render_levels = 2
    # 2) юбка: конус от бёдер до щиколоток (складки — шум по окружности)
    hip = J['mixamorig:Hips']; lf = J['mixamorig:LeftFoot']; rf = J['mixamorig:RightFoot']
    top_z = hip.z + 0.13; bot_z = min(lf.z, rf.z) + length
    lu, ru = J['mixamorig:LeftUpLeg'], J['mixamorig:RightUpLeg']; r0 = abs(lu.x - ru.x) / 2 + 0.085
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=1, depth=1, end_fill_type='NOTHING', location=(hip.x, hip.y, (top_z + bot_z) / 2))
    sk = bpy.context.object; sk.name = 'robe_skirt'
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.subdivide(number_cuts=14); bpy.ops.object.mode_set(mode='OBJECT')
    for v in sk.data.vertices:
        t = v.co.z + 0.5                        # 0 низ, 1 верх
        a = math.atan2(v.co.y, v.co.x)
        # глубокие складки тяжёлой шерсти: крупные внизу, у пояса — частые сборки; подол неровный
        fold = (0.06 * math.sin(a * 7 + 0.4) + 0.03 * math.sin(a * 13 + 2.1) + 0.015 * math.sin(a * 29 + 0.7)) * (1 - t) ** 0.8
        gather = 0.012 * math.sin(a * 41) * t ** 2
        rad = r0 * (1.0 + 0.95 * (1 - t) ** 1.3) * (1 + fold + gather)
        v.co.x, v.co.y = math.cos(a) * rad, math.sin(a) * rad * 0.82
        v.co.z *= (top_z - bot_z)
    sk.data.materials.append(mat); bpy.ops.object.shade_smooth()
    bpy.ops.object.transform_apply(location=True, scale=True)
    hz = hip.z
    _rig_like(sk, body, arm, mix={'mixamorig:Hips': lambda co: max(0.0, min(1.0, (co.z - bot_z) / max(0.01, hz - bot_z))) * 0.35 + 0.55})
    sol2 = sk.modifiers.new('thick', 'SOLIDIFY'); sol2.thickness = 0.008
    sk.modifiers.new('sub', 'SUBSURF').render_levels = 1
    # тело под одеждой не рендерим (как в играх и студийных крауд-системах): ноги не протыкают юбку, торс — рясу
    hid = body.vertex_groups.get('covered') or body.vertex_groups.new(name='covered')
    for v in body.data.vertices:
        if _w(body, v, ('Hand', 'Head', 'Neck', 'Foot', 'Toe')) < 0.2 and (v.co.z - 0) > 0.12:
            hid.add([v.index], 1.0, 'REPLACE')
    mk = body.modifiers.new('under_clothes', 'MASK'); mk.vertex_group = 'covered'; mk.invert_vertex_group = True
    while body.modifiers.find('under_clothes') > 0: bpy.context.view_layer.objects.active = body; bpy.ops.object.modifier_move_up(modifier='under_clothes')
    # верёвочный пояс прячет шов верха и юбки
    bpy.ops.mesh.primitive_torus_add(major_radius=1, minor_radius=0.012, major_segments=96, minor_segments=12, location=(hip.x, hip.y + 0.0, top_z - 0.01))
    belt = bpy.context.object; belt.name = 'rope_belt'; belt.scale = (r0 + 0.012, (r0 + 0.012) * 0.82, 1)
    bpy.ops.object.transform_apply(scale=True, location=True)
    rope = bpy.data.materials.new('rope'); rope.use_nodes = True; rb = rope.node_tree.nodes['Principled BSDF']
    rb.inputs['Base Color'].default_value = (0.11, 0.08, 0.05, 1); rb.inputs['Roughness'].default_value = 0.95
    if 'Sheen Weight' in rb.inputs: rb.inputs['Sheen Weight'].default_value = 0.4
    # витая пенька: спиральные полосы по объекту (рельеф, а не краска)
    RN, RL = rope.node_tree.nodes, rope.node_tree.links
    rw = RN.new('ShaderNodeTexWave'); rw.wave_type = 'BANDS'; rw.bands_direction = 'DIAGONAL'; rw.inputs['Scale'].default_value = 60; rw.inputs['Distortion'].default_value = 1.5
    rtc = RN.new('ShaderNodeTexCoord'); RL.new(rtc.outputs['Object'], rw.inputs['Vector'])
    rbp = RN.new('ShaderNodeBump'); rbp.inputs['Strength'].default_value = 0.8; rbp.inputs['Distance'].default_value = 0.004
    RL.new(rw.outputs['Fac'], rbp.inputs['Height']); RL.new(rbp.outputs['Normal'], rb.inputs['Normal'])
    belt.data.materials.append(rope); bpy.ops.object.shade_smooth()
    _rig_like(belt, body, arm, mix={'mixamorig:Hips': 1.0})
    out = [top, sk, belt]
    if hood: out.append(hood_obj(body, arm, mat, J))
    return out

def hood_obj(body, arm, mat, J=None):
    J = J or {k: Vector(v) for k, v in body['joints'].items()}
    head = J['mixamorig:Head']; neck = J['mixamorig:Neck']
    c = head + Vector((0, 0.005, 0.075))
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=1, location=c)
    h = bpy.context.object; h.name = 'hood'
    bm = bmesh.new(); bm.from_mesh(h.data)
    kill = [v for v in bm.verts if v.co.y > 0.5 and v.co.z > -0.6 and abs(v.co.x) < 0.8]       # открытое лицо (вперёд = +Y)
    bmesh.ops.delete(bm, geom=kill, context='VERTS')
    for v in bm.verts:
        x, y, z = v.co
        if z < -0.2: v.co.z = z * 1.9; v.co.x *= 1.0 + 0.9 * (-z - 0.2); v.co.y *= 1.0 + 0.6 * (-z - 0.2)   # ниспадает на плечи
        if z > 0.6 and y < 0: v.co.y -= 0.25 * (z - 0.6)        # острый мыс капюшона назад
    bm.to_mesh(h.data); bm.free()
    h.scale = (0.135, 0.15, 0.15); bpy.ops.object.transform_apply(scale=True, location=False)
    h.data.materials.append(mat); bpy.ops.object.shade_smooth()
    loc = h.location.copy(); bpy.ops.object.transform_apply(location=True)
    _rig_like(h, body, arm, drop=('Hand', 'ForeArm'), mix={'mixamorig:Head': lambda co: max(0.0, min(1.0, (co.z - neck.z + 0.05) / 0.15)) * 0.9})
    s = h.modifiers.new('thick', 'SOLIDIFY'); s.thickness = 0.012; s.offset = 1
    h.modifiers.new('sub', 'SUBSURF').render_levels = 2
    return h
