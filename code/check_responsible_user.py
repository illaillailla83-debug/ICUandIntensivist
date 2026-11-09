"""연구자 제공 책임의료기관 파일(data/raw/책임의료기관_지정현황_2024.csv)과 복지부 PDF 전사본(data/clean/responsible_hospitals_202403.csv) 대조.

사용: python -I -X utf8 code/check_responsible_user.py <출력txt>
"""
import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def norm(s):
    s = re.sub(r"\s+|\(.*?\)", "", s or "")
    for a in ("서울특별시", "강원도", "충청남도", "충청북도", "경상북도", "경상남도", "경기도의료원", "근로복지공단", "국민건강보험"):
        s = s.replace(a, "")
    return s.replace("대학교", "대").replace("학교", "")


user = list(csv.DictReader(open(ROOT / "data/raw/책임의료기관_지정현황_2024.csv", encoding="utf-8-sig")))
mine = list(csv.DictReader(open(ROOT / "data/clean/responsible_hospitals_202403.csv", encoding="utf-8-sig")))
out = [f"연구자 파일 {len(user)}행, 전사본 {len(mine)}행"]
for g_u, g_m in (("권역책임의료기관", "권역"), ("지역책임의료기관", "지역")):
    u = [r for r in user if r["구분"] == g_u]
    out.append(f"{g_m}: 연구자 지정 {sum(r['지정여부'] == '지정' for r in u)}, 미지정 {sum(r['지정여부'] != '지정' for r in u)} / "
               f"전사본 {sum(r['구분'] == g_m for r in mine)}")
key_m = {(r["시도"], r["진료권"] if r["구분"] != "권역" else "권역"): r for r in mine}
alias = {"강릉권": "강릉시"}
for r in user:
    k = (r["시도"], "권역" if r["구분"] == "권역책임의료기관" else alias.get(r["중진료권"], r["중진료권"]))
    m = key_m.get(k)
    if m is None:
        out.append(f"전사본에 없음: {k} {r['기관명']}")
        continue
    a, b = norm(r["기관명"]), norm(m["기관명_보도자료"])
    if (r["지정여부"] == "지정") != (m["구분"] != "미지정"):
        out.append(f"지정여부 다름: {k} 연구자={r['지정여부']} 전사본={m['구분']}")
    elif a and b and not (a in b or b in a):
        out.append(f"기관명 확인: {k} 연구자='{r['기관명']}' 전사본='{m['기관명_보도자료']}'")
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(out))
