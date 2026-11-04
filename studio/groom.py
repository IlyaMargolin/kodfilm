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

# Рот (замерено по UV-маске губ MakeHuman на этом теле, м от середины глаз): губы z −0.064…−0.083, уголки |x| 0.028 на z −0.073,
# основание носа z ≈ −0.055, подбородок вперёд на z −0.11, низ подбородка −0.13
LIP_C, LIP_W, LIP_H = -0.0735, 0.028, 0.0098

def _lip_d(x, z):
    """«эллиптическое расстояние» от центра рта: <1 — губы"""
    return math.hypot(x / LIP_W, (z - LIP_C) / LIP_H)

def beard_w(x, y, z):
    """Плотность бороды по анатомии роста (координаты от середины глаз, м: x — вбок, y — вперёд, z — вверх).
    Зоны мужской бороды: бакенбарды от уха → линия щеки (диагональ от мочки уха к углу рта) → подбородок →
    под челюстью до «линии шеи» (≈2 см над кадыком). Усы — отдельная система (moustache_w). Губы, нос и скулы чистые:
    рот всегда открыт — у живой бороды губы видны, иначе лицо «без рта»."""
    ax = abs(x)
    if y < -0.085 or ax > 0.078: return 0.0
    # линия щеки ниже скулы: от мочки уха (|x| 0.066, z −0.012) к точке на 6 мм ниже и снаружи уголка рта
    t = min(1.0, max(0.0, (0.066 - ax) / (0.066 - 0.034)))
    zl = -0.012 + (-0.078 + 0.012) * t ** 1.1 if ax > 0.034 else -0.084
    w = 1.0 - _sm(z, zl - 0.012, zl)                 # выше линии — нет волос, мягкий край
    w *= 0.55 + 0.45 * _sm(-z, 0.03, 0.06) if ax > 0.04 else 1.0   # на щеках реже, к челюсти гуще
    w *= _sm(_lip_d(x, z), 1.25, 1.6)                # губы и кайма вокруг них чистые
    w *= 1.0 - _sm(-z, 0.15, 0.165)                  # линия шеи
    if y < -0.045 and not (ax > 0.055 and z > -0.05): w *= 1.0 - _sm(-y, 0.045, 0.075)   # сзади челюсти только бакенбарды
    return max(0.0, min(1.0, w))

def moustache_w(x, y, z):
    """Усы: от основания носа до верхней губы, к уголкам рта опускаются. Желобок (фильтрум) реже."""
    ax = abs(x)
    if ax > 0.036 or y < 0.0: return 0.0
    top = -0.054 - 0.012 * _sm(ax, 0.012, 0.03)       # у крыльев носа выше, к углам рта линия опускается
    w = _sm(top - z, 0.0, 0.004) * _sm(_lip_d(x, z), 1.08, 1.3)
    if z < LIP_C and ax < LIP_W: w = 0.0              # ниже центра рта усов нет
    if ax < 0.005: w *= 0.55
    return max(0.0, min(1.0, w))

def lip_len(x, z):
    """длина бороды у рта: под нижней губой короткий «ус» подбородка, дальше — полная"""
    d = _lip_d(x, z)
    return 0.3 + 0.7 * _sm(d, 1.6, 3.2)

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
    slen = ob.vertex_groups.new(name='scalp_len'); hfront = ob.vertex_groups.new(name='hairline')
    scalp = ob.vertex_groups.new(name='scalp'); beard = ob.vertex_groups.new(name='beard'); blen = ob.vertex_groups.new(name='beard_len')
    brows = [ob.vertex_groups.new(name='brow_l'), ob.vertex_groups.new(name='brow_r')]
    must = [ob.vertex_groups.new(name='moustache_l'), ob.vertex_groups.new(name='moustache_r')]
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
        line = (0.058 + temple) * front + (-0.075) * (1 - front) + 0.008 * _sm(abs(x), 0.045, 0.065) * front
        w = _sm(z, line, line + 0.009) ** 0.6 * _sm(wh, 0.35, 0.7)   # край роста: ~1 см редкого пушка → густые волосы
        ear = _sm(abs(x), 0.062, 0.07) * (1 - _sm(z, 0.012, 0.03)) * _sm(-y, 0.0, 0.02) * (1 - _sm(-y, 0.085, 0.1))
        w *= (1 - ear)
        if y > 0.02 and z < 0.05: w = 0.0               # лицо
        # линия лба: отдельный густой подшёрсток, волосы поднимаются и уходят назад — кожа лба не просвечивает сквозь зачёс
        hf = front * _sm(z, line, line + 0.006) * (1 - _sm(z, line + 0.025, line + 0.04)) * _sm(wh, 0.35, 0.7) * (1 - ear)
        if hf > 0.05 and not (y > 0.02 and z < 0.05): hfront.add([v.index], hf, 'REPLACE')
        if w > 0.02:
            scalp.add([v.index], w, 'REPLACE')
            # виски и над ушами короче: волосы не свисают на щёки и бакенбарды, а уходят назад за ухо
            slen.add([v.index], 1.0 - 0.6 * _sm(abs(x), 0.045, 0.065) * (1 - _sm(z, 0.02, 0.07)), 'REPLACE')
        b = beard_w(x, y, z) * _sm(wh, 0.3, 0.6)
        if b > 0.05:
            beard.add([v.index], b, 'REPLACE')
            # длина бороды по зонам: на щеках короче и прижата, на подбородке и под челюстью — полная длина
            blen.add([v.index], min(0.35 + 0.65 * _sm(-z, 0.045, 0.1), lip_len(x, z)), 'REPLACE')
        mw = moustache_w(x, y, z)
        if mw > 0.05: must[0 if x > 0 else 1].add([v.index], mw, 'REPLACE')
        bw = brow_w(x, y, z)
        if bw > 0.05: brows[0 if x > 0 else 1].add([v.index], bw, 'REPLACE')
    return scalp, beard, brows, must

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

