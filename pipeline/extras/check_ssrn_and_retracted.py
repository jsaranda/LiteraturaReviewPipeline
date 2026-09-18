"""
Verifica dois problemas encontrados na revisão manual dos "irrecuperáveis
sem abstract":

1. Preprints do SSRN (doi.org/10.2139/ssrn.*) — não são peer-reviewed,
   violam IC1 do protocolo, independente de terem ou não abstract.
2. Títulos com "RETRACTED" que escaparam do filtro de título suspeito
   (o regex original só pegava "^retraction", não "^retracted").

Rode: python pipeline/extras/check_ssrn_and_retracted.py
"""

import csv
import os

IN_PATH = os.path.join("data", "processed", "after_title_filter.csv")


def main() -> None:
    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    ssrn = [r for r in rows if "10.2139/ssrn" in r.get("doi", "").lower()]
    retracted = [r for r in rows if "retract" in r.get("title", "").lower()]

    print(f"Total no corpus (pós Filter by Title): {len(rows)}")
    print(f"\nPreprints SSRN (não peer-reviewed, EC1): {len(ssrn)}")
    for r in ssrn[:20]:
        print(f"  [{r.get('source_db')}] {r.get('title')}")
    if len(ssrn) > 20:
        print(f"  ... e mais {len(ssrn) - 20}")

    print(f"\nTítulos contendo 'retract' (qualquer variante): {len(retracted)}")
    for r in retracted:
        print(f"  [{r.get('source_db')}] {r.get('title')}")


if __name__ == "__main__":
    main()