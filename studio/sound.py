# Звукорежиссёр: собирает дорожку по метаданным съёмки (meta.json): шаги точно в кадр,
# акустика помещения, атмосфера, музыка по эмоциям битов, «перспектива» звука по крупности плана.
# python studio/sound.py out/hram/meta.json out/hram/sound.wav
import sys, json, math
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
rng = np.random.default_rng(11)

def env_exp(n, tau):
    return np.exp(-np.arange(n) / (tau * SR))

def band(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype='band', fs=SR, output='sos'); return signal.sosfilt(sos, x)
def lp(x, f, order=2):
    sos = signal.butter(order, f, btype='low', fs=SR, output='sos'); return signal.sosfilt(sos, x)
def hp(x, f, order=2):
    sos = signal.butter(order, f, btype='high', fs=SR, output='sos'); return signal.sosfilt(sos, x)

def hall_ir(rt_low=3.4, rt_mid=2.7, rt_high=1.3, length=4.5):
    """Импульсный отклик большого каменного зала: ранние отражения + диффузный хвост, высокие гаснут быстрее."""
    n = int(length * SR); ir = np.zeros((n, 2))
    for ch in range(2):
        nz = rng.standard_normal(n)
        tail = (lp(nz, 300) * env_exp(n, rt_low / 6.9) + band(nz, 300, 3000) * env_exp(n, rt_mid / 6.9) + hp(nz, 3000) * env_exp(n, rt_high / 6.9))
        pre = int(0.018 * SR); tail[:pre] = 0
        for d, g in [(0.011, 0.5), (0.023, 0.38), (0.037, 0.3), (0.052, 0.26), (0.071, 0.2)]:
            k = int((d + 0.003 * ch) * SR); tail[k] += g * (1 if rng.random() > 0.5 else -1)
        ir[:, ch] = tail
    return ir / np.abs(ir).max()

def footstep(kind, gain=1.0):
    n = int(0.35 * SR); t = np.arange(n) / SR
    click = band(rng.standard_normal(n), 1800, 7000) * env_exp(n, 0.006) * (1.4 if kind == 'run' else 1.0)
    f0 = 85 + rng.random() * 25
    thump = np.sin(2 * np.pi * f0 * t * (1 - 0.3 * t)) * env_exp(n, 0.035) * 0.9
    body = lp(rng.standard_normal(n), 700) * env_exp(n, 0.02) * 0.6
    scuff = band(rng.standard_normal(n), 900, 4000) * np.clip((t - 0.03) / 0.02, 0, 1) * env_exp(n, 0.05) * (0.25 if kind == 'walk' else 0.1)
    gear = sum(np.sin(2 * np.pi * f * t + rng.random() * 6) * env_exp(n, 0.04 + rng.random() * 0.05) for f in rng.uniform(2800, 7500, 4)) * 0.05 * (2 if kind == 'run' else 1)
    x = click + thump + body + scuff + gear
    return x * gain * (1.5 if kind == 'run' else 1.0)

def add(buf, x, t, pan=0.0, gain=1.0):
    i = int(t * SR)
    if i >= len(buf): return
    x = x[:len(buf) - i]
    l, r = math.cos((pan + 1) * math.pi / 4), math.sin((pan + 1) * math.pi / 4)
    buf[i:i + len(x), 0] += x * l * gain; buf[i:i + len(x), 1] += x * r * gain

def saw(f, t, detune=0.0):
    ph = (f * (1 + detune)) * t
    return 2 * (ph - np.floor(ph + 0.5))

def pad(freqs, dur, attack=1.5, release=2.0, bright=1200, voices=3):
    n = int(dur * SR); t = np.arange(n) / SR; x = np.zeros(n)
    for f in freqs:
        for v in range(voices):
            x += saw(f, t + rng.random(), (v - 1) * 0.004) / voices
    x = lp(x, bright, 2)
    e = np.minimum(1, t / attack) * np.minimum(1, np.maximum(0, (dur - t) / release))
    return x * e / len(freqs)

