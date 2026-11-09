"""행정동 경계 geojson(vuski/admdongkor, SGIS 가공, CC BY 4.0) 다운로드 + SHA-256 기록. 이미 있으면 건너뜀.

사용: python -I -X utf8 code/collect_boundaries.py [버전, 기본 ver20261001]
출력: data/raw/admdongkor_<버전>/HangJeongDong_<버전>.geojson, download_log.txt
"""
import datetime
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VER = sys.argv[1] if len(sys.argv) > 1 else "ver20261001"
URL = f"https://raw.githubusercontent.com/vuski/admdongkor/master/{VER}/HangJeongDong_{VER}.geojson"
OUT = ROOT / f"data/raw/admdongkor_{VER}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"HangJeongDong_{VER}.geojson"
    if not dst.exists():
        req = urllib.request.Request(URL, headers={"User-Agent": "icu-access-research"})
        with urllib.request.urlopen(req, timeout=300) as r:
            dst.write_bytes(r.read())
    sha = hashlib.sha256(dst.read_bytes()).hexdigest()
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}\t{URL}\t{dst.stat().st_size} bytes\tsha256={sha}"
    with open(OUT / "download_log.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


if __name__ == "__main__":
    main()
