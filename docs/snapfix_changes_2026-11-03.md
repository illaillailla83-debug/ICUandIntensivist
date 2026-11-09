# 병원 스냅 버그 수정과 OSRM 비교 → 원고 수치 변경 (Claude Code, 2026-11-03)

## 1. 무슨 일이 있었나
- **발견 경위**: OSRM v6.0.0(표준 엔진)으로 이동시간을 다시 계산해 비교하다가 발견함
  - 영월·단양·사북·풍기에서 OSRM은 제천 명지병원(전담 ICU)으로 30–57분인데, 자체 구현은 이 병원을 건너뛰고 원주세브란스로 72–99분이었음
- **원인** (`code/analyze_access_road.py`)
  - 읍면동 대표점은 병원과 이어진 도로망에 붙였지만, **병원은 그냥 가장 가까운 도로 노드에 붙였음**
  - 그 노드가 끊긴 도로 조각(병원 안 통로 등)이면 그 병원에는 어디서도 도달할 수 없게 됨
  - 해당 병원 5곳: 명지병원(제천), 의정부을지대병원, 한도병원(안산), 강남세브란스, 강북삼성. 끊긴 조각까지의 거리 37–95 m
- **수정**: 병원도 '양방향(들어오는 길·나가는 길)으로 각각 2,000개 이상 노드에 닿는 도로망'의 가장 가까운 노드에 붙임. 섬 안의 도로망도 인정됨
  - 같은 코드를 쓰는 2SFCA·정책·민감도 스크립트도 같이 고침
  - 이후 시나리오·형평성·표·그림을 모두 다시 생성함
  - 수정 전 산출물은 `_to_delete/pre_snapfix_2026-11-03/`에 보관
- **영향**: 전담 ICU 60분 미도달이 2,013,318명 → **1,906,141명** (−107,177, −5.3%)
  - 대부분 충북(제천 주변)·강원(영월·평창)·경북 북부에서 줄어듦
  - 성인 ICU 기준 결과는 변화 없음(그 지역에 다른 ICU가 있었기 때문)
  - 결론의 방향(전담 ICU 격차, 고령·재정취약 지역 집중, 소수 기관 강화의 효과)은 그대로이고, 크기만 조금 줄어듦

## 2. OSRM 비교 결과 (수정 후 자체 구현 vs OSRM v6.0.0)
- 원자료: `output/osrm_comparison.md`, `data/clean/access_osrm_emd.csv`
- 비교 조건: 같은 OSM 추출본(sha256 523cbb38… 일치), 같은 대표점·병원 좌표, 같은 접속 규칙(20 km/h)
- 차이: OSRM 기본 car 프로필은 회전·신호 지연을 넣음

| 지표 | 자체 구현 | OSRM |
|---|---|---|
| 전담 ICU >60분, 전체 | 1,906,141 (3.7%) | 1,969,457 (3.9%) |
| 전담 ICU >60분, 65세 이상 | 647,370 (5.7%) | 667,053 (5.9%) |
| 성인 ICU >60분, 전체 | 174,482 (0.3%) | 191,655 (0.4%) |
| 전담 ICU 이동시간 중앙값(IQR) | 7.0 (4.3–14.1) | 7.4 (4.6–14.8) |
| 60분 기준 분류가 같은 인구 | — | 99.85% |

- OSRM이 미도달을 3% 많게 냄 → 지연을 넣은 만큼 예상한 방향. 분류가 갈린 곳은 대부분 59.7 vs 60.1분 같은 경계 사례
- 섬(흑산 등)은 OSRM에서 훨씬 김(OSRM 페리 기본 속도 5 km/h vs 자체 20 km/h). 두 경우 모두 >90분 범주라 60분 결과에는 영향 없음
- **주분석·민감도 중 어느 쪽에 둘지는 연구자 결정**. 권고는 아래 §4

## 3. 원고 v4에서 바꿀 숫자 (위치는 manuscript_v4/의 파일:행)

