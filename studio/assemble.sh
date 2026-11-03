#!/usr/bin/env bash
# Монтаж: кадры + звук -> фильм. Плёночное зерно, лёгкая виньетка, каше 2.39:1.
# studio/assemble.sh out/hram out/hram/film.mp4
set -e
DIR=$1; OUT=$2; FPS=$(python3 -c "import json;print(json.load(open('$DIR/meta.json'))['fps'])")
H=$(python3 -c "from PIL import Image" 2>/dev/null; ffprobe -v error -select_streams v -show_entries stream=height -of csv=p=0 $(ls $DIR/f_*.png | head -1))
W=$(ffprobe -v error -select_streams v -show_entries stream=width -of csv=p=0 $(ls $DIR/f_*.png | head -1))
BAR=$(( (H - W * 100 / 239) / 2 ))
ffmpeg -y -loglevel error -framerate $FPS -pattern_type glob -i "$DIR/f_*.png" -i "$DIR/sound.wav" \
  -vf "noise=c0s=7:c0f=t+u,vignette=angle=0.45,drawbox=x=0:y=0:w=iw:h=$BAR:color=black:t=fill,drawbox=x=0:y=ih-$BAR:w=iw:h=$BAR:color=black:t=fill,format=yuv420p" \
  -c:v libx264 -preset slow -crf 16 -c:a aac -b:a 256k -shortest -movflags +faststart "$OUT"
echo "Готово: $OUT"
