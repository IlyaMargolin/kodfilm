"""Груминг: волосы и борода частицами-прядями на теле studio/human.py (наш код, без чужих ассетов).
Как у студий: зона роста задаётся картой плотности (группа вершин), пряди — кривые с детьми-интерполяцией,
шейдер — Principled Hair (физическая модель Chiang: цвет из меланина, а не «краска»), седина — случайная примесь.
Частицы стоят в стеке сразу после скелета: пряди едут с кожей при любой анимации."""
import math
import bpy
from mathutils import Vector

def _frame(ob):
    l, r = (Vector(v) for v in ob['eyes'])
    E = (l + r) / 2; X = (l - r).normalized(); Z = Vector((0, 0, 1)); Y = Z.cross(X).normalized()
    if Y.y < 0: Y = -Y
    return E, X, Y, Z

def _sm(x, a, b): return max(0.0, min(1.0, (x - a) / (b - a)))

def beard_w(x, y, z):
    """Плотность бороды по анатомии роста (координаты от середины глаз, м: x — вбок, y — вперёд, z — вверх).
    Зоны мужской бороды: бакенбарды от уха → линия щеки (диагональ от бакенбарда к углу рта) → усы над губой →
    подбородок → под челюстью до «линии шеи» (≈2 см над кадыком). Губы, нос и скулы выше линии щеки — чистые."""
    ax = abs(x)
    if y < -0.085 or ax > 0.078: return 0.0
    # линия щеки: от бакенбарда (|x|=0.066, z=+0.005) к углу рта (|x|=0.027, z=-0.066); у центра — низ носа
    t = min(1.0, max(0.0, (0.066 - ax) / (0.066 - 0.027)))
    zl = 0.005 + (-0.066 - 0.005) * t ** 1.2 if ax > 0.027 else -0.056
    w = 1.0 - _sm(z, zl - 0.012, zl)                 # выше линии — нет волос, мягкий край
    w *= 0.55 + 0.45 * _sm(-z, 0.03, 0.06) if ax > 0.04 else 1.0   # на щеках реже, к челюсти гуще
    if ax < 0.019 and z > -0.06: return 0.0          # нос
    if ax < 0.026 and -0.094 < z < -0.069: w *= 0.0 if z < -0.076 else 0.5   # губы чистые, усы нависают над верхней
    if ax < 0.012 and -0.068 < z < -0.058: w *= 0.6  # желобок под носом реже
    w *= 1.0 - _sm(-z, 0.15, 0.165)                  # линия шеи
    if y < -0.045 and not (ax > 0.055 and z > -0.05): w *= 1.0 - _sm(-y, 0.045, 0.075)   # сзади челюсти только бакенбарды
    return max(0.0, min(1.0, w))

def brow_w(x, y, z):
    """Брови: дуга над глазом (выше всего над наружной третью радужки), у переносицы толще и гуще, к виску тонкая.
    Мужская бровь — низкая и почти прямая, лежит на надбровной дуге."""
    ax = abs(x)
    if ax < 0.011 or ax > 0.062 or y < -0.01: return 0.0
    t = (ax - 0.011) / 0.051                          # 0 — у переносицы, 1 — хвост у виска
    zc = 0.017 + 0.006 * math.sin(math.pi * min(1.0, t * 1.25)) - 0.004 * max(0.0, t - 0.8) / 0.2
    half = 0.0065 * (1 - t) + 0.0025 * t
    w = 1.0 - _sm(abs(z - zc), half * 0.6, half)
    return w * (0.65 + 0.35 * (1 - t)) * (1 - _sm(t, 0.85, 1.0) * 0.6)

