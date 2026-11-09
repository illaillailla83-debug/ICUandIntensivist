"""고령화 시나리오: 2026.10 읍면동 연령별 인구 × (시도·연령별 장래인구 Y년 ÷ 2026년) → Y년 미도달 인구.

가정: 시설 배치와 이동시간은 현재 그대로, 시도 안의 읍면동별 연령 변화율은 같다고 봄(시도 비례 배분).
입력: data/clean/{emd_points, proj_sido_5y}.csv + 접근성 파일(읍면동코드, 시간/거리 열)
출력: output/scenarios_<tag>.md, output/scenarios_<tag>.csv
사용: python -I -X utf8 code/analyze_scenarios.py <접근성csv> <ICU열> <전담ICU열> <단위> <컷오프,…> <tag>
  예: python -I -X utf8 code/analyze_scenarios.py data/clean/access_road_emd.csv ICU_분 전담ICU_분 분 30,60,90 road
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
SIDO = {"서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천", "광주광역시": "광주",
        "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종", "경기도": "경기", "강원도": "강원",
        "충청북도": "충북", "충청남도": "충남", "전라북도": "전북", "전라남도": "전남", "경상북도": "경북",
        "경상남도": "경남", "제주특별자치도": "제주"}
YEARS = ["2030", "2035"]
SCEN = {"1": "중위", "2": "고위", "3": "저위"}


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def age_key(nm):
    nm = nm.replace(" ", "")
    return "100+" if nm.startswith("100") else nm


def main(acc_path, col_all, col_int, unit, cuts, tag):
    cuts = [float(c) for c in cuts.split(",")]
    proj = defaultdict(float)  # (scen, sido, year, age) → pop
    for r in rd(C / "proj_sido_5y.csv"):
        if r["소계여부"] == "Y" or r["시도명"] not in SIDO:
            continue
        proj[(r["시나리오코드"], SIDO[r["시도명"]], r["연도"], age_key(r["연령"]))] += float(r["추계인구"])
    acc = {r["읍면동코드"]: r for r in rd(ROOT / acc_path)}
    pts = rd(C / "emd_points.csv")
    ages = [k for k in pts[0] if k.endswith("세") or k == "100+"]
    old65 = ages[13:]
    old80 = ages[16:]

    rows = []
    for p in pts:
        a = acc.get(p["읍면동코드"])
        if a is None:
            continue
        rows.append((a["시도_17"], float(a[col_all]), float(a[col_int]), {k: float(p[k]) for k in ages}))
    miss = len(pts) - len(rows)

    def ratio(s, sido, y, age):
        base = proj.get((s, sido, "2026", age), 0)
        return proj.get((s, sido, y, age), 0) / base if base else 1.0

    res = []  # (scen, year, target, cut, group, n, share)
    for s in ["0"] + list(SCEN):
        for y in (["2026"] if s == "0" else YEARS):
            tot = defaultdict(float)
            far = defaultdict(float)
            for sido, ta, ti, pop in rows:
                pp = pop if s == "0" else {k: v * ratio(s, sido, y, k) for k, v in pop.items()}
                grp = {"전체": sum(pp.values()), "65세이상": sum(pp[k] for k in old65), "80세이상": sum(pp[k] for k in old80)}
                for g, v in grp.items():
                    tot[g] += v
                    for tgt, t in (("성인ICU", ta), ("전담ICU", ti)):
                        for c in cuts:
                            if t > c:
                                far[(tgt, c, g)] += v
            for (tgt, c, g), v in sorted(far.items()):
                res.append((s, y, tgt, c, g, v, v / tot[g], tot[g]))
            for tgt in ("성인ICU", "전담ICU"):
                for c in cuts:
                    for g in tot:
                        if (tgt, c, g) not in far:
                            res.append((s, y, tgt, c, g, 0.0, 0.0, tot[g]))

    with open(ROOT / f"output/scenarios_{tag}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["시나리오", "연도", "대상", f"컷오프({unit})", "연령군", "미도달인구", "비율", "연령군총인구"])
        for s, y, tgt, c, g, v, sh, t in res:
            w.writerow(["2026.10 실제" if s == "0" else SCEN[s], y, tgt, c, g, round(v), round(sh, 4), round(t)])

    md = [f"# 고령화 시나리오 — {tag} ({acc_path})", "",
          "현재 시설·이동시간 고정, 2026.10 읍면동 연령구조에 시도·연령별 장래인구 증가율(2022년 기준 추계)을 곱함.", "",
          f"| 시나리오 | 연도 | 대상 | 컷오프 | 전체 미도달 | 65세 이상 미도달 | 80세 이상 미도달 |", "|---|---|---|---|---|---|---|"]
    idx = {(s, y, tgt, c, g): (v, sh) for s, y, tgt, c, g, v, sh, _ in res}
    for s in ["0"] + list(SCEN):
        for y in (["2026"] if s == "0" else YEARS):
            for tgt in ("성인ICU", "전담ICU"):
                for c in cuts:
                    cells = [f"{idx[(s, y, tgt, c, g)][0]:,.0f} ({idx[(s, y, tgt, c, g)][1]:.1%})"
                             for g in ("전체", "65세이상", "80세이상")]
                    md.append(f"| {'2026.10 실제' if s == '0' else SCEN[s]} | {y} | {tgt} | >{c:g}{unit} | " + " | ".join(cells) + " |")
    md += ["", f"- 접근성 자료가 없는 읍면동: {miss}"]
    (ROOT / f"output/scenarios_{tag}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("ok")


if __name__ == "__main__":
    main(*sys.argv[1:7])
