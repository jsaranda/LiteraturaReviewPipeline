"""
Aplica a decisão do Filter by Title (title_screening_results.csv),
mantendo só os registros com title_decision == "include".

Rode: python pipeline/08_apply_title_filter.py
"""

import csv
import os

IN_PATH = os.path.join("data", "processed", "title_screening_results.csv")
OUT_PATH = os.path.join("data", "processed", "after_title_filter.csv")


def main() -> None:
    kept = []
    excluded_by_source = {}

    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            source = row.get("source_db", "")
            if row.get("title_decision") == "include":
                kept.append(row)
            else:
                excluded_by_source[source] = excluded_by_source.get(source, 0) + 1

    print(f"Total mantido (include): {len(kept)}")
    print("\nExcluídos por base:")
    for source, count in sorted(excluded_by_source.items()):
        print(f"  {source:<18}{count:>8}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    print(f"\nCorpus filtrado salvo em {OUT_PATH}")


if __name__ == "__main__":
    main()