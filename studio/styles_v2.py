# Пробы стилей v2 (фильм на 17 минут): опорный кадр нейросетью, потом движение.
#   stage "key":   SDXL рисует опорные кадры по стилям (несколько сидов) + карта глубины (Depth Anything V2) для 2.5D-параллакса
#   stage "video": Wan 2.2 TI2V-5B оживляет выбранный опорный кадр (картинка -> видео), план делится на две T4
# Задание: films/styles_v2/*styles2.json. Запуск через neural/farm.py (farm.yml).
import os, sys, json, subprocess, time, gc, glob
JOB = sys.argv[1]; D = os.path.dirname(JOB); OUT = sys.argv[2] if len(sys.argv) > 2 else '/kaggle/working/out'
os.makedirs(OUT, exist_ok=True)
job = json.load(open(JOB)); STAGE = job['stage']
WORKER = os.environ.get('S2_WORKER')
def log(*a):
    print(*a, flush=True)
    with open(os.path.join(OUT, f'run_{(WORKER or "main").replace("/", "of")}.txt'), 'a') as f: print(*a, file=f)

if not WORKER:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-U', 'diffusers>=0.35', 'transformers>=4.51', 'accelerate', 'ftfy', 'imageio[ffmpeg]', 'av', 'sentencepiece'], check=False)
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
import torch, numpy as np
from PIL import Image
T0 = time.time()

if STAGE == 'key':
    from diffusers import StableDiffusionXLPipeline, AutoencoderKL
    vae = AutoencoderKL.from_pretrained('madebyollin/sdxl-vae-fp16-fix', torch_dtype=torch.float16)
    pipe = StableDiffusionXLPipeline.from_pretrained(job.get('model', 'stabilityai/stable-diffusion-xl-base-1.0'), vae=vae, torch_dtype=torch.float16, variant='fp16').to('cuda')
    W, H = job.get('w', 1344), job.get('h', 768)
    for st in job['styles']:
        for seed in st.get('seeds', [1, 2, 3, 4]):
            t0 = time.time()
            img = pipe(prompt=st['prompt'], negative_prompt=st.get('negative', job.get('negative', '')), width=W, height=H,
                       num_inference_steps=job.get('steps', 34), guidance_scale=st.get('cfg', 6.5), generator=torch.Generator('cuda').manual_seed(seed)).images[0]
            img.save(os.path.join(OUT, f"{st['name']}_s{seed}.png")); log('key', st['name'], seed, round(time.time() - t0, 1), 's')
    del pipe; gc.collect(); torch.cuda.empty_cache()
    from transformers import pipeline
    dp = pipeline('depth-estimation', model='depth-anything/Depth-Anything-V2-Large-hf', device=0)
    for p in sorted(glob.glob(os.path.join(OUT, '*_s*.png'))):
        im = Image.open(p).convert('RGB'); d = dp(im)['predicted_depth'].squeeze().float().cpu().numpy()
        d = np.array(Image.fromarray(d).resize(im.size, Image.BICUBIC)); d = (d - d.min()) / max(1e-6, d.max() - d.min())
        Image.fromarray((d * 65535).astype(np.uint16)).save(p.replace('.png', '_depth.png')); log('depth', os.path.basename(p))
    log('KEY DONE', round(time.time() - T0), 's'); sys.exit(0)

# ---- video: Wan 2.2 TI2V-5B ----
from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
MID = job.get('model', 'Wan-AI/Wan2.2-TI2V-5B-Diffusers'); W, H = job.get('w', 1024), job.get('h', 576); steps = job.get('steps', 30)
dt = torch.float16 if torch.cuda.get_device_capability(0)[0] < 8 else torch.bfloat16
EMBF = '/tmp/s2_emb.pt'
if not WORKER:
    # тексты кодируем один раз (UMT5-XXL ~11 ГБ в памяти), потом два воркера по одной T4 без текстового кодировщика
    pipe = WanImageToVideoPipeline.from_pretrained(MID, torch_dtype=dt)
    pipe.text_encoder.to('cuda'); E = {}
    NEG = job.get('negative', '')
    with torch.no_grad():
        for sh in job['shots']:
            pe, ne = pipe.encode_prompt(prompt=sh['prompt'], negative_prompt=sh.get('negative', NEG), do_classifier_free_guidance=True, device='cuda')
            E[sh['name']] = (pe.cpu(), ne.cpu())
    torch.save(E, EMBF); del pipe, E; gc.collect(); torch.cuda.empty_cache(); log('emb ok', round(time.time() - T0), 's')
    # по умолчанию один воркер: два сразу не помещаются в 29 ГБ памяти Kaggle (второй молча убивает OOM)
    n = min(job.get('workers', 1), int(subprocess.run('nvidia-smi -L | wc -l', shell=True, capture_output=True, text=True).stdout.strip() or 1))
    ps = [subprocess.Popen([sys.executable, __file__, JOB, OUT], env=dict(os.environ, S2_WORKER=f'{k}/{n}', CUDA_VISIBLE_DEVICES=str(k))) for k in range(n)]
    for p in ps: p.wait()
    log('VIDEO DONE', round(time.time() - T0), 's'); sys.exit(0)

k, n = map(int, WORKER.split('/'))
shots = job['shots'][k::n]
if not shots: sys.exit(0)
E = torch.load(EMBF)
vae = AutoencoderKLWan.from_pretrained(MID, subfolder='vae', torch_dtype=torch.float32)
pipe = WanImageToVideoPipeline.from_pretrained(MID, vae=vae, text_encoder=None, tokenizer=None, torch_dtype=dt)
pipe.enable_model_cpu_offload(); pipe.vae.enable_tiling()
import imageio.v3 as iio
for sh in shots:
    t0 = time.time(); pe, ne = E[sh['name']]; nf = (sh.get('frames', 49) - 1) // 4 * 4 + 1
    try:
        pdt = next(pipe.transformer.parameters()).dtype
        img = Image.open(os.path.join(D, sh['image'])).convert('RGB').resize((W, H), Image.LANCZOS)
        out = pipe(image=img, prompt_embeds=pe.to('cuda', pdt), negative_prompt_embeds=ne.to('cuda', pdt), height=H, width=W, num_frames=nf,
                   num_inference_steps=steps, guidance_scale=sh.get('cfg', 5.0), generator=torch.Generator('cpu').manual_seed(sh.get('seed', 7)), output_type='np').frames[0]
    except Exception:
        import traceback; open(os.path.join(OUT, sh['name'] + '_error.txt'), 'w').write(traceback.format_exc()); log('ERR', sh['name']); continue
    ok = np.isfinite(out).all() and np.nanmax(out) > 0.02
    out = (np.clip(np.nan_to_num(out), 0, 1) * 255).astype(np.uint8)
    iio.imwrite(os.path.join(OUT, sh['name'] + '.mp4'), out, fps=24, codec='libx264', quality=9)
    log('video', sh['name'], nf, 'frames', W, 'x', H, steps, 'steps', round(time.time() - t0), 's', 'ok' if ok else 'EMPTY')
