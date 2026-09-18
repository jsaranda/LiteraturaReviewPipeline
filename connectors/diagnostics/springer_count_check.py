"""
Compara o total de resultados entre a query padrão (provavelmente
full-text) e uma versão restrita ao campo título, na Springer Meta API.

Cada consulta pede só 1 registro (p=1) — só queremos o "total", não
os dados. Gasta pouquíssimo da cota diária (2 requisições).

Rode: python connectors/diagnostics/springer_count_check.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests

from config import SEARCH_BLOCKS
from config import require_env
from connectors.springer import SPRINGER_META_URL

SPRINGER_API_KEY = require_env("SPRINGER_API_KEY")


def get_total(query: str) -> int:
    resp = requests.get(
        SPRINGER_META_URL,
        params={"q": query, "api_key": SPRINGER_API_KEY, "p": 1},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return int(data.get("result", [{}])[0].get("total", 0))


def or_group(terms, field=None):
    if field:
        parts = [f'{field}:"{t}"' for t in terms]
    else:
        parts = [f'"{t}"' for t in terms]
    return "(" + " OR ".join(parts) + ")"


logistics_terms = SEARCH_BLOCKS["logistics_operations"]
agentic_terms = SEARCH_BLOCKS["ai_agents_agentic"]

# Versão atual (sem prefixo de campo — provavelmente busca full-text)
fulltext_query = f"{or_group(logistics_terms)} AND {or_group(agentic_terms)}"

# Versão restrita ao campo título
title_query = f"{or_group(logistics_terms, field='title')} AND {or_group(agentic_terms, field='title')}"

total_fulltext = get_total(fulltext_query)
print(f"Query atual (sem prefixo de campo): {total_fulltext} resultados")

total_title = get_total(title_query)
print(f"Query restrita a title:            {total_title} resultados")

print()
print(f"Diferença: {total_fulltext - total_title} resultados a mais na versão sem restrição")
