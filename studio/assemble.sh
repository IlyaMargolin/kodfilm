#!/usr/bin/env bash
# Монтаж: кадры + звук -> фильм. Плёночное зерно, лёгкая виньетка, ореол бликов (halation), кадр уже 2.39:1 (без нарисованных полос).
# studio/assemble.sh out/hram out/hram/film.mp4
set -e
DIR=$1; OUT=$2; FPS=$(python3 -c "import json;print(json.load(open('$DIR/meta.json'))['fps'])")
H=$(python3 -c "from PIL import Image" 2>/dev/null; ffprobe -v error -select_streams v -show_entries stream=height -of csv=p=0 $(ls $DIR/f_*.png | head -1))
W=$(ffprobe -v error -select_streams v -show_entries stream=width -of csv=p=0 $(ls $DIR/f_*.png | head -1))
ffmpeg -y -loglevel error -framerate $FPS -pattern_type glob -i "$DIR/f_*.png" -i "$DIR/sound.wav" \
  -filter_complex "[0:v]split[a][b];[b]curves=all='0/0 0.72/0 1/1',gblur=sigma=14,colorchannelmixer=rr=1:gg=0.55:bb=0.3[h];[a][h]blend=all_mode=screen:all_opacity=0.35,eq=saturation=0.96:gamma=0.98,noise=c0s=7:c0f=t+u,vignette=angle=0.45,format=yuv420p[v]" -map "[v]" -map 1:a \
  -c:v libx264 -preset slow -crf 16 -c:a aac -b:a 256k -shortest -movflags +faststart "$OUT"
echo "Готово: $OUT"
