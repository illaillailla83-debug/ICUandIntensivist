"""시군구 재정자립도(e-지방지표 101/DT_1YL20921, 세입과목 개편 후) → KOSIS 분석단위 시군구(256개) 대응.

규칙
  - 같은 시도 안에서 자치단체 이름으로 매칭
  - 자치구가 아닌 일반구(수원 장안구 등): 상위 시 값
  - 제주시·서귀포시(행정시): 제주특별자치도 값 / 세종: 세종특별자치시 값
  - 인천 2026.7 개편 구: 재정자립도 2026 값이 개편 전 구 기준 → 이전 구 값으로 대체
    영종구←중구, 제물포구←중구·동구 평균, 서해구←서구, 검단구←서구 (표시: 비고)
입력: data/raw/kosis_2026-11-03/fiscal_DT_1YL20921/fiscal_2022_2026.json, data/clean/sgg_crosswalk.csv
출력: data/clean/fiscal_sgg.csv, output/fiscal_qc.md
사용: python -I -X utf8 code/clean_fiscal.py
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/kosis_2026-11-03/fiscal_DT_1YL20921/fiscal_2022_2026.json"
# KOSIS 주민등록 시도코드 → e-지방지표 시도코드
K2F = {"11": "11", "26": "21", "27": "22", "28": "23", "30": "25", "31": "26", "36": "29", "41": "31", "51": "32",
       "43": "33", "44": "34", "52": "35", "47": "37", "48": "38", "50": "39"}
INCHEON = {"영종구": ["중구"], "제물포구": ["중구", "동구"], "서해구": ["서구"], "검단구": ["서구"]}


def main():
    rows = json.loads(RAW.read_text(encoding="utf-8"))
    val = {}  # (year, code) → value
    name = {}
    for r in rows:
        val[(r["PRD_DE"], r["C1"])] = float(r["DT"])
        name[r["C1"]] = r["C1_NM"]
    xw = list(csv.DictReader(open(ROOT / "data/clean/sgg_crosswalk.csv", encoding="utf-8-sig")))

    out, qc = [], []
    for u in xw:
        s = u["KOSIS코드"][:2]
        if s == "12":
            fs = "1224" if u["시도_17"] == "광주" else "1236"
        else:
            fs = K2F[s]
        target = u["KOSIS상위"] or u["KOSIS이름"]
        note = "상위 시 값(일반구)" if u["KOSIS상위"] else ""
        codes = []
        if s == "36":
            codes, note = ["29"], "세종특별자치시"
        elif s == "50":
            codes, note = ["39"], "제주특별자치도 값(행정시)"
        elif s == "28" and u["KOSIS이름"] in INCHEON:
            codes = [c for c, n in name.items() if c.startswith(fs) and len(c) > len(fs) and n in INCHEON[u["KOSIS이름"]]]
            note = "2026.7 개편 전 구 값: " + "·".join(INCHEON[u["KOSIS이름"]])
        else:
            codes = [c for c, n in name.items() if c.startswith(fs) and len(c) > len(fs) and n == target]
        if not codes:
            qc.append(f"- 매칭 실패: {u['KOSIS시도']} {u['KOSIS상위']} {u['KOSIS이름']}")
        rec = {"KOSIS코드": u["KOSIS코드"], "시도_17": u["시도_17"], "KOSIS상위": u["KOSIS상위"], "KOSIS이름": u["KOSIS이름"],
               "재정자립도_단체": "|".join(name[c] for c in codes), "재정자립도_코드": "|".join(codes), "비고": note}
        for y in ("2024", "2025", "2026"):
            vs = [val[(y, c)] for c in codes if (y, c) in val]
            rec[f"재정자립도_{y}"] = round(sum(vs) / len(vs), 2) if vs else ""
        out.append(rec)
    with open(ROOT / "data/clean/fiscal_sgg.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    v26 = [r["재정자립도_2026"] for r in out if r["재정자립도_2026"] != ""]
    lines = ["# 재정자립도 대응 QC", "", f"- 분석단위 {len(out)}개, 2026 값 있음 {len(v26)}개",
             f"- 2026 범위 {min(v26)}–{max(v26)}, 비고 있는 단위 {sum(bool(r['비고']) for r in out)}개"] + (qc or ["- 매칭 실패 없음"])
    lines += ["", "## 비고 있는 단위"] + [f"- {r['시도_17']} {r['KOSIS상위']}{r['KOSIS이름']}: {r['비고']} → {r['재정자립도_2026']}"
                                     for r in out if r["비고"] and not r["비고"].startswith("상위")]
    (ROOT / "output/fiscal_qc.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:5] + qc))


if __name__ == "__main__":
    main()
