"""data/raw/ 아래 모든 원자료의 크기·수정시각·SHA-256 목록 (원본은 읽기만 함).

이유(2026-11-03): Methods에 "raw downloads are kept unmodified with ... file size and SHA-256 hash"라고 썼으나,
SOURCES.md에는 HIRA·admdongkor·OSM·복지부 파일만 해시가 있고 KOSIS·평가 API·khqa 수기본에는 없었음.
재실행하면 목록을 다시 만들고, 이전 목록과 달라진 파일을 출력함(원자료 변조 확인용).
출력: data/raw_manifest_sha256.csv
사용: python -I -X utf8 code/make_raw_manifest.py
"""
import csv
import hashlib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw"
OUT = ROOT / "data/raw_manifest_sha256.csv"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main():
    old = {}
    if OUT.exists():
        old = {r["path"]: r["sha256"] for r in csv.DictReader(open(OUT, encoding="utf-8-sig"))}
    rows = []
    for p in sorted(RAW.rglob("*")):
        if p.is_file():
            st = p.stat()
            rows.append({"path": p.relative_to(ROOT).as_posix(), "bytes": st.st_size,
                         "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                         "sha256": sha256(p)})
    changed = [r["path"] for r in rows if r["path"] in old and old[r["path"]] != r["sha256"]]
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["path", "bytes", "modified", "sha256"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} files, {sum(r['bytes'] for r in rows) / 1e6:.1f} MB; changed since last manifest: {changed or 'none'}")


if __name__ == "__main__":
    main()
