"""Реалистичные люди с верными пропорциями. Собственный загрузчик поверх открытых данных MakeHuman (MPFB2, ассеты CC0:
базовая сетка, морф-таргеты, риг Mixamo и веса кожи). Код MPFB не запускаем и не копируем — только CC0-данные.
Данные: assets/mh (assets/fetch.sh клонирует github.com/makehumancommunity/mpfb2 и берёт src/mpfb/data).

build(arm, gender=1.0, age=0.5, muscle=0.5, weight=0.5, height=0.5, proportions=0.5, race=None)
  -> меш человека, посаженный на скелет arm (скелет Mixamo из GLB с нашим мокапом): скелет переставляется
     в суставы нового тела, ориентации костей не меняются, поэтому все действия мокапа работают без ретаргета."""
import os, gzip, json, math
import bpy, bmesh
from mathutils import Vector, Matrix
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MH = os.path.join(ROOT, 'assets', 'mh')
T = lambda *p: os.path.join(MH, 'targets', 'macrodetails', *p)

def _load_obj():
    vs, vts, faces, fuv = [], [], [], []; grp = None
    for l in open(os.path.join(MH, '3dobjs', 'base.obj')):
        if l.startswith('v '): _, x, y, z = l.split()[:4]; vs.append((float(x), float(y), float(z)))
        elif l.startswith('vt '): p = l.split(); vts.append((float(p[1]), float(p[2])))
        elif l.startswith('g '): grp = l.split()[1]
        elif l.startswith('f '):
            idx = [p.split('/') for p in l.split()[1:]]
            if grp == 'body':
                faces.append([int(i[0]) - 1 for i in idx]); fuv.append([int(i[1]) - 1 for i in idx])
            elif grp and grp.startswith('joint-'):
                JOINTS.setdefault(grp, set()).update(int(i[0]) - 1 for i in idx)
    return np.array(vs, dtype=np.float64), vts, faces, fuv

JOINTS = {}   # кубики-маркеры суставов в базовой сетке: имя группы -> индексы вершин

def _target(path):
    d = {}
    if not os.path.exists(path): return None
    with gzip.open(path, 'rt') as f:
        for l in f:
            p = l.split()
            if len(p) == 4: d[int(p[0])] = (float(p[1]), float(p[2]), float(p[3]))
    return d

def _add(V, path, w):
    if w <= 1e-4: return
    t = _target(path)
    if t is None: print('нет таргета', os.path.basename(path)); return
    if not t: return
    idx = np.fromiter(t.keys(), dtype=np.int64); dv = np.array(list(t.values()))
    V[idx] += dv * w

def _two(v, cuts):
    """значение -> {категория: вес} по частям макро-ползунка (как в MakeHuman)."""
    for lo, hi, a, b in cuts:
        if v <= hi:
            f = (v - lo) / (hi - lo); return {a: 1 - f, b: f}
    lo, hi, a, b = cuts[-1]; return {b: 1.0}

def shape(gender=1.0, age=0.5, muscle=0.5, weight=0.5, height=0.5, proportions=0.5, race=None):
    V, vts, faces, fuv = _load_obj()
    G = {'female': 1 - gender, 'male': gender}
    A = _two(age, [(0.0, 0.1875, 'baby', 'child'), (0.1875, 0.5, 'child', 'young'), (0.5, 1.0, 'young', 'old')])
    M = _two(muscle, [(0.0, 0.5, 'minmuscle', 'averagemuscle'), (0.5, 1.0, 'averagemuscle', 'maxmuscle')])
    W = _two(weight, [(0.0, 0.5, 'minweight', 'averageweight'), (0.5, 1.0, 'averageweight', 'maxweight')])
    for g, wg in G.items():
        for a, wa in A.items():
            for m, wm in M.items():
                for w, ww in W.items():
                    f = wg * wa * wm * ww
                    _add(V, T(f'universal-{g}-{a}-{m}-{w}.target.gz'), f)
                    if height != 0.5:
                        hk = 'maxheight' if height > 0.5 else 'minheight'
                        _add(V, T('height', f'{g}-{a}-{m}-{w}-{hk}.target.gz'), f * abs(height - 0.5) * 2)
                    if proportions != 0.5 and a != 'baby':
                        pk = 'idealproportions' if proportions > 0.5 else 'uncommonproportions'
                        _add(V, T('proportions', f'{g}-{a}-{m}-{w}-{pk}.target.gz'), f * abs(proportions - 0.5) * 2)
            if race:
                for r, wr in race.items(): _add(V, T(f'{r}-{g}-{a}.target.gz'), wg * wa * wr)
    # obj: Y вверх, дециметры -> Blender: Z вверх, метры, стопы на z=0
    B = np.stack([-V[:, 0], V[:, 2], V[:, 1]], 1) * 0.1   # лицом к +Y, как скелеты Mixamo из GLB
    B[:, 2] -= B[:, 2].min() if False else B[[f for fc in faces for f in fc], 2].min()
    return B, vts, faces, fuv

