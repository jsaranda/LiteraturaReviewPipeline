"""
Verifica quantos registros SEM abstract (Scopus, Taylor & Francis, etc.)
têm uma duplicata por DOI em OUTRA base do mesmo conjunto, que
TEM abstract preenchido. Se a maioria tiver, a etapa de Combination/
dedup já resolve boa parte do problema sozinha, sem esforço extra —
basta a lógica de dedup preferir a versão com abstract quando houver
mais de uma opção pelo mesmo DOI.

Rode: python pipeline/extras/check_abstract_recovery_via_dedup.py
"""

import csv
import os

IN_PATH = os.path.join("data", "processed", "after_title_filter.csv")


def normalize_doi(doi: str) -> str:
    if not doi:
        return ""
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi.strip("/")


def main() -> None:
    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # DOIs que têm abstract em ALGUMA linha do conjunto
    dois_com_abstract = set()
    for row in rows:
        doi = normalize_doi(row.get("doi", ""))
        if doi and row.get("abstract", "").strip():
            dois_com_abstract.add(doi)

    sem_abstract = [r for r in rows if not r.get("abstract", "").strip()]
    print(f"Total sem abstract: {len(sem_abstract)}")

    recuperaveis = 0
    sem_doi = 0
    irrecuperaveis = []

    for row in sem_abstract:
        doi = normalize_doi(row.get("doi", ""))
        if not doi:
            sem_doi += 1
            irrecuperaveis.append(row)
        elif doi in dois_com_abstract:
            recuperaveis += 1
        else:
            irrecuperaveis.append(row)

    print(f"Recuperáveis via dedup (mesmo DOI tem abstract em outra base): {recuperaveis}")
    print(f"Sem DOI (não dá pra checar duplicata): {sem_doi}")
    print(f"Irrecuperáveis (DOI existe, mas nenhuma cópia tem abstract): {len(irrecuperaveis) - sem_doi}")

    print("\nAmostra de irrecuperáveis (até 15):")
    for r in irrecuperaveis[:15]:
        print(f"  [{r.get('source_db')}] doi={r.get('doi') or '(sem DOI)'} | {r.get('title')}")


if __name__ == "__main__":
    main()