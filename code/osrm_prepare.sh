#!/bin/bash
# OSRM 도로망 준비 (WSL Ubuntu에서 root로 실행) — 2026-11-03
# 목적: analyze_access_road.py(자체 구현)와 비교하기 위한 표준 OSRM 이동시간.
# 같은 OSM 추출본(data/raw/osm_2026-11-03/south-korea-latest.osm.pbf)을 WSL 안으로 '복사'해서 사용(원본 수정 없음).
# 프로필: 이미지에 포함된 기본 car.lua (회전·신호 지연 포함), 알고리즘 MLD.
# 사용(Windows): wsl -d Ubuntu -u root -- bash <프로젝트 경로>/code/osrm_prepare.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"  # 프로젝트 루트 (2026-11-04: 개인 경로 제거)
IMG=ghcr.io/project-osrm/osrm-backend:v6.0.0
SRC=$ROOT/data/raw/osm_2026-11-03/south-korea-latest.osm.pbf
W=/srv/osrm-kr
LOG=$ROOT/output/osrm_prepare_log.txt
mkdir -p "$W"
{
  echo "start $(date -Is)"
  echo "image $IMG $(docker images --digests --format '{{.Digest}}' $IMG)"
  cp -f "$SRC" "$W/kr.osm.pbf"
  echo "pbf sha256 $(sha256sum "$W/kr.osm.pbf" | cut -d' ' -f1)"
  for step in "osrm-extract -p /opt/car.lua -t 24 /data/kr.osm.pbf" "osrm-partition /data/kr.osrm" "osrm-customize /data/kr.osrm"; do
    t0=$(date +%s)
    docker run --rm -v "$W:/data" "$IMG" $step > "$W/step.log" 2>&1 || { echo "FAILED: $step"; tail -20 "$W/step.log"; exit 1; }
    echo "ok ($(( $(date +%s) - t0 ))s): $step"
    grep -E "RAM|Processed|edges|nodes|ways" "$W/step.log" | tail -4 || true
  done
  docker run --rm "$IMG" sh -c 'sha256sum /opt/car.lua'
  echo "end $(date -Is)"
} 2>&1 | tee "$LOG"