| 위치 | 수정 전 | 수정 후 |
|---|---|---|
| abstract:9 | 2 013 318 (3·9%) | **1 906 141 (3·7%)** |
| abstract:9 | 688 080 (6·1%) | **647 370 (5·7%)** |
| abstract:9 | 2·5% at 30–39 … 8·0% at ≥90 | **2·4% … 7·6%** (2026-11-05 정정: 처음에 7·5%로 잘못 적음, 정확한 값 7·552%) |
| abstract:9 | CI −0·66, +0·72 | **−0·65, +0·71** |
| abstract:9 | 902 076 by 2035 (+31%) | **847 001 (+31%)** |
| abstract:9 | ten optimal: 77% | **78%** |
| abstract:9 | all 36 responsible: 68% | **65%** |
| abstract:9 | 80% speed: 7·0% | **6·7%** |
| introduction:7 (Research in context) | about 12 times | **about 11 times** (10·9배) |
| results:13 | adult ICU IQR 3·1–8·7 | **3·1–8·6** |
| results:13 | intensivist IQR 4·3–14·3 | **4·3–14·1** (중앙값 7·0 그대로) |
| results:13 | 2 013 318 (3·9%); about 12 times | **1 906 141 (3·7%); about 11 times** |
| results:13 | >30 min 6 416 656 (12·6%) | **6 281 442 (12·3%)** |
| results:13 | >90 min 388 475 (0·8%) | **295 924 (0·6%)** |
| results:15 | Jeonnam 935 427, 52·8%, 61 min (IQR 50–77) | 그대로 |
| results:15 | Gyeongbuk 529 854, 21·3% | **513 004, 20·6%** |
| results:15 | Gangwon 269 640, 17·9% | **223 001, 14·8%** |
| results:15 | three provinces 1 734 921 (86%) | **1 671 432 (88%)** |
| results:17 | 2SFCA 24·9 / 16·9 | **25·1 / 17·0** |
| results:17 | Gini 0·123, 0·167; 0·145, 0·231 | **0·121, 0·164; 0·144, 0·228** |
| results:17 | 78–82% (Seoul, Incheon, Gyeonggi) | **78–81%** (Jeonnam 23%, Gyeongbuk 37% 그대로) |
| results:21 | 2·5% (30–39), 5·1% (60–69), 7·2% (80–89), 8·0% (≥90) | **2·4%, 4·8%, 6·8%, 7·6%** (2026-11-05 정정) |
| results:21 | 688 080 (6·1%); 189 897 (7·3%) | **647 370 (5·7%); 179 646 (6·9%)** |
| results:23 | CI −0·657, +0·715 | **−0·653, +0·707** |
| results:23 | Q1 1 282 177 (12·8%); 498 303 (16·3%) | **1 205 630 (12·0%); 466 682 (15·3%)** |
| results:23 | oldest quintile 1 603 791 (15·6%) | **1 496 614 (14·5%)** |
| results:23 | non-capital 2 000 847 (8·0%) | **1 893 670 (7·6%)** (capital 12 471 그대로) |
| results:27 | total 2·01 → 2·02 million | **1·91 million in both 2026 and 2035** (1 906 141 → 1 911 055) |
| results:27 | ≥65 y: 688 080 → 782 807 → 902 076 (+31%) | **647 370 → 735 656 → 847 001 (+31%)** |
| results:27 | ≥80 y: 189 897 → 258 909 (+36%) | **179 646 → 244 363 (+36%)** |
| results:27 | share 6·1% → 5·8% | **5·7% → 5·5%** (분모 11·35 → 15·51 million 그대로) |
| results:27 | low–high 883 429–918 223 | **829 440–862 197** |
| results:31 | public 69% (to 214 685) | **67% (to 214 685)** |
| results:31 | regional medical centres 64% | **63%** |
| results:31 | responsible 68%, ≥10 beds 52% | **65%, 49%** |
| results:31 | ten (≥10 beds) 77% (to 157 460) | **78% (to 143 136)** |
| results:31 | ten (≥20 beds) 68% | **71%** |
| results:31 | first five: Suncheon, Yeongju, Haenam, Yeongwol, Namwon; 64% | **Suncheon, Andong, Haenam, Namwon, Taebaek; 65%** |
| results:31 | first three 13–21 points; 4th–10th 2–5; 14th onwards ≤1·2 | **first three 14–23; 4th–10th 2–4; 13th onwards ≤1·3** |
| results:31 | ten = 86% of attainable (77·1% vs 89·3%) | **88% (77·9% vs 88·6%)**; all 220: 89% 그대로 |
| results:35 | ×0·8: 3 585 248 (7·0%), 10·3% | **3 436 510 (6·7%), 9·8%** |
| results:35 | ×0·67: 4 677 795 (9·2%), 13·5% | **4 548 422 (8·9%), 13·1%** |
| results:35 | grade 1–2 4·5%; ≥20 beds 4·5%; 10 km/h 4·1% | **4·3%; 4·2%; 3·9%** |
| results:35 | 6–12 times | **6–13 times** (OSRM 포함 6·1–12·5배) |
| results:35 | straight-line 8·5% (12·4%) | 그대로 |
| discussion:3 | 2·0 million (3·9%); about 12 times | **1·9 million (3·7%); about 11 times** |
| discussion:3 | <0·1% vs 8·0% | **<0·1% vs 7·6%** |
| discussion:3 | CI −0·66, +0·72 | **−0·65, +0·71** |
| discussion:3 | 86% (1 734 921 of 2 013 318) | **88% (1 671 432 of 1 906 141)** |
| discussion:7 | Korea 3·9% (vs US 1·8%) | **3·7%** |
| discussion:13 | two-thirds / three-quarters / nearly two-thirds (five; Jeonnam, Gyeongbuk, Gangwon, Jeonbuk) | 그대로 맞음 (67·65% / 78% / 65%, 다섯 곳의 시도도 같음) |
| discussion:15 | about three-quarters and two-thirds (≥10, ≥20 beds) | **about three-quarters and 70%** (78%, 71%) |
| discussion:15 | 68% to 52% | **65% to 49%** |
| discussion:21 | 3·9% to 7·0% and 9·2% | **3·7% to 6·7% and 8·9%** |
| discussion:25 | 2 million people | **1·9 million people** |

