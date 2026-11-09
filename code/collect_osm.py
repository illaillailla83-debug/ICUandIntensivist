"""OpenStreetMap 한국 추출본(Geofabrik, ODbL) 다운로드 + MD5 검증 + SHA-256 기록. 이미 있으면 건너뜀.

사용: python -I -X utf8 code/collect_osm.py
출력: data/raw/osm_<날짜>/south-korea-latest.osm.pbf, download_log.txt
"""
import datetime
import hashlib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://download.geofabrik.de/asia/south-korea-latest.osm.pbf"
OUT = ROOT / f"data/raw/osm_{datetime.date.today():%Y-%m-%d}"
UA = {"User-Agent": "icu-access-research"}


def get(url, dst=None):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=600) as r:
        if dst is None:
            return r.read(), dict(r.headers)
        with open(dst, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
        return None, dict(r.headers)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / "south-korea-latest.osm.pbf"
    hdr = {}
    if not dst.exists():
        _, hdr = get(URL, dst)
    md5_ref = get(URL + ".md5")[0].decode().split()[0]
    md5 = hashlib.md5(dst.read_bytes()).hexdigest()
    sha = hashlib.sha256(dst.read_bytes()).hexdigest()
    line = (f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}\t{URL}\t{dst.stat().st_size} bytes\t"
            f"Last-Modified={hdr.get('Last-Modified', '(기존 파일)')}\tmd5_ok={md5 == md5_ref}\tsha256={sha}")
    with open(OUT / "download_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)
    if md5 != md5_ref:
        raise SystemExit("MD5 불일치: 서버 파일이 바뀌었거나 다운로드가 손상됨 → 파일을 _to_delete/로 옮기고 다시 받기")


if __name__ == "__main__":
    main()
