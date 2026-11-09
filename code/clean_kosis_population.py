"""KOSIS 인구 원자료(JSON)를 정제하고 합계를 검증한다.

입력: data/raw/kosis_2026-11-03/ (collect_kosis_population.py 산출, 수정 안 함)
출력:
  data/clean/pop_resident_202610.csv   행정구역(시도/시군구/구/읍면동) × 5세 연령 wide, 65+·80+ 합계 포함
  data/clean/proj_sido_5y.csv          시도 장래인구 long (시나리오, 시도, 연도, 연령)
  data/clean/proj_sgg_5y.csv           시군구 장래인구 long (e-지방지표)
  output/kosis_population_qc.md        계층 합계 검증·이상 보고
사용: python -I -X utf8 code/clean_kosis_population.py
"""
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/kosis_2026-11-03"
MONTH = "202610"
AGE_ORDER = ["0", "5", "10", "15", "20", "25", "30", "35", "40", "45", "50", "55", "60", "65", "70", "75", "80",
             "85", "90", "95", "100", "105"]


def load_rows(folder):
    rows = []
    for p in sorted(folder.glob("*.json")):
        rows += json.loads(p.read_text(encoding="utf-8"))
    return rows


def main():
    qc = ["# KOSIS 인구 자료 정제 QC", ""]
    meta = {m["ITM_ID"]: m for m in json.loads((RAW / "meta_DT_1B04005N_ITM.json").read_text(encoding="utf-8"))
            if m["OBJ_ID"] == "A"}
    age_nm = {m["ITM_ID"]: m["ITM_NM"] for m in json.loads((RAW / "meta_DT_1B04005N_ITM.json").read_text(encoding="utf-8"))
              if m["OBJ_ID"] == "B"}

    # ---------- 1) 주민등록인구 ----------
    rows = load_rows(RAW / f"pop_DT_1B04005N_{MONTH}")
    pop = defaultdict(dict)  # code → {age: n}
    names = {}
    for r in rows:
        if r["PRD_DE"] != MONTH:
            continue
        pop[r["C1"]][r["C2"]] = int(r["DT"]) if r["DT"] not in ("", "-") else 0
        names[r["C1"]] = r["C1_NM"]
    qc.append(f"## 주민등록인구 {MONTH} (101/DT_1B04005N)")
    qc.append(f"- 자료가 있는 지역코드: {len(pop)} (메타 4,822개 중; 나머지는 폐지·통합된 옛 코드)")
    miss_age = [c for c, a in pop.items() if set(a) != set(AGE_ORDER)]
    qc.append(f"- 연령 구간이 22개가 아닌 지역: {len(miss_age)}")
    bad_sum = [c for c, a in pop.items() if a.get("0", 0) != sum(v for k, v in a.items() if k != "0")]
    qc.append(f"- 연령 합 ≠ 계 인 지역: {len(bad_sum)} {bad_sum[:10]}")

    def parent(c):
        return meta[c].get("UP_ITM_ID") if c in meta else None

    def level(c):
        if len(c) == 2:
            return "시도"
        if len(c) == 10:
            return "읍면동"
        return "구" if len(parent(c) or "") == 5 else "시군구"

    # 분석용 시군구: 하위 '구'(자료 있음)가 있는 시는 구로, 없으면 시군구 그대로 (심평원 시군구 체계와 같음)
    has_gu = {parent(c) for c in pop if level(c) == "구"}
    out = []
    for c in sorted(pop):
        lv = level(c)
        sido = c[:2]
        p = parent(c)
        sgg5 = c if lv in ("시군구", "구") else (p if lv == "읍면동" else "")
        unit = ""
        if lv in ("시군구", "구"):
            unit = "Y" if (lv == "구" or c not in has_gu) else "N"
        a = pop[c]
        out.append({
            "코드": c, "수준": lv, "이름": names[c], "시도코드": sido, "시도명": names.get(sido, ""),
            "상위코드": p or "", "상위명": names.get(p, "") if p else "", "분석단위_시군구": unit,
            "읍면동_소속시군구": sgg5 if lv == "읍면동" else "",
            **{age_nm[k].replace(" ", ""): a.get(k, 0) for k in AGE_ORDER},
            "65세이상": sum(a.get(k, 0) for k in AGE_ORDER[14:]),
            "80세이상": sum(a.get(k, 0) for k in AGE_ORDER[17:]),
        })
    fields = list(out[0])
    with open(ROOT / f"data/clean/pop_resident_{MONTH}.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out)

    # 계층 합계 검증
    tot = lambda c: pop[c]["0"]  # noqa: E731
    sidos = [c for c in pop if len(c) == 2 and c != "00"]
    units = [o["코드"] for o in out if o["분석단위_시군구"] == "Y"]
    emds = [c for c in pop if len(c) == 10]
    nat = sum(tot(c) for c in sidos)
    qc.append(f"- 전국(시도 합): {nat:,}명 / 분석단위 시군구 {len(units)}개 합: {sum(tot(c) for c in units):,} / "
              f"읍면동 {len(emds)}개 합: {sum(tot(c) for c in emds):,}")
    if "00" in pop:
        qc.append(f"- 전국 코드(00) 값: {tot('00'):,}")
    qc += ["", "| 시도 | 인구 | 65세이상 | 고령화율 | 분석단위 시군구 수 | 시군구 합 일치 | 읍면동 수 | 읍면동 합 일치 |",
           "|---|---|---|---|---|---|---|---|"]
    for s in sorted(sidos):
        us = [u for u in units if u[:2] == s]
        es = [e for e in emds if e[:2] == s]
        o65 = sum(pop[s].get(k, 0) for k in AGE_ORDER[14:])
        qc.append(f"| {names[s]} | {tot(s):,} | {o65:,} | {o65 / tot(s):.1%} | {len(us)} | "
                  f"{'O' if sum(tot(u) for u in us) == tot(s) else sum(tot(u) for u in us) - tot(s)} | {len(es)} | "
                  f"{'O' if sum(tot(e) for e in es) == tot(s) else sum(tot(e) for e in es) - tot(s)} |")
    zero = [names[c] + "(" + c + ")" for c in units + emds if tot(c) == 0]
    qc.append(f"- 인구 0인 지역: {len(zero)} {zero[:20]}")

    # ---------- 2) 시도 장래인구 ----------
    prow = load_rows(RAW / "proj_DT_1BPB001")
    with open(ROOT / "data/clean/proj_sido_5y.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["시나리오코드", "시나리오", "시도코드", "시도명", "연도", "연령코드", "연령", "소계여부", "추계인구"])
        for r in prow:
            sub = "Y" if r["C4"] == "000" or r["C4_NM"] == "80세이상" else "N"
            w.writerow([r["C1"], r["C1_NM"].split("(")[0], r["C2"], r["C2_NM"], r["PRD_DE"], r["C4"], r["C4_NM"], sub,
                        r["DT"]])
    qc += ["", "## 시도 장래인구 (101/DT_1BPB001, 2022년 기준 추계, 최종갱신 " + prow[0]["LST_CHN_DE"] + ")"]
    by = defaultdict(int)
    for r in prow:
        if r["C1"] == "1" and r["C2"] == "00" and r["C4"] == "000":
            by[r["PRD_DE"]] = int(r["DT"])
    # '80세이상'은 80-84…100세 이상의 소계라 합산에서 제외 (1차 실행에서 65+가 26.4%로 이중계산된 것 확인)
    o65 = defaultdict(int)
    for r in prow:
        if r["C1"] == "1" and r["C2"] == "00" and r["C4"] != "000" and r["C4_NM"] != "80세이상":
            lo = int(r["C4_NM"].split("-")[0].replace("세 이상", "").replace("세", "").strip())
            if lo >= 65:
                o65[r["PRD_DE"]] += int(r["DT"])
    for y in ("2026", "2030", "2035", "2040"):
        if y in by:
            qc.append(f"- 중위 {y}: 전국 {by[y]:,}명, 65세 이상 {o65[y]:,} ({o65[y] / by[y]:.1%})")
    sido_codes = sorted({(r["C2"], r["C2_NM"]) for r in prow})
    qc.append(f"- 시도 목록({len(sido_codes)}): " + ", ".join(f"{c}={n}" for c, n in sido_codes))
    ages = sorted({(r["C4"], r["C4_NM"]) for r in prow})
    qc.append(f"- 연령 구간({len(ages)}): " + ", ".join(n for _, n in ages))

    # ---------- 3) 시군구 장래인구 ----------
    srow = load_rows(RAW / "proj_DT_1BPB002E")
    with open(ROOT / "data/clean/proj_sgg_5y.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["지역코드", "지역명", "연도", "항목코드", "항목", "추계인구"])
        for r in srow:
            w.writerow([r["C1"], r["C1_NM"], r["PRD_DE"], r["ITM_ID"], r["ITM_NM"], r["DT"]])
    regs = sorted({(r["C1"], r["C1_NM"]) for r in srow})
    qc += ["", "## 시군구 장래인구 (101/DT_1BPB002E, e-지방지표, 최종갱신 " + srow[0]["LST_CHN_DE"] + ")",
           f"- 지역 {len(regs)}개, 연도 {min(r['PRD_DE'] for r in srow)}–{max(r['PRD_DE'] for r in srow)}"]
    t26 = {r["C1"]: int(r["DT"]) for r in srow if r["PRD_DE"] == "2026" and r["ITM_ID"] == "T10"}
    tops = {c: n for c, n in regs if len(c) == 2}
    qc.append("- 2026 시도 합계: " + ", ".join(f"{tops[c]} {t26.get(c, 0):,}" for c in sorted(tops)))
    qc.append(f"- 2026 시도 합(전국): {sum(t26.get(c, 0) for c in tops):,}")
    qc.append("- 주의: 전남광주통합특별시(12) 아래에 광주(1224)와 구만 있고 전남 시군은 목록에 없음 → 전남 시군 추계는 이 표로 못 씀")

    (ROOT / "output/kosis_population_qc.md").write_text("\n".join(qc) + "\n", encoding="utf-8")
    print("done")


if __name__ == "__main__":
    main()
