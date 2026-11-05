# Гаффер: свет плана по профилю оператора (crew/cinematographers.py → light).
# Правила сняты с кадров-образцов студийного кино (тёмные интерьеры с окном, тёплые интерьеры с практиками):
#   1. Ключ с ДАЛЬНЕЙ стороны лица (short lighting): освещена щека, повёрнутая от камеры, ближняя — в тени.
#      side — угол ключа от оси камеры: 60–80° — классический портрет, 110–150° — ключ «из-за плеча», лицо в полутени.
#   2. Контраст ключ:заливка задаёт fill (0.1 ≈ 1:10 — низкий ключ, 0.4 — мягкий дневной).
#   3. Контровой (rim) сзади-сверху, сильнее ключа; цвет противоположный ключу: тёплый ключ — холодный контур и наоборот.
#   4. Дымка (haze) — множитель плотности тумана: контровой свет и окна становятся видимыми лучами и ореолом.
#   5. Свет только на актёра (light linking): ключ и заливка не рисуют пятен на колоннах — как флаги и сетки на площадке.
#   6. motivated: ключ приходит со стороны реального источника (солнце/окно), если тот рядом с короткой стороной.
#   7. капюшон/шляпа: ключ ниже, заливка сильнее (см. place).
import math
import bpy
from mathutils import Vector

def kelvin(t):
    """Цветовая температура → RGB (приближение Таннера Хелланда), нормировано по максимуму."""
    t = max(1000.0, min(40000.0, t)) / 100.0
    r = 255.0 if t <= 66 else 329.698727446 * (t - 60) ** -0.1332047592
    g = 99.4708025861 * math.log(t) - 161.1195681661 if t <= 66 else 288.1221695283 * (t - 60) ** -0.0755148492
    b = 255.0 if t >= 66 else (0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307)
    c = [max(0.0, min(255.0, x)) / 255.0 for x in (r, g, b)]
    m = max(c); return tuple(x / m for x in c)

# энергия ключа (Вт, area 1.4 м на 2.4 м от лица) по крупности: на общих ключ не нужен — свет даёт мир
KEY_W = {'ECU': 70.0, 'CU': 90.0, 'MCU': 110.0, 'MS': 150.0}
RIM_W = {'ECU': 120.0, 'CU': 160.0, 'MCU': 190.0, 'MS': 240.0}

