"""
Verifica o idioma de cada registro do corpus combinado, usando detecção
automática sobre o próprio texto (título + abstract combinados) — em
vez de confiar em metadado de idioma, que a maioria dos nossos
conectores não capturou.

DUAS CORREÇÕES importantes em relação à primeira versão deste script:

1. SEMENTE FIXA (DetectorFactory.seed = 0): a lib langdetect não é
   determinística por padrão — o mesmo texto pode dar resultados
   diferentes em execuções diferentes. Fixar a seed garante
   reprodutibilidade.

2. LIMIAR DE TAMANHO MAIS RIGOROSO (60 caracteres): testamos e
   confirmamos que textos curtos (títulos genéricos tipo "Index",
   "Abstract", "Policy Management") dão detecção ERRADA com "alta
   confiança" (ex: "Index" -> alemão, com 99.99% de confiança
   reportada) — ou seja, a confiança da lib não serve de filtro pra
   esses casos, só o tamanho do texto mesmo. Abaixo do limiar, o
   registro fica marcado como "unknown" em vez de arriscar um palpite
   errado. Repare que títulos assim de qualquer forma são candidatos a
   NÃO SEREM ARTIGOS DE VERDADE (índice, resumo de capa etc.) —
   cruze com o 02_check_publication_type.py pra esses casos.

Cobre 100% do corpus sem precisar re-baixar nada de nenhuma API.

Requer: langdetect (está no requirements.txt)
"""

import csv
import os

from langdetect import detect, DetectorFactory, LangDetectException

DetectorFactory.seed = 0  # reprodutibilidade

IN_PATH = os.path.join("data", "processed", "raw_pool_no_dedup.csv")
OUT_PATH = os.path.join("data", "processed", "language_check.csv")

MIN_TEXT_LEN = 60  # abaixo disso, não arrisca palpite -> "unknown"


def detect_language(title: str, abstract: str) -> str:
    text = f"{title} {abstract}".lower().strip()
    if len(text) < MIN_TEXT_LEN:
        return "unknown"
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"


def main() -> None:
    rows = []
    with open(IN_PATH, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames + ["detected_language"]
        for row in reader:
            lang = detect_language(row.get("title", ""), row.get("abstract", ""))
            row["detected_language"] = lang
            rows.append(row)

    by_lang = {}
    for row in rows:
        lang = row["detected_language"]
        by_lang[lang] = by_lang.get(lang, 0) + 1

    print(f"{'Idioma':<12}{'Quantidade':>12}{'%':>8}")
    print("-" * 32)
    total = len(rows)
    for lang, count in sorted(by_lang.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        print(f"{lang:<12}{count:>12}{pct:>7.1f}%")

    n_nao_ingles = total - by_lang.get("en", 0)
    n_unknown = by_lang.get("unknown", 0)
    n_outro_idioma = n_nao_ingles - n_unknown
    print(f"\nTotal de registros: {total}")
    print(f"'unknown' (texto curto demais, sem palpite): {n_unknown}")
    print(f"Detectados como outro idioma (não-inglês, com confiança): {n_outro_idioma}")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nArquivo completo (com a coluna detected_language) salvo em {OUT_PATH}")
    print("Revise os 'unknown' cruzando com 02_check_publication_type.py — muitos")
    print("provavelmente não são artigos de verdade (índice, capa, resumo solto etc).")


if __name__ == "__main__":
    main()