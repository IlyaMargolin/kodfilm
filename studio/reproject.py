# Проекция исходных видов листа на 3D-модель и запекание в её текстуру: резкость листа вместо мягкой текстуры генератора.
# Виды — вырезки *_cut.png из studio/gen3d.py (объект по центру квадрата с полем 12 %, фон прозрачный), проекция ортогональная.
# Вес вида в каждой точке = (нормаль · направление на камеру)^p × альфа; где ни один вид не смотрит — остаётся текстура генератора.
#   python studio/reproject.py -- model.glb out.glb front=a.png left=b.png back=c.png [size=4096] [fit=1.12]
import sys, os
import bpy, numpy as np
from mathutils import Vector
a = sys.argv[sys.argv.index('--') + 1:]; src, out = a[0], a[1]
opt = dict(x.split('=', 1) for x in a[2:]); SIZE = int(opt.pop('size', 4096)); FIT = float(opt.pop('fit', 1.12)); POW = float(opt.pop('pow', 3))
VIEW = dict(front=((0, -1, 0), (1, 0, 0)), left=((1, 0, 0), (0, 1, 0)), back=((0, 1, 0), (-1, 0, 0)), right=((-1, 0, 0), (0, -1, 0)))  # к камере, вправо в кадре
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
ob = next(o for o in bpy.context.scene.objects if o.type == 'MESH'); bpy.context.view_layer.objects.active = ob; ob.select_set(True)
bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM'); bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
P = np.array([v.co[:] for v in ob.data.vertices])
mat = ob.data.materials[0]; NT = mat.node_tree; N = NT.nodes; L = NT.links
base = next(n for n in N if n.type == 'TEX_IMAGE')
for n in [n for n in N if n.type in ('BSDF_PRINCIPLED', 'OUTPUT_MATERIAL')]: N.remove(n)
geo = N.new('ShaderNodeNewGeometry')
def vec(v):
    n = N.new('ShaderNodeCombineXYZ'); n.inputs[0].default_value, n.inputs[1].default_value, n.inputs[2].default_value = v; return n.outputs[0]
def dot(x, v):
    n = N.new('ShaderNodeVectorMath'); n.operation = 'DOT_PRODUCT'; L.new(x, n.inputs[0]); L.new(vec(v), n.inputs[1]); return n.outputs['Value']
def math(op, x, y=None, clamp=False):
    n = N.new('ShaderNodeMath'); n.operation = op; n.use_clamp = clamp
    for i, q in enumerate((x, y)):
        if q is None: continue
        if isinstance(q, (int, float)): n.inputs[i].default_value = q
        else: L.new(q, n.inputs[i])
    return n.outputs[0]
def mixc(f, c1, c2):
    n = N.new('ShaderNodeMix'); n.data_type = 'RGBA'; L.new(f, n.inputs['Factor'])
    L.new(c1, n.inputs[6]); L.new(c2, n.inputs[7]); return n.outputs[2]   # цветовые гнёзда (по имени 'A' попадает числовое)
def register(x, y, path, cx, cy, S, R=256):
    """Совмещение силуэта модели с альфой вырезки: перебор масштаба и сдвига по совпадению масок (IoU), от грубого к точному.
    Лист обрезает плечи рамкой, поэтому простая подгонка по габаритам врёт — сверяем форму, верх (голова) весит больше."""
    from PIL import Image, ImageFilter
    A = np.array(Image.open(path).convert('RGBA').resize((R, R), Image.LANCZOS))[..., 3] > 128
    wrow = np.linspace(2.0, 0.6, R)[:, None]          # строки сверху вниз: голова важнее обрезанных плеч
    def mask(cx, cy, S):
        u = ((x - cx) / S + 0.5) * R; v = (0.5 - (y - cy) / S) * R
        ok = (u >= 0) & (u < R) & (v >= 0) & (v < R); M = np.zeros((R, R), np.uint8); M[v[ok].astype(int), u[ok].astype(int)] = 255
        return np.array(Image.fromarray(M).filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(3))) > 0
    def score(c):
        M = mask(*c); return ((M & A) * wrow).sum() / (((M | A) * wrow).sum() + 1e-6)
    best = (cx, cy, S); bs = score(best); step = 0.06
    for it in range(5):
        for ds in (-1, 0, 1):
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    c = (best[0] + dx * step * S, best[1] + dy * step * S, best[2] * (1 + ds * step)); q = score(c)
                    if q > bs: bs, nb = q, c
        if 'nb' in dir() and nb != best: best = nb; continue
        step /= 2
    for it in range(40):      # доводка покоординатно
        moved = False
        for ds, dx, dy in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)):
            c = (best[0] + dx * step * S, best[1] + dy * step * S, best[2] * (1 + ds * step)); q = score(c)
            if q > bs: bs, best, moved = q, c, True
        if not moved:
            step /= 2
            if step < 0.002: break
    print('  совмещение IoU', round(bs, 4), flush=True); return best
