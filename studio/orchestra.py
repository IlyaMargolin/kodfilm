# Оркестр из живых сэмплов (Sonatina Symphonic Orchestra, CC Sampling Plus): струнные, хор, валторны, ударные.
import os, re, glob, functools
import numpy as np, soundfile as sf
SR = 48000
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'assets', 'sso')
NOTES = {'c': 0, 'c#': 1, 'd': 2, 'd#': 3, 'e': 4, 'f': 5, 'f#': 6, 'g': 7, 'g#': 8, 'a': 9, 'a#': 10, 'b': 11}
def midi(name):  # 'd3' -> 50
    m = re.match(r'([a-g]#?)(-?\d)', name.lower()); return 12 * (int(m.group(2)) + 1) + NOTES[m.group(1)]

@functools.lru_cache(maxsize=512)
def load(path):
    x, sr = sf.read(path, dtype='float32', always_2d=True)
    if x.shape[1] == 1: x = np.repeat(x, 2, 1)
    if sr != SR:
        n = int(len(x) * SR / sr); t = np.linspace(0, len(x) - 1, n)
        x = np.stack([np.interp(t, np.arange(len(x)), x[:, c]) for c in range(2)], 1).astype(np.float32)
    return x

class Instrument:
    def __init__(self, folder, prefix):
        files = glob.glob(os.path.join(ROOT, folder, prefix + '*'))
        self.map = {}
        for f in files:
            m = re.search(r'-([a-g]#?)(\d)(?:[-.])', os.path.basename(f).lower())
            if m: self.map.setdefault(midi(m.group(1) + m.group(2)), f)
        assert self.map, (folder, prefix)
    def note(self, n, dur, vel=1.0, attack=0.05, release=0.6):
        if isinstance(n, str): n = midi(n)
        k = min(self.map, key=lambda m: abs(m - n)); x = load(self.map[k])
        ratio = 2 ** ((n - k) / 12)
        need = int((dur + release) * SR)
        src_len = int(need * ratio) + 2
        if len(x) < src_len:   # растянуть сустейн: зацикливаем середину с кроссфейдом
            a, b = int(len(x) * 0.35), int(len(x) * 0.85); loop = x[a:b]
            fade = min(4800, len(loop) // 4); w = np.linspace(0, 1, fade)[:, None]
            out = x[:b].copy()
            while len(out) < src_len:
                out[-fade:] = out[-fade:] * (1 - w) + loop[:fade] * w
                out = np.concatenate([out, loop[fade:]])
            x = out
        t = np.arange(need) * ratio
        y = np.stack([np.interp(t, np.arange(len(x)), x[:, c]) for c in range(2)], 1)
        tt = np.arange(need) / SR
        env = np.minimum(1, tt / max(attack, 1e-3)) * np.clip((dur + release - tt) / release, 0, 1)
        return (y * env[:, None] * vel).astype(np.float32)

class Perc:
    def __init__(self, name):
        self.files = sorted(glob.glob(os.path.join(ROOT, 'Percussion', name + '*')))
        assert self.files, name
    def hit(self, i=0, vel=1.0, semis=0):
        x = load(self.files[i % len(self.files)])
        if semis:
            r = 2 ** (semis / 12); t = np.arange(int(len(x) / r)) * r
            x = np.stack([np.interp(t, np.arange(len(x)), x[:, c]) for c in range(2)], 1)
        return (x * vel).astype(np.float32)

def orchestra():
    return dict(
        basses=Instrument('Basses', 'basses-sus'), celli=Instrument('Celli', 'celli-sus'), violas=Instrument('Violas', 'violas-sus'),
        violins=Instrument('1st Violins', '1st-violins-sus'), vln_trm=Instrument('1st Violins', '1st-violins-trm'),
        vln_hrm=Instrument('1st Violins', '1st-violins-hrm'), celli_stc=Instrument('Celli', 'celli-stc-rr1'),
        basses_stc=Instrument('Basses', 'basses-stc-rr1'), horns=Instrument('Horns', 'horns-sus-ff'), horns_mp=Instrument('Horns', 'horns-sus-mp'),
        ch_f=Instrument('Chorus', 'chorus-female'), ch_m=Instrument('Chorus', 'chorus-male'),
        timp_f=Perc('timpani-f-rh'), timp_roll=Perc('timpani-roll-crsc'), tamtam=Perc('tamtam'), bd=Perc('bass_drum'), cym=Perc('cymbal_roll-a'))
