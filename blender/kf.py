# kf — студийная библиотека для Blender-сцен: рендер, материалы, свет, камера, CLI.
import bpy, sys, os, argparse, math
from mathutils import Vector

def args(extra=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='out/shot'); ap.add_argument('--w', type=int, default=1920); ap.add_argument('--h', type=int, default=1080)
    ap.add_argument('--frames', default='1'); ap.add_argument('--samples', type=int, default=128); ap.add_argument('--fps', type=int, default=24)
    ap.add_argument('--chunk', type=int, default=0); ap.add_argument('--chunks', type=int, default=1)
    for e in (extra or []): ap.add_argument(*e[0], **e[1])
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:]
    return ap.parse_args(argv)

def setup(a, look='AgX - Medium High Contrast'):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'
    sc.cycles.samples = a.samples; sc.cycles.use_adaptive_sampling = True; sc.cycles.adaptive_threshold = 0.02
    sc.cycles.use_denoising = True; sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 6; sc.cycles.diffuse_bounces = 2; sc.cycles.glossy_bounces = 3; sc.cycles.transmission_bounces = 8; sc.cycles.caustics_reflective = False
    sc.render.resolution_x, sc.render.resolution_y = a.w, a.h; sc.render.fps = a.fps
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = look
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_depth = '16'
    return sc

def world(color=(0.004, 0.005, 0.008), strength=1.0):
    w = bpy.data.worlds.new('world'); bpy.context.scene.world = w; w.use_nodes = True
    bg = w.node_tree.nodes['Background']; bg.inputs['Color'].default_value = (*color, 1); bg.inputs['Strength'].default_value = strength
    return w

def light(kind, loc, energy, color=(1, 1, 1), size=0.1, target=None, spot=None):
    ld = bpy.data.lights.new(kind, kind); ld.energy = energy; ld.color = color
    if kind == 'AREA': ld.size = size
    else: ld.shadow_soft_size = size
    if spot: ld.spot_size, ld.spot_blend = spot
    o = bpy.data.objects.new(kind, ld); o.location = loc; bpy.context.scene.collection.objects.link(o)
    if target is not None:
        c = o.constraints.new('TRACK_TO'); c.target = target; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return o

def camera(lens=50, fstop=2.8, sensor=36, focus=None):
    cd = bpy.data.cameras.new('cam'); cd.lens = lens; cd.sensor_width = sensor
    cd.dof.use_dof = fstop is not None
    if fstop: cd.dof.aperture_fstop = fstop; cd.dof.aperture_blades = 7
    if focus is not None: cd.dof.focus_object = focus
    cam = bpy.data.objects.new('cam', cd); bpy.context.scene.collection.objects.link(cam); bpy.context.scene.camera = cam
    tgt = bpy.data.objects.new('cam_target', None); bpy.context.scene.collection.objects.link(tgt)
    c = cam.constraints.new('TRACK_TO'); c.target = tgt; c.track_axis = 'TRACK_NEGATIVE_Z'; c.up_axis = 'UP_Y'
    return cam, tgt

def handheld(f, amp=1.0, seed=0.0):
    # «рука оператора»: сумма медленных синусов, детерминированно по кадру
    n = lambda k, s: math.sin(f * k + s) * 0.6 + math.sin(f * k * 2.3 + s * 1.7) * 0.3 + math.sin(f * k * 5.1 + s * 3.1) * 0.1
    return Vector((n(0.031, seed), n(0.027, seed + 2), n(0.035, seed + 4))) * amp

def _n(nt, kind, **inputs):
    node = nt.nodes.new(kind)
    for k, v in inputs.items():
        if k.startswith('_'): setattr(node, k[1:], v)
        else: node.inputs[k].default_value = v
    return node

