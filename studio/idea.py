# Идея → сценарий → фильм. Свободный текст («надиктуй, о чём фильм») превращается в сценарий движка
# (films/<имя>/script.txt) и сразу запускается: раскадровка локально и/или финальный рендер на ферме.
#
#   python3 studio/idea.py "Путник входит в пустой храм, останавливается, смотрит на свет и в решимости бежит к нему"
#   python3 studio/idea.py --name hram2 --farm "..."         # сразу на GPU-ферму (Kaggle) через GitHub Actions
#   python3 studio/idea.py --board "..."                     # раскадровка: кадр из середины каждого плана (минуты)
#
# Разбор правилами (без внешних сервисов): глаголы → действия, слова чувств → эмоции, жанровые слова → режиссёр.
# Это нижний уровень: Claude в чате пишет идею развёрнуто и подаёт сюда уже ясные фразы — по одной на бит.
import sys, os, re, json, argparse, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import styles

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# глагол → (действие сценария, длительность по умолчанию, с)
VERBS = [
    (r'бе[жг]|мчится|несётся|несется|срывается|рвётся|рвется|убегает', ('бежит', 4.0)),
    (r'иде|идё|входит|шагает|бред[её]т|проходит|движется|ступает|приближается', ('идёт', 6.0)),
    (r'останавлива|замира|застыва|стоит|ждёт|ждет', ('стоит', 3.0)),
    (r'(поднимает|запрокидывает) (голову|взгляд|глаза)|смотрит (вверх|наверх|в небо|на свод|на свет)', ('смотрит вверх', 4.5)),
    (r'опускает (голову|взгляд|глаза)|смотрит (вниз|под ноги|в пол)', ('смотрит вниз', 3.5)),
    (r'оборачивается|оглядывается|поворачивается', ('оборачивается', 2.5)),
    (r'смотрит|видит|замечает|вглядывается', ('смотрит', 3.0)),
]
EMOTIONS = {
    'благоговение': r'благогове|священн|величи|свет\w*.*свод|чуд',
    'решимость': r'реш(ает|имост|ительн)|срывается|вперёд|вперед|к свету',
    'сомнение': r'сомнева|сомнен|колеблется|один\b|одинок',
    'страх': r'страх|боится|ужас|испуг',
    'тревога': r'тревог|насторож|беспоко|угроз',
    'надежда': r'надежд|надеется',
    'триумф': r'триумф|побед',
    'восторг': r'восторг|радост|ликует',
}
# жанр/интонация → режиссёр (профили studio/crew): кто лучше всего снимет такую идею
DIRECTOR_HINTS = [
    ('bay', r'погон|гонк|взрыв|робот|машин|мотоцикл|бой\b|битв|экшн|трансформ'),
    ('deltoro', r'гигант|монстр|кайдзю|чудовищ|дожд|неон|океан|шторм|сказк'),
    ('thriller', r'страх|ужас|преслед|тревог|темнот|убий'),
    ('kubrick', r'коридор|симметр|холодн|машинн|безумн'),
    ('miyazaki', r'ветер|трав|облак|полёт|полет|лес|природ'),
    ('spielberg', r'чуд|открыт|ребён|ребен|семь'),
    ('villeneuve', r'храм|тишин|одиноч|пустын|свод|масштаб|притч'),
]
HEROES = [('pilgrim', r'путник|паломник|странник|монах|старик|мужчин|\bон\b')]
# какие актёры уже «сыграны» (есть тело и костюм): остальные — в кастинге, временно подменяем ближайшим
READY = {'pilgrim'}
TIME_OF_DAY = [  # слово → (небо, сила неба, солнце: высота, азимут, сила, туман)
    (r'закат|вечер', ('venice_sunset_1k', 0.9, (52, 90, 10), 0.006)),
    (r'рассвет|утр', ('spruit_sunrise_1k', 0.8, (14, 75, 8), 0.01)),
    (r'ноч|луна|темнот', ('moonless_golf_1k', 0.35, (8, 200, 1.2), 0.012)),
    (r'полдень|день|солнц', ('royal_esplanade_1k', 0.9, (65, 150, 9), 0.004)),
]
WORLDS = {'sponza': dict(x0=-10.3, x1=9.3, y=0.25, words=r'храм|зал|собор|галере|колонн|двор')}

