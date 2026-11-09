"""khqa.kr 수기 기록(북마크릿) 결과를 검증하고 ICU 기관 목록(체크리스트 297곳)과 매칭한다.

입력: data/raw/khqa_manual_2026-11/khqa_manual_2026-11.xlsx (수정 안 함)
      docs/khqa_checklist.csv, data/clean/icu_eval_grade.csv
출력: data/clean/icu_intensivist_khqa.csv   (매칭된 기관별 지표)
      output/khqa_manual_qc.md                (누락·불일치·검증 보고)
사용: python -I -X utf8 code/clean_khqa_manual.py
"""
import csv
import difflib
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from inspect_xlsx import read_xlsx  # noqa: E402

XLSX = ROOT / "data/raw/khqa_manual_2026-11/khqa_manual_2026-11.xlsx"
CHECK = ROOT / "docs/khqa_checklist.csv"
GRADE = ROOT / "data/clean/icu_eval_grade.csv"
OUT = ROOT / "data/clean/icu_intensivist_khqa.csv"
QC = ROOT / "output/khqa_manual_qc.md"

# 요양기호 앞 2자리 → 가능한 시도. 요양기호는 옛 도 단위라 광역시가 도 코드를 공유함
# (31=경기·인천, 34=충남·대전·세종, 36=전남·광주, 37=경북·대구, 38=경남·울산) — 1차 실행에서 확인
YK_SIDO = {"11": {"서울"}, "21": {"부산"}, "31": {"경기", "인천"}, "32": {"강원"}, "33": {"충북"},
           "34": {"충남", "대전", "세종"}, "35": {"전북"}, "36": {"전남", "광주"},
           "37": {"경북", "대구"}, "38": {"경남", "울산"}, "39": {"제주"}}

PREFIX = re.compile(r"(의료법인|재단법인|사회복지법인|학교법인|사단법인|특수법인|의료재단|의료사단|"
                    r"\(의\)|\(재\)|\(학\)|\(사\)|\(주\))")


def norm(name):
    s = re.sub(r"\s+", "", name)
    s = PREFIX.sub("", s)
    s = re.sub(r"[()\[\]·.,\-]", "", s)
    return s