def choir(freqs, dur, attack=2.0, release=2.0):
    # «ах»: пила через форманты гласной А (≈ 800, 1150, 2900 Гц) + лёгкое вибрато
    n = int(dur * SR); t = np.arange(n) / SR; x = np.zeros(n)
    for f in freqs:
        vib = 1 + 0.004 * np.sin(2 * np.pi * (5 + rng.random()) * t)
        for v in range(4):
            ph = np.cumsum(f * vib * (1 + (v - 1.5) * 0.005)) / SR
            x += 2 * (ph - np.floor(ph + 0.5))
    y = band(x, 650, 950) * 1.0 + band(x, 1000, 1300) * 0.6 + band(x, 2600, 3200) * 0.25
    e = np.minimum(1, t / attack) ** 2 * np.minimum(1, np.maximum(0, (dur - t) / release))
    return y * e / len(freqs)

def timpani(f=62):
    n = int(1.6 * SR); t = np.arange(n) / SR
    pitch = f * (1 + 0.25 * env_exp(n, 0.05))
    ph = np.cumsum(pitch) / SR
    return (np.sin(2 * np.pi * ph) * env_exp(n, 0.5) + lp(rng.standard_normal(n), 400) * env_exp(n, 0.04) * 0.6)

def cello(f, dur):
    n = int(dur * SR); t = np.arange(n) / SR
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.2 * t) * np.minimum(1, t / 0.8)
    ph = np.cumsum(f * vib) / SR; x = 2 * (ph - np.floor(ph + 0.5))
    x = band(x, 80, 1800) + 0.3 * band(x, 200, 600)
    e = np.minimum(1, t / 0.9) * np.minimum(1, np.maximum(0, (dur - t) / 1.2))
    return x * e

NOTE = lambda n: 440 * 2 ** ((n - 69) / 12)   # MIDI -> Гц

