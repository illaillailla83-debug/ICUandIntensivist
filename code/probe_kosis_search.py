"""KOSIS 통계표 검색 결과를 UTF-8 파일로 저장 (표 ID 찾기용).

사용: python -I -X utf8 code/probe_kosis_search.py <출력txt> <검색어> [<검색어> ...]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kosis_common import call, load_key  # noqa: E402

key = load_key()
out = []
for nm in sys.argv[2:]:
    try:
        res = call("statisticsSearch.do", {"method": "getList", "searchNm": nm, "startCount": 1, "resultCount": 30}, key)
    except RuntimeError as e:
        res = str(e)
    out.append(f"### {nm}")
    if isinstance(res, list):
        for r in res:
            out.append(f"{r.get('ORG_ID')}/{r.get('TBL_ID')}\t{r.get('TBL_NM')}\t{r.get('STRT_PRD_DE')}-{r.get('END_PRD_DE')}\t{r.get('STAT_NM')}\t{r.get('ORG_NM')}")
    else:
        out.append(json.dumps(res, ensure_ascii=False)[:300])
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(out))
