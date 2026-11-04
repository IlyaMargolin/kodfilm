#!/usr/bin/env bash
# Скачивает бесплатные ассеты студии (в git не храним, они большие).
# Лицензии: Sponza — Crytek, CC BY 3.0 (Khronos glTF-Sample-Assets); персонажи Soldier/Xbot/Michelle — Mixamo через three.js examples;
# HDRI — Poly Haven, CC0 (через three.js examples); голова Lee Perry-Smith — Infinite Realities, CC BY 3.0.
set -e; cd "$(dirname "$0")"
T=https://raw.githubusercontent.com/mrdoob/three.js/r170/examples
mkdir -p hdri chars sets/sponza scans
for f in venice_sunset_1k royal_esplanade_1k quarry_01_1k moonless_golf_1k pedestrian_overpass_1k blouberg_sunrise_2_1k san_giuseppe_bridge_2k spruit_sunrise_1k; do
  [ -f hdri/$f.hdr ] || curl -sSfL -o hdri/$f.hdr $T/textures/equirectangular/$f.hdr; done
for f in Soldier.glb Xbot.glb Michelle.glb RobotExpressive/RobotExpressive.glb; do
  [ -f chars/$(basename $f) ] || curl -sSfL -o chars/$(basename $f) $T/models/gltf/$f; done
for f in LeePerrySmith.glb Infinite-Level_02_Tangent_SmoothUV.jpg Map-COL.jpg; do
  [ -f scans/$f ] || curl -sSfL -o scans/$f $T/models/gltf/LeePerrySmith/$f; done
S=https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/Sponza/glTF
[ -f sets/sponza/Sponza.gltf ] || curl -sSfL -o sets/sponza/Sponza.gltf $S/Sponza.gltf
python3 -c "import json;g=json.load(open('sets/sponza/Sponza.gltf'));print('\n'.join([b['uri'] for b in g['buffers']]+[i['uri'] for i in g['images']]))" | \
  while read u; do [ -f "sets/sponza/$u" ] || curl -sSfL -o "sets/sponza/$u" "$S/$u"; done
# Фоли: шаги по камню и звуки брони — Kenney Impact Sounds, CC0 (общественное достояние)
mkdir -p sfx
if [ ! -f sfx/footstep_concrete_000.ogg ]; then
  rm -rf /tmp/kis && git clone -q --depth 1 https://github.com/Boyquotes/kenney-impact-sounds-for-godot.git /tmp/kis
  find /tmp/kis \( -name "footstep_concrete_*.ogg" -o -name "impact_metal_light_*.ogg" -o -name "impact_metal_medium_*.ogg" -o -name "impact_plate_light_*.ogg" -o -name "impact_soft_medium_*.ogg" \) -print0 | xargs -0 -I{} cp "{}" sfx/
fi
# Люди: открытые данные MakeHuman (MPFB2) — базовая сетка, морф-таргеты, риг Mixamo и веса кожи, лицензия CC0.
# Код MPFB (GPL) не используем: только каталог data, читает его наш studio/human.py.
if [ ! -f mh/3dobjs/base.obj ]; then
  rm -rf /tmp/mpfb2 && git clone -q --depth 1 https://github.com/makehumancommunity/mpfb2.git /tmp/mpfb2
  mkdir -p mh && cp -r /tmp/mpfb2/src/mpfb/data/3dobjs /tmp/mpfb2/src/mpfb/data/targets /tmp/mpfb2/src/mpfb/data/rigs /tmp/mpfb2/src/mpfb/data/textures mh/ && cp /tmp/mpfb2/LICENSE.ASSETS.md mh/
fi
# Системные ассеты MakeHuman (CC0): фото-кожа, брови, ресницы, глаза — официальный релиз MakeHuman-2, все файлы CC0
if [ ! -d mh/system/skins ]; then
  curl -sSfL -o /tmp/mh_system_CC0.zip https://github.com/Makehuman-2/MH2_Asset_Repository_CCO/releases/download/CC0/mh_system_CC0.zip
  mkdir -p mh/system && python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" /tmp/mh_system_CC0.zip /tmp/mh_sys
  d=$(dirname "$(find /tmp/mh_sys -type d -name skins | head -1)"); cp -r "$d"/* mh/system/ && rm -rf /tmp/mh_sys /tmp/mh_system_CC0.zip
fi
echo "ассеты на месте"
