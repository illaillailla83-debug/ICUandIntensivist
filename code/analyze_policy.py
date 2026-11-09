"""정책 대안: 전담전문의가 없는 기존 성인 ICU에 전담전문의를 배치(강화)할 때 60분 미도달 인구 감소량.

대안
  A. 공공병원 강화: 설립구분 공립·국립·특수법인 중 전담 미배치 ICU 전부
  B. 지방의료원 강화: 이름에 '의료원'이 들어간 전담 미배치 ICU 전부
  C. 탐욕 최적: 후보(전담 미배치 ICU 전부) 중 미도달 인구(전체 또는 65세 이상)를 가장 많이 줄이는 곳부터 k=1..20
  상한: 모든 ICU 강화 = 성인 ICU 기준 미도달 인구
방법: analyze_access_road.py와 같은 도로망. 후보마다 역방향 Dijkstra를 컷오프(분)까지만 수행해 도달 읍면동을 구함.
출력: output/policy_road.md, output/policy_road.csv
사용: python -P -X utf8 code/analyze_policy.py [컷오프분=60]
"""
import csv
import heapq
import pickle
import sys
import time
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import analyze_access_road as ar  # noqa: E402

CUT = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
ROOT, C = ar.ROOT, ar.C


def bounded(n, ptr, rv, rw, src, c0, cut, targets):
    """src에서 역방향으로 cut 분까지 탐색. targets(node→[emd idx])에 닿은 시간 반환."""
    dist = {src: c0}
    pq = [(c0, src)]
    hit = {}
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18):
            continue
        if u in targets:
            hit[u] = d
        for k in range(ptr[u], ptr[u + 1]):
            v = rv[k]
            nd = d + rw[k]
            if nd <= cut and nd < dist.get(v, 1e18):
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return hit


