"""Костюмерная: одежда строится по телу из studio/human.py и садится на тот же скелет.
robe(body)  — балахон/ряса: оболочка торса и рукавов (расширяются к запястью) + юбка-конус до щиколоток + капюшон.
cloak(body) — плащ с капюшоном поверх любой одежды.
Веса юбки и капюшона переносятся с тела (Data Transfer) и смешиваются с тазом/головой, чтобы ткань не зажимало между ног."""
import bpy, bmesh, math
from mathutils import Vector

def fabric(name='wool', color=(0.09, 0.075, 0.06), rough=0.92, sheen=0.25, scale=1.0):
    """Домотканая шерсть саржевого переплетения (как на макро-референсах): нити основы и утка ≈1.5 мм,
    диагональный рубчик саржи 2/2, пушок волокон, неровная пряжа (утолщения нити — «слабы»), потёртость.
    Всё процедурно в координатах объекта — без UV-швов тела; scale <1 — нить крупнее."""
    m = bpy.data.materials.new(name); m.use_nodes = True; N = m.node_tree.nodes; L = m.node_tree.links
    b = N['Principled BSDF']; b.inputs['Roughness'].default_value = rough
    # пушок шерсти — sheen, но тонированный цветом нити: белый sheen (по умолчанию) делает тёмную ткань серо-пыльной
    if 'Sheen Weight' in b.inputs:
        b.inputs['Sheen Weight'].default_value = sheen; b.inputs['Sheen Roughness'].default_value = 0.35
        if 'Sheen Tint' in b.inputs: b.inputs['Sheen Tint'].default_value = (*[min(1.0, c * 4) for c in color], 1)
    tc = N.new('ShaderNodeTexCoord')
    # координаты ткани: позиция в позе покоя (атрибут 'rest', см. _rest) — узор не «плывёт» по одежде при движении.
    # Нити не по плоскостям мира: плоские полосы X/Y на выпуклой груди дают концентрические кольца («соски» на ткани).
    # Основа идёт по окружности вокруг оси тела (развёртка цилиндра: u = угол·радиус), уток — по высоте.
    at = N.new('ShaderNodeAttribute'); at.attribute_type = 'GEOMETRY'; at.attribute_name = 'rest'
    P = at.outputs['Vector']; sp_ = N.new('ShaderNodeSeparateXYZ'); L.new(P, sp_.inputs[0])
    ang = N.new('ShaderNodeMath'); ang.operation = 'ARCTAN2'; L.new(sp_.outputs['X'], ang.inputs[0]); L.new(sp_.outputs['Y'], ang.inputs[1])
    uu = N.new('ShaderNodeMath'); uu.operation = 'MULTIPLY'; uu.inputs[1].default_value = 0.16; L.new(ang.outputs[0], uu.inputs[0])
    UV = N.new('ShaderNodeCombineXYZ'); L.new(uu.outputs[0], UV.inputs['X']); L.new(sp_.outputs['Z'], UV.inputs['Y'])
    UVo = UV.outputs[0]
    def wave(direction, sc_, prof='SIN'):
        w = N.new('ShaderNodeTexWave'); w.wave_type = 'BANDS'; w.bands_direction = direction; w.wave_profile = prof
        w.inputs['Scale'].default_value = sc_ * scale; w.inputs['Distortion'].default_value = 1.3; w.inputs['Detail'].default_value = 1.0
        w.inputs['Detail Scale'].default_value = 3.0
        L.new(UVo, w.inputs['Vector']); return w.outputs['Fac']
    def math(op, a, b_=None, v=None):
        n_ = N.new('ShaderNodeMath'); n_.operation = op
        for k, x in enumerate((a, b_)):
            if x is None: continue
            if isinstance(x, (int, float)): n_.inputs[k].default_value = x
            else: L.new(x, n_.inputs[k])
        if v is not None: n_.inputs[2].default_value = v
        return n_.outputs[0]
    twill = wave('DIAGONAL', 470)                         # рубчик саржи по диагонали
    weft = wave('Y', 660)                                 # уток — поперёк (по высоте одежды: v = z)
    warp = wave('X', 660)                                 # основа — вдоль (u — по окружности тела)
    fib = N.new('ShaderNodeTexNoise'); fib.inputs['Scale'].default_value = 5200 * scale; fib.inputs['Detail'].default_value = 2
    L.new(P, fib.inputs['Vector'])
    # неровная пряжа: шум, вытянутый вдоль нити
    mp = N.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = (420 * scale, 26 * scale, 1.0); L.new(UVo, mp.inputs['Vector'])
    slub = N.new('ShaderNodeTexNoise'); slub.inputs['Scale'].default_value = 1.0; slub.inputs['Detail'].default_value = 3; L.new(mp.outputs[0], slub.inputs['Vector'])
    big = N.new('ShaderNodeTexNoise'); big.inputs['Scale'].default_value = 7; big.inputs['Detail'].default_value = 6; L.new(P, big.inputs['Vector'])
    h = math('MULTIPLY_ADD', weft, 0.3); L.new(math('MULTIPLY', twill, 0.5), h.node.inputs[2])
    h = math('ADD', h, math('MULTIPLY', warp, 0.2))
    h = math('ADD', h, math('MULTIPLY', fib.outputs['Fac'], 0.18))
    h = math('ADD', h, math('MULTIPLY', slub.outputs['Fac'], 0.28))
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.55; bp.inputs['Distance'].default_value = 0.0008
    L.new(h, bp.inputs['Height']); L.new(bp.outputs['Normal'], b.inputs['Normal'])
    # цвет: нить светлее на гребне переплетения, темнее в промежутках; пятна потёртости и грязи крупным шумом
    cr = N.new('ShaderNodeValToRGB'); cr.color_ramp.elements[0].color = (color[0] * 0.55, color[1] * 0.55, color[2] * 0.55, 1)
    cr.color_ramp.elements[1].color = (color[0] * 1.45, color[1] * 1.35, color[2] * 1.25, 1)
    tone = math('MULTIPLY_ADD', big.outputs['Fac'], 0.6); L.new(math('MULTIPLY', h, 0.45), tone.node.inputs[2])
    L.new(tone, cr.inputs['Fac']); L.new(cr.outputs['Color'], b.inputs['Base Color'])
    return m

