"""
Testa se o campo title: é o problema, isolado de qualquer efeito de
rajada/cooldown das requisições anteriores.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests

from config import require_env
from connectors.springer import SPRINGER_META_URL

SPRINGER_API_KEY = require_env("SPRINGER_API_KEY")


def test(label, query):
    resp = requests.get(
        SPRINGER_META_URL,
        params={"q": query, "api_key": SPRINGER_API_KEY, "p": 1},
        timeout=30,
    )
    print(f"[{resp.status_code}] {label}")
    if resp.status_code != 200:
        print(f"   resposta: {resp.text[:300]}")
    time.sleep(3)  # espera generosa entre testes, pra descartar cooldown


test("title: com 1 termo só", 'title:"logistics"')
test("title: com 2 termos (OR)", '(title:"logistics" OR title:"supply chain")')
test("sem prefixo, mesmo termo", '"logistics"')