class ShotLights:
    """Ключ, заливка и контровой одного плана. Энергии ключуются по кадрам: вне плана свет выключен."""
    def __init__(self, sc, name, light, receivers, pal=None, hooded=False):
        self.L = light; self.on = {}; self.hooded = hooded
        col = bpy.data.collections.get('actor_lit')
        if col is None:
            col = bpy.data.collections.new('actor_lit')
            for o in receivers:
                if o and o.name not in col.objects: col.objects.link(o)
        self.objs = {}
        warm = light['temp'] < 4600
        spec = dict(key=('AREA', kelvin(light['temp']), 1.4), fill=('AREA', kelvin(light['temp'] + 1800), 2.2),
                    rim=('SPOT', kelvin(6800 if warm else 3300), 0.35))
        if pal:   # палитра кадра: тёплый/холодный ключ из её цвета света, заливка — цветом теней, контур — против ключа
            import palette as _pl
            spec['key'] = ('AREA', _pl.light_color(pal['key'], 0.7), 1.4)
            spec['fill'] = ('AREA', _pl.light_color(pal['shadow'], 0.5), 2.2)
            spec['rim'] = ('SPOT', _pl.light_color(pal['shadow'] if sum(pal['key'][:1]) > pal['key'][2] else pal['key'], 0.8), 0.35)
        for k, (tp, colr, size) in spec.items():
            d = bpy.data.lights.new(f'{k}_{name}', tp); d.color = colr; d.energy = 0.0
            if tp == 'AREA': d.shape = 'DISK'; d.size = size
            else: d.spot_size = math.radians(30); d.spot_blend = 0.7; d.shadow_soft_size = size
            o = bpy.data.objects.new(f'{k}_{name}', d); sc.collection.objects.link(o)
            ll = getattr(o, 'light_linking', None)
            if ll is not None: ll.receiver_collection = col      # свет только на актёра
            self.objs[k] = o

    def energies(self, size):
        L = self.L; k = KEY_W.get(size, 0.0) * L['key']
        hf = 1.6 if self.hooded else 1.0     # под капюшоном заливка работает за ключ: поля капюшона режут верхний свет
        return dict(key=k, fill=k * L['fill'] * 1.6 * hf, rim=RIM_W.get(size, 0.0) * L['rim'] * 0.6)

    def window(self, size, f0, f1):
        e = self.energies(size)
        for k, o in self.objs.items():
            for ff, on in ((f0 - 1, 0), (f0, 1), (f1, 1), (f1 + 1, 0)):
                o.data.energy = e[k] * on; o.data.keyframe_insert('energy', frame=max(1, ff))

    def place(self, f, head, cam_pos, fwd, sun_dir, key=True):
        """head — голова героя, fwd — куда он смотрит (гориз.), sun_dir — направление НА солнце."""
        L = self.L
        to_cam = cam_pos - head; to_cam.z = 0
        to_cam = to_cam.normalized() if to_cam.length > 1e-3 else Vector((0, -1, 0))
        up = Vector((0, 0, 1)); right = to_cam.cross(up)          # «право» с точки зрения героя, глядящего в камеру
        short = 1.0 if fwd.dot(right) >= 0 else -1.0              # сторона, куда он повернул лицо: дальняя от камеры щека
        if L.get('motivated') and sun_dir is not None:
            s2 = Vector((sun_dir.x, sun_dir.y, 0))
            if s2.length > 1e-3 and s2.normalized().dot(right * -short) > 0.5: short = -short   # солнце явно с другой стороны
        # под капюшоном свет входит только через открытый проём: ключ «из-за плеча» (110–150°) упирается в боковину
        a = math.radians(min(L['side'], 50) if self.hooded else L['side']) * short
        kd = (to_cam * math.cos(a) + right * math.sin(a)).normalized()
        o = self.objs
        # 7. капюшон: ключ опускается почти до уровня глаз (+0.25 м), иначе поля капюшона кладут на лицо чёрную тень —
        #    так на площадке светят монахов и персонажей в капюшонах: низкий мягкий ключ под поля
        o['key'].location = head + kd * 2.4 + Vector((0, 0, 0.25 if self.hooded else 0.9))
        # заливка: с камеры, низко и широко — поднимает тени, не создаёт второй тени
        o['fill'].location = head + (to_cam - right * short * 0.35).normalized() * 3.0 + Vector((0, 0, 0.1))
        # контровой: сзади, со стороны, противоположной ключу (перекрёстный), выше головы
        o['rim'].location = head - to_cam * 2.2 - right * short * 0.9 + Vector((0, 0, 1.1))
        for k, ob in o.items():
            d = head - ob.location; ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
            ob.keyframe_insert('location', frame=f); ob.keyframe_insert('rotation_euler', frame=f)

# ---------- объектив: глубина резкости как у оператора ----------
# Цель — размытие фона (диаметр кружка нерезкости в долях ширины кадра) и минимальная глубина резкости на лице.
BOKEH = {'ECU': 0.03, 'CU': 0.025, 'MCU': 0.018, 'MS': 0.011, 'FS': 0.006}   # по кадрам-образцам: фон за лицом — пятна
DOF_MIN = {'ECU': 0.03, 'CU': 0.06, 'MCU': 0.10, 'MS': 0.25, 'FS': 0.6}   # м: оба глаза и нос в зоне резкости

def fstop_for(size, lens_mm, sensor_w_mm, focus_m, bg_m, cur, coc_frac=1 / 1500, blur=1.0):
    """Самая закрытая диафрагма, при которой фон ещё размыт на BOKEH[size] кадра, но не меньше нужной глубины на лице.
    blur — множитель стиля (look.optics.dof): 1.2 = фон размыт на 20% сильнее; глубина на лице всё равно гарантирована."""
    cur = cur / blur
    if size not in BOKEH: return round(max(1.4, cur), 1)
    f = lens_mm; s = max(focus_m * 1000, f * 1.5); d = max(bg_m * 1000, s + 1)
    n_b = f * f * (d - s) / (d * (s - f) * BOKEH[size] * blur * sensor_w_mm)       # размытие фона ∝ 1/N
    c = sensor_w_mm * coc_frac
    n_dof = DOF_MIN[size] * 1000 * f * f / (2 * c * s * s)                   # глубина ≈ 2·N·c·s²/f²
    return round(max(1.4, n_dof, min(n_b, cur)), 1)
