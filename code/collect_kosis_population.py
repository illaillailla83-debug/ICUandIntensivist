"""KOSIS 인구 자료 수집 (재실행 가능: 이미 받은 조각은 건너뜀).

1) 주민등록인구 101/DT_1B04005N: 읍면동·시군구·시도 × 5세 연령, 총인구(T2), 지정 월
   - 셀 4만 개 한도 때문에 시도별(최대 500개 지역코드씩)로 나눠 호출
2) 장래인구추계 시도 101/DT_1BPB001: 시나리오 4종 × 시도 × 5세 연령, 성 계, 2024–2042
3) 장래인구추계 시군구 101/DT_1BPB002E (e-지방지표): 시군구 × 5세 연령항목, 성 계, 2024–2042

출력: data/raw/kosis_<수집일>/{pop_DT_1B04005N_<월>/, proj_DT_1BPB001/, proj_DT_1BPB002E/}/*.json + collect_log.txt
사용: python -I -X utf8 code/collect_kosis_population.py [월 YYYYMM, 기본 202610] [수집일 폴더, 기본 오늘]
"""
import datetime
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kosis_common import ROOT, call, load_key  # noqa: E402

MONTH = sys.argv[1] if len(sys.argv) > 1 else "202610"
DAY = sys.argv[2] if len(sys.argv) > 2 else f"{datetime.date.today():%Y-%m-%d}"
OUT = ROOT / f"data/raw/kosis_{DAY}"
CHUNK = 200  # KOSIS URL 4000바이트 제한(코드 1개 ≈ 13바이트) — 500에서 오류 err 21 확인 후 축소


def fetch(path_json, params, key, log):
    if path_json.exists():
        log.append(f"SKIP {path_json.name}")
        return json.loads(path_json.read_text(encoding="utf-8"))
    res = call("Param/statisticsParameterData.do", dict(params, method="getList"), key, log)
    if isinstance(res, dict) and res.get("err") == "30":
        # 폐지·통합된 행정구역(예: 광주 29 → 전남광주 12)은 해당 월 자료가 없음 → 빈 결과로 보존
        res = []
        log.append(f"NODATA {path_json.name}")
    elif isinstance(res, dict) and res.get("err"):
        log.append(f"ERR {path_json.name} {res}")
        raise RuntimeError(f"{path_json.name}: {res}")
    path_json.parent.mkdir(parents=True, exist_ok=True)
    path_json.write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    log.append(f"SAVED {path_json.name} rows={len(res)}")
    return res


def main():
    key = load_key()
    log = [f"=== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} MONTH={MONTH}"]
    try:
        # 1) 주민등록인구
        meta = json.loads((OUT / "meta_DT_1B04005N_ITM.json").read_text(encoding="utf-8"))
        regions = [m for m in meta if m["OBJ_ID"] == "A"]
        tops = [m["ITM_ID"] for m in regions if len(m["ITM_ID"]) == 2 and m["ITM_ID"] != "00"]
        for top in tops:
            codes = [m["ITM_ID"] for m in regions if m["ITM_ID"][:2] == top]
            for i in range(0, len(codes), CHUNK):
                part = codes[i:i + CHUNK]
                fetch(OUT / f"pop_DT_1B04005N_{MONTH}/{top}_{i // CHUNK}.json",
                      {"orgId": "101", "tblId": "DT_1B04005N", "itmId": "T2", "objL1": "+".join(part),
                       "objL2": "ALL", "prdSe": "M", "startPrdDe": MONTH, "endPrdDe": MONTH}, key, log)
        # 2) 시도 장래인구 (5세 구간 코드는 메타에서 3자리 코드로 추림)
        pm = json.loads((OUT / "meta_DT_1BPB001_ITM.json").read_text(encoding="utf-8"))
        ages = [m["ITM_ID"] for m in pm if m["OBJ_ID"] == "YRE" and len(m["ITM_ID"]) == 3]
        fetch(OUT / "proj_DT_1BPB001/sido_2024_2042.json",
              {"orgId": "101", "tblId": "DT_1BPB001", "itmId": "T10", "objL1": "ALL", "objL2": "ALL",
               "objL3": "0", "objL4": "+".join(ages), "prdSe": "Y", "startPrdDe": "2024", "endPrdDe": "2042"},
              key, log)
        # 3) 시군구 장래인구
        for a, b in [("2024", "2028"), ("2029", "2033"), ("2034", "2038"), ("2039", "2042")]:
            fetch(OUT / f"proj_DT_1BPB002E/sgg_{a}_{b}.json",
                  {"orgId": "101", "tblId": "DT_1BPB002E", "itmId": "ALL", "objL1": "ALL", "objL2": "0",
                   "prdSe": "Y", "startPrdDe": a, "endPrdDe": b}, key, log)
        # 4) 재정자립도 (e-지방지표 101/DT_1YL20921, 세입과목 개편 후 T20) — 형평성 분석용
        fetch(OUT / "fiscal_DT_1YL20921/fiscal_2022_2026.json",
              {"orgId": "101", "tblId": "DT_1YL20921", "itmId": "T20", "objL1": "ALL",
               "prdSe": "Y", "startPrdDe": "2022", "endPrdDe": "2026"}, key, log)
    finally:
        with open(OUT / "collect_log.txt", "a", encoding="utf-8") as f:
            f.write("\n".join(log) + "\n")


if __name__ == "__main__":
    main()
