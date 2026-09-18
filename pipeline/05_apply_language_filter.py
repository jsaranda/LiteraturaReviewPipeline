"""
Aplica o corte por idioma (EC10) sobre o corpus já filtrado por tipo de
publicação (after_type_filter.csv), usando o resultado do
04_check_language.py.

Corta apenas os confirmados como outro idioma (ex: alemão, italiano,
francês) com texto longo o suficiente pra confiança real. Os marcados
como "unknown" (texto curto demais pra decidir) ficam de fora do corte
— não são confirmação de não-inglês, são apenas ambiguidade por falta
de texto.

Faz o cruzamento por DOI (com fallback por título normalizado, já que
alguns registros manuais não têm DOI).

Rode: python pipeline/05_apply_language_filter.py
"""

import csv
import os
import re

TYPE_FILTERED_PATH = os.path.join("data", "processed", "after_type_filter.csv")
LANGUAGE_CHECK_PATH = os.path.join("data", "processed", "language_check.csv")
OUT_PATH = os.path.join("data", "processed", "after_language_filter.csv")


def normalize_doi(doi: str) -> str:
    if not doi:
        return ""
    doi = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.startswith(prefix):
            doi = doi[len(prefix):]
    return doi.strip("/")


def normalize_title(title: str) -> str:
    t = title.lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def load_language_flags() -> tuple[dict, dict]:
    """Retorna {doi: idioma} e {titulo_normalizado: idioma}."""
    by_doi = {}
    by_title = {}
    with open(LANGUAGE_CHECK_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            lang = row.get("detected_language", "")
            doi_key = normalize_doi(row.get("doi", ""))
            title_key = normalize_title(row.get("title", ""))
            if doi_key:
                by_doi[doi_key] = lang
            if title_key:
                by_title[title_key] = lang
    return by_doi, by_title


def main() -> None:
    lang_by_doi, lang_by_title = load_language_flags()

    kept = []
    excluded_by_lang = {}

    with open(TYPE_FILTERED_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            doi_key = normalize_doi(row.get("doi", ""))
            title_key = normalize_title(row.get("title", ""))

            lang = lang_by_doi.get(doi_key) or lang_by_title.get(title_key, "en")

            if lang not in ("en", "unknown"):
                excluded_by_lang[lang] = excluded_by_lang.get(lang, 0) + 1
                continue

            kept.append(row)

    total_before = sum(excluded_by_lang.values()) + len(kept)
    print(f"Total antes deste filtro: {total_before}")
    print("\nExcluídos por idioma (confirmado, não-inglês):")
    for lang, count in sorted(excluded_by_lang.items(), key=lambda x: -x[1]):
        print(f"  {lang:<8}{count:>8}")

    total_excluded = sum(excluded_by_lang.values())
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