바뀌지 않는 것: 공급 지표 전부(362, 10 932, 142, 7403, 67·7%, 13·6배 등), 성인 ICU 미도달(174 482, 0·3%), 전남 수치, 수도권 12 471명, 2SFCA 전남 23%·경북 37%, 직선거리 결과, 고령 분모, 섬 6곳 처리 문장.

## 4. Methods·Discussion 문장 (제안)
- **Methods, Travel time** (병원 연결 방식이 이제 문장과 일치하도록):
  "Each hospital was connected to the nearest non-motorway node from which at least 2000 nodes could be reached in both directions, which excludes isolated fragments such as internal hospital roads, and each dong representative point to the nearest node of the network reachable from the hospitals; the straight-line connector was converted to time at 20 km/h…"
- **Methods, Sensitivity analyses**에 추가:
  "…and with travel times recomputed with the Open Source Routing Machine itself (version 6.0.0, default car profile, which adds turn and traffic-signal penalties) on the same extract, points and connector rule."
- **Results, Sensitivity**에 추가:
  "With OSRM, 1 969 457 residents (3·9%) lived beyond 60 min of an intensivist-staffed ICU, 3% more than in the main analysis; the 60-min classification agreed for 99·85% of residents, and the median travel time was 7·4 min (IQR 4·6–14·8)."
- **Discussion, limitation 3**의 OSRM 문장 대체:
  "Our main routing re-implemented OSRM's default car profile without turn and signal penalties; recomputing travel times with OSRM itself increased the unreached population by 3% and left the 60-min classification unchanged for 99·85% of residents. Neither was calibrated against observed travel times…"
- **결정 (연구자, 2026-11-03)**: 주분석은 수정한 자체 구현으로 두고, OSRM은 민감도 분석으로 함. 위 문장들을 그대로 사용
- 결정 전 권고: 주분석은 수정한 자체 구현으로 두고, OSRM은 검증용 민감도로 두는 것
  - 이유 1: 두 결과가 거의 같음
  - 이유 2: 정책·2SFCA 분석은 자체 도로망(제한 탐색)을 써야 하므로 주분석과 같은 엔진이어야 수치가 서로 맞음
