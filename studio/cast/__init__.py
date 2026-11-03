# Каст студии.
#   studio/cast/actors/<id>.json — постоянная труппа: один файл на актёра (внешность, характер, амплуа, модель, походка).
#   films/<фильм>/cast.json      — состав конкретного фильма: какая роль каким актёром, какой план.
# Актёра можно добавить (новый файл), убрать (удалить файл), заменить в фильме (поменять actor в cast.json).
# Статус «кастинг» — роль придумана, модель ещё не создана.
import json, os, glob
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

def actors():
    return {os.path.basename(p)[:-5]: json.load(open(p, encoding='utf-8')) for p in sorted(glob.glob(os.path.join(HERE, 'actors', '*.json')))}

def film_cast(film_dir):
    p = os.path.join(film_dir, 'cast.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None

def resolve(name, film_dir=None):
    """Имя из сценария (роль, id актёра или файл модели) -> файл модели .glb."""
    A = actors(); key = name.strip().lower()
    fc = film_cast(film_dir) if film_dir else None
    if fc:
        for r in fc['roles']:
            if r['role'].lower() == key or r['actor'] == key: key = r['actor']; break
    for k, a in A.items():
        if key in (k, a['name'].lower()) and a.get('human'): return a['human'].get('skeleton', 'Soldier.glb')
        if key in (k, a['name'].lower()) and a.get('model'): return a['model']
        if a.get('model') and key == a['model'].lower().replace('.glb', ''): return a['model']
    return name + ('' if name.endswith('.glb') else '.glb')

def spec(name, film_dir=None):
    """Полная карточка актёра по имени из сценария (или None). Для «живых» людей в карточке есть блок human:
    {"skeleton": "Soldier.glb", "gender": 1, "age": 0.5, "muscle": 0.5, "weight": 0.5, "height": 0.5, "proportions": 0.6,
     "skin": [r,g,b], "wardrobe": "robe", "cloth": [r,g,b], "hood": true}"""
    A = actors(); key = name.strip().lower()
    fc = film_cast(film_dir) if film_dir else None
    if fc:
        for r in fc['roles']:
            if r['role'].lower() == key or r['actor'] == key: key = r['actor']; break
    for k, a in A.items():
        if key in (k, a['name'].lower()): return a
    return None

def roster():
    """Сводка: кто в труппе, кто в кастинге, кто в каких фильмах."""
    A = actors(); films = {}
    for p in glob.glob(os.path.join(ROOT, 'films', '*', 'cast.json')):
        fc = json.load(open(p, encoding='utf-8'))
        for r in fc['roles']: films.setdefault(r['actor'], []).append(f"{fc['film']} — {r['role']} ({r['tier']})")
    lines = []
    for k, a in A.items():
        lines.append(f"{a['name']:22s} [{k}] {a['status']:9s} план {a['tier']:5s} | {a['character']} | амплуа: {', '.join(a['range'])}"
                     + (f" | в фильмах: {'; '.join(films[k])}" if k in films else ''))
    return '\n'.join(lines)

if __name__ == '__main__':
    print(roster())
