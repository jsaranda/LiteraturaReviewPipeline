"""
Conector para a API do OpenAlex (https://openalex.org).

Por que começar por aqui:
- API pública, gratuita, sem necessidade de chave/assinatura institucional.
- Cobertura ampla (indexa Crossref, PubMed, e boa parte do que está em
  Scopus/Web of Science em termos de metadados).
- Serve como fonte extra / checagem cruzada das bases "oficiais" do
  protocolo na etapa de combinação/dedup.

Docs: https://docs.openalex.org/api-entities/works/search-works
"""

import os
import sys
import time
import requests

# Garante que a raiz do projeto (pasta que contém config.py) esteja no
# sys.path, não importa de onde/como este script seja executado
# (terminal, botão Run do VS Code, outro diretório etc.)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SEARCH_BLOCKS, YEAR_FROM, YEAR_TO, LANGUAGE, OPENALEX_MAILTO
from connectors.base import Paper, PAPER_FIELDS

OPENALEX_WORKS_URL = "https://api.openalex.org/works"

# A OpenAlex pede um e-mail via "mailto" para te colocar no "polite pool"
# (rate limit mais alto e mais estável). Não é uma chave — configure
# OPENALEX_MAILTO no .env.
POLITE_EMAIL = OPENALEX_MAILTO


def _build_filter_string() -> str:
    """
    Monta o filtro da OpenAlex combinando os 3 blocos do protocolo com AND,
    e os termos dentro de cada bloco com OR.
    A OpenAlex aceita múltiplos filtros separados por vírgula (AND) e,
    dentro de um filtro de busca textual, o pipe "|" funciona como OR.
    """
    filters = []
    for terms in SEARCH_BLOCKS.values():
        # aspas em frases com espaço, sem aspas em termo único
        quoted = [f'"{t}"' if " " in t else t for t in terms]
        or_group = "|".join(quoted)
        filters.append(f"title_and_abstract.search:{or_group}")

    if YEAR_FROM:
        filters.append(f"from_publication_date:{YEAR_FROM}-01-01")
    if YEAR_TO:
        filters.append(f"to_publication_date:{YEAR_TO}-12-31")
    if LANGUAGE:
        filters.append(f"language:{LANGUAGE}")

    return ",".join(filters)


def _extract_abstract(work: dict) -> str:
    """OpenAlex retorna o abstract como 'inverted index' — reconstrói o texto."""
    inv = work.get("abstract_inverted_index")
    if not inv:
        return ""
    positions = {}
    for word, idxs in inv.items():
        for i in idxs:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions))


def _work_to_paper(work: dict, query_used: str) -> Paper:
    authorships = work.get("authorships", []) or []
    authors = "; ".join(
        a.get("author", {}).get("display_name", "") for a in authorships
    )
    doi = work.get("doi", "") or ""
    venue = (
        work.get("primary_location", {}) or {}
    ).get("source", {}) or {}
    venue_name = venue.get("display_name", "") if venue else ""

    return Paper(
        source_db="openalex",
        title=work.get("title", "") or "",
        authors=authors,
        year=work.get("publication_year"),
        venue=venue_name,
        doi=doi,
        abstract=_extract_abstract(work),
        url=work.get("id", ""),
        raw_id=work.get("id", ""),
        query_used=query_used,
    )


def search_openalex(per_page: int = 200, max_pages: int = 20, sleep_s: float = 0.2) -> list[Paper]:
    """
    Busca todos os resultados (paginado via cursor) para o filtro combinado
    do protocolo. Retorna lista de Paper.
    """
    filter_str = _build_filter_string()
    papers = []
    cursor = "*"
    page = 0

    while cursor and page < max_pages:
        params = {
            "filter": filter_str,
            "per-page": per_page,
            "cursor": cursor,
        }
        if POLITE_EMAIL:
            params["mailto"] = POLITE_EMAIL
        resp = requests.get(OPENALEX_WORKS_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        results = data.get("results", [])
        for work in results:
            papers.append(_work_to_paper(work, query_used=filter_str))

        cursor = data.get("meta", {}).get("next_cursor")
        page += 1
        if not results:
            break
        time.sleep(sleep_s)

    return papers


if __name__ == "__main__":
    import csv
    import os

    results = search_openalex()
    print(f"Total de registros encontrados na OpenAlex: {len(results)}")

    out_path = os.path.join("data", "raw", "openalex_results.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PAPER_FIELDS)
        writer.writeheader()
        for p in results:
            writer.writerow(p.to_dict())
    print(f"Salvo em {out_path}")
