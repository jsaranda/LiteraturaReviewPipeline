"""
Diagnóstico: testa a Abstract Retrieval API com view=FULL, que é a view
que de fato inclui o campo de abstract (dc:description) — a view
padrão só traz metadados básicos.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import requests
from connectors.scopus import elsevier_headers

DOI_TESTE = "10.1016/j.jlp.2017.02.026"

headers = elsevier_headers()
url = f"https://api.elsevier.com/content/abstract/doi/{DOI_TESTE}"

resp = requests.get(url, headers=headers, params={"view": "FULL"}, timeout=30)
print("Status code:", resp.status_code)
print("URL:", resp.url)
print()

if resp.status_code == 200:
    data = resp.json()
    coredata = data.get("abstracts-retrieval-response", {}).get("coredata", {})
    print("dc:description existe?", "dc:description" in coredata)
    print("Valor:", coredata.get("dc:description", "(AUSENTE)")[:500])
else:
    print("Resposta de erro:")
    print(resp.text[:1000])