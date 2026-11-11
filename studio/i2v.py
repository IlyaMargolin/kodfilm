# План целиком нейросетью от первого кадра (лист персонажа или опорный кадр): Wan 2.2 TI2V-5B, картинка -> видео.
# Задание (…i2v.json): { "w": 896, "h": 800, "steps": 30, "style": "...", "shots": [ { "name", "image", "prompt", "frames": 81, "seed", "cfg" } ] }
# Без "image" план делается только по тексту. Запуск: neural/farm.py, если script указывает на *i2v.json.
import os, sys, json, subprocess, time, gc
JOB = sys.argv[1]; D = os.path.dirname(JOB); OUT = sys.argv[2] if len(sys.argv) > 2 else '/kaggle/working/out'
os.makedirs(OUT, exist_ok=True)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-U', 'diffusers>=0.35', 'transformers>=4.51', 'accelerate', 'ftfy', 'imageio[ffmpeg]', 'av', 'sentencepiece'], check=False)
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
import torch, numpy as np, imageio.v3 as iio
from PIL import Image
from diffusers import AutoencoderKLWan, WanImageToVideoPipeline, WanPipeline
job = json.load(open(JOB)); W, H = job.get('w', 896), job.get('h', 800); steps = job.get('steps', 30)
MID = job.get('model', 'Wan-AI/Wan2.2-TI2V-5B-Diffusers')
print('GPU:', torch.cuda.get_device_name(0), MID, flush=True)
dt = torch.bfloat16 if torch.cuda.get_device_capability(0)[0] >= 8 else torch.float16
vae = AutoencoderKLWan.from_pretrained(MID, subfolder='vae', torch_dtype=torch.float32)
I2V = any(sh.get('image') for sh in job['shots'])
pipe = (WanImageToVideoPipeline if I2V else WanPipeline).from_pretrained(MID, vae=vae, torch_dtype=dt)
NEG = job.get('negative', 'cartoon, cgi, video game, plastic skin, wax, doll, low detail, blurry, deformed face, asymmetric eyes, extra fingers, text, watermark, subtitles, flicker, static frame')
pipe.text_encoder.to('cuda'); EMB = {}
with torch.no_grad():
    for sh in job['shots']:
        pe, ne = pipe.encode_prompt(prompt=job.get('style', '') + ' ' + sh['prompt'], negative_prompt=NEG, do_classifier_free_guidance=True, device='cuda')
        EMB[sh['name']] = (pe.to('cpu'), ne.to('cpu'))
pipe.text_encoder = None; gc.collect(); torch.cuda.empty_cache()
pipe.enable_model_cpu_offload(); pipe.vae.enable_tiling()   # VAE и трансформер по очереди: вместе не помещаются в 15 ГБ T4
for sh in job['shots']:
    t0 = time.time(); pe, ne = EMB[sh['name']]; n = sh.get('frames', 81); n = (n - 1) // 4 * 4 + 1
    def run():
        pdt = next(pipe.transformer.parameters()).dtype
        kw = dict(prompt_embeds=pe.to('cuda', pdt), negative_prompt_embeds=ne.to('cuda', pdt), height=H, width=W, num_frames=n, num_inference_steps=steps,
                  guidance_scale=sh.get('cfg', 5.0), generator=torch.Generator('cpu').manual_seed(sh.get('seed', 7)), output_type='np')
        if sh.get('image'): kw['image'] = Image.open(os.path.join(D, sh['image'])).convert('RGB').resize((W, H), Image.LANCZOS)
        return pipe(**kw).frames[0]
    try:
        out = run()
    except Exception as e:
        import traceback; traceback.print_exc(); open(os.path.join(OUT, sh['name'] + '_error.txt'), 'w').write(traceback.format_exc()); continue
    ok = np.isfinite(out).all() and out.max() > 0.02
    print('кадры', out.shape, 'min', float(np.nanmin(out)), 'max', float(np.nanmax(out)), 'годно' if ok else 'ПУСТО (fp16?)', flush=True)
    out = (np.clip(np.nan_to_num(out), 0, 1) * 255).astype(np.uint8)
    iio.imwrite(os.path.join(OUT, sh['name'] + '.mp4'), out, fps=job.get('fps', 24), codec='libx264', quality=9)
    print('готово', sh['name'], n, 'кадров', round(time.time() - t0), 'с', flush=True)
print('ALL DONE')