def _joint(B, spec):
    if spec.get('strategy') == 'CUBE' and spec.get('cube_name') in JOINTS:      # центр маркера сустава (CUBE)
        return Vector(B[sorted(JOINTS[spec['cube_name']])].mean(0))
    idx = spec.get('vertex_indices') or []
    if idx: return Vector(B[idx].mean(0))
    return Vector(spec['default_position'])

def skin_material(tone=(0.62, 0.43, 0.33)):
    m = bpy.data.materials.new('skin'); m.use_nodes = True; N = m.node_tree.nodes; L = m.node_tree.links
    b = N['Principled BSDF']
    b.inputs['Base Color'].default_value = (*tone, 1); b.inputs['Roughness'].default_value = 0.48
    for k, v in (('Subsurface Weight', 0.6), ('Subsurface Scale', 0.006), ('Specular IOR Level', 0.45), ('Coat Weight', 0.06), ('Coat Roughness', 0.35)):
        if k in b.inputs: b.inputs[k].default_value = v
    if 'Subsurface Radius' in b.inputs: b.inputs['Subsurface Radius'].default_value = (1.0, 0.35, 0.2)
    # поры и неровность кожи: мелкий шум в бамп, лёгкая пятнистость цвета
    tc = N.new('ShaderNodeTexCoord'); nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 900; nz.inputs['Detail'].default_value = 4
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.08; bp.inputs['Distance'].default_value = 0.0006
    L.new(nz.outputs['Fac'], bp.inputs['Height']); L.new(bp.outputs['Normal'], b.inputs['Normal'])
    nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 40; L.new(tc.outputs['Object'], nz2.inputs['Vector'])
    mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.inputs['Factor'].default_value = 0.12
    mx.inputs['A'].default_value = (*tone, 1); mx.inputs['B'].default_value = (tone[0] * 1.1, tone[1] * 0.8, tone[2] * 0.8, 1)
    L.new(nz2.outputs['Fac'], mx.inputs['Factor']) if False else None
    L.new(mx.outputs['Result'], b.inputs['Base Color'])
    return m