def _has_verb(s): return any(re.search(pat, s.lower()) for pat, _ in VERBS)

def sentences(text):
    parts = re.split(r'(?<=[.!?…;])\s+|,\s*(?:а |и |но |потом |затем |после чего )|\s+(?:а потом|и потом|затем|после чего)\s+', text.strip())
    out = []
    for p in (p.strip(' ,.;') for p in parts if p and p.strip(' ,.;')):
        # «мчится, оборачивается в тревоге и бежит дальше» — три бита: режем по запятой/«и», если в обеих частях есть глагол
        chunks = [p]
        for sep in (r',\s+', r'\s+и\s+'):
            nxt = []
            for c in chunks:
                bits = re.split(sep, c)
                if len(bits) > 1 and all(_has_verb(b) for b in bits): nxt += bits
                else: nxt.append(c)
            chunks = nxt
        out += [c.strip(' ,.;') for c in chunks if c.strip(' ,.;')]
    return out

def classify(s):
    low = s.lower()
    act, dur = next((v for pat, v in VERBS if re.search(pat, low)), ('стоит', 3.0))
    emo = next((e for e, pat in EMOTIONS.items() if re.search(pat, low)), '')
    if 'медленно' in low: dur *= 1.3
    if 'долго' in low: dur *= 1.6
    if 'быстро' in low or 'резко' in low: dur *= 0.75
    return act, round(dur, 1), emo

