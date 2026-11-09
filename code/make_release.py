"""GitHub 공개용 패키지 만들기 (연구자가 투고 직전에 실행). 2026-11-04

명시한 파일만 release/icu-access/ 로 복사하고 FILES.sha256 목록을 만든다.
안전장치
  - .env, 캐시(road_graph_osm.pkl), 원고(manuscript/), 내부 기록(RESULTS.md, HANDOFF*), 정보공개청구 초안은 넣지 않음
  - 복사한 텍스트 파일 안에 .env의 키 값이 있으면 중단
  - 큰 원자료(OSM pbf, HIRA 원본, KOSIS JSON, 경계 geojson)는 넣지 않음 → data/SOURCES.md와 raw_manifest_sha256.csv로 대체
사용: python -I -X utf8 code/make_release.py   (release/ 가 이미 있으면 덮어쓰지 않고 중단)
"""
import hashlib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DST = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "release/icu-access"  # 인자로 시험용 위치 지정 가능
INCLUDE = [
    "code/*.py", "code/*.sh",
    "data/clean/*.csv", "data/raw_manifest_sha256.csv",
    "data/raw/khqa_manual_2026-11/*",            # 수기 기록한 전담전문의 지표 (Data sharing 문장에 명시)
    "data/raw/hira_eval_api_2026-11-03/*",       # 적정성평가 등급 API 응답 (0.8 MB)
    "data/raw/책임의료기관_지정현황_2024.csv",       # 연구자 전사·정리본
    "docs/khqa_bookmarklet.html", "docs/khqa_checklist.csv",
    "output/tables/*", "output/figures/*", "output/*_qc.md", "output/osrm_comparison.md",
    "output/osrm_prepare_log.txt", "output/refs_meta_v5_2026-11-04.txt",
    "output/policy_road.csv",                    # (2026-11-07) Critical Care Additional file 1 각주가 이 파일을 인용
    # manuscript/legends.md는 2026-11-09 연구자 요청으로 뺌(원고 관련 파일은 공개하지 않음)
]
REPO_DOCS = {"docs/repo/README.md": "README.md", "docs/repo/LICENSE": "LICENSE",
             "docs/repo/DATA_LICENSE.md": "DATA_LICENSE.md", "docs/repo/requirements.txt": "requirements.txt",
             "docs/repo/gitignore.txt": ".gitignore", "docs/repo/CITATION.cff": "CITATION.cff",
             # (2026-11-05 채팅 요청) 출처·작업 기록을 docs/에 둠
             "data/SOURCES.md": "docs/SOURCES.md", "output/RESULTS.md": "docs/RESULTS.md",
             "output/snapfix_changes_2026-11-03.md": "docs/snapfix_changes_2026-11-03.md"}
NEVER = {".env", "road_graph_osm.pkl"}
TEXT = {".py", ".sh", ".csv", ".md", ".txt", ".html", ".json"}


def env_values():
    p = ROOT / ".env"
    if not p.exists():
        return []
    vals = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            v = line.split("=", 1)[1].strip().strip('"').strip("'")
            if len(v) >= 8:
                vals.append(v)
    return vals


def main():
    if DST.exists():
        sys.exit(f"{DST} 가 이미 있음 — 확인 후 지우거나 이름을 바꾼 뒤 다시 실행")
    files = []
    for pat in INCLUDE:
        hit = sorted(p for p in ROOT.glob(pat) if p.is_file() and p.name not in NEVER)
        if not hit:
            print(f"경고: 해당 파일 없음 {pat}")
        files += hit
    secrets = env_values()
    for src in files:
        rel = src.relative_to(ROOT)
        if src.suffix in TEXT and secrets:
            t = src.read_text(encoding="utf-8", errors="ignore")
            if any(s in t for s in secrets):
                sys.exit(f"중단: {rel} 안에 .env 키 값이 있음")
        (DST / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, DST / rel)
    for src, dst in REPO_DOCS.items():
        (DST / dst).parent.mkdir(parents=True, exist_ok=True)
        if secrets and any(s in (ROOT / src).read_text(encoding="utf-8", errors="ignore") for s in secrets):
            sys.exit(f"중단: {src} 안에 .env 키 값이 있음")
        shutil.copy2(ROOT / src, DST / dst)
    lines = []
    for p in sorted(DST.rglob("*")):
        if p.is_file() and p.name != "FILES.sha256":
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(DST).as_posix()}")
    (DST / "FILES.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    size = sum(p.stat().st_size for p in DST.rglob("*") if p.is_file())
    print(f"{len(lines)} files, {size / 1e6:.1f} MB → {DST}")
    big = [(p.stat().st_size, p) for p in DST.rglob("*") if p.is_file() and p.stat().st_size > 50e6]
    for s, p in big:
        print(f"주의: GitHub 100 MB 한도에 가까운 파일 {p.relative_to(DST)} {s / 1e6:.0f} MB")


if __name__ == "__main__":
    main()