def to_num(v):
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def main():
    rows = read_xlsx(XLSX)
    sheet = next(iter(rows.values()))
    head, data = sheet[0], [r + [""] * (len(sheet[0]) - len(r)) for r in sheet[1:] if any(r)]
    recs = [dict(zip(head, r)) for r in data]

    check = list(csv.DictReader(open(CHECK, encoding="utf-8-sig")))
    # 동명 기관이 있어(예: 현대병원 종합·병원 2곳) 기관명+주소로 암호화요양기호를 찾음
    hosp = {(r["요양기관명"], r["주소"]): r for r in
            csv.DictReader(open(ROOT / "data/clean/icu_hospitals.csv", encoding="utf-8-sig"))}

    log = [f"# khqa.kr 수기 기록 QC ({XLSX.name})", ""]
    log.append(f"- 기록 행: {len(recs)}, 체크리스트: {len(check)}곳")

    # 1) 기록 자체 점검
    yk_cnt = Counter(r["ykiho"] for r in recs)
    dups = {k: v for k, v in yk_cnt.items() if v > 1}
    log.append(f"- 중복 요양기호: {len(dups)} {dups if dups else ''}")
    yrs = Counter(r["asmYr"] for r in recs)
    log.append(f"- 평가연도: {dict(yrs)}")
    bad_avg = [r for r in recs if r["icu12010101"] and
               (to_num(r["icu12010301"]) != 22.0 or to_num(r["icu12010201"]) not in (20.3, 22.7))]
    log.append(f"- 평균값(전체 22.0, 상급 20.3/종합 22.7)이 다른 행: {len(bad_avg)}")
    ts = sorted(r["recorded_at"] for r in recs)
    log.append(f"- 기록 시각 범위(UTC): {ts[0]} ~ {ts[-1]}")

    # 2) 매칭: 정규화 이름 완전일치 → 유사도(같은 시도) 순
    by_norm = {}
    for c in check:
        by_norm.setdefault(norm(c["요양기관명"]), []).append(c)
    matched, used, fuzzy = {}, set(), []
    for r in recs:
        cands = by_norm.get(norm(r["yadmNm"]), [])
        cands = [c for c in cands if c["순번"] not in used]
        if len(cands) == 1:
            matched[r["ykiho"]] = cands[0]
            used.add(cands[0]["순번"])
    for r in recs:
        if r["ykiho"] in matched:
            continue
        sido = YK_SIDO.get(r["ykiho"][:2])
        pool = [c for c in check if c["순번"] not in used and (sido is None or c["시도"] in sido)]
        best = max(pool, key=lambda c: difflib.SequenceMatcher(None, norm(r["yadmNm"]), norm(c["요양기관명"])).ratio(),
                   default=None)
        if best:
            score = difflib.SequenceMatcher(None, norm(r["yadmNm"]), norm(best["요양기관명"])).ratio()
            fuzzy.append((r, best, score))
            # 이름이 다르면 자동 채택하지 않음: 0.86 동천동강병원↔동강병원처럼 다른 기관이 붙음
            if score >= 0.99:
                matched[r["ykiho"]] = best
                used.add(best["순번"])

    # 매칭 검증: 요양기호 시도 vs 체크리스트 시도, khqa 등급 vs API 등급
    sido_mis = [(r, matched[r["ykiho"]]) for r in recs if r["ykiho"] in matched
                and matched[r["ykiho"]]["시도"] not in YK_SIDO.get(r["ykiho"][:2], {matched[r["ykiho"]]["시도"]})]
    grade_mis = [(r, matched[r["ykiho"]]) for r in recs if r["ykiho"] in matched
                 and r["grade"] != matched[r["ykiho"]]["API등급(asmGrd19)"]]

    log += ["", "## 매칭 결과", f"- 매칭: {len(matched)} / 기록 {len(recs)}"]
    log.append(f"- 유사도 매칭(이름이 다름) {len(fuzzy)}건:")
    for r, c, s in fuzzy:
        tag = "채택" if r["ykiho"] in matched else "기각"
        log.append(f"  - [{tag} {s:.2f}] khqa `{r['yadmNm']}` ({r['ykiho']}) ↔ 목록 `{c['요양기관명']}` ({c['시도']} {c['시군구']})")
    log.append(f"- 시도 불일치(요양기호 앞자리 기준): {len(sido_mis)}")
    for r, c in sido_mis:
        log.append(f"  - {r['yadmNm']} {r['ykiho']} ↔ {c['요양기관명']} {c['시도']}")
    log.append(f"- 등급 불일치(khqa vs API asmGrd19): {len(grade_mis)}")
    for r, c in grade_mis:
        log.append(f"  - {r['yadmNm']}: khqa {r['grade']} vs API {c['API등급(asmGrd19)']}")

    unmatched_rec = [r for r in recs if r["ykiho"] not in matched]
    log.append(f"- 목록에 없는 기록: {len(unmatched_rec)}")
    for r in unmatched_rec:
        log.append(f"  - {r['yadmNm']} ({r['ykiho']}, 등급 {r['grade']})")

    missing = [c for c in check if c["순번"] not in used]
    log += ["", f"## 체크리스트 중 기록 없는 기관: {len(missing)}곳",
            "| 순번 | 우선순위 | 시도 | 시군구 | 요양기관명 | 종별 | 성인ICU병상 | API등급 |", "|---|---|---|---|---|---|---|---|"]
    for c in missing:
        log.append(f"| {c['순번']} | {c['우선순위']} | {c['시도']} | {c['시군구']} | {c['요양기관명']} | {c['종별']} | "
                   f"{c['성인ICU병상']} | {c['API등급(asmGrd19)']} |")

    # 3) 지표 요약과 보고서 대조
    out_rows = []
    for r in recs:
        c = matched.get(r["ykiho"])
        g = hosp[(c["요양기관명"], c["주소"])] if c else None
        v = to_num(r["icu12010101"])
        out_rows.append({
            "암호화요양기호": g["암호화요양기호"] if g else "",
            "요양기관명_HIRA": c["요양기관명"] if c else "",
            "요양기호_khqa": r["ykiho"], "요양기관명_khqa": r["yadmNm"],
            "종별": c["종별"] if c else "", "시도": c["시도"] if c else "", "시군구": c["시군구"] if c else "",
            "성인ICU병상": c["성인ICU병상"] if c else "",
            "평가연도": r["asmYr"], "등급": r["grade"],
            "전담전문의1인당병상": "" if v is None else v,
            "전담전문의_있음": "1" if v is not None else "0",
            "간호사1인당병상": to_num(r["icu12020101"]) if r["icu12020101"] else "",
            "장비시설수": r["icu12030101"], "감염관리": r["icu12080101"],
            "recorded_at": r["recorded_at"],
        })
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0]))
        w.writeheader()
        w.writerows(out_rows)

    log += ["", "## 지표 요약 (보고서 4차 대조: 전담전문의 있음 상급 45/45, 종합 97/258; 1인당 병상 평균 22.0·중앙값 18.3·범위 5.3–86.0)"]
    for t in ("상급종합", "종합병원", ""):
        sub = [o for o in out_rows if o["종별"] == t]
        if not sub:
            continue
        vals = [o["전담전문의1인당병상"] for o in sub if o["전담전문의1인당병상"] != ""]
        line = f"- {t or '(미매칭)'}: {len(sub)}곳, 전담전문의 있음 {len(vals)} ({len(vals) / len(sub):.1%})"
        if vals:
            line += f", 1인당 병상 평균 {statistics.mean(vals):.1f}, 중앙값 {statistics.median(vals):.1f}, 범위 {min(vals)}–{max(vals)}"
        log.append(line)
    allv = [o["전담전문의1인당병상"] for o in out_rows if o["전담전문의1인당병상"] != ""]
    log.append(f"- 전체: {len(out_rows)}곳, 있음 {len(allv)}, 평균 {statistics.mean(allv):.1f}, 중앙값 {statistics.median(allv):.1f}, "
               f"범위 {min(allv)}–{max(allv)}")
    nurse_odd = [o for o in out_rows if o["간호사1인당병상"] != "" and o["간호사1인당병상"] > 5]
    log.append(f"- 간호사 1인당 병상 이상값(>5): {[(o['요양기관명_khqa'], o['간호사1인당병상']) for o in nurse_odd]}")

    # 362개 성인 ICU 기관 전체에서의 병상 분포 (미평가 65곳 포함)
    icu = list(csv.DictReader(open(ROOT / "data/clean/icu_hospitals.csv", encoding="utf-8-sig")))
    has = {o["암호화요양기호"]: o["전담전문의_있음"] for o in out_rows if o["암호화요양기호"]}
    log += ["", "## 성인 ICU 362곳 기준 (2026.9 병상)", "| 종별 | 구분 | 기관 | 병상 |", "|---|---|---|---|"]
    agg = Counter()
    for h in icu:
        st = {"1": "전담전문의 있음", "0": "없음(평가 기준)"}.get(has.get(h["암호화요양기호"]), "미평가")
        agg[(h["종별코드명"], st, "n")] += 1
        agg[(h["종별코드명"], st, "b")] += int(h["성인중환자병상수"])
    for (t, st, k) in sorted({(a, b, "n") for a, b, _ in agg}):
        log.append(f"| {t} | {st} | {agg[(t, st, 'n')]} | {agg[(t, st, 'b')]:,} |")

    QC.write_text("\n".join(log) + "\n", encoding="utf-8")
    print(f"기록 {len(recs)}, 매칭 {len(matched)}, 누락 {len(missing)}, 미매칭 기록 {len(unmatched_rec)}")


if __name__ == "__main__":
    main()
