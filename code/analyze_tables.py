"""Table 1–3 (영문, 투고용) — 기존 분석 산출물을 모아 정리.

Table 1  시도별 공급·접근성 (인구, 고령화율, 재정자립도, ICU·전담 ICU 기관/병상, 10만 명당 병상, 중앙 이동시간, 60분 미도달, 2SFCA)
Table 2  A: 컷오프·대상·연령군별 미도달 인구  B: 민감도(60분)
Table 3  A: 고령화 시나리오(전담 ICU 60분)  B: 정책 대안(2026 인구)
입력: data/clean/{icu_hospitals, icu_intensivist_khqa, access_road_emd, access_2sfca_emd, fiscal_sgg, emd_points}.csv,
      data/raw/kosis_2026-11-03/fiscal_DT_1YL20921/fiscal_2022_2026.json,
      output/{sensitivity_road, scenarios_road, policy_road}.csv
출력: output/tables/table{1,2,3}.csv/.md, tableS1_inequality, tableS2_greedy_sequence (2026-11-03 추가)
사용: python -I -X utf8 code/analyze_tables.py
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
OUT = ROOT / "output/tables"
ORDER = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남",
         "경북", "경남", "제주"]
EN = {"서울": "Seoul", "부산": "Busan", "대구": "Daegu", "인천": "Incheon", "광주": "Gwangju", "대전": "Daejeon",
      "울산": "Ulsan", "세종": "Sejong", "경기": "Gyeonggi", "강원": "Gangwon", "충북": "Chungbuk", "충남": "Chungnam",
      "전북": "Jeonbuk", "전남": "Jeonnam", "경북": "Gyeongbuk", "경남": "Gyeongnam", "제주": "Jeju"}
FIS_SIDO = {"서울": "11", "부산": "21", "대구": "22", "인천": "23", "광주": "1224", "대전": "25", "울산": "26", "세종": "29",
            "경기": "31", "강원": "32", "충북": "33", "충남": "34", "전북": "35", "전남": "1236", "경북": "37", "경남": "38",
            "제주": "39"}
CAP = {"서울", "인천", "경기"}


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def write(name, title, header, rows, notes):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / f"{name}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    md = [f"# {title}", "", "| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    md += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    md += [""] + [f"{n}" for n in notes]
    (OUT / f"{name}.md").write_text("\n".join(md) + "\n", encoding="utf-8")


def wq(pairs, q):
    """인구가중 분위수: 누적 가중치가 처음으로 q×전체 이상이 되는 값 (q=0.5는 기존 wmed와 동일)."""
    pairs = sorted(pairs)
    cut, acc = sum(w for _, w in pairs) * q, 0
    for v, w in pairs:
        acc += w
        if acc >= cut:
            return v


def wmed(pairs):
    return wq(pairs, 0.5)


def med_iqr(pairs):
    return f"{wq(pairs, 0.5):.0f} ({wq(pairs, 0.25):.0f}–{wq(pairs, 0.75):.0f})"


def table1():
    icu = rd(C / "icu_hospitals.csv")
    ints = {r["암호화요양기호"] for r in rd(C / "icu_intensivist_khqa.csv") if r["전담전문의_있음"] == "1"}
    acc = rd(C / "access_road_emd.csv")
    s2 = {r["읍면동코드"]: r for r in rd(C / "access_2sfca_emd.csv")}
    fis = {(r["PRD_DE"], r["C1"]): float(r["DT"]) for r in json.loads(
        (ROOT / "data/raw/kosis_2026-11-03/fiscal_DT_1YL20921/fiscal_2022_2026.json").read_text(encoding="utf-8"))}
    g = defaultdict(lambda: defaultdict(float))
    times = defaultdict(list)
    times_any = defaultdict(list)
    for h in icu:
        a = g[h["시도_17"]]
        b = int(h["성인중환자병상수"])
        i = h["암호화요양기호"] in ints
        a["icu"] += 1
        a["beds"] += b
        a["iicu"] += i
        a["ibeds"] += b * i
    for e in acc:
        a = g[e["시도_17"]]
        p, o = int(e["인구"]), int(e["65세이상"])
        a["pop"] += p
        a["o65"] += o
        a["far"] += p * (float(e["전담ICU_분"]) > 60)
        a["far65"] += o * (float(e["전담ICU_분"]) > 60)
        x = s2[e["읍면동코드"]]
        a["adult"] += int(x["20세이상"])
        a["a1"] += float(x["A_ICU_adult"]) * int(x["20세이상"])
        a["a2"] += float(x["A_전담ICU_adult"]) * int(x["20세이상"])
        times[e["시도_17"]].append((float(e["전담ICU_분"]), p))
        times_any[e["시도_17"]].append((float(e["ICU_분"]), p))
    # (2026-11-03 추가) 투고 규정: % 옆에 n, 중앙값 옆에 IQR. 성인 ICU 2SFCA와 전담 비율 열 추가 (기존 값은 그대로)
    header = ["Region", "Population (million)", "Aged ≥65 y (%)", "Fiscal self-reliance 2026 (%)", "Adult ICUs (n)",
              "Adult ICU beds (n)", "Beds per 100 000", "Beds per 100 000 aged ≥65 y", "ICUs with intensivist (n)",
              "Beds with intensivist (n, % of beds)", "Intensivist beds per 100 000",
              "Travel time to any adult ICU, median (IQR), min",
              "Travel time to intensivist ICU, median (IQR), min", "Beyond 60 min, all ages, n (%)",
              "Beyond 60 min, aged ≥65 y, n (%)", "2SFCA adult ICU beds per 100 000 adults",
              "2SFCA intensivist beds per 100 000 adults", "Intensivist share of accessible capacity (%)"]

    def row(name, keys, fis_val):
        a = defaultdict(float)
        for k in keys:
            for kk, v in g[k].items():
                a[kk] += v
        t = [x for k in keys for x in times[k]]
        ta = [x for k in keys for x in times_any[k]]
        return [name, f"{a['pop'] / 1e6:.2f}", f"{100 * a['o65'] / a['pop']:.1f}", fis_val, int(a["icu"]),
                f"{int(a['beds']):,}", f"{a['beds'] / a['pop'] * 1e5:.1f}", f"{a['beds'] / a['o65'] * 1e5:.1f}",
                int(a["iicu"]), f"{int(a['ibeds']):,} ({100 * a['ibeds'] / a['beds']:.1f})",
                f"{a['ibeds'] / a['pop'] * 1e5:.1f}", med_iqr(ta), med_iqr(t),
                f"{int(a['far']):,} ({100 * a['far'] / a['pop']:.1f})",
                f"{int(a['far65']):,} ({100 * a['far65'] / a['o65']:.1f})",
                f"{a['a1'] / a['adult']:.1f}", f"{a['a2'] / a['adult']:.1f}", f"{100 * a['a2'] / a['a1']:.0f}"]

    rows = [row(EN[s], [s], f"{fis[('2026', FIS_SIDO[s])]:.1f}") for s in ORDER]
    rows += [row("Capital area", sorted(CAP), "—"), row("Non-capital area", [s for s in ORDER if s not in CAP], "—"),
             row("Korea", ORDER, f"{fis[('2026', '00')]:.1f}")]
    write("table1_supply_access_by_region", "Table 1. Adult ICU supply and access by region, Korea, 2026", header, rows, [
        "Population: resident registration, October 2026 (KOSIS). ICU beds: HIRA facility data, September 2026. "
        "Intensivist: ICU with a value for 'beds per dedicated intensivist' in the 4th national ICU quality assessment "
        "(2023, HIRA). Travel time: road network (OpenStreetMap), free-flow speeds, from administrative-dong representative "
        "points; medians and shares population-weighted. IQR: population-weighted 25th–75th percentiles of the travel time "
        "of administrative-dong representative points (each dong weighted by its total resident population). Beyond 60 min: "
        "n = residents whose administrative dong lies >60 min from the nearest ICU with a dedicated intensivist; % = n divided "
        "by the region's total (or aged ≥65 y) resident population. 2SFCA: two-step floating catchment area, 60-min "
        "catchment, demand = residents aged ≥20 y; values are demand-weighted means. Intensivist share of accessible "
        "capacity = 2SFCA intensivist beds ÷ 2SFCA adult ICU beds. Gwangju and Jeonnam are shown separately although merged administratively in 2026; fiscal "
        "self-reliance for these two uses the pre-merger provincial values reported in the 2026 table. Capital area = Seoul, "
        "Incheon, Gyeonggi."])


def table2():
    sens = rd(ROOT / "output/sensitivity_road.csv")
    tgt = {"성인ICU": "Any adult ICU", "전담ICU": "ICU with dedicated intensivist"}

    pts = rd(C / "emd_points.csv")
    tot = {"pop": sum(int(p["인구"]) for p in pts), "o65": sum(int(p["65세이상"]) for p in pts),
           "o80": sum(int(p["80세이상"]) for p in pts)}

    def cell(r, c):  # 비율은 인원÷총인구로 직접 계산(이중 반올림 방지)
        return f"{int(r[c]):,} ({100 * int(r[c]) / tot[c]:.1f})"

    header = ["Panel", "Scenario / threshold", "Facilities", "Facilities (n)", "All ages, n (%)", "Aged ≥65 y, n (%)",
              "Aged ≥80 y, n (%)"]
    rows = []
    for r in sens:
        if r["시나리오"] == "기본":
            rows.append(["A", f">{r['컷오프분']} min", tgt[r["대상"]], r["시설수"], cell(r, "pop"), cell(r, "o65"), cell(r, "o80")])
    rows.sort(key=lambda x: (x[2] != "Any adult ICU", int(x[1][1:-4])))
    lab = {"S1 속도×0.8": "Speeds ×0.8 (congestion)", "S2 속도×0.67": "Speeds ×0.67 (conservative)",
           "S3 스냅 10km/h": "Access to road network at 10 km/h", "S4 전담 엄격(1–2등급)": "Intensivist ICU and grade 1–2",
           "S5 성인ICU ≥10병상": "Adult ICUs with ≥10 beds only", "S6 전담ICU ≥20병상": "Intensivist ICUs with ≥20 beds only"}
    for r in sens:
        if r["컷오프분"] == "60" and r["시나리오"] in lab:
            if (r["시나리오"] in ("S4 전담 엄격(1–2등급)", "S6 전담ICU ≥20병상") and r["대상"] == "성인ICU") or \
                    (r["시나리오"] == "S5 성인ICU ≥10병상" and r["대상"] == "전담ICU"):
                continue  # 해당 시나리오에서 바뀌지 않는 대상은 생략
            rows.append(["B (>60 min)", lab[r["시나리오"]], tgt[r["대상"]], r["시설수"], cell(r, "pop"), cell(r, "o65"),
                         cell(r, "o80")])
    # (2026-11-03 추가) 표준 엔진 비교: OSRM v6.0.0 기본 car 프로필(회전·신호 지연 포함), 같은 접속 규칙
    osrm_p = C / "access_osrm_emd.csv"
    if osrm_p.exists():
        osrm = rd(osrm_p)
        for col, t, nf in (("ICU_분_osrm", "성인ICU", 362), ("전담ICU_분_osrm", "전담ICU", 142)):
            v = {k: sum(int(o[c]) for o in osrm if float(o[col]) > 60)
                 for k, c in (("pop", "인구"), ("o65", "65세이상"), ("o80", "80세이상"))}
            rows.append(["B (>60 min)", "OSRM v6.0.0 car profile (turn and signal penalties)", tgt[t], nf,
                         cell(v, "pop"), cell(v, "o65"), cell(v, "o80")])
    write("table2_unreached_population", "Table 2. Population beyond road travel-time thresholds to adult ICUs, Korea, 2026",
          header, rows, ["Panel A: main analysis (free-flow road speeds; access from representative point to road at 20 km/h). "
                         "Panel B: sensitivity analyses at the 60-min threshold; the OSRM rows recompute travel times with the Open Source "
                         "Routing Machine (version 6.0.0, default car profile, which adds turn and traffic-signal penalties) on "
                         "the same OpenStreetMap extract, points and connector rule. Percentages are of the national population "
                         "in each age group (total 51 075 282; ≥65 y 11 350 255; ≥80 y 2 588 264)."])


def table3():
    sc = rd(ROOT / "output/scenarios_road.csv")
    scen = {"2026.10 실제": "Observed", "저위": "Low", "중위": "Medium", "고위": "High"}
    header = ["Panel", "Year / alternative", "Projection variant / facilities", "All ages, n (%)", "Aged ≥65 y, n (%)",
              "Aged ≥80 y, n (%)"]
    rows = []
    for y, ss in (("2026", ["2026.10 실제"]), ("2030", ["저위", "중위", "고위"]), ("2035", ["저위", "중위", "고위"])):
        for s in ss:
            def c(g):
                r = next(r for r in sc if r["시나리오"] == s and r["연도"] == y and r["대상"] == "전담ICU"
                         and float(r["컷오프(분)"]) == 60 and r["연령군"] == g)
                return f"{int(r['미도달인구']):,} ({100 * float(r['비율']):.1f})"
            rows.append(["A", y, scen[s], c("전체"), c("65세이상"), c("80세이상")])
    pol = rd(ROOT / "output/policy_road.csv")
    base = next(r for r in pol if r["대안"] == "현재")
    bp, bo = int(base["미도달인구"]), int(base["미도달65세이상"])

    def red(v, b):
        return f"{v:,} (−{100 * (b - v) / b:.0f}%)"
    alts = [("현재", None, None, "Current (2026)", "—"),
            ("A 공공병원(공립·국립·특수법인) 전부", None, None, "Upgrade all public hospitals with ICU", "47"),
            ("B 지방의료원 전부", None, None, "Upgrade all regional medical centres", "26"),
            ("D 책임의료기관(2024.3 지정) 전부", None, None, "Upgrade designated regional/community responsible hospitals", "36"),
            ("D' 책임의료기관 중 ICU ≥10병상", None, None, "…restricted to ICUs with ≥10 beds", "29"),
            ("C 탐욕최적(ICU≥10병상)", 5, "65세이상", "Optimal selection (ICU ≥10 beds), 5 hospitals", "5"),
            ("C 탐욕최적(ICU≥10병상)", 10, "65세이상", "Optimal selection (ICU ≥10 beds), 10 hospitals", "10"),
            ("C 탐욕최적(ICU≥20병상)", 10, "65세이상", "Optimal selection (ICU ≥20 beds), 10 hospitals", "10"),
            ("상한: 모든 ICU 강화", None, None, "Upper bound: upgrade all 220 ICUs", "220")]
    for key, k, goal, lab, nf in alts:
        r = next(r for r in pol if r["대안"] == key and (k is None or (r["k"] == str(k) and r["목표"] == goal)))
        p, o = int(r["미도달인구"]), int(r["미도달65세이상"])
        rows.append(["B (2026, >60 min)", lab, nf, red(p, bp) if key != "현재" else f"{p:,}",
                     red(o, bo) if key != "현재" else f"{o:,}", "—"])
    write("table3_scenarios_policy", "Table 3. Population beyond 60 min of an ICU with a dedicated intensivist under ageing "
          "scenarios and policy alternatives", header, rows, [
              "Panel A: facilities and travel times held at 2026; October 2026 age structure of each administrative dong "
              "scaled by province- and age-specific growth from the 2022-based population projections (Statistics Korea). "
              "Panel B: 2026 population; an alternative assumes a dedicated intensivist is staffed in existing ICUs of the "
              "listed hospitals; optimal selection = greedy maximal coverage of residents aged ≥65 y. Responsible hospitals: "
              "Ministry of Health and Welfare designation list, March 2024. Unconnected islands excluded from reductions."])


def table_s1():
    import sys
    sys.path.insert(0, str(ROOT / "code"))
    import analyze_equity as eq
    fis = {r["KOSIS코드"]: float(r["재정자립도_2026"]) for r in rd(C / "fiscal_sgg.csv")}
    agg = defaultdict(lambda: defaultdict(float))
    for e in rd(C / "access_road_emd.csv"):
        a = agg[e["시군구코드_KOSIS"]]
        p, o = int(e["인구"]), int(e["65세이상"])
        far = float(e["전담ICU_분"]) > 60
        a["pop"] += p
        a["o65"] += o
        a["far"] += p * far
        a["far65"] += o * far
    units = [{"pop": a["pop"], "o65": a["o65"], "far": a["far"], "far65": a["far65"], "y": a["far"] / a["pop"],
              "y65": a["far65"] / a["o65"], "fis": fis[k], "aging": a["o65"] / a["pop"]} for k, a in agg.items()]
    header = ["Ranking variable", "Quintile", "Range", "Districts (n)", "Population", "Beyond 60 min, n (%)",
              "Aged ≥65 y population", "Aged ≥65 y beyond 60 min, n (%)"]
    rows = []
    for key, lab in (("fis", "Fiscal self-reliance (%)"), ("aging", "Population aged ≥65 y (%)")):
        q = eq.quint(units, key, ["far", "far65", "o65"])
        for k in range(5):
            v = q[k]
            rng = f"{v['lo']:.1f}–{v['hi']:.1f}" if key == "fis" else f"{100 * v['lo']:.1f}–{100 * v['hi']:.1f}"
            rows.append([lab, f"Q{k + 1}", rng, int(v["n"]), f"{int(v['pop']):,}",
                         f"{int(v['far']):,} ({100 * v['far'] / v['pop']:.1f})", f"{int(v['o65']):,}",
                         f"{int(v['far65']):,} ({100 * v['far65'] / v['o65']:.1f})"])
        rows.append([lab, "Concentration index", "—", len(units), "—", f"{eq.ci(units, key, 'y'):+.3f}".replace("-", "−"),
                     "—", f"{eq.ci(units, key, 'y65'):+.3f}".replace("-", "−")])
    write("tableS1_inequality", "Table S1. Population beyond 60 min of an ICU with a dedicated intensivist by district "
          "fiscal self-reliance and population ageing (256 districts)", header, rows, [
              "Districts (si/gun/gu analysis units) ranked by 2026 fiscal self-reliance (KOSIS e-local indicators; "
              "non-autonomous gu take the parent city value, Jeju administrative cities take the provincial value) or by "
              "share aged ≥65 y; population-weighted quintiles. Concentration index computed on district shares beyond "
              "60 min with population-weighted fractional ranks (negative = concentrated in low-fiscal districts; "
              "positive = concentrated in older districts)."])


def table_s2():
    """(2026-11-03 추가) 탐욕 최적 선택 k=1–20 누적 감소 — '왜 10곳인가' 대비. 값은 policy_road.csv 그대로."""
    pol = rd(ROOT / "output/policy_road.csv")
    base = next(r for r in pol if r["대안"] == "현재")
    bp, bo = int(base["미도달인구"]), int(base["미도달65세이상"])
    beds = defaultdict(list)
    for h in rd(C / "icu_hospitals.csv"):
        beds[(h["요양기관명"], h["시도_17"])].append(h["성인중환자병상수"])
    variants = [("C 탐욕최적(ICU≥10병상)", "65세이상", "Aged ≥65 y; candidate ICUs ≥10 beds (Table 3)"),
                ("C 탐욕최적(ICU≥20병상)", "65세이상", "Aged ≥65 y; candidate ICUs ≥20 beds (Table 3)"),
                ("C 탐욕최적(ICU≥0병상)", "65세이상", "Aged ≥65 y; any candidate ICU"),
                ("C 탐욕최적(ICU≥0병상)", "전체인구", "All ages; any candidate ICU")]
    # (2026-11-04) 영문 병원명: data/clean/hospital_names_en.csv (공식 누리집 확인 16 / 로마자 표기 12, 근거 URL 포함)
    en_p = C / "hospital_names_en.csv"
    en = {r["korean_name"]: r for r in rd(en_p)} if en_p.exists() else {}
    header = ["Objective; candidate pool", "k", "Hospital added", "Name source", "Hospital (Korean)", "Region",
              "Adult ICU beds (n)",
              "Remaining beyond 60 min, all ages, n", "Cumulative reduction, all ages (%)",
              "Remaining beyond 60 min, aged ≥65 y, n", "Cumulative reduction, aged ≥65 y (%)"]
    rows = []
    for key, goal, lab in variants:
        seq = [r for r in pol if r["대안"] == key and r["목표"] == goal]
        for r in sorted(seq, key=lambda r: int(r["k"])):
            p, o = int(r["미도달인구"]), int(r["미도달65세이상"])
            b = beds[(r["추가기관"], r["시도"])]
            assert len(b) == 1, (r["추가기관"], r["시도"], b)
            e = en.get(r["추가기관"])
            rows.append([lab, r["k"], e["english_name"] if e else "[CHECK]", e["source"] if e else "—", r["추가기관"],
                         EN[r["시도"]], b[0], f"{p:,}", f"{100 * (bp - p) / bp:.1f}",
                         f"{o:,}", f"{100 * (bo - o) / bo:.1f}"])
    write("tableS2_greedy_sequence", "Table S2. Stepwise greedy selection of existing ICUs for dedicated-intensivist "
          "staffing: population remaining beyond 60 min, k = 1–20", header, rows, [
              f"Baseline (2026, no change): {bp:,} residents of all ages and {bo:,} aged ≥65 y beyond 60 min of an ICU with "
              "a dedicated intensivist. At each step the existing ICU without a dedicated intensivist that brings the largest "
              "additional number of residents (of the stated objective group) within 60 min is added. With candidate ICUs "
              "of ≥20 beds, no further candidate added coverage after k = 12, so the sequence stops there. Residents of the "
              "six administrative dongs on islands not connected to the road network (8 676 residents) are kept as "
              "unreached in all steps. Hospital names: official = English name used on the hospital's (or its operator's) "
              "website; romanised = Revised Romanization of Korean where no English name was found; Korean names as "
              "registered with HIRA."])


def main():
    table1()
    table2()
    table3()
    table_s1()
    table_s2()
    print("ok")


if __name__ == "__main__":
    main()
