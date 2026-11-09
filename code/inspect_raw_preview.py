"""원본 파일(csv/txt)의 인코딩 판정 + 헤더·앞부분 행을 UTF-8 파일로 출력한다 (읽기 전용).

사용: python -I code/inspect_raw_preview.py <출력파일> <파일1> [<파일2> ...]
"""
import csv
import io
import sys
from pathlib import Path


def decode(raw):
    for enc in ("utf-8-sig", "cp949"):
        try:
            return enc, raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return "cp949(replace)", raw.decode("cp949", errors="replace")


def main(out, paths, nrows=12):
    with open(out, "w", encoding="utf-8") as o:
        for p in map(Path, paths):
            enc, text = decode(p.read_bytes())
            o.write(f"\n### {p.name}\n- encoding: {enc}, bytes: {p.stat().st_size:,}\n")
            if p.suffix.lower() == ".txt":
                o.write(text + "\n")
                continue
            rows = list(csv.reader(io.StringIO(text)))
            o.write(f"- rows(헤더 제외): {len(rows) - 1:,}, cols: {len(rows[0])}\n")
            for r in rows[: nrows + 1]:
                o.write(" | ".join(r) + "\n")
            if len(rows) > nrows + 1:
                o.write("...\n" + " | ".join(rows[-1]) + "\n")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
