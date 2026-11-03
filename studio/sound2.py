# Звук v2 — как в кинопостпродакшне: стемы ФОЛИ / АТМОСФЕРА / ЭФФЕКТЫ / МУЗЫКА, акустика зала,
# звуковая перспектива по крупности плана, громкость по стандарту (−16 LUFS, пик −1 dBTP).
# python studio/sound2.py out/hram/meta.json out/hram/sound.wav
import sys, os, json, math
import numpy as np, soundfile as sf, pyloudnorm as pyln
from scipy import signal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sound as s1
from orchestra import orchestra, midi, SR
rng = np.random.default_rng(5)

def put(buf, x, t, gain=1.0, pan=0.0):
    i = int(t * SR)
    if i >= len(buf) or i < 0: return
    if x.ndim == 1:
        l, r = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4); x = np.stack([x * l, x * r], 1)
    x = x[:len(buf) - i]; buf[i:i + len(x)] += x * gain

def score(meta, N, O):
    """Партитура ре минор, по битам сцены: тема пространства → свет (ре мажор, хор) → сомнение (соло виолончели) → решимость (остинато, валторны, литавры)."""
    mus = np.zeros((N, 2), np.float32)
    beats = meta['beats']; end = meta['duration']
    for b in beats:
        t0, d = b['start'], b['dur']; A = b['action']
        if A == 'walk':
            put(mus, O['basses'].note('d2', d + 4, 0.55, attack=2.5, release=3), t0)
            put(mus, O['celli'].note('d3', d + 3, 0.35, attack=3.0, release=3), t0 + 0.8, pan=-0.2)
            put(mus, O['celli'].note('a2', d + 3, 0.3, attack=3.0, release=3), t0 + 1.2, pan=-0.3)
            put(mus, O['tamtam'].hit(2, 0.25), t0 + 0.1)
        elif A == 'stand':
            put(mus, O['violas'].note('f3', d + 3, 0.35, attack=1.5, release=2.5), t0, pan=0.2)
            put(mus, O['basses'].note('d2', d + 3, 0.45, attack=1.0, release=3), t0)
            put(mus, O['timp_roll'].hit(1, 0.35), t0 + d - 2.6)      # крещендо литавр подводит к свету
        elif A == 'look_up':
            for n, g, p in (('d4', .5, -.2), ('f#4', .45, 0), ('a4', .45, .2), ('d5', .35, .1)):
                put(mus, O['ch_f'].note(n, d + 1, g, attack=1.6, release=3), t0, pan=p)
            for n, g in (('d3', .5), ('a3', .45)):
                put(mus, O['ch_m'].note(n, d + 1, g, attack=1.8, release=3), t0, pan=-0.1)
            put(mus, O['vln_hrm'].note('a6', d, 0.25, attack=2, release=3), t0 + 0.5, pan=0.3)
            put(mus, O['basses'].note('d2', d + 1, 0.5, attack=0.5, release=3), t0)
            put(mus, O['cym'].hit(0, 0.25), t0 - 1.5)
        elif A == 'look_down':
            put(mus, O['celli'].note('f3', d * 0.5 + 0.6, 0.55, attack=0.6, release=1.2), t0 + 0.2, pan=-0.1)
            put(mus, O['celli'].note('e3', d * 0.5 + 0.6, 0.5, attack=0.4, release=1.5), t0 + 0.2 + d * 0.5, pan=-0.1)
            put(mus, O['basses'].note('d2', d + 2, 0.4, attack=0.8, release=2), t0)
        elif A == 'run':
            bpm = 126; s16 = 60 / bpm / 4; k = 0; tt = t0
            patt = ['d2', 'd2', 'd3', 'd2', 'a2', 'd2', 'f2', 'd2']
            while tt < t0 + d:
                g = 0.45 + 0.55 * (tt - t0) / d
                put(mus, O['celli_stc'].note(patt[k % 8], 0.12, 0.55 * g, attack=0.005, release=0.15), tt, pan=-0.25)
                if k % 2 == 0: put(mus, O['basses_stc'].note(patt[k % 8], 0.12, 0.5 * g, attack=0.005, release=0.15), tt, pan=0.1)
                if k % 4 == 0: put(mus, O['timp_f'].hit(k // 4, 0.55 * g, semis=-1), tt)
                tt += s16; k += 1
            put(mus, O['vln_trm'].note('d5', d, 0.4, attack=d * 0.9, release=0.3), t0, pan=0.3)
            put(mus, O['vln_trm'].note('a5', d, 0.3, attack=d * 0.9, release=0.3), t0, pan=0.35)
            put(mus, O['horns'].note('d3', d + 0.2, 0.45, attack=d * 0.6, release=0.5), t0, pan=0.1)
            put(mus, O['horns'].note('a3', d + 0.2, 0.4, attack=d * 0.6, release=0.5), t0, pan=0.15)
    # финальный аккорд ре мажор: валторны, хор, струнные, там-там + большой барабан
    tf = end
    for inst, notes, g in (('horns', ('d3', 'f#3', 'a3'), .55), ('ch_f', ('d5', 'f#5', 'a4'), .45), ('ch_m', ('d3', 'a3'), .5),
                           ('violins', ('d5', 'a5'), .35), ('celli', ('d3', 'a2'), .45), ('basses', ('d2',), .6)):
        for n in notes: put(mus, O[inst].note(n, 2.2, g, attack=0.03, release=2.5), tf, pan=rng.uniform(-.4, .4))
    put(mus, O['tamtam'].hit(0, 0.7), tf); put(mus, O['bd'].hit(0, 0.8), tf)
    return mus

def fx(meta, N):
    """Звуковой дизайн: низкий «бум» на откровении, райзер перед бегом, свист при быстром движении камеры, финальный удар."""
    out = np.zeros((N, 2), np.float32)
    def boom(dur=2.5, f0=55, f1=28):
        n = int(dur * SR); t = np.arange(n) / SR; f = f1 + (f0 - f1) * np.exp(-t / 0.4)
        return (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.9)).astype(np.float32)
    def riser(dur=1.8):
        n = int(dur * SR); t = np.arange(n) / SR; x = rng.standard_normal(n)
        y = np.zeros(n); seg = 2400
        for i in range(0, n, seg):
            fc = 300 + 5000 * (i / n) ** 2; y[i:i + seg] = s1.band(x[max(0, i - 4800):i + seg], fc * 0.7, fc * 1.4)[-len(y[i:i + seg]):]
        return (y * (t / dur) ** 2 * 0.5).astype(np.float32)
    def whoosh(dur=0.7):
        n = int(dur * SR); t = np.arange(n) / SR; x = s1.band(rng.standard_normal(n), 400, 2500)
        return (x * np.sin(np.pi * t / dur) ** 2 * 0.35).astype(np.float32)
    for b in meta['beats']:
        if b['action'] == 'look_up': put(out, boom(), b['start'] - 0.05, 0.9)
        if b['action'] == 'run': put(out, riser(), b['start'] - 1.8, 0.7); put(out, boom(1.8, 70, 35), b['start'], 0.6)
    for s in meta['shots']:
        if s['move'] in ('track', 'lead') and s['size'] in ('MS', 'CU', 'FS'): put(out, whoosh(), s['start'] - 0.15, 0.6, pan=rng.uniform(-.5, .5))
    put(out, boom(4.0, 60, 25), meta['duration'], 1.0)
    return out

def build(meta):
    dur = meta['duration'] + 4.0; N = int(dur * SR)
    O = orchestra()


    FRAME_H = {'EWS': 14.0, 'WS': 5.5, 'FS': 2.4, 'MS': 1.15, 'MCU': 0.7, 'CU': 0.42, 'ECU': 0.2, 'INS': 6.0}
    shot_at = lambda t: next((s for s in meta['shots'] if s['start'] <= t < s['end']), meta['shots'][-1])
    foley = np.zeros((N, 2), np.float32)
    for st in meta['steps']:
        s = shot_at(st['t']); h = FRAME_H[s['size']]
        g = float(np.clip(1.3 - 0.33 * math.log2(h / 0.4), 0.2, 1.4))
        put(foley, s1.footstep(st['kind'], g).astype(np.float32), st['t'], pan=(-0.12 if st['side'] == 'fl' else 0.12))
    amb = np.zeros((N, 2), np.float32)
    wind = s1.hp(s1.lp(np.cumsum(rng.standard_normal(N)) * 0.02, 900), 120); wind /= np.abs(wind).max()
    tt = np.arange(N) / SR; lfo = 0.6 + 0.4 * np.sin(2 * np.pi * tt / 7.3) * np.sin(2 * np.pi * tt / 2.9 + 1)
    amb[:, 0] = wind * lfo * 0.1; amb[:, 1] = np.roll(wind, 2400) * lfo * 0.1
    for k in range(int(dur / 3)):
        tb = 1 + k * 3 + rng.random() * 2; m = int(0.16 * SR); t2 = np.arange(m) / SR
        f = 3300 + 900 * np.sin(2 * np.pi * 15 * t2) + rng.random() * 700
        put(amb, (np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t2 / t2[-1]) * 0.015).astype(np.float32), tb, pan=rng.uniform(-.8, .8))
    mus = score(meta, N, O); efx = fx(meta, N)
    # акустика зала: общий ревёрб с посылом по стемам; «мокрее» на общих планах
    ir = s1.hall_ir()
    wet_amt = np.zeros(N, np.float32)
    for s in meta['shots']:
        wet_amt[int(s['start'] * SR):int(s['end'] * SR)] = np.clip(0.3 + 0.17 * math.log2(FRAME_H[s['size']] / 0.4), 0.25, 1.0)
    wet_amt[int(meta['shots'][-1]['end'] * SR):] = 0.9
    wet_amt = np.convolve(wet_amt, np.ones(4800) / 4800, mode='same')[:, None]
    send = foley * wet_amt + amb * 0.5 + mus * 0.28 + efx * 0.2
    rev = np.stack([signal.fftconvolve(send[:, c], ir[:, c])[:N] for c in range(2)], 1).astype(np.float32) * 0.2
    stems = dict(foley=foley * (1 - 0.5 * wet_amt), ambience=amb, fx=efx * 0.8, music=mus * 0.9, reverb=rev)
    mix = sum(stems.values())
    mix = s1.hp(mix.T, 28).T.astype(np.float32)
    # громкость: −16 LUFS (стандарт для онлайна), мягкий лимитер, пик −1 dBTP
    meter = pyln.Meter(SR); L = meter.integrated_loudness(mix)
    mix = pyln.normalize.loudness(mix, L, -16.0)
    peak = np.abs(mix).max()
    if peak > 0.89: mix = np.tanh(mix / 0.89) * 0.89
    fade = np.minimum(1, tt / 0.6) * np.minimum(1, (dur - tt) / 2.5)
    return (mix * fade[:, None]).astype(np.float32), stems

if __name__ == '__main__':
    meta = json.load(open(sys.argv[1])); out = sys.argv[2]
    mix, stems = build(meta)
    sf.write(out, mix, SR, subtype='PCM_24')
    sd = os.path.join(os.path.dirname(out), 'stems'); os.makedirs(sd, exist_ok=True)
    for k, v in stems.items(): sf.write(os.path.join(sd, k + '.wav'), v, SR, subtype='PCM_24')
    print('ok', out, 'LUFS', round(pyln.Meter(SR).integrated_loudness(mix), 1))
