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

if STAGE == 'control':
    # рисуем заново в утверждённом виде (SDXL), а расстановку берём из раскладки через карту глубины (ControlNet depth)
    # job: {"stage":"control","scale":0.6,"items":[{"name","depth","prompt","negative","seeds":[..]}]}
    from diffusers import StableDiffusionXLControlNetPipeline, ControlNetModel, AutoencoderKL
    cn = ControlNetModel.from_pretrained('diffusers/controlnet-depth-sdxl-1.0', torch_dtype=torch.float16, variant='fp16')
    vae = AutoencoderKL.from_pretrained('madebyollin/sdxl-vae-fp16-fix', torch_dtype=torch.float16)
    pipe = StableDiffusionXLControlNetPipeline.from_pretrained('stabilityai/stable-diffusion-xl-base-1.0', controlnet=cn, vae=vae, torch_dtype=torch.float16, variant='fp16').to('cuda')
    W, H = job.get('w', 1344), job.get('h', 768)
    for it in job['items']:
        d = np.asarray(Image.open(os.path.join(D, it['depth'])), np.float32); d = (d - d.min()) / max(1e-6, d.max() - d.min())
        ctl = Image.fromarray((d * 255).astype(np.uint8)).convert('RGB').resize((W, H))
        for seed in it.get('seeds', [1]):
            t0 = time.time()
            out = pipe(prompt=it['prompt'], negative_prompt=it.get('negative', job.get('negative', '')), image=ctl, width=W, height=H,
                       controlnet_conditioning_scale=it.get('scale', job.get('scale', 0.6)), num_inference_steps=job.get('steps', 34),
                       guidance_scale=it.get('cfg', 7.0), generator=torch.Generator('cuda').manual_seed(seed)).images[0]
            out.save(os.path.join(OUT, f"{it['name']}_c{seed}.png")); log('control', it['name'], seed, round(time.time() - t0, 1), 's')
    log('CONTROL DONE', round(time.time() - T0), 's'); sys.exit(0)

if STAGE == 'restyle':
    # перерисовка в утверждённый вид поверх готовой раскладки (кадр PixArt держит сюжет, SDXL даёт графику с тушью)
    # job: {"stage":"restyle","strength":0.55,"items":[{"name","image","prompt","negative","seeds":[..]}]}
    from diffusers import StableDiffusionXLImg2ImgPipeline, AutoencoderKL
    vae = AutoencoderKL.from_pretrained('madebyollin/sdxl-vae-fp16-fix', torch_dtype=torch.float16)
    pipe = StableDiffusionXLImg2ImgPipeline.from_pretrained('stabilityai/stable-diffusion-xl-base-1.0', vae=vae, torch_dtype=torch.float16, variant='fp16').to('cuda')
    for it in job['items']:
        img = Image.open(os.path.join(D, it['image'])).convert('RGB')
        for seed in it.get('seeds', [1]):
            t0 = time.time()
            out = pipe(prompt=it['prompt'], negative_prompt=it.get('negative', job.get('negative', '')), image=img, strength=it.get('strength', job.get('strength', 0.55)),
                       num_inference_steps=job.get('steps', 34), guidance_scale=it.get('cfg', 7.0), generator=torch.Generator('cuda').manual_seed(seed)).images[0]
            out.save(os.path.join(OUT, f"{it['name']}_r{seed}.png")); log('restyle', it['name'], seed, round(time.time() - t0, 1), 's')
    log('RESTYLE DONE', round(time.time() - T0), 's'); sys.exit(0)

if STAGE == 'fix':
    # точечная правка: перерисовать только область по маске (колесо, нога, лишняя статуя), остальной кадр не трогается
    # job: {"stage":"fix","fixes":[{"name","image","mask","prompt","negative","strength","seeds":[..]}]}  маска: белое = перерисовать
    from diffusers import AutoPipelineForInpainting
    pipe = AutoPipelineForInpainting.from_pretrained('diffusers/stable-diffusion-xl-1.0-inpainting-0.1', torch_dtype=torch.float16, variant='fp16').to('cuda')
    for fx in job['fixes']:
        img = Image.open(os.path.join(D, fx['image'])).convert('RGB'); W0, H0 = img.size
        W, H = (W0 // 8) * 8, (H0 // 8) * 8; img = img.resize((W, H)); m = Image.open(os.path.join(D, fx['mask'])).convert('L').resize((W, H))
        for seed in fx.get('seeds', [1, 2]):
            t0 = time.time()
            out = pipe(prompt=fx['prompt'], negative_prompt=fx.get('negative', job.get('negative', '')), image=img, mask_image=m, width=W, height=H,
                       strength=fx.get('strength', 0.9), num_inference_steps=fx.get('steps', 30), guidance_scale=fx.get('cfg', 7.0),
                       generator=torch.Generator('cuda').manual_seed(seed)).images[0]
            # склейка по размытой маске: вне маски пиксели исходного кадра
            import numpy as np
            from PIL import ImageFilter
            a = np.asarray(m.filter(ImageFilter.GaussianBlur(6)), np.float32)[..., None] / 255
            res = (np.asarray(out.resize((W, H)), np.float32) * a + np.asarray(img, np.float32) * (1 - a)).astype(np.uint8)
            Image.fromarray(res).resize((W0, H0)).save(os.path.join(OUT, f"{fx['name']}_fix{seed}.png")); log('fix', fx['name'], seed, round(time.time() - t0, 1), 's')
    log('FIX DONE', round(time.time() - T0), 's'); sys.exit(0)

if STAGE == 'key':
    from diffusers import StableDiffusionXLPipeline, AutoencoderKL
    W, H = job.get('w', 1344), job.get('h', 768)
    def load(mid):
        # PixArt-Sigma (T5): точнее слушается длинного описания сцены; SDXL: красивее фактура
        if 'PixArt' in mid:
            from diffusers import PixArtSigmaPipeline
            p = PixArtSigmaPipeline.from_pretrained(mid, torch_dtype=torch.float16); p.enable_model_cpu_offload(); return p
        vae = AutoencoderKL.from_pretrained('madebyollin/sdxl-vae-fp16-fix', torch_dtype=torch.float16)
        return StableDiffusionXLPipeline.from_pretrained(mid, vae=vae, torch_dtype=torch.float16, variant='fp16').to('cuda')
    pipe, cur = None, None
    for st in job['styles']:
        mid = st.get('model', job.get('model', 'stabilityai/stable-diffusion-xl-base-1.0'))
        if mid != cur:
            if pipe is not None: del pipe; gc.collect(); torch.cuda.empty_cache()
            pipe, cur = load(mid), mid; log('model', mid)
        for seed in st.get('seeds', [1, 2, 3, 4]):
            t0 = time.time()
            img = pipe(prompt=st['prompt'], negative_prompt=st.get('negative', job.get('negative', '')), width=W, height=H,
                       num_inference_steps=st.get('steps', job.get('steps', 34)), guidance_scale=st.get('cfg', 6.5), generator=torch.Generator('cuda').manual_seed(seed)).images[0]
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
