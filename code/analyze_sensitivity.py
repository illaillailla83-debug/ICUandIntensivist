"""민감도 분석: 이동시간 가정과 시설 정의를 바꿔 30/60/90분 미도달 인구를 다시 계산.

시나리오
  기본: 속도 ×1.0, 스냅 20 km/h, 성인 ICU 362 / 전담 ICU 142
  S1 속도 ×0.8 (간선 이동시간 ÷0.8, 혼잡 반영)      S2 속도 ×0.67 (보수적 하한)
  S3 스냅(대표점→도로) 10 km/h
  S4 전담 엄격: 전담 + 4차 평가 1–2등급
  S5 성인 ICU ≥10병상만                             S6 전담 ICU ≥20병상만
출력: output/sensitivity_road.md, output/sensitivity_road.csv
사용: python -P -X utf8 code/analyze_sensitivity.py
"""
import csv
import pickle
import sys
import time
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_access_road as ar  # noqa: E402

ROOT, C = ar.ROOT, ar.C
CUTS = [30, 60, 90]


def main():
    t0 = time.time()
    g = pickle.load(open(ar.CACHE, "rb"))
    n = len(g["lon"])
    cnt = array("i", [0]) * (n + 1)
    for v in g["ev"]:
        cnt[v + 1] += 1
    for i in range(n):
        cnt[i + 1] += cnt[i]
    ptr, fill = array("i", cnt), array("i", cnt)
    rv = array("i", [0]) * len(g["eu"])
    rw = array("d", [0.0]) * len(g["eu"])
    for u, v, w in zip(g["eu"], g["ev"], g["ew"]):
        k = fill[v]
        rv[k], rw[k] = u, w
        fill[v] = k + 1
    snapper = ar.Snapper(g)
    fsnap = ar.FacilitySnapper(g, snapper, ptr, rv)  # 2026-11-03: 병원은 연결된 도로망에 붙임(끊긴 조각 버그 수정)
    log = [f"준비 {time.time() - t0:.0f}s"]

    icu = ar.rd(C / "icu_hospitals.csv")
    kh = {r["암호화요양기호"]: r for r in ar.rd(C / "icu_intensivist_khqa.csv") if r["암호화요양기호"]}
    fac = []
    for h in icu:
        d, node, _ = fsnap.nearest(float(h["좌표X_경도"]), float(h["좌표Y_위도"]))
        r = kh.get(h["암호화요양기호"], {})
        fac.append({"node": node, "snap_km": d, "beds": int(h["성인중환자병상수"]),
                    "int": r.get("전담전문의_있음") == "1", "grade": r.get("등급", "")})

    def run(sel, w, snap_kmh):
        src = {}
        for k, f in enumerate(fac):
            if sel(f):
                c0 = f["snap_km"] / snap_kmh * 60
                if f["node"] not in src or c0 < src[f["node"]][0]:
                    src[f["node"]] = (c0, k)
        return ar.multi_source_dijkstra(n, ptr, rv, w, src)[0]

    # 읍면동 스냅: 기본 성인 ICU 도달망 기준(시나리오 간 동일 노드 사용)
    base_all = run(lambda f: True, rw, ar.SNAP_KMH)
    reach = bytearray(1 if base_all[i] < float("inf") else 0 for i in range(n))
    pts = ar.rd(C / "emd_points.csv")
    emd = []
    for p in pts:
        d, node = snapper.nearest(float(p["경도"]), float(p["위도"]), comp_ok=reach)
        emd.append({"node": node, "snap_km": d, "pop": int(p["인구"]), "o65": int(p["65세이상"]), "o80": int(p["80세이상"])})
    tot = {c: sum(e[c] for e in emd) for c in ("pop", "o65", "o80")}

    scen = [
        ("기본", 1.0, 20.0, lambda f: True, lambda f: f["int"]),
        ("S1 속도×0.8", 0.8, 20.0, lambda f: True, lambda f: f["int"]),
        ("S2 속도×0.67", 0.67, 20.0, lambda f: True, lambda f: f["int"]),
        ("S3 스냅 10km/h", 1.0, 10.0, lambda f: True, lambda f: f["int"]),
        ("S4 전담 엄격(1–2등급)", 1.0, 20.0, lambda f: True, lambda f: f["int"] and f["grade"] in ("1", "2")),
        ("S5 성인ICU ≥10병상", 1.0, 20.0, lambda f: f["beds"] >= 10, lambda f: f["int"]),
        ("S6 전담ICU ≥20병상", 1.0, 20.0, lambda f: True, lambda f: f["int"] and f["beds"] >= 20),
    ]
    res = []
    wcache = {1.0: rw}
    for name, sp, snap, sel_all, sel_int in scen:
        if sp not in wcache:
            wcache[sp] = array("d", (x / sp for x in rw))
        w = wcache[sp]
        n_all, n_int = sum(map(sel_all, fac)), sum(map(sel_int, fac))
        for tgt, sel, nf in (("성인ICU", sel_all, n_all), ("전담ICU", sel_int, n_int)):
            dist = run(sel, w, snap)
            # access_road_emd.csv와 같은 규칙(소수 1자리 반올림 후 컷오프 비교) — 경계값 분류를 일치시킴
            times = [round(dist[e["node"]] + e["snap_km"] / snap * 60, 1) for e in emd]
            for c in CUTS:
                row = {"시나리오": name, "대상": tgt, "시설수": nf, "컷오프분": c}
                for col in ("pop", "o65", "o80"):
                    v = sum(e[col] for e, t in zip(emd, times) if t > c)
                    row[col] = v
                    row[col + "_%"] = round(100 * v / tot[col], 2)
                res.append(row)
        log.append(f"{name}: 성인ICU {n_all}, 전담 {n_int} ({time.time() - t0:.0f}s)")

    with open(ROOT / "output/sensitivity_road.csv", "w", encoding="utf-8-sig", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(res[0]))
        wr.writeheader()
        wr.writerows(res)
    md = ["# 민감도 분석 — 도로 이동시간 미도달 인구", "", "인구 2026.10. 셀: 미도달 인원 (비율).", ""]
    for c in CUTS:
        md += [f"## >{c}분", "", "| 시나리오 | 대상 | 시설 수 | 전체 | 65세 이상 | 80세 이상 |", "|---|---|---|---|---|---|"]
        for r in res:
            if r["컷오프분"] == c:
                md.append(f"| {r['시나리오']} | {r['대상']} | {r['시설수']} | {r['pop']:,} ({r['pop_%']}%) | "
                          f"{r['o65']:,} ({r['o65_%']}%) | {r['o80']:,} ({r['o80_%']}%) |")
        md.append("")
    md += ["## 로그"] + [f"- {s}" for s in log]
    (ROOT / "output/sensitivity_road.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    main()