def weathered_marble(name='marble', scale=1.0, dirt=1.0, wet=0.5, moss=(0.012, 0.014, 0.008), stone=(0.66, 0.64, 0.59)):
    """Выветренный мрамор: тонкие прожилки, подповерхностное рассеяние, грязь в углублениях,
    потёки сверху вниз, тёмный мох, влажный блеск. scale — размер объекта в метрах (для частот шума)."""
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    nt = mat.node_tree; L = nt.links; nt.nodes.clear()
    out = _n(nt, 'ShaderNodeOutputMaterial'); b = _n(nt, 'ShaderNodeBsdfPrincipled')
    L.new(b.outputs[0], out.inputs['Surface'])
    tc = _n(nt, 'ShaderNodeTexCoord')
    def mapped(sx, sy, sz):
        m = _n(nt, 'ShaderNodeMapping'); m.inputs['Scale'].default_value = (sx / scale, sy / scale, sz / scale); L.new(tc.outputs['Object'], m.inputs[0]); return m
    def noise(m, sc_, det=8, rough=0.6, dist=0.0):
        t = _n(nt, 'ShaderNodeTexNoise', Scale=sc_, Detail=det, Roughness=rough, Distortion=dist); L.new(m.outputs[0], t.inputs['Vector']); return t
    def ramp(inp, p0, c0, p1, c1):
        r = nt.nodes.new('ShaderNodeValToRGB'); e = r.color_ramp.elements
        e[0].position, e[0].color, e[1].position, e[1].color = p0, (*c0, 1), p1, (*c1, 1); L.new(inp, r.inputs[0]); return r
    def math_(op, a_, b_=None, clamp=False):
        m = _n(nt, 'ShaderNodeMath', _operation=op, _use_clamp=clamp)
        for i, v in enumerate((a_, b_)):
            if v is None: continue
            if isinstance(v, (int, float)): m.inputs[i].default_value = v
            else: L.new(v, m.inputs[i])
        return m.outputs[0]
    # прожилки: искажённый шум, тонкая линия через |x-0.5|
    vn = noise(mapped(1.2, 1.2, 1.2), 1.4, det=10, rough=0.62, dist=3.5)
    vline = math_('ABSOLUTE', math_('SUBTRACT', vn.outputs['Fac'], 0.5))
    veins = ramp(vline, 0.0, (0.0, 0, 0), 0.025, (1, 1, 1))
    base = ramp(noise(mapped(3, 3, 3), 2.0, det=6).outputs['Fac'], 0.3, tuple(c * 0.92 for c in stone), 0.7, stone)
    vcol = _n(nt, 'ShaderNodeMix', _data_type='RGBA', _blend_type='MULTIPLY'); vcol.inputs['Factor'].default_value = 0.35
    L.new(base.outputs['Color'], vcol.inputs[6]); L.new(veins.outputs['Color'], vcol.inputs[7])
    # грязь в углублениях: AO + кривизна
    # (шейдерный AO очень дорогой на CPU — углубления берём из кривизны сетки)
    geo = _n(nt, 'ShaderNodeNewGeometry')
    point = ramp(geo.outputs['Pointiness'], 0.44, (1, 1, 1), 0.53, (0, 0, 0))
    cav = math_('MULTIPLY', point.outputs['Color'], 0.8)
    # потёки: шум, растянутый по вертикали (дождь веками тёк вниз)
    streak = noise(mapped(14, 14, 1.2), 1.0, det=12, rough=0.7)
    st = ramp(streak.outputs['Fac'], 0.56, (0, 0, 0), 0.7, (1, 1, 1))
    blotch = ramp(noise(mapped(5, 5, 5), 1.0, det=14, rough=0.72).outputs['Fac'], 0.55, (0, 0, 0), 0.68, (1, 1, 1))
    grime = math_('ADD', math_('ADD', math_('MULTIPLY', cav, 1.6), math_('MULTIPLY', point.outputs['Color'], 0.5)),
                  math_('ADD', math_('MULTIPLY', st.outputs['Color'], 0.55), math_('MULTIPLY', blotch.outputs['Color'], 0.6)))
    fine = noise(mapped(90, 90, 90), 1.0, det=8, rough=0.7)
    gm = math_('MULTIPLY', math_('MULTIPLY', grime, fine.outputs['Fac']), 1.5 * dirt, clamp=True)
    mossc = ramp(fine.outputs['Fac'], 0.3, moss, 0.75, tuple(min(1, c * 6) for c in moss))
    col = _n(nt, 'ShaderNodeMix', _data_type='RGBA'); L.new(gm, col.inputs['Factor'])
    L.new(vcol.outputs[2], col.inputs[6]); L.new(mossc.outputs['Color'], col.inputs[7])
    L.new(col.outputs[2], b.inputs['Base Color'])
    # шероховатость: чистый мокрый камень блестит, грязь матовая
    rough = _n(nt, 'ShaderNodeMapRange'); rough.inputs[3].default_value = 0.42 - 0.25 * wet; rough.inputs[4].default_value = 0.85
    L.new(gm, rough.inputs[0]); L.new(rough.outputs[0], b.inputs['Roughness'])
    b.inputs['Coat Weight'].default_value = 0.25 * wet; b.inputs['Coat Roughness'].default_value = 0.12
    b.inputs['Subsurface Weight'].default_value = 0.3
    b.inputs['Subsurface Radius'].default_value = (1.0, 0.8, 0.6); b.inputs['Subsurface Scale'].default_value = 0.004 * scale * 10
    # микрорельеф: поры камня, выщербины
    pores = noise(mapped(260, 260, 260), 1.0, det=4, rough=0.5)
    pits = ramp(noise(mapped(40, 40, 40), 1.0, det=6).outputs['Fac'], 0.62, (1, 1, 1), 0.7, (0, 0, 0))
    h = math_('ADD', math_('MULTIPLY', pores.outputs['Fac'], 0.5), math_('MULTIPLY', pits.outputs['Color'], 0.6))
    h = math_('SUBTRACT', h, math_('MULTIPLY', gm, 0.3))
    bump = _n(nt, 'ShaderNodeBump', Strength=0.45, Distance=0.0015 * scale * 10); L.new(h, bump.inputs['Height'])
    return mat, b, bump, nt

def water(name='water'):
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Transmission Weight'].default_value = 1.0; b.inputs['Roughness'].default_value = 0.0; b.inputs['IOR'].default_value = 1.333
    b.inputs['Base Color'].default_value = (1, 1, 1, 1)
    return m

def frames_from(a, total):
    if a.frames == 'all': fr = list(range(1, total + 1))
    elif '-' in a.frames: s0, s1 = map(int, a.frames.split('-')); fr = list(range(s0, s1 + 1))
    else: fr = [int(x) for x in a.frames.split(',')]
    per = math.ceil(len(fr) / a.chunks)
    return fr[a.chunk * per:(a.chunk + 1) * per]

def render(a, frames):
    sc = bpy.context.scene; os.makedirs(a.out, exist_ok=True)
    for f in frames:
        sc.frame_set(f); sc.render.filepath = os.path.join(os.path.abspath(a.out), f'f_{f:05d}.png')
        bpy.ops.render.render(write_still=True); print('frame', f, flush=True)
