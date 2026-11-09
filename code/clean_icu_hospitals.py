"""심평원 병원정보서비스 + 시설정보를 암호화요양기호로 결합해 성인 ICU 보유 기관 목록을 만든다.

입력 (data/raw/hira_2026-10/..., cp949, 수정하지 않음)
  1.병원정보서비스(2026.9.).csv            : 기관명·종별·시도·시군구·주소·좌표·의사수
  3.의료기관별상세정보서비스_01_시설정보   : 성인/소아/신생아 중환자병상수 등
출력
  data/clean/icu_hospitals.csv              : 성인중환자병상수 >= 1 기관 (UTF-8 BOM)
  output/table_icu_by_sido_type.csv         : 시도 × 종별 기관 수·병상 수 (long)
  output/table_icu_by_sido.csv / _by_type.csv
  output/icu_hospitals_qc.md                : 결합·품질점검 로그

사용: python -I code/clean_icu_hospitals.py   (프로젝트 루트에서; 재실행 가능, 표준 라이브러리만 사용)
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/hira_2026-10/건강보험심사평가원_전국 병의원 및 약국 현황_20260930"
F_HOSP = RAW / "1.병원정보서비스(2026.9.).csv"
F_FAC = RAW / "3.의료기관별상세정보서비스_01_시설정보(2026.9.).csv"
CLEAN = ROOT / "data/clean"
OUT = ROOT / "output"
KEY = "암호화요양기호"
ICU_COLS = ["성인중환자병상수", "소아중환자병상수", "신생아중환자병상수"]

# 시도 표기 순서 (행정안전부 행정구역 순)
SIDO_ORDER = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원",
              "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
# 대한민국 대략적 경위도 범위 (좌표 이상치 점검용)
LON_RANGE, LAT_RANGE = (124.5, 132.0), (33.0, 38.7)


def read_csv(path):
    with open(path, encoding="cp949", newline="") as f:
        return list(csv.DictReader(f))


def to_int(s):
    s = (s or "").strip()
    return int(float(s)) if s else 0


def to_float(s):
    s = (s or "").strip()
    return float(s) if s else None


def sido17(sido_name, sgg_code):
    """2026.9. 자료는 광주를 '전남광주'(360000, 광주 5개 구=3608xx)로 통합 코딩하고 세종을 '세종시'로 표기한다.
    인구·장래추계(KOSIS)와 연결하기 위해 기존 17개 시도 체계로 되돌린 파생값을 만든다."""
    if sido_name in ("전남광주", "전남", "광주"):
        if sido_name == "광주" or sgg_code.startswith("3608") or sgg_code.startswith("24"):
            return "광주"
        return "전남"
    if sido_name == "세종시":
        return "세종"
    return sido_name


def sido_key(s):
    return SIDO_ORDER.index(s) if s in SIDO_ORDER else 99


def main():
    CLEAN.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    qc = []

    hosp = read_csv(F_HOSP)
    fac = read_csv(F_FAC)
    qc.append(f"- 병원정보서비스 행: {len(hosp):,} / 시설정보 행: {len(fac):,}")

    # 키 중복 점검
    for name, rows in [("병원정보", hosp), ("시설정보", fac)]:
        dup = [k for k, c in Counter(r[KEY] for r in rows).items() if c > 1]
        qc.append(f"- {name} {KEY} 중복 키: {len(dup)}")
        if dup:
            raise SystemExit(f"{name}에 중복 키 {len(dup)}개 — 결합 규칙 재검토 필요")

    hosp_by = {r[KEY]: r for r in hosp}
    fac_by = {r[KEY]: r for r in fac}
    only_fac = set(fac_by) - set(hosp_by)
    only_hosp = set(hosp_by) - set(fac_by)
    qc.append(f"- 시설정보에만 있는 키: {len(only_fac):,} (종별: "
              f"{dict(Counter(fac_by[k]['종별코드명'] for k in only_fac).most_common(5))})")
    qc.append(f"- 병원정보에만 있는 키: {len(only_hosp):,}")

    # 성인 ICU 보유 기관 (시설정보 기준) — 병원정보에 없으면 경고
    icu_fac = [r for r in fac if to_int(r["성인중환자병상수"]) >= 1]
    unmatched = [r for r in icu_fac if r[KEY] not in hosp_by]
    qc.append(f"- 시설정보 기준 성인중환자병상 ≥1 기관: {len(icu_fac):,}, 그중 병원정보 미매칭: {len(unmatched)}")
    for r in unmatched:
        qc.append(f"  - 미매칭: {r['요양기관명']} ({r['종별코드명']}, {r['시도코드명']}) 성인ICU {r['성인중환자병상수']}")

    records, mismatch = [], []
    for f in icu_fac:
        h = hosp_by.get(f[KEY])
        src = h if h else f  # 위치정보는 병원정보 우선, 없으면 시설정보
        if h:
            for c in ["요양기관명", "종별코드", "시도코드", "시군구코드"]:
                if h[c] != f[c]:
                    mismatch.append(f"{f['요양기관명']}: {c} 병원정보={h[c]} 시설정보={f[c]}")
        rec = {
            KEY: f[KEY],
            "요양기관명": src["요양기관명"],
            "종별코드": src["종별코드"],
            "종별코드명": src["종별코드명"],
            "설립구분코드명": f["설립구분코드명"],
            "시도코드": src["시도코드"],
            "시도코드명": src["시도코드명"],
            "시도_17": sido17(src["시도코드명"], src["시군구코드"]),
            "시군구코드": src["시군구코드"],
            "시군구코드명": src["시군구코드명"],
            "읍면동": src["읍면동"],
            "주소": src["주소"],
            "좌표X_경도": to_float(h["좌표(X)"]) if h else None,
            "좌표Y_위도": to_float(h["좌표(Y)"]) if h else None,
            "성인중환자병상수": to_int(f["성인중환자병상수"]),
            "소아중환자병상수": to_int(f["소아중환자병상수"]),
            "신생아중환자병상수": to_int(f["신생아중환자병상수"]),
            "총의사수": to_int(h["총의사수"]) if h else None,
            "의과전문의수": to_int(h["의과전문의 인원수"]) if h else None,
            "병원정보_매칭": "Y" if h else "N",
        }
        records.append(rec)
    qc.append(f"- 병원정보·시설정보 간 기관명/종별/시도/시군구 코드 불일치: {len(mismatch)}")
    qc += [f"  - {m}" for m in mismatch[:30]]

    # 좌표 점검
    no_xy = [r for r in records if r["좌표X_경도"] is None or r["좌표Y_위도"] is None]
    out_xy = [r for r in records if r not in no_xy and not (
        LON_RANGE[0] <= r["좌표X_경도"] <= LON_RANGE[1] and LAT_RANGE[0] <= r["좌표Y_위도"] <= LAT_RANGE[1])]
    qc.append(f"- 좌표 결측: {len(no_xy)}, 국내 범위 밖 좌표: {len(out_xy)}")
    qc += [f"  - 좌표 문제: {r['요양기관명']} ({r['시도코드명']}) X={r['좌표X_경도']} Y={r['좌표Y_위도']}"
           for r in no_xy + out_xy]

    # 이상치 점검: 큰 병상 수, 의원·요양병원 등 비전형 종별
    big = sorted(records, key=lambda r: -r["성인중환자병상수"])[:10]
    qc.append("- 성인 ICU 병상 상위 10개 기관: " + "; ".join(
        f"{r['요양기관명']}({r['성인중환자병상수']})" for r in big))
    atypical = [r for r in records if r["종별코드명"] not in ("상급종합", "종합병원", "병원")]
    qc.append(f"- 상급종합·종합병원·병원 외 종별의 성인 ICU 보유 기관: {len(atypical)}")
    qc += [f"  - {r['요양기관명']} ({r['종별코드명']}, {r['시도코드명']}) 성인ICU {r['성인중환자병상수']}"
           for r in atypical]
    sido_present = {r["시도_17"] for r in records}
    raw_sido = Counter(r["시도코드"] + " " + r["시도코드명"] for r in hosp)
    qc.append(f"- 원자료(병원정보 전체) 시도코드/명 분포: {dict(sorted(raw_sido.items()))}")
    qc.append("- 주의: 2026.9. 자료는 광주를 '전남광주'(360000; 광주 5개 구=3608xx)로 통합 코딩, 세종은 '세종시'. "
              "구 코드('240000 광주', '360000 전남') 잔존 행 존재. 집계는 파생 컬럼 시도_17(기존 17개 시도) 기준.")
    qc.append(f"- 성인 ICU 기관이 0개인 시도(시도_17 기준):{[s for s in SIDO_ORDER if s not in sido_present] or '없음'}")
    qc.append(f"- 시도명이 표준 17개 목록에 없는 값: {sorted(sido_present - set(SIDO_ORDER)) or '없음'}")

    records.sort(key=lambda r: (sido_key(r["시도_17"]), r["시군구코드"], -r["성인중환자병상수"]))
    with open(CLEAN / "icu_hospitals.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(records[0].keys()))
        w.writeheader()
        w.writerows(records)

    # ---- 집계표 ----
    def agg(keyfun):
        d = defaultdict(lambda: [0, 0, 0, 0])
        for r in records:
            a = d[keyfun(r)]
            a[0] += 1
            a[1] += r["성인중환자병상수"]
            a[2] += r["소아중환자병상수"]
            a[3] += r["신생아중환자병상수"]
        return d

    hdr = ["기관수", "성인중환자병상수", "소아중환자병상수", "신생아중환자병상수"]
    types = sorted({r["종별코드명"] for r in records},
                   key=lambda t: {"상급종합": 0, "종합병원": 1, "병원": 2}.get(t, 9))

    by_st = agg(lambda r: (r["시도_17"], r["종별코드명"]))
    with open(OUT / "table_icu_by_sido_type.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["시도", "종별"] + hdr)
        for (s, t), v in sorted(by_st.items(), key=lambda kv: (sido_key(kv[0][0]), types.index(kv[0][1]))):
            w.writerow([s, t] + v)

    total = [0, 0, 0, 0]
    for name, d, order in [("sido", agg(lambda r: r["시도_17"]), lambda k: sido_key(k)),
                           ("type", agg(lambda r: r["종별코드명"]), lambda k: types.index(k))]:
        with open(OUT / f"table_icu_by_{name}.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["시도" if name == "sido" else "종별"] + hdr)
            tot = [0, 0, 0, 0]
            for k in sorted(d, key=order):
                w.writerow([k] + d[k])
                tot = [a + b for a, b in zip(tot, d[k])]
            w.writerow(["전체"] + tot)
            total = tot

    # 시도 × 종별 교차표 (기관수 / 성인병상) — 마크다운
    md = ["| 시도 | " + " | ".join(f"{t} 기관/성인병상" for t in types) + " | 계 기관 | 계 성인병상 | 계 소아 | 계 신생아 |",
          "|---|" + "---:|" * (len(types) + 4)]
    by_s = agg(lambda r: r["시도_17"])
    for s in sorted(by_s, key=sido_key):
        cells = [f"{by_st[(s, t)][0]}/{by_st[(s, t)][1]}" if (s, t) in by_st else "0/0" for t in types]
        v = by_s[s]
        md.append(f"| {s} | " + " | ".join(cells) + f" | {v[0]} | {v[1]:,} | {v[2]} | {v[3]} |")
    by_t = agg(lambda r: r["종별코드명"])
    md.append("| **전체** | " + " | ".join(f"{by_t[t][0]}/{by_t[t][1]:,}" for t in types)
              + f" | **{total[0]}** | **{total[1]:,}** | **{total[2]}** | **{total[3]}** |")
    (OUT / "table_icu_by_sido_type.md").write_text(
        "# 시도 × 종별 성인 ICU 보유 기관 수 / 성인 중환자병상 수\n\n"
        "자료: 심평원 전국 병의원 및 약국 현황 2026.9. 기준 (시설정보 성인중환자병상수 ≥1 기관)\n\n"
        + "\n".join(md) + "\n", encoding="utf-8")

    (OUT / "icu_hospitals_qc.md").write_text(
        "# icu_hospitals.csv 결합·품질점검 로그\n\n" + "\n".join(qc) + "\n", encoding="utf-8")
    print(f"OK: {len(records)} 기관, 성인 ICU {total[1]:,} 병상")


if __name__ == "__main__":
    main()
