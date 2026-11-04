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

def shape(gender=1.0, age=0.5, muscle=0.5, weight=0.5, height=0.5, proportions=0.5, race=None, detail=None):
    import anatomy
    race = anatomy.race(race)
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
    # черты лица и тела по анатомии (studio/anatomy.py): диморфизм, силуэт, возраст, асимметрия
    for t, w in (detail or {}).items():
        _add(V, os.path.join(MH, 'targets', t + '.target.gz'), w)
    # obj: Y вверх, дециметры -> Blender: Z вверх, метры, стопы на z=0
    B = np.stack([-V[:, 0], V[:, 2], V[:, 1]], 1) * 0.1   # лицом к +Y, как скелеты Mixamo из GLB
    B[:, 2] -= B[:, 2].min() if False else B[[f for fc in faces for f in fc], 2].min()
    return B, vts, faces, fuv

# ---------- прокси MakeHuman (CC0): брови, ресницы, глаза — геометрия, привязанная к базовой сетке ----------
SYS = os.path.join(MH, 'system')

def _proxy(kind, name):
    """Читает .mhclo + .obj: вершина прокси = Σ w·V[v1..v3] + смещение·масштаб (масштаб по осям базовой сетки)."""
    name, _, matname = name.partition(':')       # 'high-poly:brown' — меш глаз + материал радужки
    d = os.path.join(SYS, kind, name)
    if not os.path.isdir(d): return None
    clo = next(os.path.join(d, f) for f in os.listdir(d) if f.endswith('.mhclo'))
    sc = {}; refs = []; objf = None; mat = None; inv = False
    for l in open(clo, encoding='utf-8', errors='ignore'):
        p = l.split()
        if not p or p[0].startswith('#'): continue
        if p[0] in ('x_scale', 'y_scale', 'z_scale'): sc[p[0][0]] = (int(p[1]), int(p[2]), float(p[3])); continue
        if p[0] == 'obj_file': objf = os.path.join(d, p[1]); continue
        if p[0] == 'material': mat = os.path.normpath(os.path.join(d, p[1])); continue
        if p[0] == 'verts': inv = True; continue
        if inv and p[0].lstrip('-').isdigit():
            if len(p) >= 9: refs.append(([int(x) for x in p[:3]], [float(x) for x in p[3:6]], [float(x) for x in p[6:9]]))
            elif len(p) == 1: refs.append(([int(p[0])] * 3, [1.0, 0, 0], [0.0, 0, 0]))
            continue
        if inv and p[0].isalpha(): inv = False
    vs, vts, faces, fuv = [], [], [], []
    for l in open(objf):
        if l.startswith('v '): vs.append(tuple(map(float, l.split()[1:4])))
        elif l.startswith('vt '): q = l.split(); vts.append((float(q[1]), float(q[2])))
        elif l.startswith('f '):
            idx = [q.split('/') for q in l.split()[1:]]
            faces.append([int(i[0]) - 1 for i in idx]); fuv.append([int(i[1]) - 1 if len(i) > 1 and i[1] else 0 for i in idx])
    if matname: mat = os.path.join(SYS, kind, 'materials', matname + '.mhmat')
    if not mat:
        mm = next((f for f in os.listdir(d) if f.endswith('.mhmat')), None); mat = os.path.join(d, mm) if mm else None
    tex = None
    if mat and os.path.exists(mat):
        for l in open(mat, encoding='utf-8', errors='ignore'):
            if l.startswith('diffuseTexture'): tex = os.path.join(os.path.dirname(mat), l.split()[1])
    return dict(refs=refs[:len(vs)], scale=sc, faces=faces, fuv=fuv, vts=vts, tex=tex, name=name, kind=kind)

