# Монтажный лист «Джек Райдер», немая версия 7:00. Источник: сценарий 09 (5.7, 17:00), сжатие для 3 дней производства.
# Каждый план: (сек, движение, что в кадре [EN-промпт], что видит зритель [RU], звук)
# движение: P = «живая картина» 2.5D (камера по нарисованному кадру), W = Wan картинка→видео (вода, трава, звери, дым)
import json, os
JACK = "a lone rider in a pale angular full-face motorcycle helmet with a blue-green visor stripe, short light jacket with dark panels, dark trousers, light tall boots"
BIKE = "a rugged old motorcycle with a single round headlight, red taillight, a bag on the left and a jerrycan with faded blue tape on the right"
S = []
def sc(name, tod, shots): S.append(dict(scene=name, tod=tod, shots=shots))
sc("1. Ущелье, пролог и название", "рассвет после дождя", [
 (4,'W',"a waterfall pours from a wet rocky gorge, heavy droplets and mist cross a warm low sunbeam, close low angle","Вода из ущелья, луч сквозь взвесь","удар воды, тишина гор"),
 (4,'W',"flood water flows between rows of drowned apple trees in a meadow, a dry leaf floats on the roof of a sunken car, ripples","Затопленный сад, лист на крыше машины","течение, капли"),
 (4,'P',f"wide view of a wet mountain road on a cliff ledge above the flooded valley, far away {JACK} appears from behind dark tree trunks on {BIKE}","Из-за деревьев появляется крошечный байк","далёкий мотор"),
 (3,'P',f"side tracking view, {JACK} rides {BIKE} through a wet bend, low sun flickers between trunks on the visor","Джек в повороте, солнце мелькает на забрале","мотор ближе, шины по мокрому"),
 (3,'W',"tall grass by the roadside bends in a gust, tips glowing translucent against the low sun","Трава вспыхивает на просвет","порыв ветра"),
 (3,'P',f"low front view from beside the handlebar, {JACK} on {BIKE} accelerating on a dry straight road, jacket pulled by wind","Джек набирает скорость","мотор вверх, ветер"),
 (6,'P',f"high aerial view of the valley at dawn, a tiny motorcycle on a long road along the ridge, dark forested slope, empty sky for a title","Камера взмывает. Название JACK RYDER","первая тема музыки"),
 (3,'P',"a ruined roadside gas station with one surviving canopy, wet concrete, morning sun","Впереди разрушенная заправка","мотор стихает"),
 (3,'P',f"{BIKE} brakes, red brake light paints the wet edge of a pump island","Стоп-сигнал красит мокрый бетон","тормоз, тишина"),
])
sc("2. Заправка: ключ и снимок", "утро", [
 (3,'P',"close up of a dry gas pump nozzle, broken empty display, dust","Колонка сухая","металл, ветер"),
 (4,'P',f"{JACK} pours the last fuel from a sealed canister with faded blue tape into the tank of {BIKE} under the canopy","Последний бензин из своего запаса","струя, бульканье"),
 (3,'P',"close up of a hand holding a canister tilted, the last drops falling into a tank","До последней капли","капли"),
 (4,'P',"inside a dark gas station back room, a blue stunt safety strap hangs on a hook, a sunbeam from the door","Синяя каскадёрская стропа на крюке","скрип двери"),
 (4,'P',"a faded photo pinned to a wall: a stuntman in a pale helmet with a blue strap at a film set edge, a movie camera nearby","Снимок со съёмок: он был каскадёром","тишина"),
 (3,'P',"close up of a rider raising the visor of a pale helmet, calm blue eyes, stubble, morning light","Он поднимает забрало","щелчок забрала"),
 (5,'P',"close up of a hand holding a big old house key and a family photo in a clear sleeve: a man at a small table with three loved ones","Ключ от дома и семейный снимок","первая нота пианино"),
 (5,'P',f"profile of {JACK} sitting on a concrete curb, visor up, empty road in the background, waiting","Он сидит и смотрит на пустую дорогу","тишина, далёкий ветер"),
 (3,'W',"wind rolls a discarded plastic cup lid across an empty parking lot, it rattles and gets stuck in a crack","Ветер катит крышку стакана. Он вздрагивает на звук","дребезг пластика"),
 (5,'P',"long empty road into hazy hills, nobody comes","Никто не приходит","ветер"),
 (4,'P',f"{JACK} rides {BIKE} away from the gas station along the road, seen from behind","Он едет дальше","мотор"),
 (4,'P',"an old road map on a fuel tank, one route worn white from folding, a circle drawn many times","Карта: маршрут стёрт до дыр, он ездит по кругу","шелест бумаги"),
])
sc("3. Лес: олени, зима, весна", "закат → зима → весна", [
 (4,'W',"small herd of deer with glowing amber antlers grazing at a forest edge at sunset, copper sky between crowns","Стадо оленей с янтарными рогами","лес, жевание"),
 (4,'W',"close up of a deer head three-quarter view, chewing, amber antler tips glowing, eye catching the light","Олень смотрит на Джека и жуёт дальше","дыхание оленя"),
 (3,'P',f"{JACK} stopped under trees, helmet in hand, watching quietly","Джек замер и смотрит","тишина"),
 (4,'P',"inside an old road depot through an open gate: canisters, shelf with food, a blanket on one cot, autumn","Он зимует в депо","эхо"),
 (4,'W',"the same depot gate, now dry snow falls outside on dark fir trees","Через ту же дверь: зима","снег, тишина"),
 (4,'W',f"early spring, {BIKE} with {JACK} rides out through slush from the depot gate, wet clumps fly from the tyre","Весна. Он выезжает","мотор, снежная каша"),
 (4,'W',"melt water streams down a ravine from fir trees toward a river, cloud shadow passing over the forest","Талая вода ведёт к реке","ручьи"),
])
sc("4. Ночной Манхэттен: блик и гончие", "ночь", [
 (3,'P',"flying low over dark harbour water toward the silhouette of ruined Lower Manhattan, no lights, haze between towers","Подлёт к мёртвому городу","низкий гул, вода"),
 (4,'P',f"night street, collapsed facade slabs across lanes, {BIKE} headlight beam cuts the haze, a crushed bus shelter","Фара ищет проезд среди плит","мотор на малом газу"),
 (3,'W',"a motorcycle front tyre breaks the reflection in shallow water on asphalt at night, small splashes","Шина ломает отражение","шлёп воды"),
 (3,'P',"red brake light glow on a crumpled bus fender at night, a fresh tyre arc in wet dust","Красный отсвет на автобусе. След его шины","скрип тормоза"),
 (4,'P',"an empty dark window across the street, a single white glint flashes in a hanging shard of glass","Блик в окне. Там кто-то есть?","тишина, музыка стихает"),
 (3,'P',f"close up of {JACK}, visor up, leaning forward, eyes searching the dark window","Он всматривается, как на заправке","дыхание"),
 (3,'W',"a broken window shutter swings in the wind, the glass shard catches the sky light and goes dark","Это просто стекло на ветру","скрип створки"),
 (4,'P',f"inside a dark parking garage, {BIKE} with headlight on, nose to a service ramp; a steel cabinet door leans by the exit","Гараж. Фара светит на выход","капель"),
 (3,'P',"hands lift a canister with faded blue tape from a hidden floor niche, headlight light","Его тайник с топливом","металл"),
 (4,'W',"three lean ash-grey hounds with faint red glowing lines on their bodies rise from a dry lair under the ramp in darkness","Из тени поднимаются пепельные гончие","рычание"),
 (3,'W',"an ash-grey hound with red glowing lines lunges at a steel door held up as a shield, sparks of motion","Гончая бросается, он закрывается дверцей","удар металла"),
 (3,'P',f"{JACK} jumps on {BIKE} and twists the throttle, headlight swings to the ramp","Рывок к байку","мотор взрывается"),
 (3,'W',"side view, motorcycle races out of a garage ramp into a night street, two hounds running right behind, red taillight","Погоня","мотор, когти по бетону"),
 (3,'W',"a third hound cuts across a sidewalk to intercept the motorcycle, night street with slabs","Третья режет угол","рык"),
 (4,'W',"point of view of a running hound chasing a red taillight through a dark ruined street, ground rushing by","Глазами гончей: красный огонёк впереди","дыхание зверя"),
 (3,'W',"low angle, motorcycle brakes hard and slides around a fallen slab, hounds overshoot","Резкое торможение, гончие проскакивают","визг шины"),
 (3,'P',"the hounds stop at the edge of their territory and watch the motorcycle go, red lines dimming","Гончие отстают","тишина, дыхание"),
 (4,'P',"the same crumpled bus from the other side, a muddy tyre arc on wet dust filling with water","Тот же автобус. Это его собственный след","капля, тишина"),
 (3,'P',f"close up of {JACK} breathing, looking from the track to a pale strip of sky between towers","Он понял, что ездит по кругу. Смотрит в просвет","вдох"),
 (5,'P',"wide night shot, a single intact lane of a northern bridge across the Hudson, a tiny headlight crossing, distant Manhattan","Он уезжает из города по мосту","тихий альт"),
])
sc("5. Статуя Свободы", "предрассветные сумерки", [
 (4,'P',f"{BIKE} parked at a harbour edge before dawn, empty ferry gangway dips into water","Пустые сходни упираются в воду","прилив, цепь"),
 (3,'W',"close up of a rusty chain moving in the tide at a harbour railing, wet links","Цепь шевелится в прилив","звон цепи"),
 (6,'P',"telephoto over the shoulder of a man in a pale helmet: across the water the colossal broken head of the Statue of Liberty with green copper crown lies on rubble, mist","Голова Статуи Свободы на обломках","одна долгая нота"),
 (4,'P',"close up of the giant copper face of the fallen statue, wet streaks, gulls","Масштаб катастрофы","чайки"),
 (4,'P',"a road reflector plate with two white reflectors lies by a railing, a hand picks it up","Он находит катафот с двумя отражателями","металл о бетон"),
 (3,'P',"close up of a reflector plate catching the headlight, two white points flash","Два огонька вспыхивают, как тот блик в окне","звон"),
 (3,'P',f"{JACK} slides the reflector plate into the side bag of {BIKE}","Он забирает её с собой","молния сумки"),
])
sc("6. Океан и скат", "утро", [
 (4,'P',f"coastal dam road, {JACK} stops {BIKE} at a gap in sedge and dunes, open Atlantic horizon","Открывается океан","мотор глохнет, прибой"),
 (3,'W',"sedge bends in a gust, stems follow with different delays, ocean beyond","Порыв ветра в осоке","ветер"),
 (3,'P',"extreme close up through a raised visor, a blue eye finds the open water","Голубой глаз ищет воду","тишина"),
 (5,'W',"a huge ray with glowing blue patches bursts out of an ocean wave and glides over the water, water sheets stream off its wings","Огромный скат вырывается из волны","всплеск, музыка"),
 (4,'W',"the ray levitates low over the swell then slips back under, spray in the sun","Скат уходит под воду","плеск"),
 (3,'P',"a faint smile in the eyes behind a raised visor","Первая улыбка","тихо"),
])
sc("7. Промоина: падение и трап", "ливень", [
 (4,'P',"rain storm, a road ends at a washed-out concrete channel, a slope down into brown water, a raised steel ramp on a hinge above","Дорога обрывается: внизу вода, вверху поднятый трап","дождь"),
 (3,'P',"old road arrow sign on a leaning pole points down to the flooded lower crossing","Стрелка ведёт вниз, в воду","дождь по металлу"),
 (3,'W',"a hand dips a wooden plank into shallow water, it taps on concrete below","Он проверяет дно","стук дерева"),
 (3,'P',f"{JACK} aims {BIKE} at the shallow crossing in heavy rain","Решает ехать низом","мотор"),
 (3,'W',"brown water rushes from the side over the crossing, carrying sand, front tyre in the water","Сбоку бьёт бурый поток","рёв воды"),
 (3,'W',"the concrete edge breaks under the front wheel, motorcycle tips over to the right into water","Бетон ломается, байк падает","удар, всплеск"),
 (3,'P',"close up of a scratched visor in the water, rain drops, the headlight shining underwater","Забрало в воде, фара светит под водой","глухой звук под водой"),
 (4,'P',"hands hook the blue stunt strap to the motorcycle frame and a ring on dry concrete","Синяя стропа: старое ремесло спасает байк","щелчок карабина"),
 (4,'W',f"{JACK} hauls the motorcycle up the slope with the strap tensioned, rain, mud","Он вытягивает байк","натяжение, дыхание"),
 (3,'P',f"{JACK} breathing, holding his right shoulder, rain on the helmet","Плечо ушиблено","дождь"),
 (4,'P',"a manual winch with a chain and brake handle by the raised steel ramp, rain","Механизм трапа","скрип"),
 (4,'W',"the hinged steel ramp slowly lowers across the channel and lands on two concrete supports","Трап медленно опускается","цепь, лязг"),
 (3,'P',f"{JACK} walks across the ribbed steel ramp checking each step, rain","Он проверяет трап пешком","шаги по решётке"),
 (4,'P',f"{BIKE} rolls across the lowered ramp over rushing water","Байк переходит","мотор, вода внизу"),
])
sc("8. Стрелка и отражатели", "дождь уходит", [
 (4,'P',f"far side of the crossing, free road ahead, {JACK} on {BIKE} ready to go, rain moving out over the ocean","Дорога свободна. Можно уезжать","мотор на холостых"),
 (3,'P',"close up of a thumb pressing the engine kill switch","Он глушит мотор","тишина, капли"),
 (3,'P',"from this side the lower crossing looks flat and safe, the upper ramp hidden behind concrete","Отсюда ловушка выглядит безопасной","ветер"),
 (4,'P',"hands take the arrow plate off a short pole and turn it to point to the upper ramp","Он разворачивает стрелку к трапу","скрежет"),
 (3,'W',"wind turns the loose arrow plate back, rain drops fly","Ветер сбивает её обратно","дребезг"),
 (3,'P',"hands tighten the clamp with a tool, the arrow holds in the next gust","Он затягивает. Держит","ключ, тишина"),
 (4,'P',"hands fix the reflector plate with two white reflectors under the arrow","Он ставит катафот под стрелку","металл"),
 (3,'P',f"{JACK} turns on the headlight of {BIKE} toward the sign","Включает фару","щелчок"),
 (4,'P',"two white reflectors flash brightly under the arrow in the headlight beam, dusk, wet road","Два огонька вспыхивают: знак для того, кто приедет","главная тема"),
 (4,'P',f"wide shot, the corrected arrow and the shining reflectors, {JACK} small, looking back at the empty road","Он смотрит на дорогу, по которой кто-то приедет","музыка"),
])
sc("9. Залив на закате", "золотой час", [
 (5,'W',f"golden hour, {JACK} rides {BIKE} along an Atlantic beach road, two waves roll in, foam on dark sand, camera flies up over a dune","Дорога у океана","мотор, прибой, тема"),
 (5,'P',f"{JACK} sits on a low rock by the water, helmet beside him on a stone, wind moves his short hair, golden light","Он сидит у воды, шлем рядом","прибой"),
 (4,'W',"sea grass tips glow in the low sun as wind lays them into the light","Трава у залива светится","ветер"),
 (5,'P',f"{JACK} rides {BIKE} on a coastal highway toward a sunset over a calm bay, small figure in vast landscape","Он едет к закату","мотор уходит вдаль"),
 (6,'P',"wide final view of the bay at sunset, empty road, a tiny red taillight far away","Финал: дорога, залив, ветер","последняя нота"),
 (4,'P',"black title card","Чёрное. Титр JACK RYDER","прибой"),
 (3,'P',"black","Чёрное. Воздух и прибой","прибой затихает"),
])
# «живые картины» держим дольше: спокойный ритм дороги между сценами действия (итог ровно 7:00)
for _s in S: _s['shots'] = [(round(x[0] * 1.4) if x[1] == 'P' else x[0],) + tuple(x[1:]) for x in _s['shots']]
if __name__ == '__main__':
    D = os.path.dirname(os.path.abspath(__file__)); t = 0; n = 0; rows = []
    md = ["# «Джек Райдер» · немая версия 7:00 · монтажный лист", "", "Источник: режиссёрский сценарий 5.7 (17:00), ужатый под 3 дня. Выпали карьер (K03) и спортплощадка (K08). Сюжетные узлы сохранены: потеря (ключ, снимок), поиск (блик, след по кругу), выбор (стрелка и отражатели для чужого человека).", "",
          "Движение: **Ж** — «живая картина» (камера идёт по нарисованному кадру с глубиной, ничего не плывёт); **В** — видеомодель (вода, трава, звери, дым).", ""]
    for s in S:
        d = sum(x[0] for x in s['shots'])
        md += [f"## {s['scene']} · {s['tod']} · {t//60}:{t%60:02d}–{(t+d)//60}:{(t+d)%60:02d}", "", "| # | Время | Сек | Дв. | Что видит зритель | Звук |", "|---|---|---|---|---|---|"]
        for sec, mv, pr, ru, snd in s['shots']:
            n += 1; md.append(f"| {n} | {t//60}:{t%60:02d} | {sec} | {'Ж' if mv=='P' else 'В'} | {ru} | {snd} |")
            rows.append(dict(n=n, t=t, sec=sec, move=mv, prompt=pr, ru=ru, sound=snd, scene=s['scene'], tod=s['tod'])); t += sec
        md.append("")
    W = sum(r['sec'] for r in rows if r['move'] == 'W')
    md.insert(4, f"**Итого:** планов {n}, {t//60}:{t%60:02d}. Видеомодель: планов {sum(r["move"]=="W" for r in rows)} ({W} с), живая картина: планов {sum(r["move"]=="P" for r in rows)}.\n")
    open(os.path.join(D, 'shotlist.md'), 'w').write('\n'.join(md)); json.dump(rows, open(os.path.join(D, 'shots.json'), 'w'), ensure_ascii=False, indent=1)
    print(n, t, W)
