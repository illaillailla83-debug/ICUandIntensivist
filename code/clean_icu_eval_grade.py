"""병원평가정보서비스 수집분에서 중환자실 등급(asmGrd19로 추정)을 ICU 기관 목록에 붙인다.

asmGrd19 = 중환자실로 본 근거 (code/analyze_asm_code_id.py, 2026-11-03):
  - ICU 기관 보유율 82%, ICU 없는 종합병원 보유율 2%(54곳 중 1곳)로 차이가 가장 큼
  - 상급종합 47/47, 종합병원 250/283이 보유하고 병원급은 0/32 (평가 대상이 종합병원급 이상인 것과 일치)
  - 등급이 있는 기관 297곳, 1등급 72곳(24%) ≈ 4차 평가 보도치(303곳, 1등급 68곳, 22.4%)
  -> 활용가이드 코드표로 확정하기 전까지 '추정'으로 표시
입력: data/raw/hira_eval_api_2026-11-03/asm_grades_long.csv, data/clean/icu_hospitals.csv
출력: data/clean/icu_eval_grade.csv
사용: python -I code/clean_icu_eval_grade.py
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/raw/hira_eval_api_2026-11-03/asm_grades_long.csv"
ICU_CODE = "asmGrd19"


def main():
    g = {}
    for r in csv.DictReader(open(SRC, encoding="utf-8-sig")):
        if r["item"] == ICU_CODE:
            g[r["ykiho"]] = r["value"]
    icu = list(csv.DictReader(open(ROOT / "data/clean/icu_hospitals.csv", encoding="utf-8-sig")))
    out = []
    for h in icu:
        v = g.get(h["암호화요양기호"], "")
        out.append({"암호화요양기호": h["암호화요양기호"], "요양기관명": h["요양기관명"],
                    "종별코드명": h["종별코드명"], "성인중환자병상수": h["성인중환자병상수"],
                    "icu_grade": v if v.isdigit() else "",
                    "icu_grade_status": "graded" if v.isdigit() else (v or "not_evaluated"),
                    "grade_source": f"hospAsmInfoService1 {ICU_CODE} (코드 의미 추정), 2026-11-03 수집"})
    with open(ROOT / "data/clean/icu_eval_grade.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"{len(out)}곳, 등급 있음 {sum(1 for r in out if r['icu_grade'])}")


if __name__ == "__main__":
    main()