def main():
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

    icu = ar.rd(C / "icu_hospitals.csv")
    ints = {r["암호화요양기호"] for r in ar.rd(C / "icu_intensivist_khqa.csv") if r["전담전문의_있음"] == "1"}
    acc = ar.rd(C / "access_road_emd.csv")
    pts = {p["읍면동코드"]: p for p in ar.rd(C / "emd_points.csv")}

    # 읍면동: 현재 전담 ICU 시간, 스냅 노드(시설과 연결된 도로망), 스냅 시간
    emd = []
    reach_nodes = None
    for a in acc:
        p = pts[a["읍면동코드"]]
        emd.append({"code": a["읍면동코드"], "sido": a["시도_17"], "pop": int(a["인구"]), "o65": int(a["65세이상"]),
                    "t": float(a["전담ICU_분"]), "x": float(p["경도"]), "y": float(p["위도"]),
                    "snap_min": float(a["스냅_km"]) / ar.SNAP_KMH * 60})
    # 스냅 노드는 access_road와 같은 방식(연결된 망)으로 다시 구함: 거리 같은 노드 선택
    t0 = time.time()
    targets = {}
    for i, e in enumerate(emd):
        if e["t"] <= CUT:
            continue  # 이미 도달 → 후보 효과 계산 불필요
        if acc[i]["도로망연결"] != "Y":  # 미연결 섬: 시간 신뢰 불가 → 감소 효과에서 제외(보수적)
            continue
        # access_road와 같은 연결망 노드 사용 (이전: 무조건 최근접 노드 → 끊긴 도로 조각에 붙은 읍면동이 빠졌음)
        targets.setdefault(int(acc[i]["스냅노드"]), []).append(i)
    unreached = [i for i, e in enumerate(emd) if e["t"] > CUT]
    log = [f"미도달 읍면동 {len(unreached)}개, 후보 계산 대상 노드 {len(targets)} (스냅 {time.time() - t0:.0f}s)"]

    cands = []
    t0 = time.time()
    for h in icu:
        if h["암호화요양기호"] in ints:
            continue
        d, node, _ = fsnap.nearest(float(h["좌표X_경도"]), float(h["좌표Y_위도"]))
        hit = bounded(n, ptr, rv, rw, node, d / ar.SNAP_KMH * 60, CUT, targets)
        cover = set()
        for nd, tm in hit.items():
            for i in targets[nd]:
                if tm + emd[i]["snap_min"] <= CUT:
                    cover.add(i)
        cands.append({"key": h["암호화요양기호"], "name": h["요양기관명"], "sido": h["시도_17"], "sgg": h["시군구코드명"],
                      "type": h["종별코드명"],
                      "own": h["설립구분코드명"], "beds": int(h["성인중환자병상수"]), "cover": cover})
    log.append(f"후보 {len(cands)}곳 탐색 {time.time() - t0:.0f}s")

    base_pop = sum(emd[i]["pop"] for i in unreached)
    base_o65 = sum(emd[i]["o65"] for i in unreached)

    def effect(cov):
        return sum(emd[i]["pop"] for i in cov), sum(emd[i]["o65"] for i in cov)

    resp = {r["암호화요양기호"]: r["구분"] for r in ar.rd(C / "responsible_hospitals_matched.csv") if r["암호화요양기호"]}
    rows = [("현재", "", 0, base_pop, base_o65)]
    for label, sel in [("A 공공병원(공립·국립·특수법인) 전부", lambda c: c["own"] in ("공립", "국립", "특수법인")),
                       ("B 지방의료원 전부", lambda c: "의료원" in c["name"]),
                       ("D 책임의료기관(2024.3 지정) 전부", lambda c: c["key"] in resp),
                       ("D' 책임의료기관 중 ICU ≥10병상", lambda c: c["key"] in resp and c["beds"] >= 10),
                       ("상한: 모든 ICU 강화", lambda c: True)]:
        chosen = [c for c in cands if sel(c)]
        cov = set().union(*[c["cover"] for c in chosen]) if chosen else set()
        dp, do = effect(cov)
        rows.append((label, f"{len(chosen)}곳", len(chosen), base_pop - dp, base_o65 - do))

    greedy = {}
    for obj, minbed in (("pop", 0), ("o65", 0), ("o65", 10), ("o65", 20)):
        pool = [c for c in cands if c["beds"] >= minbed]
        covered, seq = set(), []
        for k in range(1, 21):
            best = max(pool, key=lambda c: sum(emd[i][obj] for i in c["cover"] - covered))
            gain = sum(emd[i][obj] for i in best["cover"] - covered)
            if gain == 0:
                break
            covered |= best["cover"]
            dp, do = effect(covered)
            seq.append((k, best, base_pop - dp, base_o65 - do))
        greedy[(obj, minbed)] = seq

    with open(ROOT / "output/policy_road.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["대안", "목표", "k", "추가기관", "시도", "미도달인구", "미도달65세이상"])
        for label, desc, k, p_, o_ in rows:
            w.writerow([label, "", k, desc, "", p_, o_])
        for (obj, mb), seq in greedy.items():
            for k, c, p_, o_ in seq:
                w.writerow([f"C 탐욕최적(ICU≥{mb}병상)", "전체인구" if obj == "pop" else "65세이상", k, c["name"], c["sido"],
                            p_, o_])

    md = [f"# 정책 대안 — 전담전문의 ICU {CUT:g}분 미도달 인구 (도로 이동시간)", "",
          "전담 미배치 기존 ICU에 전담전문의를 배치한다고 가정. 인구 2026.10. 미연결 섬은 감소 효과 계산에서 제외(보수적).", "",
          "| 대안 | 기관 수 | 미도달 인구 | 감소 | 미도달 65세 이상 | 감소 |", "|---|---|---|---|---|---|"]
    for label, desc, k, p_, o_ in rows:
        md.append(f"| {label} | {desc or '-'} | {p_:,} | {base_pop - p_:,} ({(base_pop - p_) / base_pop:.0%}) | "
                  f"{o_:,} | {base_o65 - o_:,} ({(base_o65 - o_) / base_o65:.0%}) |")
    for (obj, mb), seq in greedy.items():
        md += ["", f"## C 탐욕 최적 (목표: {'전체 인구' if obj == 'pop' else '65세 이상'} 미도달 최소화"
                   f"{f', 후보 ICU ≥{mb}병상' if mb else ''})", "",
               "| k | 추가 기관 | 시도 시군구 | 종별·설립 | ICU병상 | 미도달 인구 | 미도달 65+ |", "|---|---|---|---|---|---|---|"]
        for k, c, p_, o_ in seq:
            md.append(f"| {k} | {c['name']} | {c['sido']} {c['sgg']} | {c['type']}·{c['own']} | {c['beds']} | "
                      f"{p_:,} ({p_ / base_pop:.0%}) | {o_:,} ({o_ / base_o65:.0%}) |")
    md += ["", "## 로그"] + [f"- {s}" for s in log]
    (ROOT / "output/policy_road.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    main()
