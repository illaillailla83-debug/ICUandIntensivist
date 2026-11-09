"""투고 파일 만들기 (Lancet Regional Health – Western Pacific). 2026-11-05

출력 (output/submission/)
  Tables_TLRHWP.docx          표 1–3 (표마다 한 쪽, 제목 위·각주 아래, 가로 방향)
  Appendix_TLRHWP.docx / .pdf  부록: 표지·목차·쪽 번호 + appendix table S1, S2, S3 (PDF는 Word로 변환)
  Figure1.tif … Figure4.tif    output/figures/*.tif를 RGB(알파 없음)·LZW·300 dpi로 다시 저장
숫자 표기(Lancet): 소수점 → 가운뎃점(·), 다섯 자리 이상 정수는 3자리마다 공백(줄바꿈 없는 공백), 네 자리는 그대로(7403).
  버전 번호(6.0.0)는 바꾸지 않음. 표 내용 자체는 output/tables/*.md 그대로(값 변경 없음).
사용: python -P -X utf8 code/make_submission_files.py   (python-docx, Pillow 필요; PDF 변환에는 Microsoft Word)
"""
import re
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / "output/tables"
OUT = ROOT / "output/submission"
TITLE = ("Geographical access to intensivist-staffed intensive care in an ageing population: "
         "a nationwide travel-time analysis of South Korea")
AUTHORS = "Seung Min Baik, Jae-Myeong Lee, Kyung Sook Hong"
NBSP = " "


def lancet(s):
    keep = {}

    def protect(m):
        keep[f"@@{len(keep)}@@"] = m.group(0)
        return f"@@{len(keep) - 1}@@"
    s = re.sub(r"\d+\.\d+\.\d+", protect, s)                     # 버전 번호
    s = re.sub(r"(?<=\d),(?=\d{3}\b)", "", s)                     # 1,906,141 → 1906141
    s = re.sub(r"(?<=\d)\.(?=\d)", "·", s)                        # 3.7 → 3·7
    s = re.sub(r"(?<![\d·])\d{5,}(?![\d·])",                      # 1906141 → 1 906 141
               lambda m: f"{int(m.group(0)):,}".replace(",", NBSP), s)
    for k, v in keep.items():
        s = s.replace(k, v)
    return s


def read_md(name):
    lines = (T / f"{name}.md").read_text(encoding="utf-8").splitlines()
    title = lines[0].lstrip("# ").strip()
    rows = [[c.strip() for c in L.strip().strip("|").split("|")] for L in lines if L.startswith("|")]
    rows = [r for r in rows if not all(set(c) <= set("-: ") for c in r)]  # 구분선 제거
    notes = [L.strip() for L in lines[1:] if L.strip() and not L.startswith("|")]
    return title, rows, notes


def landscape(section):
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = Mm(297), Mm(210)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(section, side, Mm(15))


def field(paragraph, code):
    """Word 필드(PAGE, TOC 등) 삽입 — Word에서 열 때/변환 때 갱신."""
    run = paragraph.add_run()
    for tag, text in (("begin", None), (None, code), ("separate", None), (None, "…"), ("end", None)):
        if tag:
            e = OxmlElement("w:fldChar")
            e.set(qn("w:fldCharType"), tag)
        elif text == code:
            e = OxmlElement("w:instrText")
            e.set(qn("xml:space"), "preserve")
            e.text = code
        else:
            e = OxmlElement("w:t")
            e.text = text
        run._r.append(e)