def ref_render(d, r, cx, cy, S, R=1024):
    """Вид модели с её текущей текстурой той же ортокамерой, что у вырезки: опора для точного совмещения черт лица."""
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 1; sc.cycles.use_denoising = False
    sc.render.resolution_x = sc.render.resolution_y = R; sc.render.film_transparent = True; sc.view_settings.view_transform = 'Standard'
    if not sc.world: sc.world = bpy.data.worlds.new('w')
    em = N.new('ShaderNodeEmission'); L.new(base.outputs['Color'], em.inputs[0]); o = N.new('ShaderNodeOutputMaterial'); L.new(em.outputs[0], o.inputs[0])
    cd = bpy.data.cameras.new('rc'); cd.type = 'ORTHO'; cd.ortho_scale = S; cam = bpy.data.objects.new('rc', cd); sc.collection.objects.link(cam); sc.camera = cam
    up = Vector((0, 0, 1)); C = Vector(r) * cx + up * cy
    cam.location = C + Vector(d) * 20; cam.rotation_euler = (-Vector(d)).to_track_quat('-Z', 'Y').to_euler()
    tmp = os.path.splitext(os.path.abspath(out))[0] + '_ref.png'; sc.render.filepath = tmp; bpy.ops.render.render(write_still=True)
    N.remove(em); N.remove(o); bpy.data.objects.remove(cam)
    from PIL import Image
    return np.array(Image.open(tmp).convert('RGBA'))

