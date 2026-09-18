"""
Remove os candidatos a EC6 (artigo com 4 páginas ou menos) identificados
por extras/check_short_papers.py, sobre o corpus final pós Combination/Dedup.

Rode: python pipeline/15_apply_short_paper_filter.py
"""

import csv
import glob
import os
import re

import bibtexparser

MANUAL_EXPORTS_DIR = os.path.join("data", "manual_exports")
IN_PATH = os.path.join("data", "processed", "final_combined_deduplicated.csv")
OUT_PATH = os.path.join("data", "processed", "final_after_ec6.csv")

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

    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    kept = []
    excluded = []

    for row in rows:
        doi = normalize_doi(row.get("doi", ""))
        raw_id = row.get("raw_id", "")
        pages = pages_by_doi.get(doi) or pages_by_raw_id.get(raw_id)

        if pages is not None and pages <= MAX_SHORT_PAPER_PAGES:
            excluded.append((row, pages))
        else:
            kept.append(row)

    print(f"Total antes: {len(rows)}")
    print(f"Excluídos (EC6, <= {MAX_SHORT_PAPER_PAGES} páginas): {len(excluded)}")
    for row, pages in excluded:
        print(f"  [{row.get('source_db')}] ({pages}p) {row.get('title')}")
    print(f"Total restante: {len(kept)}")

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    print(f"\nCorpus salvo em {OUT_PATH}")


if __name__ == "__main__":
    main()