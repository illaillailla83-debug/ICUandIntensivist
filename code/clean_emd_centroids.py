"""읍면동(행정동) 대표점 생성 + KOSIS 주민등록 읍면동(2026.10)과 매칭.

대표점: 가장 큰 폴리곤(외곽 링)의 면적 중심. 중심이 폴리곤 밖이면(오목한 모양) 중심 위도의 수평선과
       폴리곤이 만나는 가장 긴 구간의 중점을 씀. 인구가중 중심이 아님(한계).
매칭: geojson adm_cd2(10자리 행정동코드) = KOSIS 읍면동 코드. 안 맞는 KOSIS 읍면동은 이름(시도·시군구·읍면동)으로 재시도,
     그래도 없으면 같은 시군구 경계 대표점들의 평균으로 대체하고 표시.

입력: data/raw/admdongkor_ver20261001/HangJeongDong_ver20261001.geojson, data/clean/pop_resident_202610.csv
출력: data/clean/emd_points.csv, output/emd_points_qc.md
사용: python -I -X utf8 code/clean_emd_centroids.py
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GJ = ROOT / "data/raw/admdongkor_ver20261001/HangJeongDong_ver20261001.geojson"
POP = ROOT / "data/clean/pop_resident_202610.csv"


def ring_area_centroid(ring):
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        c = x1 * y2 - x2 * y1
        a += c
        cx += (x1 + x2) * c
        cy += (y1 + y2) * c
    a /= 2
    if a == 0:
        return 0.0, ring[0][0], ring[0][1]
    return abs(a), cx / (6 * a), cy / (6 * a)


def inside(x, y, rings):
    """짝홀 규칙 (외곽+구멍 링 모두)."""
    hit = False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
                hit = not hit
    return hit


def scan_point(y, rings):
    xs = []
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y):
                xs.append((x2 - x1) * (y - y1) / (y2 - y1) + x1)
    xs.sort()
    segs = [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]
    a, b = max(segs, key=lambda s: s[1] - s[0])
    return (a + b) / 2, y


def rep_point(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    best = max(polys, key=lambda p: ring_area_centroid([tuple(c[:2]) for c in p[0]])[0])
    rings = [[tuple(c[:2]) for c in r] for r in best]
    _, x, y = ring_area_centroid(rings[0])
    if inside(x, y, rings):
        return x, y, "centroid"
    x, y = scan_point(y, rings)
    return x, y, "scanline"


def main():
    gj = json.loads(GJ.read_text(encoding="utf-8"))
    pts = {}
    for f in gj["features"]:
        p = f["properties"]
        x, y, how = rep_point(f["geometry"])
        pts[p["adm_cd2"]] = {"x": x, "y": y, "how": how, "nm": p["adm_nm"], "sgg": p["sgg"]}
    by_name = {v["nm"].replace(" ", ""): k for k, v in pts.items()}

    pop = list(csv.DictReader(open(POP, encoding="utf-8-sig")))
    names = {r["코드"]: r["이름"] for r in pop}
    emd = [r for r in pop if r["수준"] == "읍면동" and int(r["계"]) > 0]
    out, used, qc_name, qc_fallback = [], set(), [], []
    sgg_pts = defaultdict(list)
    for k, v in pts.items():
        sgg_pts[v["sgg"]].append((v["x"], v["y"]))
    for r in emd:
        code = r["코드"]
        sgg = r["읍면동_소속시군구"]
        src = "code"
        if code in pts:
            g = pts[code]
        else:
            # 이름 매칭: 시도명 + (상위 시) + 시군구/구 + 읍면동
            parent = next((p for p in pop if p["코드"] == sgg), None)
            chain = [r["시도명"]]
            if parent and parent["수준"] == "구":
                chain.append(parent["상위명"])
            chain += [names.get(sgg, ""), r["이름"]]
            key = "".join(chain).replace(" ", "")
            stem = r["이름"].rstrip("0123456789동").replace("제", "")
            sib = [v for v in pts.values() if v["sgg"] == sgg and
                   v["nm"].split()[-1].rstrip("0123456789동").replace("제", "") == stem] if stem else []
            if key in by_name:
                g, src = pts[by_name[key]], "name"
                qc_name.append(f"{r['이름']}({code}) → {g['nm']}")
            elif code[:7] + "000" in pts:
                # 출장소: 상위 읍면(코드 앞 7자리 + 000)의 대표점 사용
                g, src = pts[code[:7] + "000"], "parent_emd"
                qc_name.append(f"{r['이름']}({code}) → 상위 {g['nm']}")
            elif len(sib) == 1:
                # 분동된 신설 동(예: 고덕1동·2동): 경계판에 있는 원래 동의 대표점 사용
                g, src = sib[0], "split_dong"
                qc_name.append(f"{r['이름']}({code}) → 분동 전 {g['nm']}")
            else:
                cand = sgg_pts.get(sgg) or sgg_pts.get(sgg[:4] + "0") or []
                if cand:
                    g = {"x": sum(c[0] for c in cand) / len(cand), "y": sum(c[1] for c in cand) / len(cand),
                         "how": "sgg_mean", "nm": ""}
                else:
                    g = None
                src = "sgg_fallback"
                qc_fallback.append(f"{r['시도명']} {names.get(sgg, sgg)} {r['이름']}({code}, {int(r['계']):,}명)"
                                   + ("" if g else " [대체점 없음]"))
        if g is None:
            continue
        used.add(code if src == "code" else "")
        out.append({"읍면동코드": code, "읍면동": r["이름"], "시군구코드_KOSIS": sgg, "시도코드": r["시도코드"],
                    "경도": round(g["x"], 6), "위도": round(g["y"], 6), "대표점방법": g["how"], "매칭": src,
                    "인구": r["계"], "65세이상": r["65세이상"], "80세이상": r["80세이상"],
                    **{c: r[c] for c in r if c.endswith("세") or c == "100+"}})
    with open(ROOT / "data/clean/emd_points.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    tot = sum(int(r["계"]) for r in emd)
    fb_pop = sum(int(o["인구"]) for o in out if o["매칭"] == "sgg_fallback")
    unused = [v["nm"] for k, v in pts.items() if k not in used]
    qc = ["# 읍면동 대표점 QC", "",
          f"- 경계 {len(pts)}개(admdongkor ver20261001), KOSIS 읍면동(인구>0) {len(emd)}개, 출력 {len(out)}개",
          f"- 코드 매칭 {sum(o['매칭'] == 'code' for o in out)}, 이름/상위읍면/분동 매칭 {len(qc_name)}, "
          f"시군구 평균점 대체 {len(qc_fallback)} "
          f"(인구 {fb_pop:,}명 = {fb_pop / tot:.2%})",
          f"- 대표점 방법: centroid {sum(o['대표점방법'] == 'centroid' for o in out)}, "
          f"scanline {sum(o['대표점방법'] == 'scanline' for o in out)}",
          f"- 좌표 범위: 경도 {min(o['경도'] for o in out)}–{max(o['경도'] for o in out)}, "
          f"위도 {min(o['위도'] for o in out)}–{max(o['위도'] for o in out)}",
          "", "## 이름 매칭"] + [f"- {s}" for s in qc_name] + ["", "## 시군구 평균점 대체"] + [f"- {s}" for s in qc_fallback] + \
         ["", f"## KOSIS와 코드가 안 맞은 경계 {len(unused)}개 (일부는 이름 매칭으로 쓰임)", ", ".join(unused[:150])]
    (ROOT / "output/emd_points_qc.md").write_text("\n".join(qc) + "\n", encoding="utf-8")
    print(qc[2], qc[3], sep="\n")


if __name__ == "__main__":
    main()
