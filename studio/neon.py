# Неон: светящиеся трубки-практики на стенах декорации (вывески, полосы, рамки), как на площадке у оператора:
# трубка видна в кадре и сама освещает сцену цветом. Две части на каждую трубку:
#   • видимая трубка — излучающий материал (в кадре и в отражениях на полу), сама по себе свет не считает (без шума);
#   • настоящий свет — узкий прямоугольный area-источник вдоль трубки, лицом от стены: даёт цветные блики и контур.
# Где ставить: от центра действия бросаем лучи по горизонтали, ищем стены в 2–9 м, трубку кладём вдоль стены
# на высоте 2–3 м. Всё детерминировано (порядок направлений фиксирован), чтобы рендер кадра не зависел от фермы.
import math
import bpy
from mathutils import Vector

def _lin(h):
    h = h.lstrip('#'); c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)

def _material(name, col, strength):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new('ShaderNodeOutputMaterial'); e = nt.nodes.new('ShaderNodeEmission')
    e.inputs['Color'].default_value = (*col, 1); e.inputs['Strength'].default_value = strength
    nt.links.new(e.outputs[0], o.inputs['Surface'])
    return m

def place(scene, center, colors=('#FF2E88', '#2EC8FF'), count=3, strength=1.0, length=(1.6, 3.2), height=(2.1, 3.0)):
    """Трубки на стенах вокруг center (точка действия). Возвращает список (трубка, свет)."""
    dg = bpy.context.evaluated_depsgraph_get(); out = []; used = []
    dirs = [i * math.tau / 16 for i in (0, 8, 4, 12, 2, 10, 6, 14, 1, 9, 5, 13, 3, 11, 7, 15)]
    for k, ang in enumerate(dirs):
        if len(out) >= count: break
        hz = height[0] + (height[1] - height[0]) * ((k * 0.618) % 1.0)
        o = Vector((center.x, center.y, hz)); d = Vector((math.cos(ang), math.sin(ang), 0))
        hit, loc, nrm, *_ = scene.ray_cast(dg, o, d, distance=9.0)
        if not hit or (loc - o).length < 2.0 or abs(nrm.z) > 0.3: continue
        if any((loc - u).length < 3.0 for u in used): continue
        n = Vector((nrm.x, nrm.y, 0)).normalized(); along = Vector((-n.y, n.x, 0))
        L = length[0] + (length[1] - length[0]) * ((k * 0.382) % 1.0)
        # трубка должна лечь на стену целиком: проверяем концы
        ok = True
        for s in (-0.5, 0.5):
            p = loc + n * 0.3 + along * (L * s)
            h2 = scene.ray_cast(dg, p, -n, distance=0.6)
            if not h2[0]: ok = False; break
        if not ok: continue
        col = _lin(colors[len(out) % len(colors)])
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.022, depth=L, location=loc + n * 0.06)
        t = bpy.context.object; t.name = f'neon{len(out)}'
        t.rotation_euler = (0, math.pi / 2, math.atan2(along.y, along.x))
        t.data.materials.append(_material(t.name, col, 40.0 * strength))
        for attr in ('visible_diffuse', 'visible_shadow', 'visible_volume_scatter'): setattr(t, attr, False)  # свет считает area-источник
        ld = bpy.data.lights.new(t.name + '_L', 'AREA'); ld.shape = 'RECTANGLE'; ld.size = L; ld.size_y = 0.08
        ld.color = col; ld.energy = 60.0 * L * strength
        lo = bpy.data.objects.new(ld.name, ld); scene.collection.objects.link(lo)
        lo.location = loc + n * 0.1
        # area светит по своей −Z: направляем от стены, длинная сторона (X) вдоль трубки
        z = n; x = along; y = z.cross(x)
        from mathutils import Matrix
        lo.rotation_euler = Matrix((x, y, z)).transposed().to_euler()
        lo.visible_camera = False
        lo.rotation_euler.rotate_axis('X', math.pi)   # −Z смотрит от стены
        used.append(loc); out.append((t, lo))
    print(f'неон: {len(out)} трубок у {tuple(round(c, 1) for c in center)}', flush=True)
    return out

def ring(scene, center, radius=0.55, color='#FFB060', strength=1.0, tube=0.018):
    """Светящееся кольцо вокруг героя (как в «Dummy»): видно в кадре, отражается в пластике и металле и само
    освещает героя снизу-сбоку тёплым светом. Свет — сама трубка (излучение видно диффузу: кольцо близко,
    точечный источник дал бы неверную форму блика); шум снимает денойз."""
    col = _lin(color)
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=tube, major_segments=96, minor_segments=12, location=center)
    t = bpy.context.object; t.name = 'practical_ring'
    for p in t.data.polygons: p.use_smooth = True
    t.data.materials.append(_material(t.name, col, 25.0 * strength))
    t.visible_shadow = False
    print(f'практик: кольцо r={radius} у {tuple(round(c, 2) for c in center)}', flush=True)
    return t
