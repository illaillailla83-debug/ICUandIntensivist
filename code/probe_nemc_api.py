"""국립중앙의료원 응급의료기관 정보 API 접근 시험 (키는 .env DATA_GO_KR_KEY, 출력에서 마스킹).

사용: python -I -X utf8 code/probe_nemc_api.py <출력txt>
"""
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
key = next(l.split("=", 1)[1].strip() for l in (ROOT / ".env").read_text(encoding="utf-8-sig").splitlines()
           if l.startswith("DATA_GO_KR_KEY="))
BASES = ["https://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytListInfoInqire",
         "http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytListInfoInqire"]
out = []
for b in BASES:
    url = b + "?" + urllib.parse.urlencode({"serviceKey": key, "pageNo": 1, "numOfRows": 3})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "icu-access-research"}),
                                    timeout=60) as r:
            body = r.read().decode("utf-8", "replace")
        out.append(f"### {b}\nHTTP {r.status}\n{body[:2500]}")
    except urllib.error.HTTPError as e:
        out.append(f"### {b}\nHTTP {e.code}\n{e.read().decode('utf-8', 'replace')[:800]}")
    except Exception as e:
        out.append(f"### {b}\nERR {e!r}")
    time.sleep(1.1)
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(out).replace(key, "***"))
