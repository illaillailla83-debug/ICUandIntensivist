"""심평원 병원정보(2026.9.) 전 기관의 (시도코드명, 시군구코드, 시군구코드명) 고유값과 기관 수를 UTF-8로 출력.

사용: python -I -X utf8 code/inspect_hira_sgg.py <출력txt>
"""
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
F = ROOT / "data/raw/hira_2026-10/건강보험심사평가원_전국 병의원 및 약국 현황_20260930/1.병원정보서비스(2026.9.).csv"

cnt = Counter()
with open(F, encoding="cp949", newline="") as f:
    for r in csv.DictReader(f):
        cnt[(r["시도코드"], r["시도코드명"], r["시군구코드"], r["시군구코드명"])] += 1
lines = [f"고유 시군구 {len(cnt)}개"] + ["\t".join(k) + f"\t{n}" for k, n in sorted(cnt.items(), key=lambda kv: kv[0][2])]
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(lines))
