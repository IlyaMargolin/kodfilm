# Общие детали болванок Jack Rider: мотоцикл из простых форм, посадка героя, карта глубины лучами.
import bpy, math, numpy as np
from mathutils import Vector, Matrix

def _o(op, name, **kw):
    op(**kw); o = bpy.context.active_object; o.name = name; return o

def motorcycle(loc=(0, 0, 0), yaw=0.0):
    """Старый дорожный мотоцикл, ось Y вперёд. Колёса 0.66 м, база 1.42 м, седло 0.80 м."""
    root = bpy.data.objects.new('bike', None); bpy.context.scene.collection.objects.link(root)
    P = []
    R = 0.33
    for y in (-0.71, 0.71):                                             # колёса: шина + диск
        t = _o(bpy.ops.mesh.primitive_torus_add, 'tyre', major_radius=R - 0.06, minor_radius=0.065, location=(0, y, R)); t.rotation_euler.y = math.pi / 2; P.append(t)
        d = _o(bpy.ops.mesh.primitive_cylinder_add, 'hub', radius=R - 0.1, depth=0.05, location=(0, y, R)); d.rotation_euler.y = math.pi / 2; P.append(d)
    def tube(a, b, r=0.03, name='tube'):
        a, b = Vector(a), Vector(b); c = (a + b) / 2; v = b - a
        o = _o(bpy.ops.mesh.primitive_cylinder_add, name, radius=r, depth=v.length, location=c)
        o.rotation_euler = v.to_track_quat('Z', 'Y').to_euler(); P.append(o); return o
    for x in (-0.09, 0.09): tube((x, 0.71, R), (x, 0.52, 0.98), 0.028, 'fork')       # вилка с наклоном
    tube((-0.36, 0.48, 1.06), (0.36, 0.48, 1.06), 0.016, 'bar')                       # руль
    for x in (-0.36, 0.36): tube((x, 0.48, 1.06), (x * 1.05, 0.40, 1.08), 0.02, 'grip')
    hl = _o(bpy.ops.mesh.primitive_cylinder_add, 'headlight', radius=0.09, depth=0.12, location=(0, 0.68, 0.9)); hl.rotation_euler.x = math.pi / 2; P.append(hl)
    tank = _o(bpy.ops.mesh.primitive_uv_sphere_add, 'tank', radius=1, location=(0, 0.2, 0.86)); tank.scale = (0.17, 0.30, 0.13); P.append(tank)
    seat = _o(bpy.ops.mesh.primitive_cube_add, 'seat', location=(0, -0.28, 0.80)); seat.scale = (0.14, 0.33, 0.05); P.append(seat)
    eng = _o(bpy.ops.mesh.primitive_cube_add, 'engine', location=(0, 0.05, 0.45)); eng.scale = (0.17, 0.2, 0.17); P.append(eng)
    tube((0, -0.71, R), (0, 0.05, 0.5), 0.035, 'swingarm'); tube((0, 0.5, 0.95), (0, -0.2, 0.75), 0.035, 'spine')
    tube((0.16, 0.2, 0.35), (0.16, -0.75, 0.42), 0.04, 'exhaust')
    fend = _o(bpy.ops.mesh.primitive_cube_add, 'fender', location=(0, -0.72, 0.72)); fend.scale = (0.1, 0.22, 0.03); fend.rotation_euler.x = -0.35; P.append(fend)
    tl = _o(bpy.ops.mesh.primitive_cube_add, 'taillight', location=(0, -0.93, 0.74)); tl.scale = (0.05, 0.02, 0.03); P.append(tl)
    bag = _o(bpy.ops.mesh.primitive_cube_add, 'bag', location=(-0.24, -0.55, 0.62)); bag.scale = (0.08, 0.2, 0.15); P.append(bag)
    can = _o(bpy.ops.mesh.primitive_cube_add, 'jerrycan', location=(0.26, -0.55, 0.62)); can.scale = (0.07, 0.15, 0.2); P.append(can)
    for o in P: o.parent = root
    root.location = loc; root.rotation_euler.z = yaw
    bpy.context.view_layer.update()
    root['seat'] = list(root.matrix_world @ Vector((0, -0.30, 0.86)))
    root['grips'] = [list(root.matrix_world @ Vector((x, 0.40, 1.08))) for x in (-0.38, 0.38)]
    root['pegs'] = [list(root.matrix_world @ Vector((x, -0.05, 0.36))) for x in (-0.22, 0.22)]
    return root

def _B(arm, n):
    pb = arm.pose.bones; return pb.get('mixamorig:' + n) or pb.get('mixamorig' + n) or pb.get(n)

def _aim(arm, bone, tip_bone, target, base=(0, 0, 0)):
    """Перебором углов поворачивает кость так, чтобы следующая кость (сустав) смотрела на цель."""
    b = _B(arm, bone); t = _B(arm, tip_bone); b.rotation_mode = 'XYZ'
    bpy.context.view_layer.update()
    S = arm.matrix_world @ b.head; want = (Vector(target) - S).normalized(); best = (9, (0, 0, 0))
    for x in range(-180, 181, 10):
        for z in range(-180, 181, 10):
            b.rotation_euler = (math.radians(x), math.radians(base[1]), math.radians(z)); bpy.context.view_layer.update()
            d = ((arm.matrix_world @ t.head) - S).normalized(); err = 1 - d.dot(want)
            if err < best[0]: best = (err, (x, base[1], z))
    b.rotation_euler = [math.radians(v) for v in best[1]]; bpy.context.view_layer.update()
    return best

