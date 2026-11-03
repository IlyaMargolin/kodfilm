# Съёмочная группа: режиссёры (что и зачем снимаем), операторы (как снимаем и светим), композиторы (как звучит).
# Любой режиссёр работает с любым оператором; у каждого есть «свой» по умолчанию (как в жизни: Вильнёв — Фрейзер, Финчер — Кроненвет).
from .directors import DIRECTORS
from .cinematographers import DPS
from .composers import COMPOSERS

def crew(director, dp=None, composer=None):
    d = DIRECTORS[director]; c = DPS[dp or d['dp']]; m = COMPOSERS[composer or d['composer']]
    return d, c, m

def profile(director, dp=None):
    """Единый профиль для раскадровщика: темп и выбор планов от режиссёра, оптика, движение и композиция от оператора."""
    d, c, _ = crew(director, dp)
    comp = dict(c['comp'])
    for k, v in d.get('comp', {}).items(): comp[k] = comp.get(k, 0.5) * v
    return dict(asl=d['asl'], prefer=d['prefer'], dutch=d['dutch'], lens=c['lens'], move=c['move'], hand=c['hand'],
                sym=max(d.get('sym', 0), c['sym']), low=c['low'], fstop=c['fstop'], comp=comp, light=c['light'],
                desc=d['desc'] + ' / ' + c['desc'], director=director, dp=dp or d['dp'])
