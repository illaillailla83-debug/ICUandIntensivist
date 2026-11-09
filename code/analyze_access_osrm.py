"""OSRM(표준 엔진) 이동시간 — 자체 구현(analyze_access_road.py)과 비교하는 민감도 분석. 2026-11-03

전제: WSL에서 osrm-routed가 localhost:5000에 떠 있어야 함 (code/osrm_prepare.sh로 준비, code/osrm_serve.sh로 실행).
OSRM v6.0.0 기본 car.lua(회전·신호 지연 포함), MLD, 같은 OSM 추출본, 같은 읍면동 대표점·시설 좌표.

두 가지 시간을 저장:
  raw  = OSRM table duration (OSRM이 대표점·병원 좌표를 가장 가까운 도로에 붙인 뒤의 도로 시간, 붙이는 거리는 시간 0)
  conn = raw + (대표점→도로 + 병원→도로 거리) ÷ 20 km/h  ← 자체 구현과 같은 접속 규칙. **비교의 기본은 conn**
OSRM이 경로를 못 찾으면(null) 무한대 처리.
입력: data/clean/{emd_points, icu_hospitals, icu_intensivist_khqa, access_road_emd}.csv
출력: data/clean/access_osrm_emd.csv, output/osrm_comparison.md
사용: python -I -X utf8 code/analyze_access_osrm.py
"""
import csv
import json
import math
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
URL = "http://127.0.0.1:5000/table/v1/driving/"
SNAP_KMH = 20.0
BATCH = 200
CAPITAL = {"서울", "인천", "경기"}


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def table(src, dst):
    coords = ";".join(f"{x:.6f},{y:.6f}" for x, y in src + dst)
    q = (f"{URL}{coords}?sources={';'.join(map(str, range(len(src))))}"
         f"&destinations={';'.join(map(str, range(len(src), len(src) + len(dst))))}&annotations=duration")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(q, timeout=300) as r:
                j = json.load(r)
            if j.get("code") == "Ok":
                return j
            raise RuntimeError(j.get("code"))
        except Exception as e:  # 재시도 로그
            print(f"  retry {attempt + 1}: {e}")
            time.sleep(2)
    raise RuntimeError("OSRM table failed")


def wq(pairs, q):
    pairs = sorted(pairs)
    cut, acc = sum(w for _, w in pairs) * q, 0
    for v, w in pairs:
        acc += w
        if acc >= cut:
            return v


