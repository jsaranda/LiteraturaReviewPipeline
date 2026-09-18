"""
Confere quantos registros do corpus PÓS Filter by Title têm abstract
preenchido, por base.

Rode: python pipeline/extras/check_abstract_coverage.py
"""

import csv
import os

IN_PATH = os.path.join("data", "processed", "after_title_filter.csv")


def main() -> None:
    by_source = {}

    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = row.get("source_db", "desconhecido")
            has_abstract = bool(row.get("abstract", "").strip())

            if source not in by_source:
                by_source[source] = {"total": 0, "com_abstract": 0}
            by_source[source]["total"] += 1
            if has_abstract:
                by_source[source]["com_abstract"] += 1

    print(f"{'Base':<20}{'Total':>10}{'Com abstract':>15}{'% cobertura':>13}")
    print("-" * 58)

    total_geral = 0
    total_com_abstract = 0
    for source, counts in sorted(by_source.items()):
        total = counts["total"]
        com = counts["com_abstract"]
        pct = (com / total * 100) if total else 0
        print(f"{source:<20}{total:>10}{com:>15}{pct:>12.1f}%")
        total_geral += total
        total_com_abstract += com

    print("-" * 58)
    pct_geral = (total_com_abstract / total_geral * 100) if total_geral else 0
    print(f"{'TOTAL':<20}{total_geral:>10}{total_com_abstract:>15}{pct_geral:>12.1f}%")

    sem_abstract = total_geral - total_com_abstract
    print(f"\nRegistros SEM abstract: {sem_abstract} ({100 - pct_geral:.1f}%)")


if __name__ == "__main__":
    main()