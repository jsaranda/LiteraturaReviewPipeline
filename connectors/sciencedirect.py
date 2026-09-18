"""
Conector para a ScienceDirect Search API (Elsevier) — SCIDIR.
Docs: https://dev.elsevier.com/documentation/SCIDIRSearchAPI.wadl

Usa a MESMA chave da Elsevier do scopus.py (ELSEVIER_API_KEY) — é a
mesma família de API, só muda o endpoint. Se a chave só tiver
permissão pra Scopus (não pra ScienceDirect), a primeira chamada vai
dar 401 — nesse caso, seria preciso pedir liberação extra à Elsevier.
Na primeira execução deste pipeline foi exatamente o que aconteceu, e
a ScienceDirect acabou entrando por exportação manual (BibTeX em
data/manual_exports/sciencedirect_*.bib). Este conector fica aqui como
alternativa caso a chave tenha o entitlement.

OBS sobre a sintaxe da query: a documentação oficial usa exemplos sem
prefixo de campo (ex: "heart" AND "brain"), diferente do Scopus que
usa explicitamente TITLE-ABS-KEY(...). Mantive o mesmo padrão
TITLE-ABS-KEY do scopus.py aqui por consistência e porque a família de
API é compartilhada, mas isso não foi confirmado com uma chamada real
— se der erro de sintaxe, tente trocar por uma query sem prefixo de
campo (ver _build_query_no_field abaixo, alternativa comentada).
"""

import os
import sys
import time
import requests

# Garante que a raiz do projeto (pasta que contém config.py) esteja no
# sys.path, não importa de onde/como este script seja executado.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SEARCH_BLOCKS, YEAR_FROM, YEAR_TO
from connectors.base import Paper, PAPER_FIELDS
from connectors.scopus import elsevier_headers

SCIENCEDIRECT_SEARCH_URL = "https://api.elsevier.com/content/search/sciencedirect"

RESULTS_PER_PAGE = 25  # mesmo valor seguro usado no Scopus; ajuste se testar um maior
SLEEP_BETWEEN_REQUESTS_S = 1.0


def _build_query() -> str:
    """
    Query no formato Scopus/ScienceDirect (TITLE-ABS-KEY). Se der erro
    de sintaxe na prática, troque para _build_query_no_field().
    """
    blocks = []
    for terms in SEARCH_BLOCKS.values():
        quoted = [f'"{t}"' for t in terms]
        or_group = " OR ".join(quoted)
        blocks.append(f"({or_group})")

    query = " AND ".join(f"TITLE-ABS-KEY{b}" for b in blocks)

    if YEAR_FROM:
        year_to = YEAR_TO or 2100
        query += f" AND PUBYEAR > {YEAR_FROM - 1} AND PUBYEAR < {year_to + 1}"

    return query


def _build_query_no_field() -> str:
    """
    Alternativa sem prefixo de campo, mais parecida com os exemplos da
    documentação oficial do SCIDIR. Use esta se _build_query() der 400/403.
    """
    blocks = []
    for terms in SEARCH_BLOCKS.values():
        quoted = [f'"{t}"' for t in terms]
        or_group = " OR ".join(quoted)
        blocks.append(f"({or_group})")

    return " AND ".join(blocks)


def _entry_to_paper(entry: dict) -> Paper:
    return Paper(
        source_db="sciencedirect",
        title=entry.get("dc:title", "") or "",
        authors=entry.get("dc:creator", "") or "",
        year=int(entry["prism:coverDate"][:4]) if entry.get("prism:coverDate") else None,
        venue=entry.get("prism:publicationName", "") or "",
        doi=entry.get("prism:doi", "") or "",
        abstract="",  # a Search API geralmente não retorna abstract completo
        url=next(
            (l.get("@href", "") for l in entry.get("link", []) if l.get("@ref") == "scidir"),
            "",
        ),
        raw_id=entry.get("dc:identifier", ""),
        query_used="sciencedirect_search_api",
    )


def search_sciencedirect(start: int = 0, count: int = RESULTS_PER_PAGE,
                          max_records: int | None = None) -> list[Paper]:
    """
    Busca paginada na ScienceDirect Search API. `start` permite retomar
    de onde parou (paginação por offset), igual ao scopus.py.
    """
    query = _build_query()
    headers = elsevier_headers()

    papers: list[Paper] = []
    current_start = start
    first_page = True

    while True:
        params = {
            "query": query,
            "start": current_start,
            "count": count,
        }
        resp = requests.get(SCIENCEDIRECT_SEARCH_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("search-results", {})

        entries = data.get("entry", [])
        for entry in entries:
            if "error" in entry:
                break
            papers.append(_entry_to_paper(entry))

        total_results = int(data.get("opensearch:totalResults", 0))

        if first_page:
            print(f"Total de resultados na ScienceDirect para esta query: {total_results}")
            first_page = False

        print(f"  ...{len(papers)}/{total_results} registros baixados", flush=True)

        current_start += count

        if not entries or current_start >= total_results:
            break
        if max_records and len(papers) >= max_records:
            papers = papers[:max_records]
            break

        time.sleep(SLEEP_BETWEEN_REQUESTS_S)

    return papers


if __name__ == "__main__":
    import csv

    # Teste pequeno por padrão — remova max_records para a busca completa.
    results = search_sciencedirect(max_records=25)
    print(f"Total de registros obtidos: {len(results)}")

    out_path = os.path.join("data", "raw", "sciencedirect_results.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PAPER_FIELDS)
        writer.writeheader()
        for p in results:
            writer.writerow(p.to_dict())
    print(f"Salvo em {out_path}")