"""
Etapa final: Combination + Duplicate Removal, sobre o corpus JÁ
FILTRADO (pós Filter by Abstract). Esta é
a Combination "de verdade" do fluxo — a primeira vez que juntamos e
deduplicamos depois de cada base ter passado pelo próprio funil
completo (Impurity Removal -> Filter by Title -> Filter by Abstract),
igual ao artigo de referência.

Dedup por DOI normalizado, com fallback por título normalizado
(funções em connectors/base.py).

Rode: python pipeline/14_final_combination.py
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from connectors.base import Paper, PAPER_FIELDS, normalize_doi, normalize_title

IN_PATH = os.path.join("data", "processed", "after_abstract_filter.csv")
OUT_PATH = os.path.join("data", "processed", "final_combined_deduplicated.csv")


def load_rows() -> list[Paper]:
    papers = []
    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            year = row.get("year") or None
            try:
                year = int(year) if year else None
            except ValueError:
                year = None
            papers.append(
                Paper(
                    source_db=row.get("source_db", ""),
                    title=row.get("title", ""),
                    authors=row.get("authors", ""),
                    year=year,
                    venue=row.get("venue", ""),
                    doi=row.get("doi", ""),
                    abstract=row.get("abstract", ""),
                    url=row.get("url", ""),
                    raw_id=row.get("raw_id", ""),
                    query_used=row.get("query_used", ""),
                )
            )
    return papers


def deduplicate(papers: list[Paper]) -> tuple[list[Paper], int]:
    """
    Remove duplicatas por DOI (com fallback por título). Quando há mais
    de uma cópia do mesmo artigo, prioriza manter a que TEM abstract
    preenchido (útil já que sabemos que Scopus/T&F costumam vir sem).
    """
    seen: dict[str, Paper] = {}  # chave -> Paper já escolhido
    n_removed = 0

    for p in papers:
        doi_key = normalize_doi(p.doi)
        title_key = normalize_title(p.title)
        key = doi_key or title_key
        if not key:
            key = f"__no_key__{id(p)}"  # nunca colide, mantém tudo sem chave

        if key not in seen:
            seen[key] = p
            continue

        n_removed += 1
        existing = seen[key]
        # se o novo tem abstract e o que já está guardado não tem, troca
        if p.abstract.strip() and not existing.abstract.strip():
            seen[key] = p

    return list(seen.values()), n_removed


def main() -> None:
    papers = load_rows()

    by_source_before: dict[str, int] = {}
    for p in papers:
        by_source_before[p.source_db] = by_source_before.get(p.source_db, 0) + 1

    unique_papers, n_removed = deduplicate(papers)

    print("--- Estatísticas finais (Combination + Duplicate Removal) ---")
    print(f"{'Base':<20}{'Antes':>10}")
    for source, count in sorted(by_source_before.items()):
        print(f"{source:<20}{count:>10}")
    print("-" * 30)
    total_before = len(papers)
    pct = (n_removed / total_before * 100) if total_before else 0
    print(f"{'TOTAL (Combination)':<20}{total_before:>10}")
    print(f"{'Duplicatas removidas':<20}{n_removed:>10}  ({pct:.2f}% filtered)")
    print(f"{'TOTAL FINAL':<20}{len(unique_papers):>10}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PAPER_FIELDS)
        writer.writeheader()
        for p in unique_papers:
            writer.writerow(p.to_dict())

    print(f"\nSalvo em {OUT_PATH}")
    print("\nEste é o corpus FINAL da revisão sistemática, pronto pra leitura de full-text.")


if __name__ == "__main__":
    main()