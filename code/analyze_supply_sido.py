"""Table 1: 시도별 성인 ICU 공급 지표 (인구 2026.10, ICU 2026.9., 전담전문의 4차 평가 khqa 수기기록).

정의
  - ICU 병상: 성인중환자병상수 (심평원 시설정보)
  - 전담전문의 ICU: khqa 4차 지표 '전담전문의 1인당 병상' 값이 있는 기관 (없음·미평가는 '없음' 취급)
  - 인구: 주민등록 2026.10, 시도_17 (광주·전남 분리)
입력: data/clean/{icu_hospitals, icu_intensivist_khqa, sgg_crosswalk}.csv
출력: output/table1_supply_sido.csv/.md, data/clean/supply_sgg.csv (시군구별 공급 — 지도·접근성 분석용)
사용: python -I -X utf8 code/analyze_supply_sido.py
"""
import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "data/clean"
ORDER = ["서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남",
         "경북", "경남", "제주"]
CAPITAL = {"서울", "인천", "경기"}


def rd(p):
    return list(csv.DictReader(open(p, encoding="utf-8-sig")))


def main():
    icu = rd(C / "icu_hospitals.csv")
    ints = {r["암호화요양기호"]: r for r in rd(C / "icu_intensivist_khqa.csv") if r["암호화요양기호"]}
    xw = rd(C / "sgg_crosswalk.csv")
    h2k = {}
    for r in xw:
        for code in r["HIRA시군구코드"].split("|"):
            h2k[code] = r
    log = []

    # 시군구 단위 공급
    sgg = {r["KOSIS코드"]: dict(r, ICU기관=0, ICU병상=0, 전담기관=0, 전담병상=0) for r in xw}
    for h in icu:
        k = h2k.get(h["시군구코드"])
        if k is None:
            log.append(f"대응 없음: {h['요양기관명']} {h['시군구코드']} {h['시군구코드명']} — 시도_17로만 집계")
            continue
        s = sgg[k["KOSIS코드"]]
        beds = int(h["성인중환자병상수"])
        has = ints.get(h["암호화요양기호"], {}).get("전담전문의_있음") == "1"
        s["ICU기관"] += 1
        s["ICU병상"] += beds
        s["전담기관"] += has
        s["전담병상"] += beds * has
        if k["시도_17"] != h["시도_17"]:
            log.append(f"시도 불일치: {h['요양기관명']} 병원 {h['시도_17']} vs 대응표 {k['시도_17']}")
    with open(C / "supply_sgg.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(next(iter(sgg.values()))))
        w.writeheader()
        w.writerows(sgg.values())

    # 시도 집계 (병원은 병원 자체의 시도_17로 셈 → 대응 실패 기관도 포함)
    agg = defaultdict(lambda: defaultdict(float))
    for r in xw:
        a = agg[r["시도_17"]]
        a["인구"] += int(r["인구"])
        a["65세이상"] += int(r["65세이상"])
        a["시군구"] += 1
    for s in sgg.values():
        a = agg[s["시도_17"]]
        a["ICU없는시군구"] += s["ICU병상"] == 0
        a["ICU없는시군구인구"] += int(s["인구"]) * (s["ICU병상"] == 0)
        a["전담ICU없는시군구"] += s["전담병상"] == 0
        a["전담ICU없는시군구인구"] += int(s["인구"]) * (s["전담병상"] == 0)
    for h in icu:
        a = agg[h["시도_17"]]
        beds = int(h["성인중환자병상수"])
        has = ints.get(h["암호화요양기호"], {}).get("전담전문의_있음") == "1"
        a["ICU기관"] += 1
        a["ICU병상"] += beds
        a["전담기관"] += has
        a["전담병상"] += beds * has

    def row(name, a):
        p, o = a["인구"], a["65세이상"]
        return {
            "시도": name, "인구": int(p), "65세이상비율(%)": round(100 * o / p, 1),
            "ICU기관": int(a["ICU기관"]), "성인ICU병상": int(a["ICU병상"]),
            "병상/인구10만": round(a["ICU병상"] / p * 1e5, 1), "병상/65세이상10만": round(a["ICU병상"] / o * 1e5, 1),
            "전담전문의ICU기관": int(a["전담기관"]), "전담전문의ICU병상": int(a["전담병상"]),
            "전담병상비율(%)": round(100 * a["전담병상"] / a["ICU병상"], 1) if a["ICU병상"] else 0,
            "전담병상/인구10만": round(a["전담병상"] / p * 1e5, 1),
            "전담병상/65세이상10만": round(a["전담병상"] / o * 1e5, 1),
            "시군구": int(a["시군구"]), "ICU없는시군구": int(a["ICU없는시군구"]),
            "ICU없는시군구인구비율(%)": round(100 * a["ICU없는시군구인구"] / p, 1),
            "전담ICU없는시군구": int(a["전담ICU없는시군구"]),
            "전담ICU없는시군구인구비율(%)": round(100 * a["전담ICU없는시군구인구"] / p, 1),
        }

    out = [row(s, agg[s]) for s in ORDER]
    for label, members in [("수도권", CAPITAL), ("비수도권", set(ORDER) - CAPITAL), ("전국", set(ORDER))]:
        t = defaultdict(float)
        for s in members:
            for k, v in agg[s].items():
                t[k] += v
        out.append(row(label, t))

    with open(ROOT / "output/table1_supply_sido.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    vals = [r["병상/인구10만"] for r in out[:17]]
    dvals = [r["전담병상/인구10만"] for r in out[:17]]
    md = ["# Table 1 (초안) 시도별 성인 중환자실 공급 지표", "",
          "인구 2026.10 주민등록, ICU 병상 2026.9. 심평원, 전담전문의 = 4차(2023) 적정성평가 지표값 있음(khqa 수기 기록).", "",
          "| " + " | ".join(out[0]) + " |", "|" + "---|" * len(out[0])]
    md += ["| " + " | ".join(f"{v:,}" if isinstance(v, int) else str(v) for v in r.values()) + " |" for r in out]
    md += ["", f"- 시도 간 병상/인구10만: 최소 {min(vals)} – 최대 {max(vals)} (배율 {max(vals) / min(vals):.1f})",
           f"- 시도 간 전담병상/인구10만: 최소 {min(dvals)} – 최대 {max(dvals)}"
           + (f" (배율 {max(dvals) / min(dvals):.1f})" if min(dvals) > 0 else " (0인 시도 있음)"),
           "- 'ICU 없는 시군구'는 행정구역 안에 기관이 없다는 뜻일 뿐 접근 불가를 뜻하지 않음(이동시간 분석은 별도).", ""]
    md += ["## 로그"] + (log or ["- 대응 실패·시도 불일치 없음"])
    (ROOT / "output/table1_supply_sido.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(log) or "ok")


if __name__ == "__main__":
    main()
