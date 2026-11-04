"""Анатомия: из чего складывается «мужское», «женское», «привлекательное», «измождённое» тело и лицо.
Каждое правило — это таргеты MakeHuman (CC0) с весами. Человек собирается как у скульпторов-анатомов:
макро-пропорции (пол, возраст, мышцы, вес, рост, раса) → черты лица по половому диморфизму → тело по
соотношениям, которые глаз считывает за доли секунды → лёгкая асимметрия (идеально симметричное лицо — «кукла»).

Опорные данные (антропометрия и рисунок фигуры, см. docs: Proko «feminine vs masculine heads», Loomis, исследования
полового диморфизма лица):
  МУЖСКОЕ ЛИЦО: выраженное надбровье и низко посаженные прямые брови; лоб покатый; челюсть шире и угловатее,
    подбородок крупный и выступающий; скулы рельефные, щёки плоские; нос крупнее, спинка с горбинкой;
    губы тоньше, рот шире; шея толще (≈ ширине челюсти); глаза относительно меньше и глубже.
  ЖЕНСКОЕ ЛИЦО: гладкий лоб без надбровья, брови выше и с изломом; челюсть уже, подбородок мягкий и узкий;
    щёки полнее, скулы высокие; нос меньше и короче, кончик чуть вверх; губы полнее (верхняя с «луком Купидона»);
    глаза крупнее; шея тоньше и длиннее.
  МУЖСКОЕ ТЕЛО (привлекательное): V-силуэт, плечи/талия ≈ 1.6 (золотое «Адонисово» отношение), развитые
    дельты и широчайшие, узкий таз, длинные ноги (пропорции 8 голов — «героические»).
  ЖЕНСКОЕ ТЕЛО (привлекательное): талия/бёдра ≈ 0.7, грудь/талия/бёдра в «песочных часах», узкая талия,
    плечи уже бёдер, длинная шея, ноги ≈ половина роста и длиннее.
  ВОЗРАСТ: после 45 — опускаются щёки и уголки рта, глубже носогубные складки, мешки под глазами,
    у мужчин залысины на висках; волосы седеют от висков и бороды.
Значение веса: 0..1 (1 — полная сила таргета). Правила складываются."""
import os

