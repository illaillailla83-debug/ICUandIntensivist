"""도로 이동시간 접근성 (OSM 도로망 + 다중출발 Dijkstra). OSRM을 쓸 수 없을 때의 대체 구현.

방법 (OSRM car.lua 기본값을 단순화해 따름; 회전 페널티·신호·혼잡은 반영 안 함):
  - 자동차 통행 도로: highway ∈ SPEED, access/motor_vehicle/motorcar ∈ {no, private} 제외, area=yes 제외
  - 속도: maxspeed 태그가 있으면 maxspeed×0.8, 없으면 도로 등급 기본값(SPEED)
  - 일방통행: oneway=yes/1/true/-1, motorway·roundabout은 기본 일방
  - 카페리: route=ferry 이고 자동차 불가 표시가 없는 경로. duration 태그가 있으면 그 시간, 없으면 20 km/h
    (배 대기·운항시간표는 반영 안 함 → 섬 접근성은 과소추정)
  - 출발점·도착점 연결: 대표점/병원 좌표에서 가장 가까운 일반도로 노드(고속도로·연결로 제외)까지 직선거리를 20 km/h로 더함
  - 각 읍면동에서 가장 가까운 시설까지의 시간 = 역방향 그래프에서 시설 노드들을 출발점으로 한 Dijkstra
출력: data/clean/access_road_emd.csv, output/access_road_draft.md, 그래프 캐시 data/clean/road_graph_osm.pkl
사용: python -P -X utf8 code/analyze_access_road.py   (-P: 사용자 site-packages의 osmium 사용)
"""
import csv
import heapq
import math
import pickle
import re
import sys
import time
from array import array
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
PBF = ROOT / "data/raw/osm_2026-11-03/south-korea-latest.osm.pbf"
CACHE = C / "road_graph_osm.pkl"
SPEED = {"motorway": 90, "motorway_link": 45, "trunk": 85, "trunk_link": 40, "primary": 65, "primary_link": 30,
         "secondary": 55, "secondary_link": 25, "tertiary": 40, "tertiary_link": 20, "unclassified": 25,
         "residential": 25, "living_street": 10, "service": 15, "road": 25}
NO_SNAP = {"motorway", "motorway_link", "trunk_link"}
FERRY_KMH = 20.0
SNAP_KMH = 20.0
CUTS = [30, 60, 90]
ORDER = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남",
         "경북", "경남", "제주"]


def hav(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def parse_maxspeed(v):
    m = re.match(r"\s*(\d+(?:\.\d+)?)\s*(mph)?", v or "")
    if not m:
        return None
    s = float(m.group(1)) * (1.609 if m.group(2) else 1)
    return s if 5 <= s <= 150 else None


def parse_duration(v):
    """OSM duration: 'HH:MM', 'HH:MM:SS', 'MM', ISO 'PT1H30M' → 분."""
    if not v:
        return None
    v = v.strip()
    m = re.fullmatch(r"(\d+):(\d{1,2})(?::(\d{1,2}))?", v)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3) or 0) / 60
    if v.isdigit():
        return float(v)
    m = re.fullmatch(r"P?T?(?:(\d+)H)?(?:(\d+)M)?", v, re.I)
    if m and (m.group(1) or m.group(2)):
        return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
    return None