def _rest(ob, center):
    """Позиция в позе покоя (мир, от оси тела) в атрибут 'rest': координаты для узора ткани."""
    me = ob.data; a = me.attributes.get('rest') or me.attributes.new('rest', 'FLOAT_VECTOR', 'POINT')
    mw = ob.matrix_world; cx, cy = center[0], center[1]
    for i, v in enumerate(me.vertices):
        w = mw @ v.co; a.data[i].vector = (w.x - cx, w.y - cy, w.z)

def _w(body, v, names):
    """доля веса костей names среди всех костей вершины (нормировано, как в Armature-деформере:
    лицевые группы MakeHuman без костей в скелете не занижают долю головы)"""
    s = tot = 0.0
    for g in v.groups:
        n = body.vertex_groups[g.group].name
        if not n.startswith('mixamorig:'): continue
        tot += g.weight
        if any(k in n for k in names): s += g.weight
    return s / tot if tot > 1e-6 else 0.0

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

def _smooth_weights(ob, iters=12, k=0.5, keep=()):
    """Веса ткани размываются по сетке: у кожи тела отдельные вершины (соски, пупок) привязаны к своим костям
    иначе, чем соседи, и при опущенных руках скелет вытягивает их в «точки» под тканью. Ткань — не кожа,
    её веса меняются плавно (так делают риггеры одежды в играх: weight smooth после переноса весов).
    keep — группы, по которым вес не размывается (рукав у запястья держит руку)."""
    import numpy as np
    me = ob.data; nv = len(me.vertices); gs = list(ob.vertex_groups)
    if not gs or nv == 0: return
    W = np.zeros((nv, len(gs)), np.float32)
    for v in me.vertices:
        for g in v.groups: W[v.index, g.group] = g.weight
    E = np.array([e.vertices[:] for e in me.edges], np.int64)
    deg = np.bincount(E.ravel(), minlength=nv).astype(np.float32); deg[deg == 0] = 1
    fix = np.zeros(nv, bool)
    for j, g in enumerate(gs):
        if any(t in g.name for t in keep): fix |= W[:, j] > 0.3
    for _ in range(iters):
        S = np.zeros_like(W); np.add.at(S, E[:, 0], W[E[:, 1]]); np.add.at(S, E[:, 1], W[E[:, 0]])
        Wn = W * (1 - k) + (S / deg[:, None]) * k; Wn[fix] = W[fix]; W = Wn
    W /= np.maximum(W.sum(1, keepdims=True), 1e-6)
    for j, g in enumerate(gs):
        idx = np.nonzero(W[:, j] > 1e-3)[0]
        g.remove(list(range(nv)))
        for i in idx: g.add([int(i)], float(W[i, j]), 'REPLACE')

