"""Природа на физике.
ocean()  — FFT-океан (модификатор Ocean, как в студийных пайплайнах Tessendorf-волны) с пеной по гребням.
cliffs() — скальные стены: подразделённая сетка + многослойный дисплейсмент (крупные пласты + трещины).
fog_volume() — объём с сильным рассеянием вперёд: свечение в контровом свете и воздушная перспектива.
"""
import bpy, math

def _mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    return m, m.node_tree.nodes, m.node_tree.links

def water_material(deep=(0.006, 0.012, 0.016), foam=True):
    m, N, L = _mat('water')
    b = N['Principled BSDF']
    b.inputs['Base Color'].default_value = (*deep, 1); b.inputs['Roughness'].default_value = 0.035
    b.inputs['IOR'].default_value = 1.333
    b.inputs['Specular IOR Level'].default_value = 0.5
    if foam:   # пена из слоя модификатора: белая шероховатая на гребнях
        a = N.new('ShaderNodeAttribute'); a.attribute_name = 'foam'
        r = N.new('ShaderNodeMapRange'); r.inputs['From Min'].default_value = 0.62; r.inputs['From Max'].default_value = 1.0
        L.new(a.outputs['Fac'], r.inputs['Value'])
        mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'
        mix.inputs['A'].default_value = (*deep, 1); mix.inputs['B'].default_value = (0.75, 0.78, 0.8, 1)
        L.new(r.outputs['Result'], mix.inputs['Factor']); L.new(mix.outputs['Result'], b.inputs['Base Color'])
        rr = N.new('ShaderNodeMapRange'); rr.inputs['To Min'].default_value = 0.035; rr.inputs['To Max'].default_value = 0.6
        L.new(r.outputs['Result'], rr.inputs['Value']); L.new(rr.outputs['Result'], b.inputs['Roughness'])
    return m

def ocean(size=200, res=18, wave_scale=1.2, chop=1.4, wind=9.0, time=1.0, foam=True, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_plane_add(size=2, location=loc); o = bpy.context.object; o.name = 'ocean'
    md = o.modifiers.new('ocean', 'OCEAN')
    md.geometry_mode = 'GENERATE'; md.size = 1.0; md.spatial_size = int(size); md.resolution = res
    md.wave_scale = wave_scale; md.choppiness = chop; md.wind_velocity = wind; md.time = time
    md.wave_alignment = 0.4; md.damping = 0.5
    if foam:
        md.use_foam = True; md.foam_layer_name = 'foam'; md.foam_coverage = 0.0
    o.data.materials.append(water_material(foam=foam))
    bpy.ops.object.shade_smooth()
    return o, md

def rock_material(base=(0.05, 0.05, 0.05)):
    m, N, L = _mat('rock')
    b = N['Principled BSDF']; b.inputs['Roughness'].default_value = 0.85
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise'); nz.inputs['Scale'].default_value = 0.35; nz.inputs['Detail'].default_value = 12; nz.inputs['Roughness'].default_value = 0.62
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    ramp = N.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].color = (base[0] * 0.5, base[1] * 0.5, base[2] * 0.5, 1)
    ramp.color_ramp.elements[1].color = (base[0] * 3, base[1] * 3, base[2] * 3.1, 1)
    L.new(nz.outputs['Fac'], ramp.inputs['Fac']); L.new(ramp.outputs['Color'], b.inputs['Base Color'])
    nz2 = N.new('ShaderNodeTexNoise'); nz2.inputs['Scale'].default_value = 6; nz2.inputs['Detail'].default_value = 15
    L.new(tc.outputs['Object'], nz2.inputs['Vector'])
    bump = N.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.6; bump.inputs['Distance'].default_value = 0.3
    L.new(nz2.outputs['Fac'], bump.inputs['Height']); L.new(bump.outputs['Normal'], b.inputs['Normal'])
    return m

def cliffs(length=260, height=120, gap=46, depth=40, seed=3, subdiv=6, chunks=6):
    """Две скальные стены вдоль оси Y по бокам от x=0; фьорд уходит вперёд к +Y.
    Как в студийном kitbash: стена собирается из нескольких глыб со случайным поворотом, наклоном и высотой,
    поверх — три октавы дисплейсмента в мировых координатах (каждая глыба получает свой рельеф)."""
    import random
    rnd = random.Random(seed); out = []; mat = rock_material()
    texs = []
    for i, (tsz, st, tp) in enumerate(((38, 16, 'CLOUDS'), (9, 4.0, 'CLOUDS'), (2.5, 1.0, 'VORONOI'))):
        t = bpy.data.textures.new(f'rk{i}', tp)
        if tp == 'CLOUDS': t.noise_scale = tsz; t.noise_depth = 6
        else: t.noise_scale = tsz
        texs.append((t, st))
    seg = length / chunks
    for side in (-1, 1):
        for k in range(chunks):
            hh = height * rnd.uniform(0.75, 1.15); dd = depth * rnd.uniform(0.8, 1.3)
            x = side * (gap / 2 + dd / 2 + rnd.uniform(-6, 8) + k * rnd.uniform(-0.5, 1.5))
            y = -30 + seg * (k + 0.5) + rnd.uniform(-seg * 0.2, seg * 0.2)
            bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, hh / 2 - 10))
            o = bpy.context.object; o.name = f'cliff_{side}_{k}'; o.scale = (dd, seg * 1.5, hh)
            o.rotation_euler = (rnd.uniform(-0.05, 0.05), side * rnd.uniform(0.04, 0.16), rnd.uniform(-0.18, 0.18))
            bpy.ops.object.transform_apply(scale=True)
            s = o.modifiers.new('sub', 'SUBSURF'); s.subdivision_type = 'SIMPLE'; s.levels = s.render_levels = subdiv
            s2 = o.modifiers.new('round', 'SUBSURF'); s2.levels = s2.render_levels = 1
            for i, (t, st) in enumerate(texs):
                d = o.modifiers.new(f'd{i}', 'DISPLACE'); d.texture = t; d.strength = st; d.mid_level = 0.5; d.texture_coords = 'GLOBAL'
            o.data.materials.append(mat); bpy.ops.object.shade_smooth(); out.append(o)
    return out

def fog_volume(density=0.006, color=(0.85, 0.88, 0.92), anisotropy=0.75, size=(400, 500, 160), loc=(0, 150, 60)):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); c = bpy.context.object; c.scale = size; c.name = 'fog'
    m, N, L = _mat('fogv'); N.remove(N['Principled BSDF'])
    v = N.new('ShaderNodeVolumePrincipled'); v.inputs['Density'].default_value = density
    v.inputs['Color'].default_value = (*color, 1); v.inputs['Anisotropy'].default_value = anisotropy
    L.new(v.outputs[0], N['Material Output'].inputs['Volume']); c.data.materials.append(m)
    return c
