#!/usr/bin/env bash
# Монтаж: кадры + звук -> фильм. Плёночное зерно, лёгкая виньетка, ореол бликов (halation), кадр уже 2.39:1 (без нарисованных полос).
# studio/assemble.sh out/hram out/hram/film.mp4
set -e
DIR=$1; OUT=$2; FPS=$(python3 -c "import json;print(json.load(open('$DIR/meta.json'))['fps'])")
H=$(python3 -c "from PIL import Image" 2>/dev/null; ffprobe -v error -select_streams v -show_entries stream=height -of csv=p=0 $(ls $DIR/f_*.png | head -1))
W=$(ffprobe -v error -select_streams v -show_entries stream=width -of csv=p=0 $(ls $DIR/f_*.png | head -1))
# пост из пульта стиля (meta.json → look.post): зерно, виньетка, ореол бликов, «на двойках»; без look — прежние значения
read GR VG HA TW <<< $(python3 -c "import json;p=json.load(open('$DIR/meta.json')).get('look',{}).get('post',{});print(round(35*p.get('grain',0.2)),p.get('vignette',0.45),p.get('halation',0.35),int(bool(p.get('twos'))))")
NOISE=$([ "$GR" -gt 0 ] && echo ",noise=c0s=$GR:c0f=t+u:all_seed=7" || echo "")
VIG=$(python3 -c "print(',vignette=angle=%.3f' % (float('$VG') or 0) if float('$VG') > 0 else '')")
TWOS=$([ "$TW" = 1 ] && echo "fps=$((FPS/2)),fps=$FPS," || echo "")
ffmpeg -y -loglevel error -framerate $FPS -pattern_type glob -i "$DIR/f_*.png" -i "$DIR/sound.wav" \
  -filter_complex "[0:v]${TWOS}split[a][b];[b]curves=all='0/0 0.72/0 1/1',gblur=sigma=14,colorchannelmixer=rr=1:gg=0.55:bb=0.3[h];[a][h]blend=all_mode=screen:all_opacity=$HA,eq=saturation=0.96:gamma=0.98${NOISE}${VIG},format=yuv420p[v]" -map "[v]" -map 1:a \
  -c:v libx264 -preset slow -crf 16 -c:a aac -b:a 256k -shortest -movflags +faststart "$OUT"
echo "Готово: $OUT"
