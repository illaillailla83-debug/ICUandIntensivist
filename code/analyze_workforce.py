"""전담전문의 인력 소요와 비용 규모 (원고 v11 Discussion의 [CODE] 자리). 2026-11-06

필요 인원: 병원별 ceil(성인 ICU 병상 ÷ 전담의 1인당 병상), 기준 18·3(4차 평가 중앙값)과 22·0(평균, 범위의 하한)
대상: 최적 선택 10곳·5곳(ICU ≥10병상, 65세 이상 목표 = Table S2/S3), 전담 미배치 책임의료기관 36곳(정책 대안 D)
인건비: 필요 인원 × 의사 연평균 보수(복지부 2026-09-29, 제2차 보건의료인력 실태조사, 2023년)
  - 전체 2억 8,518만 원, 종합병원 2억 5,145만 원, 병원 3억 5,427만 원(참고: 최적 10곳은 모두 '종합병원')
가산 수가(복지부 2023-09-21, 2024.1 시행): 1:20 4만 5천 원 ~ 1:5 17만 4천 원 / 환자·일. 중간 등급은 보도자료에 없음
  - 18·3병상당 1명은 1:20 등급 근처 → 이 인력 가정과 맞는 값은 4만 5천 원. 17만 4천 원은 1:5 인력일 때만 해당
병상 가동률: 출처 있는 현재 값을 찾지 못해 가정값 70%·80%
출력: output/tables/workforce_requirement.md
사용: python -I -X utf8 code/analyze_workforce.py
"""
import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
MEDIAN, MEAN = 18.3, 22.0
CERTIFIED = 1774            # 2022 세부전문의 (원고 ref 3)
ADULT_BEDS = 10932
PAY = {"all physicians": 285.18, "general hospitals": 251.45, "hospital-class (병원)": 354.27}  # 백만 원
ALLOC_2026, PROGRAMME = 74_200, 203_000                                                        # 백만 원
RATE_LO, RATE_HI = 45_000, 174_000                                                             # 원/환자·일
OCC = (0.70, 0.80)


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def main():
    icu = {(h["요양기관명"], h["시도_17"]): h for h in rd(C / "icu_hospitals.csv")}
    pol = sorted((r for r in rd(ROOT / "output/policy_road.csv")
                  if r["대안"] == "C 탐욕최적(ICU≥10병상)" and r["목표"] == "65세이상"), key=lambda r: int(r["k"]))
    opt10 = [(r["추가기관"], int(icu[(r["추가기관"], r["시도"])]["성인중환자병상수"])) for r in pol[:10]]
    resp = [(r["요양기관명"], int(r["성인ICU병상"])) for r in rd(C / "responsible_hospitals_matched.csv")
            if r["ICU보유"] == "Y" and r["전담전문의"] != "Y" and r["암호화요양기호"]]
    assert len(resp) == 36, len(resp)

    def need(rows, ratio):
        return sum(math.ceil(b / ratio) for _, b in rows)

    md = ["# Intensivist workforce requirement and cost scale (for Discussion, manuscript v11)", "",
          f"- Adult ICU beds per certified intensivist: {ADULT_BEDS} / {CERTIFIED} = **{ADULT_BEDS / CERTIFIED:.2f}** → about one per 6 beds", "",
          "## 1. Optimal ten (ICU ≥10 beds; Table S2/S3) — all are general hospitals (종합병원)", "",
          "| k | Hospital | Adult ICU beds | Needed at 18·3 | Needed at 22·0 | Beds per intensivist at 18·3 |", "|---|---|---|---|---|---|"]
    for k, (n, b) in enumerate(opt10, 1):
        md.append(f"| {k} | {n} | {b} | {math.ceil(b / MEDIAN)} | {math.ceil(b / MEAN)} | {b / math.ceil(b / MEDIAN):.1f} |")
    beds10 = sum(b for _, b in opt10)
    n10, n10_lo = need(opt10, MEDIAN), need(opt10, MEAN)
    n5, n5_lo = need(opt10[:5], MEDIAN), need(opt10[:5], MEAN)
    nr, nr_lo = need(resp, MEDIAN), need(resp, MEAN)
    md += [f"| | **Total** | {beds10} | **{n10}** | {n10_lo} | |", "",
           "## 2. Totals", "", "| Set | Hospitals | Beds | Needed at 18·3 (% of 1774) | Needed at 22·0 (% of 1774) |", "|---|---|---|---|---|",
           f"| Optimal 10 | 10 | {beds10} | {n10} ({100 * n10 / CERTIFIED:.1f}%) | {n10_lo} ({100 * n10_lo / CERTIFIED:.1f}%) |",
           f"| Optimal 5 | 5 | {sum(b for _, b in opt10[:5])} | {n5} ({100 * n5 / CERTIFIED:.1f}%) | {n5_lo} ({100 * n5_lo / CERTIFIED:.1f}%) |",
           f"| 36 responsible hospitals without an intensivist | 36 | {sum(b for _, b in resp)} | {nr} ({100 * nr / CERTIFIED:.1f}%) | {nr_lo} ({100 * nr_lo / CERTIFIED:.1f}%) |",
           "", "Each ICU needs at least one intensivist, so small units round up (a 10-bed unit needs 1).", "",
           f"## 3. Salary cost of the optimal ten ({n10} intensivists at 18·3)", "",
           "| Pay figure (2023, ref 28) | KRW million per physician | KRW billion per year | % of KRW 74·2 billion (2026) | % of KRW 203 billion (programme) |",
           "|---|---|---|---|---|"]
    for lab, p in PAY.items():
        tot = n10 * p
        md.append(f"| {lab} | {p:,.2f} | {tot / 1000:.2f} | {100 * tot / ALLOC_2026:.1f}% | {100 * tot / PROGRAMME:.1f}% |")
    md += ["", "**Recommended**: the general-hospital figure (KRW 251 million), because all ten are general hospitals. "
           "The draft's 'KRW 354 million in hospital-class institutions' is the figure for 병원 (hospitals below general-hospital "
           "level), not for these units.", "",
           f"## 4. Supplement revenue across the ten units ({beds10} beds; occupancy is an ASSUMPTION — no sourced current value found)", "",
           "| Occupancy (assumed) | Occupied bed-days/year | At KRW 45 000 (1:20 tier) | At KRW 174 000 (1:5 tier) |", "|---|---|---|---|"]
    for o in OCC:
        days = beds10 * o * 365
        md.append(f"| {o:.0%} | {days:,.0f} | KRW {days * RATE_LO / 1e9:.2f} billion | KRW {days * RATE_HI / 1e9:.2f} billion |")
    md += ["", "**Caution**: staffing at 18·3 beds per intensivist corresponds to roughly the 1:20 tier, so the revenue consistent "
           "with the staffing assumption is the KRW 45 000 column. The KRW 174 000 tier would require about one intensivist per "
           f"five patients, ie, roughly {math.ceil(beds10 * 0.8 / 5)} intensivists at 80% occupancy instead of {n10}. Intermediate "
           "tiers are not given in the press release (ref 29).", "",
           "## 5. Sources", "",
           "- 18·3 / 22·0 beds per dedicated intensivist: HIRA fourth assessment (ref 6), reproduced in `output/khqa_manual_qc.md`",
           "- 1774 certified intensivists (2022): ref 3 (Oh & Song 2023), verified in chat",
           "- Pay: MOHW press release 2026-09-29, mohw.go.kr board.es?mid=a10503000000&bid=0027&act=view&list_no=1492074 "
           "(Code verified 2026-11-06: 의사 2억 8,518만 원; 종별 상급종합 1억 9,976만, 종합병원 2억 5,145만, 병원 3억 5,427만 원)",
           "- Supplement: MOHW press release 2023-09-21, list_no=378336 (Code verified 2026-11-06: 1:30 4.4만 원 단일 → (1:20) 4.5만 ~ (1:5) 17.4만 원, 2024년 1월부터)",
           "- KRW 74·2 billion (2026) and KRW 203 billion (programme since 2025): ref 16",
           f"- Optimal ten from `output/policy_road.csv`; 36 responsible hospitals from `data/clean/responsible_hospitals_matched.csv`"]
    (ROOT / "output/tables/workforce_requirement.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
