"""응급의료기관 지정 여부(심평원 특수진료정보 검색코드 '03 응급의료기관', 2026.9.) → ICU 기관에 결합.

한계: 지정 등급(권역센터/지역센터/지역기관)은 이 자료에 없음 → 국립중앙의료원 API(활용신청 필요)로 보완 예정.
입력: 심평원 10.특수진료정보, 4.세부정보(응급실 주간/야간 운영여부), data/clean/icu_hospitals.csv, icu_intensivist_khqa.csv
출력: data/clean/icu_emergency.csv (ICU 362곳 + 응급의료기관 여부), output/emergency_qc.md
사용: python -I -X utf8 code/clean_emergency.py
"""
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data/raw/hira_2026-10/건강보험심사평가원_전국 병의원 및 약국 현황_20260930"
K = "암호화요양기호"


def main():
    em = {r[K] for r in csv.DictReader(open(D / "10.의료기관별상세정보서비스_08_특수진료정보서비스(2026.9.).csv", encoding="cp949"))
          if r["검색코드"] == "03"}
    er = {r[K]: (r["응급실_주간_운영여부"], r["응급실_야간_운영여부"])
          for r in csv.DictReader(open(D / "4.의료기관별상세정보서비스_02_세부정보(2026.9.).csv", encoding="cp949"))}
    ints = {r[K] for r in csv.DictReader(open(ROOT / "data/clean/icu_intensivist_khqa.csv", encoding="utf-8-sig"))
            if r["전담전문의_있음"] == "1"}
    icu = list(csv.DictReader(open(ROOT / "data/clean/icu_hospitals.csv", encoding="utf-8-sig")))
    out = []
    for h in icu:
        k = h[K]
        out.append({K: k, "요양기관명": h["요양기관명"], "종별": h["종별코드명"], "시도_17": h["시도_17"],
                    "성인ICU병상": h["성인중환자병상수"], "전담전문의": "Y" if k in ints else "N",
                    "응급의료기관": "Y" if k in em else "N", "응급실_주간": er.get(k, ("", ""))[0],
                    "응급실_야간": er.get(k, ("", ""))[1]})
    with open(ROOT / "data/clean/icu_emergency.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    c = Counter((o["종별"], o["전담전문의"], o["응급의료기관"]) for o in out)
    lines = ["# 응급의료기관 결합 QC", "", f"- 심평원 '03 응급의료기관' 지정 {len(em)}곳 (전체 기관 기준)",
             f"- 성인 ICU 362곳 중 응급의료기관 {sum(o['응급의료기관'] == 'Y' for o in out)}곳",
             f"- 전담전문의 ICU 142곳 중 응급의료기관 {sum(o['응급의료기관'] == 'Y' and o['전담전문의'] == 'Y' for o in out)}곳",
             f"- 응급의료기관 지정인데 야간 응급실 '운영 안 함' 신고: {sum(o['응급의료기관'] == 'Y' and o['응급실_야간'] == 'N' for o in out)}곳",
             "", "| 종별 | 전담 | 응급의료기관 | 기관 수 |", "|---|---|---|---|"]
    lines += [f"| {t} | {i} | {e} | {n} |" for (t, i, e), n in sorted(c.items())]
    lines += ["", "## 전담전문의 ICU인데 응급의료기관 아님"] + \
             [f"- {o['시도_17']} {o['요양기관명']} ({o['종별']}, ICU {o['성인ICU병상']})" for o in out
              if o["전담전문의"] == "Y" and o["응급의료기관"] == "N"]
    (ROOT / "output/emergency_qc.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:6]))


if __name__ == "__main__":
    main()