def _system(ob, name, group, mat_index, count, length, children, width, align, clump, rough, kink=0.0, wave=0.0, rnd=0.3):
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
    ps.vertex_group_density = group.name; ps.seed = hash(name) % 1000
    st.type = 'HAIR'; st.use_advanced_hair = True; st.count = count
    st.emit_from = 'FACE'; st.use_emit_random = True; st.use_even_distribution = True
    # длина пряди = |скорость эмиссии|: нормаль + «зачёс» назад/вниз, обе в масштабе длины
    a = Vector(align); k = length / 4.0 / (0.85 * (1.0 + a.length))   # в Blender длина = 4·|скорость|; нормаль на голове смотрит куда угодно
    st.normal_factor = k; st.object_align_factor = tuple(a * k)
    st.factor_random = k * rnd      # каждый волос чуть в свою сторону: без этого пряди ложатся «черепицей» рядами
    st.hair_step = 6; st.display_step = 3; st.render_step = 5
    st.child_type = 'INTERPOLATED'; st.child_percent = 2; st.rendered_child_count = children
    st.virtual_parents = 0.0
    st.child_length = 1.0; st.child_length_threshold = 0.35           # треть детей короче — естественная неровность
    st.clump_factor = clump; st.clump_shape = 0.1                      # пряди мягко сходятся к кончикам (сильнее — «дреды»)
    # шум пучков (clump noise) в Blender задаётся в метрах мира — на голове 2 см он разбрасывает детей поперёк лица; не используем
    st.roughness_1 = rough * 0.5; st.roughness_1_size = 0.4; st.roughness_endpoint = rough * 0.8; st.roughness_end_shape = 1.2
    st.roughness_2 = rough * 0.6; st.roughness_2_size = 2.0; st.roughness_2_threshold = 0.6   # отдельные «непослушные» волоски
    if kink: st.kink = 'CURL'; st.kink_amplitude = kink; st.kink_frequency = 6
    elif wave: st.kink = 'WAVE'; st.kink_amplitude = wave; st.kink_frequency = 2.2; st.kink_shape = 0.3
    st.material = mat_index + 1
    st.root_radius = 1.0; st.tip_radius = 0.1; st.radius_scale = width; st.use_close_tip = True; st.shape = -0.2
    st.display_percentage = 20
    return ps

def groom(ob, color=None, grey=0.25, scalp_len=0.05, beard_len=0.03, density=1.0, hooded=False, recede=0.008):
    """Волосы + борода. Длины по анатомии роста: волосы ~1 см/мес, борода путника за 3–4 мес — 3–4 см.
    hooded: волосы короче, чтобы не пробивать капюшон. recede: залысины на висках (м), растут с возрастом."""
    if 'eyes' not in ob: return None
    scalp, beard, brows, must = zones(ob, recede)
    melanin = 0.8 if color is None else max(0.05, min(1.0, 1.0 - sum(color) / 3 * 6))
    m = hair_material('hair', melanin=melanin, grey=grey); ob.data.materials.append(m); mi = len(ob.data.materials) - 1
    L = scalp_len * (0.5 if hooded else 1.0)
    # скальп: зачёс назад. Толщина пряди — «рендерная», не анатомическая: волос 70 мкм на крупном плане 1080p = 0.1 пикселя,
    # он мерцает шумом и шумодав превращает его в мазню. Студии рендерят 0.2–0.3 мм и меньше кривых: каждая пиксель-стабильна
    # (14 тыс. корней × 9 детей ≈ 140 тыс. кривых — как живая шевелюра по плотности покрытия)
    ss = _system(ob, 'scalp', scalp, mi, int(14000 * density), L, 9, 0.0002, (0, -0.95, -0.45), 0.35, 0.0014, rnd=0.08)
    ss.vertex_group_length = 'scalp_len'
    _system(ob, 'hairline', ob.vertex_groups['hairline'], mi, int(2500 * density), L * 0.8, 9, 0.0002, (0, -1.4, -0.35), 0.3, 0.0012, rnd=0.06)
    # брови прядями: короткие (8–10 мм) жёсткие волоски, у переносицы вверх, дальше — к виску, прижаты к коже.
    # Ось X тела: +X — сторона левого глаза (ob['eyes'][0]); волоски уходят наружу от переносицы
    E, X, Y, Z = _frame(ob)
    for g, sx in zip(brows, (1, -1)):
        d = X * sx * 1.4 + Z * 0.45 + Y * 0.15
        _system(ob, g.name, g, mi, int(650 * density), 0.008, 8, 0.00016, tuple(d), 0.25, 0.0006, rnd=0.12)
    if beard_len > 0:
        # борода растёт вниз и вперёд, на щеках — прижата, на подбородке — пучками; волос бороды жёстче и толще (≈100 мкм)
        bs = _system(ob, 'beard', beard, mi, int(9000 * density), beard_len, 10, 0.00024, (0, 0.35, -1.25), 0.45, 0.0016)
        bs.vertex_group_length = 'beard_len'
        # усы: короткие (≈1 см), растут вниз и наружу от середины — кончики ложатся на край верхней губы и к уголкам рта,
        # но не закрывают рот
        for g, sx in zip(must, (1, -1)):
            d = X * sx * 0.9 + Z * -1.0 + Y * 0.12
            _system(ob, g.name, g, mi, int(1400 * density), min(0.011, beard_len * 0.4), 10, 0.00022, tuple(d), 0.4, 0.0008, rnd=0.2)
    return ob
