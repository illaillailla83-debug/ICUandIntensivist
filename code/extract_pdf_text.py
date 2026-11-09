"""PDF 보고서의 페이지별 텍스트를 UTF-8 txt로 추출한다 (원본 PDF는 수정하지 않음).

사용: python -P code/extract_pdf_text.py <출력폴더> <pdf1> [<pdf2> ...]
출력: <출력폴더>/<pdf이름>.txt  (페이지 구분선 '=== p.N ===' 포함)
"""
import sys
from pathlib import Path

from pypdf import PdfReader


def main(outdir, pdfs):
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    for p in map(Path, pdfs):
        reader = PdfReader(str(p))
        parts = []
        for i, page in enumerate(reader.pages, 1):
            try:
                txt = page.extract_text() or ""
            except Exception as e:  # 일부 페이지 추출 실패 시 기록하고 계속
                txt = f"[추출 실패: {e!r}]"
            parts.append(f"=== p.{i} ===\n{txt}")
        (out / f"{p.stem}.txt").write_text("\n".join(parts), encoding="utf-8")
        chars = sum(len(x) for x in parts)
        print(f"{p.name}: {len(reader.pages)}쪽, {chars:,}자")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