def build(arm, name='human', skin=None, subdiv=1, **macro):
    """Строит тело и пересаживает скелет arm (Mixamo) в его суставы. Меши, которые были у arm, удаляются."""
    B, vts, faces, fuv = shape(**macro)
    rig = json.load(open(os.path.join(MH, 'rigs', 'standard', 'rig.mixamo.json')))['bones']
    wts = json.load(open(os.path.join(MH, 'rigs', 'standard', 'weights.mixamo.json')))['weights']
    used = sorted({i for f in faces for i in f}); remap = {o: n for n, o in enumerate(used)}
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(B[i]) for i in used], [], [[remap[i] for i in f] for f in faces])
    uv = me.uv_layers.new(name='UV'); k = 0
    for poly, fu in zip(me.polygons, fuv):
        for li, ui in zip(poly.loop_indices, fu): uv.data[li].uv = vts[ui]
    me.update(); [setattr(p, 'use_smooth', True) for p in me.polygons]
    ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.data.materials.append(skin or skin_material())

    # --- суставы нового тела (мир) и Т-поза под скелет arm ---
    J = {n: (_joint(B, s['head']), _joint(B, s['tail'])) for n, s in rig.items()}
    mw = arm.matrix_world.copy(); inv = mw.inverted()
    eb_rest = {b.name: (mw @ b.head_local) for b in arm.data.bones}
    child = {}
    for b in arm.data.bones:
        if b.parent and b.parent.name not in child: child[b.parent.name] = b.name
    # первичные дети по анатомии (первый ребёнок у бёдер — Spine, нам нужна ось сустава)
    child.update({'mixamorig:Hips': 'mixamorig:Spine', 'mixamorig:Spine2': 'mixamorig:Neck', 'mixamorig:LeftHand': 'mixamorig:LeftHandMiddle1',
                  'mixamorig:RightHand': 'mixamorig:RightHandMiddle1'})
    # временный скелет из json (A-поза тела), поворачиваем кости, чтобы направления совпали с Т-позой arm
    ta = bpy.data.armatures.new('tmp'); to = bpy.data.objects.new('tmp', ta); bpy.context.scene.collection.objects.link(to)
    bpy.context.view_layer.objects.active = to; bpy.ops.object.mode_set(mode='EDIT')
    for n, s in rig.items():
        e = ta.edit_bones.new(n); e.head, e.tail = J[n]
        if (e.tail - e.head).length < 1e-4: e.tail = e.head + Vector((0, 0, 0.02))
    for n, s in rig.items():
        if s.get('parent'): ta.edit_bones[n].parent = ta.edit_bones[s['parent']]
    bpy.ops.object.mode_set(mode='OBJECT')
    # веса костей, которых нет в целевом скелете (у Soldier нет части фаланг), отдаём ближайшему существующему предку
    have = set(arm.data.bones.keys()); merged = {}
    for gname, lst in wts.items():
        g = gname
        while g not in have and rig.get(g, {}).get('parent'): g = rig[g]['parent']
        acc = merged.setdefault(g, {})
        for vi, w in lst: acc[vi] = acc.get(vi, 0) + w
    for gname, acc in merged.items():
        vg = ob.vertex_groups.new(name=gname)
        for vi, w in acc.items():
            if vi in remap: vg.add([remap[vi]], min(1.0, w), 'REPLACE')
    md = ob.modifiers.new('tpose', 'ARMATURE'); md.object = to
    bpy.context.view_layer.objects.active = to; bpy.ops.object.mode_set(mode='POSE')
    order = [n for n in rig]; done = set()
    def depth(n):
        d = 0
        while rig[n].get('parent'): n = rig[n]['parent']; d += 1
        return d
    for n in sorted(order, key=depth):
        c = child.get(n)
        if not c or c not in eb_rest or n not in eb_rest or c not in rig: continue
        bpy.context.view_layer.update()
        pb = to.pose.bones[n]
        cur_h = to.matrix_world @ pb.head
        cur_c = to.matrix_world @ to.pose.bones[c].head
        want = (eb_rest[c] - eb_rest[n]).normalized(); have = (cur_c - cur_h).normalized()
        if have.length < 1e-6 or want.length < 1e-6: continue
        q = have.rotation_difference(want)
        M = pb.matrix.copy(); R = q.to_matrix().to_4x4()
        T1 = Matrix.Translation(M.translation); M2 = T1 @ R @ Matrix.Translation(-M.translation) @ M
        pb.matrix = M2
    bpy.context.view_layer.update(); bpy.ops.object.mode_set(mode='OBJECT')
    # запекаем Т-позу в меш и снимаем суставы
    dg = bpy.context.evaluated_depsgraph_get(); ev = ob.evaluated_get(dg); nm = bpy.data.meshes.new_from_object(ev)
    ob.modifiers.remove(md); old = ob.data; ob.data = nm; nm.materials.clear(); nm.materials.append(old.materials[0])
    newJ = {n: (to.matrix_world @ to.pose.bones[n].head) for n in rig}
    if os.environ.get('HUMAN_DEBUG'):
        for n in ('mixamorig:LeftShoulder', 'mixamorig:LeftArm', 'mixamorig:LeftForeArm', 'mixamorig:LeftHand', 'mixamorig:LeftHandMiddle1'):
            print('J', n, [round(x, 3) for x in newJ[n]], 'soldier', [round(x, 3) for x in eb_rest.get(n, Vector())])
    bpy.data.objects.remove(to); bpy.data.armatures.remove(ta)
    # --- пересадка скелета arm: голова кости -> сустав тела, ориентация (и roll) прежние ---
    bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='EDIT')
    for e in arm.data.edit_bones: e.use_connect = False          # иначе перенос головы ребёнка повернёт родителя
    for e in arm.data.edit_bones:
        if e.name in newJ:
            d = e.tail - e.head; e.head = inv @ newJ[e.name]; e.tail = e.head + d
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in list(arm.children):
        if o.type == 'MESH': bpy.data.objects.remove(o)
    ob.parent = arm; ob.matrix_parent_inverse = arm.matrix_world.inverted()
    am = ob.modifiers.new('body', 'ARMATURE'); am.object = arm
    if subdiv:
        s = ob.modifiers.new('sub', 'SUBSURF'); s.levels = 1; s.render_levels = subdiv
    # глаза: склера + радужка, на месте маркеров суставов глаз (с учётом сдвига головы при Т-позе)
    dh = Vector(newJ['mixamorig:Head']) - Vector(J['mixamorig:Head'][0])
    eye_m = eye_material()
    for side in ('l', 'r'):
        g = JOINTS.get(f'joint-{side}-eye')
        if not g: continue
        c = Vector(B[sorted(g)].mean(0)) + dh
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.0118, location=c, segments=24, ring_count=16); e = bpy.context.object
        e.name = f'eye_{side}'; e.data.materials.append(eye_m); bpy.ops.object.shade_smooth()
        e.parent = arm; e.parent_type = 'BONE'; e.parent_bone = 'mixamorig:Head'
        bpy.context.view_layer.update(); e.matrix_world = Matrix.Translation(c)
    ob['joints'] = {k: list(v) for k, v in newJ.items()}
    return ob