def main():
    pts = rd(C / "emd_points.csv")
    icu = rd(C / "icu_hospitals.csv")
    ints = {r["암호화요양기호"] for r in rd(C / "icu_intensivist_khqa.csv") if r["전담전문의_있음"] == "1"}
    own = {r["읍면동코드"]: r for r in rd(C / "access_road_emd.csv")}
    dst = [(float(h["좌표X_경도"]), float(h["좌표Y_위도"])) for h in icu]
    is_int = [h["암호화요양기호"] in ints for h in icu]
    assert sum(is_int) == 142 and len(icu) == 362

    t0 = time.time()
    out = []
    for b in range(0, len(pts), BATCH):
        chunk = pts[b:b + BATCH]
        src = [(float(p["경도"]), float(p["위도"])) for p in chunk]
        j = table(src, dst)
        dsnap = [w["distance"] for w in j["destinations"]]
        for i, p in enumerate(chunk):
            ssnap = j["sources"][i]["distance"]
            row = j["durations"][i]
            best = {}
            for name, sel in (("ICU", lambda k: True), ("전담ICU", lambda k: is_int[k])):
                raw = [row[k] / 60 if row[k] is not None else math.inf for k in range(len(dst)) if sel(k)]
                conn = [(row[k] / 60 + (ssnap + dsnap[k]) / 1000 / SNAP_KMH * 60) if row[k] is not None else math.inf
                        for k in range(len(dst)) if sel(k)]
                best[name] = (min(raw), min(conn))
            out.append({"읍면동코드": p["읍면동코드"], "시도_17": own[p["읍면동코드"]]["시도_17"],
                        "인구": int(p["인구"]), "65세이상": int(p["65세이상"]), "80세이상": int(p["80세이상"]),
                        "OSRM스냅_m": round(ssnap, 1), "도로망연결": own[p["읍면동코드"]]["도로망연결"],
                        "ICU_분_osrm": round(best["ICU"][1], 1), "전담ICU_분_osrm": round(best["전담ICU"][1], 1),
                        "ICU_분_osrm_raw": round(best["ICU"][0], 1), "전담ICU_분_osrm_raw": round(best["전담ICU"][0], 1),
                        "ICU_분_자체": float(own[p["읍면동코드"]]["ICU_분"]),
                        "전담ICU_분_자체": float(own[p["읍면동코드"]]["전담ICU_분"])})
        print(f"{b + len(chunk)}/{len(pts)} ({time.time() - t0:.0f}s)")
    log = [f"OSRM table {len(pts)}×{len(dst)}, {time.time() - t0:.0f}s, 병원 스냅 최대 {max(dsnap):.0f} m"]

    with open(C / "access_osrm_emd.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    tot = {g: sum(o[g] for o in out) for g in ("인구", "65세이상", "80세이상")}

    def far(col, cut, g, rows=out):
        return sum(o[g] for o in rows if o[col] > cut)

    md = ["# OSRM v6.0.0 vs 자체 구현 — 도로 이동시간 비교", "",
          "OSRM 기본 car.lua(회전·신호 지연 포함, MLD). 'OSRM' = OSRM 도로 시간 + 접속거리 20 km/h(자체 구현과 같은 접속 규칙). "
          "'OSRM raw' = 접속시간 없이 OSRM 값만.", "",
          "## 1. 컷오프별 미도달 인구", "",
          "| 대상 | 컷오프 | 연령 | 자체 구현 | OSRM | OSRM raw | OSRM/자체 |", "|---|---|---|---|---|---|---|"]
    for name, lab in (("ICU", "성인 ICU"), ("전담ICU", "전담 ICU")):
        for cut in (30, 60, 90):
            for g in ("인구", "65세이상", "80세이상"):
                a, b_, c = far(f"{name}_분_자체", cut, g), far(f"{name}_분_osrm", cut, g), far(f"{name}_분_osrm_raw", cut, g)
                md.append(f"| {lab} | >{cut}분 | {g} | {a:,} ({100 * a / tot[g]:.1f}%) | {b_:,} ({100 * b_ / tot[g]:.1f}%) | "
                          f"{c:,} ({100 * c / tot[g]:.1f}%) | {b_ / a:.2f} |" if a else
                          f"| {lab} | >{cut}분 | {g} | 0 | {b_:,} | {c:,} | — |")

    md += ["", "## 2. 이동시간 자체 비교 (인구가중)", "", "| 대상 | 자체 중앙값(IQR) | OSRM 중앙값(IQR) | OSRM−자체 중앙값(IQR) | "
           "OSRM/자체 중앙값 | 60분 기준 분류 일치(인구%) |", "|---|---|---|---|---|---|"]
    for name, lab in (("ICU", "성인 ICU"), ("전담ICU", "전담 ICU")):
        fin = [o for o in out if math.isfinite(o[f"{name}_분_osrm"])]
        A = [(o[f"{name}_분_자체"], o["인구"]) for o in fin]
        B = [(o[f"{name}_분_osrm"], o["인구"]) for o in fin]
        D = [(o[f"{name}_분_osrm"] - o[f"{name}_분_자체"], o["인구"]) for o in fin]
        R = [(o[f"{name}_분_osrm"] / o[f"{name}_분_자체"], o["인구"]) for o in fin if o[f"{name}_분_자체"] > 0]
        agree = sum(o["인구"] for o in out if (o[f"{name}_분_자체"] > 60) == (o[f"{name}_분_osrm"] > 60)) / tot["인구"]

        def s(P):
            return f"{wq(P, .5):.1f} ({wq(P, .25):.1f}–{wq(P, .75):.1f})"
        md.append(f"| {lab} | {s(A)} | {s(B)} | {s(D)} | {wq(R, .5):.2f} | {100 * agree:.2f} |")
    nonfin = [o for o in out if not math.isfinite(o["전담ICU_분_osrm"])]
    md.append("")
    md.append(f"- OSRM이 경로를 찾지 못한 읍면동: {len(nonfin)}곳 {sum(o['인구'] for o in nonfin):,}명 "
              f"({', '.join(o['읍면동코드'] for o in nonfin[:20])})")

    md += ["", "## 3. 시도별 전담 ICU 60분 미도달 (전체 인구)", "", "| 시도 | 자체 n (%) | OSRM n (%) |", "|---|---|---|"]
    by = defaultdict(list)
    for o in out:
        by[o["시도_17"]].append(o)
    order = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남",
             "경북", "경남", "제주"]
    for s_ in order:
        rows = by[s_]
        p = sum(o["인구"] for o in rows)
        a, b_ = far("전담ICU_분_자체", 60, "인구", rows), far("전담ICU_분_osrm", 60, "인구", rows)
        md.append(f"| {s_} | {a:,} ({100 * a / p:.1f}) | {b_:,} ({100 * b_ / p:.1f}) |")
    for lab, rows in (("수도권", [o for o in out if o["시도_17"] in CAPITAL]),
                      ("비수도권", [o for o in out if o["시도_17"] not in CAPITAL])):
        p = sum(o["인구"] for o in rows)
        a, b_ = far("전담ICU_분_자체", 60, "인구", rows), far("전담ICU_분_osrm", 60, "인구", rows)
        md.append(f"| {lab} | {a:,} ({100 * a / p:.1f}) | {b_:,} ({100 * b_ / p:.1f}) |")

    md += ["", "## 4. 차이가 큰 읍면동 (전담 ICU, |OSRM−자체| 상위 15)", "",
           "| 읍면동코드 | 시도 | 인구 | 자체 | OSRM | OSRM raw | OSRM 스냅(m) | 도로망연결(자체) |", "|---|---|---|---|---|---|---|---|"]
    for o in sorted(out, key=lambda o: -abs((o["전담ICU_분_osrm"] if math.isfinite(o["전담ICU_분_osrm"]) else 999)
                                            - o["전담ICU_분_자체"]))[:15]:
        md.append(f"| {o['읍면동코드']} | {o['시도_17']} | {o['인구']:,} | {o['전담ICU_분_자체']} | {o['전담ICU_분_osrm']} | "
                  f"{o['전담ICU_분_osrm_raw']} | {o['OSRM스냅_m']:,.0f} | {o['도로망연결']} |")
    md += ["", "## 로그"] + [f"- {x}" for x in log]
    (ROOT / "output/osrm_comparison.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:40]))


if __name__ == "__main__":
    main()
