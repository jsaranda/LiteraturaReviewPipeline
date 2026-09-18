"""
Recupera o total de resultados na Scopus SEM o filtro de ano
(PUBYEAR), pra completar retroativamente a coluna "Busca Inicial" da
planilha do funil de filtragem. Faz só 2 chamadas mínimas (count=1),
gasta muito pouco da cota.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests
from config import SEARCH_BLOCKS, YEAR_FROM
from connectors.scopus import SCOPUS_SEARCH_URL, elsevier_headers


def get_total(query: str) -> int:
    headers = elsevier_headers()
    resp = requests.get(SCOPUS_SEARCH_URL, headers=headers,
                         params={"query": query, "start": 0, "count": 1}, timeout=30)
    resp.raise_for_status()
    data = resp.json().get("search-results", {})
    return int(data.get("opensearch:totalResults", 0))


def build_query(with_year_filter: bool) -> str:
    blocks = []
    for terms in SEARCH_BLOCKS.values():
        quoted = [f'"{t}"' for t in terms]
        or_group = " OR ".join(quoted)
        blocks.append(f"({or_group})")
    query = " AND ".join(f"TITLE-ABS-KEY{b}" for b in blocks)
    if with_year_filter and YEAR_FROM:
        query += f" AND PUBYEAR > {YEAR_FROM - 1}"
    return query


total_sem_filtro = get_total(build_query(with_year_filter=False))
print(f"Scopus SEM filtro de data (Busca Inicial real): {total_sem_filtro}")

total_com_filtro = get_total(build_query(with_year_filter=True))
print(f"Scopus COM filtro de data ({YEAR_FROM}+): {total_com_filtro}")

print(f"\nDiferença (excluídos pelo filtro de data): {total_sem_filtro - total_com_filtro}")