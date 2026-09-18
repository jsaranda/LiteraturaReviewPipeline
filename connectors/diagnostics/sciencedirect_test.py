"""
Teste isolado da ScienceDirect Search API: usa a query MAIS simples
possível (exatamente como no exemplo da documentação oficial da
Elsevier) pra descobrir se o 401 é autorização/entitlement (chave sem
acesso ao produto) ou algo na nossa query complexa.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests
from connectors.sciencedirect import SCIENCEDIRECT_SEARCH_URL
from connectors.scopus import elsevier_headers


def test(label, query):
    headers = elsevier_headers()
    resp = requests.get(SCIENCEDIRECT_SEARCH_URL, headers=headers, params={"query": query, "count": 1}, timeout=30)
    print(f"[{resp.status_code}] {label}")
    if resp.status_code != 200:
        print(f"   resposta: {resp.text[:300]}")


# Exatamente o exemplo da documentação oficial da Elsevier
test("query mínima 'heart' (exemplo oficial)", "heart")

# Um termo único do nosso protocolo, sem TITLE-ABS-KEY nem AND/OR
test("termo único do protocolo, sem campo", "logistics")

# Nossa sintaxe normal (TITLE-ABS-KEY), só que com um único termo
test("um termo com TITLE-ABS-KEY", 'TITLE-ABS-KEY("logistics")')