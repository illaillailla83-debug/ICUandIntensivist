"""책임의료기관(2024.3 복지부 보도참고자료 붙임2, 수기 전사) ↔ 심평원 기관(2026.9.) 매칭 + ICU·전담 여부.

매칭: 같은 시도_17 안에서, 공백·법인 접두어를 지운 기관명에 '검색키'가 들어가는 병원급 이상 기관.
       후보가 여럿이면 모두 나열하고 ICU 보유 기관 > 종별 높은 순으로 1곳 선택(QC에 표시).
입력: data/clean/responsible_hospitals_202403.csv, 심평원 1.병원정보서비스(2026.9.), data/clean/icu_hospitals.csv,
      data/clean/icu_intensivist_khqa.csv
출력: data/clean/responsible_hospitals_matched.csv, output/responsible_qc.md
사용: python -I -X utf8 code/clean_responsible.py
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "code"))
from clean_icu_hospitals import sido17  # noqa: E402

F_HOSP = ROOT / "data/raw/hira_2026-10/건강보험심사평가원_전국 병의원 및 약국 현황_20260930/1.병원정보서비스(2026.9.).csv"
TYPES = {"상급종합": 0, "종합병원": 1, "병원": 2}


def norm(s):
    s = re.sub(r"\s+", "", s)
    return re.sub(r"(의료법인|재단법인|사회복지법인|학교법인|특수법인|\(의\)|\(재\)|\(학\))", "", s)


def main():
    resp = list(csv.DictReader(open(ROOT / "data/clean/responsible_hospitals_202403.csv", encoding="utf-8-sig")))
    icu = {r["암호화요양기호"]: r for r in csv.DictReader(open(ROOT / "data/clean/icu_hospitals.csv", encoding="utf-8-sig"))}
    ints = {r["암호화요양기호"] for r in csv.DictReader(open(ROOT / "data/clean/icu_intensivist_khqa.csv", encoding="utf-8-sig"))
            if r["전담전문의_있음"] == "1"}
    hosp = []
    with open(F_HOSP, encoding="cp949", newline="") as f:
        for r in csv.DictReader(f):
            if r["종별코드명"] in TYPES:
                r["시도_17"] = sido17(r["시도코드명"], r["시군구코드"])
                hosp.append(r)

    out, qc = [], []
    for e in resp:
        if e["구분"] == "미지정":
            out.append({**e, "요양기관명": "", "종별": "", "시군구": "", "암호화요양기호": "", "ICU보유": "", "성인ICU병상": "",
                        "전담전문의": "", "후보수": 0})
            continue
        parts = [norm(p) for p in e["검색키"].split("&")]  # '&' = 모든 부분 포함

        def hit(h):
            return all(p in norm(h["요양기관명"]) for p in parts)

        cands = [h for h in hosp if h["시도_17"] == e["시도"] and hit(h)]
        if not cands:  # 예: 칠곡경북대병원은 경북 권역이지만 소재지는 대구
            cands = [h for h in hosp if hit(h)]
        # 정렬: 이름 완전일치 > ICU 보유 > 종별 높은 순
        cands.sort(key=lambda h: (norm(h["요양기관명"]) != parts[0] or len(parts) > 1,
                                  h["암호화요양기호"] not in icu, TYPES[h["종별코드명"]]))
        if len(cands) != 1:
            qc.append(f"- {e['구분']} {e['시도']} {e['진료권']} `{e['기관명_보도자료']}`: 후보 {len(cands)} — " +
                      ", ".join(f"{h['요양기관명']}({h['종별코드명']}{', ICU' if h['암호화요양기호'] in icu else ''})" for h in cands[:6]))
        h = cands[0] if cands else None
        k = h["암호화요양기호"] if h else ""
        out.append({**e, "요양기관명": h["요양기관명"] if h else "", "종별": h["종별코드명"] if h else "",
                    "시군구": h["시군구코드명"] if h else "", "암호화요양기호": k,
                    "ICU보유": ("Y" if k in icu else "N") if h else "", "성인ICU병상": icu[k]["성인중환자병상수"] if k in icu else "",
                    "전담전문의": ("Y" if k in ints else "N") if k in icu else "", "후보수": len(cands)})
    with open(ROOT / "data/clean/responsible_hospitals_matched.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    lines = ["# 책임의료기관 매칭 QC (2024.3 명단 ↔ 심평원 2026.9.)", ""]
    for g in ("권역", "지역"):
        sub = [o for o in out if o["구분"] == g]
        lines.append(f"- {g} {len(sub)}곳: 매칭 {sum(bool(o['요양기관명']) for o in sub)}, ICU 보유 {sum(o['ICU보유'] == 'Y' for o in sub)}, "
                     f"그중 전담전문의 {sum(o['전담전문의'] == 'Y' for o in sub)}")
    lines.append(f"- 미지정 중진료권 {sum(o['구분'] == '미지정' for o in out)}곳")
    lines += ["", "## 후보가 1곳이 아닌 경우 (확인 필요)"] + (qc or ["- 없음"])
    lines += ["", "## 지역 책임의료기관 중 ICU 없음"] + \
             [f"- {o['시도']} {o['진료권']} {o['요양기관명'] or o['기관명_보도자료']} ({o['종별']})" for o in out
              if o["구분"] == "지역" and o["ICU보유"] != "Y"]
    lines += ["", "## 책임의료기관 중 ICU 있고 전담전문의 없음 (정책 대안 후보)"] + \
             [f"- {o['구분']} {o['시도']} {o['진료권']} {o['요양기관명']} (ICU {o['성인ICU병상']}병상)" for o in out
              if o["ICU보유"] == "Y" and o["전담전문의"] == "N"]
    (ROOT / "output/responsible_qc.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:6]))


if __name__ == "__main__":
    main()
