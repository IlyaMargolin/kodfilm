"""Тест набора природы: судно идёт по фьорду в холодном контровом свете (по мотивам референса Ильи).
python studio/kit/fjord_test.py --out out/fjord --w 1280 --samples 64 [--frames 1-48]"""
import sys, os, math, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import bpy
import world, lens
from kit import nature, props

ap = argparse.ArgumentParser(); ap.add_argument('--out', default='out/fjord'); ap.add_argument('--w', type=int, default=1280)
ap.add_argument('--samples', type=int, default=64); ap.add_argument('--frames', default='1'); ap.add_argument('--fps', type=int, default=24)
ap.add_argument('--lens', default='cinema')
a = ap.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else sys.argv[1:])
h = int(round(a.w / 2.39 / 2)) * 2
sc = world.new_scene(a.w, h, a.fps, engine='CYCLES', TAA=a.samples)
sc.view_settings.look = 'AgX - High Contrast'; sc.view_settings.exposure = 0.3
lens.setup(sc, a.lens)

# небо: пасмурный холодный купол + низкое солнце в конце фьорда (контровой: дорожка бликов на воде)
w = bpy.data.worlds.new('sky'); sc.world = w; w.use_nodes = True
sk = w.node_tree.nodes.new('ShaderNodeTexSky')
try: sk.sky_type = 'MULTIPLE_SCATTERING'
except TypeError: sk.sky_type = 'NISHITA'
for k, v in dict(sun_elevation=math.radians(14), sun_rotation=math.radians(90), altitude=50, air_density=2.0, dust_density=6.0, sun_disc=True).items():
    if hasattr(sk, k): setattr(sk, k, v)
w.node_tree.links.new(sk.outputs[0], w.node_tree.nodes['Background'].inputs[0]); w.node_tree.nodes['Background'].inputs[1].default_value = 0.12
sun = world.sun(14, 180, strength=2.0, color=(0.92, 0.95, 1.0), angle_deg=1.5)

oc, md = nature.ocean(size=220, res=16, wave_scale=1.0, chop=1.5, wind=11)
nature.cliffs(length=320, height=140, gap=60, depth=50)
nature.fog_volume(density=0.0006, anisotropy=0.45)
ship = props.ship(loc=(0, 0, 0.1), heading=0)

cam_d = bpy.data.cameras.new('cam'); cam_d.lens = 40; cam_d.sensor_width = 24.89
cam_d.dof.use_dof = True; cam_d.dof.aperture_fstop = 4.0
cam = bpy.data.objects.new('cam', cam_d); sc.collection.objects.link(cam); sc.camera = cam
cam_d.dof.focus_object = ship

frames = list(range(int(a.frames.split('-')[0]), int(a.frames.split('-')[-1]) + 1))
os.makedirs(a.out, exist_ok=True)
for f in frames:
    t = (f - 1) / a.fps
    md.time = 1.0 + t                                    # волны живут во времени
    ship.location = (0, 4.0 * t, 0.1 + 0.18 * math.sin(t * 1.3))   # ~8 узлов, лёгкая качка
    ship.rotation_euler = (0.025 * math.sin(t * 1.1), 0.04 * math.sin(t * 0.8 + 1), 0)
    cam.location = (3.0 + 0.6 * math.sin(t * 0.3), ship.location.y - 40 + 1.5 * t, 7.0 + 0.25 * math.sin(t * 0.9))
    tgt = ship.location.copy(); tgt.y += 22; tgt.z += 1.0
    d = tgt - cam.location; cam.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    sc.frame_set(f); sc.render.filepath = os.path.abspath(f'{a.out}/f_{f:05d}.png')
    bpy.ops.render.render(write_still=True); print('frame', f, flush=True)
