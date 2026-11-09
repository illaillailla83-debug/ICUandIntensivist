"""KOSIS 통계표 후보 확인: 통계표 검색과 메타(표 이름·분류·항목) 조회 결과를 UTF-8 파일로 저장.

사용: python -I -X utf8 code/probe_kosis.py <출력txt>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # -I 실행 시에도 kosis_common 찾기
from kosis_common import call, load_key  # noqa: E402

key = load_key()
out, log = [], []

for nm in ["시군구별 5세별 주민등록인구", "장래인구추계 시도 성 연령별 추계인구"]:
    try:
        res = call("statisticsSearch.do", {"method": "getList", "searchNm": nm, "startCount": 1, "resultCount": 15},
                   key, log)
    except RuntimeError as e:
        res = str(e)
    out.append(f"### 검색: {nm}")
    if isinstance(res, list):
        for r in res:
            out.append(f"{r.get('ORG_ID')}/{r.get('TBL_ID')}\t{r.get('TBL_NM')}\t{r.get('STRT_PRD_DE')}-{r.get('END_PRD_DE')}\t{r.get('STAT_NM')}")
    else:
        out.append(json.dumps(res, ensure_ascii=False)[:500])

for org, tbl in [("101", "DT_1B04005N")]:
    for typ in ["TBL", "ITM", "PRD"]:
        try:
            res = call("statisticsData.do", {"method": "getMeta", "type": typ, "orgId": org, "tblId": tbl}, key, log)
        except RuntimeError as e:
            res = str(e)
        out.append(f"### 메타 {org}/{tbl} {typ}")
        out.append(json.dumps(res, ensure_ascii=False)[:3000])

open(sys.argv[1], "w", encoding="utf-8").write("\n".join(out + ["", "## log"] + log))
