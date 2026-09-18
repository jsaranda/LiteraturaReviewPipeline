"""
Importa exportações manuais de bases sem API amigável (ACM DL, Wiley,
Google Scholar) e normaliza para o schema comum (connectors.base.Paper).

Como gerar os arquivos de entrada:

- ACM Digital Library: na página de resultados de busca, exporte as
  citações selecionadas em formato BibTeX ("Export Citations").
- Wiley Online Library: idem, resultados de busca -> "Export Citation(s)"
  -> BibTeX.
- Google Scholar: não tem exportação em massa nativa. Use o software
  gratuito "Publish or Perish" (harzing.com/resources/publish-or-perish),
  que consulta o Google Scholar e exporta CSV/BibTeX com título, autores,
  ano, abstract (quando disponível) e link — é o caminho mais estável
  hoje em dia para automatizar isso sem violar os termos do Google.

Coloque os arquivos exportados em data/manual_exports/, com um nome que
comece com o nome da base, ex:
  data/manual_exports/acm_dl_export.bib
  data/manual_exports/wiley_export.bib
  data/manual_exports/google_scholar_export.csv

Requer: pip install bibtexparser
"""

import csv
import glob
import os
import sys

# Garante que a raiz do projeto (pasta que contém connectors/) esteja no
# sys.path, não importa de onde/como este script seja executado
# (terminal, botão Run do VS Code, outro diretório etc.)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from connectors.base import Paper

MANUAL_EXPORTS_DIR = os.path.join("data", "manual_exports")

# Mapeia prefixo do nome de arquivo -> source_db
SOURCE_PREFIXES = {
    "acm": "acm_dl",
    "wiley": "wiley",
    "google_scholar": "google_scholar",
    "scholar": "google_scholar",
    "tandf": "taylor_francis",
    "taylor": "taylor_francis",
    "wos": "web_of_science",
    "sciencedirect": "sciencedirect",
    "sd": "sciencedirect",
}


def _guess_source_db(filename: str) -> str:
    base = os.path.basename(filename).lower()
    for prefix, source in SOURCE_PREFIXES.items():
        if base.startswith(prefix):
            return source
    return "manual_unknown"


def _parse_bib(path: str) -> list[Paper]:
    try:
        import bibtexparser
    except ImportError as e:
        raise ImportError(
            "Instale bibtexparser: pip install bibtexparser"
        ) from e

    source_db = _guess_source_db(path)
    with open(path, encoding="utf-8") as f:
        bib_database = bibtexparser.load(f)

    papers = []
    for entry in bib_database.entries:
        year_raw = entry.get("year", "")
        try:
            year = int(year_raw)
        except (TypeError, ValueError):
            year = None

        papers.append(
            Paper(
                source_db=source_db,
                title=entry.get("title", "").strip("{}"),
                authors=entry.get("author", "").replace(" and ", "; "),
                year=year,
                venue=entry.get("journal") or entry.get("booktitle") or "",
                doi=entry.get("doi", ""),
                abstract=entry.get("abstract", ""),
                url=entry.get("url", ""),
                raw_id=entry.get("ID", ""),
                query_used="manual_export",
            )
        )
    return papers


def _parse_csv(path: str) -> list[Paper]:
    """
    Suporta CSV vindo do Publish or Perish (colunas costumam incluir:
    Title, Authors, Year, Source/Publisher, DOI, Abstract, URL — mas o
    nome exato das colunas pode variar por versão, então tentamos alguns
    apelidos comuns por campo).
    """
    source_db = _guess_source_db(path)

    COLUMN_ALIASES = {
        "title": ["title", "Title"],
        "authors": ["authors", "Authors", "author"],
        "year": ["year", "Year"],
        "venue": ["source", "Source", "publisher", "Publisher", "journal"],
        "doi": ["doi", "DOI"],
        "abstract": ["abstract", "Abstract"],
        "url": ["url", "URL", "link", "Link"],
    }

    def get_field(row: dict, field: str) -> str:
        for alias in COLUMN_ALIASES[field]:
            if alias in row and row[alias]:
                return row[alias]
        return ""

    papers = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            year_raw = get_field(row, "year")
            try:
                year = int(year_raw)
            except (TypeError, ValueError):
                year = None

            papers.append(
                Paper(
                    source_db=source_db,
                    title=get_field(row, "title"),
                    authors=get_field(row, "authors"),
                    year=year,
                    venue=get_field(row, "venue"),
                    doi=get_field(row, "doi"),
                    abstract=get_field(row, "abstract"),
                    url=get_field(row, "url"),
                    raw_id="",
                    query_used="manual_export",
                )
            )
    return papers


def load_manual_exports(directory: str = MANUAL_EXPORTS_DIR) -> list[Paper]:
    """Lê todos os .bib e .csv da pasta de exportações manuais."""
    papers: list[Paper] = []

    for path in glob.glob(os.path.join(directory, "*.bib")):
        papers.extend(_parse_bib(path))

    for path in glob.glob(os.path.join(directory, "*.csv")):
        papers.extend(_parse_csv(path))

    return papers


if __name__ == "__main__":
    results = load_manual_exports()
    print(f"Total de registros importados manualmente: {len(results)}")
    by_source: dict[str, int] = {}
    for p in results:
        by_source[p.source_db] = by_source.get(p.source_db, 0) + 1
    for source, count in by_source.items():
        print(f"  {source}: {count}")