MASCULINE_FACE = {
    'eyebrows/eyebrows-trans-forward': 0.55, 'eyebrows/eyebrows-trans-down': 0.3, 'eyebrows/eyebrows-angle-down': 0.25,
    'forehead/forehead-trans-backward': 0.25, 'forehead/forehead-nubian-incr': 0.2,
    'chin/chin-width-incr': 0.55, 'chin/chin-prominent-incr': 0.45, 'chin/chin-bones-incr': 0.5, 'chin/chin-height-incr': 0.25,
    'head/head-square': 0.4, 'head/head-oval': 0.0,
    'l-cheek-bones-incr': 0.3, 'r-cheek-bones-incr': 0.3, 'l-cheek-volume-decr': 0.25, 'r-cheek-volume-decr': 0.25,
    'nose/nose-scale-vert-incr': 0.25, 'nose/nose-scale-horiz-incr': 0.15, 'nose/nose-hump-incr': 0.35,
    'nose/nose-point-width-incr': 0.15, 'nose/nose-volume-incr': 0.2,
    'mouth/mouth-upperlip-volume-decr': 0.35, 'mouth/mouth-lowerlip-volume-decr': 0.2, 'mouth/mouth-scale-horiz-incr': 0.15,
    'mouth/mouth-cupidsbow-decr': 0.3,
    'l-eye-scale-decr': 0.15, 'r-eye-scale-decr': 0.15, 'l-eye-push1-in': 0.2, 'r-eye-push1-in': 0.2,
    'neck/measure-neck-circ-incr': 0.45,
}
FEMININE_FACE = {
    'eyebrows/eyebrows-trans-up': 0.3, 'eyebrows/eyebrows-angle-up': 0.25, 'eyebrows/eyebrows-trans-backward': 0.3,
    'forehead/forehead-trans-forward': 0.15,
    'chin/chin-width-decr': 0.45, 'chin/chin-prominent-decr': 0.25, 'chin/chin-bones-decr': 0.4, 'chin/chin-height-decr': 0.15,
    'head/head-oval': 0.4,
    'l-cheek-volume-incr': 0.25, 'r-cheek-volume-incr': 0.25, 'l-cheek-trans-up': 0.25, 'r-cheek-trans-up': 0.25,
    'nose/nose-scale-vert-decr': 0.25, 'nose/nose-scale-horiz-decr': 0.2, 'nose/nose-point-up': 0.25, 'nose/nose-volume-decr': 0.25,
    'mouth/mouth-upperlip-volume-incr': 0.4, 'mouth/mouth-lowerlip-volume-incr': 0.45, 'mouth/mouth-cupidsbow-incr': 0.4,
    'l-eye-scale-incr': 0.2, 'r-eye-scale-incr': 0.2,
    'neck/measure-neck-circ-decr': 0.4, 'neck/neck-scale-vert-incr': 0.2,
}
HEROIC_MALE_BODY = {   # V-силуэт: плечи/талия ~1.6
    'torso/torso-vshape-incr': 0.6, 'torso/measure-shoulder-dist-incr': 0.35, 'torso/measure-waist-circ-decr': 0.3,
    'torso/torso-muscle-dorsi-incr': 0.4, 'torso/torso-muscle-pectoral-incr': 0.25, 'hip/hip-scale-horiz-decr': 0.2,
}
HOURGLASS_FEMALE_BODY = {   # талия/бёдра ~0.7
    'torso/measure-waist-circ-decr': 0.55, 'torso/measure-hips-circ-incr': 0.35, 'torso/measure-bust-circ-incr': 0.3,
    'torso/measure-shoulder-dist-decr': 0.2, 'hip/hip-scale-horiz-incr': 0.25, 'neck/neck-scale-vert-incr': 0.15,
}
GAUNT = {   # измождённый путник: впалые щёки, рельефные скулы, сухая шея
    'l-cheek-volume-decr': 0.45, 'r-cheek-volume-decr': 0.45, 'l-cheek-bones-incr': 0.25, 'r-cheek-bones-incr': 0.25,
    'head/head-fat-decr': 0.4, 'mouth/mouth-laugh-lines-in': 0.3, 'neck/neck-double-decr': 0.5,
}
AGED = {   # 45+: обвисание, складки, мешки
    'mouth/mouth-angles-down': 0.25, 'mouth/mouth-laugh-lines-in': 0.35, 'l-eye-bag-incr': 0.35, 'r-eye-bag-incr': 0.35,
    'head/head-age-incr': 0.35,
}
# живое лицо асимметрично на 2–4%: разные глаза, скулы, нос чуть в сторону
ASYM = {'asym/asym-eye-2-l': 0.25, 'asym/asym-cheek-1-r': 0.2, 'asym/asym-nose-2-l': 0.25, 'asym/asym-mouth-1-r': 0.2,
        'asym/asym-brown-1-l': 0.2, 'asym/asym-jaw-1-r': 0.15}

PRESETS = {'masculine': MASCULINE_FACE, 'feminine': FEMININE_FACE, 'heroic_male': HEROIC_MALE_BODY,
           'hourglass': HOURGLASS_FEMALE_BODY, 'gaunt': GAUNT, 'aged': AGED, 'asym': ASYM}

def _path(key):
    """короткое имя → файл таргета: 'l-cheek-bones-incr' → cheek/…, 'r-eye-bag-incr' → eyes/…"""
    if '/' in key: return key
    for pre, d in (('l-cheek', 'cheek'), ('r-cheek', 'cheek'), ('l-eye', 'eyes'), ('r-eye', 'eyes'), ('l-ear', 'ears'), ('r-ear', 'ears')):
        if key.startswith(pre): return f'{d}/{key}'
    return key

def mix(presets=(), extra=None, gender=1.0):
    """Сумма правил: presets — имена из PRESETS; extra — свои таргеты {'nose/nose-hump-incr': 0.3}.
    Без явного выбора пол сам добавляет диморфизм лица с силой |gender-0.5|·2."""
    out = {}
    names = list(presets)
    if not any(n in names for n in ('masculine', 'feminine')):
        k = abs(gender - 0.5) * 2
        for t, w in (MASCULINE_FACE if gender >= 0.5 else FEMININE_FACE).items(): out[_path(t)] = out.get(_path(t), 0) + w * k
    for n in names:
        for t, w in PRESETS[n].items(): out[_path(t)] = out.get(_path(t), 0) + w
    for t, w in (extra or {}).items(): out[_path(t)] = out.get(_path(t), 0) + w
    return out

def race(spec):
    """'caucasian' | {'caucasian': .7, 'african': .2, 'asian': .1} → веса рас MakeHuman (сумма 1).
    Без расы MakeHuman даёт «усреднённое» лицо, которое читается как андрогинное — раса всегда задаётся."""
    if spec is None: return {'caucasian': 1 / 3, 'african': 1 / 3, 'asian': 1 / 3}
    if isinstance(spec, str): spec = {spec: 1.0}
    s = sum(spec.values()) or 1
    return {k: v / s for k, v in spec.items()}
