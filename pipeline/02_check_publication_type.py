"""
Verifica o tipo de publicação (article, inproceedings, book, incollection,
phdthesis, etc.) de cada registro.

- Para as bases manuais (ACM, Wiley, T&F, WoS, ScienceDirect): lê o
  ENTRYTYPE real direto dos arquivos .bib já baixados em
  data/manual_exports/ (nenhum custo de API, dado real).
- Para as bases via API (OpenAlex, Scopus, IEEE, Springer): nenhum
  conector capturou tipo de documento até agora, então aqui aplicamos
  uma heurística sobre o TÍTULO pra sinalizar candidatos suspeitos.

CORREÇÃO: muitas entradas da ACM (especialmente publicadas por
IFAAMAS/AAMAS, não pela ACM diretamente) não têm campo DOI no BibTeX,
mesmo tendo todos os outros dados. Por isso, além de casar por DOI,
agora também casamos pela CHAVE DE CITAÇÃO do BibTeX (raw_id/ID), que
sempre existe, como plano B quando o DOI está ausente.

Rode: python pipeline/02_check_publication_type.py
"""

import csv
import glob
import os
import re

import bibtexparser

MANUAL_EXPORTS_DIR = os.path.join("data", "manual_exports")
IN_PATH = os.path.join("data", "processed", "raw_pool_no_dedup.csv")
OUT_PATH = os.path.join("data", "processed", "publication_type_check.csv")

SUSPECT_TITLE_PATTERNS = [
    r"^erratum",
    r"^corrigendum",
    r"^retraction",
    r"^editorial\b",
    r"^book review",
    r"^front matter",
    r"^back matter",
    r"^table of contents",
    r"^preface\b",
    r"^foreword\b",
    r"^author index",
    r"^subject index",
    r"^issue information",
    r"^index$",
]
SUSPECT_REGEX = re.compile("|".join(SUSPECT_TITLE_PATTERNS), re.IGNORECASE)


def normalize_doi(doi: str) -> str:
    if not doi:
        return ""
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi.strip("/")


def load_manual_entry_types() -> tuple[dict, dict]:
    """
    Retorna dois dicts: {doi_normalizado: entrytype} e {raw_id: entrytype}.
    O segundo serve de plano B para entradas sem DOI no BibTeX (comum em
    proceedings publicados por terceiros, como AAMAS/IFAAMAS via ACM DL).
    """
    doi_to_type = {}
    raw_id_to_type = {}
    for path in glob.glob(os.path.join(MANUAL_EXPORTS_DIR, "*.bib")):
        with open(path, encoding="utf-8") as f:
            db = bibtexparser.load(f)
        for entry in db.entries:
            entrytype = entry.get("ENTRYTYPE", "unknown").lower()
            doi = normalize_doi(entry.get("doi", ""))
            citation_key = entry.get("ID", "")
            if doi:
                doi_to_type[doi] = entrytype
            if citation_key:
                raw_id_to_type[citation_key] = entrytype
    return doi_to_type, raw_id_to_type


def main() -> None:
    doi_to_type, raw_id_to_type = load_manual_entry_types()
    print(f"Tipos carregados: {len(doi_to_type)} por DOI, {len(raw_id_to_type)} por chave de citação.\n")

    rows = []
    n_matched_by_doi = 0
    n_matched_by_raw_id = 0

    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames + ["pub_type", "suspect_title"]
        for row in reader:
            doi_key = normalize_doi(row.get("doi", ""))
            raw_id_key = row.get("raw_id", "")
            source = row.get("source_db", "")

            if doi_key in doi_to_type:
                pub_type = doi_to_type[doi_key]
                n_matched_by_doi += 1
            elif raw_id_key in raw_id_to_type:
                pub_type = raw_id_to_type[raw_id_key]
                n_matched_by_raw_id += 1
            elif source in ("openalex", "scopus", "ieee_xplore", "springer"):
                pub_type = "desconhecido (API não capturou)"
            else:
                pub_type = "desconhecido (não encontrado no .bib)"

            is_suspect = bool(SUSPECT_REGEX.search(row.get("title", "")))
            row["pub_type"] = pub_type
            row["suspect_title"] = "SIM" if is_suspect else ""
            rows.append(row)

    by_type = {}
    for row in rows:
        by_type[row["pub_type"]] = by_type.get(row["pub_type"], 0) + 1

    print(f"{'Tipo de publicação':<45}{'Quantidade':>12}")
    print("-" * 57)
    for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"{t:<45}{count:>12}")

    n_suspect = sum(1 for r in rows if r["suspect_title"] == "SIM")
    print(f"\nCasados por DOI: {n_matched_by_doi}")
    print(f"Casados por chave de citação (fallback): {n_matched_by_raw_id}")
    print(f"Títulos suspeitos por padrão (erratum, editorial, etc.): {n_suspect}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nArquivo completo salvo em {OUT_PATH}")


if __name__ == "__main__":
    main()