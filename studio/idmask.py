# Маски объектов для нейро-финиша одним проходом Cycles: каналы RGB кадра — три маски.
#   R — кожа актёра (материалы skin*), G — «держать из ядра» (объекты по префиксам имён), B — небо/фон мира.
# Объекты с той же камерой, ГРИП и движением, что и в beauty, поэтому края масок совпадают с кадром.
#   python studio/idmask.py <scene.blend> <out_dir> [keep=helmet_shell,helmet_hinge] [samples=8]
#   (из Python: render(sc, out_dir, keep=(...)) после рендера beauty)
import sys, os

def _emis(name, rgb):
    import bpy
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.use_nodes = True; N = m.node_tree.nodes
    for n in list(N): N.remove(n)
    e = N.new('ShaderNodeEmission'); e.inputs[0].default_value = (*rgb, 1); o = N.new('ShaderNodeOutputMaterial')
    m.node_tree.links.new(e.outputs[0], o.inputs[0]); return m

def render(sc, out, keep=(), samples=8, frames=None):
    import bpy
    blk, skin, kp = _emis('id_black', (0, 0, 0)), _emis('id_skin', (1, 0, 0)), _emis('id_keep', (0, 1, 0))
    for o in bpy.data.objects:
        if o.type not in ('MESH', 'CURVE'): continue
        held = any(o.name.startswith(p) for p in keep)
        for sl in o.material_slots:
            nm = sl.material.name if sl.material else ''
            sl.material = kp if held else (skin if nm.startswith('skin') else blk)
        if o.type == 'MESH':
            for m in o.modifiers:
                if m.type == 'PARTICLE_SYSTEM': m.show_render = False   # волосы/щетина — не кожа
    for o in bpy.data.objects:
        if o.type == 'LIGHT': o.hide_render = True
    wt = sc.world.node_tree; N = wt.nodes
    for n in list(N): N.remove(n)
    bg = N.new('ShaderNodeBackground'); bg.inputs[0].default_value = (0, 0, 1, 1); bg.inputs[1].default_value = 1.0
    wo = N.new('ShaderNodeOutputWorld'); wt.links.new(bg.outputs[0], wo.inputs[0])
    sc.render.film_transparent = False
    sc.cycles.samples = samples; sc.cycles.use_denoising = False; sc.cycles.max_bounces = 0
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'; sc.view_settings.exposure = 0
    os.makedirs(out, exist_ok=True)
    for f in (frames or range(sc.frame_start, sc.frame_end + 1)):
        sc.frame_set(f); sc.render.filepath = os.path.join(out, f'f{f - sc.frame_start:04d}.png'); bpy.ops.render.render(write_still=True)

if __name__ == '__main__':
    import bpy
    a = [x for x in sys.argv[1:] if x != '--']
    a = a[a.index(next(x for x in a if x.endswith('.blend'))):]
    opt = dict(x.split('=', 1) for x in a[2:] if '=' in x)
    bpy.ops.wm.open_mainfile(filepath=os.path.abspath(a[0]))
    render(bpy.context.scene, a[1], keep=tuple(p for p in opt.get('keep', '').split(',') if p), samples=int(opt.get('samples', 8)))
