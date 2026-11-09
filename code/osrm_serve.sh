#!/bin/bash
# osrm-routed 실행(백그라운드 컨테이너). 사용: wsl -d Ubuntu -u root -- bash <프로젝트 경로>/code/osrm_serve.sh
# 중지: wsl -d Ubuntu -u root -- docker rm -f osrm-kr
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"  # 프로젝트 루트 (2026-11-04: 개인 경로 제거)
IMG=ghcr.io/project-osrm/osrm-backend:v6.0.0
docker rm -f osrm-kr >/dev/null 2>&1 || true
docker run -d --name osrm-kr -p 5000:5000 -v /srv/osrm-kr:/data "$IMG" \
  osrm-routed --algorithm mld --max-table-size 1000 /data/kr.osrm >/dev/null
for i in $(seq 1 60); do
  if curl -s "http://127.0.0.1:5000/nearest/v1/driving/126.978,37.566" | grep -q '"code":"Ok"'; then echo "osrm-routed ready"; exit 0; fi
  sleep 2
done
echo "osrm-routed not ready"; docker logs --tail 20 osrm-kr; exit 1
