"""
Remove preprints do SSRN (não peer-reviewed, EC1) e artigos retratados
que escaparam do filtro de título suspeito original (variante
"RETRACTED" não coberta pelo regex anterior, que só pegava
"RETRACTION").

Rode: python pipeline/09_apply_ssrn_retracted_filter.py
"""

import csv
import os

IN_PATH = os.path.join("data", "processed", "after_title_filter.csv")
OUT_PATH = os.path.join("data", "processed", "after_title_filter_clean.csv")


def main() -> None:
    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    kept = []
    excluded_ssrn = 0
    excluded_retracted = 0

    for row in rows:
        doi = row.get("doi", "").lower()
        title = row.get("title", "").lower()

        if "10.2139/ssrn" in doi:
            excluded_ssrn += 1
            continue
        if "retract" in title:
            excluded_retracted += 1
            continue

        kept.append(row)

    print(f"Total antes: {len(rows)}")
    print(f"Excluídos (SSRN, não peer-reviewed): {excluded_ssrn}")
    print(f"Excluídos (retratados): {excluded_retracted}")
    print(f"Total restante: {len(kept)}")

    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    print(f"\nCorpus limpo salvo em {OUT_PATH}")


if __name__ == "__main__":
    main()