def _fit(B, px):
    """координаты прокси в осях Blender. B — базовая сетка уже в Blender (x=-X, y=Z, z=Y, метры)."""
    O = B * np.array([-10.0, 10.0, 10.0])            # назад в оси obj (дециметры): X=-Bx, Y=Bz, Z=By
    Oy, Oz = O[:, 2].copy(), O[:, 1].copy(); O[:, 1], O[:, 2] = Oy, Oz
    s = {}
    for ax, i in (('x', 0), ('y', 1), ('z', 2)):
        a, b, den = px['scale'].get(ax, (0, 0, 1.0)); s[i] = abs(O[a, i] - O[b, i]) / den if den else 1.0
    out = []
    for vi, w, off in px['refs']:
        c = O[vi[0]] * w[0] + O[vi[1]] * w[1] + O[vi[2]] * w[2] + np.array([off[0] * s[0], off[1] * s[1], off[2] * s[2]])
        out.append((-c[0] * 0.1, c[2] * 0.1, c[1] * 0.1))
    return out

def proxy_material(px, color=(0.03, 0.022, 0.016)):
    """брови/ресницы: альфа из текстуры, цвет — цвет волос; глаза: фото радужки + влажная роговица."""
    m = bpy.data.materials.new(px['name']); m.use_nodes = True; N, L = m.node_tree.nodes, m.node_tree.links
    b = N['Principled BSDF']
    t = N.new('ShaderNodeTexImage')
    if px['tex'] and os.path.exists(px['tex']): t.image = bpy.data.images.load(px['tex'], check_existing=True)
    t.interpolation = 'Cubic'
    if px['kind'] == 'eyes':
        # фото радужки MakeHuman красноватое: под тёплым ключом глаз читается «альбиносом» — приглушаем насыщенность и яркость
        hsv = N.new('ShaderNodeHueSaturation'); hsv.inputs['Saturation'].default_value = 0.72; hsv.inputs['Value'].default_value = 0.8
        L.new(t.outputs['Color'], hsv.inputs['Color']); L.new(hsv.outputs['Color'], b.inputs['Base Color']); b.inputs['Roughness'].default_value = 0.35
        b.inputs['Coat Weight'].default_value = 1.0; b.inputs['Coat Roughness'].default_value = 0.02; b.inputs['Coat IOR'].default_value = 1.376
        if 'Subsurface Weight' in b.inputs: b.inputs['Subsurface Weight'].default_value = 0.15; b.inputs['Subsurface Scale'].default_value = 0.002
        # роговица — отдельная оболочка с UV в прозрачном углу текстуры: альфа обязательна, иначе глаз «чёрная бусина»
        L.new(t.outputs['Alpha'], b.inputs['Alpha'])
    else:
        b.inputs['Base Color'].default_value = (*[c * 0.8 for c in color], 1); b.inputs['Roughness'].default_value = 0.55
        if 'Sheen Weight' in b.inputs: b.inputs['Sheen Weight'].default_value = 0.3
        L.new(t.outputs['Alpha'], b.inputs['Alpha'])
        try: m.surface_render_method = 'DITHERED'
        except Exception: pass
    return m

def macro_from_spec(hs):
    """Блок "human" из карточки актёра → параметры build(): макро + раса + анатомия.
    "race": "caucasian" | {…}; "anatomy": ["masculine", "gaunt", "aged", "asym"]; "targets": {"nose/nose-hump-incr": 0.3}."""
    import anatomy
    m = {k: hs[k] for k in ('gender', 'age', 'muscle', 'weight', 'height', 'proportions') if k in hs}
    m['race'] = hs.get('race')
    m['detail'] = anatomy.mix(hs.get('anatomy', ['asym']), hs.get('targets'), hs.get('gender', 1.0))
    return m

def eyes_world(body, arm, head='mixamorig:Head'):
    """Где сейчас глаза (мир): покойная позиция глаз, перенесённая позой кости головы. Нужна для фокуса —
    резкость кино ставят на ближний глаз, а не на центр черепа (на 85 мм f/2.8 разница 9 см = «мыло» лица)."""
    if 'eyes' not in body or head not in arm.pose.bones: return None
    pb = arm.pose.bones[head]; M = arm.matrix_world @ pb.matrix @ pb.bone.matrix_local.inverted() @ arm.matrix_world.inverted()
    return [M @ (body.matrix_world @ Vector(e)) for e in body['eyes']]

