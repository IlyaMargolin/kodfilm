# Арт-отдел: загрузка локаций, персонажей, освещения. Всё из бесплатных ассетов (см. assets/fetch.sh).
import bpy, os, math
from mathutils import Vector, Matrix, Quaternion
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
A = lambda *p: os.path.join(ROOT, 'assets', *p)

def new_scene(w, h, fps, engine='BLENDER_EEVEE', RT=False, TAA=16):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = engine; sc.render.fps = fps
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.view_settings.view_transform = 'AgX'; sc.view_settings.look = 'AgX - Medium High Contrast'; sc.view_settings.exposure = 0.15
    sc.render.image_settings.file_format = 'PNG'
    if engine == 'BLENDER_EEVEE':
        e = sc.eevee
        for k, v in dict(use_shadows=True, use_raytracing=RT, shadow_ray_count=1, shadow_step_count=6,
                         volumetric_tile_size='4', volumetric_samples=32, taa_render_samples=TAA, use_volumetric_shadows=True).items():
            if hasattr(e, k): setattr(e, k, v)
        if hasattr(e, 'ray_tracing_options'):
            e.ray_tracing_options.resolution_scale = '2'
        if hasattr(e, 'fast_gi_method'): e.fast_gi_method = 'GLOBAL_ILLUMINATION'
    if engine == 'CYCLES':
        # Настоящая трассировка путей: физичные блики, отражения, каустика, объёмные лучи сквозь арки.
        cy = sc.cycles
        cy.samples = TAA; cy.use_adaptive_sampling = True; cy.adaptive_threshold = 0.02
        cy.use_denoising = True
        cy.max_bounces = 8; cy.diffuse_bounces = 3; cy.glossy_bounces = 4; cy.transmission_bounces = 8; cy.volume_bounces = 1
        cy.caustics_reflective = True; cy.caustics_refractive = True; cy.blur_glossy = 0.5
        cy.volume_step_rate = 2.0; cy.volume_max_steps = 256
        try:
            pr = bpy.context.preferences.addons['cycles'].preferences
            for dev in ('CUDA', 'OPTIX'):   # CUDA первым: OptiX на Kaggle падает без nvoptix.bin
                try:
                    pr.compute_device_type = dev; pr.get_devices()
                    gpus = [d for d in pr.devices if d.type == dev]
                    if gpus:
                        for d in pr.devices: d.use = d.type == dev
                        cy.device = 'GPU'; cy.denoiser = 'OPENIMAGEDENOISE'   # на Kaggle нет /usr/share/nvidia/nvoptix.bin: OptiX-денойзер не создаётся, OIDN считаем на CPU
                        try: cy.denoising_use_gpu = False
                        except AttributeError: pass
                        print('Cycles GPU:', dev, [d.name for d in gpus], flush=True); break
                except TypeError: pass
        except Exception as e: print('GPU не найден, Cycles на CPU:', e, flush=True)
    return sc

def hdri(name, strength=1.0, rot=0.0):
    w = bpy.data.worlds.new('world'); bpy.context.scene.world = w; w.use_nodes = True
    nt = w.node_tree; bg = nt.nodes['Background']
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    for r in ('_4k', '_2k'):   # HQ-версия с Poly Haven (assets/fetch_hq.py), если скачана
        hq = A('hdri', name.replace('_1k', r).replace('_2k', r))
        if os.path.exists(hq): name = os.path.basename(hq); break
    env.image = bpy.data.images.load(A('hdri', name))
    mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Rotation'].default_value[2] = rot
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(tc.outputs['Generated'], mp.inputs[0]); nt.links.new(mp.outputs[0], env.inputs[0])
    nt.links.new(env.outputs[0], bg.inputs[0]); bg.inputs[1].default_value = strength
    return w

def set_sponza():
    bpy.ops.import_scene.gltf(filepath=A('sets', 'sponza', 'Sponza.gltf'))
    objs = [o for o in bpy.context.selected_objects]
    for o in objs:
        if o.type == 'MESH':
            for m in o.data.materials:
                if m and m.use_nodes:
                    b = m.node_tree.nodes.get('Principled BSDF')
                    if b and m.blend_method != 'OPAQUE': pass
    return objs

