# Intensivist workforce requirement and cost scale (for Discussion, manuscript v11)

- Adult ICU beds per certified intensivist: 10932 / 1774 = **6.16** → about one per 6 beds

## 1. Optimal ten (ICU ≥10 beds; Table S2/S3) — all are general hospitals (종합병원)

| k | Hospital | Adult ICU beds | Needed at 18·3 | Needed at 22·0 | Beds per intensivist at 18·3 |
|---|---|---|---|---|---|
| 1 | 성가롤로병원 | 56 | 4 | 3 | 14.0 |
| 2 | 안동성소병원 | 34 | 2 | 2 | 17.0 |
| 3 | 해남우리종합병원 | 25 | 2 | 2 | 12.5 |
| 4 | 전북특별자치도 남원의료원 | 10 | 1 | 1 | 10.0 |
| 5 | 근로복지공단 태백병원 | 10 | 1 | 1 | 10.0 |
| 6 | 의료법인동춘의료재단문경제일병원 | 32 | 2 | 2 | 16.0 |
| 7 | 의료법인 거붕 백병원 | 20 | 2 | 1 | 10.0 |
| 8 | 의료법인영성의료재단 고흥종합병원 | 12 | 1 | 1 | 12.0 |
| 9 | 충청남도 서산의료원 | 10 | 1 | 1 | 10.0 |
| 10 | 강원특별자치도삼척의료원 | 10 | 1 | 1 | 10.0 |
| | **Total** | 219 | **17** | 15 | |

## 2. Totals

| Set | Hospitals | Beds | Needed at 18·3 (% of 1774) | Needed at 22·0 (% of 1774) |
|---|---|---|---|---|
| Optimal 10 | 10 | 219 | 17 (1.0%) | 15 (0.8%) |
| Optimal 5 | 5 | 135 | 10 (0.6%) | 9 (0.5%) |
| 36 responsible hospitals without an intensivist | 36 | 559 | 50 (2.8%) | 42 (2.4%) |

Each ICU needs at least one intensivist, so small units round up (a 10-bed unit needs 1).

## 3. Salary cost of the optimal ten (17 intensivists at 18·3)

| Pay figure (2023, ref 28) | KRW million per physician | KRW billion per year | % of KRW 74·2 billion (2026) | % of KRW 203 billion (programme) |
|---|---|---|---|---|
| all physicians | 285.18 | 4.85 | 6.5% | 2.4% |
| general hospitals | 251.45 | 4.27 | 5.8% | 2.1% |
| hospital-class (병원) | 354.27 | 6.02 | 8.1% | 3.0% |

**Recommended**: the general-hospital figure (KRW 251 million), because all ten are general hospitals. The draft's 'KRW 354 million in hospital-class institutions' is the figure for 병원 (hospitals below general-hospital level), not for these units.

## 4. Supplement revenue across the ten units (219 beds; occupancy is an ASSUMPTION — no sourced current value found)

| Occupancy (assumed) | Occupied bed-days/year | At KRW 45 000 (1:20 tier) | At KRW 174 000 (1:5 tier) |
|---|---|---|---|
| 70% | 55,954 | KRW 2.52 billion | KRW 9.74 billion |
| 80% | 63,948 | KRW 2.88 billion | KRW 11.13 billion |

**Caution**: staffing at 18·3 beds per intensivist corresponds to roughly the 1:20 tier, so the revenue consistent with the staffing assumption is the KRW 45 000 column. The KRW 174 000 tier would require about one intensivist per five patients, ie, roughly 36 intensivists at 80% occupancy instead of 17. Intermediate tiers are not given in the press release (ref 29).

## 5. Sources

- 18·3 / 22·0 beds per dedicated intensivist: HIRA fourth assessment (ref 6), reproduced in `output/khqa_manual_qc.md`
- 1774 certified intensivists (2022): ref 3 (Oh & Song 2023), verified in chat
- Pay: MOHW press release 2026-09-29, mohw.go.kr board.es?mid=a10503000000&bid=0027&act=view&list_no=1492074 (Code verified 2026-11-06: 의사 2억 8,518만 원; 종별 상급종합 1억 9,976만, 종합병원 2억 5,145만, 병원 3억 5,427만 원)
- Supplement: MOHW press release 2023-09-21, list_no=378336 (Code verified 2026-11-06: 1:30 4.4만 원 단일 → (1:20) 4.5만 ~ (1:5) 17.4만 원, 2024년 1월부터)
- KRW 74·2 billion (2026) and KRW 203 billion (programme since 2025): ref 16
- Optimal ten from `output/policy_road.csv`; 36 responsible hospitals from `data/clean/responsible_hospitals_matched.csv`