def build_actor(arm, hs, name='human'):
    """Карточка актёра (блок "human") → готовое тело: анатомия, фото-кожа, брови, ресницы, глаза."""
    hair = tuple(hs.get('hair', (0.03, 0.022, 0.016)))
    skin = skin_material(tuple(hs.get('skin', (0.62, 0.43, 0.33))), hair, hs.get('stubble', 0.6 if hs.get('gender', 1) > 0.5 else 0),
                         texture=hs.get('skin_texture'))
    px = []
    if hs.get('eyebrows'): px.append(('eyebrows', hs['eyebrows']))
    if hs.get('eyelashes'): px.append(('eyelashes', hs['eyelashes']))
    if hs.get('eyes'): px.append(('eyes', 'high-poly:' + hs['eyes']))
    return build(arm, name, skin=skin, subdiv=hs.get('subdiv', 2), proxies=px, hair_color=hair, **macro_from_spec(hs))

def _joint(B, spec):
    if spec.get('strategy') == 'CUBE' and spec.get('cube_name') in JOINTS:      # центр маркера сустава (CUBE)
        return Vector(B[sorted(JOINTS[spec['cube_name']])].mean(0))
    idx = spec.get('vertex_indices') or []
    if idx: return Vector(B[idx].mean(0))
    return Vector(spec['default_position'])

def _img(name):
    p = os.path.join(MH, 'textures', name)
    if not os.path.exists(p): return None
    im = bpy.data.images.load(p, check_existing=True); im.colorspace_settings.name = 'Non-Color'; return im

