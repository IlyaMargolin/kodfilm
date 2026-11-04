"""Линза в композиторе Blender (работает на HDR-данных рендера, до тонмаппинга кадра в файл):
блум от ярких источников, анаморфные горизонтальные блики, призрачные отражения и хроматическая аберрация.
Яркость порогов в линейных единицах сцены: срабатывает только на реальных засветах (солнце, лампы, металл)."""
import bpy, os

LOOKS = {
    # имя: (bloom_thr, bloom_str, streak_thr, streak_str, ghosts_str, dispersion)
    'clean':      (1.2, 0.25, 9.0, 0.0,  0.0,  0.004),
    'cinema':     (1.0, 0.40, 6.0, 0.10, 0.02, 0.008),   # по умолчанию: Дикинс-сдержанно; блики-лучи только от солнца/ламп, не от металла
    'anamorphic': (0.9, 0.50, 1.8, 0.30, 0.06, 0.016),   # Нолан/Абрамс: синие горизонтальные блики
    'dream':      (0.6, 0.85, 2.5, 0.10, 0.04, 0.020),   # Миядзаки/сказка: мягкое сияние
}

def _set(node, name, val):
    s = node.inputs.get(name)
    if s is not None:
        try: s.default_value = val
        except Exception: pass

def setup(scene, look='cinema'):
    bt, bs, st, ss, gs, disp = LOOKS.get(look, LOOKS['cinema'])
    ng = bpy.data.node_groups.new('lens', 'CompositorNodeTree')
    scene.compositing_node_group = ng
    N, L = ng.nodes, ng.links
    rl = N.new('CompositorNodeRLayers')
    out = N.new('NodeGroupOutput'); ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    cur = rl.outputs['Image']
    def glare(kind, thr, strength, **kw):
        nonlocal cur
        if strength <= 0: return
        g = N.new('CompositorNodeGlare')
        _set(g, 'Type', kind); _set(g, 'Quality', 'High')
        _set(g, 'Threshold', thr); _set(g, 'Strength', strength)
        for k, v in kw.items(): _set(g, k, v)
        L.new(cur, g.inputs['Image']); cur = g.outputs['Image']
    glare('Bloom', bt, bs, Size=0.6, Smoothness=0.3)
    glare('Streaks', st, ss, Streaks=2, **{'Streaks Angle': 0.0, 'Fade': 0.93, 'Tint': (0.55, 0.75, 1.0, 1.0)})
    glare('Ghosts', st * 1.3, gs)
    if disp > 0:
        ld = N.new('CompositorNodeLensdist')
        _set(ld, 'Dispersion', disp); _set(ld, 'Distortion', 0.0); _set(ld, 'Fit', True)
        L.new(cur, ld.inputs['Image']); cur = ld.outputs['Image']
    L.new(cur, out.inputs[0])
    return ng

def passes(scene, outdir, mist_far=60.0):
    """Рендер по слоям, как у студий (AOV): на каждый кадр multilayer EXR с точной глубиной, туманом-дистанцией и нормалями,
    плюс 16-битный PNG дистанции — точная карта глубины для нейро-прохода и DOF/тумана на монтаже без перерендера.
    Вызывать после setup(): подключается к уже собранному дереву композитора."""
    vl = scene.view_layers[0]
    vl.use_pass_z = True; vl.use_pass_mist = True; vl.use_pass_normal = True
    # векторы движения (для нейро-рестайла и ретайма): в Cycles доступны только без motion blur — его добавит пост
    scene.render.use_motion_blur = False
    try: vl.use_pass_vector = True
    except AttributeError: pass
    try: vl.use_pass_cryptomatte_object = True
    except AttributeError: pass
    if scene.world:
        scene.world.mist_settings.start = 0.5; scene.world.mist_settings.depth = mist_far; scene.world.mist_settings.falloff = 'LINEAR'
    ng = scene.compositing_node_group or setup(scene, 'clean')
    rl = next(n for n in ng.nodes if n.bl_idname == 'CompositorNodeRLayers')
    exr = ng.nodes.new('CompositorNodeOutputFile'); exr.directory = os.path.join(os.path.abspath(outdir), 'passes'); exr.file_name = 'p_#####'
    exr.format.media_type = 'MULTI_LAYER_IMAGE'; exr.format.file_format = 'OPEN_EXR_MULTILAYER'; exr.format.color_depth = '16'
    for name, kind, src in (('depth', 'FLOAT', 'Depth'), ('mist', 'FLOAT', 'Mist'), ('normal', 'VECTOR', 'Normal'), ('beauty', 'RGBA', 'Image'),
                            ('motion', 'RGBA', 'Vector'), ('crypto00', 'RGBA', 'CryptoObject00'), ('crypto01', 'RGBA', 'CryptoObject01')):
        exr.file_output_items.new(kind, name)
        if src in rl.outputs: ng.links.new(rl.outputs[src], exr.inputs[name])
    png = ng.nodes.new('CompositorNodeOutputFile'); png.directory = os.path.join(os.path.abspath(outdir), 'depth'); png.file_name = 'd_#####_'
    png.format.media_type = 'IMAGE'; png.format.file_format = 'PNG'; png.format.color_mode = 'BW'; png.format.color_depth = '16'
    png.file_output_items.new('FLOAT', 'near')
    inv = ng.nodes.new('CompositorNodeInvert')   # ближе = светлее, как у Depth-Anything
    ng.links.new(rl.outputs['Mist'], inv.inputs['Color']); ng.links.new(inv.outputs['Color'], png.inputs['near'])
