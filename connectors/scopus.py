"""
Conector para a Scopus Search API (Elsevier).
Docs: https://dev.elsevier.com/documentation/ScopusSearchAPI.wadl

Credencial: variável de ambiente ELSEVIER_API_KEY (ver .env.example).

Se você usar a API fora da rede da instituição, pode ser necessário
também um X-ELS-Insttoken (solicitado por e-mail à Elsevier; variável
ELSEVIER_INST_TOKEN) — se as chamadas começarem a retornar erro de
autorização, é provável que seja por causa disso.
"""

import os
import sys
import time
import requests

# Garante que a raiz do projeto (pasta que contém config.py) esteja no
# sys.path, não importa de onde/como este script seja executado
# (terminal, botão Run do VS Code, outro diretório etc.)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import SEARCH_BLOCKS, YEAR_FROM, YEAR_TO, ELSEVIER_INST_TOKEN, require_env
from connectors.base import Paper, PAPER_FIELDS

SCOPUS_SEARCH_URL = "https://api.elsevier.com/content/search/scopus"


def elsevier_headers() -> dict:
    """Cabeçalhos de autenticação da Elsevier (reutilizados também pela
    Abstract Retrieval API na etapa 10 e pelos diagnósticos)."""
    headers = {
        "X-ELS-APIKey": require_env("ELSEVIER_API_KEY"),
        "Accept": "application/json",
    }
    if ELSEVIER_INST_TOKEN:
        headers["X-ELS-Insttoken"] = ELSEVIER_INST_TOKEN
    return headers

RESULTS_PER_PAGE = 25  # máximo padrão da Scopus Search API sem acordo especial
SLEEP_BETWEEN_REQUESTS_S = 1.0  # folga de segurança; ajuste conforme sua cota


def _build_query() -> str:
    """
    Monta a query no formato Scopus (mesma sintaxe usada na busca do site
    Scopus). Busca em título+abstract+keywords (TITLE-ABS-KEY).
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


def _entry_to_paper(entry: dict) -> Paper:
    return Paper(
        source_db="scopus",
        title=entry.get("dc:title", "") or "",
        authors=entry.get("dc:creator", "") or "",
        year=int(entry["prism:coverDate"][:4]) if entry.get("prism:coverDate") else None,
        venue=entry.get("prism:publicationName", "") or "",
        doi=entry.get("prism:doi", "") or "",
        abstract="",  # Scopus Search API não retorna abstract completo por padrão
        url=next(
            (l.get("@href", "") for l in entry.get("link", []) if l.get("@ref") == "scopus"),
            "",
        ),
        raw_id=entry.get("dc:identifier", ""),
        query_used="scopus_search_api",
    )


def search_scopus(start: int = 0, count: int = RESULTS_PER_PAGE,
                   max_records: int | None = None) -> list[Paper]:
    """
    Busca paginada na Scopus Search API. `start` permite retomar de onde
    parou (paginação por offset).
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
        resp = requests.get(SCOPUS_SEARCH_URL, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json().get("search-results", {})

        entries = data.get("entry", [])
        for entry in entries:
            if "error" in entry:
                # Scopus retorna um "entry" de erro quando não há resultados
                break
            papers.append(_entry_to_paper(entry))

        total_results = int(data.get("opensearch:totalResults", 0))

        if first_page:
            eta_s = (total_results / count) * SLEEP_BETWEEN_REQUESTS_S
            print(f"Total de resultados na Scopus para esta query: {total_results}")
            print(f"Tempo estimado (busca completa): ~{eta_s / 60:.1f} min")
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
    import os

    # Busca completa (sem limite)
    results = search_scopus()
    print(f"Total de registros obtidos: {len(results)}")

    out_path = os.path.join("data", "raw", "scopus_results.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PAPER_FIELDS)
        writer.writeheader()
        for p in results:
            writer.writerow(p.to_dict())
    print(f"Salvo em {out_path}")
