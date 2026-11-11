# Нейро-финиш на GPU Kaggle (Wan 2.1 VACE): рендер ядра даёт форму, свет, камеру и движение,
# модель дорисовывает фотореальные лицо и фактуру. Лицо Джека держится по эталонной карточке (reference_images),
# поэтому во всех планах это один человек.
# Режимы плана (job.json -> shots[].mode):
#   'face'  — перерисовать только область маски (кожа лица), всё остальное кадра остаётся рендером ядра;
#   'depth' — перерисовать весь кадр по глубине ядра (больше реализма, больше свободы модели);
#   'hybrid' — весь кадр по глубине, но объекты «держать» (шлем, байк) и небо приходят из рендера ядра как
#              контекст (VACE видит их и подгоняет свет), а в итоге вклеиваются обратно точно.
#   'refine' — «проявитель»: рендер ядра зашумляется на долю denoise (0.3–0.6) и восстанавливается моделью Wan 2.1 (видео→видео).
#              Форма, черты и движение остаются от рендера (не плывут), модель добавляет поры, пряди, блики в глазах.
#              Нужен shots[].ids — видео/кадры studio/idmask.py: R кожа, G держать, B небо.
# Запуск: neural/farm.py, если в farm.json script указывает на job.json задания.
import os, sys, json, glob, subprocess, time, gc
JOB = sys.argv[1]; D = os.path.dirname(JOB); OUT = sys.argv[2] if len(sys.argv) > 2 else '/kaggle/working/out'
os.makedirs(OUT, exist_ok=True)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-U', 'diffusers>=0.34', 'transformers>=4.51', 'accelerate', 'ftfy',
                'imageio[ffmpeg]', 'av', 'sentencepiece'], check=False)
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
import torch, numpy as np, imageio.v3 as iio
from PIL import Image, ImageFilter

job = json.load(open(JOB)); W, H = job.get('w', 832), job.get('h', 480); steps = job.get('steps', 30)
print('GPU:', torch.cuda.get_device_name(0), flush=True)

