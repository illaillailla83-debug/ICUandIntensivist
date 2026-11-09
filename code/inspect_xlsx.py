"""xlsx를 표준 라이브러리만으로 읽어 시트별 행을 UTF-8 텍스트로 미리보기한다 (원본 수정 없음).

사용: python -I -X utf8 code/inspect_xlsx.py <xlsx> <출력txt> [최대행]
"""
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def col_idx(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path):
    """{시트명: [[셀값...], ...]} 반환. 모든 값은 문자열."""
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")))
    wb = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid2target = {r.get("Id"): r.get("Target") for r in rels}
    sheets = {}
    for s in wb.find("m:sheets", NS):
        rid = s.get(f"{{{NS['r']}}}id")
        target = rid2target[rid].lstrip("/")
        if not target.startswith("xl/"):
            target = "xl/" + target
        root = ET.fromstring(z.read(target))
        rows = []
        for row in root.iter(f"{{{NS['m']}}}row"):
            vals = {}
            for c in row.findall("m:c", NS):
                t = c.get("t")
                v = c.find("m:v", NS)
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(f"{{{NS['m']}}}t"))
                else:
                    val = v.text if v is not None else ""
                vals[col_idx(c.get("r"))] = val
            if vals:
                rows.append([vals.get(i, "") for i in range(max(vals) + 1)])
            else:
                rows.append([])
        sheets[s.get("name")] = rows
    return sheets


if __name__ == "__main__":
    src, out = sys.argv[1], sys.argv[2]
    maxrows = int(sys.argv[3]) if len(sys.argv) > 3 else 400
    lines = []
    for name, rows in read_xlsx(src).items():
        lines.append(f"### sheet '{name}': {len(rows)} rows")
        for i, r in enumerate(rows[:maxrows]):
            lines.append(f"{i}\t" + " | ".join(r))
    open(out, "w", encoding="utf-8").write("\n".join(lines))
