"""Additional file 1 (Critical Care 투고본) Table S2·S3의 병원 코드 H01–H28 대응표. 2026-11-07

연구자 결정(2026-11-06): 논문에는 병원 이름을 쓰지 않고 코드로 표시.
코드는 Table S2에 처음 나오는 순서대로 매김(채팅이 만든 hospital_codes_S2-S3.json과 같은 규칙).
독자가 표를 재현할 수 있도록 대응표를 output/tables/hospital_codes_S2-S3.csv 로 저장한다.
이름이 들어간 S2·S3 원본 표(output/tables/tableS2_*, tableS3_*)는 그대로 둔다.
사용: python -I -X utf8 code/make_hospital_codes.py
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / "output/tables"


def main():
    s2 = list(csv.DictReader(open(T / "tableS2_greedy_sequence.csv", encoding="utf-8-sig")))
    s3 = list(csv.DictReader(open(T / "tableS3_greedy_responsible.csv", encoding="utf-8-sig")))
    codes, info = {}, {}
    for r in s2:
        name = r["Hospital added"]
        if name not in codes:
            codes[name] = f"H{len(codes) + 1:02d}"
            info[name] = (r["Hospital (Korean)"], r["Region"], r["Name source"])
    missing = [r["Hospital"] for r in s3 if r["Hospital"] not in codes]
    if missing:
        raise SystemExit(f"S3 병원이 S2에 없음: {missing}")
    in_s3 = {r["Hospital"] for r in s3}

    # 채팅이 투고본을 만들 때 쓴 대응표와 같은지 확인
    chat = T / "hospital_codes_S2-S3.json"
    if chat.exists():
        cj = json.loads(chat.read_text(encoding="utf-8"))
        if cj != codes:
            diff = {k: (cj.get(k), codes.get(k)) for k in set(cj) | set(codes) if cj.get(k) != codes.get(k)}
            raise SystemExit(f"채팅 대응표와 다름: {diff}")
        print("채팅 대응표(json)와 일치")

    out = T / "hospital_codes_S2-S3.csv"
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "hospital_en", "hospital_ko", "province", "name_source", "in_table_S3"])
        for name, code in codes.items():
            ko, prov, src = info[name]
            w.writerow([code, name, ko, prov, src, "yes" if name in in_s3 else "no"])
    print(f"{len(codes)}개 병원 → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
