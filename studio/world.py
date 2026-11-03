# Арт-отдел: загрузка локаций, персонажей, освещения. Всё из бесплатных ассетов (см. assets/fetch.sh).
import bpy, os, math
from mathutils import Vector
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
            for dev in ('OPTIX', 'CUDA'):
                try:
                    pr.compute_device_type = dev; pr.get_devices()
                    gpus = [d for d in pr.devices if d.type == dev]
                    if gpus:
                        for d in pr.devices: d.use = d.type == dev
                        cy.device = 'GPU'; cy.denoiser = 'OPENIMAGEDENOISE'   # OptiX-денойзер на драйверах Kaggle не создаётся; OIDN 2 сам идёт на GPU
                        try: cy.denoising_use_gpu = True
                        except AttributeError: pass
                        print('Cycles GPU:', dev, [d.name for d in gpus], flush=True); break
                except TypeError: pass
        except Exception as e: print('GPU не найден, Cycles на CPU:', e, flush=True)
    return sc

def hdri(name, strength=1.0, rot=0.0):
    w = bpy.data.worlds.new('world'); bpy.context.scene.world = w; w.use_nodes = True
    nt = w.node_tree; bg = nt.nodes['Background']
    env = nt.nodes.new('ShaderNodeTexEnvironment'); env.image = bpy.data.images.load(A('hdri', name))
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
