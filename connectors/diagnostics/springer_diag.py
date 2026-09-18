"""
Diagnóstico do erro 403 na Springer Meta API.
Testa pedaços da query separadamente para descobrir exatamente o que
está sendo bloqueado (hipótese: WAF reagindo a muitos "OR" na query).

Cada teste pede só 1 registro (p=1), gasta muito pouco da cota diária.

Rode: python connectors/diagnostics/springer_diag.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests

from config import SEARCH_BLOCKS
from config import require_env
from connectors.springer import SPRINGER_META_URL

SPRINGER_API_KEY = require_env("SPRINGER_API_KEY")


def test_query(label: str, query: str) -> None:
    resp = requests.get(
        SPRINGER_META_URL,
        params={"q": query, "api_key": SPRINGER_API_KEY, "p": 1},
        timeout=30,
    )
    status = resp.status_code
    marker = "OK " if status == 200 else "FALHOU"
    print(f"[{marker}] {label} -> status {status}")
    if status != 200:
        print(f"         query: {query[:150]}...")
        print(f"         resposta: {resp.text[:200]}")
    print()


logistics_terms = SEARCH_BLOCKS["logistics_operations"]
agentic_terms = SEARCH_BLOCKS["ai_agents_agentic"]

def or_group(terms):
    return "(" + " OR ".join(f'"{t}"' for t in terms) + ")"


print("=== Teste 1: só o bloco 'logistics_operations' (9 termos, 8 ORs) ===")
test_query("bloco logistics sozinho", or_group(logistics_terms))

print("=== Teste 2: só o bloco 'ai_agents_agentic' (17 termos, 16 ORs) ===")
test_query("bloco agentic sozinho", or_group(agentic_terms))

print("=== Teste 3: os 2 blocos combinados com AND (a query completa que falhou) ===")
full_query = f"{or_group(logistics_terms)} AND {or_group(agentic_terms)}"
test_query("query completa", full_query)

print("=== Teste 4: versão reduzida — só 2 termos por bloco ===")
small_query = f"{or_group(logistics_terms[:2])} AND {or_group(agentic_terms[:2])}"
test_query("query pequena (2+2 termos)", small_query)

print("=== Teste 5: com prefixo de campo 'keyword:' em vez de busca livre ===")
def or_group_keyword(terms):
    return "(" + " OR ".join(f'keyword:"{t}"' for t in terms) + ")"
keyword_query = f"{or_group_keyword(logistics_terms)} AND {or_group_keyword(agentic_terms)}"
test_query("query completa com keyword:", keyword_query)


def test_page_size(p: int) -> None:
    resp = requests.get(
        SPRINGER_META_URL,
        params={"q": full_query, "api_key": SPRINGER_API_KEY, "p": p},
        timeout=30,
    )
    status = resp.status_code
    marker = "OK " if status == 200 else "FALHOU"
    print(f"[{marker}] p={p} -> status {status}")


print("=== Teste 6: bisseção do tamanho de página (p) — mesma query completa ===")
for p in [1, 10, 20, 25, 30, 50, 75, 100]:
    test_page_size(p)
