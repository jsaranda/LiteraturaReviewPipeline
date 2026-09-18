"""
Aplica a primeira leva de exclusões "objetivas" (Impurity Removal) sobre
o corpus combinado, usando os flags já calculados por
02_check_publication_type.py:

- pub_type em {book, proceedings, techreport, inbook, incollection}:
  livro inteiro, volume de conferência inteiro, relatório técnico não
  peer-reviewed, e capítulo de livro/coleção (EC1/EC2). Critério
  rígido de propósito: com um corpus de milhares de artigos, corta-se
  sem dó qualquer tipo ambíguo — inclusive os poucos artigos de
  conferência (ex: série Springer LNCS) que porventura estejam
  catalogados incorretamente como "inbook"/"incollection". Se o artigo
  está mal indexado na fonte, o corte é aceitável.
- suspect_title == SIM: erratum, corrigendum, retraction, editorial,
  book review, preface, issue information, etc. (EC1/EC2).

Ainda NÃO cruzado aqui: idioma não-inglês (04_check_language.py) — feito
numa etapa separada, já que precisa juntar por outro CSV.

Rode: python pipeline/03_apply_impurity_filters.py
"""

import csv
import os

IN_PATH = os.path.join("data", "processed", "publication_type_check.csv")
OUT_PATH = os.path.join("data", "processed", "after_type_filter.csv")

EXCLUDED_TYPES = {"book", "proceedings", "techreport", "inbook", "incollection"}


def main() -> None:
    kept = []
    excluded_by_type = {}
    excluded_suspect = 0

    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            pub_type = row.get("pub_type", "")
            is_suspect = row.get("suspect_title", "") == "SIM"

            if pub_type in EXCLUDED_TYPES:
                excluded_by_type[pub_type] = excluded_by_type.get(pub_type, 0) + 1
                continue
            if is_suspect:
                excluded_suspect += 1
                continue

            kept.append(row)

    total_before = sum(excluded_by_type.values()) + excluded_suspect + len(kept)

    print(f"Total antes deste filtro: {total_before}")
    print("\nExcluídos por tipo:")
    for t, count in sorted(excluded_by_type.items(), key=lambda x: -x[1]):
        print(f"  {t:<15}{count:>8}")
    print(f"\nExcluídos por título suspeito (erratum/editorial/etc.): {excluded_suspect}")

    total_excluded = sum(excluded_by_type.values()) + excluded_suspect
    print(f"\nTotal excluído nesta etapa: {total_excluded}")
    print(f"Total restante: {len(kept)}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)
    print(f"\nCorpus filtrado salvo em {OUT_PATH}")


if __name__ == "__main__":
    main()