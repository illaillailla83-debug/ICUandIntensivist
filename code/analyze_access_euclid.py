"""1차 접근성: 읍면동 대표점 → 가장 가까운 성인 ICU / 전담전문의 ICU 까지 직선거리(haversine).

도로 이동시간(OSRM) 전의 임시 분석. 섬·산지에서 실제 이동시간을 과소평가함(한계).
거리 컷오프: 20 / 30 / 50 km (직선). 연령: 전체, 65세 이상, 80세 이상.

입력: data/clean/{emd_points, icu_hospitals, icu_intensivist_khqa, sgg_crosswalk}.csv
출력: data/clean/access_euclid_emd.csv, output/access_euclid_draft.md
사용: python -I -X utf8 code/analyze_access_euclid.py
"""
import csv
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
CUTS = [20, 30, 50]
ORDER = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남",
         "경북", "경남", "제주"]


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def hav(lon1, lat1, lon2, lat2):
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def main():
    icu = rd(C / "icu_hospitals.csv")
    ints = {r["암호화요양기호"] for r in rd(C / "icu_intensivist_khqa.csv") if r["전담전문의_있음"] == "1"}
    fac_all = [(float(h["좌표X_경도"]), float(h["좌표Y_위도"]), h["요양기관명"]) for h in icu]
    fac_int = [(float(h["좌표X_경도"]), float(h["좌표Y_위도"]), h["요양기관명"]) for h in icu
               if h["암호화요양기호"] in ints]
    sido17 = {r["KOSIS코드"]: r["시도_17"] for r in rd(C / "sgg_crosswalk.csv")}
    pts = rd(C / "emd_points.csv")

    out = []
    for p in pts:
        x, y = float(p["경도"]), float(p["위도"])
        da = min((hav(x, y, fx, fy), n) for fx, fy, n in fac_all)
        di = min((hav(x, y, fx, fy), n) for fx, fy, n in fac_int)
        out.append({"읍면동코드": p["읍면동코드"], "읍면동": p["읍면동"], "시군구코드_KOSIS": p["시군구코드_KOSIS"],
                    "시도_17": sido17.get(p["시군구코드_KOSIS"], ""), "인구": int(p["인구"]),
                    "65세이상": int(p["65세이상"]), "80세이상": int(p["80세이상"]),
                    "최근접ICU_km": round(da[0], 2), "최근접ICU": da[1],
                    "최근접전담ICU_km": round(di[0], 2), "최근접전담ICU": di[1]})
    miss = [o for o in out if not o["시도_17"]]
    with open(C / "access_euclid_emd.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    def share(rows, col, dcol, cut):
        tot = sum(r[col] for r in rows)
        far = sum(r[col] for r in rows if r[dcol] > cut)
        return far, far / tot if tot else 0

    def wmed(rows, dcol, col="인구"):
        s = sorted(rows, key=lambda r: r[dcol])
        half, acc = sum(r[col] for r in s) / 2, 0
        for r in s:
            acc += r[col]
            if acc >= half:
                return r[dcol]

    md = ["# 접근성 1차 분석 (직선거리, 임시)", "",
          f"읍면동 대표점 {len(out)}개 → 성인 ICU {len(fac_all)}곳 / 전담전문의 ICU {len(fac_int)}곳. "
          "직선거리라 섬·산지에서 실제보다 가깝게 나옴 → 도로 이동시간(OSRM)으로 대체 예정.", "",
          "## 전국: 직선거리 컷오프를 넘는 인구", "",
          "| 대상 | 컷오프 | 전체 인구 | % | 65세 이상 | % | 80세 이상 | % |", "|---|---|---|---|---|---|---|---|"]
    for lab, dcol in [("성인 ICU", "최근접ICU_km"), ("전담전문의 ICU", "최근접전담ICU_km")]:
        for c in CUTS:
            cells = []
            for col in ("인구", "65세이상", "80세이상"):
                n, s = share(out, col, dcol, c)
                cells += [f"{n:,}", f"{s:.1%}"]
            md.append(f"| {lab} | >{c} km | " + " | ".join(cells) + " |")
    md += ["", f"- 인구가중 중앙 거리: 성인 ICU {wmed(out, '최근접ICU_km')} km, 전담전문의 ICU {wmed(out, '최근접전담ICU_km')} km",
           f"- 65세 이상 가중 중앙 거리: 성인 ICU {wmed(out, '최근접ICU_km', '65세이상')} km, "
           f"전담전문의 ICU {wmed(out, '최근접전담ICU_km', '65세이상')} km", ""]

    md += ["## 시도별: 전담전문의 ICU까지 직선 >30 km 인구 비율", "",
           "| 시도 | 인구 | 인구가중 중앙거리(전담) km | >30km 전체 | >30km 65+ | >50km 전체 | 성인 ICU >30km 전체 |",
           "|---|---|---|---|---|---|---|"]
    by = defaultdict(list)
    for o in out:
        by[o["시도_17"]].append(o)
    for s in ORDER:
        rows = by[s]
        md.append(f"| {s} | {sum(r['인구'] for r in rows):,} | {wmed(rows, '최근접전담ICU_km')} | "
                  f"{share(rows, '인구', '최근접전담ICU_km', 30)[1]:.1%} | {share(rows, '65세이상', '최근접전담ICU_km', 30)[1]:.1%} | "
                  f"{share(rows, '인구', '최근접전담ICU_km', 50)[1]:.1%} | {share(rows, '인구', '최근접ICU_km', 30)[1]:.1%} |")
    far = sorted(out, key=lambda o: -o["최근접전담ICU_km"])[:15]
    md += ["", "## 전담전문의 ICU에서 가장 먼 읍면동 15곳 (직선)", ""] + \
          [f"- {o['시도_17']} {o['읍면동']} ({o['인구']:,}명): {o['최근접전담ICU_km']} km → {o['최근접전담ICU']}" for o in far]
    md += ["", f"- 시도 미지정 읍면동: {len(miss)}"]
    (ROOT / "output/access_euclid_draft.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("ok", len(out))


if __name__ == "__main__":
    main()
