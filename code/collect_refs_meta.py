"""참고문헌 서지 확인: NCBI E-utilities(esummary, PMC/PubMed)와 Crossref API로 저자·제목·학술지·권호·DOI를 받아 기록.
지어낸 인용을 막기 위해 원고의 모든 참고문헌은 이 출력에서 확인된 것만 쓴다.

사용: python -I -X utf8 code/collect_refs_meta.py <출력txt> [pmc:ID | pmid:ID | doi:DOI ...]
"""
import json
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "icu-access-research (mailto not provided)"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def ncbi(db, ids):
    d = get(f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db={db}&id={','.join(ids)}&retmode=json")
    out = []
    for uid in d["result"]["uids"]:
        x = d["result"][uid]
        au = [a["name"] for a in x.get("authors", [])]
        doi = next((a["value"] for a in x.get("articleids", []) if a["idtype"] == "doi"), "")
        out.append(f"{db}:{uid} | {', '.join(au[:6])}{' et al' if len(au) > 6 else ''} | {x.get('title')} | "
                   f"{x.get('fulljournalname') or x.get('source')} {x.get('pubdate')};{x.get('volume')}"
                   f"({x.get('issue')}):{x.get('pages')} | doi:{doi}")
    return out


def crossref(doi):
    m = get("https://api.crossref.org/works/" + urllib.parse.quote(doi))["message"]
    au = [f"{a.get('family', '')} {''.join(p[0] for p in a.get('given', '').replace('-', ' ').split())}" for a in m.get("author", [])]
    yr = (m.get("published-print") or m.get("published-online") or m.get("issued"))["date-parts"][0][0]
    return (f"doi:{doi} | {', '.join(au[:6])}{' et al' if len(au) > 6 else ''} | {m.get('title', [''])[0]} | "
            f"{(m.get('container-title') or [''])[0]} {yr};{m.get('volume', '')}({m.get('issue', '')}):"
            f"{m.get('page', m.get('article-number', ''))}")


def main():
    out = []
    pmc = [a[4:] for a in sys.argv[2:] if a.startswith("pmc:")]
    pmid = [a[5:] for a in sys.argv[2:] if a.startswith("pmid:")]
    if pmc:
        out += ncbi("pmc", pmc)
        time.sleep(0.5)
    if pmid:
        out += ncbi("pubmed", pmid)
    for a in sys.argv[2:]:
        if a.startswith("doi:"):
            try:
                out.append(crossref(a[4:]))
            except Exception as e:
                out.append(f"{a} | 조회 실패 {e!r}")
            time.sleep(1.1)
    open(sys.argv[1], "w", encoding="utf-8").write("\n".join(out))


if __name__ == "__main__":
    main()
