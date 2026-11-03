"""Рассев инстансами (Geometry Nodes), как у студий при сборке леса или квартала: один образец в памяти — тысячи копий в кадре.
scatter(surface, collection, density) — точки по поверхности (Пуассон), фильтр по крутизне склона, случайный масштаб и поворот,
инстансы коллекции (выбор образца случайно). grass_collection() — процедурные травинки и цветы."""
import bpy, bmesh, math, random

def _ng(name):
    ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    return ng

def scatter(surface, collection, density=40.0, seed=0, scale=(0.7, 1.3), max_slope_deg=35, min_dist=0.0, keep_surface=True):
    ng = _ng(f'scatter_{collection.name}'); N, L = ng.nodes, ng.links
    gi = N.new('NodeGroupInput'); go = N.new('NodeGroupOutput')
    dist = N.new('GeometryNodeDistributePointsOnFaces')
    if min_dist > 0:
        dist.distribute_method = 'POISSON'; dist.inputs['Distance Min'].default_value = min_dist; dist.inputs['Density Max'].default_value = density
    else: dist.inputs['Density'].default_value = density
    dist.inputs['Seed'].default_value = seed
    # фильтр по склону: нормаль·Z >= cos(угла) — трава не растёт на отвесной скале
    nrm = N.new('GeometryNodeInputNormal'); sep = N.new('ShaderNodeSeparateXYZ')
    cmp = N.new('FunctionNodeCompare'); cmp.data_type = 'FLOAT'; cmp.operation = 'GREATER_EQUAL'
    cmp.inputs[1].default_value = math.cos(math.radians(max_slope_deg))
    L.new(nrm.outputs['Normal'], sep.inputs[0]); L.new(sep.outputs['Z'], cmp.inputs[0]); L.new(cmp.outputs['Result'], dist.inputs['Selection'])
    L.new(gi.outputs[0], dist.inputs['Mesh'])
    ci = N.new('GeometryNodeCollectionInfo'); ci.inputs['Collection'].default_value = collection
    ci.inputs['Separate Children'].default_value = True; ci.inputs['Reset Children'].default_value = True
    inst = N.new('GeometryNodeInstanceOnPoints'); inst.inputs['Pick Instance'].default_value = True
    L.new(dist.outputs['Points'], inst.inputs['Points']); L.new(ci.outputs[0], inst.inputs['Instance'])
    ri = N.new('FunctionNodeRandomValue'); ri.data_type = 'INT'; ri.inputs['Max'].default_value = 1000; ri.inputs['Seed'].default_value = seed + 1
    L.new(ri.outputs['Value'], inst.inputs['Instance Index'])
    rs = N.new('FunctionNodeRandomValue'); rs.data_type = 'FLOAT'; rs.inputs['Min'].default_value = scale[0]; rs.inputs['Max'].default_value = scale[1]; rs.inputs['Seed'].default_value = seed + 2
    L.new(rs.outputs['Value'], inst.inputs['Scale'])
    rr = N.new('FunctionNodeRandomValue'); rr.data_type = 'FLOAT_VECTOR'; rr.inputs['Seed'].default_value = seed + 3
    rr.inputs['Min'].default_value = (-0.15, -0.15, 0); rr.inputs['Max'].default_value = (0.15, 0.15, 6.283)
    L.new(rr.outputs['Value'], inst.inputs['Rotation'])
    if keep_surface:
        j = N.new('GeometryNodeJoinGeometry'); L.new(gi.outputs[0], j.inputs[0]); L.new(inst.outputs[0], j.inputs[0]); L.new(j.outputs[0], go.inputs[0])
    else: L.new(inst.outputs[0], go.inputs[0])
    md = surface.modifiers.new('scatter', 'NODES'); md.node_group = ng
    return md

def _blade(name, h, w, bend, mat, rnd):
    bm = bmesh.new(); n = 5; prev = None
    for i in range(n + 1):
        t = i / n; z = h * t; y = bend * t * t; ww = w * (1 - t) ** 0.7
        a = bm.verts.new((-ww / 2, y, z)); b = bm.verts.new((ww / 2, y, z))
        if prev: bm.faces.new((prev[0], prev[1], b, a))
        prev = (a, b)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(mat)
    o = bpy.data.objects.new(name, me); return o

def grass_collection(name='grass', blades=12, tufts=6, seed=1, flowers=True):
    """Пучки травы из изогнутых травинок + мелкие цветы. Материал с просвечиванием (трава светится в контровом)."""
    rnd = random.Random(seed)
    col = bpy.data.collections.new(name)
    m = bpy.data.materials.new('grass'); m.use_nodes = True; b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.06, 0.11, 0.025, 1); b.inputs['Roughness'].default_value = 0.55
    for k, v in (('Subsurface Weight', 0.0), ('Transmission Weight', 0.25)):
        if k in b.inputs: b.inputs[k].default_value = v
    fm = bpy.data.materials.new('flower'); fm.use_nodes = True; fb = fm.node_tree.nodes['Principled BSDF']
    fb.inputs['Base Color'].default_value = (0.35, 0.4, 0.9, 1); fb.inputs['Roughness'].default_value = 0.5
    for t in range(tufts):
        bm_objs = []
        for i in range(blades):
            o = _blade(f'{name}_b{t}_{i}', rnd.uniform(0.18, 0.45), rnd.uniform(0.012, 0.025), rnd.uniform(0.03, 0.12), m, rnd)
            o.location = (rnd.gauss(0, 0.04), rnd.gauss(0, 0.04), 0); o.rotation_euler[2] = rnd.uniform(0, 6.283)
            bm_objs.append(o)
        if flowers and t % 4 == 0:
            for i in range(2):
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.012); s = bpy.context.object
                bpy.context.scene.collection.objects.unlink(s); s.data.materials.append(fm)
                s.location = (rnd.gauss(0, 0.05), rnd.gauss(0, 0.05), rnd.uniform(0.25, 0.4)); bm_objs.append(s)
        # склеиваем пучок в один объект-образец
        me = bpy.data.meshes.new(f'{name}_tuft{t}'); bm = bmesh.new()
        for o in bm_objs:
            tmp = o.data.copy(); tmp.transform(o.matrix_basis); bm.from_mesh(tmp); bpy.data.meshes.remove(tmp)
        bm.to_mesh(me); bm.free()
        me.materials.append(m); me.materials.append(fm)
        for p in me.polygons: p.material_index = 1 if p.area < 0.0004 and len(p.vertices) == 3 else 0
        tuft = bpy.data.objects.new(f'{name}_tuft{t}', me); col.objects.link(tuft)
    return col
