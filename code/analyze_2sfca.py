"""2SFCA(two-step floating catchment area): 도로 이동시간 60분 집수구역, 공급=성인 ICU 병상, 수요=20세 이상 인구(기본)·65세 이상(대안).

1단계: 시설 j의 병상/집수구역 수요  R_j = S_j / Σ_{t_ij ≤ d0} P_i
2단계: 읍면동 i의 접근성      A_i = Σ_{t_ij ≤ d0} R_j  (× 10만 → '수요 10만 명당 도달 가능 병상')
시설 집합: 성인 ICU 전체(362) / 전담전문의 ICU(142). 미연결 섬은 기본 스냅 그대로(시간이 길어 대부분 0).
출력: data/clean/access_2sfca_emd.csv, output/access_2sfca.md
사용: python -P -X utf8 code/analyze_2sfca.py [d0분=60]
"""
import csv
import pickle
import sys
import time
from array import array
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_access_road as ar  # noqa: E402
from analyze_policy import bounded  # noqa: E402

D0 = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
ROOT, C = ar.ROOT, ar.C
ORDER = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남",
         "경북", "경남", "제주"]


def gini(vals, w):
    s = sorted(zip(vals, w))
    W = sum(w)
    mu = sum(v * x for v, x in s) / W
    acc, lor, prev = 0.0, 0.0, 0.0
    area = 0.0
    for v, x in s:
        acc += x
        lor_new = lor + v * x / (mu * W)
        area += (x / W) * (lor + lor_new) / 2
        lor = lor_new
    return 1 - 2 * area


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

    acc = {r["읍면동코드"]: r for r in ar.rd(C / "access_road_emd.csv")}
    pts = ar.rd(C / "emd_points.csv")
    ages = [k for k in pts[0] if k.endswith("세") or k == "100+"]
    emd, targets = [], defaultdict(list)
    for i, p in enumerate(pts):
        a = acc[p["읍면동코드"]]
        node = int(a["스냅노드"])  # access_road와 같은 연결망 노드
        snap_min = float(a["스냅_km"]) / ar.SNAP_KMH * 60
        emd.append({"code": p["읍면동코드"], "sido": a["시도_17"], "pop": int(p["인구"]),
                    "adult": sum(int(p[k]) for k in ages[4:]), "o65": int(p["65세이상"]), "snap": snap_min,
                    "linked": a["도로망연결"] == "Y"})
        if a["도로망연결"] == "Y":
            targets[node].append(i)

    icu = ar.rd(C / "icu_hospitals.csv")
    ints = {r["암호화요양기호"] for r in ar.rd(C / "icu_intensivist_khqa.csv") if r["전담전문의_있음"] == "1"}
    links = []  # (fac idx, emd idx)
    for j, h in enumerate(icu):
        d, node, _ = fsnap.nearest(float(h["좌표X_경도"]), float(h["좌표Y_위도"]))
        hit = bounded(n, ptr, rv, rw, node, d / ar.SNAP_KMH * 60, D0, targets)
        for nd, tm in hit.items():
            for i in targets[nd]:
                if tm + emd[i]["snap"] <= D0:
                    links.append((j, i))
    log = [f"시설–읍면동 연결(≤{D0:g}분) {len(links):,}쌍, {time.time() - t0:.0f}s"]

    res = {}
    for setname, sel in (("ICU", lambda h: True), ("전담ICU", lambda h: h["암호화요양기호"] in ints)):
        for dem in ("adult", "o65"):
            D = defaultdict(float)
            for j, i in links:
                if sel(icu[j]):
                    D[j] += emd[i][dem]
            R = {j: int(icu[j]["성인중환자병상수"]) / D[j] for j in D if D[j] > 0}
            A = [0.0] * len(emd)
            for j, i in links:
                if j in R:
                    A[i] += R[j]
            res[(setname, dem)] = [a * 1e5 for a in A]

    with open(C / "access_2sfca_emd.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["읍면동코드", "시도_17", "인구", "20세이상", "65세이상"] + [f"A_{s}_{d}" for s, d in res])
        for i, e in enumerate(emd):
            w.writerow([e["code"], e["sido"], e["pop"], e["adult"], e["o65"]] + [round(res[k][i], 3) for k in res])

    md = [f"# 2SFCA — 도로 {D0:g}분 집수구역 (수요 10만 명당 도달 가능 성인 ICU 병상)", "",
          "| 공급 | 수요 | 인구가중 평균 | 지니(읍면동, 수요가중) | A=0 수요 비율 |", "|---|---|---|---|---|"]
    for (s, d), A in res.items():
        wts = [e[d] for e in emd]
        mean = sum(a * x for a, x in zip(A, wts)) / sum(wts)
        zero = sum(x for a, x in zip(A, wts) if a == 0) / sum(wts)
        md.append(f"| {s} | {'20세 이상' if d == 'adult' else '65세 이상'} | {mean:.1f} | {gini(A, wts):.3f} | {zero:.1%} |")
    md += ["", "## 시도별 (수요 20세 이상, 수요가중 평균)", "", "| 시도 | 성인 ICU | 전담 ICU | 전담/성인 |", "|---|---|---|---|"]
    for s in ORDER:
        idx = [i for i, e in enumerate(emd) if e["sido"] == s]
        W = sum(emd[i]["adult"] for i in idx)
        a1 = sum(res[("ICU", "adult")][i] * emd[i]["adult"] for i in idx) / W
        a2 = sum(res[("전담ICU", "adult")][i] * emd[i]["adult"] for i in idx) / W
        md.append(f"| {s} | {a1:.1f} | {a2:.1f} | {a2 / a1:.0%} |")
    md += ["", "- 주의: 이 지표는 집수구역 경계(60분) 안의 병상을 이웃 지역과 나눠 씀. 시도 경계를 넘는 이용이 반영됨.",
           "", "## 로그"] + [f"- {s}" for s in log]
    (ROOT / "output/access_2sfca.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[2:8] + log))


if __name__ == "__main__":
    main()