def add_table(doc, name, heading_style=None, font=7, group_first_col=False):
    """group_first_col: 첫 열 값이 여러 행에 반복되면(예: Table S2의 목표·후보 조건) 열을 없애고 소제목 행으로 바꿈."""
    title, rows, notes = read_md(name)
    p = doc.add_paragraph(style=heading_style) if heading_style else doc.add_paragraph()
    r = p.add_run(lancet(title))
    r.bold = True
    r.font.size = Pt(10)
    if group_first_col:
        out, prev = [rows[0][1:]], None
        for row in rows[1:]:
            if row[0] != prev:
                out.append(("GROUP", row[0]))
                prev = row[0]
            out.append(row[1:])
        rows = out
    ncol = max(len(r) for r in rows if r and r[0] != "GROUP")
    tb = doc.add_table(rows=len(rows), cols=ncol)
    tb.style = "Table Grid"
    hdr = tb.rows[0]._tr.get_or_add_trPr()
    rep = OxmlElement("w:tblHeader")  # 쪽이 넘어가면 열 제목 반복
    rep.set(qn("w:val"), "true")
    hdr.append(rep)
    for i, row in enumerate(rows):
        if row and row[0] == "GROUP":
            cell = tb.cell(i, 0).merge(tb.cell(i, ncol - 1))
            cell.text = ""
            run = cell.paragraphs[0].add_run(lancet(row[1]))
            run.font.size = Pt(font)
            run.bold = True
            continue
        for j, c in enumerate(row):
            cell = tb.cell(i, j)
            cell.text = ""
            run = cell.paragraphs[0].add_run(lancet(c))
            run.font.size = Pt(font)
            run.bold = i == 0
    for n in notes:
        q = doc.add_paragraph()
        q.add_run(lancet(n)).font.size = Pt(8)
    return title


def style_doc(doc):
    st = doc.styles["Normal"]
    st.font.name = "Arial"
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Malgun Gothic")  # 표 안 한글 병원명
    st.font.size = Pt(10)


def tables_docx():
    doc = Document()
    style_doc(doc)
    landscape(doc.sections[0])
    for k, name in enumerate(["table1_supply_access_by_region", "table2_unreached_population", "table3_scenarios_policy"]):
        if k:
            doc.add_page_break()
        add_table(doc, name, font=7 if k == 0 else 8)
    doc.save(OUT / "Tables_TLRHWP.docx")


def appendix_docx():
    doc = Document()
    style_doc(doc)
    sec = doc.sections[0]
    landscape(sec)
    fp = sec.footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    field(fp, "PAGE")
    p = doc.add_paragraph()
    r = p.add_run("Supplementary appendix")
    r.bold = True
    r.font.size = Pt(16)
    doc.add_paragraph().add_run(TITLE).font.size = Pt(13)
    doc.add_paragraph(AUTHORS)
    doc.add_paragraph()
    doc.add_paragraph().add_run("Contents").bold = True
    field(doc.add_paragraph(), 'TOC \\o "1-1" \\h \\z \\u')
    for name in ["tableS1_inequality", "tableS2_greedy_sequence", "tableS3_greedy_responsible"]:
        doc.add_page_break()
        add_table(doc, name, heading_style="Heading 1", font=7, group_first_col=name.startswith("tableS2"))
    doc.save(OUT / "Appendix_TLRHWP.docx")


def word_pdf():
    """Word COM으로 목차·쪽 번호를 갱신하고 PDF로 내보냄."""
    src, pdf = OUT / "Appendix_TLRHWP.docx", OUT / "Appendix_TLRHWP.pdf"
    ps = (f"$w = New-Object -ComObject Word.Application; $w.Visible = $false; "
          f"$d = $w.Documents.Open('{src}'); $d.Fields.Update() | Out-Null; "
          f"foreach($t in $d.TablesOfContents){{ $t.Update() }}; $d.Save(); "
          f"$d.ExportAsFixedFormat('{pdf}', 17); $d.Close(); $w.Quit()")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not pdf.exists():
        print("PDF 변환 실패:", r.stderr[-500:])
    else:
        print("PDF:", pdf.stat().st_size, "bytes")


def figures():
    names = {"fig1_icu_distribution": 1, "fig2_travel_time_map": 2, "fig3_inequality_unreached": 3,
             "fig4_scenarios_policy": 4}
    for stem, k in names.items():
        im = Image.open(ROOT / f"output/figures/{stem}.tif")
        if im.mode != "RGB":
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1] if im.mode in ("RGBA", "LA") else None)
            im = bg
        im.save(OUT / f"Figure{k}.tif", compression="tiff_lzw", dpi=(300, 300))
        print(f"Figure{k}.tif {im.size[0]}×{im.size[1]} px = {im.size[0] / 300 * 25.4:.1f}×{im.size[1] / 300 * 25.4:.1f} mm, RGB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    figures()
    tables_docx()
    appendix_docx()
    if "--no-pdf" not in sys.argv:
        word_pdf()


if __name__ == "__main__":
    main()