def zones(ob, recede=0.0):
    """Группы вершин scalp (скальп) и beard (борода) — плотность 0..1 с мягкой линией роста."""
    E, X, Y, Z = _frame(ob)
    hg = ob.vertex_groups.get('mixamorig:Head'); hi = hg.index if hg else -1
    scalp = ob.vertex_groups.new(name='scalp'); beard = ob.vertex_groups.new(name='beard')
    brows = [ob.vertex_groups.new(name='brow_l'), ob.vertex_groups.new(name='brow_r')]
    fm = ob.data.color_attributes.get('face_mask'); ps = ob.get('proxy_start', 10 ** 9)
    bone = {g.index for g in ob.vertex_groups if g.name.startswith('mixamorig:')}
    for v in ob.data.vertices:
        if v.index >= ps: break                          # брови/ресницы/глаза — волосы из них не растут
        # доля головы среди костей (лицевые группы MakeHuman без костей не должны «прятать» бороду)
        tot = sum(g.weight for g in v.groups if g.group in bone)
        wh = max((g.weight for g in v.groups if g.group == hi), default=0.0) / tot if tot > 1e-6 else 0.0
        if wh < 0.35: continue
        d = v.co - E; x, y, z = d.dot(X), d.dot(Y), d.dot(Z)
        # линия роста: спереди ~6 см над глазами, на висках ниже, сзади до затылочной ямки
        front = _sm(y, -0.03, 0.02)                     # 1 — лоб, 0 — затылок
        # мужская линия роста: лоб ≈ 3 «пальца» над бровью (7–8 см над глазами), залысины на висках с возрастом (M-форма)
        temple = recede * _sm(abs(x), 0.018, 0.042) * (1 - _sm(abs(x), 0.06, 0.07))
        line = (0.064 + temple) * front + (-0.075) * (1 - front) + 0.008 * _sm(abs(x), 0.045, 0.065) * front
        w = _sm(z, line, line + 0.016) * _sm(wh, 0.35, 0.7)   # край роста мягкий: редкий пушок → густые волосы
        ear = _sm(abs(x), 0.062, 0.07) * (1 - _sm(z, 0.012, 0.03)) * _sm(-y, 0.0, 0.02) * (1 - _sm(-y, 0.085, 0.1))
        w *= (1 - ear)
        if y > 0.02 and z < 0.05: w = 0.0               # лицо
        if w > 0.02: scalp.add([v.index], w, 'REPLACE')
        b = beard_w(x, y, z) * _sm(wh, 0.3, 0.6)
        if b > 0.05: beard.add([v.index], b, 'REPLACE')
        bw = brow_w(x, y, z)
        if bw > 0.05: brows[0 if x > 0 else 1].add([v.index], bw, 'REPLACE')
    return scalp, beard, brows

def hair_material(name='hair', melanin=0.75, redness=0.18, grey=0.25, roughness=0.3):
    m = bpy.data.materials.new(name); m.use_nodes = True; N, L = m.node_tree.nodes, m.node_tree.links
    for n in list(N):
        if n.type != 'OUTPUT_MATERIAL': N.remove(n)
    out = next(n for n in N if n.type == 'OUTPUT_MATERIAL')
    h = N.new('ShaderNodeBsdfHairPrincipled')
    try: h.parametrization = 'MELANIN'
    except Exception: pass
    def s(k, v):
        if k in h.inputs: h.inputs[k].default_value = v
    s('Melanin', melanin); s('Melanin Redness', redness); s('Roughness', roughness); s('Radial Roughness', 0.3)
    s('Coat', 0.05); s('Random Color', 0.18); s('Random Roughness', 0.12); s('IOR', 1.55)
    # седина: часть прядей почти без меланина (Hair Info → Random)
    if grey > 0 and 'Melanin' in h.inputs:
        hi = N.new('ShaderNodeHairInfo'); mr = N.new('ShaderNodeMapRange')
        mr.inputs['From Min'].default_value = 1 - grey; mr.inputs['From Max'].default_value = 1 - grey + 0.02
        mr.inputs['To Min'].default_value = melanin; mr.inputs['To Max'].default_value = 0.08
        L.new(hi.outputs['Random'], mr.inputs['Value']); L.new(mr.outputs['Result'], h.inputs['Melanin'])
    L.new(h.outputs[0], out.inputs['Surface'])
    return m

