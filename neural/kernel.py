# Нейропроявка на GPU Kaggle: превиз-план движка -> карта глубины -> Wan2.1 VACE перерисовывает кадр
# с фактурой и светом по текстовому стилю, сохраняя камеру, композицию и движение.
# Запускается из GitHub Actions (.github/workflows/neural.yml); входы — датасет Kaggle с shots/*.mp4 и job.json.
import os, sys, json, glob, subprocess, time
import socket
try: socket.create_connection(('pypi.org', 443), 5); NET = True
except OSError: NET = False
print('интернет в ноутбуке:', NET, flush=True)
if not NET: print('НЕТ ИНТЕРНЕТА: на Kaggle нужно подтвердить телефон (Settings → Phone verification)'); sys.exit(2)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '-U', 'diffusers>=0.34', 'transformers>=4.51', 'accelerate', 'ftfy', 'imageio[ffmpeg]', 'sentencepiece'], check=False)
import torch, numpy as np, imageio.v3 as iio
from PIL import Image

IN = (glob.glob('/kaggle/input/**/job.json', recursive=True) or [None])[0]
if not IN: print('job.json не найден', glob.glob('/kaggle/input/**', recursive=True)[:40]); sys.exit(1)
D = os.path.dirname(IN)
job = json.load(open(IN)); OUT = '/kaggle/working/out'; os.makedirs(OUT, exist_ok=True)
W, H = job.get('w', 832), job.get('h', 480); steps = job.get('steps', 30)
print('GPU:', torch.cuda.get_device_name(0), 'bf16:', torch.cuda.is_bf16_supported(), flush=True)

from transformers import pipeline as hf_pipeline
depth = hf_pipeline('depth-estimation', model='depth-anything/Depth-Anything-V2-Small-hf', device=0)

def load_frames(p):
    fr = [Image.fromarray(f).convert('RGB').resize((W, H), Image.LANCZOS) for f in iio.imread(p, plugin='pyav')]
    n = len(fr); n4 = min(81, ((n + 2) // 4) * 4 + 1)
    while len(fr) < n4: fr.append(fr[-1])
    return fr[:n4], n

def to_depth(frames):
    ds = [np.array(depth(f)['depth'], dtype=np.float32) for f in frames]
    lo = min(d.min() for d in ds); hi = max(d.max() for d in ds)
    return [Image.fromarray(((d - lo) / (hi - lo + 1e-6) * 255).astype(np.uint8)).convert('RGB') for d in ds]

from diffusers import AutoencoderKLWan, WanVACEPipeline, UniPCMultistepScheduler
MID = 'Wan-AI/Wan2.1-VACE-1.3B-diffusers'
dt = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
vae = AutoencoderKLWan.from_pretrained(MID, subfolder='vae', torch_dtype=torch.float32)
pipe = WanVACEPipeline.from_pretrained(MID, vae=vae, torch_dtype=dt)
pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=3.0)
pipe.enable_model_cpu_offload()
NEG = job.get('negative', 'cartoon, cgi, video game, plastic, low detail, blurry, deformed, extra limbs, text, watermark, overexposed, flicker')

for sh in job['shots']:
    t0 = time.time()
    frames, n = load_frames(os.path.join(D, 'shots', sh['file']))
    ctrl = to_depth(frames)
    iio.imwrite(os.path.join(OUT, sh['file'].replace('.mp4', '_depth.mp4')), np.stack([np.array(c) for c in ctrl]), fps=24, codec='libx264')
    mask = [Image.new('L', (W, H), 255)] * len(ctrl)
    def run(p):
        return p(video=ctrl, mask=mask, prompt=job['style'] + ' ' + sh['prompt'], negative_prompt=NEG, height=H, width=W,
                 num_frames=len(ctrl), num_inference_steps=steps, guidance_scale=5.0, conditioning_scale=sh.get('strength', 1.0),
                 generator=torch.Generator('cpu').manual_seed(sh.get('seed', 7)), output_type='np').frames[0]
    out = run(pipe)
    if not np.isfinite(out).all() or out.max() < 0.02:          # fp16 переполнился -> повтор в fp32
        print('fp16 дал пустой кадр, повтор в fp32', flush=True); pipe.to(torch.float32); out = run(pipe)
    out = (np.clip(out[:n], 0, 1) * 255).astype(np.uint8)
    iio.imwrite(os.path.join(OUT, sh['file']), out, fps=24, codec='libx264', quality=9)
    print('готово', sh['file'], len(out), 'кадров', round(time.time() - t0), 'с', flush=True)
print('ALL DONE')
