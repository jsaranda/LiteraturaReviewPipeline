"""
Teste rápido e isolado da chave da Springer, sem toda a lógica do
conector — só pra descobrir se o problema é a chave (ainda ativando)
ou a query.

Rode: python connectors/diagnostics/springer_test.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests

from config import require_env
from connectors.springer import SPRINGER_META_URL

SPRINGER_API_KEY = require_env("SPRINGER_API_KEY")

# query minúscula e simples de propósito, sem aspas, sem AND/OR complexo
resp = requests.get(
    SPRINGER_META_URL,
    params={"q": "logistics", "api_key": SPRINGER_API_KEY, "p": 1},
    timeout=30,
)

print("Status code:", resp.status_code)
print("URL chamada:", resp.url)
print()
print("Resposta:")
print(resp.text[:1000])
