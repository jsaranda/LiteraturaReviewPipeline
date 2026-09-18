"""
Verifica o EC6 (artigo com 4 páginas ou menos) sobre o corpus FINAL
(pós Combination + Duplicate Removal, etapa 14).

Extrai o número de páginas do campo 'numpages' (mais confiável) ou
calcula a partir de 'pages' (ex: "1518-1519" -> 2 páginas) direto dos
arquivos .bib originais em data/manual_exports/ — só é possível para
as bases manuais (ACM, Wiley, T&F, WoS, ScienceDirect); bases via API
(Scopus, IEEE, OpenAlex, Springer) não têm essa informação capturada
pelos conectores.

Rode: python pipeline/extras/check_short_papers.py
"""

import csv
import glob
import os
import re

import bibtexparser

MANUAL_EXPORTS_DIR = os.path.join("data", "manual_exports")
IN_PATH = os.path.join("data", "processed", "final_combined_deduplicated.csv")

MAX_SHORT_PAPER_PAGES = 4


def normalize_doi(doi: str) -> str:
    if not doi:
        return ""
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi.strip("/")


def parse_page_count(entry: dict) -> int | None:
    numpages = entry.get("numpages", "").strip()
    if numpages.isdigit():
        return int(numpages)

    pages = entry.get("pages", "").strip()
    if pages:
        parts = re.split(r"[-–—]+", pages)
        parts = [p.strip() for p in parts if p.strip().isdigit()]
        if len(parts) == 2:
            return abs(int(parts[1]) - int(parts[0])) + 1
        # NÃO assume mais "1 página" quando só há um número sozinho —
        # muitos periódicos (principalmente Elsevier) usam número do
        # artigo em vez de intervalo de página (ex: "108234"), o que
        # antes era lido erradamente como "página 1 só". Sem intervalo
        # real, não dá pra confiar na contagem -> fica como "sem info".

    return None


def load_page_counts() -> tuple[dict, dict]:
    by_doi = {}
    by_raw_id = {}
    for path in glob.glob(os.path.join(MANUAL_EXPORTS_DIR, "*.bib")):
        with open(path, encoding="utf-8") as f:
            db = bibtexparser.load(f)
        for entry in db.entries:
            pages = parse_page_count(entry)
            if pages is None:
                continue
            doi = normalize_doi(entry.get("doi", ""))
            citation_key = entry.get("ID", "")
            if doi:
                by_doi[doi] = pages
            if citation_key:
                by_raw_id[citation_key] = pages
    return by_doi, by_raw_id


def main() -> None:
    pages_by_doi, pages_by_raw_id = load_page_counts()
    print(f"Contagem de páginas carregada: {len(pages_by_doi)} por DOI, "
          f"{len(pages_by_raw_id)} por chave de citação.\n")

    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    short_papers = []
    n_sem_info = 0

    for row in rows:
        doi = normalize_doi(row.get("doi", ""))
        raw_id = row.get("raw_id", "")

        pages = pages_by_doi.get(doi) or pages_by_raw_id.get(raw_id)
        if pages is None:
            n_sem_info += 1
            continue

        if pages <= MAX_SHORT_PAPER_PAGES:
            short_papers.append((row, pages))

    print(f"Total no corpus: {len(rows)}")
    print(f"Sem informação de páginas (não dá pra checar EC6): {n_sem_info}")
    print(f"Candidatos a EC6 (<= {MAX_SHORT_PAPER_PAGES} páginas): {len(short_papers)}\n")

    for row, pages in short_papers:
        print(f"  [{row.get('source_db')}] ({pages}p) {row.get('title')}")


if __name__ == "__main__":
    main()