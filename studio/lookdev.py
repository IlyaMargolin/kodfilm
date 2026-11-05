# Look-dev: одна тестовая сцена в каждом пресете пульта стиля — лист «стиль × план», как в студиях перед производством.
# Видно, что каждый инструмент реально работает (свет, воздух, оптика, цвет, неон), и пресеты не ломают друг друга.
# python studio/lookdev.py [--presets кино,pixar,нуар,неон,тун] [--frames 165,200] [--w 480] [--samples 16]
#   → out/lookdev/<пресет>/f_*.png и out/lookdev/sheet.png (строки — пресеты, столбцы — кадры)
import argparse, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser()
ap.add_argument('--script', default='films/hram/script.txt'); ap.add_argument('--hero', default='pilgrim')
ap.add_argument('--presets', default='кино,pixar,нуар,неон,тун'); ap.add_argument('--frames', default='165,200')
ap.add_argument('--w', type=int, default=480); ap.add_argument('--samples', type=int, default=16)
ap.add_argument('--out', default='out/lookdev')
a = ap.parse_args()
presets = a.presets.split(','); frames = [int(x) for x in a.frames.split(',')]
for p in presets:
    d = os.path.join(ROOT, a.out, p)
    if all(os.path.exists(os.path.join(d, f'f_{f:05d}.png')) for f in frames): continue
    cmd = [sys.executable, os.path.join(ROOT, 'studio', 'film.py'), '--script', a.script, '--hero', a.hero, '--look', p,
           '--engine', 'cycles', '--samples', str(a.samples), '--w', str(a.w), '--frames', a.frames, '--out', d]
    print('lookdev:', p, flush=True)
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if r.returncode: print(r.stdout[-2000:], r.stderr[-2000:]); sys.exit(f'lookdev: пресет {p} упал')
    for line in r.stdout.splitlines():
        if line.startswith(('вид:', 'неон:')): print('  ', line, flush=True)
# лист: строки — пресеты, столбцы — кадры; подпись пресета в углу (если у ffmpeg есть drawtext)
inputs, rows = [], []
for i, p in enumerate(presets):
    for j, f in enumerate(frames): inputs += ['-i', os.path.join(ROOT, a.out, p, f'f_{f:05d}.png')]
n = len(frames); fc = ''
for i, p in enumerate(presets):
    fc += ''.join(f'[{i * n + j}]' for j in range(n)) + (f'hstack=inputs={n}' if n > 1 else 'null') + f'[r{i}];'
fc += ''.join(f'[r{i}]' for i in range(len(presets))) + (f'vstack=inputs={len(presets)}' if len(presets) > 1 else 'null')
sheet = os.path.join(ROOT, a.out, 'sheet.png')
subprocess.run(['ffmpeg', '-v', 'error', '-y', *inputs, '-filter_complex', fc, sheet], check=True)
print('лист:', sheet, '— строки:', ', '.join(presets))