def _system(ob, name, group, mat_index, count, length, children, width, align, clump, rough, kink=0.0, wave=0.0):
    """Система прядей. Детализация как в студийном груминге: тонкие (60–90 мкм) волоски, собранные в пряди
    (clump + шум пучков), неровная длина, лёгкая волна."""
    pm = ob.modifiers.new(name, 'PARTICLE_SYSTEM')
    # сразу после скелета, до маски/сглаживания: топология эмиттера одна во вьюпорте и рендере
    i = list(ob.modifiers).index(pm); arm_i = max((k for k, m in enumerate(ob.modifiers) if m.type in ('ARMATURE', 'CORRECTIVE_SMOOTH')), default=-1)
    while i > arm_i + 1:
        bpy.context.view_layer.objects.active = ob
        with bpy.context.temp_override(object=ob): bpy.ops.object.modifier_move_up(modifier=pm.name)
        i -= 1
    ps = ob.particle_systems[-1]; st = ps.settings; st.name = name
    ps.vertex_group_density = group.name; ps.vertex_group_length = group.name; ps.seed = hash(name) % 1000
    st.type = 'HAIR'; st.use_advanced_hair = True; st.count = count
    st.emit_from = 'FACE'; st.use_emit_random = True; st.use_even_distribution = True
    # длина пряди = |скорость эмиссии|: нормаль + «зачёс» назад/вниз, обе в масштабе длины
    a = Vector(align); k = length / 4.0 / (0.85 * (1.0 + a.length))   # в Blender длина = 4·|скорость|; нормаль на голове смотрит куда угодно
    st.normal_factor = k; st.object_align_factor = tuple(a * k)
    st.hair_step = 6; st.display_step = 3; st.render_step = 5
    st.child_type = 'INTERPOLATED'; st.child_percent = 2; st.rendered_child_count = children
    st.virtual_parents = 0.0
    st.child_length = 1.0; st.child_length_threshold = 0.35           # треть детей короче — естественная неровность
    st.clump_factor = clump; st.clump_shape = 0.1                      # пряди мягко сходятся к кончикам (сильнее — «дреды»)
    # шум пучков (clump noise) в Blender задаётся в метрах мира — на голове 2 см он разбрасывает детей поперёк лица; не используем
    st.roughness_1 = rough; st.roughness_1_size = 0.4; st.roughness_endpoint = rough * 0.8; st.roughness_end_shape = 1.2
    st.roughness_2 = rough * 0.6; st.roughness_2_size = 2.0; st.roughness_2_threshold = 0.6   # отдельные «непослушные» волоски
    if kink: st.kink = 'CURL'; st.kink_amplitude = kink; st.kink_frequency = 6
    elif wave: st.kink = 'WAVE'; st.kink_amplitude = wave; st.kink_frequency = 2.2; st.kink_shape = 0.3
    st.material = mat_index + 1
    st.root_radius = 1.0; st.tip_radius = 0.1; st.radius_scale = width; st.use_close_tip = True; st.shape = -0.2
    st.display_percentage = 20
    return ps

def groom(ob, color=None, grey=0.25, scalp_len=0.05, beard_len=0.03, density=1.0, hooded=False, recede=0.012):
    """Волосы + борода. Длины по анатомии роста: волосы ~1 см/мес, борода путника за 3–4 мес — 3–4 см.
    hooded: волосы короче, чтобы не пробивать капюшон. recede: залысины на висках (м), растут с возрастом."""
    if 'eyes' not in ob: return None
    scalp, beard, brows = zones(ob, recede)
    melanin = 0.8 if color is None else max(0.05, min(1.0, 1.0 - sum(color) / 3 * 6))
    m = hair_material('hair', melanin=melanin, grey=grey); ob.data.materials.append(m); mi = len(ob.data.materials) - 1
    L = scalp_len * (0.5 if hooded else 1.0)
    # скальп: зачёс назад, пряди густые (на голове ~100–150 тыс. волос: 14 тыс. корней × 24 ребёнка ≈ 340 тыс. кривых — с запасом)
    _system(ob, 'scalp', scalp, mi, int(14000 * density), L, 24, 0.00008, (0, -1.1, -0.5), 0.35, 0.0014)
    # брови прядями: короткие (8–10 мм) жёсткие волоски, у переносицы вверх, дальше — к виску, прижаты к коже.
    # Ось X тела: +X — сторона левого глаза (ob['eyes'][0]); волоски уходят наружу от переносицы
    E, X, Y, Z = _frame(ob)
    for g, sx in zip(brows, (1, -1)):
        d = X * sx * 1.4 + Z * 0.45 + Y * 0.15
        _system(ob, g.name, g, mi, int(900 * density), 0.0095, 12, 0.00009, tuple(d), 0.25, 0.0006)
    if beard_len > 0:
        # борода растёт вниз и вперёд, на щеках — прижата, на подбородке — пучками; волос бороды жёстче и толще (≈100 мкм)
        _system(ob, 'beard', beard, mi, int(9000 * density), beard_len, 28, 0.0001, (0, 0.35, -1.25), 0.45, 0.0016)
    return ob
