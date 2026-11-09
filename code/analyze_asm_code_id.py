"""asmGrd 코드 중 '중환자실' 항목을 실증적으로 찾는다.

판단 근거 (중환자실 적정성평가의 알려진 특성):
  - ICU 보유 기관에는 있고, ICU가 없는 종합병원에는 거의 없어야 함
  - 4차 평가: 303곳(상급종합 45 + 종합병원 258), 1등급 68곳(22.4%) [언론 보도]
사용: python -I code/analyze_asm_code_id.py <asm_grades_long.csv> <출력 md>
"""
import csv
import sys
from collections import Counter, defaultdict


def main(src, out):
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig")))
    grp_of = {}
    by_code = defaultdict(dict)  # code -> {ykiho: value}
    type_of = {}
    for r in rows:
        grp_of[r["ykiho"]] = r["group"]
        type_of[r["ykiho"]] = r["clCdNm"]
        if r["item"].startswith("asmGrd"):
            by_code[r["item"]][r["ykiho"]] = r["value"]
    n = Counter(grp_of.values())
    lines = [f"# asmGrd 코드 식별\n\n대상 기관 수: {dict(n)}\n",
             "| 코드 | ICU기관 보유율 | 비ICU 종합병원 보유율 | 비율차 | ICU기관 중 상급종합 보유 | 숫자등급 기관수 | 등급분포(ICU기관) |",
             "|---|---:|---:|---:|---:|---:|---|"]
    n_top = sum(1 for k, g in grp_of.items() if g == "icu" and type_of.get(k) == "상급종합")
    stats = []
    for code, d in by_code.items():
        icu = [k for k in d if grp_of[k] == "icu"]
        ctl = [k for k in d if grp_of[k] != "icu"]
        p_icu = len(icu) / n["icu"]
        p_ctl = len(ctl) / max(n["control_noicu_general"], 1)
        top = sum(1 for k in icu if type_of.get(k) == "상급종합")
        dist = Counter(d[k] for k in icu)
        numeric = sum(v for g, v in dist.items() if g.isdigit())
        stats.append((p_icu - p_ctl, code, p_icu, p_ctl, top, numeric, dist))
    for diff, code, p_icu, p_ctl, top, numeric, dist in sorted(stats, reverse=True):
        lines.append(f"| {code} | {p_icu:.0%} | {p_ctl:.0%} | {diff:+.0%} | {top}/{n_top} | {numeric} | "
                     + ", ".join(f"{g}:{c}" for g, c in sorted(dist.items())) + " |")
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
