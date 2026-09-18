"""
Sorteia uma amostra de títulos, estratificada por base, para calibrar
o critério de exclusão do Filter by Title (e o prompt da etapa 06).

Rode: python pipeline/extras/sample_titles_for_calibration.py
"""

import csv
import os
import random

IN_PATH = os.path.join("data", "processed", "after_language_filter.csv")
N_PER_SOURCE = 6  # quantos títulos sortear de cada base

random.seed(42)  # reprodutível — mesma amostra toda vez que rodar


def main() -> None:
    by_source = {}
    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = row.get("source_db", "")
            by_source.setdefault(source, []).append(row)

    print(f"{'#':<4}{'Base':<18}Título\n")
    n = 1
    for source in sorted(by_source.keys()):
        rows = by_source[source]
        sample = random.sample(rows, min(N_PER_SOURCE, len(rows)))
        for row in sample:
            print(f"{n:<4}{source:<18}{row.get('title', '')}")
            n += 1


if __name__ == "__main__":
    main()