"""
Recupera o total de resultados na OpenAlex SEM o filtro de ano
(from_publication_date), pra completar a coluna "Busca Inicial" da
planilha. Faz só 2 chamadas mínimas (per-page=1), sem custo de cota
(OpenAlex é gratuita e sem limite prático).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests
from config import SEARCH_BLOCKS, YEAR_FROM, LANGUAGE
from connectors.openalex import OPENALEX_WORKS_URL, POLITE_EMAIL


def build_filter_string(with_year_filter: bool) -> str:
    filters = []
    for terms in SEARCH_BLOCKS.values():
        quoted = [f'"{t}"' if " " in t else t for t in terms]
        or_group = "|".join(quoted)
        filters.append(f"title_and_abstract.search:{or_group}")
    if with_year_filter and YEAR_FROM:
        filters.append(f"from_publication_date:{YEAR_FROM}-01-01")
    if LANGUAGE:
        filters.append(f"language:{LANGUAGE}")
    return ",".join(filters)


def get_total(with_year_filter: bool) -> int:
    params = {
        "filter": build_filter_string(with_year_filter),
        "per-page": 1,
    }
    if POLITE_EMAIL:
        params["mailto"] = POLITE_EMAIL
    resp = requests.get(OPENALEX_WORKS_URL, params=params, timeout=30)
    resp.raise_for_status()
    return int(resp.json().get("meta", {}).get("count", 0))


total_sem_filtro = get_total(with_year_filter=False)
print(f"OpenAlex SEM filtro de data (Busca Inicial real): {total_sem_filtro}")

total_com_filtro = get_total(with_year_filter=True)
print(f"OpenAlex COM filtro de data ({YEAR_FROM}+): {total_com_filtro}")

print(f"\nDiferença (excluídos pelo filtro de data): {total_sem_filtro - total_com_filtro}")