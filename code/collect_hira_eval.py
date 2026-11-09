"""심평원 병원평가정보서비스(getHospAsmInfo1)로 기관별 평가항목 등급을 수집한다.

대상: data/clean/icu_hospitals.csv의 성인 ICU 기관 전체
      + 대조군: 성인 ICU가 없는 종합병원 전체 (어느 asmGrd 코드가 중환자실인지 실증적으로 찾기 위함)
출력: data/raw/hira_eval_api_<YYYY-MM-DD>/asm_grades_long.csv  (ykiho, 코드, 등급 — 원응답 그대로)
      data/raw/hira_eval_api_<YYYY-MM-DD>/collect_log.txt
- 키는 .env의 DATA_GO_KR_KEY. 요청 간격 1.1초. 실패 시 최대 3회 재시도하고 로그에 남김.
- 재실행하면 이미 받은 ykiho는 건너뜀 (같은 날짜 폴더 기준).

사용: python -I code/collect_hira_eval.py
"""
import csv
import datetime as dt
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://apis.data.go.kr/B551182/hospAsmInfoService1/getHospAsmInfo1"
RAW_HOSP = ROOT / "data/raw/hira_2026-10/건강보험심사평가원_전국 병의원 및 약국 현황_20260930"
OUTDIR = ROOT / f"data/raw/hira_eval_api_{dt.date.today().isoformat()}"
FIELDS = ["ykiho", "group", "yadmNm", "clCdNm", "item", "value", "fetched_at"]


def load_key():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("DATA_GO_KR_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit(".env에 DATA_GO_KR_KEY가 없음")


def targets():
    icu = list(csv.DictReader(open(ROOT / "data/clean/icu_hospitals.csv", encoding="utf-8-sig")))
    icu_keys = {r["암호화요양기호"] for r in icu}
    out = [(r["암호화요양기호"], "icu") for r in icu]
    fac = RAW_HOSP / "3.의료기관별상세정보서비스_01_시설정보(2026.9.).csv"
    with open(fac, encoding="cp949", newline="") as f:
        for r in csv.DictReader(f):
            if r["종별코드명"] == "종합병원" and r["암호화요양기호"] not in icu_keys:
                out.append((r["암호화요양기호"], "control_noicu_general"))
    return out


def fetch(ykiho, key, log):
    q = urllib.parse.urlencode({"serviceKey": key, "ykiho": ykiho, "pageNo": 1, "numOfRows": 10})
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"{BASE}?{q}"), timeout=30) as r:
                body = r.read().decode("utf-8")
            root = ET.fromstring(body)
            code = root.findtext("header/resultCode")
            if code != "00":
                raise RuntimeError(f"resultCode={code} {root.findtext('header/resultMsg')}")
            return root.findall("body/items/item")
        except (urllib.error.URLError, RuntimeError, ET.ParseError, TimeoutError) as e:
            log.write(f"{dt.datetime.now().isoformat(timespec='seconds')} retry {attempt}/3 {ykiho[:20]}… {e!r}\n")
            log.flush()
            time.sleep(3 * attempt)
    return None


def main():
    OUTDIR.mkdir(parents=True, exist_ok=True)
    key = load_key()
    out_csv = OUTDIR / "asm_grades_long.csv"
    done = set()
    if out_csv.exists():
        done = {r["ykiho"] for r in csv.DictReader(open(out_csv, encoding="utf-8-sig"))}
    new_file = not out_csv.exists()
    tg = [t for t in targets() if t[0] not in done]
    with open(out_csv, "a", encoding="utf-8-sig", newline="") as f, \
            open(OUTDIR / "collect_log.txt", "a", encoding="utf-8") as log:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        log.write(f"{dt.datetime.now().isoformat(timespec='seconds')} start: {len(tg)} targets ({len(done)} already done)\n")
        n_fail = 0
        for i, (yk, grp) in enumerate(tg, 1):
            items = fetch(yk, key, log)
            now = dt.datetime.now().isoformat(timespec="seconds")
            if items is None:
                n_fail += 1
                log.write(f"{now} FAILED {yk}\n")
            elif not items:
                w.writerow({"ykiho": yk, "group": grp, "item": "(no_item)", "value": "", "fetched_at": now})
            else:
                for it in items:
                    base = {"ykiho": yk, "group": grp, "yadmNm": it.findtext("yadmNm"),
                            "clCdNm": it.findtext("clCdNm"), "fetched_at": now}
                    grades = [c for c in it if c.tag.startswith("asmGrd")]
                    if not grades:
                        w.writerow({**base, "item": "(no_grade)", "value": ""})
                    for c in grades:
                        w.writerow({**base, "item": c.tag, "value": c.text})
            f.flush()
            if i % 50 == 0:
                log.write(f"{now} progress {i}/{len(tg)}\n")
                log.flush()
            time.sleep(1.1)
        log.write(f"{dt.datetime.now().isoformat(timespec='seconds')} end: failed={n_fail}\n")
    print(f"done; failed={n_fail}; out={out_csv}")


if __name__ == "__main__":
    main()
