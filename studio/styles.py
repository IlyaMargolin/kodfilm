# Стили поверх ядра. Каждый стилевой репозиторий (kodfilm-restyle, -toon, -2d, -miniature …) кладёт в корень
# style.json (style_api: 1): name, stage, needs, looks, keywords, render. Ядро ищет их рядом с собой:
#   ../kodfilm-*/style.json   и в папках из KODFILM_STYLES (через «:»).
# stage:
#   post     — перерисовка готовых кадров ядра: look-файл looks/<look>.json ({"lens","passes","post"}) идёт в film.py --lens
#   shading  — свой рендер сцены (cel, миниатюра): ядро отдаёт сценарий и раскадровку, рендер в движке стиля
#   render   — полностью свой движок (2D): ядро отдаёт сценарий и раскадровку
import os, re, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def find():
    dirs = glob.glob(os.path.join(os.path.dirname(ROOT), 'kodfilm-*'))
    dirs += [d for d in os.environ.get('KODFILM_STYLES', '').split(':') if d]
    out = {}
    for d in dirs:
        p = os.path.join(d, 'style.json')
        if not os.path.isfile(p): continue
        try: s = json.load(open(p, encoding='utf-8'))
        except (OSError, ValueError): continue
        if s.get('style_api') != 1 or not s.get('name'): continue
        s['_dir'] = os.path.abspath(d); out[s['name']] = s
    return out

def pick(text, styles=None):
    """Стиль по ключевым словам идеи: (стиль, look) или (None, None). Слово стиля ищется как начало слова в тексте
    («неон» ловит «неоновый», «мульт» — «мультфильм»); побеждает стиль с наибольшим числом совпадений."""
    styles = find() if styles is None else styles
    low = text.lower(); best = (0, None, None)
    for name, s in styles.items():
        hits = [k for k in s.get('keywords', []) if re.search(r'(?<!\w)' + re.escape(k.lower()), low)]
        looks = list(s.get('looks', {}))
        look = next((l for l in looks if re.search(r'(?<!\w)' + re.escape(l.lower()), low)), None)
        if look: hits.append(look)
        if len(hits) > best[0]:
            # look: названный в тексте, иначе первый, у которого есть look-файл для ядра, иначе первый по списку
            look = look or next((l for l in looks if os.path.isfile(os.path.join(s['_dir'], 'looks', l + '.json'))), looks[0] if looks else None)
            best = (len(hits), name, look)
    return best[1], best[2]

def look_file(spec, styles=None):
    """«restyle/neon» → путь к look.json для film.py --lens, если стиль стадии post и файл на месте; иначе None."""
    name, _, look = spec.partition('/')
    s = (find() if styles is None else styles).get(name)
    if not s or s.get('stage') != 'post': return None
    look = look or next(iter(s.get('looks', {})), '')
    p = os.path.join(s['_dir'], 'looks', look + '.json')
    return p if os.path.isfile(p) else None

if __name__ == '__main__':
    import sys
    st = find()
    for n, s in st.items(): print(f'{n:10} {s.get("stage"):8} {", ".join(s.get("looks", {}))}   ← {", ".join(s.get("keywords", []))}')
    if len(sys.argv) > 1:
        n, l = pick(' '.join(sys.argv[1:]), st); print('выбор:', n and f'{n}/{l}', '→', n and look_file(f'{n}/{l}', st))