def skin_material(tone=(0.62, 0.43, 0.33), hair=(0.03, 0.022, 0.016), stubble=0.0, texture=None, painted_brows=None):
    """Кожа: подповерхностное рассеяние, поры, румянец губ и век по UV-маскам MakeHuman (CC0),
    брови и щетина — по маске в атрибуте face_mask (R — брови, G — щетина), её считает build()."""
    # тон задан как цвет на экране (sRGB, как в справочниках по коже), шейдеру нужен линейный: 0.55 sRGB = 0.26 линейно.
    # Без перевода кожа выходит фарфоровой — «кукольное» лицо
    tone = tuple(c ** 2.2 for c in tone)
    m = bpy.data.materials.new('skin'); m.use_nodes = True; N = m.node_tree.nodes; L = m.node_tree.links
    b = N['Principled BSDF']
    b.inputs['Roughness'].default_value = 0.5
    for k, v in (('Subsurface Weight', 0.6), ('Subsurface Scale', 0.006), ('Specular IOR Level', 0.45), ('Coat Weight', 0.05), ('Coat Roughness', 0.35)):
        if k in b.inputs: b.inputs[k].default_value = v
    if 'Subsurface Radius' in b.inputs: b.inputs['Subsurface Radius'].default_value = (1.0, 0.35, 0.2)
    tc = N.new('ShaderNodeTexCoord')
    def mix(a_sock, col, fac_sock, k=1.0):
        mx = N.new('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MIX'
        if isinstance(a_sock, tuple): mx.inputs[6].default_value = (*a_sock, 1)
        else: L.new(a_sock, mx.inputs[6])
        mx.inputs[7].default_value = (*col, 1)
        mm = N.new('ShaderNodeMath'); mm.operation = 'MULTIPLY'; mm.inputs[1].default_value = k; L.new(fac_sock, mm.inputs[0])
        L.new(mm.outputs[0], mx.inputs['Factor']); return mx.outputs[2]
    # пятнистость кожи
    nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 60; nz2.inputs['Detail'].default_value = 6; L.new(tc.outputs['Object'], nz2.inputs['Vector'])
    col = mix(tone, (tone[0] * 1.08, tone[1] * 0.82, tone[2] * 0.8), nz2.outputs['Fac'], 0.35)
    tex = None
    if texture:
        # фотографическая карта кожи MakeHuman (CC0): веснушки, сосуды, тени щетины, губы и веки — с реального человека.
        # Тон актёра задаётся умножением: средний цвет карты (≈ sRGB 0.86/0.72/0.62) приводится к нужному.
        d = os.path.join(MH, 'system', 'skins', texture)
        f = next((x for x in os.listdir(d) if x.endswith('_diffuse.png')), None) if os.path.isdir(d) else None
        if f:
            tex = N.new('ShaderNodeTexImage'); tex.image = bpy.data.images.load(os.path.join(d, f), check_existing=True); tex.interpolation = 'Cubic'
            L.new(tc.outputs['UV'], tex.inputs['Vector'])
            ref = (0.72, 0.49, 0.35); tint = tuple(min(2.0, t / r) for t, r in zip(tone, ref))
            mt = N.new('ShaderNodeMix'); mt.data_type = 'RGBA'; mt.blend_type = 'MULTIPLY'; mt.inputs[0].default_value = 1.0
            L.new(tex.outputs['Color'], mt.inputs[6]); mt.inputs[7].default_value = (*tint, 1)
            # лёгкая пятнистость поверх фото: кожа на солнце неровная
            mv = N.new('ShaderNodeMix'); mv.data_type = 'RGBA'; mv.blend_type = 'MULTIPLY'; L.new(nz2.outputs['Fac'], mv.inputs[0])
            L.new(mt.outputs[2], mv.inputs[6]); mv.inputs[7].default_value = (1.06, 0.9, 0.86, 1)
            mm_ = N.new('ShaderNodeMath'); mm_.operation = 'MULTIPLY'; mm_.inputs[1].default_value = 0.35; L.new(nz2.outputs['Fac'], mm_.inputs[0]); L.new(mm_.outputs[0], mv.inputs[0])
            col = mv.outputs[2]
    if painted_brows is None: painted_brows = tex is None
    for name, c, k in (('mpfb_lips.jpg', (tone[0] * 0.85, tone[1] * 0.5, tone[2] * 0.5), 0.75), ('mpfb_eyelids.jpg', (tone[0] * 0.75, tone[1] * 0.6, tone[2] * 0.62), 0.5),
                       ('mpfb_fingernails.jpg', (tone[0] * 1.15, tone[1] * 1.0, tone[2] * 1.0), 0.8)):
        im = _img(name)
        if im and tex is None:
            t = N.new('ShaderNodeTexImage'); t.image = im; L.new(tc.outputs['UV'], t.inputs['Vector']); col = mix(col, c, t.outputs['Color'], k)
    fm = N.new('ShaderNodeVertexColor'); fm.layer_name = 'face_mask'; sp = N.new('ShaderNodeSeparateColor'); L.new(fm.outputs['Color'], sp.inputs[0])
    hn = N.new('ShaderNodeTexNoise'); hn.inputs['Scale'].default_value = 2500; hn.inputs['Detail'].default_value = 2; L.new(tc.outputs['Object'], hn.inputs['Vector'])
    br = N.new('ShaderNodeMath'); br.operation = 'MULTIPLY'; L.new(sp.outputs['Red'], br.inputs[0]); L.new(hn.outputs['Fac'], br.inputs[1])
    br2 = N.new('ShaderNodeMath'); br2.operation = 'MULTIPLY'; br2.inputs[1].default_value = 1.25; br2.use_clamp = True; L.new(br.outputs[0], br2.inputs[0])
    if painted_brows: col = mix(col, hair, br2.outputs[0], 1.0)
    if stubble > 0:
        st = N.new('ShaderNodeMath'); st.operation = 'MULTIPLY'; L.new(sp.outputs['Green'], st.inputs[0]); L.new(hn.outputs['Fac'], st.inputs[1])
        col = mix(col, (hair[0] * 2, hair[1] * 2, hair[2] * 2), st.outputs[0], 1.2 * stubble)
    L.new(col, b.inputs['Base Color'])
    # поры
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 900; nz.inputs['Detail'].default_value = 4; L.new(tc.outputs['Object'], nz.inputs['Vector'])
    hb = N.new('ShaderNodeMath'); hb.operation = 'ADD'; L.new(nz.outputs['Fac'], hb.inputs[0]); L.new(br.outputs[0], hb.inputs[1])
    # вторая октава пор (мельче) и шероховатость пятнами: Т-зона блестит, щёки матовые — кожа не «пластик»
    nzf = N.new('ShaderNodeTexNoise'); nzf.inputs['Scale'].default_value = 2600; nzf.inputs['Detail'].default_value = 2; L.new(tc.outputs['Object'], nzf.inputs['Vector'])
    hb2 = N.new('ShaderNodeMath'); hb2.operation = 'MULTIPLY_ADD'; L.new(nzf.outputs['Fac'], hb2.inputs[0]); hb2.inputs[1].default_value = 0.6; L.new(hb.outputs[0], hb2.inputs[2]); hb = hb2
    rr = N.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = 0.38; rr.inputs['To Max'].default_value = 0.62; L.new(nz2.outputs['Fac'], rr.inputs['Value']); L.new(rr.outputs['Result'], b.inputs['Roughness'])
    bp = N.new('ShaderNodeBump'); bp.inputs['Strength'].default_value = 0.22; bp.inputs['Distance'].default_value = 0.0005
    L.new(hb.outputs[0], bp.inputs['Height']); L.new(bp.outputs['Normal'], b.inputs['Normal'])
    return m

def face_mask(ob, eye_l, eye_r):
    """Маска бровей (R) и щетины (G) в атрибуте face_mask по геометрии головы относительно глаз."""
    E = (eye_l + eye_r) / 2; X = (eye_l - eye_r).normalized(); Z = Vector((0, 0, 1)); Y = Z.cross(X).normalized()
    if Y.y < 0: Y = -Y
    ca = ob.data.color_attributes.new('face_mask', 'FLOAT_COLOR', 'POINT')
    sm = lambda x, a, b: max(0.0, min(1.0, (x - a) / (b - a)))
    for v in ob.data.vertices:
        d = v.co - E; x, y, z = d.dot(X), d.dot(Y), d.dot(Z)
        brow = 0.0
        for ex in (eye_l, eye_r):
            dx = (v.co - ex).dot(X)
            arch = 0.016 + 0.006 * (1 - (dx / 0.03) ** 2)
            if y > -0.005 and abs(dx) < 0.03:
                brow = max(brow, sm(z - (ex - E).dot(Z), arch - 0.006, arch - 0.002) * (1 - sm(z - (ex - E).dot(Z), arch + 0.002, arch + 0.007)) * (1 - sm(abs(dx), 0.022, 0.03)))
        stub = 0.0
        if y > -0.07 and abs(x) < 0.075:
            stub = sm(-z, 0.055, 0.07) * (1 - sm(-z, 0.125, 0.14)) * (1 - sm(abs(x), 0.06, 0.075))
            mouth = sm(-z, 0.075, 0.08) * (1 - sm(-z, 0.092, 0.097)) * (1 - sm(abs(x), 0.0, 0.028))
            stub *= (1 - mouth)
        ca.data[v.index].color = (brow, stub, 0, 1)

def build(arm, name='human', skin=None, subdiv=1, proxies=(), hair_color=(0.03, 0.022, 0.016), **macro):
    """Строит тело и пересаживает скелет arm (Mixamo) в его суставы. Меши, которые были у arm, удаляются."""
    pp = arm.data.pose_position; arm.data.pose_position = 'REST'   # строим всё в позе покоя, иначе текущая анимация исказит привязку
    try: return _build(arm, name, skin, subdiv, proxies, hair_color, **macro)
    finally: arm.data.pose_position = pp; bpy.context.view_layer.update()

def _build(arm, name, skin, subdiv, proxies, hair_color, **macro):
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
    # прокси (брови, ресницы, глаза) вливаем в меш тела: они едут через ту же Т-позу и скелет, веса — от опорных вершин
    PXW = {}; PXR = []; px_eyes = False; ob['proxy_start'] = len(me.vertices)     # всё, что дальше, — не кожа (одежда это не копирует)
    for kind, pname in proxies:
        px = _proxy(kind, pname)
        if not px: print('нет прокси', kind, pname); continue
        P = _fit(B, px); bm = bmesh.new(); bm.from_mesh(me); n0 = len(bm.verts)
        nv = [bm.verts.new(c) for c in P]; bm.verts.ensure_lookup_table()
        me.materials.append(proxy_material(px, hair_color)); mi = len(me.materials) - 1
        uvl = bm.loops.layers.uv.active or bm.loops.layers.uv.new('UV')
        for f, fu in zip(px['faces'], px['fuv']):
            try: nf = bm.faces.new([nv[i] for i in f])
            except ValueError: continue
            nf.material_index = mi; nf.smooth = True
            for lp, ui in zip(nf.loops, fu):
                if ui < len(px['vts']): lp[uvl].uv = px['vts'][ui]
        bm.to_mesh(me); bm.free(); PXR.append((n0, n0 + len(P), mi))
        for k, (vi, w, off) in enumerate(px['refs']): PXW[n0 + k] = list(zip(vi, w))
        if kind == 'eyes': px_eyes = True

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
        for n, lst in PXW.items():           # вершины прокси: смесь весов трёх опорных вершин
            w = sum(acc.get(vi, 0.0) * ww for vi, ww in lst)
            if w > 1e-4: vg.add([n], min(1.0, w), 'REPLACE')
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
    ob.modifiers.remove(md); old = ob.data; ob.data = nm; nm.materials.clear()
    for m_ in old.materials: nm.materials.append(m_)       # кожа + материалы прокси (брови, ресницы, глаза)
    if PXR:   # индексы материалов прокси по диапазонам вершин (запекание через depsgraph их не сохраняет)
        fv = [0] * len(nm.polygons); fi = [0] * len(nm.polygons)
        nm.polygons.foreach_get('loop_start', fv)
        for p_ in nm.polygons:
            v0 = nm.loops[p_.loop_start].vertex_index
            for a_, b_, m__ in PXR:
                if a_ <= v0 < b_: fi[p_.index] = m__; break
        nm.polygons.foreach_set('material_index', fi)
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
    # длина кости до сустава-ребёнка (направление и roll прежние, анимация не меняется):
    # хвост голени = голеностоп, хвост плеча = локоть — на этом держится IK опоры стоп
    for e in arm.data.edit_bones:
        kids = [c for c in e.children if c.name in newJ]
        if len(kids) == 1 and e.name in newJ:
            d = (e.tail - e.head).normalized(); L = (kids[0].head - e.head).dot(d)
            if L > 0.5: e.tail = e.head + d * L     # хвосты у мокап-скелета бывают «в 40 м» — приводим к суставу
    bpy.ops.object.mode_set(mode='OBJECT')
    for o in list(arm.children):
        if o.type == 'MESH': bpy.data.objects.remove(o)
    ob.parent = arm; ob.matrix_parent_inverse = arm.matrix_world.inverted()
    am = ob.modifiers.new('body', 'ARMATURE'); am.object = arm
    cs = ob.modifiers.new('corrective', 'CORRECTIVE_SMOOTH'); cs.rest_source = 'ORCO'; cs.smooth_type = 'LENGTH_WEIGHTED'; cs.iterations = 6; cs.factor = 0.7   # суставы без «заломов»
    if subdiv:
        s = ob.modifiers.new('sub', 'SUBSURF'); s.levels = 1; s.render_levels = subdiv
    # глаза: склера + радужка, на месте маркеров суставов глаз (с учётом сдвига головы при Т-позе)
    dh = Vector(newJ['mixamorig:Head']) - Vector(J['mixamorig:Head'][0])
    EYEC = {}; EYES = {}
    for side in ('l', 'r'):
        g = JOINTS.get(f'joint-{side}-eye')
        if not g: continue
        c0 = B[sorted(g)].mean(0)
        ring = [remap[i] for i in np.where(np.linalg.norm(B - c0, axis=1) < 0.017)[0] if i in remap]   # веки вокруг глаза после Т-позы
        c = (sum((ob.data.vertices[i].co for i in ring), Vector()) / len(ring)) if ring else Vector(c0) + dh
        c = ob.matrix_world @ c; EYES[side] = c
        if px_eyes: EYEC[side] = c; continue      # глаза уже из прокси (фото радужки), свои сферы не нужны
        eye_m = bpy.data.materials.get('eye_tmp') or bpy.data.materials.new('eye_tmp')
        # глазное яблоко — часть меша тела, вес головы 1.0: едет с головой при любой анимации, без родителей и смещений
        bm = bmesh.new(); bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=0.0118)
        for v in bm.verts: v.co = ob.matrix_world.inverted() @ (c + v.co)
        n0 = len(ob.data.vertices); bm2 = bmesh.new(); bm2.from_mesh(ob.data)
        mi = len(ob.data.materials)
        if eye_m.name not in [m.name for m in ob.data.materials if m]: ob.data.materials.append(eye_m)
        mi = [m.name for m in ob.data.materials].index(eye_m.name)
        vmap = {v: bm2.verts.new(v.co) for v in bm.verts}
        for f in bm.faces:
            nf = bm2.faces.new([vmap[v] for v in f.verts]); nf.material_index = mi; nf.smooth = True
        bm2.to_mesh(ob.data); bm.free(); bm2.free()
        hg = ob.vertex_groups.get('mixamorig:Head') or ob.vertex_groups.new(name='mixamorig:Head')
        hg.add(list(range(n0, len(ob.data.vertices))), 1.0, 'REPLACE')
        # центр глаза в атрибуте для шейдера: Object-координаты меша общие, поэтому радужку рисуем от центра каждого глаза
        EYEC[side] = c
    if len(EYES) == 2:
        face_mask(ob, EYES['l'], EYES['r'])
        if 'eye_tmp' in [x.name for x in ob.data.materials]:
            m = eye_material(EYES['l'], EYES['r']); ob.data.materials[[x.name for x in ob.data.materials].index('eye_tmp')] = m
    ob['joints'] = {k: list(v) for k, v in newJ.items()}
    if len(EYES) == 2: ob['eyes'] = [list(ob.matrix_world.inverted() @ EYES['l']), list(ob.matrix_world.inverted() @ EYES['r'])]
    return ob