def _hang_front(verts, mw, belt_z, col=0.025):
    """Шерсть висит, а не облегает: от вершины груди до пояса ткань идёт прямой линией (как полотно, натянутое
    между двумя опорами), поэтому складка под грудной мышцей и «рельеф торса» не читаются — так сидит ряса
    на референсах. Каждая вершина переда между поясом и грудью выдвигается вперёд до этой прямой (только наружу)."""
    import numpy as np
    if not verts: return
    mwi = mw.inverted(); W = np.array([(mw @ v.co)[:] for v in verts])
    pec = (np.abs(W[:, 0]) > 0.03) & (np.abs(W[:, 0]) < 0.17) & (W[:, 2] > belt_z + 0.15)
    if not pec.any(): return
    zp = W[pec][np.argmax(W[pec][:, 1]), 2]          # высота вершины груди
    moved = 0
    for i, v in enumerate(verts):
        x, y, z = W[i]
        if not (belt_z < z < zp): continue
        c = np.abs(W[:, 0] - x) < col
        top = c & (W[:, 2] >= z) & (W[:, 2] <= zp + 0.03); bot = c & (np.abs(W[:, 2] - belt_z) < 0.03)
        if not top.any() or not bot.any(): continue
        y_top = W[top][:, 1].max(); z_top = W[top][np.argmax(W[top][:, 1]), 2]; y_bot = W[bot][:, 1].max()
        if z_top <= belt_z + 1e-3: continue
        t = (z - belt_z) / (z_top - belt_z); target = y_bot + (y_top - y_bot) * min(1.0, t)
        if target > y: v.co = mwi @ Vector((x, target, z)); moved += 1
    print('robe: ткань висит от груди к поясу, сдвинуто вершин', moved, 'грудь z', round(float(zp), 3), 'пояс z', round(belt_z, 3))

