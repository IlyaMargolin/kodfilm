# Увеличение видов с листа персонажа перед проекцией на модель: Real-ESRGAN x4 (spandrel, на CPU около 40 с на вид).
#   python studio/upscale.py in_cut.png out.png [in2 out2 ...]   (PNG с альфой из studio/gen3d.py -> 2048 px)
# Веса: RealESRGAN_x4plus.pth из релиза xinntao/Real-ESRGAN v0.1.0, путь в ESRGAN_PTH (иначе скачиваются в /tmp).
import os, urllib.request
PTH = os.environ.get('ESRGAN_PTH', '/tmp/RealESRGAN_x4plus.pth')
if not os.path.exists(PTH): urllib.request.urlretrieve('https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth', PTH)
import sys, torch, cv2, numpy as np
from spandrel import ModelLoader
m = ModelLoader().load_from_file(PTH).model.eval()
for src, dst in zip(sys.argv[1::2], sys.argv[2::2]):
    a = cv2.imread(src, -1); al = a[..., 3]; rgb = a[..., :3].astype(np.float32)
    # фон под альфой — серый, чтобы край не тянул чёрное
    w = (al[..., None] / 255.0); rgb = rgb * w + 127 * (1 - w)
    s = cv2.resize(rgb, (512, 512), interpolation=cv2.INTER_AREA)
    t = torch.from_numpy(s[..., ::-1].copy() / 255).permute(2, 0, 1)[None].float()
    with torch.no_grad(): o = m(t)[0].clamp(0, 1).permute(1, 2, 0).numpy()[..., ::-1] * 255
    A = cv2.resize(al, (o.shape[1], o.shape[0]), interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(dst, np.dstack([o, A]).astype(np.uint8)); print(dst, o.shape, flush=True)
