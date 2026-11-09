"""병원평가정보서비스 API 시험 호출: 오퍼레이션명과 응답 필드, 중환자실 항목이 있는지 확인한다.

사용: python -I code/probe_hira_eval_api.py <응답 저장 폴더>
- 키는 .env의 DATA_GO_KR_KEY에서 읽음 (코드에 넣지 않음).
- 요청 간격 1.1초 이상. 실패는 로그로 남김.
"""
import csv
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://apis.data.go.kr/B551182/hospAsmInfoService1"
# 정확한 오퍼레이션명을 몰라 후보를 차례로 시도
OPS = ["getHospAsmInfo1", "getHospAsmDtlGrdInfo1", "getHospAsmGrdInfo1", "getHospAsmDtlInfo1"]


def load_key():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATA_GO_KR_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(".env에 DATA_GO_KR_KEY가 없음")


def call(op, params, key):
    q = urllib.parse.urlencode({"serviceKey": key, **params})
    req = urllib.request.Request(f"{BASE}/{op}?{q}", headers={"User-Agent": "icu-access-research"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", errors="replace")
        except Exception as e:  # 네트워크 오류는 재시도
            print(f"  재시도 {attempt + 1}/3: {op} {e!r}")
            time.sleep(3)
    return None, "FAILED"


def main(outdir):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    key = load_key()
    rows = list(csv.DictReader(open(ROOT / "data/clean/icu_hospitals.csv", encoding="utf-8-sig")))
    # 종별마다 1곳씩 시험
    sample = {}
    for r in rows:
        sample.setdefault(r["종별코드명"], r)
    log = []
    op_ok = None
    for op in OPS:
        r = sample["상급종합"]
        status, body = call(op, {"ykiho": r["암호화요양기호"], "pageNo": 1, "numOfRows": 100}, key)
        (out / f"{op}_상급종합.xml").write_text(body, encoding="utf-8")
        log.append(f"{op} status={status} len={len(body)} head={body[:200]!r}")
        time.sleep(1.1)
        if status == 200 and "<item>" in body:
            op_ok = op
            break
    if op_ok:
        for t, r in sample.items():
            if t == "상급종합":
                continue
            status, body = call(op_ok, {"ykiho": r["암호화요양기호"], "pageNo": 1, "numOfRows": 100}, key)
            (out / f"{op_ok}_{t}.xml").write_text(body, encoding="utf-8")
            log.append(f"{op_ok} {t} {r['요양기관명']} status={status} len={len(body)}")
            time.sleep(1.1)
    (out / "probe_log.txt").write_text("\n".join(log), encoding="utf-8")
    print("\n".join(log))


if __name__ == "__main__":
    main(sys.argv[1])
