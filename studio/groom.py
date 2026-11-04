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

def zones(ob):
    """Группы вершин scalp (скальп) и beard (борода) — плотность 0..1 с мягкой линией роста."""
    E, X, Y, Z = _frame(ob)
    hg = ob.vertex_groups.get('mixamorig:Head'); hi = hg.index if hg else -1
    scalp = ob.vertex_groups.new(name='scalp'); beard = ob.vertex_groups.new(name='beard')
    fm = ob.data.color_attributes.get('face_mask')
    for v in ob.data.vertices:
        wh = max((g.weight for g in v.groups if g.group == hi), default=0.0)
        if wh < 0.35: continue
        d = v.co - E; x, y, z = d.dot(X), d.dot(Y), d.dot(Z)
        # линия роста: спереди ~6 см над глазами, на висках ниже, сзади до затылочной ямки
        front = _sm(y, -0.03, 0.02)                     # 1 — лоб, 0 — затылок
        line = 0.058 * front + (-0.075) * (1 - front) + 0.012 * _sm(abs(x), 0.03, 0.06) * front
        w = _sm(z, line, line + 0.012) * _sm(wh, 0.35, 0.7)
        ear = _sm(abs(x), 0.062, 0.07) * (1 - _sm(z, 0.012, 0.03)) * _sm(-y, 0.0, 0.02) * (1 - _sm(-y, 0.085, 0.1))
        w *= (1 - ear)
        if y > 0.02 and z < 0.05: w = 0.0               # лицо
        if w > 0.02: scalp.add([v.index], w, 'REPLACE')
        if fm:
            b = fm.data[v.index].color[1] * (1 - _sm(-z, 0.115, 0.13)) * _sm(y, -0.06, -0.03)   # не ниже челюсти, не на шее
            if b > 0.05: beard.add([v.index], min(1.0, b * 1.2), 'REPLACE')
    return scalp, beard

def hair_material(name='hair', melanin=0.75, redness=0.35, grey=0.25, roughness=0.32):
    m = bpy.data.materials.new(name); m.use_nodes = True; N, L = m.node_tree.nodes, m.node_tree.links
    for n in list(N):
        if n.type != 'OUTPUT_MATERIAL': N.remove(n)
    out = next(n for n in N if n.type == 'OUTPUT_MATERIAL')
    h = N.new('ShaderNodeBsdfHairPrincipled')
    try: h.parametrization = 'MELANIN'
    except Exception: pass
    def s(k, v):
        if k in h.inputs: h.inputs[k].default_value = v
    s('Melanin', melanin); s('Melanin Redness', redness); s('Roughness', roughness); s('Radial Roughness', 0.35)
    s('Coat', 0.05); s('Random Color', 0.18); s('Random Roughness', 0.12); s('IOR', 1.55)
    # седина: часть прядей почти без меланина (Hair Info → Random)
    if grey > 0 and 'Melanin' in h.inputs:
        hi = N.new('ShaderNodeHairInfo'); mr = N.new('ShaderNodeMapRange')
        mr.inputs['From Min'].default_value = 1 - grey; mr.inputs['From Max'].default_value = 1 - grey + 0.02
        mr.inputs['To Min'].default_value = melanin; mr.inputs['To Max'].default_value = 0.08
        L.new(hi.outputs['Random'], mr.inputs['Value']); L.new(mr.outputs['Result'], h.inputs['Melanin'])
    L.new(h.outputs[0], out.inputs['Surface'])
    return m

def _system(ob, name, group, mat_index, count, length, children, width, align, clump, rough, kink=0.0):
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
    st.hair_step = 5; st.display_step = 3; st.render_step = 4
    st.child_type = 'INTERPOLATED'; st.child_percent = 2; st.rendered_child_count = children
    st.child_length = 1.0; st.child_length_threshold = 0.25           # четверть детей короче — естественная неровность
    st.clump_factor = clump; st.clump_shape = 0.2
    st.roughness_1 = rough; st.roughness_1_size = 0.6; st.roughness_endpoint = rough * 0.6; st.roughness_end_shape = 1.0
    st.roughness_2 = rough * 0.5; st.roughness_2_size = 1.5
    if kink: st.kink = 'CURL'; st.kink_amplitude = kink; st.kink_frequency = 6
    st.material = mat_index + 1
    st.root_radius = 1.0; st.tip_radius = 0.15; st.radius_scale = width; st.use_close_tip = True
    st.display_percentage = 20
    return ps

def groom(ob, color=None, grey=0.25, scalp_len=0.022, beard_len=0.009, density=1.0, hooded=False):
    """Короткая стрижка + борода. hooded: волосы короче, чтобы не пробивать капюшон."""
    if 'eyes' not in ob: return None
    scalp, beard = zones(ob)
    melanin = 0.8 if color is None else max(0.05, min(1.0, 1.0 - sum(color) / 3 * 6))
    m = hair_material('hair', melanin=melanin, grey=grey); ob.data.materials.append(m); mi = len(ob.data.materials) - 1
    L = scalp_len * (0.6 if hooded else 1.0)
    _system(ob, 'scalp', scalp, mi, int(9000 * density), L, 14, 0.00022, (0, -0.6, -0.9), 0.3, 0.0015)
    _system(ob, 'beard', beard, mi, int(5000 * density), beard_len, 10, 0.0002, (0, 0.1, -1.1), 0.35, 0.0012, kink=0.001)
    return ob