def align(path, ref, tag):
    """Подтянуть вид листа к чертам на модели: общий сдвиг/масштаб (ECC), затем плавное поле смещений (оптический поток).
    Сетка генератора похожа на лист, но не до пикселя: без этого глаза и губы листа ложатся мимо своих мест на сетке."""
    import cv2
    from PIL import Image
    R = ref.shape[0]; cut = np.array(Image.open(path).convert('RGBA').resize((R, R), Image.LANCZOS))
    g = lambda im: cv2.GaussianBlur(cv2.cvtColor(im[..., :3], cv2.COLOR_RGB2GRAY), (0, 0), 2).astype(np.float32) / 255
    a, b = g(ref), g(cut); m = ((ref[..., 3] > 128) & (cut[..., 3] > 128)).astype(np.uint8) * 255
    W = np.eye(2, 3, dtype=np.float32)
    try: _, W = cv2.findTransformECC(a, b, W, cv2.MOTION_AFFINE, (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 200, 1e-6), m, 5)
    except cv2.error as e: print('  ECC не сошёлся:', str(e)[:80])
    if np.abs(W[:, 2]).max() > R * 0.07 or np.abs(W[:, :2] - np.eye(2)).max() > 0.12:      # ECC уехал (прозрачное забрало, блики) — не верим
        print('  ECC отброшен:', [round(float(v), 1) for v in W[:, 2]]); W = np.eye(2, 3, dtype=np.float32)
    cut = cv2.warpAffine(cut, W, (R, R), flags=cv2.INTER_LANCZOS4 | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    fl = cv2.calcOpticalFlowFarneback((a * 255).astype(np.uint8), (g(cut) * 255).astype(np.uint8), None, 0.5, 5, 41, 5, 7, 1.5, 0)
    fl = np.clip(cv2.GaussianBlur(fl, (0, 0), 9), -R * 0.04, R * 0.04)
    yy, xx = np.mgrid[0:R, 0:R].astype(np.float32)
    big = np.array(Image.open(path).convert('RGBA')); k = big.shape[0] / R      # поле применяем к вырезке в полном размере
    Wb = W.copy(); Wb[:, 2] *= k
    big = cv2.warpAffine(big, Wb, big.shape[1::-1], flags=cv2.INTER_LANCZOS4 | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    flb = cv2.resize(fl, big.shape[1::-1], interpolation=cv2.INTER_LINEAR) * k
    Y, X = np.mgrid[0:big.shape[0], 0:big.shape[1]].astype(np.float32)
    big = cv2.remap(big, X + flb[..., 0], Y + flb[..., 1], cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    o = os.path.splitext(os.path.abspath(out))[0] + f'_{tag}_aligned.png'; Image.fromarray(big).save(o)
    print('  черты: сдвиг', [round(float(v), 1) for v in W[:, 2]], 'поток до', round(float(np.abs(fl).max()), 1), 'px', flush=True); return o
col = base.outputs['Color']; acc_w = None; REG = {}
# Виды по приоритету: первый закрашивает всё, что видит уверенно, следующий — только оставшееся. Без смешения двух видов
# в одной точке: сетка генератора не совпадает с листом до пикселя, и смесь анфаса с профилем двоит глаза и губы.
# right=@left — правая сторона тем же профилем насквозь (зеркально), если на листе нет вида справа.
for k, path in opt.items():
    d, r = VIEW[k]; d = np.array(d, float); up = np.array((0, 0, 1.0))
    if path.startswith('@'):
        r, cx, cy, S, tex = REG[path[1:]]
    else:
        r = np.array(r, float); x, y = P @ r, P @ up
        cx, cy = (x.min() + x.max()) / 2, (y.min() + y.max()) / 2; S = FIT * max(np.ptp(x), np.ptp(y))
        cx, cy, S = register(x, y, os.path.abspath(path), cx, cy, S)
        path = align(os.path.abspath(path), ref_render(d, r, cx, cy, S), k)
        img = bpy.data.images.load(os.path.abspath(path)); tex = N.new('ShaderNodeTexImage'); tex.image = img; tex.extension = 'CLIP'; tex.interpolation = 'Cubic'
        u = math('ADD', math('DIVIDE', math('SUBTRACT', dot(geo.outputs['Position'], r), cx), S), 0.5)
        v = math('ADD', math('DIVIDE', math('SUBTRACT', dot(geo.outputs['Position'], up), cy), S), 0.5)
        uv = N.new('ShaderNodeCombineXYZ'); L_ = NT.links; L_.new(u, uv.inputs[0]); L_.new(v, uv.inputs[1]); L_.new(uv.outputs[0], tex.inputs['Vector'])
        REG[k] = (r, cx, cy, S, tex)
    lo = 0.12 if k == 'front' else 0.05
    facing = math('DIVIDE', math('SUBTRACT', dot(geo.outputs['True Normal'], d), lo), 0.3, clamp=True)   # 0 на скользящих углах, 1 при взгляде в лоб
    w = math('MULTIPLY', facing, tex.outputs['Alpha'])
    if acc_w is None: proj, acc_w = tex.outputs['Color'], w
    else:
        w = math('MULTIPLY', w, math('SUBTRACT', 1.0, acc_w, clamp=True))            # только то, что ещё не закрыто
        tot = math('ADD', acc_w, w, clamp=True)
        proj = mixc(math('DIVIDE', w, math('MAXIMUM', tot, 1e-5), clamp=True), proj, tex.outputs['Color']); acc_w = tot
    print(k, 'рамка', round(S, 3), 'центр', round(cx, 3), round(cy, 3), flush=True)
cover = acc_w
final = mixc(cover, col, proj)
em = N.new('ShaderNodeEmission'); L.new(final, em.inputs[0]); o = N.new('ShaderNodeOutputMaterial'); L.new(em.outputs[0], o.inputs[0])
bake = bpy.data.images.new('baked', SIZE, SIZE); bt = N.new('ShaderNodeTexImage'); bt.image = bake; N.active = bt
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 4; sc.cycles.use_denoising = False; sc.render.bake.margin = 16
sc.view_settings.view_transform = 'Standard'
bpy.ops.object.bake(type='EMIT')
png = os.path.splitext(os.path.abspath(out))[0] + '_albedo.png'; bake.filepath_raw = png; bake.file_format = 'PNG'; bake.save()
for n in list(N):
    if n != bt: N.remove(n)
bs = N.new('ShaderNodeBsdfPrincipled'); bs.inputs['Roughness'].default_value = 0.85; bs.inputs['Specular IOR Level'].default_value = 0.25; L.new(bt.outputs['Color'], bs.inputs['Base Color'])
o = N.new('ShaderNodeOutputMaterial'); L.new(bs.outputs[0], o.inputs[0])
bpy.ops.export_scene.gltf(filepath=os.path.abspath(out), export_format='GLB')
print('готово', out)
