"""Линза в композиторе Blender (работает на HDR-данных рендера, до тонмаппинга кадра в файл):
блум от ярких источников, анаморфные горизонтальные блики, призрачные отражения и хроматическая аберрация.
Яркость порогов в линейных единицах сцены: срабатывает только на реальных засветах (солнце, лампы, металл)."""
import bpy

LOOKS = {
    # имя: (bloom_thr, bloom_str, streak_thr, streak_str, ghosts_str, dispersion)
    'clean':      (1.2, 0.25, 9.0, 0.0,  0.0,  0.004),
    'cinema':     (1.0, 0.40, 3.0, 0.12, 0.03, 0.010),   # по умолчанию: Дикинс-сдержанно
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