def rider(bike, cast, human, world, lean=24):
    hero = world.Actor('Soldier.glb')
    hs = dict((cast.spec('pilgrim') or {}).get('human', {})); hs.pop('skin_texture', None); hs['subdiv'] = 0
    body = human.build_actor(hero.arm, hs)
    arm = hero.arm; bpy.context.scene.frame_set(1)
    for pb in arm.pose.bones: pb.rotation_mode = 'XYZ'; pb.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()
    # корень так, чтобы таз лёг на седло, лицом вперёд (+Y)
    hero.root.rotation_euler.z = bike.rotation_euler.z + math.pi * 0  # Soldier смотрит в +Y? проверяется по носу ниже
    bpy.context.view_layer.update()
    hips = arm.matrix_world @ _B(arm, 'Hips').head; seat = Vector(bike['seat'])
    nose = (arm.matrix_world @ _B(arm, 'Head').tail) - (arm.matrix_world @ _B(arm, 'Head').head)
    hero.root.location += seat + Vector((0, 0, 0.10)) - hips; bpy.context.view_layer.update()
    # корпус вперёд к рулю
    sp = _B(arm, 'Spine'); sp.rotation_euler = (math.radians(lean), 0, 0); bpy.context.view_layer.update()
    gl, gr = [Vector(g) for g in bike['grips']]; pl, pr = [Vector(p) for p in bike['pegs']]
    hipL = arm.matrix_world @ _B(arm, 'LeftUpLeg').head; hipR = arm.matrix_world @ _B(arm, 'RightUpLeg').head
    # колени: вперёд-вниз к баку, чуть наружу
    kneeL = Vector((hipL.x * 1.0 - 0.05 if hipL.x < seat.x else hipL.x + 0.05, seat.y + 0.42, seat.z + 0.02))
    kneeR = Vector((hipR.x - 0.05 if hipR.x < seat.x else hipR.x + 0.05, seat.y + 0.42, seat.z + 0.02))
    res = {}
    for side, knee, peg in (('Left', kneeL, None), ('Right', kneeR, None)):
        res[side + 'UpLeg'] = _aim(arm, side + 'UpLeg', side + 'Leg', knee)
    # голень к подножке ближней стороны
    for side in ('Left', 'Right'):
        kn = arm.matrix_world @ _B(arm, side + 'Leg').head
        peg = min((pl, pr), key=lambda p: (p - kn).length)
        res[side + 'Leg'] = _aim(arm, side + 'Leg', side + 'Foot', peg)
    for side in ('Left', 'Right'):
        sh = arm.matrix_world @ _B(arm, side + 'Arm').head
        g = min((gl, gr), key=lambda p: (p - sh).length)
        el = sh + (g - sh) * 0.5 + Vector((0, 0, -0.08))
        el.x += -0.08 if sh.x < seat.x else 0.08
        res[side + 'Arm'] = _aim(arm, side + 'Arm', side + 'ForeArm', el)
        res[side + 'ForeArm'] = _aim(arm, side + 'ForeArm', side + 'Hand', g)
    hd = _B(arm, 'Head'); hd.rotation_euler = (math.radians(-lean * 0.8), 0, 0); bpy.context.view_layer.update()
    print('посадка', {k: (round(v[0], 3), v[1]) for k, v in res.items()}, 'нос', tuple(round(c, 2) for c in nose), flush=True)
    # шлем-интеграл: сфера на кости головы
    hw = arm.matrix_world @ hd.head; c = hw + Vector((0, 0.02, 0.075))
    helm = _o(bpy.ops.mesh.primitive_uv_sphere_add, 'helmet', radius=0.145, location=c); helm.scale = (0.95, 1.08, 1.0)
    mw = helm.matrix_world.copy(); helm.parent = arm; helm.parent_type = 'BONE'; helm.parent_bone = hd.name; bpy.context.view_layer.update(); helm.matrix_world = mw
    return hero

def depth(sc, cam, path, far=300, scale=0.5):
    """Карта глубины лучами из камеры (ближнее светлое, как у Depth Anything), 16 бит."""
    import cv2
    W, H = int(sc.render.resolution_x * scale), int(sc.render.resolution_y * scale)
    dg = bpy.context.evaluated_depsgraph_get(); fr = cam.data.view_frame(scene=sc)
    tr, br, bl, tl = [cam.matrix_world @ v for v in fr]; o = cam.matrix_world.translation
    D = np.full((H, W), far, np.float32)
    for j in range(H):
        v = 1 - (j + 0.5) / H
        L = bl + (tl - bl) * v; Rr = br + (tr - br) * v
        for i in range(W):
            p = L + (Rr - L) * ((i + 0.5) / W); d = (p - o).normalized()
            hit, loc, *_ = sc.ray_cast(dg, o, d, distance=far)
            if hit: D[j, i] = (loc - o).length
    inv = 1 / np.maximum(D, 0.3); inv = (inv - inv.min()) / (inv.max() - inv.min())
    out = cv2.resize(inv, (sc.render.resolution_x, sc.render.resolution_y), interpolation=cv2.INTER_LINEAR)
    cv2.imwrite(path, (out * 65535).astype(np.uint16))