def eye_material(cl, cr, iris=(0.22, 0.14, 0.06), r=0.0118):
    """Глаза внутри меша тела: координата Object (покой) минус центр ближнего глаза; зрачок там, где вектор смотрит в +Y."""
    m = bpy.data.materials.new('eye'); m.use_nodes = True; N = m.node_tree.nodes; L = m.node_tree.links
    b = N['Principled BSDF']; b.inputs['Roughness'].default_value = 0.3; b.inputs['Coat Weight'].default_value = 1.0
    b.inputs['Coat Roughness'].default_value = 0.0
    tc = N.new('ShaderNodeTexCoord'); sep = N.new('ShaderNodeSeparateXYZ'); L.new(tc.outputs['Object'], sep.inputs[0])
    # выбор глаза по знаку X относительно середины
    mid = (cl.x + cr.x) / 2
    def comp(cx):
        dy = N.new('ShaderNodeMath'); dy.operation = 'SUBTRACT'; L.new(sep.outputs['Y'], dy.inputs[0]); dy.inputs[1].default_value = cl.y
        dv = N.new('ShaderNodeMath'); dv.operation = 'DIVIDE'; dv.inputs[1].default_value = r; L.new(dy.outputs[0], dv.inputs[0]); return dv
    v = comp(cl.x)
    rmp = N.new('ShaderNodeValToRGB'); e = rmp.color_ramp.elements
    e[0].position = 0.0; e[0].color = (0.8, 0.76, 0.72, 1); e[1].position = 0.83; e[1].color = (0.75, 0.7, 0.66, 1)
    for pos, col in ((0.845, (iris[0] * 0.5, iris[1] * 0.5, iris[2] * 0.5, 1)), (0.9, (*iris, 1)), (0.955, (iris[0] * 1.4, iris[1] * 1.3, iris[2], 1)),
                     (0.962, (0.004, 0.004, 0.004, 1)), (1.0, (0.004, 0.004, 0.004, 1))):
        n = e.new(pos); n.color = col
    L.new(v.outputs[0], rmp.inputs['Fac']); L.new(rmp.outputs['Color'], b.inputs['Base Color'])
    return m
