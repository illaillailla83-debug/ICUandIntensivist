"""KOSIS OpenAPI 공통 함수: .env 키 로드, 1초 간격 호출, 재시도 로그, 키 마스킹."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://kosis.kr/openapi/"
_last = [0.0]


def load_key(name="KOSIS_KEY"):
    for line in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines():
        if "=" in line and line.split("=", 1)[0].strip() == name:
            return line.split("=", 1)[1].strip()
    raise SystemExit(f".env에 {name}가 없습니다")


def mask(url, key):
    return url.replace(urllib.parse.quote(key, safe=""), "***").replace(key, "***")


def call(path, params, key, log=None, retries=3):
    """KOSIS 호출 → 파싱된 JSON. 호출 간격 ≥1.1초, 실패 시 재시도하고 log(list)에 기록."""
    q = dict(params, apiKey=key, format="json", jsonVD="Y")
    url = BASE + path + "?" + urllib.parse.urlencode(q)
    for attempt in range(1, retries + 1):
        wait = 1.1 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "icu-access-research"}),
                                        timeout=60) as r:
                raw = r.read().decode("utf-8")
            data = json.loads(raw)
            if log is not None:
                log.append(f"OK {mask(url, key)}")
            return data
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if log is not None:
                log.append(f"RETRY{attempt} {mask(url, key)} {e!r}")
            time.sleep(2 * attempt)
    raise RuntimeError(f"KOSIS 호출 실패: {mask(url, key)}")