def fog(density=0.02, color=(1, 0.95, 0.9), anisotropy=0.6, size=(60, 40, 30)):
    # объёмный туман: даёт «пыль в лучах» и воздушную перспективу
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, size[2] / 2 - 1))
    c = bpy.context.object; c.scale = size; c.name = 'fog'
    m = bpy.data.materials.new('fog'); m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    o = nt.nodes.new('ShaderNodeOutputMaterial'); v = nt.nodes.new('ShaderNodeVolumePrincipled')
    v.inputs['Density'].default_value = density; v.inputs['Color'].default_value = (*color, 1); v.inputs['Anisotropy'].default_value = anisotropy
    nt.links.new(v.outputs[0], o.inputs['Volume']); c.data.materials.append(m)
    c.visible_shadow = False
    return c

def sun(elev_deg, azim_deg, strength=6, color=(1.0, 0.78, 0.55), angle_deg=0.6):
    ld = bpy.data.lights.new('sun', 'SUN'); ld.energy = strength; ld.color = color; ld.angle = math.radians(angle_deg)
    o = bpy.data.objects.new('sun', ld); bpy.context.scene.collection.objects.link(o)
    o.rotation_euler = (math.radians(90 - elev_deg), 0, math.radians(azim_deg))
    return o

def _fcurves(action):
    """Все F-кривые действия (Blender 5: слои -> полосы -> каналы слотов; раньше action.fcurves)."""
    if hasattr(action, 'fcurves'): return list(action.fcurves)
    out = []
    for ly in action.layers:
        for st in ly.strips:
            for cb in st.channelbags: out.extend(cb.fcurves)
    return out

