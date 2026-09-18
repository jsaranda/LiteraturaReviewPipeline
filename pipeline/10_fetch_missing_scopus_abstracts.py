"""
Preenche os abstracts faltantes de registros do Scopus usando a
Abstract Retrieval API da Elsevier (mesma chave ELSEVIER_API_KEY do
connectors/scopus.py, endpoint diferente da Search API).

Só busca abstract pra registros que:
1. São do Scopus (source_db == "scopus")
2. Não têm abstract preenchido
3. Têm DOI (só dá pra usar a Abstract Retrieval API com um identificador)

Evita chamadas duplicadas: se o mesmo DOI aparecer mais de uma vez,
busca só uma vez e aplica o resultado em todas as ocorrências.

Rode: python pipeline/10_fetch_missing_scopus_abstracts.py
"""

import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from connectors.scopus import elsevier_headers

ABSTRACT_RETRIEVAL_URL = "https://api.elsevier.com/content/abstract/doi/{doi}"

IN_PATH = os.path.join("data", "processed", "after_title_filter_clean.csv")
OUT_PATH = os.path.join("data", "processed", "after_title_filter_with_abstracts.csv")

SLEEP_BETWEEN_REQUESTS_S = 1.0


def fetch_abstract(doi: str) -> str:
    """Busca o abstract de um DOI via Abstract Retrieval API. Retorna
    string vazia se não encontrar ou der erro."""
    headers = elsevier_headers()
    url = ABSTRACT_RETRIEVAL_URL.format(doi=doi)

    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            return ""
        data = resp.json()
        coredata = data.get("abstracts-retrieval-response", {}).get("coredata", {})
        return coredata.get("dc:description", "") or ""
    except Exception:
        return ""


def main() -> None:
    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    # Identifica quais DOIs únicos precisam de busca
    dois_a_buscar = set()
    for row in rows:
        if (row.get("source_db") == "scopus"
                and not row.get("abstract", "").strip()
                and row.get("doi", "").strip()):
            dois_a_buscar.add(row["doi"].strip())

    print(f"DOIs únicos do Scopus sem abstract a buscar: {len(dois_a_buscar)}")

    doi_to_abstract = {}
    n_encontrados = 0
    for i, doi in enumerate(dois_a_buscar, 1):
        abstract = fetch_abstract(doi)
        if abstract:
            doi_to_abstract[doi] = abstract
            n_encontrados += 1
        if i % 25 == 0 or i == len(dois_a_buscar):
            print(f"  ...{i}/{len(dois_a_buscar)} verificados, {n_encontrados} encontrados", flush=True)
        time.sleep(SLEEP_BETWEEN_REQUESTS_S)

    print(f"\nAbstracts encontrados: {n_encontrados}/{len(dois_a_buscar)}")

    n_preenchidos = 0
    for row in rows:
        if not row.get("abstract", "").strip() and row.get("doi", "").strip() in doi_to_abstract:
            row["abstract"] = doi_to_abstract[row["doi"].strip()]
            n_preenchidos += 1

    print(f"Registros preenchidos no arquivo final: {n_preenchidos}")

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSalvo em {OUT_PATH}")


if __name__ == "__main__":
    main()