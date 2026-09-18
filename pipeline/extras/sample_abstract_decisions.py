"""
Sorteia uma amostra das decisões do Filter by Abstract, estratificada
por base e por decisão (include/exclude), para revisão manual.

Rode: python pipeline/extras/sample_abstract_decisions.py
"""

import csv
import os
import random

IN_PATH = os.path.join("data", "processed", "abstract_screening_results.csv")
N_PER_SOURCE_PER_DECISION = 3

random.seed(42)


def main() -> None:
    by_key = {}
    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            source = row.get("source_db", "")
            decision = row.get("abstract_decision", "")
            by_key.setdefault((source, decision), []).append(row)

    n = 1
    for (source, decision), rows in sorted(by_key.items()):
        if decision not in ("include", "exclude"):
            continue
        sample = random.sample(rows, min(N_PER_SOURCE_PER_DECISION, len(rows)))
        for row in sample:
            print(f"[{n}] [{source}] [{decision.upper()}] {row.get('title')}")
            print(f"    razão: {row.get('abstract_reason')}")
            abstract = row.get("abstract", "").strip()
            if abstract:
                print(f"    abstract: {abstract[:250]}...")
            else:
                print(f"    abstract: [SEM ABSTRACT]")
            print()
            n += 1


if __name__ == "__main__":
    main()