def build(meta):
    dur = meta['duration'] + 3.0; N = int(dur * SR)
    dry = np.zeros((N, 2)); music = np.zeros((N, 2)); amb = np.zeros((N, 2))
    FRAME_H = {'EWS': 14.0, 'WS': 5.5, 'FS': 2.4, 'MS': 1.15, 'MCU': 0.7, 'CU': 0.42, 'ECU': 0.2}
    def shot_at(t):
        return next((s for s in meta['shots'] if s['start'] <= t < s['end']), meta['shots'][-1])
    # --- шаги: громкость и «сухость» зависят от того, насколько близко камера
    wet_curve = np.zeros(N)
    for st in meta['steps']:
        s = shot_at(st['t']); h = FRAME_H[s['size']]
        g = np.clip(1.3 - 0.33 * math.log2(h / 0.4), 0.25, 1.4)
        if s['size'] == 'ECU' and 'шаг' in s['note']: g *= 1.6
        add(dry, footstep(st['kind'], g), st['t'], pan=(-0.15 if st['side'] == 'fl' else 0.15))
    for s in meta['shots']:
        i0, i1 = int(s['start'] * SR), int(s['end'] * SR)
        wet_curve[i0:i1] = np.clip(0.25 + 0.18 * math.log2(FRAME_H[s['size']] / 0.4), 0.2, 1.0)
    wet_curve[int(meta['shots'][-1]['end'] * SR):] = 0.8
    wet_curve = np.convolve(wet_curve, np.ones(2400) / 2400, mode='same')
    # --- атмосфера: ветер в галереях, далёкие птицы, тон зала
    n = N; wind = lp(np.cumsum(rng.standard_normal(n)) * 0.02, 900)
    wind = hp(wind, 120); lfo = 0.6 + 0.4 * np.sin(2 * np.pi * np.arange(n) / SR / 7.3) * np.sin(2 * np.pi * np.arange(n) / SR / 2.9 + 1)
    wind = wind / np.abs(wind).max() * lfo * 0.12
    amb[:, 0] += wind; amb[:, 1] += np.roll(wind, 1800)
    for k in range(int(dur / 3.5)):
        tb = 1.5 + k * 3.5 + rng.random() * 2; m = int(0.18 * SR); tt = np.arange(m) / SR
        f = 3200 + 900 * np.sin(2 * np.pi * 14 * tt) + rng.random() * 600
        chirp = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * tt / tt[-1]) * 0.018
        add(amb, chirp, tb, pan=rng.uniform(-0.8, 0.8))
    # --- музыка: по битам и эмоциям
    D2, A2, D3, F3, A3, C4, D4, E4, F4, A4 = (NOTE(m) for m in (38, 45, 50, 53, 57, 60, 62, 64, 65, 69))
    for b in meta['beats']:
        s0, d = b['start'], b['dur']
        if b['action'] == 'walk':
            add(music, pad([D2, A2, D3], d + 3, attack=3, release=3, bright=500), s0, gain=0.55)
        elif b['action'] == 'stand':
            add(music, pad([D2, A2, F3], d + 2.5, attack=1.5, release=2.5, bright=700), s0, gain=0.5)
        elif b['action'] == 'look_up':
            add(music, choir([D3, A3, D4, NOTE(66)], d + 3, attack=2.2, release=2.5), s0, gain=0.9)   # ре мажор: свет
            add(music, pad([D2, A2], d + 3, attack=2, release=3, bright=900), s0, gain=0.45)
            sh = sum(np.sin(2 * np.pi * f * np.arange(int((d + 2) * SR)) / SR) for f in (NOTE(86), NOTE(90), NOTE(93)))
            sh *= np.minimum(1, np.arange(len(sh)) / SR / 2) * np.minimum(1, np.maximum(0, (d + 2 - np.arange(len(sh)) / SR) / 2)) * 0.012
            add(music, sh, s0)
        elif b['action'] == 'look_down':
            add(music, cello(D3, d + 1.5) * 0.25, s0 + 0.3, pan=-0.1)
            add(music, cello(F3, d * 0.6) * 0.15, s0 + d * 0.45, pan=0.1)
            add(music, pad([D2], d + 2, attack=1, release=2, bright=300), s0, gain=0.5)
        elif b['action'] == 'run':
            bpm = 112; beat = 60 / bpm; k = 0; tt = s0
            while tt < s0 + d:
                g = 0.35 + 0.65 * (tt - s0) / d
                add(music, timpani(62 if k % 4 else 52) * 0.35 * g, tt)
                tt += beat * (1 if k % 4 != 3 else 0.5); k += 1
            # остинато струнных, нарастает
            notes = [D3, F3, A3, D4, A3, F3]; step = beat / 2; tt = s0; j = 0
            while tt < s0 + d:
                g = 0.15 + 0.6 * (tt - s0) / d
                add(music, pad([notes[j % 6]], step * 1.1, attack=0.02, release=0.08, bright=2500, voices=2) * g, tt, pan=(-0.3 if j % 2 else 0.3))
                tt += step; j += 1
            add(music, choir([D3, A3, D4, F4, A4], d + 4, attack=d * 0.8, release=3.0), s0, gain=0.7)
            end = s0 + d
            add(music, timpani(46) * 0.9, end); add(music, pad([D2, A2, D3, F3, A3], 4.5, attack=0.05, release=4, bright=1600) * 0.9, end)
    # --- сведение
    ir = hall_ir()
    wet = np.stack([signal.fftconvolve(dry[:, c] + music[:, c] * 0.35 + amb[:, c] * 0.4, ir[:, c])[:N] for c in range(2)], 1)
    mix = dry * (1 - 0.6 * wet_curve[:, None]) + wet * 0.22 * (0.5 + wet_curve[:, None]) + music * 0.8 + amb * 0.6
    mix = hp(mix.T, 30).T
    mix = np.tanh(mix / (np.abs(mix).max() + 1e-9) * 1.6) * 0.89
    fade = np.minimum(1, np.arange(N) / (0.8 * SR)) * np.minimum(1, (N - np.arange(N)) / (2.5 * SR))
    return (mix * fade[:, None]).astype(np.float32)

if __name__ == '__main__':
    meta = json.load(open(sys.argv[1]))
    wavfile.write(sys.argv[2], SR, build(meta))
    print('ok', sys.argv[2])
