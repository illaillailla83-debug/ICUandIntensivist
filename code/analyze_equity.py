"""형평성: 시군구별 '전담전문의 ICU 60분 미도달 비율'의 집중지수(재정자립도·고령화율 순위)와 5분위 비교.

집중지수(CI): 인구가중 분수 순위 R(재정자립도 낮은→높은), y=시군구 미도달 비율, CI = 2·cov_w(y,R)/mean_w(y).
  CI<0 → 재정자립도 낮은(가난한) 지역에 미도달이 몰림. 고령화율은 높은 순으로 순위를 매겨 CI>0이면 고령 지역 집중.
입력: data/clean/{access_road_emd, fiscal_sgg, sgg_crosswalk}.csv
출력: output/equity_road.md
사용: python -I -X utf8 code/analyze_equity.py [컷오프분=60]
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
CUT = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def ci(units, rank_key, ycol, reverse=False):
    s = sorted(units, key=lambda u: u[rank_key], reverse=reverse)
    W = sum(u["pop"] for u in s)
    acc, R = 0.0, []
    for u in s:
        R.append((acc + u["pop"] / 2) / W)
        acc += u["pop"]
    my = sum(u["pop"] * u[ycol] for u in s) / W
    mr = sum(u["pop"] * r for u, r in zip(s, R)) / W
    cov = sum(u["pop"] * (u[ycol] - my) * (r - mr) for u, r in zip(s, R)) / W
    return 2 * cov / my if my else 0.0


def quint(units, key, cols, reverse=False):
    s = sorted(units, key=lambda u: u[key], reverse=reverse)
    W = sum(u["pop"] for u in s)
    q = defaultdict(lambda: defaultdict(float))
    acc = 0.0
    for u in s:
        k = min(4, int(5 * (acc + u["pop"] / 2) / W))
        acc += u["pop"]
        q[k]["pop"] += u["pop"]
        q[k]["n"] += 1
        q[k]["lo"] = min(q[k].get("lo", 1e9), u[key])
        q[k]["hi"] = max(q[k].get("hi", -1e9), u[key])
        for c in cols:
            q[k][c] += u[c]
    return q


def main():
    fis = {r["KOSIS코드"]: float(r["재정자립도_2026"]) for r in rd(C / "fiscal_sgg.csv")}
    xw = {r["KOSIS코드"]: r for r in rd(C / "sgg_crosswalk.csv")}
    agg = defaultdict(lambda: defaultdict(float))
    for e in rd(C / "access_road_emd.csv"):
        a = agg[e["시군구코드_KOSIS"]]
        p, o = int(e["인구"]), int(e["65세이상"])
        a["pop"] += p
        a["o65"] += o
        far = float(e["전담ICU_분"]) > CUT
        a["far"] += p * far
        a["far65"] += o * far
    units = []
    for k, a in agg.items():
        units.append({"code": k, "name": xw[k]["KOSIS이름"], "sido": xw[k]["시도_17"], "pop": a["pop"], "o65": a["o65"],
                      "far": a["far"], "far65": a["far65"], "y": a["far"] / a["pop"], "y65": a["far65"] / a["o65"],
                      "fis": fis[k], "aging": a["o65"] / a["pop"]})
    md = [f"# 형평성 — 전담전문의 ICU {CUT:g}분 미도달 (도로, 시군구 {len(units)}개)", "",
          "| 순위 변수 | 결과 | 집중지수 |", "|---|---|---|",
          f"| 재정자립도(낮은→높은) | 전체 미도달 비율 | {ci(units, 'fis', 'y'):.3f} |",
          f"| 재정자립도(낮은→높은) | 65세 이상 미도달 비율 | {ci(units, 'fis', 'y65'):.3f} |",
          f"| 고령화율(낮은→높은) | 전체 미도달 비율 | {ci(units, 'aging', 'y'):.3f} |",
          "", "CI<0(재정자립도): 재정이 약한 지역에 미도달이 몰림. CI>0(고령화율): 고령화된 지역에 몰림.", ""]
    for key, lab, rev in (("fis", "재정자립도 5분위 (Q1=가장 낮음, 인구가중)", False), ("aging", "고령화율 5분위 (Q1=가장 낮음)", False)):
        q = quint(units, key, ["far", "far65", "o65"], rev)
        md += [f"## {lab}", "", "| 분위 | 범위 | 시군구 | 인구 | 미도달 | 미도달 비율 | 65+ 미도달 비율 |", "|---|---|---|---|---|---|---|"]
        for k in range(5):
            v = q[k]
            fmt = (lambda x: f"{x:.1f}") if key == "fis" else (lambda x: f"{x:.1%}")
            md.append(f"| Q{k + 1} | {fmt(v['lo'])}–{fmt(v['hi'])} | {int(v['n'])} | {int(v['pop']):,} | {int(v['far']):,} | "
                      f"{v['far'] / v['pop']:.1%} | {v['far65'] / v['o65']:.1%} |")
        md.append("")
    cap = {"서울", "인천", "경기"}
    for lab, sel in (("수도권", lambda u: u["sido"] in cap), ("비수도권", lambda u: u["sido"] not in cap)):
        s = [u for u in units if sel(u)]
        md.append(f"- {lab}: 미도달 {sum(u['far'] for u in s):,.0f}명 ({sum(u['far'] for u in s) / sum(u['pop'] for u in s):.1%}), "
                  f"65+ {sum(u['far65'] for u in s) / sum(u['o65'] for u in s):.1%}")
    (ROOT / "output/equity_road.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[2:8]))


if __name__ == "__main__":
    main()
