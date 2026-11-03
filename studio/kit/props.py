"""Процедурный реквизит. ship() — небольшое судно (траулер): корпус, рубка, мачта, ходовые огни."""
import bpy, bmesh, math

def _pbr(name, col, rough=0.5, metal=0.0, emit=None, strength=0):
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*col, 1); b.inputs['Roughness'].default_value = rough; b.inputs['Metallic'].default_value = metal
    if emit: b.inputs['Emission Color'].default_value = (*emit, 1); b.inputs['Emission Strength'].default_value = strength
    return m

def _box(name, loc, scale, mat, parent, bevel=0.05):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.object; o.name = name; o.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    if bevel: bv = o.modifiers.new('bv', 'BEVEL'); bv.width = bevel; bv.segments = 2
    o.data.materials.append(mat); o.parent = parent; return o

def hull_mesh(L=16, B=4.6, D=2.6):
    """Корпус: сечения по длине, нос заострён и поднят, корма транцевая."""
    bm = bmesh.new(); rings = []
    n = 14
    for i in range(n + 1):
        t = i / n; y = (t - 0.5) * L
        w = B / 2 * (1 - max(0, t - 0.62) / 0.38) ** 0.8 if t > 0.62 else B / 2 * (0.86 + 0.14 * math.sin(t / 0.62 * math.pi / 2))
        sheer = D + 0.9 * max(0, t - 0.6) ** 2 * 6
        keel = 0.25 * (1 - t)
        prof = [(-w, sheer), (-w * 0.97, D * 0.5), (-w * 0.6, keel + 0.15), (0, keel), (w * 0.6, keel + 0.15), (w * 0.97, D * 0.5), (w, sheer)]
        rings.append([bm.verts.new((x, y, z)) for x, z in prof])
    for a, b in zip(rings, rings[1:]):
        for j in range(len(a) - 1): bm.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    bm.faces.new(rings[0][::-1]); bm.faces.new(rings[-1])
    me = bpy.data.meshes.new('hull'); bm.to_mesh(me); bm.free(); return me

def ship(loc=(0, 0, 0), heading=0.0):
    root = bpy.data.objects.new('ship', None); bpy.context.scene.collection.objects.link(root)
    root.location = loc; root.rotation_euler[2] = heading
    paint = _pbr('hull_paint', (0.035, 0.037, 0.04), 0.45); white = _pbr('superstructure', (0.28, 0.29, 0.3), 0.55)
    steel = _pbr('steel', (0.2, 0.2, 0.21), 0.35, 1.0); glass = _pbr('window', (0.01, 0.01, 0.012), 0.05, emit=(1.0, 0.75, 0.45), strength=3)
    lamp = _pbr('lamp', (1, 1, 1), 0.2, emit=(1.0, 0.92, 0.8), strength=60)
    h = bpy.data.objects.new('hull', hull_mesh()); bpy.context.scene.collection.objects.link(h); h.parent = root
    h.data.materials.append(paint); h.location.z = -1.2
    sb = h.modifiers.new('sub', 'SUBSURF'); sb.levels = sb.render_levels = 2
    _box('deck', (0, 0, 1.45), (4.2, 15, 0.12), steel, root, 0.02)
    _box('cabin', (0, -1.0, 2.6), (3.2, 4.5, 2.2), white, root)
    _box('bridge', (0, -0.4, 4.2), (3.0, 2.6, 1.2), white, root)
    _box('windows', (0, 0.92, 4.3), (2.7, 0.05, 0.45), glass, root, 0)
    _box('stack', (0, -2.8, 4.4), (0.9, 1.0, 2.0), paint, root)
    _box('mast', (0, 0.4, 6.6), (0.14, 0.14, 4.2), steel, root, 0.01)
    _box('yard', (0, 0.4, 7.6), (2.6, 0.1, 0.1), steel, root, 0.01)
    _box('aframe', (0, -6.6, 3.4), (3.6, 0.2, 0.2), steel, root, 0.01)
    for x in (-1.7, 1.7): _box(f'aleg{x}', (x, -6.6, 2.4), (0.18, 0.18, 2.0), steel, root, 0.01)
    for x in (-2.15, 2.15):
        for y in range(-6, 7, 2): _box(f'rail{x}{y}', (x, y, 1.95), (0.05, 0.05, 0.9), steel, root, 0)
    for p in ((0, 0.4, 8.75), (-1.2, 0.4, 7.6), (1.2, 0.4, 7.6), (0, 7.4, 2.9)):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.12, location=p); s = bpy.context.object; s.data.materials.append(lamp); s.parent = root
        ld = bpy.data.lights.new('nav', 'POINT'); ld.energy = 60; ld.color = (1.0, 0.9, 0.75); ld.shadow_soft_size = 0.1
        lo = bpy.data.objects.new('nav', ld); bpy.context.scene.collection.objects.link(lo); lo.location = p; lo.parent = root
    return root