def frames(path, mode='RGB'):
    fs = sorted(glob.glob(os.path.join(D, path, '*.png'))) if os.path.isdir(os.path.join(D, path)) else None
    imgs = [Image.open(f).convert(mode) for f in fs] if fs else [Image.fromarray(f).convert(mode) for f in iio.imread(os.path.join(D, path), plugin='pyav')]
    imgs = [i.resize((W, H), Image.LANCZOS) for i in imgs]
    n = len(imgs); n4 = min(81, ((n - 1 + 3) // 4) * 4 + 1)
    while len(imgs) < n4: imgs.append(imgs[-1])
    return imgs[:n4], n

def depth_maps(fr):
    from transformers import pipeline as hp
    dp = hp('depth-estimation', model='depth-anything/Depth-Anything-V2-Small-hf', device=0)
    ds = [np.array(dp(f)['depth'], dtype=np.float32) for f in fr]; lo = min(d.min() for d in ds); hi = max(d.max() for d in ds)
    del dp; gc.collect(); torch.cuda.empty_cache()
    return [Image.fromarray(((d - lo) / (hi - lo + 1e-6) * 255).astype(np.uint8)).convert('RGB') for d in ds]

PREP = {}
for sh in job['shots']:
    src, n = frames(sh['src'])
    if sh.get('mode', 'face') == 'face':
        mk, _ = frames(sh['mask'], 'L')
        mk = [m.point(lambda v: 255 if v > 40 else 0).filter(ImageFilter.MaxFilter(17)).filter(ImageFilter.MinFilter(7)).filter(ImageFilter.GaussianBlur(2)) for m in mk]
        vid = [Image.composite(Image.new('RGB', (W, H), (127, 127, 127)), s, m) for s, m in zip(src, mk)]
    elif sh['mode'] == 'refine':
        vid = src; mk = None
    elif sh['mode'] == 'hybrid':
        ids, _ = frames(sh['ids'])
        keep = [Image.fromarray((np.array(i)[..., 1:].max(-1) > 100).astype(np.uint8) * 255) for i in ids]
        g = sh.get('grow', 5)   # на сколько пикселей генерация заходит за край зоны (волосам нужен запас под выбившиеся пряди)
        mk = [k.point(lambda v: 255 - v).filter(ImageFilter.MaxFilter(g)).filter(ImageFilter.GaussianBlur(1)) for k in keep]
        dep = depth_maps(src)
        vid = [Image.composite(d, s, m) for d, s, m in zip(dep, src, mk)]   # в зоне генерации — глубина, вне — сам рендер
        kf = [k.filter(ImageFilter.MinFilter(g)).filter(ImageFilter.GaussianBlur(2)) for k in keep]   # мягкая вклейка обратно
    else:
        vid = depth_maps(src); mk = [Image.new('L', (W, H), 255)] * len(vid)
    ref = [Image.open(os.path.join(D, r)).convert('RGB') for r in sh.get('refs', job.get('refs', []))]
    PREP[sh['name']] = (src, vid, mk, ref, n, kf if sh.get('mode') == 'hybrid' else None)
    if sh.get('mode') != 'refine': iio.imwrite(os.path.join(OUT, sh['name'] + '_input.mp4'), np.stack([np.array(v) for v in vid]), fps=24, codec='libx264')

from diffusers import AutoencoderKLWan, WanVACEPipeline, WanVideoToVideoPipeline, UniPCMultistepScheduler
REFINE = all(sh.get('mode') == 'refine' for sh in job['shots'])   # одно задание — один режим модели
MID = job.get('model', 'Wan-AI/Wan2.1-T2V-1.3B-Diffusers' if REFINE else 'Wan-AI/Wan2.1-VACE-1.3B-diffusers')
dt = torch.bfloat16 if torch.cuda.get_device_capability(0)[0] >= 8 else torch.float16
vae = AutoencoderKLWan.from_pretrained(MID, subfolder='vae', torch_dtype=torch.float32)
pipe = (WanVideoToVideoPipeline if REFINE else WanVACEPipeline).from_pretrained(MID, vae=vae, torch_dtype=dt)
pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=3.0)
NEG = job.get('negative', 'cartoon, cgi, video game, 3d render, plastic skin, wax, doll, low detail, blurry, deformed face, asymmetric eyes, beard, long sideburns, text, watermark, flicker')
pipe.text_encoder.to('cuda'); EMB = {}
with torch.no_grad():
    for sh in job['shots']:
        pe, ne = pipe.encode_prompt(prompt=job['style'] + ' ' + sh['prompt'], negative_prompt=NEG, do_classifier_free_guidance=True, device='cuda')
        EMB[sh['name']] = (pe.to('cpu'), ne.to('cpu'))
pipe.text_encoder = None; gc.collect(); torch.cuda.empty_cache()
pipe.to('cuda'); pipe.vae.enable_tiling()

for sh in job['shots']:
    t0 = time.time(); src, vid, mk, ref, n, kf = PREP[sh['name']]
    pe, ne = EMB[sh['name']]
    def run():
        pdt = next(pipe.transformer.parameters()).dtype
        if REFINE:
            return pipe(video=vid, prompt_embeds=pe.to('cuda', pdt), negative_prompt_embeds=ne.to('cuda', pdt), height=H, width=W,
                        num_inference_steps=steps, strength=sh.get('denoise', 0.4), guidance_scale=sh.get('cfg', 5.0),
                        generator=torch.Generator('cpu').manual_seed(sh.get('seed', 7)), output_type='np').frames[0]
        return pipe(video=vid, mask=mk, reference_images=ref or None, prompt_embeds=pe.to('cuda', pdt), negative_prompt_embeds=ne.to('cuda', pdt),
                    height=H, width=W, num_frames=len(vid), num_inference_steps=steps, guidance_scale=sh.get('cfg', 5.0),
                    conditioning_scale=sh.get('strength', 1.0), generator=torch.Generator('cpu').manual_seed(sh.get('seed', 7)), output_type='np').frames[0]
    out = run()
    if not np.isfinite(out).all() or out.max() < 0.02:
        print('fp16 дал пустой кадр, повтор в fp32', flush=True); pipe.transformer.to(torch.float32); out = run()
    out = (np.clip(out[:n], 0, 1) * 255).astype(np.uint8)
    if sh.get('mode', 'face') == 'face':   # вне маски — точно рендер ядра (модель не трогает шлем, куртку, фон)
        out = np.stack([np.array(Image.composite(Image.fromarray(o), s, m)) for o, s, m in zip(out, src[:n], mk[:n])])
    if kf:   # шлем, байк, небо — точно из ядра
        out = np.stack([np.array(Image.composite(s, Image.fromarray(o), k)) for o, s, k in zip(out, src[:n], kf[:n])])
    iio.imwrite(os.path.join(OUT, sh['name'] + '.mp4'), out, fps=24, codec='libx264', quality=9)
    side = np.concatenate([np.stack([np.array(s) for s in src[:n]]), out], axis=2)
    iio.imwrite(os.path.join(OUT, sh['name'] + '_before_after.mp4'), side, fps=24, codec='libx264', quality=9)
    print('готово', sh['name'], n, 'кадров', round(time.time() - t0), 'с', flush=True)
print('ALL DONE')
