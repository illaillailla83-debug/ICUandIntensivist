"""심평원 시군구코드(2026.9.) ↔ KOSIS 분석단위 시군구(2026.10 주민등록, 258개) 대응표.

규칙(같은 시도 안에서만 매칭):
  - 이름 그대로 (서울 구, 도의 시·군)
  - 광역시 약칭 + 이름 (부산남구, 울산중구, 광주동구 …)
  - 상위 시 이름('시' 제외) + 구 이름 (고양덕양구, 창원마산합포구 …)
  - 세종: 세종특별자치시 ↔ 세종시
예외: 심평원 옛 광주코드(240001/240002)는 광주 구로, '화성시'(312500)처럼 구가 정해지지 않은 코드는 '모호'로 표시.

입력: data/raw/hira_2026-10/.../1.병원정보서비스(2026.9.).csv, data/clean/pop_resident_202610.csv
출력: data/clean/sgg_crosswalk.csv, output/sgg_crosswalk_qc.md
사용: python -I -X utf8 code/clean_sgg_crosswalk.py
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
F_HIRA = ROOT / "data/raw/hira_2026-10/건강보험심사평가원_전국 병의원 및 약국 현황_20260930/1.병원정보서비스(2026.9.).csv"
F_POP = ROOT / "data/clean/pop_resident_202610.csv"

# KOSIS 시도코드 → 심평원 시도코드(들)
K2H = {"11": ["110000"], "26": ["210000"], "27": ["230000"], "28": ["220000"], "30": ["250000"], "31": ["260000"],
       "36": ["410000"], "41": ["310000"], "51": ["320000"], "43": ["330000"], "44": ["340000"], "52": ["350000"],
       "12": ["360000", "240000"], "47": ["370000"], "48": ["380000"], "50": ["390000"]}
METRO = {"26": "부산", "27": "대구", "28": "인천", "30": "대전", "31": "울산", "12": "광주"}
GWANGJU_GU = {"동구", "서구", "남구", "북구", "광산구"}
SIDO17 = {"11": "서울", "26": "부산", "27": "대구", "28": "인천", "30": "대전", "31": "울산", "36": "세종", "41": "경기",
          "51": "강원", "43": "충북", "44": "충남", "52": "전북", "47": "경북", "48": "경남", "50": "제주"}
MANUAL = {"240001": "광주동구", "240002": "광주북구"}  # 옛 광주 코드 → 현 이름
AMBIGUOUS = {"312500"}  # 화성시(구 미지정)


def main():
    hira = {}  # 시군구코드 → (시도코드, 이름), 기관수
    nfac = Counter()
    with open(F_HIRA, encoding="cp949", newline="") as f:
        for r in csv.DictReader(f):
            hira.setdefault(r["시군구코드"], (r["시도코드"], r["시군구코드명"]))
            nfac[r["시군구코드"]] += 1
    pop = [r for r in csv.DictReader(open(F_POP, encoding="utf-8-sig")) if r["분석단위_시군구"] == "Y"]
    pop = [r for r in pop if int(r["계"]) > 0]  # 출장소 코드 제외

    by_name = defaultdict(list)  # (심평원 시도코드, 이름) → 코드
    for code, (sd, nm) in hira.items():
        nm2 = MANUAL.get(code, nm)
        by_name[(sd, nm2)].append(code)

    rows, used = [], set()
    for p in pop:
        s = p["시도코드"]
        nm, parent = p["이름"], p["상위명"]
        cands = {nm}
        if s in METRO:
            cands.add(METRO[s] + nm)
        if p["수준"] == "구":
            cands.add(parent.removesuffix("시") + nm)
        if s == "36":
            cands.add("세종시")
        codes = sorted({c for sd in K2H[s] for cand in cands for c in by_name.get((sd, cand), [])})
        if s == "12":
            sido17 = "광주" if (nm in GWANGJU_GU) else "전남"
        else:
            sido17 = SIDO17[s]
        used.update(codes)
        rows.append({"KOSIS코드": p["코드"], "KOSIS시도": p["시도명"], "KOSIS상위": parent if p["수준"] == "구" else "",
                     "KOSIS이름": nm, "시도_17": sido17, "HIRA시군구코드": "|".join(codes),
                     "HIRA시군구명": "|".join(hira[c][1] for c in codes), "HIRA기관수": sum(nfac[c] for c in codes),
                     "인구": p["계"], "65세이상": p["65세이상"], "80세이상": p["80세이상"]})
    with open(ROOT / "data/clean/sgg_crosswalk.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    qc = ["# 시군구 대응표 QC (심평원 2026.9. ↔ KOSIS 2026.10)", "",
          f"- KOSIS 분석단위 {len(rows)}개, 심평원 고유 시군구코드 {len(hira)}개"]
    nomatch = [r for r in rows if not r["HIRA시군구코드"]]
    multi = [r for r in rows if "|" in r["HIRA시군구코드"]]
    qc.append(f"- 심평원 코드가 없는 KOSIS 단위: {len(nomatch)} " +
              ", ".join(f"{r['KOSIS시도']} {r['KOSIS상위']}{r['KOSIS이름']}({r['인구']}명)" for r in nomatch))
    qc.append(f"- 심평원 코드가 2개 이상인 KOSIS 단위: {len(multi)} " +
              ", ".join(f"{r['KOSIS이름']}={r['HIRA시군구명']}({r['HIRA시군구코드']})" for r in multi))
    left = sorted(set(hira) - used)
    qc.append(f"- KOSIS 단위에 붙지 않은 심평원 코드: {len(left)} " +
              ", ".join(f"{c} {hira[c][1]}({nfac[c]}곳){' [모호: 구 미지정]' if c in AMBIGUOUS else ''}" for c in left))
    s17 = Counter(r["시도_17"] for r in rows)
    qc.append("- 시도_17별 단위 수: " + ", ".join(f"{k} {v}" for k, v in sorted(s17.items())))
    (ROOT / "output/sgg_crosswalk_qc.md").write_text("\n".join(qc) + "\n", encoding="utf-8")
    print(f"단위 {len(rows)}, 미매칭 {len(nomatch)}, 다중 {len(multi)}, 남은 심평원코드 {len(left)}")


if __name__ == "__main__":
    main()
