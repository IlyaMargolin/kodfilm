"""HQ-ассеты для фермы (где есть интернет, например Kaggle): Poly Haven, лицензия CC0 — можно всё, включая коммерческое кино.
HDRI в 4k вместо 1k (чёткие отражения и точный свет неба). Запуск: python assets/fetch_hq.py [4k]"""
import os, sys, json, glob, urllib.request
R = sys.argv[1] if len(sys.argv) > 1 else '4k'
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'hdri')
def get(u): return urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'kodfilm-studio'}), timeout=60).read()
for p in glob.glob(os.path.join(D, '*_1k.hdr')) + glob.glob(os.path.join(D, '*_2k.hdr')):
    aid = os.path.basename(p).rsplit('_', 1)[0]; out = os.path.join(D, f'{aid}_{R}.hdr')
    if os.path.exists(out): continue
    try:
        url = json.loads(get(f'https://api.polyhaven.com/files/{aid}'))['hdri'][R]['hdr']['url']
        open(out, 'wb').write(get(url)); print('HDRI', R, aid, flush=True)
    except Exception as e: print('пропуск', aid, e, flush=True)