def build_graph():
    import osmium  # 사용자 site-packages

    class H(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.idx = {}
            self.lon, self.lat = array("d"), array("d")
            self.snap = bytearray()
            self.eu, self.ev, self.ew = array("i"), array("i"), array("f")  # 정방향 간선(분)
            self.stat = defaultdict(int)

        def nid(self, n, snappable):
            i = self.idx.get(n.ref)
            if i is None:
                i = len(self.lon)
                self.idx[n.ref] = i
                self.lon.append(n.lon)
                self.lat.append(n.lat)
                self.snap.append(1 if snappable else 0)
            elif snappable:
                self.snap[i] = 1
            return i

        def way(self, w):
            t = w.tags
            hw, route = t.get("highway"), t.get("route")
            acc = {t.get(k) for k in ("access", "motor_vehicle", "motorcar", "vehicle")}
            if route == "ferry":
                if acc & {"no", "private"} or t.get("motorcar") == "no":
                    return
                kind = "ferry"
            elif hw in SPEED:
                if acc & {"no", "private"} or t.get("area") == "yes":
                    return
                kind = hw
            else:
                return
            try:
                nodes = [n for n in w.nodes if n.location.valid()]
            except osmium.InvalidLocationError:
                return
            if len(nodes) < 2:
                return
            ow = t.get("oneway", "")
            fwd, bwd = True, True
            if ow in ("yes", "1", "true") or (kind in ("motorway",) and ow != "no") or t.get("junction") == "roundabout":
                bwd = False
            elif ow == "-1":
                fwd = False
            snappable = kind not in NO_SNAP and kind != "ferry"
            ids = [self.nid(n, snappable) for n in nodes]
            seg = [hav(a.lon, a.lat, b.lon, b.lat) for a, b in zip(nodes, nodes[1:])]
            if kind == "ferry":
                dur = parse_duration(t.get("duration"))
                tot = sum(seg)
                mins = [(dur * s / tot if dur and tot else s / FERRY_KMH * 60) for s in seg]
                self.stat["ferry_dur" if dur else "ferry_nodur"] += 1
            else:
                kmh = parse_maxspeed(t.get("maxspeed"))
                kmh = kmh * 0.8 if kmh else SPEED[kind]
                mins = [s / kmh * 60 for s in seg]
            self.stat[kind] += 1
            for a, b, m in zip(ids, ids[1:], mins):
                if fwd:
                    self.eu.append(a); self.ev.append(b); self.ew.append(m)
                if bwd:
                    self.eu.append(b); self.ev.append(a); self.ew.append(m)

    h = H()
    t0 = time.time()
    h.apply_file(str(PBF), locations=True, idx="flex_mem")
    g = {"lon": h.lon, "lat": h.lat, "snap": bytes(h.snap), "eu": h.eu, "ev": h.ev, "ew": h.ew,
         "stat": dict(h.stat), "build_sec": time.time() - t0}
    with open(CACHE, "wb") as f:
        pickle.dump(g, f, protocol=pickle.HIGHEST_PROTOCOL)
    return g


class Snapper:
    """0.01° 격자 최근접 노드 탐색 (snappable 노드만)."""

    def __init__(self, g, cell=0.01):
        self.g, self.cell = g, cell
        self.grid = defaultdict(list)
        lon, lat, snap = g["lon"], g["lat"], g["snap"]
        for i in range(len(lon)):
            if snap[i]:
                self.grid[(int(lon[i] / cell), int(lat[i] / cell))].append(i)

    def nearest(self, x, y, comp_ok=None):
        cx, cy = int(x / self.cell), int(y / self.cell)
        best = (float("inf"), -1)
        for r in range(0, 400):  # 최대 약 4° — 연결 안 된 섬에서도 본토 노드를 찾도록
            for gx in range(cx - r, cx + r + 1):
                for gy in range(cy - r, cy + r + 1):
                    if max(abs(gx - cx), abs(gy - cy)) != r:
                        continue
                    for i in self.grid.get((gx, gy), ()):
                        if comp_ok is not None and not comp_ok[i]:
                            continue
                        d = hav(x, y, self.g["lon"][i], self.g["lat"][i])
                        if d < best[0]:
                            best = (d, i)
            # 현재 링 바깥은 최소 r*cell*~88km 떨어짐 → 충분히 찾았으면 종료
            if best[1] >= 0 and best[0] < r * self.cell * 88:
                break
        return best


class FacilitySnapper:
    """병원 좌표 → 가장 가까운 '양방향으로 충분히 큰 도로망'의 노드. (2026-11-03 버그 수정)

    이전에는 병원을 그냥 가장 가까운 노드에 붙였음. 그 노드가 끊긴 조각(병원 내부 통로, 출입제한 도로로만
    이어진 길 등)이면 역방향 탐색이 밖으로 못 나가 그 병원에 아무도 도달하지 못함
    → OSRM 비교에서 발견: 전담 ICU 3곳(명지병원 제천, 조선대병원, 인천세종병원), 성인 ICU 10곳이 어떤 읍면동의 최근접으로도 안 잡힘.
    기준: 그 노드에서 정방향·역방향 BFS가 각각 MIN_REACH개 이상 노드에 닿을 것(섬 안의 도로망도 인정됨).
    """
    MIN_REACH = 2000

    def __init__(self, g, snapper, rptr, rv):
        n = len(g["lon"])
        cnt = array("i", [0]) * (n + 1)
        for u in g["eu"]:
            cnt[u + 1] += 1
        for i in range(n):
            cnt[i + 1] += cnt[i]
        self.fptr, fill = array("i", cnt), array("i", cnt)
        self.fv = array("i", [0]) * len(g["eu"])
        for u, v in zip(g["eu"], g["ev"]):
            self.fv[fill[u]] = v
            fill[u] += 1
        self.rptr, self.rv, self.s, self.cache = rptr, rv, snapper, {}

    def _reach(self, s, ptr, adj):
        seen, stack = {s}, [s]
        while stack and len(seen) < self.MIN_REACH:
            u = stack.pop()
            for k in range(ptr[u], ptr[u + 1]):
                v = adj[k]
                if v not in seen:
                    seen.add(v)
                    stack.append(v)
        return len(seen) >= self.MIN_REACH

    def ok(self, i):
        if i not in self.cache:
            self.cache[i] = self._reach(i, self.fptr, self.fv) and self._reach(i, self.rptr, self.rv)
        return self.cache[i]

    def nearest(self, x, y):
        """반환: (거리 km, 노드, 단순 최근접 대비 바뀌었는지)."""
        s, cell = self.s, self.s.cell
        cx, cy = int(x / cell), int(y / cell)
        tested, cand = set(), []
        d0 = None
        for r in range(0, 400):
            for gx in range(cx - r, cx + r + 1):
                for gy in range(cy - r, cy + r + 1):
                    if max(abs(gx - cx), abs(gy - cy)) == r:
                        cand += [(hav(x, y, s.g["lon"][i], s.g["lat"][i]), i) for i in s.grid.get((gx, gy), ())]
            cand.sort()
            if d0 is None and cand:
                d0 = cand[0][0]
            bound = r * cell * 88  # 이 링 바깥 노드는 최소 이만큼 떨어짐
            for d, i in cand:
                if d >= bound:
                    break
                if i not in tested:
                    tested.add(i)
                    if self.ok(i):
                        return d, i, d > d0
        raise RuntimeError("no connected node")


def multi_source_dijkstra(n, radj_ptr, radj_v, radj_w, sources):
    """sources: {node: 시작비용(분)}. 역방향 그래프에서 시설→모든 노드 최소시간과 시설 라벨."""
    # double 필수: float32로 저장하면 pop한 d(double) > dist[u](반올림값)가 되어 노드가 건너뛰어짐 (1차 실행 버그)
    dist = array("d", [float("inf")]) * n
    lab = array("i", [-1]) * n
    pq = []
    for s, (c0, l) in sources.items():
        if c0 < dist[s]:
            dist[s], lab[s] = c0, l
            heapq.heappush(pq, (c0, s))
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        lu = lab[u]
        for k in range(radj_ptr[u], radj_ptr[u + 1]):
            v = radj_v[k]
            nd = d + radj_w[k]
            if nd < dist[v]:
                dist[v], lab[v] = nd, lu
                heapq.heappush(pq, (nd, v))
    return dist, lab


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def main():
    log = []
    if CACHE.exists() and CACHE.stat().st_mtime > PBF.stat().st_mtime:
        g = pickle.load(open(CACHE, "rb"))
        log.append("그래프 캐시 사용")
    else:
        g = build_graph()
    n = len(g["lon"])
    log.append(f"노드 {n:,}, 방향간선 {len(g['eu']):,}, 빌드 {g['build_sec']:.0f}s, 도로/항로 way 수 {g['stat']}")

    # 역방향 CSR: 간선 u→v 를 v에서 u로 탐색
    t0 = time.time()
    cnt = array("i", [0]) * (n + 1)
    for v in g["ev"]:
        cnt[v + 1] += 1
    for i in range(n):
        cnt[i + 1] += cnt[i]
    ptr = array("i", cnt)
    fill = array("i", cnt)
    rv = array("i", [0]) * len(g["eu"])
    rw = array("f", [0.0]) * len(g["eu"])
    for u, v, w in zip(g["eu"], g["ev"], g["ew"]):
        k = fill[v]
        rv[k], rw[k] = u, w
        fill[v] = k + 1
    log.append(f"역방향 CSR {time.time() - t0:.0f}s")

    snapper = Snapper(g)
    icu = rd(C / "icu_hospitals.csv")
    ints = {r["암호화요양기호"] for r in rd(C / "icu_intensivist_khqa.csv") if r["전담전문의_있음"] == "1"}
    fsnap = FacilitySnapper(g, snapper, ptr, rv)
    fac = []
    for k, h in enumerate(icu):
        d, node, moved = fsnap.nearest(float(h["좌표X_경도"]), float(h["좌표Y_위도"]))
        fac.append({"name": h["요양기관명"], "node": node, "snap_km": d, "int": h["암호화요양기호"] in ints, "moved": moved})
    log.append(f"병원 스냅 거리: 최대 {max(f['snap_km'] for f in fac):.2f} km, >0.5km {sum(f['snap_km'] > 0.5 for f in fac)}곳")
    log.append("끊긴 도로 조각을 피해 다시 붙인 병원 " + str(sum(f["moved"] for f in fac)) + "곳: "
               + ", ".join(f"{f['name']}({f['snap_km'] * 1000:.0f}m)" for f in fac if f["moved"]))

    def run(sel):
        src = {}
        for k, f in enumerate(fac):
            if sel(f):
                c0 = f["snap_km"] / SNAP_KMH * 60
                if f["node"] not in src or c0 < src[f["node"]][0]:
                    src[f["node"]] = (c0, k)
        return multi_source_dijkstra(n, ptr, rv, rw, src)

    t0 = time.time()
    dist_all, lab_all = run(lambda f: True)
    dist_int, lab_int = run(lambda f: f["int"])
    log.append(f"Dijkstra 2회 {time.time() - t0:.0f}s")
    reach = bytearray(1 if dist_all[i] < float("inf") else 0 for i in range(n))

    sido17 = {r["KOSIS코드"]: r["시도_17"] for r in rd(C / "sgg_crosswalk.csv")}
    pts = rd(C / "emd_points.csv")
    out = []
    for p in pts:
        x, y = float(p["경도"]), float(p["위도"])
        d, node = snapper.nearest(x, y, comp_ok=reach)  # 시설에 닿는 도로망에 스냅
        d0, node0 = snapper.nearest(x, y)
        snap_min = d / SNAP_KMH * 60
        ta = dist_all[node] + snap_min
        ti = dist_int[node] + snap_min
        out.append({"읍면동코드": p["읍면동코드"], "읍면동": p["읍면동"], "시군구코드_KOSIS": p["시군구코드_KOSIS"],
                    "시도_17": sido17.get(p["시군구코드_KOSIS"], ""), "인구": int(p["인구"]),
                    "65세이상": int(p["65세이상"]), "80세이상": int(p["80세이상"]),
                    "스냅_km": round(d, 3), "최근접도로_km(연결무관)": round(d0, 3),
                    # 시설과 이어진 도로망이 가장 가까운 도로보다 1km 넘게 멀면 = 연결 안 된 섬(항로 누락 등) → 시간 신뢰 불가
                    "도로망연결": "N" if d - d0 > 1.0 else "Y",
                    "스냅노드": node,  # 시설과 연결된 도로망 노드 — 정책·2SFCA 분석이 같은 노드를 쓰도록 저장
                    "ICU_분": round(ta, 1), "ICU": fac[lab_all[node]]["name"],
                    "전담ICU_분": round(ti, 1), "전담ICU": fac[lab_int[node]]["name"]})
    with open(C / "access_road_emd.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    def share(rows, col, tcol, cut):
        tot = sum(r[col] for r in rows)
        far = sum(r[col] for r in rows if r[tcol] > cut)
        return far, (far / tot if tot else 0)

    def wmed(rows, tcol, col="인구"):
        s = sorted(rows, key=lambda r: r[tcol])
        half, acc = sum(r[col] for r in s) / 2, 0
        for r in s:
            acc += r[col]
            if acc >= half:
                return r[tcol]

    md = ["# 접근성 — 도로 이동시간 (OSM 도로망 + Dijkstra, OSRM 대체 구현, 초안)", "",
          "자유주행(혼잡·신호·회전 미반영) 가정이라 실제보다 짧게 나올 수 있음. 카페리는 운항 대기 미반영.", "",
          "## 전국: 이동시간 컷오프를 넘는 인구", "",
          "| 대상 | 컷오프 | 전체 인구 | % | 65세 이상 | % | 80세 이상 | % |", "|---|---|---|---|---|---|---|---|"]
    for lab, tcol in [("성인 ICU", "ICU_분"), ("전담전문의 ICU", "전담ICU_분")]:
        for c in CUTS:
            cells = []
            for col in ("인구", "65세이상", "80세이상"):
                k, s = share(out, col, tcol, c)
                cells += [f"{k:,}", f"{s:.1%}"]
            md.append(f"| {lab} | >{c}분 | " + " | ".join(cells) + " |")
    md += ["", f"- 인구가중 중앙 이동시간: 성인 ICU {wmed(out, 'ICU_분')}분, 전담전문의 ICU {wmed(out, '전담ICU_분')}분",
           f"- 65세 이상 가중 중앙: 성인 ICU {wmed(out, 'ICU_분', '65세이상')}분, 전담 {wmed(out, '전담ICU_분', '65세이상')}분", "",
           "## 시도별", "",
           "| 시도 | 인구 | 중앙 이동시간(전담) 분 | 전담 >60분 전체 | 전담 >60분 65+ | 전담 >30분 전체 | 성인ICU >60분 전체 |",
           "|---|---|---|---|---|---|---|"]
    by = defaultdict(list)
    for o in out:
        by[o["시도_17"]].append(o)
    for s in ORDER:
        rows = by[s]
        md.append(f"| {s} | {sum(r['인구'] for r in rows):,} | {wmed(rows, '전담ICU_분')} | "
                  f"{share(rows, '인구', '전담ICU_분', 60)[1]:.1%} | {share(rows, '65세이상', '전담ICU_분', 60)[1]:.1%} | "
                  f"{share(rows, '인구', '전담ICU_분', 30)[1]:.1%} | {share(rows, '인구', 'ICU_분', 60)[1]:.1%} |")
    far = sorted(out, key=lambda o: -o["전담ICU_분"])[:15]
    big_snap = [o for o in out if o["스냅_km"] > 2]
    md += ["", "## 전담전문의 ICU까지 가장 먼 읍면동 15곳", ""] + \
          [f"- {o['시도_17']} {o['읍면동']} ({o['인구']:,}명): {o['전담ICU_분']}분 → {o['전담ICU']}" for o in far]
    unc = [o for o in out if o["도로망연결"] == "N"]
    md += ["", "## 도로망 미연결 읍면동 (섬, 시간 신뢰 불가 — 표에는 계산값 그대로 포함)",
           f"- {len(unc)}개, 인구 {sum(o['인구'] for o in unc):,}명, 65세 이상 {sum(o['65세이상'] for o in unc):,}명: " +
           ", ".join(f"{o['시도_17']} {o['읍면동']}({o['인구']:,}명, {o['전담ICU_분']}분)" for o in unc)]
    md += ["", "## 점검",f"- 스냅 거리 >2 km 읍면동 {len(big_snap)}개 (인구 {sum(o['인구'] for o in big_snap):,}): " +
           ", ".join(f"{o['읍면동']}({o['스냅_km']}km, 연결무관 {o['최근접도로_km(연결무관)']}km)" for o in big_snap[:30])]
    md += ["", "## 로그"] + [f"- {s}" for s in log]
    (ROOT / "output/access_road_draft.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    main()
