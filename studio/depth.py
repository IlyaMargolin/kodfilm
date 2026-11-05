# Объём кадра по точной глубине рендера: «лидар» движка. Рендер знает расстояние до каждого пикселя
# (проход Mist), и на нём держатся приёмы, которыми студии делают кадр объёмным, а не плоским:
#   1. воздушная перспектива — чем дальше, тем ниже контраст и тем ближе цвет к воздуху (Леонардо, Pixar, Дикинс);
#      воздух берём из самого кадра (сильно размытый кадр = рассеянный свет пространства) и тонируем палитрой,
#      поэтому дымка сама подстраивается под экспозицию: у окна светлая, в тёмном нефе тёмная;
#   2. небо почти не трогаем (оно и так «воздух»), иначе закат тускнеет;
#   3. сила зависит от плана: на общем плане глубины много, на крупном воздух между камерой и лицом не нужен.
# Стоимость: два узла размытия и смешивание в композиторе, без перерендера и без лишних сэмплов.
import bpy
import palette

# доля смешивания с воздухом на дальней границе (far) по крупности плана
K_SIZE = {'EWS': 0.6, 'WS': 0.52, 'FS': 0.45, 'MS': 0.36, 'MCU': 0.22, 'CU': 0.15, 'ECU': 0.1, 'INS': 0.1}   # замер на Храме: 0.36 на общем почти не видно
MIST_GAMMA = 0.7      # воздух копится быстрее вблизи и медленнее вдали (как 1 − e^(−d/D)): средний план тоже отходит назад
SKY_K = 0.25          # доля силы для неба (mist = 1)
AIR_GAIN = 1.6        # воздух светится: рассеянный в дымке свет ярче среднего отражения стен (замер: ×1 в тёмном нефе не видно)
FAR = {'sponza': 18.0, 'loft': 12.0}   # дистанция полной дымки по миру: в интерьере воздух «съедает» дальнюю стену, снаружи — горизонт

def _node(ng, t, **inputs):
    n = ng.nodes.new(t)
    for k, v in inputs.items():
        s = n.inputs.get(k) if isinstance(k, str) else n.inputs[k]
        if s is not None: s.default_value = v
    return n

def _math(ng, op, a=None, b=None):
    n = ng.nodes.new('ShaderNodeMath'); n.operation = op
    for i, v in enumerate((a, b)):
        if v is None: continue
        if isinstance(v, (int, float)): n.inputs[i].default_value = v
        else: ng.links.new(v, n.inputs[i])
    return n.outputs[0]

def _mix_rgba(ng, fac, a, b):
    m = ng.nodes.new('ShaderNodeMix'); m.data_type = 'RGBA'; m.blend_type = 'MIX'; m.clamp_factor = True
    ins = [s for s in m.inputs if s.enabled]
    f = next(s for s in ins if s.name == 'Factor'); A = next(s for s in ins if s.name == 'A'); B = next(s for s in ins if s.name == 'B')
    for sock, v in ((f, fac), (A, a), (B, b)):
        if isinstance(v, tuple): sock.default_value = v
        elif isinstance(v, (int, float)): sock.default_value = v
        else: ng.links.new(v, sock)
    return next(s for s in m.outputs if s.enabled)

def setup(scene, start=1.5, far=40.0):
    """Узлы воздушной перспективы перед грейдом. far — дистанция, на которой дымка достигает полной силы плана."""
    ng = scene.compositing_node_group
    if ng is None or 'grade' not in ng.nodes: return None
    vl = scene.view_layers[0]; vl.use_pass_mist = True
    if scene.world:
        ms = scene.world.mist_settings; ms.start = start; ms.depth = far; ms.falloff = 'LINEAR'
    rl = next(n for n in ng.nodes if n.bl_idname == 'CompositorNodeRLayers')
    cb = ng.nodes['grade']; img_in = cb.inputs.get('Image') or cb.inputs[-1]
    src = img_in.links[0].from_socket
    # воздух: кадр, размытый до пятен света (~12% ширины), умноженный на тон палитры
    bl = ng.nodes.new('CompositorNodeBlur'); bl.name = 'depth_air_blur'
    try: bl.inputs['Type'].default_value = 'Fast Gaussian'
    except Exception: pass
    bl.inputs['Size'].default_value = (scene.render.resolution_x * 0.12,) * 2 if len(bl.inputs['Size'].default_value) == 2 else (scene.render.resolution_x * 0.12,) * 3
    ng.links.new(src, bl.inputs['Image'])
    tint = ng.nodes.new('CompositorNodeRGB'); tint.name = 'depth_tint'; tint.outputs[0].default_value = (1, 1, 1, 1)
    gain = ng.nodes.new('CompositorNodeRGB'); gain.outputs[0].default_value = (AIR_GAIN,) * 3 + (1.0,)
    air = _mix_rgba(ng, 1.0, bl.outputs[0], tint.outputs[0]); air.node.blend_type = 'MULTIPLY'
    air = _mix_rgba(ng, 1.0, air, gain.outputs[0]); air.node.blend_type = 'MULTIPLY'
    # сила: k·mist для геометрии, k·SKY_K для неба
    kk = ng.nodes.new('ShaderNodeValue'); kk.name = 'depth_k'; kk.outputs[0].default_value = 0.0
    # проход Mist шумит там, где луч проходит объёмный туман (точки по всему кадру): сглаживаем его с сохранением
    # краёв — двусторонний фильтр по уже очищенному кадру, чтобы дымка не «перелезала» через силуэт героя
    bb = ng.nodes.new('CompositorNodeBilateralblur'); bb.name = 'depth_mist_clean'
    bb.inputs['Size'].default_value = max(3, scene.render.resolution_x // 160); bb.inputs['Threshold'].default_value = 0.15
    ng.links.new(rl.outputs['Mist'], bb.inputs['Image']); ng.links.new(rl.outputs['Image'], bb.inputs['Determinator'])
    sepc = ng.nodes.new('CompositorNodeSeparateColor'); ng.links.new(bb.outputs[0], sepc.inputs[0])
    mist = sepc.outputs['Red']
    sky = _math(ng, 'GREATER_THAN', mist, 0.9995)
    geo = _math(ng, 'MULTIPLY', _math(ng, 'POWER', mist, MIST_GAMMA), _math(ng, 'SUBTRACT', 1.0, sky))
    w = _math(ng, 'ADD', geo, _math(ng, 'MULTIPLY', sky, SKY_K))
    fac = _math(ng, 'MULTIPLY', w, kk.outputs[0])
    out = _mix_rgba(ng, fac, src, air)
    ng.links.new(out, img_in)
    return ng

def apply(scene, p, size, haze=1.0):
    """Перед кадром: тон воздуха из палитры плана и сила по крупности. haze — множитель оператора (дымка сцены)."""
    ng = scene.compositing_node_group
    if ng is None or 'depth_k' not in ng.nodes: return
    ng.nodes['depth_k'].outputs[0].default_value = min(0.75, K_SIZE.get(size, 0.3) * haze)
    if p:
        c = tuple(0.5 * a + 0.5 * b for a, b in zip(p['key'], p['hi']))   # воздух светится светом сцены
        ng.nodes['depth_tint'].outputs[0].default_value = (*palette._tint(c, 0.35), 1.0)