class Actor:
    """Персонаж со скелетом и набором действий из мокапа. Ноги не скользят:
    скорость корня вычисляется из движения стопы в фазе опоры."""
    def __init__(self, glb, name='hero'):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=A('chars', glb))
        new = [o for o in bpy.data.objects if o not in before]
        self.arm = next(o for o in new if o.type == 'ARMATURE')
        self.root = bpy.data.objects.new(name, None); bpy.context.scene.collection.objects.link(self.root)
        self.arm.parent = self.root
        self.actions = {a.name.lower(): a for a in bpy.data.actions}
        ad = self.arm.animation_data or self.arm.animation_data_create()
        ad.action = None
        for tr in list(ad.nla_tracks): ad.nla_tracks.remove(tr)
        self.track = ad.nla_tracks.new(); self.track.name = 'body'
        self.clips = []
        self.foot = next((b for b in ('mixamorig:LeftFoot', 'mixamorigLeftFoot', 'LeftFoot') if b in self.arm.pose.bones), None)
        self.head = next((b for b in ('mixamorig:Head', 'mixamorigHead', 'Head') if b in self.arm.pose.bones), None)
        self._speed = {}

    def cycle_speed(self, act):
        """м/с, с которыми надо двигать корень, чтобы стопа стояла на месте."""
        if act in self._speed: return self._speed[act]
        sc = bpy.context.scene; a = self.actions[act]; ad = self.arm.animation_data
        keep = [s.mute for s in self.track.strips]
        for s in self.track.strips: s.mute = True
        ad.action = a
        f0, f1 = int(a.frame_range[0]), int(a.frame_range[1])
        pts = []
        for f in range(f0, f1 + 1):
            sc.frame_set(f); bpy.context.view_layer.update()
            pts.append((self.arm.matrix_world @ self.arm.pose.bones[self.foot].head).copy())
        ad.action = None
        for s, m in zip(self.track.strips, keep): s.mute = m
        zmin = min(p.z for p in pts)
        v = [(pts[i + 1] - pts[i]).length * sc.render.fps for i in range(len(pts) - 1) if pts[i].z < zmin + 0.03]
        v = sorted(v)[len(v) // 2] if v else 0
        self._speed[act] = v
        return v

    def _feet_yaw(self, act):
        """Средний курс стоп (в плоскости пола) за клип: куда «смотрит» тело в этом движении."""
        sc = bpy.context.scene; a = self.actions[act]; ad = self.arm.animation_data
        keep = [s.mute for s in self.track.strips]
        for s in self.track.strips: s.mute = True
        ad.action = a; cx = cy = 0.0
        for f in range(int(a.frame_range[0]), int(a.frame_range[1]) + 1, 2):
            sc.frame_set(f)
            for n in (self.foot, self.foot.replace('Left', 'Right')):
                v = (self.arm.matrix_world @ self.arm.pose.bones[n].matrix).to_3x3() @ Vector((0, 1, 0))
                d = math.hypot(v.x, v.y) or 1; cx += v.x / d; cy += v.y / d
        ad.action = None
        for s, m in zip(self.track.strips, keep): s.mute = m
        return math.atan2(cy, cx)

    def align_facing(self, act, ref='walk', min_deg=8):
        """Мокап-клипы сняты с разным разворотом тела (idle у Mixamo стоит вполоборота).
        Если клип не довернуть, при переходе ходьба→стойка всё тело плавно крутится на месте,
        как на поворотном столе. Доворачиваем бёдра клипа вокруг вертикали к курсу эталонного клипа."""
        if act not in self.actions or ref not in self.actions: return 0.0
        d = self._feet_yaw(ref) - self._feet_yaw(act); d = (d + math.pi) % (2 * math.pi) - math.pi
        if abs(math.degrees(d)) < min_deg: return d
        sc = bpy.context.scene; a = self.actions[act]; ad = self.arm.animation_data
        hips = next(b for b in self.arm.pose.bones if b.parent is None or b.name.endswith('Hips'))
        hips.rotation_mode = 'QUATERNION'
        up = (self.arm.matrix_world.inverted().to_3x3() @ Vector((0, 0, 1))).normalized()   # вертикаль в осях скелета
        R = Matrix.Rotation(d, 4, up)
        keep = [s.mute for s in self.track.strips]
        for s in self.track.strips: s.mute = True
        ad.action = a
        fcs = [fc for fc in _fcurves(a) if fc.data_path in (f'pose.bones["{hips.name}"].location', f'pose.bones["{hips.name}"].rotation_quaternion')]
        times = sorted({round(k.co[0], 4) for fc in fcs for k in fc.keyframe_points})
        # знак кватерниона как у эталонного клипа: NLA смешивает кватернионы покомпонентно,
        # противоположные полусферы дают в середине перехода «выворот» таза
        prev = None
        for fc in _fcurves(self.actions[ref]):
            if fc.data_path == f'pose.bones["{hips.name}"].rotation_quaternion':
                prev = prev or Quaternion((1, 0, 0, 0)); prev[fc.array_index] = fc.evaluate(self.actions[ref].frame_range[0])
        new = {}
        for t in times:   # ключи мокапа часто на дробных кадрах (30 к/с в 24): берём ровно их моменты
            sc.frame_set(int(math.floor(t)), subframe=t - math.floor(t)); m = R @ hips.matrix.copy()
            hips.matrix = m; bpy.context.view_layer.update()
            q = hips.rotation_quaternion.copy()
            if prev is not None and q.dot(prev) < 0: q.negate()
            prev = q; new[t] = (hips.location.copy(), q)
        for fc in fcs:
            loc = fc.data_path.endswith('location')
            for k in fc.keyframe_points:
                v = new[round(k.co[0], 4)][0 if loc else 1][fc.array_index]
                k.co[1] = v; k.handle_left[1] = v; k.handle_right[1] = v
            fc.update()
        ad.action = None
        for s, m in zip(self.track.strips, keep): s.mute = m
        return d

    def plant_feet(self, f0, f1, ramp=4):
        """Стопа в опоре стоит на полу намертво (как у аниматоров Rockstar/Naughty Dog: foot locking).
        Опора = стопа низко и почти не движется. На время опоры ставим IK на голень (цепь 2) и фиксируем
        разворот стопы — ступня не скользит и не проворачивается при смене клипов; вне опоры цели совпадают
        с исходной анимацией, на краях — плавный переход за `ramp` кадров."""
        sc = bpy.context.scene; fps = sc.render.fps; out = []
        for n in (self.foot, self.foot.replace('Left', 'Right')):
            pb = self.arm.pose.bones[n]; leg = pb.parent
            W = []; OFF = []   # OFF: хвост голени относительно голеностопа (у пересаженного скелета не ноль)
            for f in range(f0, f1 + 1):
                sc.frame_set(f); M = self.arm.matrix_world; W.append((M @ pb.matrix).copy())
                OFF.append((M @ leg.tail) - (M @ pb.head))
            P = [m.translation.copy() for m in W]
            zf = sorted(p.z for p in P)[len(P) // 20]
            spd = [((P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]).length * fps / (2 if 0 < i < len(P) - 1 else 1)) for i in range(len(P))]
            low = [P[i].z < zf + 0.035 for i in range(len(P))]
            con = [low[i] and spd[i] < 0.45 for i in range(len(P))]
            segs = []; i = 0
            while i < len(con):
                if con[i]:
                    # опора длится, пока стопа не оторвалась от пола: «шарканье» исходного клипа при смене
                    # движения (ходьба→стойка) не превращается в проворот — нога остаётся там, куда шагнула
                    j = i
                    while j + 1 < len(con) and low[j + 1] and ((P[j + 1] - P[i]).to_2d().length < 0.3 or con[j + 1]) and (P[j + 1] - P[i]).to_2d().length < 0.45: j += 1
                    if j - i >= 2: segs.append((i, j))
                    i = j + 1
                else: i += 1
            def yaw(m): v = m.to_3x3() @ Vector((0, 1, 0)); return math.atan2(v.y, v.x)
            T = [m.copy() for m in W]
            def locked(i, a):   # кадр i с пятой и курсом, прибитыми к началу опоры a
                dz = yaw(W[a]) - yaw(W[i]); dz = (dz + math.pi) % (2 * math.pi) - math.pi
                m = Matrix.Translation(W[a].translation) @ Matrix.Rotation(dz, 4, 'Z') @ W[i].to_3x3().to_4x4()
                return m
            def mix(m0, m1, w):
                q = m0.to_quaternion().slerp(m1.to_quaternion(), w)
                return Matrix.Translation(m0.translation.lerp(m1.translation, w)) @ q.to_matrix().to_4x4()
            for a_, b_ in segs:
                for i in range(a_, b_ + 1): T[i] = locked(i, a_)
                for k in range(1, ramp + 1):
                    w = 1 - k / (ramp + 1); w = w * w * (3 - 2 * w)
                    if a_ - k >= 0 and not any(s[0] <= a_ - k <= s[1] for s in segs):
                        L = locked(a_, a_); off = L.translation - W[a_].translation
                        m = W[a_ - k].copy(); m.translation += off * w; T[a_ - k] = mix(W[a_ - k], m, 1)
                    if b_ + k < len(W) and not any(s[0] <= b_ + k <= s[1] for s in segs):
                        Lb = locked(b_, a_); off = Lb.translation - W[b_].translation
                        dz = yaw(Lb) - yaw(W[b_]); dz = (dz + math.pi) % (2 * math.pi) - math.pi
                        m = Matrix.Translation(W[b_ + k].translation + off * w) @ Matrix.Rotation(dz * w, 4, 'Z') @ W[b_ + k].to_3x3().to_4x4()
                        T[b_ + k] = m
            tgt = bpy.data.objects.new(f'plant_{n[-8:]}', None); sc.collection.objects.link(tgt)
            tgt.rotation_mode = 'QUATERNION'
            for i, m in enumerate(T):
                tgt.location = m.translation + OFF[i]; tgt.rotation_quaternion = m.to_quaternion()
                tgt.keyframe_insert('location', frame=f0 + i); tgt.keyframe_insert('rotation_quaternion', frame=f0 + i)
            ik = leg.constraints.new('IK'); ik.target = tgt; ik.chain_count = 2; ik.use_tail = True; ik.use_stretch = False
            cr = pb.constraints.new('COPY_ROTATION'); cr.target = tgt
            out.append((n, len(segs)))
        return out

    def play(self, act, start, end, blend=8):
        a = self.actions[act]
        s = self.track.strips.new(f'{act}_{start}', int(start), a)
        s.action_frame_start, s.action_frame_end = a.frame_range
        s.frame_end = int(end)
        s.repeat = max(1.0, (end - start) / max(1, a.frame_range[1] - a.frame_range[0]))
        s.frame_end = int(end)
        s.blend_type = 'REPLACE'; s.extrapolation = 'HOLD_FORWARD'
        s.blend_in = s.blend_out = 0
        s.use_auto_blend = False
        self.clips.append(s)
        return s
