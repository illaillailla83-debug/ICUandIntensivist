"""Table S3: 최적 선택(탐욕, ICU ≥10병상, 65세 이상 목표) 상위 20곳 × 책임의료기관 지정(2024.3). 2026-11-04

목적: Discussion의 "책임의료기관망이 자연스러운 수단" 서술 점검 — 최적으로 고른 기관이 실제로 지정 기관인지.
변경(2026-11-04): 부록 번호가 정해져 tableS2b(한글) → tableS3(영문)으로 바꿈. 영문 병원명은
  data/clean/hospital_names_en.csv(공식 누리집 > HIRA 영문 > 로마자 표기 순, 출처 열 포함)가 있으면 붙임.
입력: output/policy_road.csv, data/clean/{icu_hospitals, responsible_hospitals_matched, responsible_hospitals_202403,
      hospital_names_en(선택)}.csv
출력: output/tables/tableS3_greedy_responsible.md/.csv
사용: python -I -X utf8 code/analyze_greedy_responsible.py
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
PROV = {"서울": "Seoul", "부산": "Busan", "대구": "Daegu", "인천": "Incheon", "광주": "Gwangju", "대전": "Daejeon",
        "울산": "Ulsan", "세종": "Sejong", "경기": "Gyeonggi", "강원": "Gangwon", "충북": "Chungbuk", "충남": "Chungnam",
        "전북": "Jeonbuk", "전남": "Jeonnam", "경북": "Gyeongbuk", "경남": "Gyeongnam", "제주": "Jeju"}
# HIRA 설립구분 → 영문 (표 각주에 'HIRA classification'으로 명시)
OWN = {"개인": "Individually owned", "의료법인": "Medical corporation", "재단법인": "Non-profit foundation",
       "학교법인": "Educational foundation", "공립": "Public", "국립": "National",
       "특수법인": "Special corporation", "사회복지법인": "Social welfare corporation", "군병원": "Military"}
# 이 표에 나오는 시군구 (국어의 로마자 표기법)
DIST = {"순천시": "Suncheon", "안동시": "Andong", "해남군": "Haenam", "남원시": "Namwon", "태백시": "Taebaek",
        "문경시": "Mungyeong", "거제시": "Geoje", "고흥군": "Goheung", "서산시": "Seosan", "삼척시": "Samcheok",
        "속초시": "Sokcho", "포천시": "Pocheon", "영월군": "Yeongwol", "무안군": "Muan", "김천시": "Gimcheon",
        "영주시": "Yeongju", "목포시": "Mokpo", "영천시": "Yeongcheon", "충주시": "Chungju", "정읍시": "Jeongeup"}
AREA = {"남원권": "Namwon area", "서산권": "Seosan area", "동해권": "Donghae area", "포천시": "Pocheon",
        "영월권": "Yeongwol area", "구미권": "Gumi area", "영주권": "Yeongju area"}


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def main():
    pol = [r for r in rd(ROOT / "output/policy_road.csv") if r["대안"] == "C 탐욕최적(ICU≥10병상)" and r["목표"] == "65세이상"]
    icu = {(h["요양기관명"], h["시도_17"]): h for h in rd(C / "icu_hospitals.csv")}
    resp = {r["암호화요양기호"]: r for r in rd(C / "responsible_hospitals_matched.csv") if r["암호화요양기호"]}
    # 미지정 중진료권의 소속 시군구 (연구자 제공본; 일부 진료권은 '시군구 구성 확인 필요' 비고가 있음)
    undesig_sgg = {}
    for r in rd(ROOT / "data/raw/책임의료기관_지정현황_2024.csv"):
        if r["지정여부"].startswith("미지정"):
            for s in r["중진료권_시군구"].split("·"):
                undesig_sgg[(r["시도"], s.strip())] = (r["중진료권"], r["비고"])
    en_p = C / "hospital_names_en.csv"
    en = {r["korean_name"]: r for r in rd(en_p)} if en_p.exists() else {}
    rows, flagged = [], []
    for r in sorted(pol, key=lambda r: int(r["k"])):
        h = icu[(r["추가기관"], r["시도"])]
        d = resp.get(h["암호화요양기호"])
        sgg = h["시군구코드명"]
        if d:
            des = f"{'Regional' if d['구분'] == '권역' else 'Community'} ({AREA.get(d['진료권'], d['진료권'])})"
        else:
            des = "Not designated"
            u = undesig_sgg.get((r["시도"], sgg))
            if u:
                des += " (care area without a designated hospital)"
                flagged.append(f"{sgg}: {u[0]}" + (f" — 비고 '{u[1]}'" if u[1] else ""))
        e = en.get(r["추가기관"])
        rows.append([r["k"], e["english_name"] if e else "[CHECK]", (e["source"] if e else "—"), r["추가기관"],
                     PROV[r["시도"]], DIST[sgg], OWN[h["설립구분코드명"]], h["성인중환자병상수"], des])
    hdr = ["k", "Hospital", "Name source", "Hospital (Korean)", "Province", "District", "Ownership (HIRA)",
           "Adult ICU beds (n)", "Responsible-hospital designation (March 2024)"]
    with open(ROOT / "output/tables/tableS3_greedy_responsible.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(hdr)
        w.writerows(rows)
    n5 = sum(not r[8].startswith("Not") for r in rows[:5])
    n10 = sum(not r[8].startswith("Not") for r in rows[:10])
    md = ["# Table S3. Optimal selection of existing ICUs (candidate ICUs ≥10 beds; objective: residents aged ≥65 y "
          "beyond 60 min) and responsible-hospital designation (March 2024)", "",
          "| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows]
    md += ["", f"Sequence as in appendix table S2. Designation from the Ministry of Health and Welfare list of 27 March 2024 "
           f"(17 regional and 55 community responsible hospitals; 15 medium-sized care areas without a designated hospital). "
           f"Of the five best-placed hospitals {n5} was a designated responsible hospital; of the ten, {n10}. Ownership is "
           f"HIRA's establishment classification. Name source: official = the hospital's own website; HIRA = HIRA English "
           f"hospital information; romanised = Revised Romanization of Korean (no official English name found)."]
    (ROOT / "output/tables/tableS3_greedy_responsible.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[2:10]))
    print("미지정 진료권 소속:", flagged)
    print(f"top5 designated {n5}, top10 {n10}; English names {'from ' + str(en_p) if en else 'not yet available'}")


if __name__ == "__main__":
    main()
