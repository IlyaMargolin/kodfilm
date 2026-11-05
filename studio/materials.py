# Материалы из пульта стиля (look.material): то, что делает твёрдые поверхности «дорогими» в CGI, почти бесплатно.
#   bevel — фаска на рёбрах в шейдере (узел Bevel → нормаль): острое ребро ловит блик, как у настоящего пластика и металла.
#           Геометрию не трогаем: ни полигонов, ни времени сборки сцены; в Cycles это несколько лучей на шейдинг.
#   wear  — износ по впадинам: узел Ambient Occlusion находит стыки и углубления, туда кладём грязь (темнее, матовее),
#           на выступы — потёртость (светлее). Грязь «сама» садится туда, где её оставила бы жизнь.
# Применяется к материалам с Principled BSDF; эмиссия, волосы, кожа и глаза пропускаются (им фаска и грязь вредят).
import bpy

SKIP = ('hair', 'skin', 'eye', 'neon', 'fog', 'cornea', 'teeth', 'brow', 'lash')

def _principled(m):
    if not m or not m.use_nodes or any(k in m.name.lower() for k in SKIP): return None
    return next((n for n in m.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'), None)

def bevel(mats, radius=0.004):
    n_ok = 0
    for m in mats:
        p = _principled(m)
        if p is None or p.inputs['Normal'].is_linked: continue      # уже есть карта нормалей — не ломаем её
        b = m.node_tree.nodes.new('ShaderNodeBevel'); b.samples = 6; b.inputs['Radius'].default_value = radius
        m.node_tree.links.new(b.outputs['Normal'], p.inputs['Normal']); n_ok += 1
    return n_ok

def wear(mats, amount=0.5, distance=0.04):
    n_ok = 0
    for m in mats:
        p = _principled(m)
        if p is None: continue
        nt = m.node_tree; N, L = nt.nodes, nt.links
        ao = N.new('ShaderNodeAmbientOcclusion'); ao.samples = 8; ao.inputs['Distance'].default_value = distance
        # маска грязи: 1 во впадине, 0 на открытом месте
        inv = N.new('ShaderNodeMath'); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
        L.new(ao.outputs['AO'], inv.inputs[1])
        k = N.new('ShaderNodeMath'); k.operation = 'MULTIPLY'; k.inputs[1].default_value = amount; k.use_clamp = True
        L.new(inv.outputs[0], k.inputs[0])
        base = p.inputs['Base Color']; src = base.links[0].from_socket if base.is_linked else None
        mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
        ins = [s for s in mix.inputs if s.enabled]
        fac = next(s for s in ins if s.name == 'Factor'); A = next(s for s in ins if s.name == 'A'); B = next(s for s in ins if s.name == 'B')
        L.new(k.outputs[0], fac)
        if src: L.new(src, A)
        else: A.default_value = base.default_value
        B.default_value = (0.35, 0.3, 0.26, 1.0)           # грязь: тёплая тёмная, не чёрная
        L.new(next(s for s in mix.outputs if s.enabled), base)
        r = p.inputs['Roughness']
        if not r.is_linked:
            rm = N.new('ShaderNodeMath'); rm.operation = 'MULTIPLY_ADD'; rm.use_clamp = True
            L.new(k.outputs[0], rm.inputs[0]); rm.inputs[1].default_value = 0.4; rm.inputs[2].default_value = r.default_value
            L.new(rm.outputs[0], r)
        n_ok += 1
    return n_ok

def apply(lk, objects):
    """Материалы объектов (декорация, реквизит, роботы) по разделу look.material."""
    mt = lk.get('material', {}); mats = {s.material for o in objects if o.type == 'MESH' for s in o.material_slots if s.material}
    if mt.get('bevel'): print(f"материалы: фаска {mt['bevel'] * 1000:.0f} мм на {bevel(mats, mt['bevel'])} материалах", flush=True)
    if mt.get('wear'): print(f"материалы: износ {mt['wear']:.2f} на {wear(mats, mt['wear'])} материалах", flush=True)
    if mt.get('toon'): print('материалы: тун-заливка рисуется стилевым движком kodfilm-toon (в Cycles нет Shader to RGB)', flush=True)
