"""
Junta todos os dados brutos (APIs + exportações manuais) SEM
deduplicar — (a deduplicação só acontece no fim, na etapa 14).

A ordem correta do fluxo (igual ao artigo de referência) é:
  Initial Search -> Impurity Removal -> Filter by Title ->
  Filter by Abstract -> Combination (só AQUI dedup) -> Duplicate Removal

Ou seja: cada base percorre seu próprio funil primeiro, e só no fim
tudo se junta com deduplicação. Este script gera o ponto de partida
para esse funil por base.
"""

import csv
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from connectors.base import Paper, PAPER_FIELDS
from ingest.manual_import import load_manual_exports

RAW_DIR = os.path.join("data", "raw")
OUT_PATH = os.path.join("data", "processed", "raw_pool_no_dedup.csv")


def load_raw_csvs(directory: str = RAW_DIR) -> list[Paper]:
    papers = []
    for path in glob.glob(os.path.join(directory, "*.csv")):
        with open(path, encoding="utf-8") as f:
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


def main() -> None:
    api_papers = load_raw_csvs()
    manual_papers = load_manual_exports()
    all_papers = api_papers + manual_papers

    by_source = {}
    for p in all_papers:
        by_source[p.source_db] = by_source.get(p.source_db, 0) + 1

    print("Pool bruto (sem dedup) por base:")
    for source, count in sorted(by_source.items()):
        print(f"  {source:<18}{count:>8}")
    print(f"  {'TOTAL':<18}{len(all_papers):>8}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PAPER_FIELDS)
        writer.writeheader()
        for p in all_papers:
            writer.writerow(p.to_dict())

    print(f"\nSalvo em {OUT_PATH}")


if __name__ == "__main__":
    main()