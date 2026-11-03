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
echo "ассеты на месте"