def _taubin(verts, iters, lam=0.6, mu=-0.63):
    """Сглаживание Таубина: шаг λ сглаживает, шаг μ возвращает объём — рельеф уходит, форма торса не худеет.
    Соседи вне списка неподвижны (граница зоны)."""
    for _ in range(iters):
        for f in (lam, mu):
            new = {}
            for v in verts:
                nb = [e.other_vert(v).co for e in v.link_edges]
                if nb: new[v] = v.co + (sum(nb, Vector()) / len(nb) - v.co) * f
            for v, c in new.items(): v.co = c

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
    kill = []; ps = body.get('proxy_start', 10 ** 9)
    # рельеф груди (грудные мышцы и соски): сглаживание «только наружу» ниже держит выпуклости как опоры, и шерсть
    # натягивалась на них шатром с точкой, а равномерное сглаживание драпировки ещё и усиливало бугор (замер: пик
    # грудной мышцы 20 мм над окрестностью 5 см → 10 после старого сглаживания → 17 после толщины ткани).
    # Старая зона (вес позвоночника > 0.5) обрывалась ровно на вершине мышцы, и граница держала бугор. Теперь зона —
    # вся передняя поверхность торса от пояса до ключиц, без рук; сглаживание Таубина (λ/μ) — не сжимает объём.
    hip = J['mixamorig:Hips']; hipy = hip.y; mw_ = body.matrix_world
    neck_z = J['mixamorig:Neck'].z if 'mixamorig:Neck' in J else hip.z + 0.55
    front = []
    for v in bm.verts:
        if v.index >= ps or v.is_boundary: continue
        w = mw_ @ v.co; bv = body.data.vertices[v.index]
        if w.y > hipy - 0.01 and hip.z + 0.08 < w.z < neck_z - 0.03 and _w(body, bv, ('Arm', 'Hand')) < 0.3: front.append(v)
    _taubin(front, 40)
    bm.normal_update(); print('robe: сглажен рельеф груди, вершин', len(front))
    for v in bm.verts:
        bv = body.data.vertices[v.index]
        if _w(body, bv, ('Hand', 'Head', 'Neck')) > 0.5 or _w(body, bv, ('Leg', 'Foot', 'Toe')) > 0.5: kill.append(v); continue
        if v.index >= ps or any(f.material_index > 0 for f in v.link_faces): kill.append(v); continue     # брови/ресницы/глаза — не ткань
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
    # после «только наружу» перед торса ещё раз выравнивается: опоры-бугры не должны проступать сквозь шерсть
    _taubin([v for v in front if v not in killset], 30)
    _hang_front([v for v in front if v not in killset], mw_, hip.z + 0.12)
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
    if poles:
        # шатёр: сглаживание «только наружу» держало соски как опоры. Срезаем рельеф ткани в радиусе 5 см вокруг полюса
        pc = [v.co.copy() for v in poles]
        area = [v for v in bm.verts if not v.is_boundary and any((v.co - c).length < 0.05 for c in pc)]
        for _ in range(30):
            new = {v: v.co.lerp(sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges), 0.6) for v in area}
            for v, c in new.items(): v.co = c
        # растворяем полюс и ставим новую вершину в центр дыры (poke): ровный веер вместо тонких треугольников-щепок,
        # которые после сглаживания давали звезду-блик на месте соска; затем кольцо выравнивается (лапласиан)
        bmesh.ops.dissolve_verts(bm, verts=poles)
        ng = [f for f in bm.faces if len(f.verts) > 4]
        res = bmesh.ops.poke(bm, faces=ng, center_mode='MEAN_WEIGHTED')
        ring = set(res['verts'])
        for v in list(ring): ring.update(e.other_vert(v) for e in v.link_edges)
        for _ in range(12):
            for v in ring:
                if v.is_boundary: continue
                nb = [e.other_vert(v).co for e in v.link_edges]
                v.co = v.co.lerp(sum(nb, Vector()) / len(nb), 0.5)
    print('robe top: merged/cleaned, removed', len(small), 'island verts,', len(poles), 'poles')
    bm.to_mesh(me); bm.free()
    me.materials.clear(); me.materials.append(mat)
    _rest(top, J['mixamorig:Hips'])
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
    _smooth_weights(top, iters=12, keep=('ForeArm', 'Hand'))
    am = top.modifiers.new('body', 'ARMATURE'); am.object = arm
    top.parent = arm; top.matrix_parent_inverse = arm.matrix_world.inverted()
    # корректирующее сглаживание после скелета (аналог корректирующих шейпов в играх): плечо и подмышка не мнутся
    # «грудью», когда руки опущены из Т-позы — ткань сохраняет длины рёбер исходной формы
    cs = top.modifiers.new('corrective', 'CORRECTIVE_SMOOTH'); cs.rest_source = 'ORCO'; cs.smooth_type = 'LENGTH_WEIGHTED'; cs.iterations = 8; cs.factor = 0.6
    # лёгкая драпировка: рельеф уже снят Таубином в сетке. 60 равномерных итераций (как было) стягивали вершины к
    # сгущениям сетки у подмышек и рождали острый бугор на груди в позе с опущенными руками (замер: +12 мм)
    sm = top.modifiers.new('drape', 'SMOOTH'); sm.factor = 1.0; sm.iterations = 12
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
    _rest(sk, J['mixamorig:Hips'])
    hz = hip.z
    _rig_like(sk, body, arm, mix={'mixamorig:Hips': lambda co: max(0.0, min(1.0, (co.z - bot_z) / max(0.01, hz - bot_z))) * 0.35 + 0.55})
    sol2 = sk.modifiers.new('thick', 'SOLIDIFY'); sol2.thickness = 0.008
    sk.modifiers.new('sub', 'SUBSURF').render_levels = 1
    # тело под одеждой не рендерим (как в играх и студийных крауд-системах): ноги не протыкают юбку, торс — рясу
    hid = body.vertex_groups.get('covered') or body.vertex_groups.new(name='covered')
    ps = body.get('proxy_start', 10 ** 9)
    for v in body.data.vertices:
        if v.index < ps and _w(body, v, ('Hand', 'Head', 'Neck', 'Foot', 'Toe')) < 0.2 and (v.co.z - 0) > 0.12:
            hid.add([v.index], 1.0, 'REPLACE')
    mk = body.modifiers.new('under_clothes', 'MASK'); mk.vertex_group = 'covered'; mk.invert_vertex_group = True
    # маска — после скелета и сглаживания (CorrectiveSmooth сверяет число вершин с ORCO), но до subsurf
    want = max((k for k, m in enumerate(body.modifiers) if m.type in ('ARMATURE', 'CORRECTIVE_SMOOTH')), default=-1) + 1
    with bpy.context.temp_override(object=body):
        while body.modifiers.find('under_clothes') > want: bpy.ops.object.modifier_move_up(modifier='under_clothes')
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
    _rest(h, J['mixamorig:Hips'])
    _rig_like(h, body, arm, drop=('Hand', 'ForeArm'), mix={'mixamorig:Head': lambda co: max(0.0, min(1.0, (co.z - neck.z + 0.05) / 0.15)) * 0.9})
    s = h.modifiers.new('thick', 'SOLIDIFY'); s.thickness = 0.012; s.offset = 1
    h.modifiers.new('sub', 'SUBSURF').render_levels = 2
    return h
