"""심평원 전국 병의원 및 약국 현황 원본 파일의 인코딩·행 수·컬럼을 점검한다 (읽기 전용).

사용: python -I code/inspect_hira_files.py <원본 폴더>
"""
import csv
import sys
from pathlib import Path

ENCODINGS = ["cp949", "utf-8-sig", "utf-8"]


def detect_encoding(path: Path) -> str:
    # 파일 전체를 디코딩해 판정 (부분 바이트로 자르면 2바이트 문자가 잘려 오판함)
    raw = path.read_bytes()
    for enc in ENCODINGS:
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩 판정 실패: {path}")


def main(folder: str) -> None:
    for path in sorted(Path(folder).glob("*.csv"), key=lambda p: int(p.name.split(".")[0])):
        enc = detect_encoding(path)
        with open(path, encoding=enc, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            first = next(reader, None)
            n = 1 + sum(1 for _ in reader)
        print(f"\n### {path.name}\n- encoding: {enc}, rows: {n:,}, cols: {len(header)}")
        for i, col in enumerate(header):
            ex = first[i] if first and i < len(first) else ""
            print(f"  {i:2d}. {col}  | 예: {ex[:40]}")


if __name__ == "__main__":
    main(sys.argv[1])
