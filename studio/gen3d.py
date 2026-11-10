# 3D-модели прямо с листов персонажей (Hunyuan3D-2mv, открытые веса) на GPU Kaggle: по видам «спереди / слева / сзади»
# строит сетку и рисует на неё текстуру с того же листа. Выход: <name>.glb (с текстурой) и <name>_shape.glb (только форма).
# Запуск: neural/farm.py, если в farm.json script указывает на gen3d.json;  python studio/gen3d.py <gen3d.json> <out>
import os, sys, json, subprocess, time, gc, traceback
JOB = sys.argv[1]; D = os.path.dirname(JOB); OUT = sys.argv[2] if len(sys.argv) > 2 else '/kaggle/working/out'
os.makedirs(OUT, exist_ok=True); job = json.load(open(JOB))
sh = lambda c: subprocess.run(c, shell=True, check=False)
H = '/tmp/Hunyuan3D-2'
if not os.path.isdir(H):
    sh(f'git clone -q --depth 1 https://github.com/Tencent/Hunyuan3D-2.git {H}')
    sh(f"cd {H} && grep -viE '^(torch|torchvision|torchaudio|numpy|gradio|fastapi|uvicorn|bpy)([=<>~ ]|$)' requirements.txt > req.txt; cat req.txt; {sys.executable} -m pip install -q -r req.txt")
    sh(f'{sys.executable} -m pip install -q rembg onnxruntime pybind11 ninja')
    sh(f"{sys.executable} -m pip install -q 'transformers==4.48.3'")   # новее — другие имена слоёв DINOv2, веса не грузятся
    sh(f'cd {H} && {sys.executable} -m pip install -q --no-deps -e .')
    if job.get('texture', True):
        sh(f'cd {H}/hy3dgen/texgen/custom_rasterizer && {sys.executable} setup.py install > {OUT}/install_rast.txt 2>&1; tail -3 {OUT}/install_rast.txt')
        sh(f'cd {H}/hy3dgen/texgen/differentiable_renderer && {sys.executable} setup.py install > {OUT}/install_dr.txt 2>&1; tail -3 {OUT}/install_dr.txt')
sys.path.insert(0, H)
sh(f"{sys.executable} -m pip list 2>/dev/null | grep -iE '^(transformers|diffusers|torch|pymeshlab|trimesh|xatlas|custom.rasterizer|mesh.processor) ' > {OUT}/versions.txt; cat {OUT}/versions.txt")
import torch
from PIL import Image
print('GPU:', torch.cuda.get_device_name(0), round(torch.cuda.get_device_properties(0).total_memory / 2 ** 30, 1), 'ГБ', flush=True)
from hy3dgen.rembg import BackgroundRemover
from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline, FaceReducer, FloaterRemover, DegenerateFaceRemover
rem = BackgroundRemover()
def view(p):
    im = rem(Image.open(os.path.join(D, p)).convert('RGB'))
    bb = im.getbbox(); im = im.crop(bb); s = int(max(im.size) * 1.12)   # объект по центру квадрата
    q = Image.new('RGBA', (s, s), (0, 0, 0, 0)); q.paste(im, ((s - im.width) // 2, (s - im.height) // 2)); return q.resize((1024, 1024), Image.LANCZOS)
VIEWS = {}
for ob in job['objects']:
    VIEWS[ob['name']] = {k: view(p) for k, p in ob['views'].items()}
    for k, im in VIEWS[ob['name']].items(): im.save(os.path.join(OUT, f"{ob['name']}_{k}_cut.png"))
del rem; gc.collect()
pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained('tencent/Hunyuan3D-2mv', subfolder='hunyuan3d-dit-v2-mv', variant='fp16')
MESH = {}
for ob in job['objects']:
    t0 = time.time(); n = ob['name']
    try:
        m = pipe(image=VIEWS[n], num_inference_steps=job.get('steps', 30), octree_resolution=job.get('octree', 380), num_chunks=20000,
                 generator=torch.manual_seed(ob.get('seed', 12345)), output_type='trimesh')[0]
        for f in (FloaterRemover(), DegenerateFaceRemover()): m = f(m)
        m = FaceReducer()(m, max_facenum=job.get('faces', 200000))
        m.export(os.path.join(OUT, n + '_shape.glb')); MESH[n] = m
        print('форма', n, len(m.faces), 'граней', round(time.time() - t0), 'с', flush=True)
    except Exception: traceback.print_exc()
del pipe; gc.collect(); torch.cuda.empty_cache()
if job.get('texture', True):
    try:
        from hy3dgen.texgen import Hunyuan3DPaintPipeline
        paint = Hunyuan3DPaintPipeline.from_pretrained('tencent/Hunyuan3D-2')
        try: paint.enable_model_cpu_offload()
        except Exception as e: print('offload нет:', e)
        for n, m in MESH.items():
            t0 = time.time()
            try:
                v = VIEWS[n]; imgs = [v[k] for k in ('front', 'left', 'back') if k in v]
                try: tm = paint(m, image=imgs)
                except Exception: traceback.print_exc(); tm = paint(m, image=imgs[0])
                tm.export(os.path.join(OUT, n + '.glb')); print('текстура', n, round(time.time() - t0), 'с', flush=True)
            except Exception: traceback.print_exc()
            gc.collect(); torch.cuda.empty_cache()
    except Exception: traceback.print_exc()
print('ALL DONE')
