# GPU-ферма на Kaggle: тот же движок (studio/film.py), но Cycles — трассировка путей на видеокартах T4.
# Физичный свет: настоящие блики и отражения, объёмные лучи сквозь арки, каустика, мягкие тени, денойз OptiX.
# Запускается из .github/workflows/farm.yml; вход — датасет с кодом студии и farm.json.
import os, sys, json, glob, subprocess, shutil, time
J = (glob.glob('/kaggle/input/**/farm.json', recursive=True) or [None])[0]
if not J: print('farm.json не найден'); sys.exit(1)
SRC = os.path.dirname(J); job = json.load(open(J)); W = '/kaggle/working/kf'; OUT = '/kaggle/working/out'
shutil.copytree(SRC, W, dirs_exist_ok=True); os.makedirs(OUT, exist_ok=True)
sh = lambda c: subprocess.run(c, shell=True, check=False)
sh(f'{sys.executable} -m pip install -q bpy==5.2.3 soundfile')
sh('apt-get -qq install -y libxi6 libxxf86vm1 libxfixes3 libxrender1 libsm6 libgl1 libegl1 >/dev/null 2>&1 || true')
sh(f'cd {W} && bash assets/fetch.sh')
n = int(subprocess.run('nvidia-smi -L | wc -l', shell=True, capture_output=True, text=True).stdout.strip() or 1)
print('GPU:', subprocess.run('nvidia-smi -L', shell=True, capture_output=True, text=True).stdout, flush=True)
t0 = time.time(); procs = []
args = f"--script {job['script']} --out {OUT}/frames --w {job.get('w', 1920)} --engine cycles --samples {job.get('samples', 96)}"
if job.get('frames'): args += f" --frames {job['frames']}"
for k in range(n):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(k))
    procs.append(subprocess.Popen(f'cd {W} && {sys.executable} studio/film.py -- {args} --chunk {k} --chunks {n} > {OUT}/log_{k}.txt 2>&1', shell=True, env=env))
for p in procs: p.wait()
fr = sorted(glob.glob(f'{OUT}/frames/f_*.png'))
print('кадров:', len(fr), 'за', round(time.time() - t0), 'с', flush=True)
for k in range(n): sh(f'grep -E "Cycles GPU|Traceback|Error" {OUT}/log_{k}.txt | head -5; tail -3 {OUT}/log_{k}.txt')
if fr:
    first = int(os.path.basename(fr[0])[2:7])
    sh(f'ffmpeg -loglevel error -y -framerate 24 -start_number {first} -i {OUT}/frames/f_%05d.png -c:v libx264 -preset slow -crf 10 -pix_fmt yuv420p {OUT}/frames.mp4')
    shutil.copy(f'{OUT}/frames/meta.json', f'{OUT}/meta.json')
    shutil.rmtree(f'{OUT}/frames')          # PNG не тащим обратно: mp4 почти без потерь
print('ALL DONE')