def eye_material(iris=(0.22, 0.14, 0.06)):
    """Глаз смотрит вдоль +Y объекта: зрачок и радужка по косинусу от переднего полюса, мокрая роговица (coat)."""
    m = bpy.data.materials.new('eye'); m.use_nodes = True; N = m.node_tree.nodes; L = m.node_tree.links
    b = N['Principled BSDF']; b.inputs['Roughness'].default_value = 0.25; b.inputs['Coat Weight'].default_value = 1.0
    b.inputs['Coat Roughness'].default_value = 0.0
    tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    dv = N.new('ShaderNodeMath'); dv.operation = 'DIVIDE'; dv.inputs[1].default_value = 0.0118; L.new(sep.outputs['Y'], dv.inputs[0])
    r = N.new('ShaderNodeValToRGB'); e = r.color_ramp.elements
    e[0].position = 0.0; e[0].color = (0.8, 0.76, 0.72, 1); e[1].position = 0.83; e[1].color = (0.75, 0.7, 0.66, 1)
    for pos, col in ((0.845, (iris[0] * 0.6, iris[1] * 0.6, iris[2] * 0.6, 1)), (0.9, (*iris, 1)), (0.955, (iris[0] * 1.4, iris[1] * 1.3, iris[2], 1)),
                     (0.962, (0.004, 0.004, 0.004, 1)), (1.0, (0.004, 0.004, 0.004, 1))):
        n = e.new(pos); n.color = col
    L.new(dv.outputs[0], r.inputs['Fac']); L.new(r.outputs['Color'], b.inputs['Base Color'])
    return m