def build(text, name=None, director=None, hero=None, style=None):
    low = text.lower()
    world = next((w for w, d in WORLDS.items() if re.search(d['words'], low)), 'sponza'); W = WORLDS[world]
    sky, skyk, sun, fog = next((v for pat, v in TIME_OF_DAY if re.search(pat, low)), TIME_OF_DAY[0][1])
    director = director or next((d for d, pat in DIRECTOR_HINTS if re.search(pat, low)), 'villeneuve')
    hero = hero or next((h for h, pat in HEROES if re.search(pat, low)), 'pilgrim')
    note = ''
    # стиль: явно (--style restyle/neon) или по ключевым словам из style.json стилевых репозиториев; 'none' — без стиля
    if style is None:
        sn, sl = styles.pick(text); style = f'{sn}/{sl}' if sn else ''
    if style == 'none': style = ''
    if hero not in READY: note = f'# актёр {hero} ещё в кастинге — сыграет pilgrim'; hero = 'pilgrim'
    beats = [classify(s) + (s,) for s in sentences(text)]
    # «срывается и бежит» — одно действие: соседние биты с одним глаголом движения сливаются
    merged = []
    for b in beats:
        if merged and b[0] == merged[-1][0] and b[0] in ('идёт', 'бежит'):
            p_ = merged[-1]; merged[-1] = (p_[0], p_[1] + b[1] * 0.5, p_[2] or b[2], p_[3] + ' и ' + b[3][0].lower() + b[3][1:])
        else: merged.append(b)
    beats = merged
    # маршрут героя по локации: путь делится между битами движения пропорционально «естественной» дистанции
    # (шаг ≈1.25 м/с, бег ≈4.5 м/с); если зал короче — все отрезки сжимаются, ни один не схлопывается в ноль
    want = [(1.25 if b[0] == 'идёт' else 4.5) * b[1] if b[0] in ('идёт', 'бежит') else 0.0 for b in beats]
    k = min(1.0, (W['x1'] - W['x0']) / (sum(want) or 1)); x = W['x0']; lines = []
    for (act, dur, emo, s), dw in zip(beats, want):
        if act in ('идёт', 'бежит'):
            x2 = min(W['x1'], x + max(1.5, dw * k))
            tag = f'{act} {x:.1f},{W["y"]} -> {x2:.1f},{W["y"]}'; x = x2
        else:
            tag = f'{act} {dur}'
        lines.append(f'[{tag}{" | " + emo if emo else ""}] {s[0].upper() + s[1:]}.')
    title = name or re.sub(r'[^a-zа-яё0-9]+', '_', ' '.join(low.split()[:3]))[:24].strip('_')
    head = [f'СЦЕНА: {text.strip().split(".")[0][:60]}', f'МИР: {world}', f'НЕБО: {sky} {skyk}', 'СОЛНЦЕ: ' + ' '.join(str(v) for v in sun),
            f'ТУМАН: {fog}', 'ГЕРОЙ: Он', f'РЕЖИССЁР: {director}'] + ([f'СТИЛЬ: {style}'] if style else []) + ([note] if note else [])
    return title, hero, style, '\n'.join(head + ['---'] + lines) + '\n'

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('idea', nargs='+'); ap.add_argument('--name'); ap.add_argument('--director'); ap.add_argument('--hero'); ap.add_argument('--style', help='restyle/neon, toon/cel …; none — без стиля; пусто — по словам идеи')
    ap.add_argument('--board', action='store_true'); ap.add_argument('--farm', action='store_true'); ap.add_argument('--width', type=int, default=1920); ap.add_argument('--samples', type=int, default=64)
    a = ap.parse_args()
    title, hero, style, txt = build(' '.join(a.idea), a.name, a.director, a.hero, a.style)
    st = styles.find(); sname = style.partition('/')[0]
    if style and not styles.look_file(style, st):
        s_ = st.get(sname, {})
        print(f'стиль {style} ({s_.get("stage", "?")}): рисует в своём движке — ядро отдаёт сценарий и раскадровку;',
              f'рендер: cd {s_.get("_dir", "kodfilm-" + sname)} && {s_.get("render", "node core/render.mjs --film <film>")}')
    d = os.path.join(ROOT, 'films', title); os.makedirs(d, exist_ok=True); p = os.path.join(d, 'script.txt')
    open(p, 'w').write(txt); print(txt); print('→', os.path.relpath(p, ROOT))
    if a.board:   # раскадровка быстрым движком: кадр на план — постановка видна за минуты
        py = os.environ.get('BLENDER_PY', '/home/claude/bvenv/bin/python')
        subprocess.run([py, os.path.join(ROOT, 'studio/film.py'), '--script', p, '--hero', hero, '--board', '--w', '960', '--out', os.path.join(ROOT, 'out', title + '_board')], check=True)
    if a.farm:    # финал: трассировка путей на ферме (сценарий должен быть в репозитории — коммит и пуш)
        rel = os.path.relpath(p, ROOT)
        subprocess.run(['git', '-C', ROOT, 'add', rel], check=True)
        subprocess.run(['git', '-C', ROOT, 'commit', '-qm', f'Сценарий из идеи: {title}'], check=False)
        subprocess.run(['git', '-C', ROOT, 'push', '-q', 'origin', 'HEAD:main'], check=True)
        subprocess.run(['gh', 'api', '-X', 'POST', 'repos/IlyaMargolin/kodfilm/actions/workflows/farm.yml/dispatches', '-f', 'ref=main',
                        '-f', f'inputs[script]={rel}', '-f', f'inputs[width]={a.width}', '-f', f'inputs[samples]={a.samples}', '-f', 'inputs[frames]=', '-f', f'inputs[hero]={hero}'], check=True)
        print('ферма запущена:', rel)
        lf = style and styles.look_file(style, st)
        if lf and json.load(open(lf, encoding='utf-8')).get('post'):   # на ферме стилевого репозитория нет: перерисовка после скачивания кадров
            post = os.path.normpath(os.path.join(os.path.dirname(lf), json.load(open(lf, encoding='utf-8'))['post']))
            print(f'после фермы: python3 {post} <папка кадров> <папка кадров>/meta.json')
