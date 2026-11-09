"""KOSIS 통계표 메타(TBL/ITM/PRD)를 data/raw/kosis_<날짜>/meta_<tbl>_<type>.json으로 보존하고 분류 요약을 출력.

사용: python -I -X utf8 code/collect_kosis_meta.py <요약txt> [tbl ...]
"""
import datetime
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kosis_common import ROOT, call, load_key  # noqa: E402

TABLES = sys.argv[2:] or ["DT_1B04005N", "DT_1BPB001", "DT_1BPB002E"]
OUTDIR = ROOT / f"data/raw/kosis_{datetime.date.today():%Y-%m-%d}"


def main():
    key = load_key()
    OUTDIR.mkdir(parents=True, exist_ok=True)
    log, summary = [], []
    for tbl in TABLES:
        for typ in ["TBL", "ITM", "PRD"]:
            res = call("statisticsData.do", {"method": "getMeta", "type": typ, "orgId": "101", "tblId": tbl}, key, log)
            (OUTDIR / f"meta_{tbl}_{typ}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            if typ == "TBL":
                summary.append(f"## {tbl}: {res[0].get('TBL_NM') if isinstance(res, list) else res}")
            elif typ == "PRD":
                summary.append(f"- 기간: {res}")
            else:
                if not isinstance(res, list):
                    summary.append(f"- ITM 오류: {res}")
                    continue
                objs = Counter((r["OBJ_ID"], r["OBJ_NM"]) for r in res)
                for (oid, onm), n in objs.items():
                    items = [r for r in res if r["OBJ_ID"] == oid]
                    sample = ", ".join(f"{r['ITM_ID']}={r['ITM_NM']}" for r in items[:40])
                    summary.append(f"- {oid} {onm}: {n}개 — {sample}")
                    if oid == "A":
                        lv = Counter(len(r["ITM_ID"]) for r in items)
                        summary.append(f"  - 코드 길이 분포: {dict(lv)}")
    (OUTDIR / "meta_log.txt").write_text("\n".join(log), encoding="utf-8")
    open(sys.argv[1], "w", encoding="utf-8").write("\n".join(summary))


if __name__ == "__main__":
    main()
